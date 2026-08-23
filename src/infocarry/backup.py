"""Lossless, read-only backup workflow recovered from ``VicTwo.dll``.

Protocol names remain deliberately neutral until the response formats are
decoded.  Every response is persisted before it is inspected or used to plan
the next receive operation.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from .capture import CaptureError
from .protocol import ProtocolError, ReadOnlyReceiver, TransferLengthError
from .transport import InfoCarrySession


FIXED_RESPONSE_LENGTH = 64
COMMAND_BACKUP_BLOB = 0x8004
BACKUP_COMMANDS = frozenset({0x0024, 0x001B, 0x001C, 0x001D, 0x001E, 0x001F, COMMAND_BACKUP_BLOB})

# The observed hardware response reports no value larger than 4 MiB.  This
# deliberately generous ceiling prevents a corrupt probe from requesting an
# unbounded allocation or transfer; it is a safety policy, not a device fact.
MAX_BACKUP_BLOB_LENGTH = 16 * 1024 * 1024


class BackupProbeError(ProtocolError):
    """Raised when the preserved 0x8004 probe cannot safely size the blob."""


class FixedResponseError(ProtocolError):
    """Raised when a fixed backup response violates its recovered structure."""


@dataclass(frozen=True)
class OffsetListResponse:
    """Neutral structure shared by commands 0x001b through 0x001e.

    Live cross-file captures show that ``record_offsets`` are relative to the
    blob's metadata start, not absolute blob offsets. For the observed header,
    add ``0x40`` to correlate one with ``BackupRecord.offset``.
    """

    count: int
    value_04_be16: int
    value_06_be16: int
    record_offsets: Sequence[int]
    unused_tail_hex: str


@dataclass(frozen=True)
class GroupedValuesResponse:
    """Neutral structure returned by command 0x001f."""

    groups: Sequence[Sequence[int]]
    unused_tail_hex: str


@dataclass(frozen=True)
class BackupObjectSpec:
    command: int
    kind: str
    length: int = FIXED_RESPONSE_LENGTH


FIXED_BACKUP_OBJECTS: Sequence[BackupObjectSpec] = (
    BackupObjectSpec(0x0024, "response-0024"),
    BackupObjectSpec(0x001B, "response-001b"),
    BackupObjectSpec(0x001C, "response-001c"),
    BackupObjectSpec(0x001D, "response-001d"),
    BackupObjectSpec(0x001E, "response-001e"),
    BackupObjectSpec(0x001F, "response-001f"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_backup_blob_length(probe: bytes) -> int:
    """Apply the exact length calculation used by VicTwo's probe helper.

    Static analysis verifies a direct big-endian length at raw offset 0x38.
    The value 0xffffffff selects a fallback calculation using the big-endian
    values at offsets 0x30 and 0x34. Their semantic names remain unknown.
    """

    if len(probe) != FIXED_RESPONSE_LENGTH:
        raise TransferLengthError(
            f"backup probe is {len(probe)} bytes; expected {FIXED_RESPONSE_LENGTH}"
        )
    direct_length = int.from_bytes(probe[0x38:0x3C], "big")
    if direct_length == 0xFFFFFFFF:
        first = int.from_bytes(probe[0x30:0x34], "big")
        second = int.from_bytes(probe[0x34:0x38], "big")
        combined = first + second
        length = (combined // 4) * 4 + 4
    else:
        length = direct_length
    if length == 0 or length > MAX_BACKUP_BLOB_LENGTH:
        raise BackupProbeError(
            f"backup probe requests unsafe length {length}; valid range is 1 through "
            f"{MAX_BACKUP_BLOB_LENGTH} bytes"
        )
    return length


def _require_fixed_response(data: bytes) -> None:
    if len(data) != FIXED_RESPONSE_LENGTH:
        raise TransferLengthError(
            f"fixed response is {len(data)} bytes; expected {FIXED_RESPONSE_LENGTH}"
        )


def parse_offset_list_response(data: bytes) -> OffsetListResponse:
    """Parse the statically verified 0x001b--0x001e response layout.

    Only the first ``count`` offsets are entries. Live mark-state captures
    show that later slots can retain bytes from a previously populated shared
    response buffer even when ``count`` is zero.
    """

    _require_fixed_response(data)
    count = int.from_bytes(data[0:4], "big")
    # VicTwo.dll 0x10005760 rejects 14 or more entries. Thirteen entries fit
    # exactly after the eight-byte fixed prefix in a 64-byte response.
    if count >= 14:
        raise FixedResponseError(
            f"offset-list response declares {count} entries; maximum is 13"
        )
    end = 8 + count * 4
    return OffsetListResponse(
        count=count,
        value_04_be16=int.from_bytes(data[4:6], "big"),
        value_06_be16=int.from_bytes(data[6:8], "big"),
        record_offsets=tuple(
            int.from_bytes(data[offset : offset + 4], "big")
            for offset in range(8, end, 4)
        ),
        unused_tail_hex=data[end:].hex(),
    )


def parse_grouped_values_response(data: bytes) -> GroupedValuesResponse:
    """Parse command 0x001f as two groups of five big-endian dwords."""

    _require_fixed_response(data)
    values = tuple(
        int.from_bytes(data[offset : offset + 4], "big")
        for offset in range(0, 40, 4)
    )
    return GroupedValuesResponse(
        groups=(values[:5], values[5:]),
        unused_tail_hex=data[40:].hex(),
    )


class RawBackupArchive:
    """A new, non-overwriting directory containing lossless raw objects."""

    def __init__(self, directory: Path):
        self.directory = directory
        self._created_at = _utc_now()
        self._objects: List[Dict[str, Any]] = []
        self._state = "in_progress"
        self._error: Optional[Dict[str, str]] = None

    @classmethod
    def create(cls, directory: Path) -> "RawBackupArchive":
        path = directory.expanduser().resolve()
        try:
            path.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise CaptureError(f"refusing to overwrite existing backup path: {path}") from exc
        except OSError as exc:
            raise CaptureError(f"could not create backup directory {path}: {exc}") from exc
        archive = cls(path)
        archive._write_manifest()
        return archive

    @property
    def objects(self) -> Sequence[Dict[str, Any]]:
        return tuple(dict(entry) for entry in self._objects)

    def save(self, spec: BackupObjectSpec, data: bytes) -> Dict[str, Any]:
        if self._state != "in_progress":
            raise CaptureError(f"backup archive is already {self._state}")
        if len(data) != spec.length:
            raise TransferLengthError(
                f"command 0x{spec.command:04x} returned {len(data)} bytes; expected {spec.length}"
            )
        sequence = len(self._objects) + 1
        filename = f"object-{sequence:02d}-command-{spec.command:04x}.bin"
        path = self.directory / filename
        try:
            with path.open("xb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
        except OSError as exc:
            raise CaptureError(f"could not preserve raw backup object {path}: {exc}") from exc
        entry = {
            "sequence": sequence,
            "command": f"0x{spec.command:04x}",
            "kind": spec.kind,
            "filename": filename,
            "requested_length": spec.length,
            "received_length": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "received_at_utc": _utc_now(),
        }
        self._objects.append(entry)
        self._write_manifest()
        return dict(entry)

    def finalize(self) -> None:
        if self._state == "complete":
            return
        if self._state != "in_progress":
            raise CaptureError(f"cannot finalize a backup archive marked {self._state}")
        self._state = "complete"
        self._write_manifest()

    def mark_incomplete(self, error: BaseException) -> None:
        if self._state != "in_progress":
            return
        self._state = "incomplete"
        self._error = {"type": type(error).__name__, "message": str(error)}
        self._write_manifest()

    def _write_manifest(self) -> None:
        manifest: Dict[str, Any] = {
            "format": "infocarry-raw-backup-v1",
            "state": self._state,
            "created_at_utc": self._created_at,
            "updated_at_utc": _utc_now(),
            "device": {"vendor_id": "0x054c", "product_id": "0x001e"},
            "protocol": {
                "direction": "device-to-host",
                "command_header": "uint16le command + uint32le requested_length",
                "source": "static analysis of VicTwo.dll",
            },
            "objects": self._objects,
        }
        if self._error is not None:
            manifest["error"] = self._error
        temporary = self.directory / "manifest.json.tmp"
        destination = self.directory / "manifest.json"
        try:
            with temporary.open("w", encoding="utf-8") as output:
                json.dump(manifest, output, indent=2, sort_keys=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(destination)
        except OSError as exc:
            raise CaptureError(f"could not update backup manifest: {exc}") from exc


class BackupClient:
    """Receive the statically recovered backup objects in legacy order."""

    def __init__(self, session: InfoCarrySession):
        self._receiver = ReadOnlyReceiver(
            session.backend,
            session.endpoints.bulk_in,
            allowed_commands=BACKUP_COMMANDS,
        )

    def backup(
        self,
        archive: RawBackupArchive,
        *,
        cancelled: Optional[Callable[[], bool]] = None,
        progress: Optional[Callable[[str, int, int], None]] = None,
    ) -> Sequence[Dict[str, Any]]:
        try:
            total_steps = len(FIXED_BACKUP_OBJECTS) + 2
            completed_steps = 0

            def notify(label: str) -> None:
                if progress is not None:
                    progress(label, completed_steps, total_steps)

            for spec in FIXED_BACKUP_OBJECTS:
                notify(f"Reading {spec.kind}")
                data = self._receiver.receive(spec.command, spec.length, cancelled=cancelled)
                archive.save(spec, data)
                completed_steps += 1
                notify(f"Read {spec.kind}")

            probe_spec = BackupObjectSpec(COMMAND_BACKUP_BLOB, "backup-blob-probe")
            notify("Reading backup size probe")
            probe = self._receiver.receive(
                probe_spec.command, probe_spec.length, cancelled=cancelled
            )
            archive.save(probe_spec, probe)
            completed_steps += 1
            notify("Read backup size probe")

            blob_length = parse_backup_blob_length(probe)
            blob_spec = BackupObjectSpec(
                COMMAND_BACKUP_BLOB, "backup-blob", blob_length
            )
            notify(f"Reading backup content ({blob_length:,} bytes)")
            blob = self._receiver.receive(
                blob_spec.command, blob_spec.length, cancelled=cancelled
            )
            archive.save(blob_spec, blob)
            archive.finalize()
            completed_steps += 1
            notify("Backup verified")
            return archive.objects
        except (Exception, KeyboardInterrupt) as exc:
            try:
                archive.mark_incomplete(exc)
            except CaptureError:
                # Preserve the original transfer/storage failure. The most
                # recent durable manifest and any raw files remain available.
                pass
            raise
