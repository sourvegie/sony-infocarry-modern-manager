"""Host-only assessment of prepared direct-leaf transfer shapes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .prepared_content import PreparedContentArtifact


TRANSFER_SHAPE_ASSESSMENT_FORMAT = "infocarry-transfer-shape-assessment-v1"
VNW_V15_MODEL_PROFILE_ID = "sony-vnw-v15-reviewed-v1"
EXACT_VERIFIED_LIVE_PROFILE = "exact_verified_vnw_v15_txt_bmp_txt"
PLAUSIBLE_FUTURE_DIRECT_LEAF_V15 = "plausible_future_vnw_v15_direct_leaf"
UNMAPPABLE_UNSUPPORTED_SHAPE = "unmappable_unsupported_shape"
CURRENT_VERIFIED_CHILD_KINDS = ("txt", "bmp", "txt")
MAX_FUTURE_DIRECT_LEAF_CHILDREN = 8


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class TransferShapeAssessment:
    artifact_identity: str
    model_profile_id: str
    classification: str
    root_name: str
    child_count: int
    ordered_kinds: tuple[str, ...]
    direct_leaf: bool
    requires_capability_validation: bool
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_identity, str) or len(self.artifact_identity) != 64 or self.artifact_identity != self.artifact_identity.lower():
            raise ValueError("transfer-shape artifact identity must be a SHA-256 string")
        try:
            int(self.artifact_identity, 16)
        except ValueError as exc:
            raise ValueError("transfer-shape artifact identity must be a SHA-256 string") from exc
        if self.model_profile_id != VNW_V15_MODEL_PROFILE_ID:
            raise ValueError("transfer-shape assessment is bound to the reviewed VNW-V15 profile")
        if self.classification not in {EXACT_VERIFIED_LIVE_PROFILE, PLAUSIBLE_FUTURE_DIRECT_LEAF_V15, UNMAPPABLE_UNSUPPORTED_SHAPE}:
            raise ValueError("unsupported transfer-shape classification")
        if self.child_count != len(self.ordered_kinds):
            raise ValueError("transfer-shape child count differs from ordered kinds")
        if any(kind not in {"folder", "txt", "bmp"} for kind in self.ordered_kinds):
            raise ValueError("transfer-shape ordered kinds are malformed")

    @property
    def exact_verified_live_profile(self) -> bool:
        return self.classification == EXACT_VERIFIED_LIVE_PROFILE

    @property
    def plausible_future_direct_leaf(self) -> bool:
        return self.classification == PLAUSIBLE_FUTURE_DIRECT_LEAF_V15

    @property
    def unmappable(self) -> bool:
        return self.classification == UNMAPPABLE_UNSUPPORTED_SHAPE

    def to_dict(self) -> dict[str, Any]:
        unsigned = {
            "format": TRANSFER_SHAPE_ASSESSMENT_FORMAT,
            "version": 1,
            "artifact_identity": self.artifact_identity,
            "model_profile_id": self.model_profile_id,
            "classification": self.classification,
            "root_name": self.root_name,
            "child_count": self.child_count,
            "ordered_kinds": list(self.ordered_kinds),
            "direct_leaf": self.direct_leaf,
            "requires_capability_validation": self.requires_capability_validation,
            "reasons": list(self.reasons),
            "host_only": True,
            "candidate_constructed": False,
            "authorization_created": False,
            "sender_called": False,
        }
        return {**unsigned, "assessment_sha256": hashlib.sha256(_canonical_json(unsigned)).hexdigest()}


def assess_transfer_shape(
    artifact: PreparedContentArtifact,
    *,
    model_profile_id: str = VNW_V15_MODEL_PROFILE_ID,
) -> TransferShapeAssessment:
    if not isinstance(artifact, PreparedContentArtifact):
        raise TypeError("transfer-shape assessment requires a PreparedContentArtifact")
    if model_profile_id != VNW_V15_MODEL_PROFILE_ID:
        raise ValueError("transfer-shape assessment is only defined for reviewed VNW-V15")
    kinds = tuple(child.kind for child in artifact.children)
    direct_leaf = all(
        child.kind in {"txt", "bmp"}
        and child.path.rsplit("\\", 1)[0] == artifact.root_path
        for child in artifact.children
    )
    exact = direct_leaf and kinds == CURRENT_VERIFIED_CHILD_KINDS
    plausible = direct_leaf and 1 <= len(kinds) <= MAX_FUTURE_DIRECT_LEAF_CHILDREN and all(kind in {"txt", "bmp"} for kind in kinds)
    reasons: list[str] = []
    if exact:
        classification = EXACT_VERIFIED_LIVE_PROFILE
        requires = False
        reasons.append("ordered direct children exactly match the reviewed VNW-V15 TXT → BMP → TXT shape")
    elif plausible:
        classification = PLAUSIBLE_FUTURE_DIRECT_LEAF_V15
        requires = True
        reasons.extend(
            (
                "direct TXT/BMP leaves are structurally plausible but this exact shape has no reusable live proof",
                "capability validation and separately scoped evidence are required before live readiness",
            )
        )
    else:
        classification = UNMAPPABLE_UNSUPPORTED_SHAPE
        requires = False
        if not direct_leaf:
            reasons.append("nested folders or non-leaf paths cannot be mapped to the reviewed direct-leaf profile")
        if len(kinds) > MAX_FUTURE_DIRECT_LEAF_CHILDREN:
            reasons.append("the prepared artifact contains more than eight direct leaves")
        if any(kind not in {"txt", "bmp", "folder"} for kind in kinds):
            reasons.append("the prepared artifact contains an unsupported record kind")
        if not reasons:
            reasons.append("the prepared artifact cannot be mapped safely to a reviewed host shape")
    return TransferShapeAssessment(
        artifact_identity=artifact.artifact_identity,
        model_profile_id=model_profile_id,
        classification=classification,
        root_name=artifact.root_name,
        child_count=len(kinds),
        ordered_kinds=kinds,
        direct_leaf=direct_leaf,
        requires_capability_validation=requires,
        reasons=tuple(dict.fromkeys(reasons)),
    )


__all__ = [
    "CURRENT_VERIFIED_CHILD_KINDS",
    "EXACT_VERIFIED_LIVE_PROFILE",
    "MAX_FUTURE_DIRECT_LEAF_CHILDREN",
    "PLAUSIBLE_FUTURE_DIRECT_LEAF_V15",
    "TRANSFER_SHAPE_ASSESSMENT_FORMAT",
    "TransferShapeAssessment",
    "UNMAPPABLE_UNSUPPORTED_SHAPE",
    "assess_transfer_shape",
]
