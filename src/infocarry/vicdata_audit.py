"""Deterministic, non-transmitting audits for VICDATA replacements."""

import hashlib
from typing import Any, Dict, Mapping

from .backup_format import ParsedBackupBlob
from .vicdata import (
    OBSERVED_VICDATA_XOR_KEY,
    VicDataError,
    decode_vicdata,
    repack_existing_vicdata,
)


VICDATA_AUDIT_FORMAT = "infocarry-vicdata-replacement-audit-v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _regions(parsed: ParsedBackupBlob) -> Mapping[str, bytes]:
    header = parsed.header
    return {
        "header": parsed.data[: header.metadata_start],
        "metadata": parsed.data[header.metadata_start : header.content_start],
        "content": parsed.data[
            header.content_start : header.content_start + header.content_length
        ],
        "trailer": parsed.data[-4:],
    }


def _region_audit(before: bytes, after: bytes) -> Dict[str, Any]:
    overlap = min(len(before), len(after))
    changed = sum(before[index] != after[index] for index in range(overlap))
    return {
        "before_bytes": len(before),
        "after_bytes": len(after),
        "length_delta": len(after) - len(before),
        "changed_positions_in_overlap": changed,
        "before_sha256": _sha256(before),
        "after_sha256": _sha256(after),
        "byte_identical": before == after,
    }


def build_replacement_audit(
    encoded: bytes,
    record_offset: int,
    replacement: bytes,
    *,
    key: int = OBSERVED_VICDATA_XOR_KEY,
) -> Dict[str, Any]:
    """Describe one offline existing-record replacement without saving it.

    The returned object is JSON-serializable. It includes hashes rather than
    candidate bytes and explicitly records that neither USB nor filesystem
    output occurred.
    """

    if not isinstance(replacement, (bytes, bytearray, memoryview)):
        raise VicDataError("replacement payload must be bytes-like")
    payload = bytes(replacement)
    before = decode_vicdata(encoded, key=key)
    record = before.record_at(record_offset)
    if record.kind != "file":
        raise VicDataError(f"replacement target 0x{record_offset:x} is not a file")
    prefix, old_payload = before.payload_parts(record)

    rebuilt_encoded = repack_existing_vicdata(
        encoded, {record_offset: payload}, key=key
    )
    after = decode_vicdata(rebuilt_encoded, key=key)
    after_record = after.record_at(record_offset)
    after_prefix, after_payload = after.payload_parts(after_record)
    if after_payload != payload:
        raise VicDataError("replacement payload failed final verification")

    path_parts = before.paths.get(record_offset)
    path = None if path_parts is None else "\\".join(path_parts)
    if path is not None and record.extension:
        path = f"{path}.{record.extension}"

    before_regions = _regions(before)
    after_regions = _regions(after)
    return {
        "format": VICDATA_AUDIT_FORMAT,
        "encoding": {
            "kind": "observed-single-byte-xor",
            "key_hex": f"0x{key:02x}",
            "universal_key_proven": False,
        },
        "source": {
            "encoded_bytes": len(encoded),
            "encoded_sha256": _sha256(bytes(encoded)),
            "decoded_bytes": len(before.data),
            "decoded_sha256": _sha256(before.data),
            "stored_checksum_hex": f"0x{before.header.stored_checksum:08x}",
        },
        "candidate": {
            "encoded_bytes": len(rebuilt_encoded),
            "encoded_sha256": _sha256(rebuilt_encoded),
            "decoded_bytes": len(after.data),
            "decoded_sha256": _sha256(after.data),
            "stored_checksum_hex": f"0x{after.header.stored_checksum:08x}",
        },
        "target": {
            "record_offset_hex": f"0x{record_offset:08x}",
            "path": path,
            "native_prefix_bytes": len(prefix),
            "native_prefix_preserved": after_prefix == prefix,
            "before_payload_bytes": len(old_payload),
            "before_payload_sha256": _sha256(old_payload),
            "after_payload_bytes": len(payload),
            "after_payload_sha256": _sha256(payload),
        },
        "invariants": {
            "record_count_preserved": len(after.records) == len(before.records),
            "paths_preserved": after.paths == before.paths,
            "target_payload_verified": after_payload == payload,
        },
        "regions": {
            name: _region_audit(before_regions[name], after_regions[name])
            for name in ("header", "metadata", "content", "trailer")
        },
        "safety": {
            "usb_operation_performed": False,
            "filesystem_output_performed": False,
            "candidate_bytes_included": False,
            "device_acceptance_claimed": False,
        },
    }


__all__ = ["VICDATA_AUDIT_FORMAT", "build_replacement_audit"]
