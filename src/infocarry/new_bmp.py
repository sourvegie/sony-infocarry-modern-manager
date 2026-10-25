"""Offline construction of one template-backed root-level BMP record.

The record is cloned from an existing reachable BMP (including its opaque
record fields and native payload prefix) and inserted into the existing root
directory by the established backup duplicator. This creates no device,
sender, claim, marker, UI, or capability gate by itself.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .backup import parse_grouped_values_response, parse_offset_list_response
from .backup_duplicate import BackupDuplicateError, add_file_from_template
from .backup_format import BackupFormatError, parse_backup_blob
from .new_txt import (
    NewTxtAddError, NewTxtAddResult, _build_transaction,
    _preservation_report, _read_verified_object, _validate_complete_backup,
)
from .prepared_media_package import PreparedMediaPackageError, validate_bmp_payload
from .write_state import StateSerializationError, rebase_fixed_state_responses
from .write_gate import DEFAULT_MAX_AGE_SECONDS


ROOT_BMP_ADD_FORMAT = "infocarry-offline-new-root-bmp-v1"
_FIXED_STATE_KEYS = (
    "0x001b:response-001b", "0x001c:response-001c",
    "0x001d:response-001d", "0x001e:response-001e",
)


@dataclass(frozen=True)
class NewBmpAddResult(NewTxtAddResult):
    """Typed BMP candidate using the existing immutable sender result shape."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_content_geometry(parsed, label: str) -> None:
    """Require reachable file segments to be aligned, bounded and disjoint."""
    segments = []
    for offset, path in parsed.paths.items():
        record = parsed.record_at(offset)
        if record.kind != "file":
            continue
        try:
            prefix, payload = parsed.payload_parts(record)
        except BackupFormatError as exc:
            raise NewTxtAddError(f"{label} file segment is invalid at {'\\'.join(path)}: {exc}") from exc
        start = record.field_04_be32
        end = start + len(prefix) + len(payload)
        if start % 4 or end > parsed.header.content_length or end < start:
            raise NewTxtAddError(f"{label} file segment has unsupported alignment/bounds at {'\\'.join(path)}")
        segments.append((start, end, path))
    segments.sort()
    for previous, current in zip(segments, segments[1:]):
        if current[0] < previous[1]:
            raise NewTxtAddError(
                f"{label} file segments overlap at {'\\'.join(previous[2])} and {'\\'.join(current[2])}"
            )


def _resolve_file_reference(parsed, relative_offset: int, label: str) -> tuple[str, ...]:
    absolute_offset = parsed.header.metadata_start + relative_offset
    try:
        record = parsed.record_at(absolute_offset)
    except BackupFormatError as exc:
        raise NewTxtAddError(f"{label} is dangling in the native record table") from exc
    path = parsed.paths.get(absolute_offset)
    if path is None or record.kind != "file":
        raise NewTxtAddError(f"{label} does not resolve to a reachable file")
    return tuple(path)


def _validate_fixed_state_rebase(parsed_before, parsed_after, state_before, state_after,
                                 grouped_before: bytes, grouped_after: bytes,
                                 *, insertion_offset: int, metadata_delta: int) -> None:
    """Check active fixed-state pointers still identify the same surviving files."""
    for index, (before, after) in enumerate(zip(state_before, state_after)):
        old = parse_offset_list_response(before)
        new = parse_offset_list_response(after)
        if (old.value_04_be16, old.value_06_be16, old.count) != (
                new.value_04_be16, new.value_06_be16, new.count):
            raise NewTxtAddError(f"fixed-state list {index} changed its header/count")
        active_end = 8 + old.count * 4
        if before[active_end:] != after[active_end:]:
            raise NewTxtAddError(f"fixed-state list {index} changed its unused bytes")
        if len(set(old.record_offsets)) != len(old.record_offsets):
            raise NewTxtAddError(f"fixed-state list {index} has duplicate active references")
        for entry_index, (before_offset, after_offset) in enumerate(
                zip(old.record_offsets, new.record_offsets)):
            if before_offset == 0:
                raise NewTxtAddError(f"fixed-state list {index} has a null active reference")
            expected_path = _resolve_file_reference(
                parsed_before, before_offset, f"fixed-state list {index} entry {entry_index}")
            expected_offset = before_offset + (metadata_delta if before_offset >= insertion_offset else 0)
            if after_offset != expected_offset or _resolve_file_reference(
                    parsed_after, after_offset,
                    f"rebased fixed-state list {index} entry {entry_index}") != expected_path:
                raise NewTxtAddError(f"fixed-state list {index} no longer points to its original file")

    old_groups = parse_grouped_values_response(grouped_before).groups
    new_groups = parse_grouped_values_response(grouped_after).groups
    if grouped_before[40:] != grouped_after[40:]:
        raise NewTxtAddError("grouped-state unused bytes changed")
    for group_index, (old_group, new_group) in enumerate(zip(old_groups, new_groups)):
        if not any(old_group):
            if any(new_group):
                raise NewTxtAddError(f"inactive grouped-state entry {group_index} changed")
            continue
        before_offset, after_offset = old_group[0], new_group[0]
        if before_offset == 0:
            raise NewTxtAddError(f"active grouped-state entry {group_index} has a null record pointer")
        expected_path = _resolve_file_reference(
            parsed_before, before_offset, f"grouped-state entry {group_index}")
        expected_offset = before_offset + (metadata_delta if before_offset >= insertion_offset else 0)
        if after_offset != expected_offset or old_group[1:] != new_group[1:] or _resolve_file_reference(
                parsed_after, after_offset,
                f"rebased grouped-state entry {group_index}") != expected_path:
            raise NewTxtAddError(f"grouped-state entry {group_index} no longer points to its original file")


def _build_new_bmp_add(
    backup_directory: Path,
    source_path: Path,
    target_filename: str,
    *,
    source_template_offset: int,
    available_capacity_bytes: Optional[int],
    record_timestamp_be32: int,
    now=None,
    max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
    target_directory_path: tuple[str, ...] = ("root",),
    target_directory_offset: int | None = None,
) -> NewTxtAddResult:
    """Build one unread 16-byte-prefix BMP candidate offline.

    This deliberately accepts only the P16-observed all-``ff`` 16-byte BMP
    prefix and unread ``0xe0`` file state. All other BMP record bytes are
    copied from a reachable BMP template, including opaque fields.
    """
    if (not isinstance(target_filename, str) or not target_filename.endswith(".bmp")
            or target_filename in {".bmp", "..bmp"} or "\x00" in target_filename
            or "/" in target_filename or "\\" in target_filename
            or target_filename != target_filename.strip()):
        raise NewTxtAddError("target filename must be one trimmed root-level .bmp name")
    basename = target_filename[:-4]
    try:
        encoded = basename.encode("cp932", errors="strict")
    except UnicodeEncodeError as exc:
        raise NewTxtAddError("target filename is not representable in CP932") from exc
    if not basename or "." in basename or len(encoded) >= 40:
        raise NewTxtAddError("target basename must be unambiguous and leave room for NUL")
    if (available_capacity_bytes is None or isinstance(available_capacity_bytes, bool)
            or not isinstance(available_capacity_bytes, int) or available_capacity_bytes < 0):
        raise NewTxtAddError("available capacity requires an explicit non-negative byte budget")
    if (isinstance(record_timestamp_be32, bool) or not isinstance(record_timestamp_be32, int)
            or not 0 <= record_timestamp_be32 <= 0xffffffff):
        raise NewTxtAddError("record timestamp must fit uint32")

    source = Path(source_path).expanduser().resolve()
    try:
        payload = source.read_bytes()
    except OSError as exc:
        raise NewTxtAddError(f"BMP source could not be read: {exc}") from exc
    try:
        validate_bmp_payload(payload)
    except PreparedMediaPackageError as exc:
        raise NewTxtAddError(f"BMP payload failed the reviewed image profile: {exc}") from exc

    backup = _validate_complete_backup(Path(backup_directory), now=now,
                                       max_age_seconds=max_age_seconds)
    if target_directory_path != ("root",) and backup.device_identity != ("0x054c", "0x001e"):
        raise NewTxtAddError("nested BMP preparation requires a VNW-V15 archive")
    baseline_blob = _read_verified_object(backup, "0x8004:backup-blob")
    try:
        before = parse_backup_blob(baseline_blob)
        template = before.record_at(source_template_offset)
    except BackupFormatError as exc:
        raise NewTxtAddError(f"BMP template/baseline is invalid: {exc}") from exc
    _validate_content_geometry(before, "baseline")
    template_path = before.paths.get(source_template_offset)
    if (template_path is None or template.kind != "file" or
            template.extension != "bmp" or template.flag != 0xe0 or
            template.field_14_be32 != 0x100 or template.payload_prefix_length != 16):
        raise NewTxtAddError("template must be a reachable unread BMP with 16-byte prefix")
    prefix, template_payload = before.payload_parts(template)
    if prefix != b"\xff" * 16:
        raise NewTxtAddError("template BMP prefix differs from the observed all-ff 16-byte form")
    try:
        validate_bmp_payload(template_payload)
    except PreparedMediaPackageError as exc:
        raise NewTxtAddError(f"template BMP payload is invalid: {exc}") from exc
    nested = target_directory_path != ("root",)
    parent_offset = before.header.metadata_start
    if nested:
        matches = [o for o, p in before.paths.items() if p == target_directory_path]
        if (type(target_directory_path) is not tuple or not 2 <= len(target_directory_path) <= 3
                or target_directory_path[0] != "root" or len(matches) != 1
                or type(target_directory_offset) is not int or matches != [target_directory_offset]
                or before.record_at(target_directory_offset).kind != "directory"):
            raise NewTxtAddError("nested BMP requires an exact existing parent path and offset")
        parent_offset = target_directory_offset
        if template.field_10_be32 != 0xffffffff:
            raise NewTxtAddError("nested BMP template opaque field +0x10 must be 0xffffffff")
    target_path = target_directory_path + (basename,)
    target_matches = [path for path in before.paths.values()
                      if tuple(p.casefold() for p in path[:-1]) == tuple(p.casefold() for p in target_directory_path)
                      and path[-1].casefold() == basename.casefold()]
    if target_matches:
        raise NewTxtAddError("BMP target already exists or is ambiguous in its parent")

    try:
        candidate_blob = add_file_from_template(
            before, parent_offset, source_template_offset,
            basename, payload, timestamp_be32=record_timestamp_be32,
            fresh_new_allocation=True,
        )
        after = parse_backup_blob(candidate_blob)
    except (BackupDuplicateError, BackupFormatError, OverflowError) as exc:
        raise NewTxtAddError(f"template-backed root BMP construction failed: {exc}") from exc
    _validate_content_geometry(after, "candidate")
    offsets = [offset for offset, path in after.paths.items() if path == target_path]
    if len(offsets) != 1:
        raise NewTxtAddError("candidate does not contain exactly one target root BMP")
    target = after.record_at(offsets[0])
    if len(after.paths) != len(set(after.paths.values())):
        raise NewTxtAddError("candidate has ambiguous native paths")
    before_root_order = [path for _, path in sorted(
        (offset, path) for offset, path in before.paths.items() if path[:-1] == target_directory_path)]
    after_root_order = [path for _, path in sorted(
        (offset, path) for offset, path in after.paths.items() if path[:-1] == target_directory_path)]
    if after_root_order != before_root_order + [target_path]:
        raise NewTxtAddError("candidate did not append the BMP after existing root children")
    if (target.kind != "file" or target.extension != "bmp" or
            target.flag != 0xe0 or target.field_14_be32 != 0x100):
        raise NewTxtAddError("candidate target changed the cloned BMP record profile")
    new_prefix, new_payload = after.payload_parts(target)
    if new_prefix != prefix or new_payload != payload:
        raise NewTxtAddError("candidate BMP wrapper or payload differs from exact source")
    preservation = _preservation_report(before, after, target_path)
    # Check all surviving semantic identities, timestamps, native prefixes and
    # payloads by path; only established table/content pointers may rebase.
    for old_offset, path in before.paths.items():
        new_offset = next((o for o, p in after.paths.items() if p == path), None)
        if new_offset is None:
            raise NewTxtAddError(f"candidate removed existing path {'\\'.join(path)}")
        old, new = before.record_at(old_offset), after.record_at(new_offset)
        if (old.kind, old.extension, old.flag, old.timestamp_be32,
                old.field_10_be32, old.field_14_be32) != (
                new.kind, new.extension, new.flag, new.timestamp_be32,
                new.field_10_be32, new.field_14_be32):
            raise NewTxtAddError(f"candidate changed surviving record fields at {'\\'.join(path)}")
        if old.kind == "file" and before.payload_parts(old) != after.payload_parts(new):
            raise NewTxtAddError(f"candidate changed surviving file bytes at {'\\'.join(path)}")

    metadata_delta = after.header.metadata_length - before.header.metadata_length
    if metadata_delta != before.header.record_size:
        raise NewTxtAddError("candidate metadata growth is not exactly one record")
    if nested:
        from .delete_model import build_one_nested_file_delete_model
        restored = build_one_nested_file_delete_model(after, "\\".join(target_path) + ".bmp", offsets[0])
        if restored.candidate_blob != baseline_blob:
            raise NewTxtAddError("nested BMP inverse Delete does not restore the exact original model")
    relative_offset = offsets[0] - before.header.metadata_start
    try:
        state_before = tuple(_read_verified_object(backup, key) for key in _FIXED_STATE_KEYS)
        grouped_before = _read_verified_object(backup, "0x001f:response-001f")
        rebased_lists, rebased_grouped = rebase_fixed_state_responses(
            state_before, grouped_before, insertion_offset=relative_offset,
            metadata_delta=metadata_delta)
        _validate_fixed_state_rebase(
            before, after, state_before, rebased_lists, grouped_before, rebased_grouped,
            insertion_offset=relative_offset, metadata_delta=metadata_delta)
        if nested:
            from .prepared_fixed_state import assess_prepared_fixed_state
            snapshot = assess_prepared_fixed_state(backup, allow_verified_display_history=True,
                                                   allow_verified_bookmarks=True).require_supported()
            protected, _history, _bookmarks = snapshot.rebase_auxiliary_state(
                before, after, insertion_offset=relative_offset, metadata_delta=metadata_delta)
            if protected.candidate_raw_blocks != tuple(rebased_lists) + (rebased_grouped,):
                raise NewTxtAddError("nested BMP protected-state derivation disagrees with pointer rebase")
    except StateSerializationError as exc:
        raise NewTxtAddError(f"protected-state pointer rebase failed: {exc}") from exc
    transaction = _build_transaction(candidate_blob, (b"".join(rebased_lists), rebased_grouped))
    growth = len(candidate_blob) - len(baseline_blob)
    if growth < 0 or growth > available_capacity_bytes:
        raise NewTxtAddError("candidate growth exceeds the supplied safe capacity budget")
    padding = growth - metadata_delta - len(prefix) - len(payload)
    if padding < 0 or padding >= 4:
        raise NewTxtAddError("candidate alignment padding is outside the observed 0..3-byte range")

    audit = {
        "format": ROOT_BMP_ADD_FORMAT, "state": "offline_only",
        "usb_transmission_performed": False,
        "device_identity": {"vendor_id": backup.device_identity[0], "product_id": backup.device_identity[1]},
        "source": {"path": str(source), "size": len(payload), "sha256": _sha(payload),
                   "encoded_payload_size": len(payload), "encoded_payload_sha256": _sha(payload)},
        "target": {"path": "root\\" + target_filename, "record_offset_hex": f"0x{offsets[0]:08x}",
                   "record_flag_hex": f"0x{target.flag:08x}", "extension": target.extension,
                   "record_field_04_hex": f"0x{target.field_04_be32:08x}",
                   "payload_offset_hex": f"0x{after.header.content_start + target.field_04_be32 + len(prefix):08x}",
                   "payload_length": len(new_payload), "payload_sha256": _sha(new_payload),
                   "native_prefix_length": len(new_prefix), "native_prefix_sha256": _sha(new_prefix)},
        "template": {"record_offset_hex": f"0x{source_template_offset:08x}",
                     "path": "\\".join(template_path) + ".bmp",
                     "record_sha256": _sha(bytes.fromhex(template.raw_hex))},
        "baseline": {"backup_directory": str(backup.directory), "manifest_sha256": backup.manifest_sha256,
                     "blob_sha256": backup.blob_sha256, "blob_size": len(baseline_blob)},
        "candidate": {"blob_sha256": _sha(candidate_blob), "blob_size": len(candidate_blob),
                      "transaction_sha256": transaction.concatenated_sha256,
                      "transaction_payload_length": transaction.payload_length,
                      "range_lengths": [len(item) for item in transaction.ranges]},
        "allocation": {"metadata_delta": metadata_delta,
                       "content_delta": after.header.content_length-before.header.content_length,
                       "record_segment_length": len(prefix)+len(payload),
                       "alignment_padding_bytes": padding, "candidate_growth_bytes": growth,
                       "available_capacity_budget_bytes": available_capacity_bytes,
                       "capacity_check": "passed"},
        "state_rebase": {"metadata_insertion_offset_relative_hex": f"0x{relative_offset:08x}",
                         "metadata_delta": metadata_delta,
                         "fixed_response_commands": ["0x001b", "0x001c", "0x001d", "0x001e", "0x001f"],
                         "new_membership_assigned": False,
                         "policy": "shift only established metadata-relative record references"},
        "preservation": preservation,
        "assumptions": [
            "The copied reachable BMP record is the template for one unread 16-byte-prefix root BMP.",
            "Record-specific opaque fields and the 16-byte native prefix are copied unchanged from the BMP template.",
            "No Manager-local sidecar membership is created or changed.",
            "Native root placement, exact completion behavior, and physical readback remain unproven.",
        ],
    }
    if nested:
        audit.update(format="infocarry-offline-new-nested-bmp-v1")
        audit["target"]["path"] = "\\".join(target_path) + ".bmp"
        audit["target"]["parent_record_offset"] = parent_offset
        audit["template"].update(payload_sha256=_sha(template_payload), prefix_sha256=_sha(prefix),
            copied_record_fields_sha256=_sha(bytes.fromhex(template.raw_hex)[:4] + bytes.fromhex(template.raw_hex)[16:24]))
        audit["preservation"]["inverse_nested_delete_exact_baseline"] = True
        audit["assumptions"] = ["Host-only nested BMP insertion and inverse model; no physical nested BMP proof or live admission.",
                                "Native auxiliary response/probe changes are not predicted by this host model."]
    return NewBmpAddResult(candidate_blob, transaction, audit)


def build_new_root_bmp_add(backup_directory, source_path, target_filename, *, source_template_offset,
                          available_capacity_bytes, record_timestamp_be32, now=None,
                          max_age_seconds=DEFAULT_MAX_AGE_SECONDS):
    return _build_new_bmp_add(backup_directory, source_path, target_filename,
        source_template_offset=source_template_offset, available_capacity_bytes=available_capacity_bytes,
        record_timestamp_be32=record_timestamp_be32, now=now, max_age_seconds=max_age_seconds)


def build_new_nested_bmp_add(backup_directory, source_path, target_filename, *, target_directory_path,
                            target_directory_offset, source_template_offset, available_capacity_bytes,
                            record_timestamp_be32, now=None, max_age_seconds=DEFAULT_MAX_AGE_SECONDS):
    """Host-only bounded placement preparation; no facade, sender or admission."""
    if target_directory_path == ("root",):
        raise NewTxtAddError("nested BMP parent must be below root")
    return _build_new_bmp_add(backup_directory, source_path, target_filename,
        target_directory_path=target_directory_path, target_directory_offset=target_directory_offset,
        source_template_offset=source_template_offset, available_capacity_bytes=available_capacity_bytes,
        record_timestamp_be32=record_timestamp_be32, now=now, max_age_seconds=max_age_seconds)


__all__ = ["ROOT_BMP_ADD_FORMAT", "NewBmpAddResult", "build_new_root_bmp_add", "build_new_nested_bmp_add"]
