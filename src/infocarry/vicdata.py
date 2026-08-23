"""Offline helpers for manager-produced ``VICDATA.bin`` files.

Preserved manager fixtures use a single-byte XOR layer around the parsed
backup blob.  The default key here is an observation from those fixtures,
not a guarantee that every manager version uses the same encoding.

This module only transforms bytes in memory.  It contains no USB access and
cannot write to an InfoCarry device. Repacking supports existing-record
payload replacement, a template-based bounded add, a leaf-file delete, and
an in-place rename. It does not generate model nodes or sidecars.
"""

from typing import Mapping, Optional

from .backup_format import BackupFormatError, ParsedBackupBlob, parse_backup_blob
from .backup_duplicate import (
    BackupDuplicateError,
    add_file_from_template,
)
from .backup_repack import (
    BackupRepackError,
    delete_existing_file,
    rename_existing_record,
    repack_existing_records,
)


OBSERVED_VICDATA_XOR_KEY = 0xAA


class VicDataError(BackupFormatError):
    """Raised when a VICDATA transformation cannot be validated safely."""


def _validated_key(key: int) -> int:
    if isinstance(key, bool) or not isinstance(key, int) or not 0 <= key <= 0xFF:
        raise VicDataError("VICDATA XOR key must fit one byte")
    return key


def xor_vicdata(data: bytes, *, key: int = OBSERVED_VICDATA_XOR_KEY) -> bytes:
    """Apply the observed symmetric single-byte XOR transformation."""

    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise VicDataError("VICDATA input must be bytes-like")
    validated_key = _validated_key(key)
    return bytes(value ^ validated_key for value in data)


def decode_vicdata(
    encoded: bytes, *, key: int = OBSERVED_VICDATA_XOR_KEY
) -> ParsedBackupBlob:
    """Decode and structurally validate an encoded manager file."""

    decoded = xor_vicdata(encoded, key=key)
    try:
        return parse_backup_blob(decoded)
    except BackupFormatError as exc:
        raise VicDataError(f"decoded VICDATA failed structural validation: {exc}") from exc


def encode_vicdata(
    decoded: bytes, *, key: int = OBSERVED_VICDATA_XOR_KEY
) -> bytes:
    """Validate a decoded backup blob and apply the observed XOR layer."""

    if not isinstance(decoded, (bytes, bytearray, memoryview)):
        raise VicDataError("decoded VICDATA input must be bytes-like")
    blob = bytes(decoded)
    try:
        parse_backup_blob(blob)
    except BackupFormatError as exc:
        raise VicDataError(f"VICDATA blob failed structural validation: {exc}") from exc
    return xor_vicdata(blob, key=key)


def repack_existing_vicdata(
    encoded: bytes,
    replacements: Mapping[int, bytes],
    *,
    key: int = OBSERVED_VICDATA_XOR_KEY,
) -> bytes:
    """Replace existing record payloads and return validated encoded bytes.

    ``replacements`` maps metadata record offsets to complete payload bytes,
    excluding the record's preserved native prefix.  An empty mapping returns
    byte-identical encoded input after validating it.
    """

    parsed = decode_vicdata(encoded, key=key)
    try:
        rebuilt = repack_existing_records(parsed, replacements)
    except BackupRepackError as exc:
        raise VicDataError(f"VICDATA replacement failed: {exc}") from exc
    result = encode_vicdata(rebuilt, key=key)
    decode_vicdata(result, key=key)
    return result


def rename_existing_vicdata(
    encoded: bytes,
    record_offset: int,
    new_name: str,
    *,
    key: int = OBSERVED_VICDATA_XOR_KEY,
) -> bytes:
    """Rename one reachable record and return validated encoded VICDATA bytes."""

    parsed = decode_vicdata(encoded, key=key)
    try:
        rebuilt = rename_existing_record(parsed, record_offset, new_name)
    except BackupRepackError as exc:
        raise VicDataError(f"VICDATA rename failed: {exc}") from exc
    result = encode_vicdata(rebuilt, key=key)
    decode_vicdata(result, key=key)
    return result


def delete_existing_vicdata(
    encoded: bytes,
    record_offset: int,
    *,
    key: int = OBSERVED_VICDATA_XOR_KEY,
) -> bytes:
    """Delete one reachable file record through the encoded VICDATA layer."""

    parsed = decode_vicdata(encoded, key=key)
    try:
        rebuilt = delete_existing_file(parsed, record_offset)
    except BackupRepackError as exc:
        raise VicDataError(f"VICDATA delete failed: {exc}") from exc
    result = encode_vicdata(rebuilt, key=key)
    decode_vicdata(result, key=key)
    return result


def add_file_from_template_vicdata(
    encoded: bytes,
    target_directory_offset: int,
    source_offset: int,
    new_name: str,
    payload: bytes,
    *,
    timestamp_be32: Optional[int] = None,
    flag: Optional[int] = None,
    metadata_timestamp_be32: Optional[int] = None,
    metadata_timestamps: Optional[Mapping[int, int]] = None,
    key: int = OBSERVED_VICDATA_XOR_KEY,
) -> bytes:
    """Add one file from an existing template and replace its payload."""

    parsed = decode_vicdata(encoded, key=key)
    try:
        rebuilt = add_file_from_template(
            parsed,
            target_directory_offset,
            source_offset,
            new_name,
            payload,
            timestamp_be32=timestamp_be32,
            flag=flag,
            metadata_timestamp_be32=metadata_timestamp_be32,
            metadata_timestamps=metadata_timestamps,
        )
    except (BackupDuplicateError, BackupRepackError) as exc:
        raise VicDataError(f"VICDATA add failed: {exc}") from exc
    result = encode_vicdata(rebuilt, key=key)
    decode_vicdata(result, key=key)
    return result


__all__ = [
    "OBSERVED_VICDATA_XOR_KEY",
    "VicDataError",
    "add_file_from_template_vicdata",
    "decode_vicdata",
    "delete_existing_vicdata",
    "encode_vicdata",
    "repack_existing_vicdata",
    "rename_existing_vicdata",
    "xor_vicdata",
]
