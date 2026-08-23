"""Fail-closed evidence assessment for timestamp and fixed-state rules.

Milestone I.7 characterizes the available evidence; it does not authorize a
device operation.  A rule is usable for a future candidate only when its
status is explicitly ``verified_independent``.  Plausible, observed, or
inferred rules remain ineligible so a caller cannot turn a golden fixture into
general live eligibility by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


VERIFIED_INDEPENDENT = "verified_independent"
KNOWN_EVIDENCE_STATUSES = frozenset(
    {
        VERIFIED_INDEPENDENT,
        "verified",
        "observed_multiple",
        "observed_single",
        "inferred",
        "unresolved",
    }
)


class I7ReadinessError(RuntimeError):
    """Raised only when an ineligible I.7 result is explicitly required."""


@dataclass(frozen=True)
class TimestampFixedStateEvidence:
    """Portable statement of the evidence supporting two generation rules."""

    timestamp_rule_status: str
    fixed_state_rule_status: str
    timestamp_independent_cases: int = 0
    fixed_state_independent_cases: int = 0
    unresolved_references: tuple[str, ...] = ()
    fresh_backup_complete: bool = True
    exact_supported_scope: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("timestamp_rule_status", self.timestamp_rule_status),
            ("fixed_state_rule_status", self.fixed_state_rule_status),
        ):
            if value not in KNOWN_EVIDENCE_STATUSES:
                raise ValueError(f"{name} is not a recognized evidence status")
        for name, value in (
            ("timestamp_independent_cases", self.timestamp_independent_cases),
            ("fixed_state_independent_cases", self.fixed_state_independent_cases),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")


@dataclass(frozen=True)
class TimestampFixedStateEligibility:
    """Explainable, non-authorizing eligibility for a proven rule set."""

    eligible: bool
    checks: Mapping[str, bool]
    reasons: tuple[str, ...]
    evidence: TimestampFixedStateEvidence
    scope: str = "constrained_one_folder_one_txt"

    def require_supported(self) -> None:
        if not self.eligible:
            raise I7ReadinessError(
                "timestamp/fixed-state rules are not eligible for generalization: "
                + "; ".join(self.reasons)
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "scope": self.scope,
            "checks": dict(self.checks),
            "reasons": list(self.reasons),
            "evidence": {
                "timestamp_rule_status": self.evidence.timestamp_rule_status,
                "fixed_state_rule_status": self.evidence.fixed_state_rule_status,
                "timestamp_independent_cases": self.evidence.timestamp_independent_cases,
                "fixed_state_independent_cases": self.evidence.fixed_state_independent_cases,
                "unresolved_references": list(self.evidence.unresolved_references),
                "fresh_backup_complete": self.evidence.fresh_backup_complete,
                "exact_supported_scope": self.evidence.exact_supported_scope,
            },
        }


def assess_timestamp_fixed_state_eligibility(
    evidence: TimestampFixedStateEvidence,
) -> TimestampFixedStateEligibility:
    """Return I.7 eligibility without building or authorizing a transaction."""

    if not isinstance(evidence, TimestampFixedStateEvidence):
        raise TypeError("evidence must be TimestampFixedStateEvidence")

    checks: dict[str, bool] = {}
    reasons: list[str] = []

    checks["timestamp_rule_independently_verified"] = (
        evidence.timestamp_rule_status == VERIFIED_INDEPENDENT
        and evidence.timestamp_independent_cases >= 2
    )
    if not checks["timestamp_rule_independently_verified"]:
        reasons.append(
            "timestamp +0x0c generation is not independently verified across at least two cases"
        )

    checks["fixed_state_rule_independently_verified"] = (
        evidence.fixed_state_rule_status == VERIFIED_INDEPENDENT
        and evidence.fixed_state_independent_cases >= 2
    )
    if not checks["fixed_state_rule_independently_verified"]:
        reasons.append(
            "0x001b-0x001f derivation is not independently verified across at least two cases"
        )

    checks["no_unresolved_references"] = not evidence.unresolved_references
    if not checks["no_unresolved_references"]:
        reasons.append(
            "target has unresolved fixed-state references: "
            + ", ".join(evidence.unresolved_references)
        )

    checks["complete_fresh_backup"] = evidence.fresh_backup_complete
    if not checks["complete_fresh_backup"]:
        reasons.append("complete fresh backup is not verified")

    checks["exact_supported_scope"] = evidence.exact_supported_scope
    if not checks["exact_supported_scope"]:
        reasons.append("requested scope exceeds the characterized operation")

    return TimestampFixedStateEligibility(
        eligible=not reasons,
        checks=checks,
        reasons=tuple(reasons),
        evidence=evidence,
    )


__all__ = [
    "I7ReadinessError",
    "KNOWN_EVIDENCE_STATUSES",
    "TimestampFixedStateEvidence",
    "TimestampFixedStateEligibility",
    "VERIFIED_INDEPENDENT",
    "assess_timestamp_fixed_state_eligibility",
]
