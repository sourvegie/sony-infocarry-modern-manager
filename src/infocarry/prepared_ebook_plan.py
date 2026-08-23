"""Manifest-driven, offline-only plan for the smallest typed ebook shape.

The current plan accepts one root folder with a flat ordered TXT/BMP sequence.
Section folders and nested paths are rejected explicitly because I.7 and the
available package evidence do not prove their native construction.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .prepared_media_package import (
    PreparedMediaPackage,
    PreparedMediaPackageError,
    build_prepared_media_package,
)
from .prepared_package import _canonical_json, _validate_component


PREPARED_EBOOK_PLAN_FORMAT = "infocarry-prepared-ebook-plan-v1"
PREPARED_EBOOK_NOTICE = "OFFLINE EBOOK PLAN ONLY — no device change has occurred"


class PreparedEbookPlanError(ValueError):
    """Raised when a manifest exceeds the proven offline ebook scope."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalized_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(manifest)
    items = normalized.get("items")
    if isinstance(items, list):
        normalized["items"] = [
            {
                **dict(item),
                "source": str(item.get("source")) if isinstance(item, Mapping) else None,
            }
            if isinstance(item, Mapping)
            else item
            for item in items
        ]
    return normalized


@dataclass(frozen=True)
class PreparedEbookPlan:
    """Hash-bound plan and logical package for one flat typed ebook."""

    package: PreparedMediaPackage
    report: Mapping[str, Any]

    @property
    def eligible(self) -> bool:
        return bool(self.report["eligibility"]["device_candidate_eligible"])

    @property
    def plan_sha256(self) -> str:
        return str(self.report["plan_sha256"])

    def to_dict(self) -> dict[str, Any]:
        return dict(self.report)


def build_prepared_ebook_plan(manifest: Mapping[str, Any]) -> PreparedEbookPlan:
    """Build the smallest manifest-driven ebook plan without USB access."""

    if not isinstance(manifest, Mapping):
        raise PreparedEbookPlanError("ebook manifest must be a mapping")
    root_folder = manifest.get("root_folder")
    try:
        _validate_component(root_folder, label="root folder")
    except Exception as exc:
        raise PreparedEbookPlanError(f"root folder is invalid: {exc}") from exc

    sections = manifest.get("sections", ())
    if sections not in (None, (), []):
        raise PreparedEbookPlanError(
            "nested section folders remain unproven; this plan supports one flat root folder only"
        )
    items = manifest.get("items")
    if not isinstance(items, (list, tuple)) or len(items) < 2:
        raise PreparedEbookPlanError("ebook manifest must contain at least two ordered items")

    source_specs: list[tuple[Path, str]] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise PreparedEbookPlanError(f"ebook item {index} must be a mapping")
        source = item.get("source")
        name = item.get("name")
        if not isinstance(source, (str, Path)) or not isinstance(name, str):
            raise PreparedEbookPlanError(f"ebook item {index} requires source and name")
        if "section" in item and item.get("section") not in (None, ""):
            raise PreparedEbookPlanError(
                "nested section folders remain unproven; item sections are not accepted"
            )
        source_specs.append((Path(source), name))

    try:
        package = build_prepared_media_package(source_specs, root_folder)
    except PreparedMediaPackageError as exc:
        raise PreparedEbookPlanError(str(exc)) from exc

    package_manifest = package.manifest_dict()
    source_manifest = _normalized_manifest(manifest)
    report: dict[str, Any] = {
        "format": PREPARED_EBOOK_PLAN_FORMAT,
        "state": "previewed_offline",
        "notice": PREPARED_EBOOK_NOTICE,
        "usb_accessed": False,
        "device_change": "none",
        "source_manifest_sha256": _sha256(_canonical_json(source_manifest)),
        "package_manifest_sha256": package.prepared_manifest_sha256,
        "target": {
            "root_folder": package.target_folder_path,
            "paths": [package.target_folder_path, *package.target_item_paths],
            "nested_sections": False,
            "ordered_items": [
                {
                    "order": index,
                    "kind": item.kind,
                    "path": package.target_item_paths[index],
                    "source_sha256": item.source_sha256,
                    "payload_sha256": item.payload_sha256,
                }
                for index, item in enumerate(package.items)
            ],
        },
        "package": package_manifest,
        "capacity": {
            "status": "not_evaluated_without_verified_backup",
            "baseline_model_bytes": None,
            "candidate_model_bytes": None,
            "growth_bytes": package.estimated_growth_lower_bound,
            "capacity_limit_bytes": None,
            "native_0019_response_sha256": None,
        },
        "policy": {
            "timestamp_policy": "unresolved_for_generalized_package",
            "fixed_state_policy": "unresolved_for_generalized_package",
            "candidate_transaction_hash": None,
            "expected_readback": {
                "added_paths": [package.target_folder_path, *package.target_item_paths],
                "removed_paths": [],
                "shared_payloads_preserved": True,
                "exact_native_candidate": False,
            },
        },
        "eligibility": {
            "preparation_ready": True,
            "flat_root_shape_supported_offline": True,
            "nested_sections_supported": False,
            "device_candidate_eligible": False,
            "reasons": [
                "nested folder construction is unproven and fail-closed",
                "general timestamp and fixed-state rules are unresolved",
                "exact native multi-record growth and capacity are unresolved",
                "no device candidate or transaction is constructed",
            ],
        },
        "safety": {
            "source_mutated": False,
            "candidate_bytes_included": False,
            "authorization_created": False,
            "sender_called": False,
            "automatic_retry": False,
        },
    }
    report["plan_sha256"] = _sha256(_canonical_json(report))
    return PreparedEbookPlan(package=package, report=report)


__all__ = [
    "PREPARED_EBOOK_NOTICE",
    "PREPARED_EBOOK_PLAN_FORMAT",
    "PreparedEbookPlan",
    "PreparedEbookPlanError",
    "build_prepared_ebook_plan",
]
