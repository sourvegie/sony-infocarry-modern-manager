"""Conservative offline authoring of CP932 text replacements.

The preserved manager fixture contains CRLF line endings in every reachable
``txt`` payload inspected so far.  This module therefore normalizes authored
Unicode text to CRLF, encodes it with strict CP932, rejects NUL and unsupported
characters, and preserves the target record's existing native prefix exactly.
It produces an audit report in memory; it does not write files or use USB.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Dict, Optional

from .backup_format import BackupFormatError, ParsedBackupBlob
from .vicdata import (
    OBSERVED_VICDATA_XOR_KEY,
    VicDataError,
    decode_vicdata,
    xor_vicdata,
)
from .vicdata_audit import build_replacement_audit
from .view_wrapper import parse_text_view_wrapper


TEXT_AUTHORING_FORMAT = "infocarry-text-authoring-preview-v1"
TEXT_ENCODING = "cp932"
TEXT_NEWLINE_POLICY = "crlf"


class TextAuthoringError(VicDataError):
    """Raised when text cannot be represented by the conservative policy."""


@dataclass(frozen=True)
class EncodedText:
    """The in-memory result of strict text normalization and encoding."""

    original_text: str
    normalized_text: str
    payload: bytes


def _normalize_crlf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")


def encode_cp932_text(text: str) -> EncodedText:
    """Normalize newlines to CRLF and encode text with strict CP932.

    No replacement character or escape sequence is inserted for unsupported
    Unicode. NUL is rejected because it is unsafe to introduce into a native
    record payload whose surrounding format uses NUL-terminated fields.
    """

    if not isinstance(text, str):
        raise TextAuthoringError("text input must be a Unicode string")
    if "\x00" in text:
        raise TextAuthoringError("text input must not contain NUL characters")
    normalized = _normalize_crlf(text)
    try:
        payload = normalized.encode(TEXT_ENCODING, errors="strict")
    except UnicodeEncodeError as exc:
        offending = normalized[exc.start : exc.end]
        codepoints = ", ".join(f"U+{ord(char):04X}" for char in offending)
        raise TextAuthoringError(
            f"text contains characters unsupported by CP932 ({codepoints})"
        ) from exc
    return EncodedText(text, normalized, payload)


def _validate_capacity(max_payload_bytes: Optional[int]) -> Optional[int]:
    if max_payload_bytes is None:
        return None
    if (
        isinstance(max_payload_bytes, bool)
        or not isinstance(max_payload_bytes, int)
        or not 0 <= max_payload_bytes <= 0xFFFFFFFF
    ):
        raise TextAuthoringError("max_payload_bytes must fit an unsigned 32-bit integer")
    return max_payload_bytes


def _target_path(parsed: ParsedBackupBlob, record_offset: int) -> Optional[str]:
    path = parsed.paths.get(record_offset)
    if path is None:
        return None
    return "\\".join(path)


def preview_text_replacement(
    encoded_vicdata: bytes,
    record_offset: int,
    text: str,
    *,
    max_payload_bytes: Optional[int] = None,
    key: int = OBSERVED_VICDATA_XOR_KEY,
) -> Dict[str, Any]:
    """Build a JSON-safe in-memory audit for replacing one existing ``txt``.

    The returned report deliberately contains hashes and metadata, not the
    candidate payload. Capacity is checked only when the caller supplies an
    explicit bound; no unverified device-capacity assumption is made.
    """

    capacity = _validate_capacity(max_payload_bytes)
    authored = encode_cp932_text(text)
    parsed = decode_vicdata(encoded_vicdata, key=key)
    try:
        record = parsed.record_at(record_offset)
    except BackupFormatError as exc:
        raise TextAuthoringError(
            f"could not resolve text record 0x{record_offset:x}: {exc}"
        ) from exc
    if record.kind != "file" or record.offset not in parsed.paths:
        raise TextAuthoringError(
            f"target 0x{record_offset:x} is not a reachable file record"
        )
    if record.extension.lower() != "txt":
        raise TextAuthoringError(
            f"target 0x{record_offset:x} has extension {record.extension!r}, not 'txt'"
        )
    prefix, old_payload = parsed.payload_parts(record)
    if capacity is not None and len(authored.payload) > capacity:
        raise TextAuthoringError(
            f"encoded text is {len(authored.payload)} bytes; supplied capacity is {capacity}"
        )

    audit = build_replacement_audit(
        encoded_vicdata, record_offset, authored.payload, key=key
    )
    wrapper_details: Dict[str, Any] = {
        "length_bytes": len(prefix),
        "raw_hex": prefix.hex(),
        "preserved_exactly": True,
    }
    if len(prefix) == 0x20:
        wrapper_details["parsed"] = parse_text_view_wrapper(prefix).to_dict()

    audit["format"] = TEXT_AUTHORING_FORMAT
    audit["authoring"] = {
        "encoding": TEXT_ENCODING,
        "newline_policy": TEXT_NEWLINE_POLICY,
        "input_characters": len(authored.original_text),
        "input_utf8_bytes": len(authored.original_text.encode("utf-8")),
        "normalized_characters": len(authored.normalized_text),
        "normalized_utf8_bytes": len(authored.normalized_text.encode("utf-8")),
        "source_text_sha256": hashlib.sha256(
            authored.original_text.encode("utf-8")
        ).hexdigest(),
        "normalized_text_sha256": hashlib.sha256(
            authored.normalized_text.encode("utf-8")
        ).hexdigest(),
        "encoded_payload_bytes": len(authored.payload),
        "encoded_payload_sha256": hashlib.sha256(authored.payload).hexdigest(),
        "unsupported_characters_replaced": False,
        "nul_characters_rejected": True,
    }
    audit["capacity"] = {
        "limit_bytes": capacity,
        "limit_applied": capacity is not None,
        "encoded_payload_within_limit": capacity is None
        or len(authored.payload) <= capacity,
        "device_capacity_claimed": False,
    }
    audit["target"]["path"] = _target_path(parsed, record_offset)
    audit["target"]["native_prefix"] = wrapper_details
    audit["target"]["before_payload_sha256"] = hashlib.sha256(
        old_payload
    ).hexdigest()
    audit["safety"]["candidate_bytes_included"] = False
    return audit


def preview_decoded_text_replacement(
    decoded_vicdata: bytes | bytearray | memoryview,
    record_offset: int,
    text: str,
    *,
    max_payload_bytes: Optional[int] = None,
    key: int = OBSERVED_VICDATA_XOR_KEY,
) -> Dict[str, Any]:
    """Preview a replacement against a raw decoded backup blob.

    Raw macOS backups contain decoded VICDATA, while the existing authoring
    audit intentionally models the manager-side XOR representation. The
    involution is applied in memory only and the resulting report retains the
    same no-candidate/no-device guarantees.
    """

    if not isinstance(decoded_vicdata, (bytes, bytearray, memoryview)):
        raise TextAuthoringError("decoded VICDATA must be bytes-like")
    return preview_text_replacement(
        xor_vicdata(bytes(decoded_vicdata), key=key),
        record_offset,
        text,
        max_payload_bytes=max_payload_bytes,
        key=key,
    )


__all__ = [
    "EncodedText",
    "TEXT_AUTHORING_FORMAT",
    "TEXT_ENCODING",
    "TEXT_NEWLINE_POLICY",
    "TextAuthoringError",
    "encode_cp932_text",
    "preview_decoded_text_replacement",
    "preview_text_replacement",
]
