"""Exact authorization binding for the offline multi-child package path."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Mapping, Optional

from .capacity_evidence import NATIVE_CAPACITY_EVIDENCE_SOURCE, NATIVE_CAPACITY_EVIDENCE_VERSION, NATIVE_CAPACITY_FIELD_OFFSET
from .prepared_fixed_state import assess_prepared_fixed_state
from .prepared_package_multi_candidate import PreparedMultiPackageCandidate, PreparedMultiCandidateError, _display_path
from .write_gate import DEFAULT_MAX_AGE_SECONDS, VerifiedBackup, verify_fresh_backup


PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE = "ADD ONE INFOCARRY MULTI-CHILD PACKAGE"
PREPARED_MULTI_PACKAGE_GATE_FORMAT = "infocarry-modern-ordered-package-gate-v1"


class PreparedMultiPackageGateError(RuntimeError):
    """Raised when an ordered package authorization is invalid."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value.lower()):
        raise PreparedMultiPackageGateError(f"{label} must be a lowercase SHA-256 digest")
    return value.lower()


def _candidate_binding(candidate: PreparedMultiPackageCandidate) -> dict[str, Any]:
    if not isinstance(candidate, PreparedMultiPackageCandidate):
        raise PreparedMultiPackageGateError("candidate must be a PreparedMultiPackageCandidate")
    audit = candidate.audit
    try:
        device = audit["device_identity"]
        baseline = audit["baseline"]
        package = audit["package"]
        candidate_data = audit["candidate"]
        allocation = audit["allocation"]
        evidence = audit["capacity_evidence"]
        transaction = audit["transaction"]
        template = audit["template"]
        policy = audit["policy"]
        expected_post = audit["expected_post_operation"]
        fixed_state = audit["fixed_state"]
        fixed_snapshot = fixed_state["snapshot"]
        display_history = fixed_snapshot["display_history"]
        display_history_rebase = audit["display_history_validation"]
        items = tuple(package["ordered_items"])
        values = {
            "device_identity": (device["vendor_id"], device["product_id"]),
            "baseline_manifest_sha256": baseline["manifest_sha256"],
            "baseline_blob_sha256": baseline["blob_sha256"],
            "prepared_manifest_sha256": package["prepared_manifest_sha256"],
            "source_sha256": tuple(item["source_sha256"] for item in items),
            "source_paths": tuple(item["source_path"] for item in items),
            "target_paths": tuple(package["paths"]),
            "target_kinds": ("directory", *(item["kind"] for item in items)),
            "target_record_offsets": tuple(int(value, 16) for value in package["record_offsets"]),
            "new_record_timestamp_be32": int(candidate_data["new_record_timestamp_be32"], 16),
            "candidate_blob_sha256": candidate_data["blob_sha256"],
            "candidate_transaction_sha256": transaction["sha256"],
            "template_blob_sha256": template["blob_sha256"],
            "template_folder_path": template["folder_path"],
            "template_item_paths": tuple(sorted(template["item_paths"].items())),
            "template_item_record_offsets": tuple(sorted(template["item_record_offsets"].items())),
            "template_prefix_sha256": tuple(sorted(template["prefix_sha256"].items())),
            "timestamp_policy": policy["timestamp"],
            "fixed_state_policy": policy["fixed_state"],
            "display_history_record_offsets": tuple(
                display_history["relative_record_offsets"]
            ),
            "display_history_paths": tuple(
                entry["path"] for entry in display_history["paths"]
            ),
            "display_history_candidate_record_offsets": tuple(
                display_history["candidate_relative_record_offsets"]
            ),
            "display_history_metadata_start": int(
                display_history["metadata_start"], 16
            ),
            "display_history_rebase_policy": display_history_rebase[
                "preservation_policy"
            ],
            "display_history_reference_pairs": tuple(
                (
                    entry["before_relative_record_offset"],
                    entry["candidate_relative_record_offset"],
                    entry["path"],
                    entry["rebased"],
                )
                for entry in display_history_rebase.get("references", [])
            ),
            "display_history_insertion_offset": (
                None
                if display_history_rebase.get("insertion_offset") is None
                else int(display_history_rebase["insertion_offset"], 16)
            ),
            "display_history_insertion_offset_absolute": (
                None
                if display_history_rebase.get("insertion_offset_absolute") is None
                else int(display_history_rebase["insertion_offset_absolute"], 16)
            ),
            "display_history_metadata_delta": int(
                display_history_rebase.get("metadata_delta", "0x00000000"), 16
            ),
            "display_history_references_rebased": int(
                display_history_rebase["references_rebased"]
            ),
            "display_history_semantic_preserved": bool(
                display_history_rebase["semantic_preserved"]
            ),
            "display_history_raw_preserved_exactly": bool(
                display_history_rebase["raw_preserved_exactly"]
            ),
            "expected_added_paths": tuple(expected_post["added_paths"]),
            "expected_removed_paths": tuple(expected_post["removed_paths"]),
            "expected_ordered_kinds": tuple(expected_post["ordered_kinds"]),
            "expected_new_payload_sha256": tuple(expected_post["new_payload_sha256"]),
            "fixed_state_sha256": tuple(transaction["fixed_state_hashes"]),
            "fixed_state_before_sha256": tuple(
                entry["sha256"] for entry in fixed_snapshot["before_sha256_by_command"]
            ),
            "fixed_state_candidate_sha256": tuple(
                entry["sha256"] for entry in fixed_snapshot["candidate_sha256_by_command"]
            ),
            "capacity_response_sha256": evidence["raw_response_sha256"],
            "capacity_response_command": int(evidence["response_command"], 16),
            "capacity_response_field_offset": int(evidence["field_offset"], 16),
            "capacity_evidence_source": evidence["evidence_source"],
            "capacity_evidence_version": evidence["evidence_version"],
            "capacity_limit_bytes": allocation["capacity_limit_bytes"],
            "baseline_model_bytes": allocation["baseline_model_bytes"],
            "candidate_model_bytes": allocation["candidate_model_bytes"],
            "remaining_growth_bytes": allocation["remaining_growth_bytes"],
            "candidate_growth_bytes": allocation["candidate_growth_bytes"],
            "capacity_result": allocation["capacity_result"],
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise PreparedMultiPackageGateError("candidate audit is missing multi-package binding fields") from exc
    if len(values["device_identity"]) != 2 or any(not isinstance(value, str) or not value for value in values["device_identity"]):
        raise PreparedMultiPackageGateError("candidate device identity is invalid")
    for key in ("baseline_manifest_sha256", "baseline_blob_sha256", "prepared_manifest_sha256", "candidate_blob_sha256", "candidate_transaction_sha256", "capacity_response_sha256", "template_blob_sha256"):
        values[key] = _digest(values[key], key)
    if len(values["source_sha256"]) < 2:
        raise PreparedMultiPackageGateError("candidate must bind at least two source hashes")
    values["source_sha256"] = tuple(_digest(value, "source hash") for value in values["source_sha256"])
    if any(not isinstance(path, str) or not path for path in (values["template_folder_path"], *[path for _kind, path in values["template_item_paths"]])):
        raise PreparedMultiPackageGateError("candidate template path binding is invalid")
    if any(kind not in {"txt", "bmp"} or not isinstance(path, str) or not path for kind, path in values["template_item_paths"]):
        raise PreparedMultiPackageGateError("candidate template item binding is invalid")
    for _kind, digest in values["template_prefix_sha256"]:
        _digest(digest, "template prefix hash")
    for digest in values["expected_new_payload_sha256"]:
        _digest(digest, "expected payload hash")
    if values["timestamp_policy"] != "one_explicit_frozen_value_for_new_records_only":
        raise PreparedMultiPackageGateError("candidate timestamp policy is not the reviewed modern policy")
    if values["fixed_state_policy"] not in {
        "capture7_exact_all_zero_fixed_state",
        "verified_display_history_0x001b_semantic_rebase_plus_zero_0x001c_to_0x001f",
    }:
        raise PreparedMultiPackageGateError("candidate fixed-state policy is not supported")
    if len(values["display_history_record_offsets"]) != len(values["display_history_paths"]):
        raise PreparedMultiPackageGateError("candidate display-history binding is inconsistent")
    if len(values["display_history_record_offsets"]) != len(
        values["display_history_candidate_record_offsets"]
    ):
        raise PreparedMultiPackageGateError("candidate display-history candidate binding is inconsistent")
    if (
        isinstance(values["display_history_metadata_start"], bool)
        or not isinstance(values["display_history_metadata_start"], int)
        or values["display_history_metadata_start"] < 0
        or values["display_history_metadata_start"] % 0x40
    ):
        raise PreparedMultiPackageGateError("candidate display-history metadata base is invalid")
    if any(
        not isinstance(offset, str) or not offset.startswith("0x")
        for offset in values["display_history_record_offsets"]
    ) or any(
        not isinstance(path, str) or not path
        for path in values["display_history_paths"]
    ):
        raise PreparedMultiPackageGateError("candidate display-history binding is invalid")
    if values["fixed_state_policy"] == "capture7_exact_all_zero_fixed_state" and values["display_history_record_offsets"]:
        raise PreparedMultiPackageGateError("zero fixed-state policy cannot contain display history")
    if values["fixed_state_policy"] == "verified_display_history_0x001b_semantic_rebase_plus_zero_0x001c_to_0x001f" and not values["display_history_record_offsets"]:
        raise PreparedMultiPackageGateError("display-history policy has no active references")
    if values["fixed_state_policy"] == "capture7_exact_all_zero_fixed_state":
        if (
            values["display_history_rebase_policy"] != "raw_exact"
            or values["display_history_reference_pairs"]
            or values["display_history_insertion_offset"] is not None
                or values["display_history_metadata_delta"] != 0
                or values["display_history_semantic_preserved"]
                or values["display_history_raw_preserved_exactly"] is not True
        ):
            raise PreparedMultiPackageGateError("zero fixed-state display-history binding is inconsistent")
    else:
        if (
            values["display_history_rebase_policy"]
            != "semantic_rebase_by_exact_metadata_delta"
            or not values["display_history_semantic_preserved"]
            or len(values["display_history_reference_pairs"])
            != len(values["display_history_record_offsets"])
            or values["display_history_insertion_offset"] is None
            or values["display_history_insertion_offset_absolute"] is None
            or values["display_history_metadata_delta"] <= 0
        ):
            raise PreparedMultiPackageGateError("semantic display-history binding is incomplete")
        if values["display_history_references_rebased"] != sum(
            pair[0] != pair[1] for pair in values["display_history_reference_pairs"]
        ):
            raise PreparedMultiPackageGateError("semantic display-history rebase count is inconsistent")
        for before, after, path, rebased in values["display_history_reference_pairs"]:
            if (
                not isinstance(before, str)
                or not isinstance(after, str)
                or not isinstance(path, str)
                or not path
                or not isinstance(rebased, bool)
            ):
                raise PreparedMultiPackageGateError("semantic display-history reference binding is invalid")
        if values["display_history_raw_preserved_exactly"] != (
            values["display_history_references_rebased"] == 0
        ):
            raise PreparedMultiPackageGateError("semantic display-history raw-preservation binding is inconsistent")
    if len(values["source_paths"]) != len(values["source_sha256"]) or any(
        not isinstance(value, str) or not value for value in values["source_paths"]
    ):
        raise PreparedMultiPackageGateError("candidate source path binding is invalid")
    fixed = values["fixed_state_sha256"]
    if len(fixed) != 5:
        raise PreparedMultiPackageGateError("candidate must bind five fixed-state hashes")
    values["fixed_state_sha256"] = tuple(_digest(value, "fixed-state hash") for value in fixed)
    for label in ("fixed_state_before_sha256", "fixed_state_candidate_sha256"):
        if len(values[label]) != 5:
            raise PreparedMultiPackageGateError(f"candidate must bind five {label} hashes")
        values[label] = tuple(_digest(value, f"{label} hash") for value in values[label])
    if values["fixed_state_candidate_sha256"] != values["fixed_state_sha256"]:
        raise PreparedMultiPackageGateError("candidate fixed-state hash bindings are inconsistent")
    if len(values["target_paths"]) != len(values["source_sha256"]) + 1 or len(values["target_kinds"]) != len(values["source_sha256"]) + 1:
        raise PreparedMultiPackageGateError("candidate path and item bindings are inconsistent")
    if any(not isinstance(path, str) or not path for path in values["target_paths"]):
        raise PreparedMultiPackageGateError("candidate target paths are invalid")
    if values["target_kinds"][0] != "directory" or len(values["target_kinds"]) != len(values["target_paths"]):
        raise PreparedMultiPackageGateError("candidate target kinds are invalid")
    if values["expected_added_paths"] != values["target_paths"] or values["expected_removed_paths"]:
        raise PreparedMultiPackageGateError("candidate expected post-operation path delta is invalid")
    if (
        values["expected_ordered_kinds"] != values["target_kinds"]
        or len(values["expected_new_payload_sha256"]) != len(values["source_sha256"])
    ):
        raise PreparedMultiPackageGateError("candidate expected post-operation payload delta is invalid")
    numeric = ("new_record_timestamp_be32", "capacity_limit_bytes", "baseline_model_bytes", "candidate_model_bytes", "remaining_growth_bytes", "candidate_growth_bytes", "capacity_response_command", "capacity_response_field_offset")
    for key in numeric:
        value = values[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise PreparedMultiPackageGateError(f"candidate {key} is invalid")
    if values["new_record_timestamp_be32"] > 0xFFFFFFFF or values["capacity_response_command"] != 0x0019 or values["capacity_response_field_offset"] != NATIVE_CAPACITY_FIELD_OFFSET:
        raise PreparedMultiPackageGateError("candidate capacity or timestamp binding is invalid")
    if values["capacity_evidence_source"] != NATIVE_CAPACITY_EVIDENCE_SOURCE or values["capacity_evidence_version"] != NATIVE_CAPACITY_EVIDENCE_VERSION:
        raise PreparedMultiPackageGateError("candidate capacity evidence is not parsed native 0x0019")
    if values["capacity_result"] != "sufficient" or values["candidate_model_bytes"] > values["capacity_limit_bytes"] or values["candidate_model_bytes"] < values["baseline_model_bytes"] or values["candidate_growth_bytes"] != values["candidate_model_bytes"] - values["baseline_model_bytes"] or values["remaining_growth_bytes"] != values["capacity_limit_bytes"] - values["baseline_model_bytes"] or values["candidate_growth_bytes"] > values["remaining_growth_bytes"]:
        raise PreparedMultiPackageGateError("candidate capacity binding is not an exact sufficient result")
    if len(values["target_record_offsets"]) != len(values["target_paths"]):
        raise PreparedMultiPackageGateError("candidate record-offset bindings are inconsistent")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 or value % 0x40 for value in values["target_record_offsets"]):
        raise PreparedMultiPackageGateError("candidate record-offset binding is invalid")
    if _sha256(candidate.candidate_blob) != values["candidate_blob_sha256"] or candidate.transaction_sha256 != values["candidate_transaction_sha256"]:
        raise PreparedMultiPackageGateError("candidate or transaction hash does not match its audit")
    if values["baseline_manifest_sha256"] != candidate.backup.manifest_sha256 or values["baseline_blob_sha256"] != candidate.backup.blob_sha256:
        raise PreparedMultiPackageGateError("candidate backup binding does not match the verified backup")
    if values["prepared_manifest_sha256"] != candidate.package.prepared_manifest_sha256:
        raise PreparedMultiPackageGateError("candidate package manifest binding does not match the package")
    candidate_template = candidate.audit.get("template")
    if not isinstance(candidate_template, Mapping) or candidate_template.get("blob_sha256") != values["template_blob_sha256"]:
        raise PreparedMultiPackageGateError("candidate template blob binding does not match")
    if candidate.audit.get("policy", {}).get("timestamp") != values["timestamp_policy"]:
        raise PreparedMultiPackageGateError("candidate timestamp policy binding does not match")
    actual_sources = tuple(item.source_sha256 for item in candidate.package.items)
    if actual_sources != values["source_sha256"]:
        raise PreparedMultiPackageGateError("candidate source binding does not match package order")
    actual_source_paths = tuple(str(item.source_path) for item in candidate.package.items)
    if actual_source_paths != values["source_paths"]:
        raise PreparedMultiPackageGateError("candidate source path binding does not match package order")
    actual_fixed = tuple(_sha256(block) for block in candidate.fixed_state.raw_blocks)
    actual_candidate_fixed = tuple(
        _sha256(block) for block in candidate.fixed_state.candidate_raw_blocks
    )
    if actual_fixed != values["fixed_state_before_sha256"]:
        raise PreparedMultiPackageGateError("candidate before fixed-state binding does not match preserved bytes")
    if actual_candidate_fixed != values["fixed_state_candidate_sha256"]:
        raise PreparedMultiPackageGateError("candidate fixed-state binding does not match prospective bytes")
    actual_fixed_snapshot = candidate.fixed_state.to_dict()
    actual_display_history = actual_fixed_snapshot["display_history"]
    actual_rebase = candidate.audit.get("display_history_validation")
    if (
        actual_fixed_snapshot["policy"] != values["fixed_state_policy"]
        or tuple(actual_display_history["relative_record_offsets"])
        != values["display_history_record_offsets"]
        or tuple(actual_display_history["candidate_relative_record_offsets"])
        != values["display_history_candidate_record_offsets"]
        or tuple(entry["path"] for entry in actual_display_history["paths"])
        != values["display_history_paths"]
        or bool(actual_display_history["raw_preserved_exactly"])
        != values["display_history_raw_preserved_exactly"]
        or bool(actual_display_history["semantic_preserved"])
        != values["display_history_semantic_preserved"]
        or int(actual_display_history["metadata_start"], 16)
        != values["display_history_metadata_start"]
        or actual_display_history["preservation_policy"]
        != values["display_history_rebase_policy"]
        or not isinstance(actual_rebase, Mapping)
        or actual_rebase.get("preservation_policy")
        != values["display_history_rebase_policy"]
        or bool(actual_rebase.get("semantic_preserved"))
        != values["display_history_semantic_preserved"]
        or int(actual_rebase.get("references_rebased", -1))
        != values["display_history_references_rebased"]
        or tuple(
            (
                entry["before_relative_record_offset"],
                entry["candidate_relative_record_offset"],
                entry["path"],
                entry["rebased"],
            )
            for entry in actual_rebase.get("references", [])
        )
        != values["display_history_reference_pairs"]
        or bool(actual_rebase.get("raw_preserved_exactly"))
        != values["display_history_raw_preserved_exactly"]
        or int(actual_rebase.get("metadata_delta", "0x00000000"), 16)
        != values["display_history_metadata_delta"]
        or (
            None
            if actual_rebase.get("insertion_offset") is None
            else int(actual_rebase["insertion_offset"], 16)
        )
        != values["display_history_insertion_offset"]
        or (
            None
            if actual_rebase.get("insertion_offset_absolute") is None
            else int(actual_rebase["insertion_offset_absolute"], 16)
        )
        != values["display_history_insertion_offset_absolute"]
    ):
        raise PreparedMultiPackageGateError("candidate display-history preservation binding does not match")
    evidence_object = candidate.native_capacity_evidence
    if (
        evidence_object.device_identity != tuple(int(value, 16) for value in candidate.backup.device_identity)
        or evidence_object.raw_response_sha256 != values["capacity_response_sha256"]
        or evidence_object.response_command != values["capacity_response_command"]
        or evidence_object.field_offset != values["capacity_response_field_offset"]
        or evidence_object.evidence_source != values["capacity_evidence_source"]
        or evidence_object.evidence_version != values["capacity_evidence_version"]
        or evidence_object.capacity_limit_bytes != values["capacity_limit_bytes"]
        or evidence_object.baseline_model_bytes != values["baseline_model_bytes"]
        or evidence_object.candidate_model_bytes != values["candidate_model_bytes"]
        or evidence_object.remaining_growth_bytes != values["remaining_growth_bytes"]
    ):
        raise PreparedMultiPackageGateError("candidate native capacity evidence binding does not match parsed evidence")
    folder_path = ("root", candidate.package.folder_name)
    child_paths = tuple(folder_path + (item.name.rsplit(".", 1)[0],) for item in candidate.package.items)
    actual_paths = (_display_path(folder_path), *(_display_path(path, item.kind) for path, item in zip(child_paths, candidate.package.items)))
    actual_kinds = ("directory", *(item.kind for item in candidate.package.items))
    actual_offsets = tuple(
        candidate.candidate.record_at(offset).offset
        for offset, path in candidate.candidate.paths.items()
        if path in (folder_path, *child_paths)
    )
    if values["target_paths"] != actual_paths or values["target_kinds"] != actual_kinds or set(values["target_record_offsets"]) != set(actual_offsets):
        raise PreparedMultiPackageGateError("candidate target identity or record-offset binding does not match candidate")
    return values


@dataclass(frozen=True)
class PreparedMultiPackageAuthorization:
    device_identity: tuple[str, str]
    baseline_manifest_sha256: str
    baseline_blob_sha256: str
    prepared_manifest_sha256: str
    source_sha256: tuple[str, ...]
    source_paths: tuple[str, ...]
    template_blob_sha256: str
    template_folder_path: str
    template_item_paths: tuple[tuple[str, str], ...]
    template_item_record_offsets: tuple[tuple[str, str], ...]
    template_prefix_sha256: tuple[tuple[str, str], ...]
    timestamp_policy: str
    expected_added_paths: tuple[str, ...]
    expected_removed_paths: tuple[str, ...]
    expected_ordered_kinds: tuple[str, ...]
    expected_new_payload_sha256: tuple[str, ...]
    target_paths: tuple[str, ...]
    target_kinds: tuple[str, ...]
    target_record_offsets: tuple[int, ...]
    new_record_timestamp_be32: int
    candidate_blob_sha256: str
    candidate_transaction_sha256: str
    fixed_state_sha256: tuple[str, ...]
    fixed_state_before_sha256: tuple[str, ...]
    fixed_state_candidate_sha256: tuple[str, ...]
    fixed_state_policy: str
    display_history_record_offsets: tuple[str, ...]
    display_history_candidate_record_offsets: tuple[str, ...]
    display_history_paths: tuple[str, ...]
    display_history_metadata_start: int
    display_history_rebase_policy: str
    display_history_reference_pairs: tuple[tuple[str, str, str, bool], ...]
    display_history_insertion_offset: int | None
    display_history_insertion_offset_absolute: int | None
    display_history_metadata_delta: int
    display_history_references_rebased: int
    display_history_semantic_preserved: bool
    display_history_raw_preserved_exactly: bool
    capacity_response_sha256: str
    capacity_response_command: int
    capacity_response_field_offset: int
    capacity_evidence_source: str
    capacity_evidence_version: str
    capacity_limit_bytes: int
    baseline_model_bytes: int
    candidate_model_bytes: int
    remaining_growth_bytes: int
    candidate_growth_bytes: int
    capacity_result: str
    confirmation_phrase: str

    def __post_init__(self) -> None:
        if self.confirmation_phrase != PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE:
            raise PreparedMultiPackageGateError("wrong multi-package confirmation phrase")
        if len(self.device_identity) != 2 or any(not isinstance(value, str) or not value for value in self.device_identity):
            raise PreparedMultiPackageGateError("authorization device identity is invalid")
        for label, value in (("baseline manifest", self.baseline_manifest_sha256), ("baseline blob", self.baseline_blob_sha256), ("prepared manifest", self.prepared_manifest_sha256), ("candidate blob", self.candidate_blob_sha256), ("candidate transaction", self.candidate_transaction_sha256), ("capacity response", self.capacity_response_sha256), ("template blob", self.template_blob_sha256)):
            _digest(value, label)
        if len(self.source_sha256) < 2 or len(self.source_paths) != len(self.source_sha256) or len(self.target_kinds) != len(self.source_sha256) + 1 or len(self.target_record_offsets) != len(self.source_sha256) + 1 or len(self.target_paths) != len(self.source_sha256) + 1:
            raise PreparedMultiPackageGateError("authorization item bindings are inconsistent")
        for index, value in enumerate(self.source_sha256):
            _digest(value, f"source hash {index}")
        if any(not isinstance(value, str) or not value for value in self.source_paths):
            raise PreparedMultiPackageGateError("authorization source path binding is invalid")
        if not self.template_folder_path or not self.template_item_paths or not self.template_item_record_offsets:
            raise PreparedMultiPackageGateError("authorization template binding is incomplete")
        if any(kind not in {"txt", "bmp"} or not path for kind, path in self.template_item_paths):
            raise PreparedMultiPackageGateError("authorization template item path binding is invalid")
        for _kind, digest in self.template_prefix_sha256:
            _digest(digest, "template prefix hash")
        for digest in self.expected_new_payload_sha256:
            _digest(digest, "expected payload hash")
        if self.timestamp_policy != "one_explicit_frozen_value_for_new_records_only":
            raise PreparedMultiPackageGateError("authorization timestamp policy is invalid")
        if self.expected_added_paths != self.target_paths or self.expected_removed_paths or self.expected_ordered_kinds != self.target_kinds:
            raise PreparedMultiPackageGateError("authorization expected post-operation path binding is invalid")
        if len(self.expected_new_payload_sha256) != len(self.source_sha256):
            raise PreparedMultiPackageGateError("authorization expected payload binding is invalid")
        if len(self.fixed_state_sha256) != 5:
            raise PreparedMultiPackageGateError("authorization must bind five fixed-state hashes")
        for index, value in enumerate(self.fixed_state_sha256):
            _digest(value, f"fixed-state hash {index}")
        if len(self.fixed_state_before_sha256) != 5 or len(self.fixed_state_candidate_sha256) != 5:
            raise PreparedMultiPackageGateError("authorization must bind before and candidate fixed-state hashes")
        for index, value in enumerate(self.fixed_state_before_sha256):
            _digest(value, f"fixed-state before hash {index}")
        for index, value in enumerate(self.fixed_state_candidate_sha256):
            _digest(value, f"fixed-state candidate hash {index}")
        if self.fixed_state_candidate_sha256 != self.fixed_state_sha256:
            raise PreparedMultiPackageGateError("authorization candidate fixed-state hashes are inconsistent")
        if self.fixed_state_policy not in {
            "capture7_exact_all_zero_fixed_state",
            "verified_display_history_0x001b_semantic_rebase_plus_zero_0x001c_to_0x001f",
        }:
            raise PreparedMultiPackageGateError("authorization fixed-state policy is not supported")
        if len(self.display_history_record_offsets) != len(self.display_history_paths):
            raise PreparedMultiPackageGateError("authorization display-history binding is inconsistent")
        if len(self.display_history_record_offsets) != len(self.display_history_candidate_record_offsets):
            raise PreparedMultiPackageGateError("authorization display-history candidate binding is inconsistent")
        if (
            isinstance(self.display_history_metadata_start, bool)
            or not isinstance(self.display_history_metadata_start, int)
            or self.display_history_metadata_start < 0
            or self.display_history_metadata_start % 0x40
        ):
            raise PreparedMultiPackageGateError("authorization display-history metadata base is invalid")
        if any(
            not isinstance(offset, str) or not offset.startswith("0x")
            for offset in self.display_history_record_offsets
        ) or any(
            not isinstance(path, str) or not path for path in self.display_history_paths
        ):
            raise PreparedMultiPackageGateError("authorization display-history binding is invalid")
        if any(
            not isinstance(offset, str) or not offset.startswith("0x")
            for offset in self.display_history_candidate_record_offsets
        ):
            raise PreparedMultiPackageGateError("authorization display-history candidate offsets are invalid")
        if self.fixed_state_policy == "capture7_exact_all_zero_fixed_state" and self.display_history_record_offsets:
            raise PreparedMultiPackageGateError("zero fixed-state authorization cannot contain display history")
        if self.fixed_state_policy == "verified_display_history_0x001b_semantic_rebase_plus_zero_0x001c_to_0x001f" and not self.display_history_record_offsets:
            raise PreparedMultiPackageGateError("display-history authorization has no active references")
        if self.display_history_rebase_policy not in {"raw_exact", "semantic_rebase_by_exact_metadata_delta"}:
            raise PreparedMultiPackageGateError("authorization display-history preservation policy is invalid")
        if isinstance(self.display_history_references_rebased, bool) or not isinstance(self.display_history_references_rebased, int) or self.display_history_references_rebased < 0:
            raise PreparedMultiPackageGateError("authorization display-history rebase count is invalid")
        if self.fixed_state_policy == "capture7_exact_all_zero_fixed_state":
            if (
                self.display_history_rebase_policy != "raw_exact"
                or self.display_history_reference_pairs
                or self.display_history_insertion_offset is not None
                or self.display_history_insertion_offset_absolute is not None
                or self.display_history_metadata_delta != 0
                or self.display_history_references_rebased != 0
                or self.display_history_semantic_preserved
                or not self.display_history_raw_preserved_exactly
            ):
                raise PreparedMultiPackageGateError("zero fixed-state display-history authorization is inconsistent")
        else:
            if (
                self.display_history_rebase_policy != "semantic_rebase_by_exact_metadata_delta"
                or not self.display_history_reference_pairs
                or self.display_history_insertion_offset is None
                or self.display_history_insertion_offset_absolute is None
                or self.display_history_metadata_delta <= 0
                or not self.display_history_semantic_preserved
            ):
                raise PreparedMultiPackageGateError("semantic display-history authorization is incomplete")
            if self.display_history_references_rebased != sum(
                before != after
                for before, after, _path, _rebased in self.display_history_reference_pairs
            ):
                raise PreparedMultiPackageGateError("semantic display-history authorization rebase count is inconsistent")
            if self.display_history_raw_preserved_exactly != (self.display_history_references_rebased == 0):
                raise PreparedMultiPackageGateError("semantic display-history raw-preservation authorization is inconsistent")
            if len(self.display_history_reference_pairs) != len(self.display_history_record_offsets):
                raise PreparedMultiPackageGateError("semantic display-history reference pairs are incomplete")
            for before, after, path, rebased in self.display_history_reference_pairs:
                if (
                    not isinstance(before, str)
                    or not isinstance(after, str)
                    or not isinstance(path, str)
                    or not path
                    or not isinstance(rebased, bool)
                ):
                    raise PreparedMultiPackageGateError("semantic display-history reference pair is invalid")
                try:
                    before_value = int(before, 16)
                    after_value = int(after, 16)
                except ValueError as exc:
                    raise PreparedMultiPackageGateError("semantic display-history reference pair is not hexadecimal") from exc
                if (before_value % 0x40) or (after_value % 0x40) or rebased != (before_value != after_value):
                    raise PreparedMultiPackageGateError("semantic display-history reference pair is inconsistent")
            if tuple(pair[0] for pair in self.display_history_reference_pairs) != self.display_history_record_offsets or tuple(pair[1] for pair in self.display_history_reference_pairs) != self.display_history_candidate_record_offsets or tuple(pair[2] for pair in self.display_history_reference_pairs) != self.display_history_paths:
                raise PreparedMultiPackageGateError("semantic display-history reference binding does not match offsets or paths")
            for label, value in (("display-history insertion offset", self.display_history_insertion_offset), ("display-history absolute insertion offset", self.display_history_insertion_offset_absolute)):
                if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value % 0x40:
                    raise PreparedMultiPackageGateError(f"{label} is invalid")
            if self.display_history_metadata_delta <= 0 or self.display_history_metadata_delta % 0x40:
                raise PreparedMultiPackageGateError("semantic display-history metadata delta is invalid")
        if self.target_kinds[0] != "directory" or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 or value % 0x40 for value in self.target_record_offsets):
            raise PreparedMultiPackageGateError("authorization target record binding is invalid")
        if isinstance(self.new_record_timestamp_be32, bool) or not 0 <= self.new_record_timestamp_be32 <= 0xFFFFFFFF:
            raise PreparedMultiPackageGateError("authorization timestamp is invalid")
        numeric = (self.capacity_response_command, self.capacity_response_field_offset, self.capacity_limit_bytes, self.baseline_model_bytes, self.candidate_model_bytes, self.remaining_growth_bytes, self.candidate_growth_bytes)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in numeric):
            raise PreparedMultiPackageGateError("authorization numeric binding is invalid")
        if self.capacity_response_command != 0x0019 or self.capacity_response_field_offset != NATIVE_CAPACITY_FIELD_OFFSET or self.capacity_evidence_source != NATIVE_CAPACITY_EVIDENCE_SOURCE or self.capacity_evidence_version != NATIVE_CAPACITY_EVIDENCE_VERSION:
            raise PreparedMultiPackageGateError("authorization capacity source is not native parsed 0x0019")
        if self.capacity_result != "sufficient" or self.candidate_model_bytes > self.capacity_limit_bytes or self.candidate_model_bytes < self.baseline_model_bytes or self.candidate_growth_bytes != self.candidate_model_bytes - self.baseline_model_bytes or self.remaining_growth_bytes != self.capacity_limit_bytes - self.baseline_model_bytes or self.candidate_growth_bytes > self.remaining_growth_bytes:
            raise PreparedMultiPackageGateError("authorization capacity binding is inconsistent")

    def _expected(self) -> dict[str, Any]:
        return {key: getattr(self, key) for key in ("device_identity", "baseline_manifest_sha256", "baseline_blob_sha256", "prepared_manifest_sha256", "source_sha256", "source_paths", "template_blob_sha256", "template_folder_path", "template_item_paths", "template_item_record_offsets", "template_prefix_sha256", "timestamp_policy", "fixed_state_policy", "display_history_record_offsets", "display_history_candidate_record_offsets", "display_history_paths", "display_history_metadata_start", "display_history_rebase_policy", "display_history_reference_pairs", "display_history_insertion_offset", "display_history_insertion_offset_absolute", "display_history_metadata_delta", "display_history_references_rebased", "display_history_semantic_preserved", "display_history_raw_preserved_exactly", "expected_added_paths", "expected_removed_paths", "expected_ordered_kinds", "expected_new_payload_sha256", "target_paths", "target_kinds", "target_record_offsets", "new_record_timestamp_be32", "candidate_blob_sha256", "candidate_transaction_sha256", "fixed_state_before_sha256", "fixed_state_candidate_sha256", "fixed_state_sha256", "capacity_response_sha256", "capacity_response_command", "capacity_response_field_offset", "capacity_evidence_source", "capacity_evidence_version", "capacity_limit_bytes", "baseline_model_bytes", "candidate_model_bytes", "remaining_growth_bytes", "candidate_growth_bytes", "capacity_result")}

    def require_same_candidate(self, candidate: PreparedMultiPackageCandidate) -> None:
        actual = _candidate_binding(candidate)
        for key, expected in self._expected().items():
            if actual[key] != expected:
                raise PreparedMultiPackageGateError(f"candidate {key} differs from authorization")

    def revalidate(self, candidate: PreparedMultiPackageCandidate, *, now: Optional[datetime] = None, max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS) -> VerifiedBackup:
        self.require_same_candidate(candidate)
        for item, expected in zip(candidate.package.items, self.source_sha256):
            try:
                data = item.source_path.read_bytes()
            except OSError as exc:
                raise PreparedMultiPackageGateError(f"bound package source could not be reread: {exc}") from exc
            if data != item.source_bytes or _sha256(data) != expected:
                raise PreparedMultiPackageGateError("bound package source bytes changed")
        try:
            backup = verify_fresh_backup(candidate.backup.directory, now=now, max_age_seconds=max_age_seconds)
        except Exception as exc:
            raise PreparedMultiPackageGateError(f"fresh backup revalidation failed: {exc}") from exc
        if backup.device_identity != self.device_identity:
            raise PreparedMultiPackageGateError("fresh backup device identity differs")
        fresh_fixed = assess_prepared_fixed_state(
            backup,
            allow_verified_display_history=True,
        ).require_supported()
        if tuple(_sha256(block) for block in fresh_fixed.raw_blocks) != self.fixed_state_before_sha256:
            raise PreparedMultiPackageGateError("fresh backup fixed-state before hashes differ")
        fresh_display = fresh_fixed.to_dict()["display_history"]
        if (
            tuple(fresh_display["relative_record_offsets"])
            != self.display_history_record_offsets
            or tuple(entry["path"] for entry in fresh_display["paths"])
            != self.display_history_paths
        ):
            raise PreparedMultiPackageGateError("fresh backup display-history references differ")
        if self.fixed_state_policy != "capture7_exact_all_zero_fixed_state":
            if fresh_fixed.display_history_record_offsets != tuple(
                int(offset, 16) for offset in self.display_history_record_offsets
            ):
                raise PreparedMultiPackageGateError("fresh backup display-history offsets differ")
        return backup

    def to_dict(self) -> dict[str, Any]:
        result = {"format": PREPARED_MULTI_PACKAGE_GATE_FORMAT, "state": "authorized_for_fake_transport_only", "usb_transmission_performed": False, "operation": "add_one_root_folder_ordered_package", "confirmation_phrase": self.confirmation_phrase}
        result.update(self._expected())
        result["source_sha256"] = list(self.source_sha256)
        result["source_paths"] = list(self.source_paths)
        result["template_item_paths"] = {key: value for key, value in self.template_item_paths}
        result["template_item_record_offsets"] = {key: value for key, value in self.template_item_record_offsets}
        result["template_prefix_sha256"] = {key: value for key, value in self.template_prefix_sha256}
        result["expected_added_paths"] = list(self.expected_added_paths)
        result["expected_removed_paths"] = list(self.expected_removed_paths)
        result["expected_ordered_kinds"] = list(self.expected_ordered_kinds)
        result["expected_new_payload_sha256"] = list(self.expected_new_payload_sha256)
        result["target_paths"] = list(self.target_paths)
        result["target_kinds"] = list(self.target_kinds)
        result["target_record_offsets"] = [f"0x{value:08x}" for value in self.target_record_offsets]
        result["fixed_state_sha256"] = list(self.fixed_state_sha256)
        result["fixed_state_before_sha256"] = list(self.fixed_state_before_sha256)
        result["fixed_state_candidate_sha256"] = list(self.fixed_state_candidate_sha256)
        result["display_history_record_offsets"] = list(self.display_history_record_offsets)
        result["display_history_candidate_record_offsets"] = list(self.display_history_candidate_record_offsets)
        result["display_history_paths"] = list(self.display_history_paths)
        result["display_history_metadata_start"] = f"0x{self.display_history_metadata_start:08x}"
        result["display_history_rebase_policy"] = self.display_history_rebase_policy
        result["display_history_insertion_offset"] = (
            None
            if self.display_history_insertion_offset is None
            else f"0x{self.display_history_insertion_offset:08x}"
        )
        result["display_history_insertion_offset_absolute"] = (
            None
            if self.display_history_insertion_offset_absolute is None
            else f"0x{self.display_history_insertion_offset_absolute:08x}"
        )
        result["display_history_metadata_delta"] = f"0x{self.display_history_metadata_delta:08x}"
        result["display_history_references_rebased"] = self.display_history_references_rebased
        result["display_history_semantic_preserved"] = self.display_history_semantic_preserved
        result["display_history_raw_preserved_exactly"] = self.display_history_raw_preserved_exactly
        result["display_history_reference_pairs"] = [
            {
                "before_relative_record_offset": before,
                "candidate_relative_record_offset": after,
                "path": path,
                "rebased": rebased,
            }
            for before, after, path, rebased in self.display_history_reference_pairs
        ]
        return result


def authorize_prepared_multi_package(candidate: PreparedMultiPackageCandidate, *, confirmation: str) -> PreparedMultiPackageAuthorization:
    if confirmation != PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE:
        raise PreparedMultiPackageGateError("wrong multi-package confirmation phrase")
    values = _candidate_binding(candidate)
    return PreparedMultiPackageAuthorization(**values, confirmation_phrase=confirmation)


__all__ = [
    "PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE",
    "PREPARED_MULTI_PACKAGE_GATE_FORMAT",
    "PreparedMultiPackageAuthorization",
    "PreparedMultiPackageGateError",
    "authorize_prepared_multi_package",
]
