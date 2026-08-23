"""Fail-closed offline eligibility checks for a future selective delete.

This module deliberately stops short of building or sending a delete.  It
turns the Milestone H.1 exit conditions into a framework-independent result so
callers can distinguish a captured-fixture reproduction from a deletion that
is eligible for a later, separately approved workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Optional, Sequence


SUPPORTED_DEVICE = (0x054C, 0x001E)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class DeleteReadinessError(RuntimeError):
    """Raised when a caller attempts to require an ineligible result."""


@dataclass(frozen=True)
class DeleteEligibility:
    """A durable, explainable result for one narrowly scoped delete preflight."""

    eligible: bool
    checks: Mapping[str, bool]
    reasons: tuple[str, ...]
    scope: str = "one_root_txt"

    def require(self) -> None:
        """Raise with every blocker; this never authorizes or sends a write."""

        if not self.eligible:
            raise DeleteReadinessError("not eligible for live deletion: " + "; ".join(self.reasons))

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "scope": self.scope,
            "checks": dict(self.checks),
            "reasons": list(self.reasons),
        }


def _hash_is_valid(value: Optional[str]) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value.lower()))


def _is_root_txt(path: Optional[str]) -> bool:
    return (
        isinstance(path, str)
        and "\x00" not in path
        and path.startswith("root\\")
        and path.count("\\") == 1
        and path.lower().endswith(".txt")
        and len(path) > len("root\\.txt")
    )


def assess_delete_eligibility(
    *,
    device_identity: Optional[tuple[int, int]],
    baseline_manifest_sha256: Optional[str],
    baseline_blob_sha256: Optional[str],
    target_path: Optional[str],
    target_record_offset: Optional[int],
    target_payload_sha256: Optional[str],
    target_is_root_txt: bool,
    disposable_target_confirmed: bool,
    unresolved_references: Sequence[str] = (),
    timestamp_rule: Optional[str],
    fixed_state_derivation: Optional[str],
    candidate_blob_sha256: Optional[str],
    transaction_sha256: Optional[str],
    operation_phrase_bound: bool,
    exactly_one_removed: Optional[bool],
    no_added_paths: Optional[bool],
    unrelated_payloads_preserved: Optional[bool],
    storage_sufficient: Optional[bool],
    captured_fixture_only: bool = False,
) -> DeleteEligibility:
    """Assess the narrow H.1 live-delete conditions without device access.

    ``None`` means that a fact is unknown, not that it is safe.  A captured
    fixture is never eligible merely because it reproduces a legacy candidate.
    The exact candidate and transaction hashes are required for a future
    authorization binding, but this result itself performs no authorization.
    """

    checks: dict[str, bool] = {}
    reasons: list[str] = []

    checks["supported_device_identity"] = device_identity == SUPPORTED_DEVICE
    if not checks["supported_device_identity"]:
        reasons.append("exact supported device identity is not established")

    for name, value, label in (
        ("complete_fresh_backup_manifest", baseline_manifest_sha256, "fresh backup manifest hash"),
        ("complete_fresh_backup_blob", baseline_blob_sha256, "fresh backup dynamic-blob hash"),
        ("target_payload", target_payload_sha256, "target payload hash"),
        ("candidate_blob", candidate_blob_sha256, "candidate dynamic-blob hash"),
        ("prospective_transaction", transaction_sha256, "prospective transaction hash"),
    ):
        checks[name] = _hash_is_valid(value)
        if not checks[name]:
            reasons.append(f"{label} is missing or invalid")

    checks["exact_root_txt_target"] = _is_root_txt(target_path) and target_is_root_txt
    if not checks["exact_root_txt_target"]:
        reasons.append("target is not an exact reachable root-level TXT path")

    checks["record_offset"] = (
        isinstance(target_record_offset, int)
        and not isinstance(target_record_offset, bool)
        and target_record_offset >= 0
        and target_record_offset % 0x40 == 0
    )
    if not checks["record_offset"]:
        reasons.append("target record offset is missing or not metadata-record aligned")

    checks["disposable_target"] = disposable_target_confirmed
    if not checks["disposable_target"]:
        reasons.append("target has not been explicitly confirmed disposable")

    checks["no_unresolved_references"] = not tuple(unresolved_references)
    if not checks["no_unresolved_references"]:
        reasons.append(
            "target is referenced by unresolved state structure(s): "
            + ", ".join(str(item) for item in unresolved_references)
        )

    checks["timestamp_rule"] = isinstance(timestamp_rule, str) and bool(timestamp_rule.strip())
    if not checks["timestamp_rule"]:
        reasons.append("metadata +0x0c generation rule is unresolved")

    checks["fixed_state_derivation"] = (
        isinstance(fixed_state_derivation, str) and bool(fixed_state_derivation.strip())
    )
    if not checks["fixed_state_derivation"]:
        reasons.append("fresh fixed-state derivation is unresolved")

    checks["operation_phrase_bound"] = operation_phrase_bound
    if not checks["operation_phrase_bound"]:
        reasons.append("delete-specific confirmation phrase is not bound")

    for name, value, label in (
        ("exactly_one_removed", exactly_one_removed, "candidate removal is not exactly one path"),
        ("no_added_paths", no_added_paths, "candidate adds an unexpected path or is unverified"),
        (
            "unrelated_payloads_preserved",
            unrelated_payloads_preserved,
            "unrelated payload preservation is unverified",
        ),
        ("storage_sufficient", storage_sufficient, "preserved before/after evidence storage is unverified"),
    ):
        checks[name] = value is True
        if not checks[name]:
            reasons.append(label)

    checks["not_fixture_only"] = not captured_fixture_only
    if not checks["not_fixture_only"]:
        reasons.append("captured-fixture reproduction is not live-delete eligibility")

    return DeleteEligibility(
        eligible=not reasons,
        checks=checks,
        reasons=tuple(reasons),
    )


__all__ = [
    "DeleteEligibility",
    "DeleteReadinessError",
    "SUPPORTED_DEVICE",
    "assess_delete_eligibility",
]
