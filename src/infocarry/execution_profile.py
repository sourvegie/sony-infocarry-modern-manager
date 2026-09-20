"""Exact profiles accepted by the guarded live execution boundary.

The descriptors remain narrow exact shapes so the guarded runner cannot
inherit the broader host-side 1--8 child envelope.  Both descriptors are
normal reviewed VNW-V15 shapes; operation identity and fresh safety evidence
remain transaction-specific at the caller boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .capability_profile import (
    INITIAL_EXPERIMENTAL_PROFILE_ID,
    VNW_V15_FOUR_LEAF_PROFILE_ID,
    capability_profile_by_id,
)


FRESH_CHILD_KINDS = ("txt", "bmp", "txt")
FRESH_CHILD_NAMES = (
    "01-introduction.txt",
    "02-page-01.bmp",
    "03-ending.txt",
)
FOUR_LEAF_CHILD_KINDS = ("txt", "bmp", "txt", "txt")
FOUR_LEAF_CHILD_NAMES = (
    "01-introduction.txt",
    "02-page-01.bmp",
    "03-ending.txt",
    "04-extra.txt",
)


@dataclass(frozen=True)
class GuardedExecutionProfile:
    """One exact package shape admitted by the shared guarded runner."""

    profile_id: str
    child_kinds: tuple[str, ...]
    child_names: tuple[str, ...]
    exact_target: Optional[str] = None
    operation_specific: bool = False

    @property
    def profile_sha256(self) -> str:
        return capability_profile_by_id(self.profile_id).sha256

    @property
    def expected_post_kinds(self) -> tuple[str, ...]:
        return ("directory", *self.child_kinds)

    def require_target(self, target_folder_name: str) -> None:
        if self.exact_target is not None and target_folder_name != self.exact_target:
            raise ValueError(
                f"{self.profile_id} requires target {self.exact_target!r}"
            )


_PROFILES = {
    INITIAL_EXPERIMENTAL_PROFILE_ID: GuardedExecutionProfile(
        profile_id=INITIAL_EXPERIMENTAL_PROFILE_ID,
        child_kinds=FRESH_CHILD_KINDS,
        child_names=FRESH_CHILD_NAMES,
    ),
    VNW_V15_FOUR_LEAF_PROFILE_ID: GuardedExecutionProfile(
        profile_id=VNW_V15_FOUR_LEAF_PROFILE_ID,
        child_kinds=tuple(FOUR_LEAF_CHILD_KINDS),
        child_names=tuple(FOUR_LEAF_CHILD_NAMES),
        exact_target=None,
        operation_specific=False,
    ),
}


def guarded_execution_profile(profile_id: str) -> GuardedExecutionProfile:
    """Return the exact profile or fail closed for every other profile."""

    try:
        return _PROFILES[profile_id]
    except KeyError as exc:
        raise ValueError(f"profile {profile_id!r} is not live-execution enabled") from exc


def is_guarded_execution_profile(profile_id: str) -> bool:
    return profile_id in _PROFILES


__all__ = [
    "FRESH_CHILD_KINDS",
    "FRESH_CHILD_NAMES",
    "VNW_V15_FOUR_LEAF_PROFILE_ID",
    "GuardedExecutionProfile",
    "guarded_execution_profile",
    "is_guarded_execution_profile",
]
