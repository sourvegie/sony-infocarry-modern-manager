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
from .new_txt import NewTxtAddResult, build_new_root_txt_add, build_new_nested_txt_add
from .new_bmp import build_new_root_bmp_add, build_new_nested_bmp_add
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
DISPOSABLE_NESTED_TXT_PLACEMENT_PROFILE = "vnw-v15-disposable-nested-txt-placement-validation-v1"
DISPOSABLE_NESTED_BMP_PLACEMENT_PROFILE = "vnw-v15-disposable-nested-bmp-placement-validation-v1"
DISPOSABLE_ROOT_BMP_PLACEMENT_PROFILE = "vnw-v15-disposable-root-bmp-placement-validation-v1"


def _placement_fixture(target_path, validation_placement, media_type="txt", *, nested_validation=False):
    if type(validation_placement) is not bool:
        raise ValueError("validation placement opt-in must be explicit boolean")
    if type(nested_validation) is not bool:
        raise ValueError("nested validation opt-in must be explicit boolean")
    if nested_validation:
        from .delete_workflow import (NESTED_TXT_DELETE_VALIDATION_PATH, NESTED_TXT_DELETE_VALIDATION_BYTES,
                                      NESTED_BMP_DELETE_VALIDATION_PATH, ROOT_BMP_DELETE_FIXTURE_BYTES)
        expected = {"txt": (NESTED_TXT_DELETE_VALIDATION_PATH, NESTED_TXT_DELETE_VALIDATION_BYTES),
                    "bmp": (NESTED_BMP_DELETE_VALIDATION_PATH, ROOT_BMP_DELETE_FIXTURE_BYTES)}
        if not validation_placement or media_type not in expected or target_path != expected[media_type][0]:
            raise ValueError("nested placement admits only its exact disposable validation target")
        return target_path.split("\\")[-1], expected[media_type][1]
    if media_type not in {"txt", "bmp"}:
        raise ValueError("placement media type must be TXT or BMP")
    if media_type == "bmp" and not validation_placement:
        raise ValueError("root BMP placement is restricted to the disposable experiment")
    if validation_placement:
        # Lazy: delete_workflow inherits the existing placement bundle.
        if media_type == "bmp":
            from .delete_workflow import ROOT_BMP_DELETE_VALIDATION_FILES
            payload = ROOT_BMP_DELETE_VALIDATION_FILES.get(target_path)
        else:
            from .delete_workflow import ROOT_TXT_DELETE_VALIDATION_FILES
            payload = ROOT_TXT_DELETE_VALIDATION_FILES.get(target_path)
        if payload is None:
            raise ValueError("only the exact named disposable placement target is admitted")
        return target_path.split("\\")[-1], payload
    if media_type != "txt":
        raise ValueError("only the exact VNW-V15 direct-root TXT fixture is admitted")
    if target_path != FIXTURE_PATH:
        raise ValueError("only the exact VNW-V15 direct-root TXT fixture is admitted")
    return FIXTURE_FILENAME, FIXTURE_BYTES


def _fixture_dict(target_path, validation_placement, media_type="txt", *, nested_validation=False):
    if not validation_placement:
        return fixture_identity()
    filename, payload = _placement_fixture(target_path, True, media_type, nested_validation=nested_validation)
    return {"path": target_path, "filename": filename, "length": len(payload),
            "sha256": _sha(payload), "media_type": media_type,
            "disposable_validation_only": True}


def _absent_disposable_target(parsed, filename):
    stem = filename[:-4].casefold()
    if any(len(path) == 2 and path[0].casefold() == "root" and
           path[1].casefold() == stem for path in parsed.paths.values()):
        raise ValueError("disposable target must be absent without native-stem ambiguity")


def _select_nested_txt_template(parsed):
    """Use the existing facade traversal consistently in host and live preparation.

    Eligible records may have different identities and payloads. Only the copied
    native signature may agree; full source identity is bound separately.
    """
    offsets = [offset for offset in parsed.paths
               if parsed.record_at(offset).kind == "file"
               and parsed.record_at(offset).extension == "txt"
               and parsed.record_at(offset).flag == 0xe0
               and parsed.record_at(offset).field_10_be32 == 0xffffffff
               and parsed.record_at(offset).field_14_be32 == 0x200
               and len(parsed.payload_parts(parsed.record_at(offset))[0]) == 32]
    signatures = {bytes.fromhex(parsed.record_at(offset).raw_hex)[:4] +
                  bytes.fromhex(parsed.record_at(offset).raw_hex)[16:24] +
                  parsed.payload_parts(parsed.record_at(offset))[0] for offset in offsets}
    if not offsets or len(signatures) != 1:
        raise ValueError("nested TXT templates are missing or have ambiguous copied native fields")
    return offsets[0]


def _nested_txt_template_provenance(parsed, offset):
    if type(offset) is not int or offset not in parsed.paths:
        raise ValueError("nested template identity is not an exact reachable record")
    record = parsed.record_at(offset)
    prefix, payload = parsed.payload_parts(record)
    raw = bytes.fromhex(record.raw_hex)
    return {"record_offset_hex": f"0x{offset:08x}",
            "path": "\\".join(parsed.paths[offset]) + "." + record.extension,
            "record_sha256": _sha(raw), "payload_sha256": _sha(payload),
            "prefix_sha256": _sha(prefix), "copied_fields_sha256": _sha(raw[:4] + raw[16:24])}


def _select_nested_bmp_template(parsed):
    """One canonical source traversal for rehearsal and guarded preparation."""
    from .prepared_media_package import validate_bmp_payload
    offsets = []
    for offset in parsed.paths:
        record = parsed.record_at(offset)
        if (record.kind != "file" or record.extension != "bmp" or record.flag != 0xe0
                or record.field_10_be32 != 0xffffffff or record.field_14_be32 != 0x100):
            continue
        prefix, payload = parsed.payload_parts(record)
        if prefix != b"\xff" * 16:
            continue
        try:
            validate_bmp_payload(payload)
        except ValueError:
            continue
        offsets.append(offset)
    signatures = {bytes.fromhex(parsed.record_at(o).raw_hex)[:4] +
                  bytes.fromhex(parsed.record_at(o).raw_hex)[16:24] +
                  parsed.payload_parts(parsed.record_at(o))[0] for o in offsets}
    if not offsets or len(signatures) != 1:
        raise ValueError("nested BMP templates are missing or have ambiguous copied native fields")
    return offsets[0]


def require_nested_placement_provenance(parsed, operation, candidate_audit, media_type="txt"):
    """Reject contradictory provenance even if resulting device bytes agree."""
    if media_type not in {"txt", "bmp"}:
        raise ValueError("unsupported nested template media")
    offset = (_select_nested_bmp_template if media_type == "bmp" else _select_nested_txt_template)(parsed)
    identity = _nested_txt_template_provenance(parsed, offset)
    expected = {key: identity[key] for key in ("record_offset_hex", "path", "record_sha256")}
    if media_type == "bmp":
        expected.update(payload_sha256=identity["payload_sha256"], prefix_sha256=identity["prefix_sha256"],
                        copied_record_fields_sha256=identity["copied_fields_sha256"])
    if (type(operation.get("template_offset")) is not int
            or operation["template_offset"] != offset
            or operation.get("template_provenance") != identity
            or candidate_audit.get("template") != expected):
        raise ValueError("task and sealed placement source-template provenance differ")


def _nested_parent(parsed, target_path):
    parent_path = tuple(target_path.split("\\")[:-1])
    offsets = [offset for offset, path in parsed.paths.items() if path == parent_path]
    if len(offsets) != 1 or parsed.record_at(offsets[0]).kind != "directory":
        raise ValueError("exact existing disposable nested parent is unavailable")
    return parent_path, offsets[0]


def _nested_disposable_delta(before, after, target_path, media_type="txt"):
    from .delete_model import verify_nested_file_delete_model
    filename, payload = _placement_fixture(target_path, True, media_type, nested_validation=True)
    baseline, candidate = parse_backup_blob(before), parse_backup_blob(after)
    parent_path, _ = _nested_parent(baseline, target_path)
    target = parent_path + (filename[:-4],)
    if any(tuple(part.casefold() for part in path) == tuple(part.casefold() for part in target)
           for path in baseline.paths.values()):
        raise ValueError("nested disposable target already exists or is ambiguous")
    offsets = [offset for offset, path in candidate.paths.items() if path == target]
    if len(offsets) != 1:
        raise ValueError("one exact nested disposable target is required")
    record = candidate.record_at(offsets[0])
    prefix, actual = candidate.payload_parts(record)
    if (record.kind != "file" or record.extension != media_type or record.flag != 0xe0
            or record.field_10_be32 != 0xffffffff
            or record.field_14_be32 != (0x100 if media_type == "bmp" else 0x200)
            or len(prefix) != (16 if media_type == "bmp" else 32)
            or (media_type == "bmp" and prefix != b"\xff" * 16) or actual != payload):
        raise ValueError("nested disposable target native identity differs")
    # An independent inverse check proves all raw survivor records, markers,
    # payloads, padding, timestamps and opaque header/trailer bytes are exact.
    verify_nested_file_delete_model(candidate, before, target_path, record.offset)
    return {"fixture_count_in_parent": 1, "payload_length": len(payload),
            "payload_sha256": _sha(payload), "only_path_delta": target_path,
            "unrelated_payloads_unchanged": True, "surviving_prefixes_unchanged": True,
            "surviving_timestamps_unchanged": True, "inverse_delete_exact_baseline": True}


def _disposable_delta(before, after, target_path, media_type="txt", *, nested_validation=False):
    if nested_validation:
        return _nested_disposable_delta(before, after, target_path, media_type)
    filename, payload = _placement_fixture(target_path, True, media_type)
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
    old_order = [path for offset, path in sorted((o, p) for o, p in baseline.paths.items()
                                                 if len(p) == 2 and p[0].casefold() == "root")]
    new_order = [path for offset, path in sorted((o, p) for o, p in candidate.paths.items()
                                                 if len(p) == 2 and p[0].casefold() == "root")]
    if new_order != old_order + [target]:
        raise ValueError("placement did not append exactly one direct-root child")
    added = new[target]
    if added.kind != "file":
        raise ValueError("placement target is not an ordinary file record")
    if media_type == "bmp":
        from .delete_workflow import ROOT_BMP_DELETE_EXPANSION_PATH, _root_bmp_expansion_anchor_present
        if target_path == ROOT_BMP_DELETE_EXPANSION_PATH:
            if added.offset != 0x6c0 or not _root_bmp_expansion_anchor_present(baseline):
                raise ValueError("BMP B placement requires the exact TXT A anchor at 0x680 and B at 0x6c0")
    if media_type == "txt":
        expected = (added.extension == "txt" and added.flag in (0x20, 0xE0)
                    and added.field_14_be32 == 0x200)
    else:
        prefix, bmp_payload = candidate.payload_parts(added)
        expected = (added.extension == "bmp" and added.flag == 0xE0
                    and added.field_14_be32 == 0x100 and prefix == b"\xff" * 16
                    and bmp_payload == payload)
    if not expected or candidate.payload_parts(added)[1] != payload:
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


def _require_nested_bmp_task_header(envelope, source_head):
    from .delete_workflow import NESTED_BMP_DELETE_VALIDATION_PATH, ROOT_BMP_DELETE_FIXTURE_BYTES
    if (type(source_head) is not str or len(source_head) != 40
            or any(c not in "0123456789abcdef" for c in source_head)
            or type(envelope) is not dict
            or envelope.get("format") != "infocarry-nested-bmp-delete-task-envelope-v1"
            or envelope.get("task") != "P18-051"
            or envelope.get("status") != "prepared_for_independent_review"
            or envelope.get("source_head") != source_head
            or envelope.get("model") != "VNW-V15"
            or envelope.get("vendor_id") != "0x054c" or envelope.get("product_id") != "0x001e"
            or envelope.get("target") != NESTED_BMP_DELETE_VALIDATION_PATH
            or _json(envelope.get("fixture")) != _json({"bytes":len(ROOT_BMP_DELETE_FIXTURE_BYTES), "sha256":_sha(ROOT_BMP_DELETE_FIXTURE_BYTES)})
            or type(envelope.get("maximum_sender_invocations")) is not int
            or envelope["maximum_sender_invocations"] != 2
            or envelope.get("automatic_retry_allowed") is not False
            or type(envelope.get("extra_setup_or_cleanup_writes")) is not int
            or envelope["extra_setup_or_cleanup_writes"] != 0):
        raise ValueError("exact two-write nested BMP task contract required")


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
        return {"format": ("infocarry-disposable-nested-bmp-placement-authorization-v1"
                           if self.core.profile_id == DISPOSABLE_NESTED_BMP_PLACEMENT_PROFILE
                           else "infocarry-disposable-nested-txt-placement-authorization-v1"
                           if self.core.profile_id == DISPOSABLE_NESTED_TXT_PLACEMENT_PROFILE
                           else "infocarry-disposable-root-bmp-placement-authorization-v1"
                           if self.core.profile_id == DISPOSABLE_ROOT_BMP_PLACEMENT_PROFILE
                           else "infocarry-disposable-root-txt-placement-authorization-v1"
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
    placement_media: str = field(default="txt", kw_only=True)
    nested_validation: bool = field(default=False, kw_only=True)

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
        if self.nested_validation:
            return f"nested-{self.placement_media}-placement-" + self.seal_sha256
        prefix = "root-bmp-placement-" if self.placement_media == "bmp" else "root-txt-placement-"
        return prefix + self.seal_sha256

    @property
    def operation_profile(self) -> str:
        if self.nested_validation:
            return DISPOSABLE_NESTED_BMP_PLACEMENT_PROFILE if self.placement_media == "bmp" else DISPOSABLE_NESTED_TXT_PLACEMENT_PROFILE
        if self.validation_placement and self.placement_media == "bmp":
            return DISPOSABLE_ROOT_BMP_PLACEMENT_PROFILE
        return DISPOSABLE_ROOT_TXT_PLACEMENT_PROFILE if self.validation_placement else ROOT_TXT_PLACEMENT_PROFILE

    @property
    def owner_confirmation_phrase(self) -> Optional[str]:
        if self.nested_validation:
            return f"ADD {self.expected_folder_name} ONCE"
        if self.validation_placement and self.placement_media == "bmp":
            return f"ADD {self.expected_folder_name} ONCE"
        return None

    @property
    def result_format(self) -> str:
        if self.nested_validation:
            return f"infocarry-disposable-nested-{self.placement_media}-placement-result-v1"
        if self.validation_placement and self.placement_media == "bmp":
            return "infocarry-disposable-root-bmp-placement-result-v1"
        return ("infocarry-disposable-root-txt-placement-result-v1" if self.validation_placement
                else "infocarry-exact-root-txt-placement-result-v1")

    @property
    def terminal_format(self) -> str:
        if self.nested_validation:
            return f"infocarry-disposable-nested-{self.placement_media}-placement-terminal-resolution-v1"
        if self.validation_placement and self.placement_media == "bmp":
            return "infocarry-disposable-root-bmp-placement-terminal-resolution-v1"
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
        review_format = (f"infocarry-disposable-nested-{self.placement_media}-placement-review-v1" if self.nested_validation
                         else "infocarry-disposable-root-bmp-placement-review-v1"
                         if self.validation_placement and self.placement_media == "bmp"
                         else "infocarry-disposable-root-txt-placement-review-v1"
                         if self.validation_placement else "infocarry-exact-root-txt-placement-review-v2")
        return {"format": review_format,
                "owner_identity": OwnerAuthorizedOperationIdentity.from_bundle(self).to_dict(),
                "fixture": _fixture_dict(self.placement_target_path, self.validation_placement, self.placement_media, nested_validation=self.nested_validation),
                "device_state_binding": {
                    "model": "VNW-V15",
                    "baseline_state_identity_sha256": self.baseline_state_identity_sha256,
                    "capacity_response_sha256": self.capacity_response_sha256,
                    "target_absent": True,
                },
                "confirmation_phrase": self.authorization.core.confirmation_phrase, "automatic_retry_allowed": False,
                "required_post_backup": "complete_independent_exact_readback"}

    def _envelope(self) -> dict[str, Any]:
        envelope_format = (f"infocarry-disposable-nested-{self.placement_media}-placement-bundle-v1" if self.nested_validation
                           else "infocarry-disposable-root-bmp-placement-bundle-v1"
                           if self.validation_placement and self.placement_media == "bmp"
                           else "infocarry-disposable-root-txt-placement-bundle-v1"
                           if self.validation_placement else "infocarry-exact-root-txt-placement-bundle-v2")
        return {"format": envelope_format,
                "profile": self.operation_profile, "model": "VNW-V15",
                "fixture": _fixture_dict(self.placement_target_path, self.validation_placement, self.placement_media, nested_validation=self.nested_validation),
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
        filename, payload = _placement_fixture(self.placement_target_path, self.validation_placement, self.placement_media, nested_validation=self.nested_validation)
        if self.source_path.name != filename or self.source_path.read_bytes() != payload:
            raise ValueError("exact fixture source changed")
        expected_profile = self.operation_profile
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
            _disposable_delta(_blob(before), self.candidate.candidate_blob, self.placement_target_path, self.placement_media, nested_validation=self.nested_validation)
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
        builder = ((build_new_nested_bmp_add if self.placement_media == "bmp" else build_new_nested_txt_add) if self.nested_validation else
                   build_new_root_bmp_add if self.placement_media == "bmp" else build_new_root_txt_add)
        kwargs = {"source_template_offset": int(audit["template"]["record_offset_hex"], 16),
                  "available_capacity_bytes": self.capacity_response.capacity_limit_bytes-len(_blob(before)),
                  "record_timestamp_be32": preparation["record_timestamp_be32"],
                  "max_age_seconds": None}
        if self.nested_validation:
            parent_path, parent_offset = _nested_parent(parse_backup_blob(_blob(before)), self.placement_target_path)
            kwargs.update(target_directory_path=parent_path, target_directory_offset=parent_offset)
        elif self.placement_media == "txt":
            kwargs["fresh_new_allocation"] = True
        result = builder(before.directory, self.source_path, self.expected_folder_name, **kwargs)
        rebuilt_audit = result.audit_dict()
        rebuilt_audit["disposable_placement"] = preparation
        if result.candidate_blob != self.candidate.candidate_blob or result.transaction != self.candidate.transaction or _json(rebuilt_audit) != self.candidate.audit_json:
            raise ValueError("disposable candidate/transaction/audit differs from independent reconstruction")

    def require_two_write_task_binding(self, envelope, *, source_head, placement_result=None):
        """Bind this exact placement and its inverse to the single task intent."""
        from .delete_generalized import build_nested_file_delete_candidate
        from .delete_workflow import NESTED_BMP_DELETE_VALIDATION_PATH
        self.verify_seal()
        if (not self.nested_validation or self.placement_media != "bmp"
                or self.placement_target_path != NESTED_BMP_DELETE_VALIDATION_PATH
                or placement_result is not None):
            raise ValueError("two-write task requires the exact nested BMP placement")
        _require_nested_bmp_task_header(envelope, source_head)
        before = parse_backup_blob(_blob(self.before_backup))
        after = parse_backup_blob(self.candidate.candidate_blob)
        parent_path, parent_offset = _nested_parent(before, self.placement_target_path)
        offsets = [o for o,p in after.paths.items() if p == parent_path + (self.expected_folder_name[:-4],)]
        if len(offsets) != 1:
            raise ValueError("task target is ambiguous")
        record = after.record_at(offsets[0])
        prefix, payload = after.payload_parts(record)
        profile = {"flag":"0xe0", "opaque":"0xffffffff", "selector":"0x100",
                   "prefix_bytes":16, "prefix_sha256":_sha(prefix),
                   "target_record_sha256":_sha(bytes.fromhex(record.raw_hex)),
                   "timestamp_be32":record.timestamp_be32}
        audit = self.candidate.audit_dict()
        template = _select_nested_bmp_template(before)
        first = {"ordinal":1, "operation":"place_exact_nested_bmp", "target":self.placement_target_path,
                 "target_record_offset":record.offset, "template_offset":template,
                 "template_provenance":_nested_txt_template_provenance(before, template),
                 "candidate_sha256":self.candidate_blob_sha256, "transaction_sha256":self.transaction_sha256,
                 "growth_bytes":len(after.data)-len(before.data),
                 "expected_added_paths":[self.placement_target_path], "expected_removed_paths":[], "sender_invocations":1}
        operations = envelope.get("operations")
        if type(operations) is not list or len(operations) != 2 or _json(operations[0]) != _json(first):
            raise ValueError("task placement differs from the frozen operation")
        require_nested_placement_provenance(before, operations[0], audit, media_type="bmp")
        # The inverse is independently modeled from candidate bytes. It must
        # produce the precise second transaction and original six write objects.
        from .delete_model import build_one_nested_file_delete_model
        from .new_txt import _build_transaction, _read_verified_object
        inverse = build_one_nested_file_delete_model(after, self.placement_target_path, record.offset)
        tx = self.candidate.transaction
        original_fixed = tuple(_read_verified_object(self.before_backup, f"0x{c:04x}:response-{c:04x}")
                               for c in range(0x1b,0x20))
        inverse_tx = _build_transaction(inverse.candidate_blob, (b"".join(original_fixed[:4]), original_fixed[4]))
        second = {"ordinal":2, "operation":"delete_same_nested_bmp", "target":self.placement_target_path,
                  "target_record_offset":record.offset, "candidate_sha256":_sha(inverse.candidate_blob),
                  "transaction_sha256":inverse_tx.concatenated_sha256,
                  "expected_added_paths":[], "expected_removed_paths":[self.placement_target_path], "sender_invocations":1}
        expected_objects = {"0x8004:backup-blob": self.candidate_blob_sha256,
                            "0x001f:response-001f": _sha(tx.ranges[1])}
        expected_objects.update({f"0x{c:04x}:response-{c:04x}": _sha(tx.ranges[0][i*64:(i+1)*64])
                                 for i,c in enumerate(range(0x1b,0x1f))})
        if (inverse.candidate_blob != before.data
                or _json(operations[1]) != _json(second)
                or envelope.get("baseline_objects") != dict(self.before_backup.object_sha256_by_key)
                or envelope.get("restoration_objects") != dict(self.before_backup.object_sha256_by_key)
                or envelope.get("baseline_state_identity_sha256") != self.baseline_state_identity_sha256
                or envelope.get("restoration_state_identity_sha256") != self.baseline_state_identity_sha256
                or envelope.get("capacity") != self.capacity_response.to_dict()
                or envelope.get("target_record_offset") != record.offset
                or envelope.get("parent_record_offset") != parent_offset
                or envelope.get("parent_path") != "\\".join(parent_path)
                or envelope.get("placement_timestamp_be32") != record.timestamp_be32
                or _json(envelope.get("native_profile")) != _json(profile)
                or envelope.get("placement_expected_objects") != expected_objects
                or envelope.get("placement_unpredicted_objects") != ["0x0024:response-0024", "0x8004:backup-blob-probe"]):
            raise ValueError("two-write task state, provenance, profile or inverse differs")


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
        exact = (_disposable_delta(_blob(self.before_backup), _blob(after), self.placement_target_path,
                                   self.placement_media, nested_validation=self.nested_validation)
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
            "fixture": _fixture_dict(self.placement_target_path, self.validation_placement, self.placement_media, nested_validation=self.nested_validation), "post_placement_backup": {
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
            report_format = (f"infocarry-disposable-nested-{self.placement_media}-placement-report-v1" if self.nested_validation
                             else "infocarry-disposable-root-bmp-placement-report-v1"
                             if self.placement_media == "bmp"
                             else "infocarry-disposable-root-txt-placement-report-v1")
            _write_json(path, {"format": report_format,
                "experiment_id": ("P18-051" if self.placement_media == "bmp" else "P18-049") if self.nested_validation else ("P18-047" if self.placement_target_path == "root\\IC_P18_047_DELETE_B.bmp" else "P18-046") if self.placement_media == "bmp" else "P18-045" if self.placement_target_path == "root\\IC_P18_045_DELETE_C.txt" else "P18-044",
                "status": "completed_and_independently_verified",
                "operation": "separate_fixture_placement", "fixture": _fixture_dict(self.placement_target_path, True, self.placement_media, nested_validation=self.nested_validation),
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
            expected_format = (f"infocarry-disposable-nested-{self.placement_media}-placement-report-v1" if self.nested_validation
                               else "infocarry-disposable-root-bmp-placement-report-v1"
                               if self.placement_media == "bmp"
                               else "infocarry-disposable-root-txt-placement-report-v1")
            if (report.get("format") != expected_format
                    or report.get("fixture") != _fixture_dict(self.placement_target_path, True, self.placement_media, nested_validation=self.nested_validation)
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
        self._task_binding = None

    def bind_task(self, envelope, *, source_head, placement_result=None):
        if self._prepared_operation is None or self.owner_approval_accepted:
            raise ValueError("task must bind the current preparation before owner acceptance")
        frozen = _json(envelope)
        self._prepared_operation.require_two_write_task_binding(json.loads(frozen), source_head=source_head, placement_result=placement_result)
        self._task_binding = (self._prepared_operation, frozen, source_head, placement_result)

    def require_task_binding(self):
        bundle = self._prepared_operation
        if bundle is not None and bundle.operation_profile in {DISPOSABLE_NESTED_BMP_PLACEMENT_PROFILE, "vnw-v15-exact-nested-bmp-delete-validation-v1"}:
            binding = self._task_binding
            if binding is None or binding[0] is not bundle:
                raise ValueError("exact two-write BMP task must be bound before owner acceptance")
            bundle.require_two_write_task_binding(json.loads(binding[1]), source_head=binding[2], placement_result=binding[3])

    def authorize_prepared_operation(self, approval_phrase):
        self.require_task_binding()
        return super().authorize_prepared_operation(approval_phrase)

    def discard_prepared_operation(self) -> None:
        self._task_binding = None
        super().discard_prepared_operation()
        self.runtime.close()

    def prepare(self, source_path: Path, *, target_path: str = FIXTURE_PATH,
                device_model: str = "VNW-V15", max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
                validation_placement: bool = False, placement_media: str = "txt",
                nested_validation: bool = False):
        if self.stop_approved_rebuild():
            raise LibraryTransferExecutionError("approved operation cannot refresh or adopt a new candidate", stage="owner_authorization")
        try:
            if self._prepared_operation is not None:
                raise ValueError("discard the previous operation before preparing another")
            if device_model != "VNW-V15":
                raise ValueError("only VNW-V15 placement is admitted")
            filename, payload = _placement_fixture(target_path, validation_placement, placement_media, nested_validation=nested_validation)
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
            root = Path(runtime.evidence_namespace).expanduser().resolve() / (f"prepared-root-{placement_media}-" + uuid4().hex)
            root.mkdir(parents=True)
            before = capture_and_verify_fresh_backup(root / "backup-baseline", runtime.capture)
            if before.device_identity != ("0x054c", "0x001e"):
                raise ValueError("backup is not VNW-V15")
            runtime.assert_same_session(runtime.session_binding_token)
            baseline_blob = _blob(before)
            parsed = parse_backup_blob(baseline_blob)
            template_extension = placement_media
            templates = [offset for offset in parsed.paths if parsed.record_at(offset).kind == "file" and parsed.record_at(offset).extension.lower() == template_extension]
            if nested_validation:
                _nested_parent(parsed, target_path)
                templates = [(_select_nested_bmp_template if placement_media == "bmp" else _select_nested_txt_template)(parsed)]
            elif validation_placement and placement_media == "txt":
                templates = [offset for offset in templates if parsed.paths[offset][:-1] == ("root",)
                             and parsed.record_at(offset).extension == "txt"
                             and parsed.record_at(offset).flag in (0x20, 0xE0)
                             and parsed.record_at(offset).field_14_be32 == 0x200]
            elif validation_placement and placement_media == "bmp":
                from .backup_format import BackupFormatError
                from .prepared_media_package import validate_bmp_payload
                from .prepared_media_package import PreparedMediaPackageError
                eligible = []
                for offset in templates:
                    record = parsed.record_at(offset)
                    try:
                        prefix, template_payload = parsed.payload_parts(record)
                        validate_bmp_payload(template_payload)
                    except (BackupFormatError, PreparedMediaPackageError):
                        continue
                    if (record.flag == 0xE0 and record.field_14_be32 == 0x100
                            and record.payload_prefix_length == 16 and prefix == b"\xff" * 16):
                        eligible.append(offset)
                if eligible:
                    # Restrict to one captured record profile. Opaque BMP
                    # fields must agree before choosing the first stable template.
                    signatures = {(parsed.record_at(o).flag,
                                   bytes.fromhex(parsed.record_at(o).raw_hex)[1:4],
                                   parsed.record_at(o).field_10_be32,
                                   parsed.record_at(o).field_14_be32,
                                   parsed.payload_parts(parsed.record_at(o))[0]) for o in eligible}
                    if len(signatures) != 1:
                        raise ValueError("baseline BMP templates have ambiguous native record fields")
                    templates = eligible
                else:
                    templates = []
            if not templates:
                raise ValueError(f"baseline has no eligible ordinary {placement_media.upper()} template")
            if validation_placement and not nested_validation:
                _absent_disposable_target(parsed, filename)
            source_copy = root / filename
            with source_copy.open("xb") as output:
                output.write(source.read_bytes())
            timestamp = runtime.new_record_timestamp_be32()
            if nested_validation:
                parent_path, parent_offset = _nested_parent(parsed, target_path)
                builder = build_new_nested_bmp_add if placement_media == "bmp" else build_new_nested_txt_add
                result = builder(before.directory, source_copy, filename,
                    target_directory_path=parent_path, target_directory_offset=parent_offset,
                    source_template_offset=templates[0], available_capacity_bytes=capacity.capacity_limit_bytes-len(baseline_blob),
                    record_timestamp_be32=timestamp)
            elif placement_media == "bmp":
                result = build_new_root_bmp_add(before.directory, source_copy, filename,
                    source_template_offset=templates[0], available_capacity_bytes=capacity.capacity_limit_bytes-len(baseline_blob),
                    record_timestamp_be32=timestamp)
            else:
                result = build_new_root_txt_add(before.directory, source_copy, filename,
                    source_template_offset=templates[0], available_capacity_bytes=capacity.capacity_limit_bytes-len(baseline_blob),
                    record_timestamp_be32=timestamp, fresh_new_allocation=validation_placement)
            if validation_placement:
                _disposable_delta(baseline_blob, result.candidate_blob, target_path, placement_media, nested_validation=nested_validation)
            else:
                _exact_delta(baseline_blob, result.candidate_blob)
            capacity.bind_model_lengths(len(baseline_blob), len(result.candidate_blob))
            candidate_path = root / "candidate.bin"
            with candidate_path.open("xb") as output:
                output.write(result.candidate_blob)
            transaction_directory = root / "transaction"
            result.transaction.preserve(transaction_directory, source=f"disposable-root-{placement_media}-placement" if validation_placement else "exact-root-txt-placement")
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
                profile_id=(DISPOSABLE_NESTED_BMP_PLACEMENT_PROFILE if placement_media == "bmp" else DISPOSABLE_NESTED_TXT_PLACEMENT_PROFILE) if nested_validation else DISPOSABLE_ROOT_BMP_PLACEMENT_PROFILE if validation_placement and placement_media == "bmp"
                else DISPOSABLE_ROOT_TXT_PLACEMENT_PROFILE if validation_placement else ROOT_TXT_PLACEMENT_PROFILE))
            seal_path = root / "operation-bundle.json"
            from dataclasses import replace
            provisional = RootTxtPlacementBundle(runtime,before,capacity,candidate,authorization,
                OperationArtifact.file(source_copy), OperationArtifact.file(candidate_path),
                OperationArtifact.file(capacity_path), OperationArtifact.backup_manifest(before.directory),
                OperationArtifact(str(seal_path), "0"*64, "file_bytes", 0),
                transaction_directory,b"", "0"*64,runtime.session_binding_token,None,
                placement_target_path=target_path, validation_placement=validation_placement,
                placement_media=placement_media, nested_validation=nested_validation)
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
            self.require_task_binding()
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
