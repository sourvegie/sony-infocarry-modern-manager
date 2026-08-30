"""Fail-closed fixed-state preflight for constrained package operations.

The normal product paths accept only the five zero-filled capture-7 state
objects. The isolated mixed-package path may additionally opt in to one
verified display-history block, while still requiring exact zero mark and
bookmark state and preserving every accepted raw byte.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

from .backup import parse_grouped_values_response, parse_offset_list_response
from .backup_format import BackupFormatError, ParsedBackupBlob, parse_backup_blob
from .write_gate import VerifiedBackup


FIXED_STATE_COMMANDS = (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)
FIXED_STATE_KINDS = {
    0x001B: "response-001b",
    0x001C: "response-001c",
    0x001D: "response-001d",
    0x001E: "response-001e",
    0x001F: "response-001f",
}
CAPTURE7_ZERO_STATE_SHA256 = hashlib.sha256(b"\x00" * 64).hexdigest()
DISPLAY_HISTORY_COMMAND = 0x001B


class PreparedFixedStateError(ValueError):
    """Raised when a fresh backup is not eligible for the constrained policy."""


def _key(command: int) -> str:
    return f"0x{command:04x}:{FIXED_STATE_KINDS[command]}"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class PreparedFixedStateSnapshot:
    """Verified raw fixed-state bytes, preserved for a prospective transaction."""

    raw_blocks: tuple[bytes, bytes, bytes, bytes, bytes]
    sha256_by_command: tuple[tuple[int, str], ...]
    display_history_record_offsets: tuple[int, ...] = ()
    display_history_paths: tuple[tuple[int, tuple[str, ...]], ...] = ()
    display_history_metadata_start: int = 0x40

    @property
    def range1(self) -> bytes:
        return b"".join(self.raw_blocks[:4])

    @property
    def range2(self) -> bytes:
        return self.raw_blocks[4]

    def to_dict(self) -> dict[str, Any]:
        display_history = {
            "present": bool(self.display_history_record_offsets),
            "raw_preserved_exactly": True,
            "metadata_start": f"0x{self.display_history_metadata_start:08x}",
            "relative_record_offsets": [
                f"0x{offset:08x}" for offset in self.display_history_record_offsets
            ],
            "absolute_record_offsets": [
                f"0x{offset + self.display_history_metadata_start:08x}"
                for offset in self.display_history_record_offsets
            ],
            "paths": [
                {
                    "relative_record_offset": f"0x{offset:08x}",
                    "path": "\\".join(path),
                }
                for offset, path in self.display_history_paths
            ],
            "candidate_offset_policy": "references must remain valid at the same absolute metadata offsets; no rebasing or raw-block rewrite",
        }
        return {
            "policy": (
                "verified_display_history_0x001b_plus_zero_0x001c_to_0x001f"
                if self.display_history_record_offsets
                else "capture7_exact_all_zero_fixed_state"
            ),
            "supported": True,
            "raw_bytes_preserved": True,
            "blocks": {
                f"0x{command:04x}": {
                    "sha256": digest,
                    "length": len(self.raw_blocks[index]),
                    "active_entries": (
                        len(self.display_history_record_offsets)
                        if command == DISPLAY_HISTORY_COMMAND
                        else 0
                    ),
                }
                for index, (command, digest) in enumerate(self.sha256_by_command)
            },
            "prospective_range1_sha256": _sha256(self.range1),
            "prospective_range2_sha256": _sha256(self.range2),
            "display_history": display_history,
        }

    def validate_display_history_unshifted(
        self,
        baseline: ParsedBackupBlob,
        candidate: ParsedBackupBlob,
    ) -> dict[str, Any]:
        """Require every accepted display-history reference to remain unshifted.

        The raw 0x001b block is safe to preserve only when its metadata-relative
        offsets still identify the same reachable records after the additive
        candidate is rebuilt.  A root insertion normally shifts later records;
        that geometry is rejected rather than silently rebasing the block.
        """

        if not self.display_history_record_offsets:
            return {
                "present": False,
                "raw_preserved_exactly": True,
                "references_validated": 0,
                "references_unshifted": True,
            }
        if (
            baseline.header.metadata_start != self.display_history_metadata_start
            or candidate.header.metadata_start != self.display_history_metadata_start
        ):
            raise PreparedFixedStateError(
                "display-history metadata base changed in the prospective candidate"
            )
        if len(self.display_history_record_offsets) != len(self.display_history_paths):
            raise PreparedFixedStateError(
                "display-history reference/path binding is incomplete"
            )
        validated: list[dict[str, Any]] = []
        for relative_offset, (bound_offset, bound_path) in zip(
            self.display_history_record_offsets, self.display_history_paths
        ):
            if relative_offset != bound_offset:
                raise PreparedFixedStateError(
                    "display-history reference binding is internally inconsistent"
                )
            absolute_offset = baseline.header.metadata_start + relative_offset
            if baseline.paths.get(absolute_offset) != bound_path:
                raise PreparedFixedStateError(
                    "display-history reference no longer resolves in the baseline"
                )
            if candidate.paths.get(absolute_offset) != bound_path:
                raise PreparedFixedStateError(
                    "display-history reference shifted in the prospective candidate"
                )
            try:
                before = baseline.record_at(absolute_offset)
                after = candidate.record_at(absolute_offset)
            except BackupFormatError as exc:
                raise PreparedFixedStateError(
                    "display-history reference is not aligned in the prospective candidate"
                ) from exc
            before_raw = bytes.fromhex(before.raw_hex)
            after_raw = bytes.fromhex(after.raw_hex)
            if before_raw[:4] + before_raw[0x0C:] != after_raw[:4] + after_raw[0x0C:]:
                raise PreparedFixedStateError(
                    "display-history referenced record changed outside permitted offsets"
                )
            validated.append(
                {
                    "relative_record_offset": f"0x{relative_offset:08x}",
                    "absolute_record_offset": f"0x{absolute_offset:08x}",
                    "path": "\\".join(bound_path),
                    "unshifted": True,
                }
            )
        return {
            "present": True,
            "raw_preserved_exactly": True,
            "references_validated": len(validated),
            "references_unshifted": True,
            "references": validated,
        }


@dataclass(frozen=True)
class PreparedFixedStateAssessment:
    """Diagnostic, non-authorizing result for one verified fresh backup."""

    eligible: bool
    reasons: tuple[str, ...]
    snapshot: PreparedFixedStateSnapshot | None
    block_reports: tuple[Mapping[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reasons": list(self.reasons),
            "blocks": [dict(report) for report in self.block_reports],
            "snapshot": None if self.snapshot is None else self.snapshot.to_dict(),
        }

    def require_supported(self) -> PreparedFixedStateSnapshot:
        if not self.eligible or self.snapshot is None:
            reason = "; ".join(self.reasons) or "fresh fixed state is not supported"
            raise PreparedFixedStateError(reason)
        return self.snapshot


def _load_backup_blob(backup: VerifiedBackup) -> ParsedBackupBlob:
    filename = backup.object_filename("0x8004:backup-blob")
    expected = backup.object_sha256("0x8004:backup-blob")
    if filename is None or expected is None or expected != backup.blob_sha256:
        raise PreparedFixedStateError("verified backup is missing its dynamic blob")
    try:
        data = (backup.directory / filename).read_bytes()
    except OSError as exc:
        raise PreparedFixedStateError(f"could not read verified backup dynamic blob: {exc}") from exc
    if _sha256(data) != expected:
        raise PreparedFixedStateError("verified backup dynamic blob changed after verification")
    try:
        return parse_backup_blob(data)
    except BackupFormatError as exc:
        raise PreparedFixedStateError(f"verified backup dynamic blob is malformed: {exc}") from exc


def _parse_display_history(
    backup: VerifiedBackup,
    data: bytes,
) -> tuple[
    tuple[int, ...],
    tuple[tuple[int, tuple[str, ...]], ...],
    int,
]:
    try:
        parsed_response = parse_offset_list_response(data)
    except Exception as exc:
        raise PreparedFixedStateError(f"display-history response is malformed: {exc}") from exc
    if parsed_response.value_04_be16 or parsed_response.value_06_be16:
        raise PreparedFixedStateError(
            "display-history response contains unfamiliar fixed header words"
        )
    tail = bytes.fromhex(parsed_response.unused_tail_hex)
    if any(tail):
        raise PreparedFixedStateError(
            "display-history response contains nonzero reserved tail bytes"
        )
    if not parsed_response.record_offsets:
        raise PreparedFixedStateError(
            "display-history response is nonzero but contains no active entries"
        )
    parsed_backup = _load_backup_blob(backup)
    paths: list[tuple[int, tuple[str, ...]]] = []
    seen: set[int] = set()
    for relative_offset in parsed_response.record_offsets:
        if relative_offset % 0x40:
            raise PreparedFixedStateError(
                f"display-history record offset 0x{relative_offset:08x} is not record-aligned"
            )
        if relative_offset in seen:
            raise PreparedFixedStateError(
                f"display-history record offset 0x{relative_offset:08x} is duplicated"
            )
        seen.add(relative_offset)
        absolute_offset = parsed_backup.header.metadata_start + relative_offset
        try:
            record = parsed_backup.record_at(absolute_offset)
        except BackupFormatError as exc:
            raise PreparedFixedStateError(
                f"display-history record offset 0x{relative_offset:08x} is dangling"
            ) from exc
        path = parsed_backup.paths.get(absolute_offset)
        if path is None or record.kind != "file":
            raise PreparedFixedStateError(
                f"display-history reference 0x{relative_offset:08x} does not resolve to an existing file"
            )
        paths.append((relative_offset, tuple(path)))
    return (
        tuple(parsed_response.record_offsets),
        tuple(paths),
        parsed_backup.header.metadata_start,
    )


def assess_prepared_fixed_state(
    backup: VerifiedBackup,
    *,
    allow_verified_display_history: bool = False,
) -> PreparedFixedStateAssessment:
    """Assess the exact zero state, or opt-in verified display history.

    The opt-in is intentionally separate from the normal product paths.  Only
    the constrained mixed-package candidate enables it, and it still requires
    all mark/bookmark blocks to remain the exact supported zero state.
    """

    if not isinstance(backup, VerifiedBackup):
        raise PreparedFixedStateError("fixed-state assessment requires a VerifiedBackup")

    reasons: list[str] = []
    reports: list[dict[str, Any]] = []
    blocks: list[bytes] = []
    display_history_offsets: tuple[int, ...] = ()
    display_history_paths: tuple[tuple[int, tuple[str, ...]], ...] = ()
    display_history_metadata_start = 0x40
    for command in FIXED_STATE_COMMANDS:
        key = _key(command)
        filename = backup.object_filename(key)
        expected_hash = backup.object_sha256(key)
        report: dict[str, Any] = {
            "command": f"0x{command:04x}",
            "key": key,
            "expected_sha256": expected_hash,
            "active_entries": None,
            "raw_sha256": None,
            "length": None,
            "supported": False,
        }
        if filename is None or expected_hash is None:
            reasons.append(f"missing fixed-state object {key}")
            reports.append(report)
            continue
        try:
            data = (backup.directory / filename).read_bytes()
        except OSError as exc:
            reasons.append(f"could not read fixed-state object {key}: {exc}")
            reports.append(report)
            continue
        report["length"] = len(data)
        report["raw_sha256"] = _sha256(data)
        if len(data) != 64:
            reasons.append(f"{key} has length {len(data)}; expected 64")
            reports.append(report)
            continue
        if report["raw_sha256"] != expected_hash:
            reasons.append(f"{key} changed after backup verification")
            reports.append(report)
            continue
        block_reasons: list[str] = []
        active_entries = 0
        try:
            if command == DISPLAY_HISTORY_COMMAND:
                parsed = parse_offset_list_response(data)
                active_entries = parsed.count
                tail = bytes.fromhex(parsed.unused_tail_hex)
                if data != b"\x00" * 64 and not allow_verified_display_history:
                    if parsed.count:
                        block_reasons.append(
                            f"{key} contains {parsed.count} active offset entries"
                        )
                    if parsed.value_04_be16 or parsed.value_06_be16:
                        block_reasons.append(
                            f"{key} contains unfamiliar fixed header words"
                        )
                    if any(tail):
                        block_reasons.append(
                            f"{key} contains nonzero reserved tail bytes"
                        )
                    block_reasons.append(
                        f"{key} contains nonzero display-history state"
                    )
                elif data != b"\x00" * 64:
                    (
                        display_history_offsets,
                        display_history_paths,
                        display_history_metadata_start,
                    ) = _parse_display_history(
                        backup, data
                    )
                    report["display_history_record_offsets"] = [
                        f"0x{offset:08x}" for offset in display_history_offsets
                    ]
                    report["display_history_paths"] = [
                        "\\".join(path) for _offset, path in display_history_paths
                    ]
                    report["display_history_metadata_start"] = (
                        f"0x{display_history_metadata_start:08x}"
                    )
            elif command == 0x001F:
                parsed = parse_grouped_values_response(data)
                active_entries = sum(value != 0 for group in parsed.groups for value in group)
                tail = bytes.fromhex(parsed.unused_tail_hex)
                tail_nonzero = any(tail)
                if active_entries:
                    block_reasons.append(f"{key} contains nonzero bookmark values")
                if tail_nonzero:
                    block_reasons.append(f"{key} contains nonzero reserved tail bytes")
            else:
                parsed = parse_offset_list_response(data)
                active_entries = parsed.count
                tail = bytes.fromhex(parsed.unused_tail_hex)
                tail_nonzero = any(tail)
                if parsed.count:
                    block_reasons.append(f"{key} contains {parsed.count} active offset entries")
                if parsed.value_04_be16 or parsed.value_06_be16:
                    block_reasons.append(f"{key} contains unfamiliar fixed header words")
                if tail_nonzero:
                    block_reasons.append(f"{key} contains nonzero reserved tail bytes")
        except Exception as exc:
            reasons.append(f"{key} is malformed: {exc}")
            reports.append(report)
            continue
        report["active_entries"] = active_entries
        if data != b"\x00" * 64 and not (
            command == DISPLAY_HISTORY_COMMAND and display_history_offsets
        ):
            block_reasons.append(f"{key} differs from exact capture-7 all-zero state")
        reasons.extend(block_reasons)
        report["supported"] = not block_reasons
        blocks.append(data)
        reports.append(report)

    if len(blocks) != len(FIXED_STATE_COMMANDS):
        return PreparedFixedStateAssessment(False, tuple(reasons), None, tuple(reports))
    if not display_history_offsets and (
        len(set(blocks)) != 1 or _sha256(blocks[0]) != CAPTURE7_ZERO_STATE_SHA256
    ):
        if not any("exact capture-7 all-zero" in reason for reason in reasons):
            reasons.append("fixed-state blocks do not match exact capture-7 all-zero state")
    snapshot = PreparedFixedStateSnapshot(
        raw_blocks=tuple(blocks),
        sha256_by_command=tuple(
            (command, _sha256(blocks[index]))
            for index, command in enumerate(FIXED_STATE_COMMANDS)
        ),
        display_history_record_offsets=display_history_offsets,
        display_history_paths=display_history_paths,
        display_history_metadata_start=display_history_metadata_start,
    )
    eligible = not reasons
    if not eligible:
        snapshot = None
    return PreparedFixedStateAssessment(eligible, tuple(reasons), snapshot, tuple(reports))


__all__ = [
    "CAPTURE7_ZERO_STATE_SHA256",
    "DISPLAY_HISTORY_COMMAND",
    "FIXED_STATE_COMMANDS",
    "PreparedFixedStateAssessment",
    "PreparedFixedStateError",
    "PreparedFixedStateSnapshot",
    "assess_prepared_fixed_state",
]
