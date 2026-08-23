"""Explicit offline capacity semantics for the ordinary write path.

The preserved legacy dispatcher compares the prospective model size ``N + M``
with a device limit.  This module keeps that total-limit calculation distinct
from a remaining-growth budget supplied by older offline callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class CapacitySemanticsError(ValueError):
    """Raised when capacity evidence is missing or internally inconsistent."""


@dataclass(frozen=True)
class CapacityAssessment:
    """One checked total-limit comparison in bytes."""

    capacity_limit_bytes: int
    baseline_model_bytes: int
    candidate_model_bytes: int
    candidate_growth_bytes: int
    remaining_growth_bytes: int
    source: str

    def __post_init__(self) -> None:
        values = (
            ("capacity_limit_bytes", self.capacity_limit_bytes),
            ("baseline_model_bytes", self.baseline_model_bytes),
            ("candidate_model_bytes", self.candidate_model_bytes),
            ("candidate_growth_bytes", self.candidate_growth_bytes),
            ("remaining_growth_bytes", self.remaining_growth_bytes),
        )
        for label, value in values:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise CapacitySemanticsError(f"{label} must be a non-negative integer")
        if not isinstance(self.source, str) or not self.source:
            raise CapacitySemanticsError("capacity source must be a non-empty string")
        if self.candidate_model_bytes < self.baseline_model_bytes:
            raise CapacitySemanticsError("candidate model is smaller than the baseline model")
        if self.candidate_model_bytes > self.capacity_limit_bytes:
            raise CapacitySemanticsError(
                "candidate model exceeds the total capacity limit"
            )
        if self.candidate_growth_bytes != (
            self.candidate_model_bytes - self.baseline_model_bytes
        ):
            raise CapacitySemanticsError(
                "candidate growth is inconsistent with baseline and candidate model lengths"
            )
        if self.remaining_growth_bytes != (
            self.capacity_limit_bytes - self.baseline_model_bytes
        ):
            raise CapacitySemanticsError(
                "remaining growth is inconsistent with the total capacity limit"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capacity_limit_bytes": self.capacity_limit_bytes,
            "baseline_model_bytes": self.baseline_model_bytes,
            "candidate_model_bytes": self.candidate_model_bytes,
            "candidate_growth_bytes": self.candidate_growth_bytes,
            "remaining_growth_bytes": self.remaining_growth_bytes,
            "source": self.source,
            "candidate_within_total_limit": True,
        }


def assess_total_capacity(
    capacity_limit_bytes: int,
    baseline_model_bytes: int,
    candidate_model_bytes: int,
    *,
    source: str,
) -> CapacityAssessment:
    """Check a total model limit without interpreting any UI or probe value."""

    for label, value in (
        ("capacity_limit_bytes", capacity_limit_bytes),
        ("baseline_model_bytes", baseline_model_bytes),
        ("candidate_model_bytes", candidate_model_bytes),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise CapacitySemanticsError(f"{label} must be a non-negative integer")
    if not isinstance(source, str) or not source:
        raise CapacitySemanticsError("capacity source must be a non-empty string")
    if candidate_model_bytes < baseline_model_bytes:
        raise CapacitySemanticsError("candidate model is smaller than the baseline model")
    if candidate_model_bytes > capacity_limit_bytes:
        raise CapacitySemanticsError("candidate model exceeds the total capacity limit")

    return CapacityAssessment(
        capacity_limit_bytes=capacity_limit_bytes,
        baseline_model_bytes=baseline_model_bytes,
        candidate_model_bytes=candidate_model_bytes,
        candidate_growth_bytes=candidate_model_bytes - baseline_model_bytes,
        remaining_growth_bytes=capacity_limit_bytes - baseline_model_bytes,
        source=source,
    )


def assess_legacy_remaining_budget(
    remaining_growth_budget_bytes: int,
    baseline_model_bytes: int,
    candidate_model_bytes: int,
) -> CapacityAssessment:
    """Preserve the old offline API as an explicitly derived compatibility path.

    The caller-supplied budget is not device evidence.  Deriving a synthetic
    total here keeps old tests and fake workflows working without allowing the
    names ``available`` and ``limit`` to become interchangeable in new audits.
    """

    if (
        isinstance(remaining_growth_budget_bytes, bool)
        or not isinstance(remaining_growth_budget_bytes, int)
        or remaining_growth_budget_bytes < 0
    ):
        raise CapacitySemanticsError(
            "remaining_growth_budget_bytes must be a non-negative integer"
        )
    if (
        isinstance(baseline_model_bytes, bool)
        or not isinstance(baseline_model_bytes, int)
        or baseline_model_bytes < 0
    ):
        raise CapacitySemanticsError("baseline_model_bytes must be a non-negative integer")
    return assess_total_capacity(
        baseline_model_bytes + remaining_growth_budget_bytes,
        baseline_model_bytes,
        candidate_model_bytes,
        source="legacy_remaining_growth_budget_compatibility",
    )


__all__ = [
    "CapacityAssessment",
    "CapacitySemanticsError",
    "assess_legacy_remaining_budget",
    "assess_total_capacity",
]
