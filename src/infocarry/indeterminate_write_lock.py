"""Persistent per-device indeterminate-write lock contract.

The store is intentionally independent of USB and is not imported by the
normal GUI/CLI or live runner in this milestone.  It gives the future R3
execution boundary a restart-safe contract: an ambiguous outcome leaves a
device locked until a complete read-only diagnostic backup and documented
recovery decision are recorded.  No method automatically clears a lock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping


INDETERMINATE_LOCK_FORMAT = "infocarry-indeterminate-write-lock-v1"
SUPPORTED_DEVICE_IDENTITY = ("0x054c", "0x001e")


class IndeterminateWriteLockError(ValueError):
    """Raised when a lock cannot be safely read, written, or cleared."""


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise IndeterminateWriteLockError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _device_key(identity: tuple[str, str]) -> str:
    if tuple(identity) != SUPPORTED_DEVICE_IDENTITY:
        raise IndeterminateWriteLockError("unsupported device identity for lock contract")
    return ":".join(identity)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _strict_json(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise IndeterminateWriteLockError(f"duplicate lock JSON key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise IndeterminateWriteLockError(f"indeterminate lock is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise IndeterminateWriteLockError("indeterminate lock must be an object")
    return value


def _empty_document() -> dict[str, Any]:
    return {"format": INDETERMINATE_LOCK_FORMAT, "devices": {}}


@dataclass(frozen=True)
class DiagnosticBackupEvidence:
    """Verified read-only backup evidence required before a lock can clear."""

    device_identity: tuple[str, str]
    backup_sha256: str
    object_count: int
    complete: bool = True
    read_only: bool = True
    integrity_verified: bool = True

    def __post_init__(self) -> None:
        _device_key(self.device_identity)
        _digest(self.backup_sha256, "diagnostic backup sha256")
        if (
            isinstance(self.object_count, bool)
            or not isinstance(self.object_count, int)
            or self.object_count <= 0
            or type(self.complete) is not bool
            or self.complete is not True
            or type(self.read_only) is not bool
            or self.read_only is not True
            or type(self.integrity_verified) is not bool
            or self.integrity_verified is not True
        ):
            raise IndeterminateWriteLockError(
                "diagnostic backup must be complete, read-only, and integrity-verified"
            )


@dataclass(frozen=True)
class IndeterminateWriteLockRecord:
    device_identity: tuple[str, str]
    state: str
    reason: str
    evidence_root: str
    recorded_at_utc: str
    diagnostic_backup_sha256: str | None = None
    recovery_decision: str | None = None
    decision_record_sha256: str | None = None

    def __post_init__(self) -> None:
        _device_key(self.device_identity)
        if self.state not in {"locked", "cleared"}:
            raise IndeterminateWriteLockError("invalid indeterminate lock state")
        if not self.reason or not self.evidence_root or not self.recorded_at_utc:
            raise IndeterminateWriteLockError("lock provenance is incomplete")
        if self.state == "cleared":
            _digest(self.diagnostic_backup_sha256, "diagnostic_backup_sha256")
            _digest(self.decision_record_sha256, "decision_record_sha256")
            if not self.recovery_decision:
                raise IndeterminateWriteLockError("recovery decision is required to clear a lock")

    @property
    def locked(self) -> bool:
        return self.state == "locked"

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_identity": list(self.device_identity),
            "state": self.state,
            "reason": self.reason,
            "evidence_root": self.evidence_root,
            "recorded_at_utc": self.recorded_at_utc,
            "diagnostic_backup_sha256": self.diagnostic_backup_sha256,
            "recovery_decision": self.recovery_decision,
            "decision_record_sha256": self.decision_record_sha256,
        }


class PersistentIndeterminateWriteLock:
    """Small atomic JSON store; callers must place it outside Git."""

    def __init__(self, path: Path):
        resolved = Path(path).expanduser().resolve()
        if resolved.exists() and resolved.is_dir():
            raise IndeterminateWriteLockError("lock path must be a file")
        self.path = resolved

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return _empty_document()
        document = _strict_json(self.path)
        if set(document) != {"format", "devices"}:
            raise IndeterminateWriteLockError("indeterminate lock schema differs")
        if document["format"] != INDETERMINATE_LOCK_FORMAT or not isinstance(
            document["devices"], dict
        ):
            raise IndeterminateWriteLockError("indeterminate lock format is unsupported")
        return document

    def _write(self, document: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", dir=self.path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(document, stream, ensure_ascii=True, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def read(self, device_identity: tuple[str, str] = SUPPORTED_DEVICE_IDENTITY) -> IndeterminateWriteLockRecord | None:
        key = _device_key(device_identity)
        entry = self._read()["devices"].get(key)
        if entry is None:
            return None
        if not isinstance(entry, Mapping):
            raise IndeterminateWriteLockError("device lock entry is malformed")
        try:
            return IndeterminateWriteLockRecord(
                device_identity=tuple(entry["device_identity"]),
                state=entry["state"],
                reason=entry["reason"],
                evidence_root=entry["evidence_root"],
                recorded_at_utc=entry["recorded_at_utc"],
                diagnostic_backup_sha256=entry.get("diagnostic_backup_sha256"),
                recovery_decision=entry.get("recovery_decision"),
                decision_record_sha256=entry.get("decision_record_sha256"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise IndeterminateWriteLockError("device lock entry is malformed") from exc

    def assert_unlocked(self, device_identity: tuple[str, str] = SUPPORTED_DEVICE_IDENTITY) -> None:
        record = self.read(device_identity)
        if record is not None and record.locked:
            raise IndeterminateWriteLockError(
                "device is locked after an indeterminate write; read-only diagnosis is required"
            )

    def record_indeterminate(
        self,
        *,
        reason: str,
        evidence_root: str,
        device_identity: tuple[str, str] = SUPPORTED_DEVICE_IDENTITY,
    ) -> IndeterminateWriteLockRecord:
        key = _device_key(device_identity)
        existing = self.read(device_identity)
        if existing is not None and existing.locked:
            return existing
        record = IndeterminateWriteLockRecord(
            device_identity=device_identity,
            state="locked",
            reason=reason,
            evidence_root=evidence_root,
            recorded_at_utc=_utc_now(),
        )
        document = self._read()
        document["devices"][key] = record.to_dict()
        self._write(document)
        return record

    def clear_after_diagnostic(
        self,
        *,
        diagnostic_backup: DiagnosticBackupEvidence,
        recovery_decision: str,
        decision_record_sha256: str,
        evidence_root: str,
        device_identity: tuple[str, str] = SUPPORTED_DEVICE_IDENTITY,
    ) -> IndeterminateWriteLockRecord:
        key = _device_key(device_identity)
        existing = self.read(device_identity)
        if existing is None or not existing.locked:
            raise IndeterminateWriteLockError("no active lock requires clearing")
        if not isinstance(diagnostic_backup, DiagnosticBackupEvidence):
            raise IndeterminateWriteLockError(
                "diagnostic backup must use the verified evidence contract"
            )
        if diagnostic_backup.device_identity != device_identity:
            raise IndeterminateWriteLockError("diagnostic backup device identity differs")
        record = IndeterminateWriteLockRecord(
            device_identity=device_identity,
            state="cleared",
            reason=existing.reason,
            evidence_root=evidence_root,
            recorded_at_utc=_utc_now(),
            diagnostic_backup_sha256=diagnostic_backup.backup_sha256,
            recovery_decision=recovery_decision,
            decision_record_sha256=decision_record_sha256,
        )
        document = self._read()
        document["devices"][key] = record.to_dict()
        self._write(document)
        return record


__all__ = [
    "DiagnosticBackupEvidence",
    "INDETERMINATE_LOCK_FORMAT",
    "IndeterminateWriteLockError",
    "IndeterminateWriteLockRecord",
    "PersistentIndeterminateWriteLock",
    "SUPPORTED_DEVICE_IDENTITY",
]
