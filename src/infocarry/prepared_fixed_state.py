"""Fail-closed fixed-state preflight for constrained package operations.

The normal product paths accept only the five zero-filled capture-7 state
objects. The isolated mixed-package path may additionally opt in to one
verified display-history block, while still requiring exact zero mark and
bookmark state.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from typing import Any, Mapping

from .backup import parse_grouped_values_response, parse_offset_list_response
from .backup_format import BackupFormatError, ParsedBackupBlob, parse_backup_blob
from .write_gate import VerifiedBackup
from .write_state import StateSerializationError, rebase_fixed_state_responses


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
    prospective_raw_blocks: tuple[bytes, bytes, bytes, bytes, bytes] | None = None
    display_history_candidate_record_offsets: tuple[int, ...] = ()
    display_history_insertion_offset: int | None = None
    display_history_metadata_delta: int = 0

    @property
    def candidate_raw_blocks(self) -> tuple[bytes, bytes, bytes, bytes, bytes]:
        return self.raw_blocks if self.prospective_raw_blocks is None else self.prospective_raw_blocks

    @property
    def range1(self) -> bytes:
        return b"".join(self.candidate_raw_blocks[:4])

    @property
    def range2(self) -> bytes:
        return self.candidate_raw_blocks[4]

    def to_dict(self) -> dict[str, Any]:
        display_history = {
            "present": bool(self.display_history_record_offsets),
            "preservation_policy": (
                "semantic_rebase_by_exact_metadata_delta"
                if self.display_history_record_offsets
                else "raw_exact"
            ),
            "raw_preserved_exactly": (
                self.candidate_raw_blocks[0] == self.raw_blocks[0]
            ),
            "semantic_preserved": bool(self.display_history_record_offsets),
            "metadata_start": f"0x{self.display_history_metadata_start:08x}",
            "relative_record_offsets": [
                f"0x{offset:08x}" for offset in self.display_history_record_offsets
            ],
            "candidate_relative_record_offsets": [
                f"0x{offset:08x}"
                for offset in (
                    self.display_history_candidate_record_offsets
                    or self.display_history_record_offsets
                )
            ],
            "absolute_record_offsets": [
                f"0x{offset + self.display_history_metadata_start:08x}"
                for offset in self.display_history_record_offsets
            ],
            "candidate_absolute_record_offsets": [
                f"0x{offset + self.display_history_metadata_start:08x}"
                for offset in (
                    self.display_history_candidate_record_offsets
                    or self.display_history_record_offsets
                )
            ],
            "paths": [
                {
                    "relative_record_offset": f"0x{offset:08x}",
                    "path": "\\".join(path),
                }
                for offset, path in self.display_history_paths
            ],
            "insertion_offset": (
                None
                if self.display_history_insertion_offset is None
                else f"0x{self.display_history_insertion_offset:08x}"
            ),
            "metadata_delta": f"0x{self.display_history_metadata_delta:08x}",
            "references_rebased": sum(
                before != after
                for before, after in zip(
                    self.display_history_record_offsets,
                    self.display_history_candidate_record_offsets
                    or self.display_history_record_offsets,
                )
            ),
            "candidate_offset_policy": "counted references at or after the exact insertion offset rebase by the exact metadata delta; all other bytes remain unchanged",
        }
        candidate_blocks = self.candidate_raw_blocks
        return {
            "policy": (
                "verified_display_history_0x001b_semantic_rebase_plus_zero_0x001c_to_0x001f"
                if self.display_history_record_offsets
                else "capture7_exact_all_zero_fixed_state"
            ),
            "supported": True,
            "raw_bytes_preserved": all(
                candidate_blocks[index] == self.raw_blocks[index]
                for index in range(len(self.raw_blocks))
            ),
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
            "candidate_blocks": {
                f"0x{command:04x}": {
                    "sha256": _sha256(candidate_blocks[index]),
                    "length": len(candidate_blocks[index]),
                    "active_entries": (
                        len(self.display_history_candidate_record_offsets)
                        if command == DISPLAY_HISTORY_COMMAND
                        else 0
                    ),
                }
                for index, (command, _digest) in enumerate(self.sha256_by_command)
            },
            "before_sha256_by_command": [
                {"command": f"0x{command:04x}", "sha256": digest}
                for command, digest in self.sha256_by_command
            ],
            "candidate_sha256_by_command": [
                {
                    "command": f"0x{command:04x}",
                    "sha256": _sha256(candidate_blocks[index]),
                }
                for index, (command, _digest) in enumerate(self.sha256_by_command)
            ],
            "prospective_range1_sha256": _sha256(self.range1),
            "prospective_range2_sha256": _sha256(self.range2),
            "display_history": display_history,
        }

    def rebase_display_history(
        self,
        baseline: ParsedBackupBlob,
        candidate: ParsedBackupBlob,
        *,
        insertion_offset: int,
        metadata_delta: int,
    ) -> tuple["PreparedFixedStateSnapshot", dict[str, Any]]:
        """Apply and verify the exact evidence-backed semantic rebase policy."""

        if not self.display_history_record_offsets:
            result = replace(self, prospective_raw_blocks=self.raw_blocks)
            return result, {
                "present": False,
                "preservation_policy": "raw_exact",
                "raw_preserved_exactly": True,
                "semantic_preserved": False,
                "references_rebased": 0,
            }
        if baseline.header.metadata_start != self.display_history_metadata_start:
            raise PreparedFixedStateError("display-history baseline metadata base changed")
        if candidate.header.metadata_start != baseline.header.metadata_start:
            raise PreparedFixedStateError("display-history candidate metadata base changed")
        if (
            isinstance(insertion_offset, bool)
            or not isinstance(insertion_offset, int)
            or insertion_offset < 0
            or insertion_offset % 0x40
            or isinstance(metadata_delta, bool)
            or not isinstance(metadata_delta, int)
            or metadata_delta <= 0
            or metadata_delta % 0x40
        ):
            raise PreparedFixedStateError("display-history rebase geometry is not record-aligned")
        try:
            rebased_ranges, rebased_grouped = rebase_fixed_state_responses(
                self.raw_blocks[:4],
                self.raw_blocks[4],
                insertion_offset=insertion_offset,
                metadata_delta=metadata_delta,
            )
        except StateSerializationError as exc:
            raise PreparedFixedStateError(
                f"display-history semantic rebase failed: {exc}"
            ) from exc
        prospective_blocks = tuple(rebased_ranges) + (rebased_grouped,)
        if prospective_blocks[1:] != self.raw_blocks[1:]:
            raise PreparedFixedStateError(
                "display-history rebase changed Mark/Bookmark state"
            )
        try:
            before_response = parse_offset_list_response(self.raw_blocks[0])
            candidate_response = parse_offset_list_response(prospective_blocks[0])
        except Exception as exc:
            raise PreparedFixedStateError(
                f"display-history rebased response is malformed: {exc}"
            ) from exc
        if (
            candidate_response.count != before_response.count
            or candidate_response.value_04_be16 != before_response.value_04_be16
            or candidate_response.value_06_be16 != before_response.value_06_be16
            or candidate_response.unused_tail_hex != before_response.unused_tail_hex
        ):
            raise PreparedFixedStateError(
                "display-history rebase changed count, header words, or reserved tail"
            )
        expected_offsets = tuple(
            offset + metadata_delta if offset >= insertion_offset else offset
            for offset in self.display_history_record_offsets
        )
        if tuple(candidate_response.record_offsets) != expected_offsets:
            raise PreparedFixedStateError(
                "display-history reference was unexpectedly shifted or left unshifted"
            )
        if len(self.display_history_paths) != len(expected_offsets):
            raise PreparedFixedStateError("display-history path binding is incomplete")
        references: list[dict[str, Any]] = []
        for before_offset, candidate_offset, (_bound_offset, bound_path) in zip(
            self.display_history_record_offsets,
            expected_offsets,
            self.display_history_paths,
        ):
            if before_offset % 0x40 or candidate_offset % 0x40:
                raise PreparedFixedStateError(
                    "display-history reference is not record-aligned"
                )
            before_absolute = baseline.header.metadata_start + before_offset
            candidate_absolute = candidate.header.metadata_start + candidate_offset
            if baseline.paths.get(before_absolute) != bound_path:
                raise PreparedFixedStateError(
                    "display-history reference no longer resolves in the baseline"
                )
            if candidate.paths.get(candidate_absolute) != bound_path:
                raise PreparedFixedStateError(
                    "rebased display-history reference resolves to a different path"
                )
            try:
                before_record = baseline.record_at(before_absolute)
                candidate_record = candidate.record_at(candidate_absolute)
                before_prefix, before_payload = baseline.payload_parts(before_record)
                candidate_prefix, candidate_payload = candidate.payload_parts(candidate_record)
            except BackupFormatError as exc:
                raise PreparedFixedStateError(
                    "display-history reference does not resolve to a complete record"
                ) from exc
            before_raw = bytes.fromhex(before_record.raw_hex)
            candidate_raw = bytes.fromhex(candidate_record.raw_hex)
            if before_raw[:4] + before_raw[0x0C:] != candidate_raw[:4] + candidate_raw[0x0C:]:
                raise PreparedFixedStateError(
                    "rebased display-history reference changed preserved record bytes"
                )
            if before_prefix != candidate_prefix or before_payload != candidate_payload:
                raise PreparedFixedStateError(
                    "rebased display-history reference changed the preserved payload"
                )
            references.append(
                {
                    "before_relative_record_offset": f"0x{before_offset:08x}",
                    "before_absolute_record_offset": f"0x{before_absolute:08x}",
                    "candidate_relative_record_offset": f"0x{candidate_offset:08x}",
                    "candidate_absolute_record_offset": f"0x{candidate_absolute:08x}",
                    "path": "\\".join(bound_path),
                    "rebased": before_offset != candidate_offset,
                }
            )
        result = replace(
            self,
            prospective_raw_blocks=prospective_blocks,
            display_history_candidate_record_offsets=expected_offsets,
            display_history_insertion_offset=insertion_offset,
            display_history_metadata_delta=metadata_delta,
        )
        return result, {
            "present": True,
            "preservation_policy": "semantic_rebase_by_exact_metadata_delta",
            "raw_preserved_exactly": prospective_blocks[0] == self.raw_blocks[0],
            "semantic_preserved": True,
            "insertion_offset": f"0x{insertion_offset:08x}",
            "metadata_delta": f"0x{metadata_delta:08x}",
            "references_rebased": sum(item["rebased"] for item in references),
            "references": references,
            "count_header_tail_preserved": True,
            "unshifted_references_byte_identical": True,
        }

    def validate_display_history_unshifted(
        self,
        baseline: ParsedBackupBlob,
        candidate: ParsedBackupBlob,
    ) -> dict[str, Any]:
        """Validate the legacy raw-exact/unshifted display-history rule.

        The raw 0x001b block is safe to preserve only when its metadata-relative
        offsets still identify the same reachable records after the additive
        candidate is rebuilt.  A root insertion normally shifts later records;
        this compatibility validator rejects that geometry rather than silently
        rebasing the block. The semantic-rebase policy is implemented by
        :meth:`rebase_display_history` and is deliberately a separate opt-in.
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
