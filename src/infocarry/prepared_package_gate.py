"""Authorization binding for the constrained prepared text package.

The records here are framework-independent and transport-free.  They are
deliberately more specific than the generic write authorization: a package
authorization cannot be reused for a root TXT add, replacement, delete, or a
different package.  Revalidation rechecks the fresh backup, source bytes,
exact fixed state, and every candidate-bound value before a future sender may
be considered.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Optional

from .capacity_evidence import (
    NATIVE_CAPACITY_EVIDENCE_SOURCE,
    NATIVE_CAPACITY_EVIDENCE_VERSION,
    NATIVE_CAPACITY_FIELD_OFFSET,
    NativeCapacityEvidence,
)
from .prepared_fixed_state import assess_prepared_fixed_state
from .prepared_package_candidate import (
    PreparedPackageCandidate,
    PreparedPackageCandidateError,
)
from .write_artifact import ProspectiveWriteTransaction
from .write_gate import DEFAULT_MAX_AGE_SECONDS, VerifiedBackup, verify_fresh_backup


PREPARED_PACKAGE_CONFIRMATION_PHRASE = "ADD ONE INFOCARRY TEXT PACKAGE"
PREPARED_PACKAGE_GATE_FORMAT = "infocarry-prepared-text-package-gate-v1"


class PreparedPackageGateError(RuntimeError):
    """Raised when package authorization or revalidation fails closed."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value.lower())
    ):
        raise PreparedPackageGateError(f"{label} must be a lowercase SHA-256 digest")
    return value.lower()


def _candidate_values(candidate: PreparedPackageCandidate) -> dict[str, Any]:
    if not isinstance(candidate, PreparedPackageCandidate):
        raise PreparedPackageGateError("candidate must be a PreparedPackageCandidate")
    audit = candidate.audit
    try:
        device = audit["device_identity"]
        source = audit["source"]
        package = audit["package"]
        baseline = audit["baseline"]
        candidate_data = audit["candidate"]
        allocation = audit["allocation"]
        transaction = audit["transaction"]
        identity = (device["vendor_id"], device["product_id"])
        values = {
            "device_identity": identity,
            "baseline_manifest_sha256": baseline["manifest_sha256"],
            "baseline_blob_sha256": baseline["blob_sha256"],
            "source_sha256": source["sha256"],
            "prepared_manifest_sha256": package["prepared_manifest_sha256"],
            "folder_path": package["folder_path"],
            "child_path": package["child_path"],
            "new_record_timestamp_be32": int(candidate_data["new_record_timestamp_be32"], 16),
            "candidate_blob_sha256": candidate_data["blob_sha256"],
            "candidate_transaction_sha256": transaction["sha256"],
            "fixed_state_sha256": tuple(transaction["fixed_state_hashes"]),
            "capacity_limit_bytes": allocation["capacity_limit_bytes"],
            "baseline_model_bytes": allocation["baseline_model_bytes"],
            "candidate_model_bytes": allocation["candidate_model_bytes"],
            "remaining_growth_bytes": allocation["remaining_growth_bytes"],
            "capacity_source": allocation["capacity_source"],
            # Compatibility aliases retained so old audit consumers fail
            # closed if either spelling is changed independently.
            "capacity_available_bytes": allocation["available_capacity_bytes"],
            "candidate_growth_bytes": allocation["complete_candidate_growth_bytes"],
            "capacity_result": allocation["capacity_result"],
            "capacity_response_sha256": None,
            "capacity_response_command": None,
            "capacity_response_field_offset": None,
            "capacity_evidence_source": None,
            "capacity_evidence_version": None,
            "native_capacity_evidence": False,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise PreparedPackageGateError("candidate audit is missing package binding fields") from exc

    native_evidence = candidate.native_capacity_evidence
    evidence_audit = audit.get("capacity_evidence")
    if native_evidence is None:
        if evidence_audit is not None:
            raise PreparedPackageGateError("candidate audit contains capacity evidence without a native response")
    else:
        if not isinstance(native_evidence, NativeCapacityEvidence):
            raise PreparedPackageGateError("candidate native capacity evidence is malformed")
        if not isinstance(evidence_audit, dict) or evidence_audit != native_evidence.to_dict():
            raise PreparedPackageGateError("candidate capacity evidence audit differs from the bound response")
        evidence = native_evidence.to_dict()
        try:
            backup_identity = tuple(int(value, 16) for value in identity)
        except (TypeError, ValueError) as exc:
            raise PreparedPackageGateError("candidate backup device identity is not hexadecimal VID/PID") from exc
        if native_evidence.device_identity != backup_identity:
            raise PreparedPackageGateError("candidate native capacity evidence device identity differs from backup")
        values.update(
            {
                "capacity_response_sha256": _require_digest(
                    evidence["raw_response_sha256"], "capacity response"
                ),
                "capacity_response_command": int(evidence["response_command"], 16),
                "capacity_response_field_offset": int(evidence["field_offset"], 16),
                "capacity_evidence_source": evidence["evidence_source"],
                "capacity_evidence_version": evidence["evidence_version"],
                "native_capacity_evidence": True,
            }
        )

    if any(not isinstance(value, str) or not value for value in (*identity, values["folder_path"], values["child_path"], values["capacity_result"], values["capacity_source"])):
        raise PreparedPackageGateError("candidate audit contains an invalid package binding value")
    for key in (
        "baseline_manifest_sha256",
        "baseline_blob_sha256",
        "source_sha256",
        "prepared_manifest_sha256",
        "candidate_blob_sha256",
        "candidate_transaction_sha256",
    ):
        values[key] = _require_digest(values[key], key)
    fixed = values["fixed_state_sha256"]
    if len(fixed) != 5:
        raise PreparedPackageGateError("candidate audit must bind five fixed-state hashes")
    values["fixed_state_sha256"] = tuple(_require_digest(value, "fixed-state hash") for value in fixed)
    capacity_fields = (
        "capacity_limit_bytes",
        "baseline_model_bytes",
        "candidate_model_bytes",
        "remaining_growth_bytes",
        "capacity_available_bytes",
        "candidate_growth_bytes",
    )
    if any(
        isinstance(values[key], bool)
        or not isinstance(values[key], int)
        or values[key] < 0
        for key in capacity_fields
    ) or (
        values["candidate_growth_bytes"] <= 0
        or values["candidate_model_bytes"] < values["baseline_model_bytes"]
        or values["candidate_model_bytes"] > values["capacity_limit_bytes"]
        or values["candidate_growth_bytes"] != values["candidate_model_bytes"] - values["baseline_model_bytes"]
        or values["remaining_growth_bytes"] != values["capacity_limit_bytes"] - values["baseline_model_bytes"]
        or values["capacity_available_bytes"] != values["remaining_growth_bytes"]
        or values["candidate_growth_bytes"] > values["remaining_growth_bytes"]
        or values["capacity_result"] != "sufficient"
    ):
        raise PreparedPackageGateError("candidate capacity binding is not a sufficient exact result")
    if values["native_capacity_evidence"] and (
        values["capacity_response_command"] != 0x0019
        or values["capacity_response_field_offset"] != NATIVE_CAPACITY_FIELD_OFFSET
        or values["capacity_evidence_source"] != NATIVE_CAPACITY_EVIDENCE_SOURCE
        or values["capacity_evidence_version"] != NATIVE_CAPACITY_EVIDENCE_VERSION
        or values["capacity_limit_bytes"] != native_evidence.capacity_limit_bytes
        or values["baseline_model_bytes"] != native_evidence.baseline_model_bytes
        or values["candidate_model_bytes"] != native_evidence.candidate_model_bytes
        or values["remaining_growth_bytes"] != native_evidence.remaining_growth_bytes
    ):
        raise PreparedPackageGateError("candidate native capacity evidence is inconsistent")
    if isinstance(values["new_record_timestamp_be32"], bool) or not 0 <= values["new_record_timestamp_be32"] <= 0xFFFFFFFF:
        raise PreparedPackageGateError("candidate timestamp binding is not a uint32")
    if _sha256(candidate.candidate_blob) != values["candidate_blob_sha256"]:
        raise PreparedPackageGateError("candidate audit blob hash does not match candidate bytes")
    if candidate.transaction.concatenated_sha256 != values["candidate_transaction_sha256"]:
        raise PreparedPackageGateError("candidate audit transaction hash does not match candidate bytes")
    if values["baseline_manifest_sha256"] != candidate.backup.manifest_sha256:
        raise PreparedPackageGateError("candidate audit baseline manifest does not match the verified backup")
    if values["baseline_blob_sha256"] != candidate.backup.blob_sha256:
        raise PreparedPackageGateError("candidate audit baseline blob does not match the verified backup")
    if values["source_sha256"] != candidate.package.source_sha256:
        raise PreparedPackageGateError("candidate audit source hash does not match the prepared package")
    if values["prepared_manifest_sha256"] != candidate.package.prepared_manifest_sha256:
        raise PreparedPackageGateError("candidate audit package manifest does not match the prepared package")
    if values["folder_path"] != candidate.package.target_folder_path or values["child_path"] != candidate.package.target_item_path:
        raise PreparedPackageGateError("candidate audit paths do not match the prepared package")
    if (
        values["capacity_limit_bytes"] != candidate.capacity_limit_bytes
        or values["baseline_model_bytes"] != candidate.baseline_model_bytes
        or values["candidate_model_bytes"] != candidate.candidate_model_bytes
        or values["remaining_growth_bytes"] != candidate.remaining_growth_bytes
        or values["capacity_source"] != candidate.capacity_source
        or values["capacity_available_bytes"] != candidate.available_capacity_bytes
    ):
        raise PreparedPackageGateError("candidate audit capacity does not match the candidate")
    expected_growth = len(candidate.candidate.data) - len(candidate.baseline.data)
    if values["candidate_growth_bytes"] != expected_growth or values["candidate_model_bytes"] != len(candidate.candidate.data) or values["baseline_model_bytes"] != len(candidate.baseline.data):
        raise PreparedPackageGateError("candidate audit growth does not match candidate bytes")
    folder_offsets = [
        offset
        for offset, path in candidate.candidate.paths.items()
        if path == ("root", candidate.package.folder_name)
    ]
    child_offsets = [
        offset
        for offset, path in candidate.candidate.paths.items()
        if path == ("root", candidate.package.folder_name, candidate.package.item.name[:-4])
    ]
    if len(folder_offsets) != 1 or len(child_offsets) != 1:
        raise PreparedPackageGateError("candidate does not contain exactly the authorized folder and child")
    folder_record = candidate.candidate.record_at(folder_offsets[0])
    child_record = candidate.candidate.record_at(child_offsets[0])
    try:
        leading_record = candidate.candidate.record_at(folder_record.offset + 0x40)
    except Exception as exc:
        raise PreparedPackageGateError("candidate folder leading marker is unavailable") from exc
    if (
        folder_record.timestamp_be32 != values["new_record_timestamp_be32"]
        or leading_record.kind != "directory"
        or leading_record.name != ".."
        or leading_record.timestamp_be32 != values["new_record_timestamp_be32"]
        or child_record.timestamp_be32 != values["new_record_timestamp_be32"]
    ):
        raise PreparedPackageGateError("candidate new-record timestamps do not match authorization")
    actual_fixed = tuple(_sha256(block) for block in candidate.fixed_state.raw_blocks)
    if actual_fixed != values["fixed_state_sha256"]:
        raise PreparedPackageGateError("candidate audit fixed-state hashes do not match preserved bytes")
    return values


@dataclass(frozen=True)
class PreparedPackageAuthorization:
    """Exact no-USB authorization for one constrained package candidate."""

    device_identity: tuple[str, str]
    baseline_manifest_sha256: str
    baseline_blob_sha256: str
    source_sha256: str
    prepared_manifest_sha256: str
    folder_path: str
    child_path: str
    new_record_timestamp_be32: int
    candidate_blob_sha256: str
    candidate_transaction_sha256: str
    fixed_state_sha256: tuple[str, ...]
    capacity_limit_bytes: int
    baseline_model_bytes: int
    candidate_model_bytes: int
    remaining_growth_bytes: int
    capacity_source: str
    capacity_available_bytes: int
    candidate_growth_bytes: int
    capacity_result: str
    confirmation_phrase: str
    capacity_response_sha256: Optional[str] = None
    capacity_response_command: Optional[int] = None
    capacity_response_field_offset: Optional[int] = None
    capacity_evidence_source: Optional[str] = None
    capacity_evidence_version: Optional[str] = None
    live_eligible: bool = False
    native_capacity_evidence: bool = False

    def __post_init__(self) -> None:
        if self.confirmation_phrase != PREPARED_PACKAGE_CONFIRMATION_PHRASE:
            raise PreparedPackageGateError("authorization does not contain the package confirmation phrase")
        if len(self.device_identity) != 2 or any(not isinstance(value, str) or not value for value in self.device_identity):
            raise PreparedPackageGateError("authorization device identity is invalid")
        if len(self.fixed_state_sha256) != 5:
            raise PreparedPackageGateError("authorization must bind five fixed-state hashes")
        for label, value in (
            ("baseline manifest", self.baseline_manifest_sha256),
            ("baseline blob", self.baseline_blob_sha256),
            ("source", self.source_sha256),
            ("prepared manifest", self.prepared_manifest_sha256),
            ("candidate blob", self.candidate_blob_sha256),
            ("candidate transaction", self.candidate_transaction_sha256),
        ):
            _require_digest(value, label)
        for index, value in enumerate(self.fixed_state_sha256):
            _require_digest(value, f"fixed-state hash {index}")
        if isinstance(self.new_record_timestamp_be32, bool) or not 0 <= self.new_record_timestamp_be32 <= 0xFFFFFFFF:
            raise PreparedPackageGateError("authorized timestamp must fit uint32")
        if not isinstance(self.capacity_source, str) or not self.capacity_source:
            raise PreparedPackageGateError("authorization capacity source is invalid")
        if self.capacity_result != "sufficient":
            raise PreparedPackageGateError("authorization requires a sufficient capacity result")
        capacity_fields = (
            self.capacity_limit_bytes,
            self.baseline_model_bytes,
            self.candidate_model_bytes,
            self.remaining_growth_bytes,
            self.capacity_available_bytes,
            self.candidate_growth_bytes,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in capacity_fields):
            raise PreparedPackageGateError("authorization capacity values are inconsistent")
        if (
            self.candidate_growth_bytes <= 0
            or self.candidate_model_bytes < self.baseline_model_bytes
            or self.candidate_model_bytes > self.capacity_limit_bytes
            or self.candidate_growth_bytes != self.candidate_model_bytes - self.baseline_model_bytes
            or self.remaining_growth_bytes != self.capacity_limit_bytes - self.baseline_model_bytes
            or self.capacity_available_bytes != self.remaining_growth_bytes
            or self.candidate_growth_bytes > self.remaining_growth_bytes
        ):
            raise PreparedPackageGateError("authorization capacity values are inconsistent")
        evidence_values = (
            self.capacity_response_sha256,
            self.capacity_response_command,
            self.capacity_response_field_offset,
            self.capacity_evidence_source,
            self.capacity_evidence_version,
        )
        if self.live_eligible and any(value is None for value in evidence_values):
            raise PreparedPackageGateError("live package authorization requires native 0x0019 capacity evidence")
        if self.live_eligible and not self.native_capacity_evidence:
            raise PreparedPackageGateError("live package authorization cannot use compatibility capacity evidence")
        if any(value is not None for value in evidence_values):
            if self.capacity_response_sha256 is None:
                raise PreparedPackageGateError("capacity response hash is missing")
            _require_digest(self.capacity_response_sha256, "capacity response")
            if self.capacity_response_command != 0x0019 or self.capacity_response_field_offset != NATIVE_CAPACITY_FIELD_OFFSET:
                raise PreparedPackageGateError("authorization capacity response binding is not 0x0019 +0x08")
            if self.capacity_evidence_source != NATIVE_CAPACITY_EVIDENCE_SOURCE or self.capacity_evidence_version != NATIVE_CAPACITY_EVIDENCE_VERSION:
                raise PreparedPackageGateError("authorization capacity evidence source is not native parsed 0x0019")

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": PREPARED_PACKAGE_GATE_FORMAT,
            "state": "authorized_for_future_writer_only",
            "usb_transmission_performed": False,
            "operation": "add_one_root_folder_one_txt_package",
            "device": {
                "vendor_id": self.device_identity[0],
                "product_id": self.device_identity[1],
            },
            "baseline_manifest_sha256": self.baseline_manifest_sha256,
            "baseline_blob_sha256": self.baseline_blob_sha256,
            "source_sha256": self.source_sha256,
            "prepared_manifest_sha256": self.prepared_manifest_sha256,
            "folder_path": self.folder_path,
            "child_path": self.child_path,
            "new_record_timestamp_be32": f"0x{self.new_record_timestamp_be32:08x}",
            "candidate_blob_sha256": self.candidate_blob_sha256,
            "candidate_transaction_sha256": self.candidate_transaction_sha256,
            "fixed_state_sha256": list(self.fixed_state_sha256),
            "capacity_limit_bytes": self.capacity_limit_bytes,
            "baseline_model_bytes": self.baseline_model_bytes,
            "candidate_model_bytes": self.candidate_model_bytes,
            "remaining_growth_bytes": self.remaining_growth_bytes,
            "capacity_source": self.capacity_source,
            "capacity_available_bytes": self.capacity_available_bytes,
            "candidate_growth_bytes": self.candidate_growth_bytes,
            "capacity_result": self.capacity_result,
            "capacity_response_sha256": self.capacity_response_sha256,
            "capacity_response_command": self.capacity_response_command,
            "capacity_response_field_offset": self.capacity_response_field_offset,
            "capacity_evidence_source": self.capacity_evidence_source,
            "capacity_evidence_version": self.capacity_evidence_version,
            "live_eligible": self.live_eligible,
            "native_capacity_evidence": self.native_capacity_evidence,
            "confirmation_phrase": self.confirmation_phrase,
        }

    def require_same_candidate(self, candidate: PreparedPackageCandidate) -> None:
        actual = _candidate_values(candidate)
        expected = {
            "device_identity": self.device_identity,
            "baseline_manifest_sha256": self.baseline_manifest_sha256,
            "baseline_blob_sha256": self.baseline_blob_sha256,
            "source_sha256": self.source_sha256,
            "prepared_manifest_sha256": self.prepared_manifest_sha256,
            "folder_path": self.folder_path,
            "child_path": self.child_path,
            "new_record_timestamp_be32": self.new_record_timestamp_be32,
            "candidate_blob_sha256": self.candidate_blob_sha256,
            "candidate_transaction_sha256": self.candidate_transaction_sha256,
            "fixed_state_sha256": self.fixed_state_sha256,
            "capacity_limit_bytes": self.capacity_limit_bytes,
            "baseline_model_bytes": self.baseline_model_bytes,
            "candidate_model_bytes": self.candidate_model_bytes,
            "remaining_growth_bytes": self.remaining_growth_bytes,
            "capacity_source": self.capacity_source,
            "capacity_available_bytes": self.capacity_available_bytes,
            "candidate_growth_bytes": self.candidate_growth_bytes,
            "capacity_result": self.capacity_result,
            "capacity_response_sha256": self.capacity_response_sha256,
            "capacity_response_command": self.capacity_response_command,
            "capacity_response_field_offset": self.capacity_response_field_offset,
            "capacity_evidence_source": self.capacity_evidence_source,
            "capacity_evidence_version": self.capacity_evidence_version,
        }
        for key, value in expected.items():
            if actual[key] != value:
                raise PreparedPackageGateError(f"candidate {key} differs from authorization")
        if self.live_eligible and not actual["native_capacity_evidence"]:
            raise PreparedPackageGateError("live authorization cannot use compatibility capacity evidence")

    def revalidate(
        self,
        candidate: PreparedPackageCandidate,
        *,
        now: Optional[datetime] = None,
        max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
    ) -> VerifiedBackup:
        """Recheck every binding immediately before a future sender."""

        self.require_same_candidate(candidate)
        try:
            current_source = candidate.package.source_path.read_bytes()
        except OSError as exc:
            raise PreparedPackageGateError(f"bound package source could not be reread: {exc}") from exc
        if _sha256(current_source) != self.source_sha256 or current_source != candidate.package.source_bytes:
            raise PreparedPackageGateError("bound package source bytes changed")
        try:
            verified = verify_fresh_backup(
                candidate.backup.directory,
                now=now,
                max_age_seconds=max_age_seconds,
            )
        except Exception as exc:
            raise PreparedPackageGateError(f"bound baseline backup failed revalidation: {exc}") from exc
        if verified.device_identity != self.device_identity:
            raise PreparedPackageGateError("bound device identity changed")
        if verified.manifest_sha256 != self.baseline_manifest_sha256:
            raise PreparedPackageGateError("bound baseline manifest changed")
        if verified.blob_sha256 != self.baseline_blob_sha256:
            raise PreparedPackageGateError("bound baseline blob changed")
        assessment = assess_prepared_fixed_state(verified)
        try:
            snapshot = assessment.require_supported()
        except Exception as exc:
            raise PreparedPackageGateError(f"bound fixed state is no longer eligible: {exc}") from exc
        if tuple(_sha256(block) for block in snapshot.raw_blocks) != self.fixed_state_sha256:
            raise PreparedPackageGateError("bound fixed-state bytes changed")
        return verified


@dataclass(frozen=True)
class PreparedPackageTransportAuthorization:
    """Sender adapter that carries no USB handle and binds one package."""

    authorization: PreparedPackageAuthorization
    candidate: PreparedPackageCandidate
    now: Optional[datetime] = None
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS

    def __post_init__(self) -> None:
        if not isinstance(self.authorization, PreparedPackageAuthorization):
            raise PreparedPackageGateError("sender requires package authorization")
        self.authorization.require_same_candidate(self.candidate)

    def revalidate(self, transaction: ProspectiveWriteTransaction) -> None:
        if not isinstance(transaction, ProspectiveWriteTransaction):
            raise PreparedPackageGateError("sender transaction is not prospective")
        if transaction.concatenated_sha256 != self.authorization.candidate_transaction_sha256:
            raise PreparedPackageGateError("sender transaction differs from package authorization")
        self.authorization.revalidate(
            self.candidate,
            now=self.now,
            max_age_seconds=self.max_age_seconds,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": "authorized_for_future_writer_only",
            "usb_transmission_performed": False,
            "binding": self.authorization.to_dict(),
            "candidate_transaction_sha256": self.candidate.transaction_sha256,
            "live_eligible": self.authorization.live_eligible,
        }


def authorize_prepared_package(
    candidate: PreparedPackageCandidate,
    *,
    confirmation: str,
    require_native_capacity_evidence: bool = False,
) -> PreparedPackageAuthorization:
    """Authorize one candidate only after the exact package phrase."""

    if confirmation != PREPARED_PACKAGE_CONFIRMATION_PHRASE:
        raise PreparedPackageGateError("package confirmation phrase was not accepted")
    values = _candidate_values(candidate)
    if require_native_capacity_evidence and not values["native_capacity_evidence"]:
        raise PreparedPackageGateError(
            "live package authorization requires verified parsed 0x0019 capacity evidence"
        )
    authorization = PreparedPackageAuthorization(
        **values,
        confirmation_phrase=confirmation,
        live_eligible=require_native_capacity_evidence,
    )
    authorization.require_same_candidate(candidate)
    return authorization


def bind_prepared_package_sender(
    authorization: PreparedPackageAuthorization,
    candidate: PreparedPackageCandidate,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> PreparedPackageTransportAuthorization:
    """Create a no-USB sender adapter after immediate revalidation."""

    adapter = PreparedPackageTransportAuthorization(
        authorization=authorization,
        candidate=candidate,
        now=now,
        max_age_seconds=max_age_seconds,
    )
    adapter.revalidate(candidate.transaction)
    return adapter


__all__ = [
    "PREPARED_PACKAGE_CONFIRMATION_PHRASE",
    "PREPARED_PACKAGE_GATE_FORMAT",
    "PreparedPackageAuthorization",
    "PreparedPackageGateError",
    "PreparedPackageTransportAuthorization",
    "authorize_prepared_package",
    "bind_prepared_package_sender",
]
