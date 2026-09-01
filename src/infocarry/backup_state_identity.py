"""Canonical identity for a completely verified raw device backup.

The raw objects in a backup are device-state evidence.  The archive path,
capture timestamps, and the hash of the manifest are acquisition provenance.
They are retained by :mod:`infocarry.write_gate` and the evidence manifests,
but are intentionally not part of this identity.  This distinction lets two
independently captured archives of the same device state compare equal
without normalizing or rewriting either archive.

This module is deliberately framework-independent and does not open USB or
construct a write.  ``derive_backup_state_identity`` re-runs the existing
complete-backup verifier before deriving an identity, so callers cannot use
an unchecked archive as a state binding.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .backup import COMMAND_BACKUP_BLOB, FIXED_BACKUP_OBJECTS, FIXED_RESPONSE_LENGTH
from .write_gate import VerifiedBackup, verify_fresh_backup


BACKUP_STATE_IDENTITY_FORMAT = "infocarry-verified-backup-state-identity-v1"
_EXPECTED_PROTOCOL = {
    "command_header": "uint16le command + uint32le requested_length",
    "direction": "device-to-host",
    "source": "static analysis of VicTwo.dll",
}
_FILENAME_WITH_COMMAND = re.compile(
    r"^object-(?P<sequence>[0-9]{2})-command-(?P<command>[0-9a-f]{4})\.bin$"
)
_FILENAME_WITHOUT_COMMAND = re.compile(r"^object-(?P<sequence>[0-9]{2})\.bin$")


class BackupStateIdentityError(ValueError):
    """Raised when a backup cannot produce a canonical state identity."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise BackupStateIdentityError(f"{label} is not a lowercase SHA-256 digest")
    return value


def _read_manifest(backup: VerifiedBackup) -> dict[str, Any]:
    path = Path(backup.directory) / "manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupStateIdentityError(f"could not read verified backup manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise BackupStateIdentityError("verified backup manifest is not an object")
    return value


@dataclass(frozen=True)
class BackupObjectStateIdentity:
    """One ordered raw object included in a device-state identity."""

    sequence: int
    key: str
    role: str
    command: str
    filename: str
    requested_length: int
    length: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "key": self.key,
            "role": self.role,
            "command": self.command,
            "filename": self.filename,
            "requested_length": self.requested_length,
            "length": self.length,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class BackupStateIdentity:
    """Immutable, provenance-independent identity of a verified device state."""

    device_identity: tuple[tuple[str, str], ...]
    protocol_identity: tuple[tuple[str, str], ...]
    objects: tuple[BackupObjectStateIdentity, ...]
    dynamic_blob_length: int
    dynamic_blob_sha256: str
    fixed_state_sha256: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": BACKUP_STATE_IDENTITY_FORMAT,
            "device_identity": {key: value for key, value in self.device_identity},
            "protocol_identity": {key: value for key, value in self.protocol_identity},
            "objects": [item.to_dict() for item in self.objects],
            "dynamic_blob": {
                "length": self.dynamic_blob_length,
                "sha256": self.dynamic_blob_sha256,
            },
            "fixed_state_sha256": {
                key: value for key, value in self.fixed_state_sha256
            },
        }

    @property
    def sha256(self) -> str:
        """Hash of the canonical JSON identity, useful for audit binding."""

        return _sha256(_canonical_json(self.to_dict()))


def _expected_object_specs() -> tuple[tuple[int, str, int], ...]:
    fixed = tuple(
        (spec.command, spec.kind, spec.length) for spec in FIXED_BACKUP_OBJECTS
    )
    return fixed + (
        (COMMAND_BACKUP_BLOB, "backup-blob-probe", FIXED_RESPONSE_LENGTH),
        (COMMAND_BACKUP_BLOB, "backup-blob", -1),
    )


def _filename_semantics(filename: Any, *, sequence: int, command: int) -> str:
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise BackupStateIdentityError("backup object filename is not a simple name")
    match = _FILENAME_WITH_COMMAND.fullmatch(filename)
    if match is not None:
        if int(match.group("sequence")) != sequence or int(
            match.group("command"), 16
        ) != command:
            raise BackupStateIdentityError(
                f"backup object filename semantics do not match sequence {sequence}"
            )
        return filename
    match = _FILENAME_WITHOUT_COMMAND.fullmatch(filename)
    if match is not None and int(match.group("sequence")) == sequence:
        # Compact fake archives used by the portable suite predate the
        # command-bearing production filename.  They still carry the same
        # ordered object semantics and are accepted as a test-only filename
        # spelling; arbitrary names remain rejected.
        return filename
    raise BackupStateIdentityError(
        f"backup object filename has unsupported semantics: {filename!r}"
    )


def _verified_again(backup: VerifiedBackup) -> VerifiedBackup:
    """Re-run the established complete/integrity verifier without freshness."""

    try:
        verified = verify_fresh_backup(
            Path(backup.directory),
            now=None,
            max_age_seconds=None,
        )
    except Exception as exc:
        raise BackupStateIdentityError(
            f"backup did not pass complete integrity verification: {exc}"
        ) from exc
    # A forged VerifiedBackup must not supply any state fields to this module.
    # Provenance (directory, manifest hash, and capture times) is deliberately
    # not compared here.
    if (
        verified.device_identity != backup.device_identity
        or verified.object_count != backup.object_count
        or verified.blob_sha256 != backup.blob_sha256
        or verified.object_sha256_by_key != backup.object_sha256_by_key
        or verified.object_filename_by_key != backup.object_filename_by_key
    ):
        raise BackupStateIdentityError(
            "supplied VerifiedBackup differs from its re-verified object state"
        )
    return verified


def derive_backup_state_identity(backup: VerifiedBackup) -> BackupStateIdentity:
    """Derive the canonical identity only from a complete verified archive."""

    if not isinstance(backup, VerifiedBackup):
        raise BackupStateIdentityError("a VerifiedBackup is required")
    verified = _verified_again(backup)
    manifest = _read_manifest(verified)
    if manifest.get("format") != "infocarry-raw-backup-v1" or manifest.get("state") != "complete":
        raise BackupStateIdentityError("backup manifest is not a complete raw backup")
    expected_device = {
        "vendor_id": verified.device_identity[0],
        "product_id": verified.device_identity[1],
    }
    if manifest.get("device") != expected_device:
        raise BackupStateIdentityError("backup manifest device identity is inconsistent")
    protocol = manifest.get("protocol")
    if protocol != _EXPECTED_PROTOCOL:
        raise BackupStateIdentityError(
            "backup manifest protocol identity is missing or unsupported"
        )
    entries = manifest.get("objects")
    if not isinstance(entries, list) or len(entries) != len(_expected_object_specs()):
        raise BackupStateIdentityError("backup does not contain the canonical eight-object set")

    verified_by_key = dict(verified.object_sha256_by_key)
    expected_objects: list[BackupObjectStateIdentity] = []
    fixed_hashes: list[tuple[str, str]] = []
    dynamic_length: int | None = None
    dynamic_hash: str | None = None
    for index, (entry, expected) in enumerate(zip(entries, _expected_object_specs()), start=1):
        if not isinstance(entry, dict):
            raise BackupStateIdentityError("backup manifest contains a malformed object")
        command, role, expected_length = expected
        expected_command = f"0x{command:04x}"
        expected_key = f"{expected_command}:{role}"
        if (
            entry.get("sequence") != index
            or entry.get("command") != expected_command
            or entry.get("kind") != role
        ):
            raise BackupStateIdentityError(
                f"backup object {index} does not match the canonical role/order"
            )
        filename = _filename_semantics(
            entry.get("filename"), sequence=index, command=command
        )
        requested_length = entry.get("requested_length")
        length = entry.get("received_length")
        if (
            not isinstance(requested_length, int)
            or isinstance(requested_length, bool)
            or not isinstance(length, int)
            or isinstance(length, bool)
            or length < 0
            or requested_length != length
            or (expected_length >= 0 and length != expected_length)
        ):
            raise BackupStateIdentityError(
                f"backup object {expected_key} has an unsupported length binding"
            )
        if expected_length < 0 and length <= 0:
            raise BackupStateIdentityError("dynamic backup blob has an invalid length")
        digest = _require_digest(entry.get("sha256"), f"backup object {expected_key} hash")
        if verified_by_key.get(expected_key) != digest:
            raise BackupStateIdentityError(
                f"backup object {expected_key} hash is not the verified raw hash"
            )
        item = BackupObjectStateIdentity(
            sequence=index,
            key=expected_key,
            role=role,
            command=expected_command,
            filename=filename,
            requested_length=requested_length,
            length=length,
            sha256=digest,
        )
        expected_objects.append(item)
        if role == "backup-blob":
            dynamic_length = length
            dynamic_hash = digest
        if role.startswith("response-00") and command in {
            0x001B,
            0x001C,
            0x001D,
            0x001E,
            0x001F,
        }:
            fixed_hashes.append((expected_command, digest))
    if dynamic_length is None or dynamic_hash is None or len(fixed_hashes) != 5:
        raise BackupStateIdentityError("backup dynamic or fixed-state identity is incomplete")
    return BackupStateIdentity(
        device_identity=tuple(sorted(expected_device.items())),
        protocol_identity=tuple(sorted(protocol.items())),
        objects=tuple(expected_objects),
        dynamic_blob_length=dynamic_length,
        dynamic_blob_sha256=dynamic_hash,
        fixed_state_sha256=tuple(fixed_hashes),
    )


def _provenance_snapshot(backup: VerifiedBackup) -> dict[str, Any]:
    manifest = _read_manifest(backup)
    objects = manifest.get("objects", [])
    received = [
        {
            "sequence": entry.get("sequence"),
            "received_at_utc": entry.get("received_at_utc"),
        }
        for entry in objects
        if isinstance(entry, dict) and "received_at_utc" in entry
    ]
    return {
        "archive_directory": str(backup.directory),
        "manifest_sha256": backup.manifest_sha256,
        "created_at_utc": manifest.get("created_at_utc"),
        "updated_at_utc": manifest.get("updated_at_utc"),
        "verified_at_utc": backup.verified_at_utc,
        "object_received_at_utc": received,
    }


def _diff_values(left: Any, right: Any, path: str = "") -> list[dict[str, Any]]:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        result: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            result.extend(
                _diff_values(
                    left.get(key),
                    right.get(key),
                    f"{path}.{key}" if path else str(key),
                )
            )
        return result
    if left != right:
        return [{"field": path, "left": left, "right": right}]
    return []


@dataclass(frozen=True)
class BackupStateComparison:
    """Deterministic state/provenance comparison suitable for an audit."""

    left_identity_sha256: str
    right_identity_sha256: str
    raw_state_equal: bool
    raw_state_differences: tuple[dict[str, Any], ...]
    provenance_differences: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "infocarry-verified-backup-state-comparison-v1",
            "raw_state_equal": self.raw_state_equal,
            "left_identity_sha256": self.left_identity_sha256,
            "right_identity_sha256": self.right_identity_sha256,
            "raw_state_differences": [dict(value) for value in self.raw_state_differences],
            "provenance_differences": [dict(value) for value in self.provenance_differences],
            "provenance_excluded_from_state_equality": [
                "archive_directory",
                "manifest_sha256",
                "created_at_utc",
                "updated_at_utc",
                "verified_at_utc",
                "object_received_at_utc",
            ],
        }


def compare_verified_backups(
    left: VerifiedBackup,
    right: VerifiedBackup,
) -> BackupStateComparison:
    """Compare two complete backups and report state vs provenance separately."""

    left_identity = derive_backup_state_identity(left)
    right_identity = derive_backup_state_identity(right)
    left_dict = left_identity.to_dict()
    right_dict = right_identity.to_dict()
    return BackupStateComparison(
        left_identity_sha256=left_identity.sha256,
        right_identity_sha256=right_identity.sha256,
        raw_state_equal=left_identity == right_identity,
        raw_state_differences=tuple(_diff_values(left_dict, right_dict)),
        provenance_differences=tuple(
            _diff_values(_provenance_snapshot(left), _provenance_snapshot(right))
        ),
    )


__all__ = [
    "BACKUP_STATE_IDENTITY_FORMAT",
    "BackupObjectStateIdentity",
    "BackupStateComparison",
    "BackupStateIdentity",
    "BackupStateIdentityError",
    "compare_verified_backups",
    "derive_backup_state_identity",
]
