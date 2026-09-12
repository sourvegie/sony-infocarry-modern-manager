"""One persistent application-wide owner for device-write safety state.

The owner is deliberately neutral about candidate formats and terminal
verification.  It is the single shared boundary for the durable execution
claim, sender-start marker, and installation-wide indeterminate lock used by
every reachable device-changing operation.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Mapping
from uuid import uuid4

from .device_model_profile import DeviceModelProfile, VNW_V15_PROFILE
from .execution_claim_store import (
    ExecutionClaimRecord,
    ExecutionClaimStoreError,
    PersistentExecutionClaimStore,
    SenderInFlightHandle,
)
from .indeterminate_write_lock import (
    IndeterminateWriteLockError,
    IndeterminateWriteLockRecord,
    PersistentIndeterminateWriteLock,
)


class WriteSafetyBoundaryError(RuntimeError):
    """Raised when the shared persistent safety owner cannot proceed safely."""


class PersistentWriteSafetyOwner:
    """Own the shared installation-wide claim/marker/lock lifecycle.

    Candidate construction, authorization semantics, sender transport, and
    terminal verification remain operation-specific.  This service owns only
    the durable state transitions that every write route must share.
    """

    def __init__(
        self,
        *,
        execution_claim_store: PersistentExecutionClaimStore,
        indeterminate_write_lock: PersistentIndeterminateWriteLock,
        device_model_profile: DeviceModelProfile = VNW_V15_PROFILE,
    ) -> None:
        if not isinstance(execution_claim_store, PersistentExecutionClaimStore):
            raise WriteSafetyBoundaryError(
                "application-wide write safety requires a persistent execution claim store"
            )
        if not isinstance(indeterminate_write_lock, PersistentIndeterminateWriteLock):
            raise WriteSafetyBoundaryError(
                "application-wide write safety requires a persistent indeterminate-write lock"
            )
        if (
            not isinstance(device_model_profile, DeviceModelProfile)
            or device_model_profile != VNW_V15_PROFILE
            or not device_model_profile.transfer_capable
        ):
            raise WriteSafetyBoundaryError(
                "only the reviewed VNW-V15 model profile is actionable"
            )
        self.execution_claim_store = execution_claim_store
        self.indeterminate_write_lock = indeterminate_write_lock
        self.device_model_profile = device_model_profile

    def assert_execution_boundary_available(self) -> None:
        """Reject locks/markers and validate the durable claim-store schema.

        An abandoned marker is promoted to the existing global lock.  A
        marker paired with a separately cleared, incident-bound lock can be
        resolved after diagnostic recovery, matching the canonical Library
        behavior.
        """

        self.indeterminate_write_lock.assert_unlocked(
            self.device_model_profile.lock_key
        )
        self.execution_claim_store.validate_integrity()
        marker = self.execution_claim_store.read_sender_in_flight()
        if marker is None:
            return
        lock_record = self.indeterminate_write_lock.read(
            self.device_model_profile.lock_key
        )
        if (
            lock_record is not None
            and not lock_record.locked
            and lock_record.attempt_id == marker.attempt_id
            and lock_record.incident_id == marker.incident_id
        ):
            self.execution_claim_store.resolve_sender_after_diagnostic(
                marker,
                lock_record=lock_record,
            )
            return
        self.indeterminate_write_lock.record_indeterminate(
            reason=(
                "abandoned sender-start marker found after process restart; "
                "physical outcome is indeterminate"
            ),
            evidence_root=marker.evidence_root,
            model_key=self.device_model_profile.lock_key,
            incident_id=marker.incident_id,
            attempt_id=marker.attempt_id,
        )
        self.execution_claim_store.mark_sender_lock_recorded(marker)
        raise IndeterminateWriteLockError(
            "InfoCarry writes are globally locked after an abandoned sender-start boundary; "
            "read-only diagnosis is required"
        )

    def consume_execution_claim(
        self,
        bindings: Mapping[str, str],
    ) -> ExecutionClaimRecord:
        """Consume one reviewed hash-only operation claim."""

        if not isinstance(bindings, Mapping):
            raise ExecutionClaimStoreError("execution claim bindings must be a mapping")
        try:
            return self.execution_claim_store.consume(**dict(bindings))
        except TypeError as exc:
            raise ExecutionClaimStoreError(
                f"execution claim bindings are incomplete: {exc}"
            ) from exc

    def mark_sender_start(
        self,
        claim: ExecutionClaimRecord,
        *,
        attempt_id: str,
        evidence_root: str,
        operation_label: str,
    ) -> SenderInFlightHandle:
        """Commit the sender-start marker before invoking an operation sender."""

        if not operation_label or not isinstance(operation_label, str):
            raise WriteSafetyBoundaryError("write operation label is required")
        return self.execution_claim_store.mark_sender_in_flight(
            claim,
            attempt_id=attempt_id,
            incident_id=f"{operation_label}-{attempt_id}",
            evidence_root=evidence_root,
        )

    def resolve_sender_terminal(
        self,
        marker: SenderInFlightHandle,
        *,
        resolution: str,
    ) -> None:
        """Close a marker only after determinate or verified terminal handling."""

        self.execution_claim_store.resolve_sender_terminal(
            marker,
            resolution=resolution,
        )

    def record_indeterminate(
        self,
        error: BaseException,
        *,
        attempt_id: str,
        evidence_root: Path,
        operation_label: str,
    ) -> IndeterminateWriteLockRecord:
        """Persist the global lock and retain/promote the sender marker."""

        audit = getattr(error, "audit", {})
        if not isinstance(audit, Mapping):
            audit = {}
        claim_audit = audit.get("execution_claim")
        marker_audit = (
            claim_audit.get("sender_marker")
            if isinstance(claim_audit, Mapping)
            else None
        )
        incident_id = (
            marker_audit.get("incident_id")
            if isinstance(marker_audit, Mapping)
            else None
        )
        marker_attempt_id = (
            marker_audit.get("attempt_id")
            if isinstance(marker_audit, Mapping)
            else None
        )
        record = self.indeterminate_write_lock.record_indeterminate(
            reason=str(error),
            evidence_root=(
                marker_audit.get("evidence_root")
                if isinstance(marker_audit, Mapping)
                and isinstance(marker_audit.get("evidence_root"), str)
                else str(evidence_root)
            ),
            model_key=self.device_model_profile.lock_key,
            incident_id=incident_id or f"{operation_label}-{uuid4().hex}",
            attempt_id=marker_attempt_id or attempt_id,
        )
        if hasattr(error, "audit") and isinstance(getattr(error, "audit"), dict):
            getattr(error, "audit")["indeterminate_write_lock"] = record.to_dict()
        try:
            marker = self.execution_claim_store.read_sender_in_flight()
            if marker is not None:
                self.execution_claim_store.mark_sender_lock_recorded(marker)
        except ExecutionClaimStoreError:
            # The committed global lock is already fail-safe.  Retaining the
            # marker preserves the original incident for diagnostic binding.
            pass
        setattr(error, "indeterminate_write_lock_record", record)
        return record


def _application_state_root() -> Path:
    """Return the platform's installation/application state location."""

    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state"))
    return (base / "SonyInfoCarryModernManager").expanduser().resolve()


def create_default_application_write_safety_owner() -> PersistentWriteSafetyOwner:
    """Create the single default owner used by the desktop product path."""

    root = _application_state_root()
    return PersistentWriteSafetyOwner(
        execution_claim_store=PersistentExecutionClaimStore(
            root / "execution-claims.sqlite3"
        ),
        indeterminate_write_lock=PersistentIndeterminateWriteLock(
            root / "indeterminate-write-lock.json"
        ),
    )


__all__ = [
    "PersistentWriteSafetyOwner",
    "WriteSafetyBoundaryError",
    "create_default_application_write_safety_owner",
]
