"""Bounded profiles accepted by the guarded Library operation boundary.

The physically enabled descriptors remain narrow exact shapes.  The
generalized descriptor is host-admission-only and carries the ordered child
projection into preflight without widening physical proof.  Operation identity
and fresh safety evidence remain transaction-specific at the caller boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .capability_profile import (
    GENERALIZED_FLAT_PROFILE_ID,
    INITIAL_EXPERIMENTAL_PROFILE_ID,
    MAX_FLAT_LEAF_COUNT,
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
    generalized_flat: bool = False

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

    def accepts_children(
        self, child_kinds: tuple[str, ...], child_names: Optional[tuple[str, ...]] = None
    ) -> bool:
        """Check one ordered child projection against this descriptor."""

        kinds = tuple(child_kinds)
        names = None if child_names is None else tuple(child_names)
        if self.generalized_flat:
            if not 1 <= len(kinds) <= MAX_FLAT_LEAF_COUNT:
                return False
            if any(kind not in {"txt", "bmp"} for kind in kinds):
                return False
            return names is None or len(names) == len(kinds)
        return kinds == self.child_kinds and (
            names is None or names == self.child_names
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
    GENERALIZED_FLAT_PROFILE_ID: GuardedExecutionProfile(
        profile_id=GENERALIZED_FLAT_PROFILE_ID,
        child_kinds=(),
        child_names=(),
        generalized_flat=True,
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
