"""Offline connection between the flat ebook plan and ordered package candidates."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping, Optional

from .prepared_ebook_plan import PreparedEbookPlan, build_prepared_ebook_plan
from .prepared_package_multi_candidate import (
    PreparedMultiPackageCandidate,
    build_prepared_multi_package_candidate,
)
from .backup_format import ParsedBackupBlob
from .capacity_evidence import NativeCapacityResponse
from .write_gate import VerifiedBackup


@dataclass(frozen=True)
class PreparedEbookCandidate:
    """A flat manifest plan and its offline mixed-package candidate."""

    plan: PreparedEbookPlan
    candidate: PreparedMultiPackageCandidate
    report: Mapping[str, Any]

    @property
    def candidate_blob_sha256(self) -> str:
        return self.candidate.candidate_blob_sha256

    @property
    def transaction_sha256(self) -> str:
        return self.candidate.transaction_sha256

    def to_dict(self) -> dict[str, Any]:
        return dict(self.report)


def build_prepared_ebook_candidate(
    manifest: Mapping[str, Any],
    backup: VerifiedBackup,
    template: ParsedBackupBlob,
    *,
    new_record_timestamp_be32: int,
    native_capacity_response: NativeCapacityResponse,
    template_folder_path: tuple[str, ...] = ("root", "IC_I_FOLDER_20260823_01"),
    template_item_paths: Optional[Mapping[str, tuple[str, ...]]] = None,
) -> PreparedEbookCandidate:
    """Build a candidate for the existing deliberately flat ebook plan."""

    plan = build_prepared_ebook_plan(manifest)
    candidate = build_prepared_multi_package_candidate(
        plan.package,
        backup,
        template,
        new_record_timestamp_be32=new_record_timestamp_be32,
        native_capacity_response=native_capacity_response,
        template_folder_path=template_folder_path,
        template_item_paths=template_item_paths,
    )
    report = {
        "format": "infocarry-flat-ebook-candidate-v1",
        "state": "previewed_offline",
        "device_change": "none",
        "usb_accessed": False,
        "notice": "OFFLINE EBOOK CANDIDATE ONLY — no device change has occurred",
        "plan_sha256": plan.plan_sha256,
        "package_manifest_sha256": plan.package.prepared_manifest_sha256,
        "candidate_blob_sha256": candidate.candidate_blob_sha256,
        "transaction_sha256": candidate.transaction_sha256,
        "target_paths": list(candidate.audit["package"]["paths"]),
        "ordered_items": list(candidate.audit["package"]["ordered_items"]),
        "capacity": dict(candidate.audit["allocation"]),
        "candidate": dict(candidate.audit["candidate"]),
        "policy": {
            "shape": "one flat root folder with ordered TXT/BMP children",
            "nested_sections": "rejected",
            "timestamp": "one explicit frozen timestamp for new records",
            "fixed_state": "exact fresh capture-7-compatible bytes",
        },
        "safety": {
            "candidate_bytes_included": False,
            "sender_called": False,
            "automatic_retry": False,
        },
    }
    report["report_sha256"] = hashlib.sha256(
        json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return PreparedEbookCandidate(plan=plan, candidate=candidate, report=report)


__all__ = ["PreparedEbookCandidate", "build_prepared_ebook_candidate"]
