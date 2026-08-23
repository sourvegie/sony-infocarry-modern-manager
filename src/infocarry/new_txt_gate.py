"""Offline operation binding for a future new-root-TXT writer.

This module is intentionally framework-independent.  It binds one generated
candidate to the exact device identity, verified baseline, source bytes,
target path, and candidate transaction.  It authorizes no transport and is
not imported by the normal CLI or desktop workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Optional

from .new_txt import NewTxtAddResult
from .write_gate import (
    DEFAULT_MAX_AGE_SECONDS,
    PostWriteVerification,
    verify_fresh_backup,
    verify_post_write_backup,
)
from .write_artifact import ProspectiveWriteTransaction


NEW_ROOT_TXT_CONFIRMATION_PHRASE = "ADD INFOCARRY TXT"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _candidate_binding_values(
    result: NewTxtAddResult,
) -> tuple[tuple[str, str], str, str, str, str, str, str]:
    """Validate audit identity against the actual candidate bytes."""

    if not isinstance(result, NewTxtAddResult):
        raise NewTxtGateError("candidate must be a NewTxtAddResult")
    audit = result.audit
    try:
        device = audit["device_identity"]
        source = audit["source"]
        target = audit["target"]
        baseline = audit["baseline"]
        candidate = audit["candidate"]
        identity = (device["vendor_id"], device["product_id"])
        values = (
            baseline["manifest_sha256"],
            baseline["blob_sha256"],
            source["sha256"],
            target["path"],
            candidate["blob_sha256"],
            candidate["transaction_sha256"],
        )
    except (KeyError, TypeError) as exc:
        raise NewTxtGateError("candidate audit is missing new-TXT binding fields") from exc
    if any(not isinstance(value, str) or not value for value in (*identity, *values)):
        raise NewTxtGateError("candidate audit contains an invalid new-TXT binding value")
    actual_blob_hash = _sha256(result.transaction.ranges[4] + result.transaction.ranges[7])
    if actual_blob_hash != values[4]:
        raise NewTxtGateError("candidate audit blob hash does not match candidate bytes")
    if result.transaction.concatenated_sha256 != values[5]:
        raise NewTxtGateError("candidate audit transaction hash does not match candidate bytes")
    return identity, *values


class NewTxtGateError(RuntimeError):
    """Raised when a new-TXT operation binding is unsafe or incomplete."""


@dataclass(frozen=True)
class NewTxtAddAuthorization:
    """A candidate-bound, no-USB authorization for a future writer."""

    device_identity: tuple[str, str]
    baseline_manifest_sha256: str
    baseline_blob_sha256: str
    source_sha256: str
    target_path: str
    candidate_blob_sha256: str
    candidate_transaction_sha256: str
    confirmation_phrase: str

    def __post_init__(self) -> None:
        if self.confirmation_phrase != NEW_ROOT_TXT_CONFIRMATION_PHRASE:
            raise NewTxtGateError("authorization does not contain the new-TXT confirmation phrase")

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "infocarry-new-root-txt-gate-v1",
            "state": "authorized_for_future_writer_only",
            "usb_transmission_performed": False,
            "operation": "add_one_root_txt",
            "device": {
                "vendor_id": self.device_identity[0],
                "product_id": self.device_identity[1],
            },
            "baseline_manifest_sha256": self.baseline_manifest_sha256,
            "baseline_blob_sha256": self.baseline_blob_sha256,
            "source_sha256": self.source_sha256,
            "target_path": self.target_path,
            "candidate_blob_sha256": self.candidate_blob_sha256,
            "candidate_transaction_sha256": self.candidate_transaction_sha256,
            "confirmation_phrase": self.confirmation_phrase,
        }

    def require_same_candidate(self, result: NewTxtAddResult) -> None:
        """Reject any candidate whose identity or bytes differ from binding."""

        if not isinstance(result, NewTxtAddResult):
            raise NewTxtGateError("candidate must be a NewTxtAddResult")
        audit = result.audit
        device = audit.get("device_identity")
        source = audit.get("source")
        target = audit.get("target")
        baseline = audit.get("baseline")
        candidate = audit.get("candidate")
        if not all(isinstance(value, dict) for value in (device, source, target, baseline, candidate)):
            raise NewTxtGateError("candidate audit is missing operation identity fields")
        actual_identity = (device.get("vendor_id"), device.get("product_id"))
        if actual_identity != self.device_identity:
            raise NewTxtGateError("candidate device identity differs from authorization")
        checks = (
            (baseline.get("manifest_sha256"), self.baseline_manifest_sha256, "baseline manifest"),
            (baseline.get("blob_sha256"), self.baseline_blob_sha256, "baseline blob"),
            (source.get("sha256"), self.source_sha256, "source"),
            (target.get("path"), self.target_path, "target path"),
            (candidate.get("blob_sha256"), self.candidate_blob_sha256, "candidate blob"),
            (candidate.get("transaction_sha256"), self.candidate_transaction_sha256, "candidate transaction"),
        )
        for actual, expected, label in checks:
            if actual != expected:
                raise NewTxtGateError(f"candidate {label} differs from authorization")

    def revalidate(
        self,
        result: NewTxtAddResult,
        backup_directory: Path,
        source_path: Path,
        *,
        now: Optional[datetime] = None,
        max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
    ) -> None:
        """Recheck the bound baseline and source before any future transport."""

        self.require_same_candidate(result)
        revalidate_new_txt_inputs(
            result,
            backup_directory,
            source_path,
            now=now,
            max_age_seconds=max_age_seconds,
        )

    def verify_post_add_backup(
        self,
        result: NewTxtAddResult,
        backup_directory: Path,
        source_path: Path,
        post_add_directory: Path,
        *,
        now: Optional[datetime] = None,
        max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
    ) -> PostWriteVerification:
        """Independently verify one candidate against a complete read-back.

        The caller supplies the preserved post-add archive. This method never
        captures, sends, retries, or opens a transport; it delegates the
        fixed-state, dynamic-blob, and unrelated-object checks to the existing
        USB-neutral verifier.
        """

        self.revalidate(
            result,
            backup_directory,
            source_path,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        try:
            before = verify_fresh_backup(
                backup_directory,
                now=now,
                max_age_seconds=max_age_seconds,
            )
            return verify_post_write_backup(
                before,
                post_add_directory,
                result.transaction,
                now=now,
                max_age_seconds=max_age_seconds,
            )
        except Exception as exc:
            raise NewTxtGateError(
                f"new-TXT post-add read-back verification failed; no retry attempted: {exc}"
            ) from exc


@dataclass(frozen=True)
class NewTxtTransportAuthorization:
    """Sender-compatible adapter for one already-bound new-TXT candidate.

    The adapter exists only so the generic sender can call ``revalidate``
    immediately before its first control request.  It carries no USB handle,
    endpoint, or transport implementation.
    """

    binding: NewTxtAddAuthorization
    result: NewTxtAddResult
    backup_directory: Path
    source_path: Path
    now: Optional[datetime] = None
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS

    def __post_init__(self) -> None:
        if not isinstance(self.binding, NewTxtAddAuthorization):
            raise NewTxtGateError("sender binding requires a NewTxtAddAuthorization")
        if not isinstance(self.result, NewTxtAddResult):
            raise NewTxtGateError("sender binding requires a NewTxtAddResult")
        self.binding.require_same_candidate(self.result)

    def revalidate(self, transaction: ProspectiveWriteTransaction) -> None:
        """Recheck exact transaction, baseline, device identity, and source."""

        if transaction is not self.result.transaction:
            if not isinstance(transaction, ProspectiveWriteTransaction):
                raise NewTxtGateError("sender candidate is not a prospective transaction")
            if transaction.concatenated_sha256 != self.result.transaction.concatenated_sha256:
                raise NewTxtGateError("sender transaction differs from the bound candidate")
        self.binding.revalidate(
            self.result,
            self.backup_directory,
            self.source_path,
            now=self.now,
            max_age_seconds=self.max_age_seconds,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": "authorized_for_future_writer_only",
            "usb_transmission_performed": False,
            "binding": self.binding.to_dict(),
            "candidate_transaction_sha256": self.result.transaction.concatenated_sha256,
        }


def bind_new_txt_sender(
    authorization: NewTxtAddAuthorization,
    result: NewTxtAddResult,
    backup_directory: Path,
    source_path: Path,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> NewTxtTransportAuthorization:
    """Create a no-USB sender adapter after checking the candidate binding."""

    adapter = NewTxtTransportAuthorization(
        binding=authorization,
        result=result,
        backup_directory=Path(backup_directory).expanduser().resolve(),
        source_path=Path(source_path).expanduser().resolve(),
        now=now,
        max_age_seconds=max_age_seconds,
    )
    adapter.revalidate(result.transaction)
    return adapter


def revalidate_new_txt_inputs(
    result: NewTxtAddResult,
    backup_directory: Path,
    source_path: Path,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> None:
    """Recheck identity, complete baseline, source, and candidate before auth."""

    identity, manifest_hash, blob_hash, source_hash, _target, _candidate_blob, _transaction = (
        _candidate_binding_values(result)
    )
    try:
        backup = verify_fresh_backup(
            backup_directory,
            now=now,
            max_age_seconds=max_age_seconds,
        )
    except Exception as exc:
        raise NewTxtGateError(f"bound baseline backup failed revalidation: {exc}") from exc
    if backup.device_identity != identity:
        raise NewTxtGateError("bound device identity changed")
    if backup.manifest_sha256 != manifest_hash:
        raise NewTxtGateError("bound baseline manifest changed")
    if backup.blob_sha256 != blob_hash:
        raise NewTxtGateError("bound baseline blob changed")
    try:
        source_bytes = Path(source_path).expanduser().resolve().read_bytes()
    except OSError as exc:
        raise NewTxtGateError(f"bound source could not be reread: {exc}") from exc
    if _sha256(source_bytes) != source_hash:
        raise NewTxtGateError("bound source bytes changed")


def authorize_new_txt_add(
    result: NewTxtAddResult,
    *,
    confirmation: str,
) -> NewTxtAddAuthorization:
    """Bind one candidate only after the exact operation-specific phrase."""

    if confirmation != NEW_ROOT_TXT_CONFIRMATION_PHRASE:
        raise NewTxtGateError("new-TXT confirmation phrase was not accepted")
    identity, *values = _candidate_binding_values(result)
    authorization = NewTxtAddAuthorization(
        device_identity=identity,
        baseline_manifest_sha256=values[0],
        baseline_blob_sha256=values[1],
        source_sha256=values[2],
        target_path=values[3],
        candidate_blob_sha256=values[4],
        candidate_transaction_sha256=values[5],
        confirmation_phrase=confirmation,
    )
    authorization.require_same_candidate(result)
    return authorization


__all__ = [
    "NEW_ROOT_TXT_CONFIRMATION_PHRASE",
    "NewTxtAddAuthorization",
    "NewTxtGateError",
    "NewTxtTransportAuthorization",
    "authorize_new_txt_add",
    "bind_new_txt_sender",
    "revalidate_new_txt_inputs",
]
