"""Fail-closed fixed-state derivation for the provisional delete policy.

The state experiment proves only two safe inputs for a modern offline
candidate: an exact all-zero ``0x001b``--``0x001f`` state, or the exact target
reference forms observed for Display History, Mark 1, and Bookmark 1.  This
module parses those structures, clears only those proven target references,
preserves the raw bytes otherwise, and rejects every unfamiliar nonzero form.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

from .backup import parse_grouped_values_response, parse_offset_list_response


DELETE_STATE_FORMAT = "infocarry-supported-delete-state-v1"
FIXED_STATE_COMMANDS = (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)
FIXED_STATE_LENGTH = 0x40
_ZERO_STATE = b"\x00" * FIXED_STATE_LENGTH
_BOOKMARK_TARGET_TAG = 0x80000000


class DeleteStateError(ValueError):
    """Raised when fixed state is not in the supported delete subset."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_block(command: int, value: Any) -> bytes:
    if not isinstance(value, bytes) or len(value) != FIXED_STATE_LENGTH:
        raise DeleteStateError(f"fixed state 0x{command:04x} must be exactly 64 bytes")
    return value


def _clear_offset_list(command: int, raw: bytes, target_ref: int) -> tuple[bytes, bool, str]:
    if raw == _ZERO_STATE:
        parse_offset_list_response(raw)
        return raw, False, "exact all-zero state preserved"
    try:
        parsed = parse_offset_list_response(raw)
    except Exception as exc:
        raise DeleteStateError(f"fixed state 0x{command:04x} is malformed: {exc}") from exc
    if parsed.value_04_be16 != 0 or parsed.value_06_be16 != 0:
        raise DeleteStateError(f"fixed state 0x{command:04x} has unfamiliar nonzero header fields")
    active_end = 8 + parsed.count * 4
    if any(raw[active_end:]):
        raise DeleteStateError(f"fixed state 0x{command:04x} has unfamiliar nonzero tail bytes")
    if parsed.count != 1 or tuple(parsed.record_offsets) != (target_ref,):
        raise DeleteStateError(
            f"fixed state 0x{command:04x} contains an unsupported reference pattern"
        )
    return _ZERO_STATE, True, "single target reference cleared"


def _clear_bookmarks(raw: bytes, target_ref: int) -> tuple[bytes, bool, str]:
    if raw == _ZERO_STATE:
        parse_grouped_values_response(raw)
        return raw, False, "exact all-zero state preserved"
    try:
        parsed = parse_grouped_values_response(raw)
    except Exception as exc:
        raise DeleteStateError(f"fixed state 0x001f is malformed: {exc}") from exc
    expected = (
        (target_ref, 0, _BOOKMARK_TARGET_TAG, 0, 0),
        (0, 0, 0, 0, 0),
    )
    if tuple(tuple(group) for group in parsed.groups) != expected:
        raise DeleteStateError("fixed state 0x001f contains an unsupported bookmark pattern")
    return _ZERO_STATE, True, "Bookmark 1 target reference cleared"


@dataclass(frozen=True)
class DeleteStateCandidate:
    """Raw fixed-state bytes before and after the supported transformation."""

    before: tuple[bytes, bytes, bytes, bytes, bytes]
    after: tuple[bytes, bytes, bytes, bytes, bytes]
    target_metadata_reference: int
    changed_commands: tuple[int, ...]
    audit: Mapping[str, Any]

    @property
    def range1(self) -> bytes:
        return b"".join(self.after[:4])

    @property
    def grouped_values(self) -> bytes:
        return self.after[4]

    @property
    def before_hashes(self) -> tuple[str, ...]:
        return tuple(_sha256(value) for value in self.before)

    @property
    def after_hashes(self) -> tuple[str, ...]:
        return tuple(_sha256(value) for value in self.after)


def derive_supported_delete_state(
    fixed_state: Mapping[int, bytes],
    *,
    target_record_offset: int,
    metadata_start: int,
    record_size: int,
) -> DeleteStateCandidate:
    """Derive fixed state for one exact target, or fail closed."""

    if not isinstance(fixed_state, Mapping):
        raise DeleteStateError("fixed_state must be a command-to-bytes mapping")
    if isinstance(target_record_offset, bool) or not isinstance(target_record_offset, int):
        raise DeleteStateError("target record offset must be an integer")
    if isinstance(metadata_start, bool) or not isinstance(metadata_start, int) or metadata_start < 0:
        raise DeleteStateError("metadata_start must be a non-negative integer")
    if isinstance(record_size, bool) or not isinstance(record_size, int) or record_size <= 0:
        raise DeleteStateError("record_size must be positive")
    if target_record_offset < metadata_start or (target_record_offset - metadata_start) % record_size:
        raise DeleteStateError("target record offset is not aligned to the metadata model")
    target_ref = target_record_offset - metadata_start
    if target_ref > 0xFFFFFFFF:
        raise DeleteStateError("target metadata reference does not fit the state format")
    if set(fixed_state) != set(FIXED_STATE_COMMANDS):
        raise DeleteStateError("fixed state must contain exactly commands 0x001b through 0x001f")

    before = tuple(_require_block(command, fixed_state[command]) for command in FIXED_STATE_COMMANDS)
    after_values: list[bytes] = []
    classifications: dict[str, str] = {}
    changed: list[int] = []
    for command, raw in zip(FIXED_STATE_COMMANDS[:4], before[:4]):
        transformed, did_change, classification = _clear_offset_list(command, raw, target_ref)
        after_values.append(transformed)
        classifications[f"0x{command:04x}"] = classification
        if did_change:
            changed.append(command)
    transformed, did_change, classification = _clear_bookmarks(before[4], target_ref)
    after_values.append(transformed)
    classifications["0x001f"] = classification
    if did_change:
        changed.append(0x001F)

    audit = {
        "format": DELETE_STATE_FORMAT,
        "policy": "exact_target_reference_clear_only",
        "target_metadata_reference_hex": f"0x{target_ref:08x}",
        "metadata_start_hex": f"0x{metadata_start:08x}",
        "record_size": record_size,
        "changed_commands": [f"0x{command:04x}" for command in changed],
        "classifications": classifications,
        "before_sha256": {
            f"0x{command:04x}": _sha256(raw)
            for command, raw in zip(FIXED_STATE_COMMANDS, before)
        },
        "after_sha256": {
            f"0x{command:04x}": _sha256(raw)
            for command, raw in zip(FIXED_STATE_COMMANDS, after_values)
        },
        "unknown_nonzero_state_rejected": True,
        "usb_transmission_performed": False,
    }
    return DeleteStateCandidate(
        before=before,
        after=tuple(after_values),  # type: ignore[arg-type]
        target_metadata_reference=target_ref,
        changed_commands=tuple(changed),
        audit=audit,
    )


def derive_preserved_delete_state(backup, baseline, candidate, *, target_record_offset):
    """Preserve established history/bookmark associations across one removal.

    Unlike the historical target-clear policy, this opt-in refuses to delete
    an auxiliary-referenced target. Only the already supported history and
    bookmark pointer fields may move; Mark state and opaque bytes stay exact.
    """
    from .prepared_fixed_state import assess_prepared_fixed_state

    try:
        snapshot = assess_prepared_fixed_state(
            backup, allow_verified_display_history=True,
            allow_verified_bookmarks=True,
        ).require_supported()
        size = baseline.header.record_size
        if size != 0x40 or candidate.header.metadata_start != baseline.header.metadata_start:
            raise DeleteStateError("unsupported delete metadata geometry")
        if len(candidate.records) != len(baseline.records) - 1:
            raise DeleteStateError("auxiliary rebase requires exactly one removed record")
        target_ref = target_record_offset - baseline.header.metadata_start
        if target_ref < 0 or target_ref % size:
            raise DeleteStateError("delete target metadata reference is not aligned")
        after = [bytearray(raw) for raw in snapshot.raw_blocks]
        references = []

        def preserve(relative, path, block_index, byte_offset):
            if relative == target_ref:
                raise DeleteStateError("delete target is referenced by protected auxiliary state")
            new_ref = relative - size if relative > target_ref else relative
            old_offset = baseline.header.metadata_start + relative
            new_offset = candidate.header.metadata_start + new_ref
            if baseline.paths.get(old_offset) != path or candidate.paths.get(new_offset) != path:
                raise DeleteStateError("auxiliary reference no longer resolves to the same survivor")
            old_record, new_record = baseline.record_at(old_offset), candidate.record_at(new_offset)
            old_raw, new_raw = bytes.fromhex(old_record.raw_hex), bytes.fromhex(new_record.raw_hex)
            if old_record.kind != "file" or new_record.kind != "file":
                raise DeleteStateError("protected auxiliary reference is not an ordinary file")
            if old_raw[:4] + old_raw[8:] != new_raw[:4] + new_raw[8:]:
                raise DeleteStateError("protected survivor bytes changed outside its payload pointer")
            if baseline.payload_parts(old_record) != candidate.payload_parts(new_record):
                raise DeleteStateError("protected survivor prefix or payload changed")
            after[block_index][byte_offset:byte_offset + 4] = new_ref.to_bytes(4, "big")
            references.append({"command": f"0x{FIXED_STATE_COMMANDS[block_index]:04x}",
                "byte_offset": byte_offset, "before_relative": relative,
                "after_relative": new_ref, "path": "\\".join(path)})

        for index, (relative, path) in enumerate(snapshot.display_history_paths):
            preserve(relative, path, 0, 8 + index * 4)
        for group_index, relative, path in snapshot.bookmark_group_paths:
            preserve(relative, path, 4, group_index * 20)
        after = tuple(bytes(raw) for raw in after)
        # Independently prove that no byte outside a resolved pointer moved.
        allowed = {(entry["command"], entry["byte_offset"] + i)
                   for entry in references for i in range(4)}
        for command, old, new in zip(FIXED_STATE_COMMANDS, snapshot.raw_blocks, after):
            for offset, (left, right) in enumerate(zip(old, new)):
                if left != right and (f"0x{command:04x}", offset) not in allowed:
                    raise DeleteStateError("delete rebase changed opaque fixed-state bytes")
        changed = tuple(c for c, old, new in zip(FIXED_STATE_COMMANDS, snapshot.raw_blocks, after)
                        if old != new)
        return DeleteStateCandidate(snapshot.raw_blocks, after, target_ref, changed,
            {"format": DELETE_STATE_FORMAT,
             "policy": "preserve_supported_auxiliary_associations_across_one_removal",
             "target_referenced": False, "metadata_delta": -size,
             "references": references, "opaque_bytes_preserved_exactly": True,
             "usb_transmission_performed": False})
    except DeleteStateError:
        raise
    except Exception as exc:
        raise DeleteStateError(f"protected delete-state derivation failed: {exc}") from exc


__all__ = [
    "DELETE_STATE_FORMAT",
    "FIXED_STATE_COMMANDS",
    "FIXED_STATE_LENGTH",
    "DeleteStateCandidate",
    "DeleteStateError",
    "derive_supported_delete_state",
    "derive_preserved_delete_state",
]
