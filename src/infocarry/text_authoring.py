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

# These are deliberately small, explicit substitutions at the encoding
# boundary.  They cover punctuation and a few common Latin variants that are
# frequently introduced by copy/paste, while unsupported symbols continue to
# fail closed instead of being replaced with an arbitrary question mark.
CP932_SAFE_SUBSTITUTIONS = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u2026": "...",
    "\u00a0": " ",
    "\u00c0": "A",
    "\u00c1": "A",
    "\u00c2": "A",
    "\u00c3": "A",
    "\u00c4": "A",
    "\u00c5": "A",
    "\u00e0": "a",
    "\u00e1": "a",
    "\u00e2": "a",
    "\u00e3": "a",
    "\u00e4": "a",
    "\u00e5": "a",
    "\u00c7": "C",
    "\u00e7": "c",
    "\u00c8": "E",
    "\u00c9": "E",
    "\u00ca": "E",
    "\u00cb": "E",
    "\u00e8": "e",
    "\u00e9": "e",
    "\u00ea": "e",
    "\u00eb": "e",
    "\u00cc": "I",
    "\u00cd": "I",
    "\u00ce": "I",
    "\u00cf": "I",
    "\u00ec": "i",
    "\u00ed": "i",
    "\u00ee": "i",
    "\u00ef": "i",
    "\u00d1": "N",
    "\u00f1": "n",
    "\u00d2": "O",
    "\u00d3": "O",
    "\u00d4": "O",
    "\u00d5": "O",
    "\u00d6": "O",
    "\u00f2": "o",
    "\u00f3": "o",
    "\u00f4": "o",
    "\u00f5": "o",
    "\u00f6": "o",
    "\u00d9": "U",
    "\u00da": "U",
    "\u00db": "U",
    "\u00dc": "U",
    "\u00f9": "u",
    "\u00fa": "u",
    "\u00fb": "u",
    "\u00fc": "u",
    "\u00dd": "Y",
    "\u00fd": "y",
    "\u00ff": "y",
}
CP932_NORMALIZATION_POLICY = "explicit-punctuation-and-common-latin-v1"


class TextAuthoringError(VicDataError):
    """Raised when text cannot be represented by the conservative policy."""


@dataclass(frozen=True)
class EncodedText:
    """The in-memory result of strict text normalization and encoding."""

    original_text: str
    normalized_text: str
    payload: bytes
    substitutions: tuple[tuple[str, str], ...] = ()


def _normalize_crlf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")


def _normalize_cp932_safe_characters(text: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    substitutions: list[tuple[str, str]] = []
    normalized: list[str] = []
    for character in text:
        replacement = CP932_SAFE_SUBSTITUTIONS.get(character)
        if replacement is None:
            normalized.append(character)
            continue
        normalized.append(replacement)
        substitutions.append((character, replacement))
    return "".join(normalized), tuple(substitutions)


def _unsupported_character_locations(text: str) -> tuple[tuple[int, int, str], ...]:
    """Locate characters that have no deterministic CP932 representation.

    This slower per-character pass runs only after strict encoding fails, so
    ordinary preparation keeps the single-pass encoder cost. Coordinates are
    one-based and refer to the original UTF-8 source text.
    """

    locations: list[tuple[int, int, str]] = []
    line = 1
    column = 1
    previous_was_cr = False
    for character in text:
        replacement = CP932_SAFE_SUBSTITUTIONS.get(character, character)
        try:
            replacement.encode(TEXT_ENCODING, errors="strict")
        except UnicodeEncodeError:
            locations.append((line, column, character))
        if character == "\r":
            line += 1
            column = 1
            previous_was_cr = True
        elif character == "\n":
            if not previous_was_cr:
                line += 1
            column = 1
            previous_was_cr = False
        else:
            column += 1
            previous_was_cr = False
    return tuple(locations)


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
    normalized, substitutions = _normalize_cp932_safe_characters(_normalize_crlf(text))
    try:
        payload = normalized.encode(TEXT_ENCODING, errors="strict")
    except UnicodeEncodeError as exc:
        locations = _unsupported_character_locations(text)
        if locations:
            samples = "; ".join(
                f"U+{ord(character):04X} at line {line}, column {column}"
                for line, column, character in locations[:8]
            )
            remaining = len(locations) - min(len(locations), 8)
            suffix = f"; and {remaining} more" if remaining else ""
            detail = f"{len(locations)} unrepresentable character(s): {samples}{suffix}"
        else:
            offending = normalized[exc.start : exc.end]
            codepoints = ", ".join(f"U+{ord(char):04X}" for char in offending)
            detail = f"{codepoints} (source location unavailable)"
        raise TextAuthoringError(
            f"text contains characters unsupported by CP932: {detail}"
        ) from exc
    return EncodedText(text, normalized, payload, substitutions)


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
        "unsupported_characters_replaced": bool(authored.substitutions),
        "normalization_substitutions": [
            {"from": source, "to": replacement}
            for source, replacement in authored.substitutions
        ],
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
    "CP932_NORMALIZATION_POLICY",
    "CP932_SAFE_SUBSTITUTIONS",
    "TEXT_AUTHORING_FORMAT",
    "TEXT_ENCODING",
    "TEXT_NEWLINE_POLICY",
    "TextAuthoringError",
    "encode_cp932_text",
    "preview_decoded_text_replacement",
    "preview_text_replacement",
]
