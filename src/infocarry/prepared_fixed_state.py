"""Fail-closed fixed-state preflight for the constrained modern package.

Capture 7 observed five zero-filled 64-byte state objects before and after
the legacy folder add.  This module accepts only that exact supported state.
It returns the verified bytes from the fresh backup for later transaction
construction; it never creates replacement zero blocks or rebases references.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

from .backup import parse_grouped_values_response, parse_offset_list_response
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

    @property
    def range1(self) -> bytes:
        return b"".join(self.raw_blocks[:4])

    @property
    def range2(self) -> bytes:
        return self.raw_blocks[4]

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": "capture7_exact_all_zero_fixed_state",
            "supported": True,
            "raw_bytes_preserved": True,
            "blocks": {
                f"0x{command:04x}": {
                    "sha256": digest,
                    "length": len(self.raw_blocks[index]),
                    "active_entries": 0,
                }
                for index, (command, digest) in enumerate(self.sha256_by_command)
            },
            "prospective_range1_sha256": _sha256(self.range1),
            "prospective_range2_sha256": _sha256(self.range2),
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


def assess_prepared_fixed_state(backup: VerifiedBackup) -> PreparedFixedStateAssessment:
    """Assess exact capture-7-compatible fixed state from a verified backup."""

    if not isinstance(backup, VerifiedBackup):
        raise PreparedFixedStateError("fixed-state assessment requires a VerifiedBackup")

    reasons: list[str] = []
    reports: list[dict[str, Any]] = []
    blocks: list[bytes] = []
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
        try:
            if command == 0x001F:
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
        if data != b"\x00" * 64:
            block_reasons.append(f"{key} differs from exact capture-7 all-zero state")
        reasons.extend(block_reasons)
        report["supported"] = not block_reasons
        blocks.append(data)
        reports.append(report)

    if len(blocks) != len(FIXED_STATE_COMMANDS):
        return PreparedFixedStateAssessment(False, tuple(reasons), None, tuple(reports))
    if len(set(blocks)) != 1 or _sha256(blocks[0]) != CAPTURE7_ZERO_STATE_SHA256:
        if not any("exact capture-7 all-zero" in reason for reason in reasons):
            reasons.append("fixed-state blocks do not match exact capture-7 all-zero state")
    snapshot = PreparedFixedStateSnapshot(
        raw_blocks=tuple(blocks),
        sha256_by_command=tuple(
            (command, _sha256(blocks[index]))
            for index, command in enumerate(FIXED_STATE_COMMANDS)
        ),
    )
    eligible = not reasons
    if not eligible:
        snapshot = None
    return PreparedFixedStateAssessment(eligible, tuple(reasons), snapshot, tuple(reports))


__all__ = [
    "CAPTURE7_ZERO_STATE_SHA256",
    "FIXED_STATE_COMMANDS",
    "PreparedFixedStateAssessment",
    "PreparedFixedStateError",
    "PreparedFixedStateSnapshot",
    "assess_prepared_fixed_state",
]
