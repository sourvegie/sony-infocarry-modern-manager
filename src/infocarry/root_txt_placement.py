"""Exact root-TXT fixture admission into the existing guarded write lifecycle.

No protocol, sender, persistent claim, marker, or lock is implemented here.
The owner approves one immutable operation bundle. Execution may reconnect;
the sender is armed only after a read-only state-equivalence check proves that
the current VNW-V15 state still matches the approved baseline. General TXT
addition is not exposed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

from .backup_format import parse_backup_blob
from .capacity_evidence import NativeCapacityResponse
from .library_transfer_execution import (
    LibraryTransferExecutionFacade, LibraryTransferExecutionError,
    OwnerAuthorizedOperationIdentity,
)
from .library_transfer_runtime_provider import PinnedRootTxtRuntime
from .new_txt import NewTxtAddResult, build_new_root_txt_add
from .new_txt_gate import authorize_new_txt_add, NEW_ROOT_TXT_CONFIRMATION_PHRASE
from .prepared_library_package_operation_bundle import OperationArtifact
from .write_artifact import ProspectiveWriteTransaction, load_preserved_artifact
from .write_gate import verify_fresh_backup, capture_and_verify_fresh_backup, DEFAULT_MAX_AGE_SECONDS
from .write_safety_boundary import PersistentWriteSafetyOwner
from .p18_041h_experiment import (
    FIXTURE_FILENAME, FIXTURE_PATH, FIXTURE_BYTES, FIXTURE_SHA256,
    fixture_identity, PRESTAGE_REPORT_FORMAT, _validate_fixture_prestage_report,
)

ROOT_TXT_PLACEMENT_PROFILE = "vnw-v15-exact-clock-root-txt-placement-v1"
CONFIRMATION = f"ADD {FIXTURE_FILENAME} ONCE"
DISPOSABLE_ROOT_TXT_PLACEMENT_PROFILE = "vnw-v15-disposable-root-txt-placement-validation-v1"


def _placement_fixture(target_path, validation_placement):
    if type(validation_placement) is not bool:
        raise ValueError("validation placement opt-in must be explicit boolean")
    if validation_placement:
        # Lazy: delete_workflow inherits the existing placement bundle.
        from .delete_workflow import ROOT_TXT_DELETE_VALIDATION_FILES
        payload = ROOT_TXT_DELETE_VALIDATION_FILES.get(target_path)
        if payload is None:
            raise ValueError("only exact disposable A/B placement targets are admitted")
        return target_path.split("\\")[-1], payload
    if target_path != FIXTURE_PATH:
        raise ValueError("only the exact VNW-V15 direct-root TXT fixture is admitted")
    return FIXTURE_FILENAME, FIXTURE_BYTES


def _fixture_dict(target_path, validation_placement):
    if not validation_placement:
        return fixture_identity()
    filename, payload = _placement_fixture(target_path, True)
    return {"path": target_path, "filename": filename, "length": len(payload),
            "sha256": _sha(payload), "disposable_validation_only": True}


def _absent_disposable_target(parsed, filename):
    stem = filename[:-4].casefold()
    if any(len(path) == 2 and path[0].casefold() == "root" and
           path[1].casefold() == stem for path in parsed.paths.values()):
        raise ValueError("disposable target must be absent without native-stem ambiguity")


def _disposable_delta(before, after, target_path):
    filename, payload = _placement_fixture(target_path, True)
    baseline, candidate = parse_backup_blob(before), parse_backup_blob(after)
    _absent_disposable_target(baseline, filename)
    target = ("root", filename[:-4])
    def records(parsed):
        values = {}
        for offset, path in parsed.paths.items():
            if path in values:
                raise ValueError("ambiguous native path")
            record = parsed.record_at(offset)
            values[path] = record
        return values
    old, new = records(baseline), records(candidate)
    if set(new) - set(old) != {target} or set(old) - set(new):
        raise ValueError("placement requires exactly one absent direct-root addition")
    added = new[target]
    if (added.kind != "file" or added.extension != "txt" or added.flag not in (0x20, 0xE0)
            or added.field_14_be32 != 0x200 or candidate.payload_parts(added)[1] != payload):
        raise ValueError("placement target payload differs from disposable identity")
    for path, record in old.items():
        survivor = new[path]
        if (record.kind, record.extension, record.timestamp_be32) != (survivor.kind, survivor.extension, survivor.timestamp_be32):
            raise ValueError("prior record type or timestamp changed")
        if record.kind == "file" and baseline.payload_parts(record) != candidate.payload_parts(survivor):
            raise ValueError("prior payload or native prefix changed")
    return {"fixture_count_at_root": 1, "payload_length": len(payload),
            "payload_sha256": _sha(payload), "only_path_delta": target_path,
            "unrelated_payloads_unchanged": True, "surviving_prefixes_unchanged": True,
            "surviving_timestamps_unchanged": True}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _write_json(path: Path, value: Any) -> None:
    with path.open("xb") as output:
        output.write(_json(value))
        output.flush()
        import os
        os.fsync(output.fileno())


def _blob(backup: Any) -> bytes:
    # VerifiedBackup has already checked all manifest/object hashes.
    manifest = json.loads((backup.directory / "manifest.json").read_bytes())
    entries = [entry for entry in manifest["objects"] if entry["kind"] == "backup-blob"]
    if len(entries) != 1:
        raise ValueError("complete backup has no unique dynamic blob")
    return (backup.directory / entries[0]["filename"]).read_bytes()


def _exact_delta(before: bytes, after: bytes) -> dict[str, Any]:
    baseline, candidate = parse_backup_blob(before), parse_backup_blob(after)
    def leaves(parsed):
        result = {}
        for offset, path in parsed.paths.items():
            record = parsed.record_at(offset)
            if record.kind == "file":
                if path in result:
                    raise ValueError("duplicate native path")
                result[path] = (record.extension.lower(), parsed.payload_parts(record)[1])
        return result
    old, new = leaves(baseline), leaves(candidate)
    target = ("root", Path(FIXTURE_FILENAME).stem)
    if target in old or set(new) - set(old) != {target} or set(old) - set(new):
        raise ValueError("fixture requires exactly one absent direct-root addition")
    if new[target] != ("txt", FIXTURE_BYTES):
        raise ValueError("fixture is not the exact ordinary 29-byte TXT")
    if any(new[path] != value for path, value in old.items()):
        raise ValueError("unrelated file payload changed")
    # Directories and structural paths must also be unchanged.
    old_paths = list(baseline.paths.values())
    new_paths = list(candidate.paths.values())
    if new_paths.count(target) != 1 or sorted(new_paths) != sorted(old_paths + [target]):
        raise ValueError("another native path changed")
    return {"fixture_count_at_root": 1, "payload_length": 29,
            "payload_sha256": FIXTURE_SHA256, "only_path_delta": FIXTURE_PATH,
            "unrelated_payloads_unchanged": True}


@dataclass(frozen=True)
class RootTxtPlacementCandidate:
    candidate_blob: bytes
    transaction: ProspectiveWriteTransaction
    audit_json: bytes

    @property
    def core(self) -> NewTxtAddResult:
        # Return a defensive copy for the legacy builder/gate API.
        return NewTxtAddResult(self.candidate_blob, self.transaction, json.loads(self.audit_json))

    @property
    def candidate_blob_sha256(self) -> str:
        return _sha(self.candidate_blob)

    @property
    def transaction_sha256(self) -> str:
        return self.transaction.concatenated_sha256

    def audit_dict(self) -> dict[str, Any]:
        return json.loads(self.audit_json)


@dataclass(frozen=True)
class RootTxtAuthorizationCore:
    binding: Any
    backup_directory: Path
    source_path: Path
    confirmation_phrase: str = CONFIRMATION
    confirmation_policy: str = "explicit_phrase"
    profile_id: str = ROOT_TXT_PLACEMENT_PROFILE

    def revalidate(self, candidate: NewTxtAddResult, *, now=None,
                   max_age_seconds=DEFAULT_MAX_AGE_SECONDS) -> None:
        self.binding.revalidate(candidate, self.backup_directory, self.source_path,
                                now=now, max_age_seconds=max_age_seconds)


@dataclass(frozen=True)
class RootTxtPlacementAuthorization:
    core: RootTxtAuthorizationCore

    def require_same_candidate(self, candidate: RootTxtPlacementCandidate) -> None:
        self.core.binding.require_same_candidate(candidate.core)

    def to_dict(self) -> dict[str, Any]:
        return {"format": ("infocarry-disposable-root-txt-placement-authorization-v1"
                           if self.core.profile_id == DISPOSABLE_ROOT_TXT_PLACEMENT_PROFILE
                           else "infocarry-exact-root-txt-authorization-v1"),
                "profile": self.core.profile_id,
                "confirmation_phrase": self.core.confirmation_phrase,
                "inner_binding": self.core.binding.to_dict()}


@dataclass(frozen=True)
class RootTxtReadback:
    report_json: bytes

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.report_json)


@dataclass(frozen=True)
class RootTxtPlacementBundle:
    runtime: PinnedRootTxtRuntime
    before_backup: Any
    capacity_response: NativeCapacityResponse
    candidate: RootTxtPlacementCandidate
    authorization: RootTxtPlacementAuthorization
    source_artifact: OperationArtifact
    candidate_artifact: OperationArtifact
    capacity_artifact: OperationArtifact
    backup_artifact: OperationArtifact
    seal_artifact: OperationArtifact
    transaction_directory: Path
    envelope_json: bytes
    seal_sha256: str
    session_binding_token: str
    max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS
    placement_target_path: str = field(default=FIXTURE_PATH, kw_only=True)
    validation_placement: bool = field(default=False, kw_only=True)

    @property
    def operation_bundle(self):
        return self

    @property
    def core(self):
        return self

    @property
    def ready(self) -> bool:
        return True

    @property
    def source_path(self) -> Path:
        return Path(self.source_artifact.path)

    @property
    def bulk_out_endpoint(self) -> int:
        return 0x01

    @property
    def expected_folder_name(self) -> str:
        return self.placement_target_path.split("\\")[-1]

    @property
    def device_identity(self) -> tuple[str, str]:
        return ("0x054c", "0x001e")

    @property
    def operation_id(self) -> str:
        return "root-txt-placement-" + self.seal_sha256

    @property
    def operation_profile(self) -> str:
        return DISPOSABLE_ROOT_TXT_PLACEMENT_PROFILE if self.validation_placement else ROOT_TXT_PLACEMENT_PROFILE

    @property
    def result_format(self) -> str:
        return ("infocarry-disposable-root-txt-placement-result-v1" if self.validation_placement
                else "infocarry-exact-root-txt-placement-result-v1")

    @property
    def terminal_format(self) -> str:
        return ("infocarry-disposable-root-txt-placement-terminal-resolution-v1" if self.validation_placement
                else "infocarry-exact-root-txt-terminal-resolution-v1")

    @property
    def bundle_sha256(self) -> str:
        return self.seal_sha256

    @property
    def core_preflight_seal_sha256(self) -> str:
        return self.seal_sha256

    @property
    def preflight_seal_sha256(self) -> str:
        return self.seal_sha256

    @property
    def baseline_state_identity_sha256(self) -> str:
        from .prepared_library_package_live_adapter import _backup_identity
        return _backup_identity(self.before_backup).sha256

    @property
    def capacity_response_sha256(self) -> str:
        return _sha(_json(self.capacity_response.to_dict()))

    @property
    def candidate_blob_sha256(self) -> str:
        return self.candidate.candidate_blob_sha256

    @property
    def transaction_sha256(self) -> str:
        return self.candidate.transaction_sha256

    @property
    def authorization_sha256(self) -> str:
        return _sha(_json(self.authorization.to_dict()))

    @property
    def audit(self) -> Mapping[str, Any]:
        return MappingProxyType({"owner_approval_phrase":
            OwnerAuthorizedOperationIdentity.from_bundle(self).approval_phrase})

    def review_dict(self) -> dict[str, Any]:
        return {"format": ("infocarry-disposable-root-txt-placement-review-v1" if self.validation_placement else "infocarry-exact-root-txt-placement-review-v2"),
                "owner_identity": OwnerAuthorizedOperationIdentity.from_bundle(self).to_dict(),
                "fixture": _fixture_dict(self.placement_target_path, self.validation_placement),
                "device_state_binding": {
                    "model": "VNW-V15",
                    "baseline_state_identity_sha256": self.baseline_state_identity_sha256,
                    "capacity_response_sha256": self.capacity_response_sha256,
                    "target_absent": True,
                },
                "confirmation_phrase": self.authorization.core.confirmation_phrase, "automatic_retry_allowed": False,
                "required_post_backup": "complete_independent_exact_readback"}

    def _envelope(self) -> dict[str, Any]:
        return {"format": ("infocarry-disposable-root-txt-placement-bundle-v1" if self.validation_placement else "infocarry-exact-root-txt-placement-bundle-v2"),
                "profile": self.operation_profile, "model": "VNW-V15",
                "fixture": _fixture_dict(self.placement_target_path, self.validation_placement),
                "baseline_state_identity_sha256": self.baseline_state_identity_sha256,
                "baseline_artifact": self.backup_artifact.to_dict(),
                "source_artifact": self.source_artifact.to_dict(),
                "candidate_artifact": self.candidate_artifact.to_dict(),
                "candidate_audit_sha256": _sha(self.candidate.audit_json),
                "candidate_blob_sha256": self.candidate_blob_sha256,
                "transaction_sha256": self.transaction_sha256,
                "transaction_directory": str(self.transaction_directory),
                "capacity_artifact": self.capacity_artifact.to_dict(),
                "capacity_response_sha256": self.capacity_response_sha256,
                "authorization_sha256": self.authorization_sha256,
                "confirmation_phrase": self.authorization.core.confirmation_phrase, "no_retry": True,
                "one_sender": True, "native_success": "0x0000",
                "post_backup": "complete_independent_exact_readback"}

    def verify_seal(self) -> None:
        for artifact in (self.source_artifact, self.candidate_artifact, self.capacity_artifact,
                         self.backup_artifact, self.seal_artifact):
            artifact.verify()
        filename, payload = _placement_fixture(self.placement_target_path, self.validation_placement)
        if self.source_path.name != filename or self.source_path.read_bytes() != payload:
            raise ValueError("exact fixture source changed")
        expected_profile = DISPOSABLE_ROOT_TXT_PLACEMENT_PROFILE if self.validation_placement else ROOT_TXT_PLACEMENT_PROFILE
        expected_phrase = f"ADD {filename} ONCE"
        if self.authorization.core.profile_id != expected_profile or self.authorization.core.confirmation_phrase != expected_phrase:
            raise ValueError("placement authorization profile or target phrase differs")
        if self.candidate_artifact.sha256 != self.candidate_blob_sha256:
            raise ValueError("candidate artifact differs from frozen candidate")
        if self.capacity_artifact.sha256 != _sha(self.capacity_response.raw_response):
            raise ValueError("capacity artifact differs from frozen response")
        if self.authorization.core.backup_directory != self.before_backup.directory or self.authorization.core.source_path != self.source_path:
            raise ValueError("authorization paths differ from frozen inputs")
        if _json(self._envelope()) != self.envelope_json or _sha(self.envelope_json) != self.seal_sha256 or self.seal_artifact.sha256 != self.seal_sha256:
            raise ValueError("sealed operation identity changed")
        preserved = load_preserved_artifact(self.transaction_directory)
        if preserved != self.candidate.transaction:
            raise ValueError("preserved transaction differs from frozen transaction")
        before = verify_fresh_backup(self.before_backup.directory, max_age_seconds=None)
        if self.validation_placement:
            self._reconstruct_disposable_candidate(before)
            _disposable_delta(_blob(before), self.candidate.candidate_blob, self.placement_target_path)
        else:
            _exact_delta(_blob(before), self.candidate.candidate_blob)
        self.capacity_response.bind_model_lengths(len(_blob(before)), len(self.candidate.candidate_blob))
        self.authorization.require_same_candidate(self.candidate)
        self.authorization.core.revalidate(self.candidate.core, max_age_seconds=None)

    def _reconstruct_disposable_candidate(self, before):
        audit = self.candidate.audit_dict()
        preparation = audit.get("disposable_placement")
        if not isinstance(preparation, dict):
            raise ValueError("disposable placement preparation identity missing")
        result = build_new_root_txt_add(before.directory, self.source_path, self.expected_folder_name,
            source_template_offset=int(audit["template"]["record_offset_hex"], 16),
            available_capacity_bytes=self.capacity_response.capacity_limit_bytes-len(_blob(before)),
            record_timestamp_be32=preparation["record_timestamp_be32"], max_age_seconds=None,
            fresh_new_allocation=True)
        rebuilt_audit = result.audit_dict()
        rebuilt_audit["disposable_placement"] = preparation
        if result.candidate_blob != self.candidate.candidate_blob or result.transaction != self.candidate.transaction or _json(rebuilt_audit) != self.candidate.audit_json:
            raise ValueError("disposable candidate/transaction/audit differs from independent reconstruction")

    def _consume_execution_claim(self, owner: PersistentWriteSafetyOwner):
        from .prepared_library_package_live_adapter import _execution_claim_bindings
        self.verify_seal()
        return owner.consume_execution_claim(_execution_claim_bindings(self))

    def verify_execution_equivalence(self, before, capacity) -> dict[str, Any]:
        """Check current read-only state immediately before claim/sender."""
        from .prepared_library_package_live_adapter import _backup_identity
        owner = PersistentWriteSafetyOwner(
            execution_claim_store=self.runtime.execution_claim_store,
            indeterminate_write_lock=self.runtime.indeterminate_write_lock,
        )
        owner.inspect_execution_boundary()
        if self.runtime.execution_equivalence is None:
            device = self.runtime.detect_device()
            observed_capacity = self.runtime.query_capacity()
            generation = None
        else:
            device, observed_capacity, generation = self.runtime.execution_equivalence(
                self.session_binding_token
            )
        if device != (0x054C, 0x001E):
            raise ValueError("execution-equivalence device is not VNW-V15")
        if observed_capacity != self.capacity_response or capacity != self.capacity_response:
            raise ValueError("execution-equivalence capacity differs from approved state")
        if _backup_identity(before).sha256 != self.baseline_state_identity_sha256:
            raise ValueError("execution-equivalence baseline state differs from approval")
        self._exact_candidate_binding()
        if self.runtime.arm_sender is not None and generation is not None:
            self.runtime.arm_sender(generation)
        return {
            "device_identity": ["0x054c", "0x001e"],
            "baseline_state_identity_sha256": self.baseline_state_identity_sha256,
            "capacity_response_sha256": self.capacity_response_sha256,
            "target_absent": True,
            "candidate_blob_sha256": self.candidate_blob_sha256,
            "transaction_sha256": self.transaction_sha256,
            "claim": "none_before_equivalence",
            "sender_marker": "none_before_equivalence",
            "global_lock": "clear_before_equivalence",
        }

    def _exact_candidate_binding(self) -> None:
        if self.candidate_artifact.sha256 != self.candidate_blob_sha256:
            raise ValueError("candidate artifact differs from frozen candidate")
        if self.candidate.transaction.ranges[4] + self.candidate.transaction.ranges[7] != self.candidate.candidate_blob:
            raise ValueError("sender transaction does not contain the exact frozen candidate")
        if self.authorization.core.binding.candidate_blob_sha256 != self.candidate_blob_sha256:
            raise ValueError("authorization does not bind the exact frozen candidate")

    def revalidate_frozen_candidate(self, before, capacity):
        from .prepared_library_package_live_adapter import _backup_identity
        self.verify_seal()
        if _backup_identity(before).sha256 != self.baseline_state_identity_sha256 or capacity != self.capacity_response:
            raise ValueError("fresh baseline/capacity differs from frozen bundle")
        return self.candidate, self.authorization

    def verify_readback(self, after, *, completion, now=None, max_age_seconds=None):
        self.verify_seal()
        if type(completion) is not int or completion != 0:
            raise ValueError("normal terminal native 0x0000 is required")
        verified = self.authorization.core.binding.verify_post_add_backup(
            self.candidate.core, self.before_backup.directory, self.source_path, after.directory,
            now=now, max_age_seconds=max_age_seconds)
        exact = (_disposable_delta(_blob(self.before_backup), _blob(after), self.placement_target_path)
                 if self.validation_placement else _exact_delta(_blob(self.before_backup), _blob(after)))
        return RootTxtReadback(_json({"independent_complete_backup_verification": verified.to_dict(),
                                     "exact_path_and_payload_verification": exact}))

    def write_success_evidence(self, destination, before, after, audit) -> None:
        verification = self.verify_readback(after, completion=0).to_dict()
        audit_verification = audit.get("verification")
        # Backup verification timestamps are observational and may differ by
        # the time the terminal evidence is written; all immutable identity
        # and payload fields remain exact.
        if isinstance(audit_verification, dict):
            audit_verification = json.loads(json.dumps(audit_verification))
            for label in ("before_backup", "after_backup"):
                if isinstance(audit_verification.get("independent_complete_backup_verification", {}).get(label), dict):
                    audit_verification["independent_complete_backup_verification"][label].pop("verified_at_utc", None)
        expected_verification = json.loads(json.dumps(verification))
        for label in ("before_backup", "after_backup"):
            if isinstance(expected_verification.get("independent_complete_backup_verification", {}).get(label), dict):
                expected_verification["independent_complete_backup_verification"][label].pop("verified_at_utc", None)
        if audit.get("state") != "readback_verified" or audit.get("completion") != "0x0000" or audit.get("workflow", {}).get("sender_calls") != 1 or audit_verification != expected_verification:
            raise ValueError("success audit is not the verified one-shot result")
        _write_json(destination, {"format": self.result_format,
                                 "bundle": json.loads(self.envelope_json),
                                 "before_backup": before.to_dict(), "after_backup": after.to_dict(),
                                 "result_audit": audit})

    def write_terminal_evidence(self, destination, claim, marker, store, result_manifest) -> None:
        current = store.read_sender_in_flight()
        if current is not None:
            raise ValueError("sender marker remains unresolved")
        _write_json(destination, {"format": self.terminal_format,
                                 "claim": claim.to_dict(), "sender_marker": marker.to_dict(),
                                 "resolution": "verified_terminal_success",
                                 "result_manifest": OperationArtifact.file(result_manifest).to_dict()})

    def write_placement_report(self, root, audit, after) -> Path:
        if self.validation_placement:
            raise ValueError("disposable placement cannot produce a P18-041H prestage report")
        if audit.get("execution_claim", {}).get("committed") is not True or audit.get("execution_claim", {}).get("sender_marker", {}).get("resolved") is not True:
            raise ValueError("report requires a committed claim and terminal marker resolution")
        verification = self.verify_readback(after, completion=0).to_dict()
        path = Path(root) / "01-fixture-prestage" / "placement-readback-or-backup-report.json"
        path.parent.mkdir()
        _write_json(path, {"format": PRESTAGE_REPORT_FORMAT, "experiment_id": "P18-041H",
            "status": "completed_and_independently_verified", "operation": "separate_fixture_placement",
            "completed_before_delete": True, "placement_readback_verified": True,
            "owner_authorization_status": "separate_owner_authorized",
            "owner_authorized_operation": OwnerAuthorizedOperationIdentity.from_bundle(self).to_dict(),
            "owner_authorization_fingerprint": OwnerAuthorizedOperationIdentity.from_bundle(self).identity_sha256,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "physical_operation_count": 1, "add_count": 1, "delete_count": 0,
            "subtree_operation": False, "retry_count": 0, "sender_invocations": 1,
            "fixture": _fixture_dict(self.placement_target_path, self.validation_placement), "post_placement_backup": {
                "path": str(after.directory), "manifest_sha256": after.manifest_sha256,
                "blob_sha256": after.blob_sha256}, "verification": verification,
            "later_delete_session": "not_started_by_placement",
            "result_manifest": OperationArtifact.file(Path(root) / "result-manifest-0001.json").to_dict()})
        _validate_fixture_prestage_report(path)
        return path

    def write_operation_report(self, root, audit, after) -> Path:
        """Canonical runner hook; the established placement report is unchanged."""
        if self.validation_placement:
            if audit.get("state") != "readback_verified" or audit.get("completion") != "0x0000" or audit.get("workflow", {}).get("sender_calls") != 1:
                raise ValueError("disposable report requires verified native-zero one-shot result")
            if audit.get("execution_claim", {}).get("committed") is not True or audit.get("execution_claim", {}).get("sender_marker", {}).get("resolved") is not True:
                raise ValueError("report requires committed claim and resolved marker")
            path = Path(root) / "disposable-placement-report.json"
            _write_json(path, {"format": "infocarry-disposable-root-txt-placement-report-v1",
                "experiment_id": "P18-044", "status": "completed_and_independently_verified",
                "operation": "separate_fixture_placement", "fixture": _fixture_dict(self.placement_target_path, True),
                "sender_invocations": 1, "add_count": 1, "delete_count": 0, "retry_count": 0,
                "native_completion": "0x0000",
                "owner_authorized_operation": OwnerAuthorizedOperationIdentity.from_bundle(self).to_dict(),
                "post_placement_backup": {"path": str(after.directory), "manifest_sha256": after.manifest_sha256,
                                          "blob_sha256": after.blob_sha256},
                "verification": self.verify_readback(after, completion=0).to_dict(),
                "result_manifest": OperationArtifact.file(Path(root) / "result-manifest-0001.json").to_dict()})
            return path
        return self.write_placement_report(root, audit, after)

    def reconcile_result(self, result):
        if result.preflight is not self or result.candidate is not self.candidate or result.authorization is not self.authorization or result.audit.get("workflow", {}).get("sender_calls") != 1:
            raise ValueError("runner result differs from the approved frozen bundle")
        verification = self.verify_readback(result.after_backup, completion=result.completion).to_dict()
        actual = json.loads(json.dumps(result.verification.to_dict()))
        audited = json.loads(json.dumps(result.audit.get("verification")))
        expected = json.loads(json.dumps(verification))
        for value in (actual, audited, expected):
            for label in ("before_backup", "after_backup"):
                node = value.get("independent_complete_backup_verification", {}).get(label)
                if isinstance(node, dict):
                    node.pop("verified_at_utc", None)
        if actual != expected or audited != expected:
            raise ValueError("independent root readback reconciliation failed")
        if self.validation_placement:
            report = json.loads((Path(result.audit["evidence_outputs"]["root"]) / "disposable-placement-report.json").read_bytes())
            if (report.get("format") != "infocarry-disposable-root-txt-placement-report-v1"
                    or report.get("fixture") != _fixture_dict(self.placement_target_path, True)
                    or report.get("native_completion") != "0x0000"
                    or report.get("sender_invocations") != 1 or report.get("retry_count") != 0
                    or report.get("owner_authorized_operation") != OwnerAuthorizedOperationIdentity.from_bundle(self).to_dict()):
                raise ValueError("disposable placement report identity differs")
        else:
            _validate_fixture_prestage_report(Path(result.audit["evidence_outputs"]["root"]) / "01-fixture-prestage" / "placement-readback-or-backup-report.json")
        return result


class RootTxtPlacementFacade(LibraryTransferExecutionFacade):
    """Reuse exact owner approval and P18-040's approved-rebuild barrier."""

    def __init__(self, runtime: PinnedRootTxtRuntime):
        if not isinstance(runtime, PinnedRootTxtRuntime):
            raise ValueError("placement requires the pinned operation runtime")
        super().__init__()
        self.runtime = runtime

    def discard_prepared_operation(self) -> None:
        super().discard_prepared_operation()
        self.runtime.close()

    def prepare(self, source_path: Path, *, target_path: str = FIXTURE_PATH,
                device_model: str = "VNW-V15", max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
                validation_placement: bool = False):
        if self.stop_approved_rebuild():
            raise LibraryTransferExecutionError("approved operation cannot refresh or adopt a new candidate", stage="owner_authorization")
        try:
            if self._prepared_operation is not None:
                raise ValueError("discard the previous operation before preparing another")
            if device_model != "VNW-V15":
                raise ValueError("only VNW-V15 placement is admitted")
            filename, payload = _placement_fixture(target_path, validation_placement)
            source = Path(source_path).expanduser().resolve()
            if source.name != filename or not source.is_file() or source.read_bytes() != payload:
                raise ValueError("fixture source name/payload differs")
            if max_age_seconds != DEFAULT_MAX_AGE_SECONDS:
                raise ValueError("placement must use the established fresh-backup age policy")
            runtime = self.runtime
            owner = PersistentWriteSafetyOwner(execution_claim_store=runtime.execution_claim_store,
                                                indeterminate_write_lock=runtime.indeterminate_write_lock)
            owner.inspect_execution_boundary()
            if runtime.detect_device() != (0x054c, 0x001e):
                raise ValueError("detected device is not VNW-V15")
            capacity = runtime.query_capacity()
            if not isinstance(capacity, NativeCapacityResponse):
                raise ValueError("fresh native capacity response required")
            root = Path(runtime.evidence_namespace).expanduser().resolve() / ("prepared-root-txt-" + uuid4().hex)
            root.mkdir(parents=True)
            before = capture_and_verify_fresh_backup(root / "backup-baseline", runtime.capture)
            if before.device_identity != ("0x054c", "0x001e"):
                raise ValueError("backup is not VNW-V15")
            runtime.assert_same_session(runtime.session_binding_token)
            baseline_blob = _blob(before)
            parsed = parse_backup_blob(baseline_blob)
            templates = [offset for offset in parsed.paths if parsed.record_at(offset).kind == "file" and parsed.record_at(offset).extension.lower() == "txt"]
            if validation_placement:
                templates = [offset for offset in templates if parsed.paths[offset][:-1] == ("root",)
                             and parsed.record_at(offset).extension == "txt"
                             and parsed.record_at(offset).flag in (0x20, 0xE0)
                             and parsed.record_at(offset).field_14_be32 == 0x200]
            if not templates:
                raise ValueError("baseline has no ordinary TXT template")
            if validation_placement:
                _absent_disposable_target(parsed, filename)
            source_copy = root / filename
            with source_copy.open("xb") as output:
                output.write(source.read_bytes())
            timestamp = runtime.new_record_timestamp_be32()
            result = build_new_root_txt_add(before.directory, source_copy, filename,
                source_template_offset=templates[0], available_capacity_bytes=capacity.capacity_limit_bytes-len(baseline_blob),
                record_timestamp_be32=timestamp, fresh_new_allocation=validation_placement)
            if validation_placement:
                _disposable_delta(baseline_blob, result.candidate_blob, target_path)
            else:
                _exact_delta(baseline_blob, result.candidate_blob)
            capacity.bind_model_lengths(len(baseline_blob), len(result.candidate_blob))
            candidate_path = root / "candidate.bin"
            with candidate_path.open("xb") as output:
                output.write(result.candidate_blob)
            transaction_directory = root / "transaction"
            result.transaction.preserve(transaction_directory, source="disposable-root-txt-placement" if validation_placement else "exact-root-txt-placement")
            capacity_path = root / "capacity-0019.bin"
            with capacity_path.open("xb") as output:
                output.write(capacity.raw_response)
            candidate_audit = result.audit_dict()
            if validation_placement:
                candidate_audit["disposable_placement"] = {"record_timestamp_be32": timestamp}
            candidate = RootTxtPlacementCandidate(result.candidate_blob, result.transaction, _json(candidate_audit))
            binding = authorize_new_txt_add(result, confirmation=NEW_ROOT_TXT_CONFIRMATION_PHRASE)
            authorization = RootTxtPlacementAuthorization(RootTxtAuthorizationCore(binding, before.directory, source_copy,
                confirmation_phrase=f"ADD {filename} ONCE",
                profile_id=DISPOSABLE_ROOT_TXT_PLACEMENT_PROFILE if validation_placement else ROOT_TXT_PLACEMENT_PROFILE))
            seal_path = root / "operation-bundle.json"
            from dataclasses import replace
            provisional = RootTxtPlacementBundle(runtime,before,capacity,candidate,authorization,
                OperationArtifact.file(source_copy), OperationArtifact.file(candidate_path),
                OperationArtifact.file(capacity_path), OperationArtifact.backup_manifest(before.directory),
                OperationArtifact(str(seal_path), "0"*64, "file_bytes", 0),
                transaction_directory,b"", "0"*64,runtime.session_binding_token,None,
                placement_target_path=target_path, validation_placement=validation_placement)
            envelope = _json(provisional._envelope())
            with seal_path.open("xb") as output:
                output.write(envelope)
            bundle = replace(provisional, envelope_json=envelope, seal_sha256=_sha(envelope),
                             seal_artifact=OperationArtifact.file(seal_path))
            bundle.verify_seal()
            self._prepared_operation = bundle
            return bundle
        except BaseException:
            self.discard_prepared_operation()
            raise

    def adopt_prepared_operation(self, prepared) -> None:
        if self.owner_approval_accepted:
            self.discard_prepared_operation()
            raise LibraryTransferExecutionError("approved operation cannot adopt a replacement", stage="owner_authorization")
        if type(prepared) is not RootTxtPlacementBundle or prepared.runtime is not self.runtime:
            raise ValueError("placement can adopt only its own pinned bundle")
        prepared.verify_seal()
        self._prepared_operation = prepared

    def execute_once(self, *, confirmation_interaction, progress=None, **runner_overrides):
        prepared = self._prepared_operation
        try:
            if prepared is None or self._owner_authorized_identity is None:
                raise LibraryTransferExecutionError("separate exact owner approval required", stage="owner_authorization")
            prepared.verify_seal()
            admit = getattr(prepared, "assert_execution_admitted", None)
            if admit is not None:
                admit()
            if OwnerAuthorizedOperationIdentity.from_bundle(prepared) != self._owner_authorized_identity:
                raise LibraryTransferExecutionError("stale owner approval", stage="owner_authorization")
            if runner_overrides:
                raise ValueError("root placement does not permit runtime/candidate rebinding")
            from .experimental_library_transfer import GuardedLibraryExecutionCoordinator
            coordinator = GuardedLibraryExecutionCoordinator(
                execution_claim_store=self.runtime.execution_claim_store,
                indeterminate_write_lock=self.runtime.indeterminate_write_lock)
            return coordinator.execute(prepared, plan_report=prepared.review_dict(),
                confirmation_interaction=confirmation_interaction,
                owner_authorized_identity=self._owner_authorized_identity,
                detect_device=self.runtime.detect_device, query_capacity=self.runtime.query_capacity,
                backend=self.runtime.backend, capture=self.runtime.capture,
                evidence_namespace=self.runtime.evidence_namespace,
                max_age_seconds=None, progress=progress)
        finally:
            self.discard_prepared_operation()
