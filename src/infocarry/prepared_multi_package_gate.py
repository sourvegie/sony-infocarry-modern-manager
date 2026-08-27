"""Exact authorization binding for the offline multi-child package path."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any, Optional

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
        items = tuple(package["ordered_items"])
        values = {
            "device_identity": (device["vendor_id"], device["product_id"]),
            "baseline_manifest_sha256": baseline["manifest_sha256"],
            "baseline_blob_sha256": baseline["blob_sha256"],
            "prepared_manifest_sha256": package["prepared_manifest_sha256"],
            "source_sha256": tuple(item["source_sha256"] for item in items),
            "target_paths": tuple(package["paths"]),
            "target_kinds": ("directory", *(item["kind"] for item in items)),
            "target_record_offsets": tuple(int(value, 16) for value in package["record_offsets"]),
            "new_record_timestamp_be32": int(candidate_data["new_record_timestamp_be32"], 16),
            "candidate_blob_sha256": candidate_data["blob_sha256"],
            "candidate_transaction_sha256": transaction["sha256"],
            "fixed_state_sha256": tuple(transaction["fixed_state_hashes"]),
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
    for key in ("baseline_manifest_sha256", "baseline_blob_sha256", "prepared_manifest_sha256", "candidate_blob_sha256", "candidate_transaction_sha256", "capacity_response_sha256"):
        values[key] = _digest(values[key], key)
    if len(values["source_sha256"]) < 2:
        raise PreparedMultiPackageGateError("candidate must bind at least two source hashes")
    values["source_sha256"] = tuple(_digest(value, "source hash") for value in values["source_sha256"])
    fixed = values["fixed_state_sha256"]
    if len(fixed) != 5:
        raise PreparedMultiPackageGateError("candidate must bind five fixed-state hashes")
    values["fixed_state_sha256"] = tuple(_digest(value, "fixed-state hash") for value in fixed)
    if len(values["target_paths"]) != len(values["source_sha256"]) + 1 or len(values["target_kinds"]) != len(values["source_sha256"]) + 1:
        raise PreparedMultiPackageGateError("candidate path and item bindings are inconsistent")
    if any(not isinstance(path, str) or not path for path in values["target_paths"]):
        raise PreparedMultiPackageGateError("candidate target paths are invalid")
    if values["target_kinds"][0] != "directory" or len(values["target_kinds"]) != len(values["target_paths"]):
        raise PreparedMultiPackageGateError("candidate target kinds are invalid")
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
    actual_sources = tuple(item.source_sha256 for item in candidate.package.items)
    if actual_sources != values["source_sha256"]:
        raise PreparedMultiPackageGateError("candidate source binding does not match package order")
    actual_fixed = tuple(_sha256(block) for block in candidate.fixed_state.raw_blocks)
    if actual_fixed != values["fixed_state_sha256"]:
        raise PreparedMultiPackageGateError("candidate fixed-state binding does not match preserved bytes")
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
    target_paths: tuple[str, ...]
    target_kinds: tuple[str, ...]
    target_record_offsets: tuple[int, ...]
    new_record_timestamp_be32: int
    candidate_blob_sha256: str
    candidate_transaction_sha256: str
    fixed_state_sha256: tuple[str, ...]
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
        for label, value in (("baseline manifest", self.baseline_manifest_sha256), ("baseline blob", self.baseline_blob_sha256), ("prepared manifest", self.prepared_manifest_sha256), ("candidate blob", self.candidate_blob_sha256), ("candidate transaction", self.candidate_transaction_sha256), ("capacity response", self.capacity_response_sha256)):
            _digest(value, label)
        if len(self.source_sha256) < 2 or len(self.target_kinds) != len(self.source_sha256) + 1 or len(self.target_record_offsets) != len(self.source_sha256) + 1 or len(self.target_paths) != len(self.source_sha256) + 1:
            raise PreparedMultiPackageGateError("authorization item bindings are inconsistent")
        for index, value in enumerate(self.source_sha256):
            _digest(value, f"source hash {index}")
        if len(self.fixed_state_sha256) != 5:
            raise PreparedMultiPackageGateError("authorization must bind five fixed-state hashes")
        for index, value in enumerate(self.fixed_state_sha256):
            _digest(value, f"fixed-state hash {index}")
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
        return {key: getattr(self, key) for key in ("device_identity", "baseline_manifest_sha256", "baseline_blob_sha256", "prepared_manifest_sha256", "source_sha256", "target_paths", "target_kinds", "target_record_offsets", "new_record_timestamp_be32", "candidate_blob_sha256", "candidate_transaction_sha256", "fixed_state_sha256", "capacity_response_sha256", "capacity_response_command", "capacity_response_field_offset", "capacity_evidence_source", "capacity_evidence_version", "capacity_limit_bytes", "baseline_model_bytes", "candidate_model_bytes", "remaining_growth_bytes", "candidate_growth_bytes", "capacity_result")}

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
        assess_prepared_fixed_state(backup).require_supported()
        return backup

    def to_dict(self) -> dict[str, Any]:
        result = {"format": PREPARED_MULTI_PACKAGE_GATE_FORMAT, "state": "authorized_for_fake_transport_only", "usb_transmission_performed": False, "operation": "add_one_root_folder_ordered_package", "confirmation_phrase": self.confirmation_phrase}
        result.update(self._expected())
        result["source_sha256"] = list(self.source_sha256)
        result["target_paths"] = list(self.target_paths)
        result["target_kinds"] = list(self.target_kinds)
        result["target_record_offsets"] = [f"0x{value:08x}" for value in self.target_record_offsets]
        result["fixed_state_sha256"] = list(self.fixed_state_sha256)
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
