"""Fail-closed fixed-state preflight for constrained package operations.

The normal product paths accept only the five zero-filled capture-7 state
objects. The isolated mixed-package path may additionally opt in to verified
display-history and bookmark references.  Counted mark membership remains
zero; unused/stale bytes and opaque bookmark values are preserved exactly.
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
BOOKMARK_COMMAND = 0x001F


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
    bookmark_groups: tuple[tuple[int, int, int, int, int], ...] = ()
    bookmark_group_paths: tuple[tuple[int, int, tuple[str, ...]], ...] = ()
    bookmark_candidate_record_offsets: tuple[int, ...] = ()

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
        bookmark_offsets = tuple(
            offset for _group_index, offset, _path in self.bookmark_group_paths
        )
        candidate_bookmark_offsets = (
            self.bookmark_candidate_record_offsets or bookmark_offsets
        )
        bookmarks = {
            "present": bool(self.bookmark_group_paths),
            "preservation_policy": (
                "record_pointer_semantic_rebase_opaque_values_raw_exact"
                if self.bookmark_group_paths
                else "raw_exact"
            ),
            "groups": [
                {
                    "group_index": group_index,
                    "before_relative_record_offset": f"0x{offset:08x}",
                    "candidate_relative_record_offset": f"0x{candidate_offset:08x}",
                    "path": "\\".join(path),
                    "pointer_rebased": offset != candidate_offset,
                    "opaque_values_sha256": _sha256(
                        b"".join(value.to_bytes(4, "big") for value in self.bookmark_groups[group_index][1:])
                    ),
                    "opaque_values_preserved_exactly": True,
                }
                for (group_index, offset, path), candidate_offset in zip(
                    self.bookmark_group_paths, candidate_bookmark_offsets
                )
            ],
            "nonzero_values": sum(
                value != 0 for group in self.bookmark_groups for value in group
            ),
            "opaque_values_preserved_exactly": True,
            "raw_preserved_exactly": candidate_blocks[4] == self.raw_blocks[4],
        }
        if self.bookmark_group_paths:
            policy = "verified_display_history_0x001b_and_bookmark_0x001f_semantic_rebase_plus_zero_count_0x001c_to_0x001e"
        elif self.display_history_record_offsets:
            policy = "verified_display_history_0x001b_semantic_rebase_plus_zero_0x001c_to_0x001f"
        else:
            policy = "capture7_exact_all_zero_fixed_state"
        return {
            "policy": policy,
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
                        else sum(value != 0 for group in self.bookmark_groups for value in group)
                        if command == BOOKMARK_COMMAND
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
                        else sum(value != 0 for group in self.bookmark_groups for value in group)
                        if command == BOOKMARK_COMMAND
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
            "bookmarks": bookmarks,
        }

    def rebase_auxiliary_state(
        self,
        baseline: ParsedBackupBlob,
        candidate: ParsedBackupBlob,
        *,
        insertion_offset: int,
        metadata_delta: int,
    ) -> tuple["PreparedFixedStateSnapshot", dict[str, Any], dict[str, Any]]:
        """Rebase established pointers and prove all opaque bytes unchanged."""

        if not self.display_history_record_offsets and not self.bookmark_group_paths:
            result = replace(self, prospective_raw_blocks=self.raw_blocks)
            empty_display = {
                "present": False,
                "preservation_policy": "raw_exact",
                "raw_preserved_exactly": True,
                "semantic_preserved": False,
                "references_rebased": 0,
            }
            empty_bookmarks = {
                "present": False,
                "preservation_policy": "raw_exact",
                "raw_preserved_exactly": True,
                "semantic_preserved": False,
                "references_rebased": 0,
                "opaque_values_preserved_exactly": True,
                "groups": [],
            }
            return result, empty_display, empty_bookmarks
        if baseline.header.metadata_start != self.display_history_metadata_start:
            raise PreparedFixedStateError("auxiliary-state baseline metadata base changed")
        if candidate.header.metadata_start != baseline.header.metadata_start:
            raise PreparedFixedStateError("auxiliary-state candidate metadata base changed")
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
            raise PreparedFixedStateError("auxiliary-state rebase geometry is not record-aligned")
        try:
            rebased_ranges, rebased_grouped = rebase_fixed_state_responses(
                self.raw_blocks[:4], self.raw_blocks[4],
                insertion_offset=insertion_offset, metadata_delta=metadata_delta,
            )
        except StateSerializationError as exc:
            raise PreparedFixedStateError(f"auxiliary-state semantic rebase failed: {exc}") from exc
        prospective_blocks = tuple(rebased_ranges) + (rebased_grouped,)
        if prospective_blocks[1:4] != self.raw_blocks[1:4]:
            raise PreparedFixedStateError("auxiliary-state rebase changed zero-count Mark state")

        display_result, display_report = self._verify_display_history_rebase(
            baseline, candidate, prospective_blocks,
            insertion_offset=insertion_offset, metadata_delta=metadata_delta,
        )
        bookmark_offsets: list[int] = []
        bookmark_reports: list[dict[str, Any]] = []
        try:
            before_bookmarks = parse_grouped_values_response(self.raw_blocks[4])
            after_bookmarks = parse_grouped_values_response(prospective_blocks[4])
        except Exception as exc:
            raise PreparedFixedStateError(f"bookmark rebased response is malformed: {exc}") from exc
        if before_bookmarks.unused_tail_hex != after_bookmarks.unused_tail_hex:
            raise PreparedFixedStateError("bookmark rebase changed unused tail bytes")
        bindings = {index: (offset, path) for index, offset, path in self.bookmark_group_paths}
        for group_index, (before_group, after_group) in enumerate(zip(before_bookmarks.groups, after_bookmarks.groups)):
            if tuple(before_group[1:]) != tuple(after_group[1:]):
                raise PreparedFixedStateError("bookmark rebase changed opaque values")
            if group_index not in bindings:
                if tuple(before_group) != tuple(after_group):
                    raise PreparedFixedStateError("bookmark rebase changed an unbound group")
                continue
            before_offset, bound_path = bindings[group_index]
            expected_offset = before_offset + metadata_delta if before_offset >= insertion_offset else before_offset
            if before_group[0] != before_offset or after_group[0] != expected_offset:
                raise PreparedFixedStateError("bookmark record pointer was unexpectedly shifted or left unshifted")
            before_absolute = baseline.header.metadata_start + before_offset
            after_absolute = candidate.header.metadata_start + expected_offset
            if baseline.paths.get(before_absolute) != bound_path or candidate.paths.get(after_absolute) != bound_path:
                raise PreparedFixedStateError("rebased bookmark pointer resolves to a different path")
            try:
                before_record = baseline.record_at(before_absolute)
                after_record = candidate.record_at(after_absolute)
                before_prefix, before_payload = baseline.payload_parts(before_record)
                after_prefix, after_payload = candidate.payload_parts(after_record)
            except BackupFormatError as exc:
                raise PreparedFixedStateError("bookmark pointer does not resolve to a complete file record") from exc
            before_raw = bytes.fromhex(before_record.raw_hex)
            after_raw = bytes.fromhex(after_record.raw_hex)
            if before_raw[:4] + before_raw[0x0C:] != after_raw[:4] + after_raw[0x0C:]:
                raise PreparedFixedStateError("rebased bookmark pointer changed preserved record bytes")
            if before_prefix != after_prefix or before_payload != after_payload:
                raise PreparedFixedStateError("rebased bookmark pointer changed preserved payload")
            bookmark_offsets.append(expected_offset)
            bookmark_reports.append({
                "group_index": group_index,
                "before_relative_record_offset": f"0x{before_offset:08x}",
                "candidate_relative_record_offset": f"0x{expected_offset:08x}",
                "path": "\\".join(bound_path),
                "rebased": before_offset != expected_offset,
                "opaque_values_sha256": _sha256(b"".join(value.to_bytes(4, "big") for value in before_group[1:])),
                "opaque_values_preserved_exactly": True,
            })
        result = replace(
            display_result,
            prospective_raw_blocks=prospective_blocks,
            bookmark_candidate_record_offsets=tuple(bookmark_offsets),
        )
        return result, display_report, {
            "present": bool(bookmark_reports),
            "preservation_policy": "record_pointer_semantic_rebase_opaque_values_raw_exact" if bookmark_reports else "raw_exact",
            "raw_preserved_exactly": prospective_blocks[4] == self.raw_blocks[4],
            "semantic_preserved": bool(bookmark_reports),
            "insertion_offset": f"0x{insertion_offset:08x}" if bookmark_reports else None,
            "metadata_delta": f"0x{metadata_delta:08x}" if bookmark_reports else "0x00000000",
            "references_rebased": sum(item["rebased"] for item in bookmark_reports),
            "opaque_values_preserved_exactly": True,
            "unused_tail_preserved_exactly": True,
            "groups": bookmark_reports,
        }

    def _verify_display_history_rebase(
        self, baseline: ParsedBackupBlob, candidate: ParsedBackupBlob,
        prospective_blocks: tuple[bytes, bytes, bytes, bytes, bytes], *,
        insertion_offset: int, metadata_delta: int,
    ) -> tuple["PreparedFixedStateSnapshot", dict[str, Any]]:
        """Verify the display-history part of a combined auxiliary rebase."""
        if not self.display_history_record_offsets:
            return self, {
                "present": False, "preservation_policy": "raw_exact",
                "raw_preserved_exactly": True, "semantic_preserved": False,
                "references_rebased": 0,
            }
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

    def rebase_display_history(
        self,
        baseline: ParsedBackupBlob,
        candidate: ParsedBackupBlob,
        *,
        insertion_offset: int,
        metadata_delta: int,
    ) -> tuple["PreparedFixedStateSnapshot", dict[str, Any]]:
        """Compatibility wrapper for the earlier display-only callers."""

        result, display, _bookmarks = self.rebase_auxiliary_state(
            baseline,
            candidate,
            insertion_offset=insertion_offset,
            metadata_delta=metadata_delta,
        )
        return result, display

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
    *,
    allow_opaque_tail: bool = False,
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
    if any(tail) and not allow_opaque_tail:
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


def _parse_bookmarks(
    backup: VerifiedBackup,
    data: bytes,
) -> tuple[
    tuple[tuple[int, int, int, int, int], ...],
    tuple[tuple[int, int, tuple[str, ...]], ...],
    int,
]:
    """Bind only bookmark dword 1; leave dwords 2--5 opaque."""

    try:
        parsed_response = parse_grouped_values_response(data)
    except Exception as exc:
        raise PreparedFixedStateError(f"bookmark response is malformed: {exc}") from exc
    parsed_backup = _load_backup_blob(backup)
    groups = tuple(tuple(group) for group in parsed_response.groups)
    paths: list[tuple[int, int, tuple[str, ...]]] = []
    for group_index, group in enumerate(groups):
        if not any(group):
            continue
        relative_offset = group[0]
        if relative_offset == 0:
            raise PreparedFixedStateError(
                f"bookmark group {group_index} has opaque activity without a record pointer"
            )
        if relative_offset % 0x40:
            raise PreparedFixedStateError(
                f"bookmark group {group_index} record pointer 0x{relative_offset:08x} is not record-aligned"
            )
        absolute_offset = parsed_backup.header.metadata_start + relative_offset
        try:
            record = parsed_backup.record_at(absolute_offset)
        except BackupFormatError as exc:
            raise PreparedFixedStateError(
                f"bookmark group {group_index} record pointer 0x{relative_offset:08x} is dangling"
            ) from exc
        path = parsed_backup.paths.get(absolute_offset)
        if path is None or record.kind != "file":
            raise PreparedFixedStateError(
                f"bookmark group {group_index} does not resolve to an existing file"
            )
        paths.append((group_index, relative_offset, tuple(path)))
    if not paths:
        raise PreparedFixedStateError(
            "bookmark response is nonzero but contains no bound bookmark group"
        )
    return groups, tuple(paths), parsed_backup.header.metadata_start


def assess_prepared_fixed_state(
    backup: VerifiedBackup,
    *,
    allow_verified_display_history: bool = False,
    allow_verified_bookmarks: bool = False,
) -> PreparedFixedStateAssessment:
    """Assess the exact zero state, or opt-in verified display history.

    The opt-ins are intentionally separate from normal product paths. The
    bookmark mode also accepts authoritative zero-count 0x001c--0x001e blocks
    with opaque unused bytes, while preserving every such byte exactly.
    """

    if not isinstance(backup, VerifiedBackup):
        raise PreparedFixedStateError("fixed-state assessment requires a VerifiedBackup")

    reasons: list[str] = []
    reports: list[dict[str, Any]] = []
    blocks: list[bytes] = []
    display_history_offsets: tuple[int, ...] = ()
    display_history_paths: tuple[tuple[int, tuple[str, ...]], ...] = ()
    display_history_metadata_start = 0x40
    bookmark_groups: tuple[tuple[int, int, int, int, int], ...] = ()
    bookmark_paths: tuple[tuple[int, int, tuple[str, ...]], ...] = ()
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
                        backup, data, allow_opaque_tail=allow_verified_bookmarks
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
                if active_entries and allow_verified_bookmarks:
                    (
                        bookmark_groups,
                        bookmark_paths,
                        bookmark_metadata_start,
                    ) = _parse_bookmarks(backup, data)
                    if bookmark_metadata_start != display_history_metadata_start:
                        block_reasons.append(f"{key} metadata base differs from display history")
                    report["bookmark_groups"] = [
                        {
                            "group_index": group_index,
                            "record_offset": f"0x{offset:08x}",
                            "path": "\\".join(path),
                            "opaque_values_sha256": _sha256(
                                b"".join(value.to_bytes(4, "big") for value in bookmark_groups[group_index][1:])
                            ),
                        }
                        for group_index, offset, path in bookmark_paths
                    ]
                elif active_entries:
                    block_reasons.append(f"{key} contains nonzero bookmark values")
                if tail_nonzero and not allow_verified_bookmarks:
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
                if tail_nonzero and not allow_verified_bookmarks:
                    block_reasons.append(f"{key} contains nonzero reserved tail bytes")
        except Exception as exc:
            reasons.append(f"{key} is malformed: {exc}")
            reports.append(report)
            continue
        report["active_entries"] = active_entries
        semantically_supported = (
            command == DISPLAY_HISTORY_COMMAND and bool(display_history_offsets)
        ) or (
            command == BOOKMARK_COMMAND and bool(bookmark_paths)
        ) or (
            allow_verified_bookmarks
            and command in (0x001C, 0x001D, 0x001E)
            and active_entries == 0
            and parsed.value_04_be16 == 0
            and parsed.value_06_be16 == 0
        )
        if data != b"\x00" * 64 and not semantically_supported:
            block_reasons.append(f"{key} differs from exact capture-7 all-zero state")
        reasons.extend(block_reasons)
        report["supported"] = not block_reasons
        blocks.append(data)
        reports.append(report)

    if len(blocks) != len(FIXED_STATE_COMMANDS):
        return PreparedFixedStateAssessment(False, tuple(reasons), None, tuple(reports))
    if not display_history_offsets and not bookmark_paths and (
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
        bookmark_groups=bookmark_groups,
        bookmark_group_paths=bookmark_paths,
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
