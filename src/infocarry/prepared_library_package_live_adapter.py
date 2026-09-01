"""Isolated P17-005 execution boundary for one Library package.

This module is intentionally absent from the normal CLI and GUI import graph.
It is a thin adapter around the reviewed P17-003 Library bridge, the existing
multi-package read-back verifier, and :class:`AuthorizedWriteSender`.  It does
not open USB merely by being imported.  Callers must inject every detection,
capacity, backup, and write boundary; host tests inject fakes only.

The supported operation is exactly the P17-004 profile: one explicitly
imported Library package, destination ``IC_P17_LIBRARY_20260831_03``, and
ordered TXT/BMP/TXT children.  The adapter is a future execution boundary,
not a product transfer API and not a claim of physical compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional

from .backup_format import ParsedBackupBlob
from .backup_state_identity import (
    BackupStateIdentity,
    compare_verified_backups,
    derive_backup_state_identity,
)
from .capacity_evidence import NativeCapacityResponse
from .library import LibraryCatalog
from .prepared_library_package_bridge import (
    P17_003_CONFIRMATION_PHRASE,
    P17_003_TEMPLATE_FOLDER_PATH,
    P17_003_TEMPLATE_ITEM_PATHS,
    PreparedLibraryPackageAuthorization,
    PreparedLibraryPackageBridgeError,
    PreparedLibraryPackageCandidate,
    PreparedLibraryPackagePreflight,
    authorize_prepared_library_package,
    build_prepared_library_package_candidate,
    prepare_prepared_library_package_preflight,
)
from .prepared_package_multi_verify import (
    PreparedMultiPackageReadback,
    verify_prepared_multi_package_readback,
)
from .protocol import TransferCancelledError
from .write_gate import (
    DEFAULT_MAX_AGE_SECONDS,
    VerifiedBackup,
    capture_and_verify_fresh_backup,
    verify_fresh_backup,
)
from .write_protocol import (
    WriteBackend,
    WriteFailureAssessment,
    WritePolicy,
    assess_write_failure,
)
from .write_artifact import ProspectiveWriteTransaction


P17_005_TARGET_FOLDER = "IC_P17_LIBRARY_20260831_03"
P17_005_DEVICE_IDENTITY = (0x054C, 0x001E)
P17_005_PROFILE = "one_selected_library_item_root_txt_bmp_txt"
P17_005_OWNER_APPROVAL = "APPROVE P17-003 MODERN LIBRARY PACKAGE SMOKE 01"
P17_005_CONFIRMATION = P17_003_CONFIRMATION_PHRASE
P17_005_RUNNER_FORMAT = "infocarry-p17-005-library-package-live-adapter-v1"
P17_005_EVIDENCE_MANIFEST_FORMAT = (
    "infocarry-p17-005-library-package-evidence-manifest-v1"
)
P17_005_SUCCESS_SEQUENCE = (
    "live_preflight_seal_verified",
    "owner_approval",
    "confirmation_phrase",
    "device_revalidated",
    "capacity_revalidated",
    "sealed_preflight_backup_revalidated",
    "fresh_pre_transaction_backup_verified",
    "library_candidate_reconstructed",
    "authorization_revalidated",
    "single_0x101b_transaction",
    "completion_0x0000",
    "fresh_post_operation_backup_verified",
    "independent_readback_verification",
    "versioned_before_after_evidence_manifest_verified",
)

ProgressCallback = Callable[[str, int, int], None]
CancelledCallback = Callable[[], bool]
CaptureCallback = Callable[..., None]
DetectDeviceCallback = Callable[[], tuple[int, int]]
CapacityQueryCallback = Callable[[], NativeCapacityResponse]
PreviewCallback = Callable[[Mapping[str, Any]], None]
Clock = Callable[[], float]


class PreparedLibraryPackageLiveAdapterError(RuntimeError):
    """Terminal adapter error; an indeterminate operation is never retried."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        state: str,
        write_started: bool = False,
        audit: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.state = state
        self.write_started = write_started
        self.automatic_retry_allowed = False
        self.audit = dict(audit or {})
        self.audit.setdefault("automatic_retry_allowed", False)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(child) for child in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw(child) for child in value]
    return value


def _json_equivalent(left: Any, right: Any) -> bool:
    """Compare report values after the tuple/list JSON boundary."""

    return _canonical_json(left) == _canonical_json(right)


def _audit_without_seal(audit: Mapping[str, Any]) -> dict[str, Any]:
    """Return the complete outer report covered by the live seal."""

    value = _thaw(audit)
    if not isinstance(value, dict):
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-005 live preflight report is malformed",
            stage="preflight_seal",
            state="failed",
        )
    value.pop("preflight_seal_sha256", None)
    return value


def _sealed_backup_dict(backup: VerifiedBackup) -> dict[str, Any]:
    result = backup.to_dict()
    # Verification time is an observation about this process, not device
    # state.  Excluding it makes a sealed backup replayable without changing
    # any captured object or manifest bytes.
    result.pop("verified_at_utc", None)
    return result


def _backup_identity(backup: VerifiedBackup) -> BackupStateIdentity:
    """Return canonical raw state identity, excluding capture provenance."""

    return derive_backup_state_identity(backup)


def _candidate_comparison_view(
    candidate: PreparedLibraryPackageCandidate | Mapping[str, Any],
) -> dict[str, Any]:
    """Return candidate bindings with only archive provenance removed.

    Candidate bytes and transactions remain compared exactly.  The sole
    omitted candidate field is the baseline archive's manifest hash: it is a
    provenance binding that can differ when the same raw state is captured
    into a new archive.  The complete backup reports and the state-identity
    comparison remain separately preserved in the operation audit.
    """

    source = (
        candidate.audit_dict()
        if isinstance(candidate, PreparedLibraryPackageCandidate)
        else candidate
    )
    value = json.loads(json.dumps(source, ensure_ascii=True))
    baseline = value.get("baseline")
    if isinstance(baseline, dict):
        baseline.pop("manifest_sha256", None)
    return value


def _require_reconstructed_candidate_matches(
    sealed: PreparedLibraryPackageCandidate,
    current: PreparedLibraryPackageCandidate,
) -> None:
    if current.candidate_blob != sealed.candidate_blob:
        raise ValueError("rebuilt Library candidate bytes differ from sealed preflight")
    if current.transaction != sealed.transaction:
        raise ValueError("rebuilt Library transaction differs from sealed preflight")
    if _candidate_comparison_view(current) != _candidate_comparison_view(sealed):
        raise ValueError(
            "rebuilt Library candidate differs from sealed preflight outside backup provenance"
        )


def _authorization_comparison_view(
    authorization: Mapping[str, Any] | PreparedLibraryPackageAuthorization,
) -> dict[str, Any]:
    """Compare authorization bindings without the fresh archive provenance hash."""

    source = (
        authorization.to_dict()
        if isinstance(authorization, PreparedLibraryPackageAuthorization)
        else authorization
    )
    value = json.loads(json.dumps(source, ensure_ascii=True))
    value.pop("baseline_manifest_sha256", None)
    return value


def _backup_report_matches(backup: VerifiedBackup, report: Any) -> bool:
    if not isinstance(report, Mapping):
        return False
    normalized = dict(report)
    normalized.pop("verified_at_utc", None)
    return _json_equivalent(normalized, _sealed_backup_dict(backup))


def _validate_result_audit(
    result_audit: Mapping[str, Any],
    *,
    preflight: PreparedLibraryPackageLivePreflight,
    before_backup: VerifiedBackup,
    after_backup: VerifiedBackup,
) -> dict[str, Any]:
    """Require the complete hash-only success record for the manifest."""

    value = _thaw(result_audit)
    if not isinstance(value, dict):
        raise PreparedLibraryPackageLiveAdapterError(
            "result_audit must be a JSON object",
            stage="evidence_manifest",
            state="failed",
        )
    required = {
        "format",
        "state",
        "profile",
        "device_identity",
        "expected_folder_name",
        "usb_transmission_performed",
        "device_changing_operation_performed",
        "preflight_seal_sha256",
        "backup_state_comparison",
        "candidate",
        "authorization",
        "completion",
        "verification",
        "workflow",
    }
    if not required.issubset(value):
        missing = sorted(required - set(value))
        raise PreparedLibraryPackageLiveAdapterError(
            f"result_audit is missing required fields: {missing}",
            stage="evidence_manifest",
            state="failed",
        )
    allowed_top_level = required
    unexpected = sorted(set(value) - allowed_top_level)
    if unexpected:
        raise PreparedLibraryPackageLiveAdapterError(
            f"result_audit contains unexpected fields: {unexpected}",
            stage="evidence_manifest",
            state="failed",
        )
    if (
        value["format"] != P17_005_RUNNER_FORMAT
        or value["state"] != "readback_verified"
        or value["profile"] != P17_005_PROFILE
        or value["device_identity"] != list(_expected_device_hex())
        or value["expected_folder_name"] != preflight.expected_folder_name
        or value["usb_transmission_performed"] is not True
        or value["device_changing_operation_performed"] is not True
        or value["preflight_seal_sha256"] != preflight.seal_sha256
        or value["completion"] != "0x0000"
    ):
        raise PreparedLibraryPackageLiveAdapterError(
            "result_audit does not describe the exact verified P17-005 success",
            stage="evidence_manifest",
            state="failed",
        )
    candidate = value["candidate"]
    candidate_details = (
        candidate.get("candidate") if isinstance(candidate, Mapping) else None
    )
    transaction_details = (
        candidate.get("transaction") if isinstance(candidate, Mapping) else None
    )
    if not isinstance(candidate_details, Mapping) or not isinstance(
        transaction_details, Mapping
    ) or (
        candidate_details.get("blob_sha256")
        != preflight.candidate.candidate_blob_sha256
        or transaction_details.get("sha256")
        != preflight.candidate.transaction_sha256
    ):
        raise PreparedLibraryPackageLiveAdapterError(
            "result_audit candidate hashes do not match the sealed preflight",
            stage="evidence_manifest",
            state="failed",
        )
    if _candidate_comparison_view(candidate) != _candidate_comparison_view(
        preflight.candidate
    ):
        raise PreparedLibraryPackageLiveAdapterError(
            "result_audit candidate is not the sealed candidate outside backup provenance",
            stage="evidence_manifest",
            state="failed",
        )
    try:
        expected_state_comparison = compare_verified_backups(
            preflight.before_backup,
            before_backup,
        ).to_dict()
    except Exception as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"result_audit backup-state comparison could not be verified: {exc}",
            stage="evidence_manifest",
            state="failed",
        ) from exc
    if not _json_equivalent(
        value["backup_state_comparison"], expected_state_comparison
    ):
        raise PreparedLibraryPackageLiveAdapterError(
            "result_audit backup-state comparison is not the verified raw/provenance audit",
            stage="evidence_manifest",
            state="failed",
        )
    authorization = value["authorization"]
    if not isinstance(authorization, Mapping) or _authorization_comparison_view(
        authorization
    ) != _authorization_comparison_view(preflight.authorization):
        raise PreparedLibraryPackageLiveAdapterError(
            "result_audit authorization is not the sealed authorization outside backup provenance",
            stage="evidence_manifest",
            state="failed",
        )
    verification = value["verification"]
    verification_required = {
        "format",
        "state",
        "success",
        "completion",
        "candidate_blob_sha256",
        "transaction_sha256",
        "before_backup",
        "after_backup",
        "shared_path_count",
        "fixed_state_sha256",
        "details",
        "automatic_retry",
    }
    if not isinstance(verification, Mapping) or set(verification) != verification_required or (
        verification.get("format") != "infocarry-ordered-package-readback-v1"
        or verification.get("state") != "readback_verified"
        or verification.get("success") is not True
        or verification.get("completion") != "0x0000"
        or verification.get("candidate_blob_sha256")
        != preflight.candidate.candidate_blob_sha256
        or verification.get("transaction_sha256")
        != preflight.candidate.transaction_sha256
        or verification.get("automatic_retry") is not False
        or not isinstance(verification.get("shared_path_count"), int)
        or verification.get("shared_path_count") < 0
        or not isinstance(verification.get("fixed_state_sha256"), list)
        or not isinstance(verification.get("details"), Mapping)
        or not _backup_report_matches(
            before_backup,
            verification.get("before_backup"),
        )
        or not _backup_report_matches(
            after_backup,
            verification.get("after_backup"),
        )
    ):
        raise PreparedLibraryPackageLiveAdapterError(
            "result_audit verification is not an exact successful read-back",
            stage="evidence_manifest",
            state="failed",
        )
    workflow = value["workflow"]
    workflow_required = {
        "isolated_one_shot_adapter",
        "sender_calls",
        "automatic_retry_allowed",
        "operation_sequence",
    }
    if not isinstance(workflow, Mapping) or set(workflow) != workflow_required or (
        workflow.get("isolated_one_shot_adapter") is not True
        or workflow.get("sender_calls") != 1
        or workflow.get("automatic_retry_allowed") is not False
        or workflow.get("operation_sequence") != list(P17_005_SUCCESS_SEQUENCE)
    ):
        raise PreparedLibraryPackageLiveAdapterError(
            "result_audit workflow is not a one-shot no-retry result",
            stage="evidence_manifest",
            state="failed",
        )
    encoded = _canonical_json(value)
    if b'"candidate_blob":' in encoded or b'"transaction_bytes":' in encoded:
        raise PreparedLibraryPackageLiveAdapterError(
            "result_audit must not contain candidate or transaction bytes",
            stage="evidence_manifest",
            state="failed",
        )
    return value


def _expected_device_hex() -> tuple[str, str]:
    return tuple(f"0x{value:04x}" for value in P17_005_DEVICE_IDENTITY)


def _validate_callbacks(
    *,
    detect_device: Optional[DetectDeviceCallback],
    query_capacity: Optional[CapacityQueryCallback],
    capture: Optional[CaptureCallback],
    preview_callback: Optional[PreviewCallback] = None,
) -> None:
    callbacks = (
        (detect_device, "detect_device"),
        (query_capacity, "query_capacity"),
        (capture, "capture"),
    )
    if preview_callback is not None:
        callbacks += ((preview_callback, "preview_callback"),)
    for callback, label in callbacks:
        if callback is None or not callable(callback):
            raise PreparedLibraryPackageLiveAdapterError(
                f"P17-005 requires {label}",
                stage="preflight",
                state="failed",
            )


def _validate_expected_folder(expected_folder_name: str) -> None:
    if expected_folder_name != P17_005_TARGET_FOLDER:
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-005 destination is fixed to the reviewed P17-004 folder",
            stage="package",
            state="failed",
        )


def _seal_payload(
    *,
    core: PreparedLibraryPackagePreflight,
    expected_folder_name: str,
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "format": P17_005_RUNNER_FORMAT,
        "profile": P17_005_PROFILE,
        "device_identity": list(_expected_device_hex()),
        "expected_folder_name": expected_folder_name,
        "core_preflight_seal_sha256": core.seal_sha256,
        "core_preflight": core.to_dict(),
        "audit": _audit_without_seal(audit),
        "owner_approval_phrase": P17_005_OWNER_APPROVAL,
        "confirmation_phrase": P17_005_CONFIRMATION,
        "automatic_retry_allowed": False,
        "normal_gui_cli_transfer_exposed": False,
    }


def _seal_sha256(
    *,
    core: PreparedLibraryPackagePreflight,
    expected_folder_name: str,
    audit: Mapping[str, Any],
) -> str:
    return _sha256(
        _canonical_json(
            _seal_payload(
                core=core,
                expected_folder_name=expected_folder_name,
                audit=audit,
            )
        )
    )


@dataclass(frozen=True)
class PreparedLibraryPackageLivePreflight:
    """Fresh hash-bound preflight for the later one-shot boundary."""

    core: PreparedLibraryPackagePreflight
    expected_folder_name: str
    seal_sha256: str
    audit: Mapping[str, Any]

    def __post_init__(self) -> None:
        _validate_expected_folder(self.expected_folder_name)
        object.__setattr__(self, "audit", _freeze(self.audit))

    @property
    def candidate(self) -> PreparedLibraryPackageCandidate:
        return self.core.candidate

    @property
    def authorization(self) -> PreparedLibraryPackageAuthorization:
        return self.core.authorization

    @property
    def before_backup(self) -> VerifiedBackup:
        return self.core.before_backup

    @property
    def capacity_response(self) -> NativeCapacityResponse:
        return self.core.capacity_response

    @property
    def template(self) -> ParsedBackupBlob:
        return self.core.template

    def verify_seal(self) -> None:
        try:
            self.core.verify_seal()
        except PreparedLibraryPackageBridgeError as exc:
            raise PreparedLibraryPackageLiveAdapterError(
                f"P17-005 core preflight seal failed: {exc}",
                stage="preflight_seal",
                state="failed",
            ) from exc
        report = _thaw(self.audit)
        if not isinstance(report, dict):
            raise PreparedLibraryPackageLiveAdapterError(
                "P17-005 live preflight report is malformed",
                stage="preflight_seal",
                state="failed",
            )
        try:
            expected_state_identity = _backup_identity(self.core.before_backup)
        except Exception as exc:
            raise PreparedLibraryPackageLiveAdapterError(
                f"P17-005 sealed backup state identity could not be verified: {exc}",
                stage="preflight_seal",
                state="failed",
            ) from exc
        if (
            report.get("preflight_seal_sha256") != self.seal_sha256
            or report.get("core_preflight_seal_sha256") != self.core.seal_sha256
            or report.get("backup_state_identity")
            != expected_state_identity.to_dict()
            or report.get("backup_state_identity_sha256")
            != expected_state_identity.sha256
            or not _json_equivalent(
                report.get("candidate"), self.core.candidate.audit_dict()
            )
            or not _json_equivalent(
                report.get("authorization"), self.core.authorization.to_dict()
            )
            or not _json_equivalent(
                report.get("before_backup"), _sealed_backup_dict(self.core.before_backup)
            )
            or not _json_equivalent(
                report.get("capacity_response"), self.core.capacity_response.to_dict()
            )
        ):
            raise PreparedLibraryPackageLiveAdapterError(
                "P17-005 live preflight report bindings were modified",
                stage="preflight_seal",
                state="failed",
            )
        actual = _seal_sha256(
            core=self.core,
            expected_folder_name=self.expected_folder_name,
            audit=self.audit,
        )
        if actual != self.seal_sha256:
            raise PreparedLibraryPackageLiveAdapterError(
                "P17-005 live preflight seal was modified",
                stage="preflight_seal",
                state="failed",
            )

    def to_dict(self) -> dict[str, Any]:
        return _thaw(self.audit)


@dataclass(frozen=True)
class PreparedLibraryPackageLiveResult:
    preflight: PreparedLibraryPackageLivePreflight
    candidate: PreparedLibraryPackageCandidate
    authorization: PreparedLibraryPackageAuthorization
    before_backup: VerifiedBackup
    after_backup: VerifiedBackup
    completion: int
    verification: PreparedMultiPackageReadback
    audit: Mapping[str, Any]


def _failure(
    message: str,
    *,
    stage: str,
    state: str,
    sequence: list[str],
    sender_calls: int = 0,
    write_started: bool = False,
    candidate: Optional[PreparedLibraryPackageCandidate] = None,
    authorization: Optional[PreparedLibraryPackageAuthorization] = None,
    primary_error: Optional[str] = None,
) -> PreparedLibraryPackageLiveAdapterError:
    audit: dict[str, Any] = {
        "format": P17_005_RUNNER_FORMAT,
        "state": state,
        "stage": stage,
        "write_started": write_started,
        "device_change": (
            "indeterminate_after_transaction_start"
            if write_started
            else "none_started"
        ),
        "automatic_retry_allowed": False,
        "operation_sequence": list(sequence),
    }
    audit["sender_calls"] = sender_calls
    if primary_error is not None:
        audit["primary_error"] = primary_error
    if candidate is not None:
        audit["candidate"] = candidate.audit_dict()
    if authorization is not None:
        audit["authorization"] = authorization.to_dict()
    return PreparedLibraryPackageLiveAdapterError(
        f"{message}; no automatic retry is allowed",
        stage=stage,
        state=state,
        write_started=write_started,
        audit=audit,
    )


def prepare_prepared_library_package_live_preflight(
    *,
    catalog: LibraryCatalog,
    selected_item_id: str,
    backup_destination: Path,
    template: ParsedBackupBlob,
    new_record_timestamp_be32: int,
    expected_folder_name: str = P17_005_TARGET_FOLDER,
    detect_device: DetectDeviceCallback,
    query_capacity: CapacityQueryCallback,
    capture: CaptureCallback,
    preview_callback: PreviewCallback,
    cancelled: Optional[CancelledCallback] = None,
    progress: Optional[ProgressCallback] = None,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> PreparedLibraryPackageLivePreflight:
    """Run and seal the required fresh, read-only injected preflight.

    The order is fixed: cancellation check, expected-device detection, native
    capacity response, complete backup capture/verification, Library/package
    reconstruction, hash-only preview, then sealing.  No sender is accepted or
    called here.
    """

    _validate_expected_folder(expected_folder_name)
    _validate_callbacks(
        detect_device=detect_device,
        query_capacity=query_capacity,
        capture=capture,
        preview_callback=preview_callback,
    )
    sequence = ["read_only_preflight"]
    try:
        if cancelled is not None and cancelled():
            raise TransferCancelledError("P17-005 preflight was cancelled")
        detected = detect_device()
        if detected != P17_005_DEVICE_IDENTITY:
            raise ValueError("detected device is not Sony 0x054c:0x001e")
        sequence.append("expected_device_detected")
        capacity = query_capacity()
        if not isinstance(capacity, NativeCapacityResponse):
            raise ValueError("capacity query did not return parsed native 0x0019 evidence")
        if capacity.device_identity != detected:
            raise ValueError("capacity response identity differs from detected device")
        sequence.append("fresh_capacity_queried_0x0019")
    except TransferCancelledError as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            str(exc),
            stage="preflight",
            state="cancelled_before_transaction",
            audit={"operation_sequence": sequence},
        ) from exc
    except Exception as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"P17-005 read-only detection/capacity preflight failed: {exc}",
            stage="capacity_query",
            state="failed",
            audit={"operation_sequence": sequence},
        ) from exc

    try:
        before = capture_and_verify_fresh_backup(
            Path(backup_destination),
            lambda destination: capture(
                destination,
                cancelled=cancelled,
                progress=progress,
            ),
            now=now,
            max_age_seconds=max_age_seconds,
        )
        if before.device_identity != _expected_device_hex():
            raise ValueError("fresh backup identity differs from Sony 0x054c:0x001e")
        sequence.append("fresh_complete_backup_verified")
    except Exception as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"P17-005 fresh backup preflight failed: {exc}",
            stage="fresh_backup",
            state="failed",
            audit={"operation_sequence": sequence},
        ) from exc

    try:
        core = prepare_prepared_library_package_preflight(
            catalog,
            selected_item_id,
            before,
            template,
            new_record_timestamp_be32=new_record_timestamp_be32,
            native_capacity_response=capacity,
            template_folder_path=P17_003_TEMPLATE_FOLDER_PATH,
            template_item_paths=P17_003_TEMPLATE_ITEM_PATHS,
        )
        if core.candidate.library_binding.get("folder_name") != expected_folder_name:
            raise ValueError("selected Library package differs from the exact P17-004 destination")
        preview_callback(core.candidate.audit_dict())
        sequence.extend(["library_candidate_reconstructed", "hash_only_preview_presented"])
    except Exception as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"P17-005 Library candidate preflight failed: {exc}",
            stage="candidate",
            state="failed",
            audit={"operation_sequence": sequence},
        ) from exc

    sequence.append("live_preflight_sealed")
    audit = {
        "format": P17_005_RUNNER_FORMAT,
        "state": "ready_for_hardware_test_host_only",
        "profile": P17_005_PROFILE,
        "device_identity": list(_expected_device_hex()),
        "expected_folder_name": expected_folder_name,
        "read_only_preflight": True,
        "hardware_accessed": False,
        "usb_transmission_performed": False,
        "device_changing_operation_performed": False,
        "target_absent_from_fresh_backup": True,
        "core_preflight_seal_sha256": core.seal_sha256,
        "backup_state_identity": _backup_identity(before).to_dict(),
        "backup_state_identity_sha256": _backup_identity(before).sha256,
        "candidate": core.candidate.audit_dict(),
        "authorization": core.authorization.to_dict(),
        "before_backup": _sealed_backup_dict(before),
        "capacity_response": capacity.to_dict(),
        "operation_sequence": sequence,
        "owner_approval_phrase": P17_005_OWNER_APPROVAL,
        "confirmation_phrase": P17_005_CONFIRMATION,
        "automatic_retry_allowed": False,
        "normal_gui_cli_transfer_exposed": False,
        "send_count": 0,
    }
    seal = _seal_sha256(
        core=core,
        expected_folder_name=expected_folder_name,
        audit=audit,
    )
    audit["preflight_seal_sha256"] = seal
    return PreparedLibraryPackageLivePreflight(
        core=core,
        expected_folder_name=expected_folder_name,
        seal_sha256=seal,
        audit=audit,
    )


def execute_prepared_library_package_live(
    preflight: PreparedLibraryPackageLivePreflight,
    *,
    catalog: LibraryCatalog,
    selected_item_id: str,
    backup_destination: Path,
    execution_template: Optional[ParsedBackupBlob] = None,
    post_operation_destination: Path,
    evidence_manifest_destination: Path,
    owner_approval: str,
    confirmation: str,
    detect_device: DetectDeviceCallback,
    query_capacity: CapacityQueryCallback,
    backend: WriteBackend,
    bulk_out_endpoint: int,
    capture: CaptureCallback,
    policy: WritePolicy = WritePolicy(),
    clock: Clock = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    cancelled: Optional[CancelledCallback] = None,
    progress: Optional[ProgressCallback] = None,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> PreparedLibraryPackageLiveResult:
    """Execute exactly one approved transaction after sealed revalidation.

    A new complete backup is captured and verified immediately before the
    sender call.  The Library catalog, package, source files, candidate,
    capacity, and authorization are rebuilt from that fresh backup and must
    remain byte-for-byte equivalent to the sealed preview. Any post-start
    failure is terminal and indeterminate; this function has no retry or
    corrective-write path.
    """

    if not isinstance(preflight, PreparedLibraryPackageLivePreflight):
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-005 requires a sealed live preflight",
            stage="preflight",
            state="failed",
        )
    _validate_callbacks(
        detect_device=detect_device,
        query_capacity=query_capacity,
        capture=capture,
    )
    sequence = ["live_preflight_seal_verified"]
    sender_calls = 0
    try:
        preflight.verify_seal()
    except PreparedLibraryPackageLiveAdapterError:
        raise

    if owner_approval != P17_005_OWNER_APPROVAL:
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-005 owner approval phrase was not accepted; no transaction attempted",
            stage="approval",
            state="failed",
        )
    if confirmation != P17_005_CONFIRMATION:
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-005 confirmation phrase was not accepted; no transaction attempted",
            stage="approval",
            state="failed",
        )
    sequence.extend(["owner_approval", "confirmation_phrase"])

    if cancelled is not None and cancelled():
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-005 execution cancelled before fresh pre-write backup",
            stage="pre_transaction",
            state="cancelled_before_transaction",
            audit={"operation_sequence": sequence},
        )

    try:
        detected = detect_device()
        if detected != P17_005_DEVICE_IDENTITY:
            raise ValueError("detected device is not Sony 0x054c:0x001e")
        capacity = query_capacity()
        if not isinstance(capacity, NativeCapacityResponse):
            raise ValueError("capacity query did not return parsed native 0x0019 evidence")
        if capacity != preflight.capacity_response:
            raise ValueError("fresh 0x0019 capacity response differs from sealed preflight")
        sequence.extend(["device_revalidated", "capacity_revalidated"])
        sealed_before = verify_fresh_backup(
            preflight.before_backup.directory,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        if _backup_identity(sealed_before) != _backup_identity(preflight.before_backup):
            raise ValueError("sealed preflight backup changed before execution")
        sequence.append("sealed_preflight_backup_revalidated")
        before = capture_and_verify_fresh_backup(
            Path(backup_destination),
            lambda destination: capture(
                destination,
                cancelled=cancelled,
                progress=progress,
            ),
            now=now,
            max_age_seconds=max_age_seconds,
        )
        if before.device_identity != _expected_device_hex():
            raise ValueError("fresh pre-write backup identity differs from Sony 0x054c:0x001e")
        if _backup_identity(before) != _backup_identity(preflight.before_backup):
            raise ValueError("fresh pre-write backup differs from the sealed baseline")
        sequence.append("fresh_pre_transaction_backup_verified")
    except Exception as exc:
        raise _failure(
            f"P17-005 pre-send device/backup revalidation failed: {exc}",
            stage="preflight_revalidation",
            state="failed",
            sequence=sequence,
            sender_calls=sender_calls,
            primary_error=str(exc),
        ) from exc

    template = execution_template or preflight.template
    try:
        candidate = build_prepared_library_package_candidate(
            catalog,
            selected_item_id,
            before,
            template,
            new_record_timestamp_be32=preflight.core.new_record_timestamp_be32,
            native_capacity_response=capacity,
            template_folder_path=preflight.core.template_folder_path,
            template_item_paths=preflight.core._paths(),
        )
        if candidate.library_binding.get("folder_name") != preflight.expected_folder_name:
            raise ValueError("selected Library destination differs from sealed preflight")
        _require_reconstructed_candidate_matches(preflight.candidate, candidate)
        authorization = authorize_prepared_library_package(
            candidate,
            confirmation=confirmation,
        )
        authorization.require_same_candidate(candidate)
        sequence.extend(["library_candidate_reconstructed", "authorization_revalidated"])
    except Exception as exc:
        raise _failure(
            f"P17-005 Library candidate revalidation failed: {exc}",
            stage="candidate_revalidation",
            state="failed",
            sequence=sequence,
            sender_calls=sender_calls,
            primary_error=str(exc),
        ) from exc

    try:
        if cancelled is not None and cancelled():
            raise TransferCancelledError(
                "P17-005 execution cancelled before transaction start"
            )
    except TransferCancelledError as exc:
        raise _failure(
            str(exc),
            stage="pre_transaction",
            state="cancelled_before_transaction",
            sequence=sequence,
            sender_calls=sender_calls,
            candidate=candidate,
            authorization=authorization,
        ) from exc

    try:
        if not all(
            hasattr(backend, name)
            for name in ("control_out", "control_in", "bulk_write")
        ):
            raise PreparedLibraryPackageLiveAdapterError(
                "P17-005 requires a write backend at the approved boundary",
                stage="sender",
                state="failed",
            )
        from .write_protocol import AuthorizedWriteSender as _AuthorizedWriteSender

        sender_impl = _AuthorizedWriteSender(
            backend,
            bulk_out_endpoint,
            policy=policy,
            clock=clock,
            sleep=sleep,
        )

        class BoundAuthorization:
            """Execution-local authorization created only after all gates."""

            def revalidate(self, transaction: ProspectiveWriteTransaction) -> None:
                if transaction != candidate.transaction:
                    raise PreparedLibraryPackageLiveAdapterError(
                        "sender transaction differs from the sealed Library candidate",
                        stage="authorization",
                        state="failed",
                    )
                authorization.require_same_candidate(candidate)
                authorization.core.revalidate(
                    candidate.core,
                    now=now,
                    max_age_seconds=max_age_seconds,
                )

        def send_once() -> int:
            nonlocal sender_calls
            if sender_calls:
                raise PreparedLibraryPackageLiveAdapterError(
                    "P17-005 sender is one-shot; a second transaction is refused",
                    stage="write_guard",
                    state="failed",
                )
            sender_calls = 1
            return sender_impl.send(
                candidate.transaction,
                BoundAuthorization(),
                cancelled=cancelled,
                progress=progress,
            )

        completion = send_once()
        sequence.append("single_0x101b_transaction")
    except Exception as exc:
        assessment = assess_write_failure(exc)
        if isinstance(exc, TransferCancelledError) and not assessment.write_started:
            raise _failure(
                str(exc),
                stage="pre_transaction",
                state="cancelled_before_transaction",
                sequence=sequence,
                sender_calls=sender_calls,
                write_started=False,
                candidate=candidate,
                authorization=authorization,
            ) from exc
        if not isinstance(
            getattr(exc, "write_failure_assessment", None), WriteFailureAssessment
        ):
            assessment = WriteFailureAssessment(
                primary_error=str(exc),
                write_started=False,
                device_outcome="not_started",
            )
        state = (
            "indeterminate_after_transaction_start"
            if assessment.device_outcome == "indeterminate"
            else "failed"
        )
        raise _failure(
            f"P17-005 transaction stopped: {exc}",
            stage="write",
            state=state,
            sequence=sequence,
            sender_calls=sender_calls,
            write_started=assessment.write_started,
            candidate=candidate,
            authorization=authorization,
            primary_error=assessment.primary_error,
        ) from exc

    if isinstance(completion, bool) or not isinstance(completion, int) or completion != 0:
        value = repr(completion) if not isinstance(completion, int) else f"0x{completion:04x}"
        raise _failure(
            f"P17-005 completion {value} is not 0x0000",
            stage="write_completion",
            state="failed",
            sequence=sequence,
            sender_calls=sender_calls,
            write_started=True,
            candidate=candidate,
            authorization=authorization,
            primary_error=f"completion={value}",
        )
    sequence.append("completion_0x0000")

    try:
        after = capture_and_verify_fresh_backup(
            Path(post_operation_destination),
            lambda destination: capture(
                destination,
                cancelled=cancelled,
                progress=progress,
            ),
            now=now,
            max_age_seconds=max_age_seconds,
        )
        if after.device_identity != _expected_device_hex():
            raise ValueError("post-operation backup identity differs from Sony 0x054c:0x001e")
        sequence.append("fresh_post_operation_backup_verified")
        verification = verify_prepared_multi_package_readback(
            candidate.core,
            after.directory,
            completion=completion,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        sequence.append("independent_readback_verification")

        sequence.append("versioned_before_after_evidence_manifest_verified")
        audit = {
            "format": P17_005_RUNNER_FORMAT,
            "state": "readback_verified",
            "profile": P17_005_PROFILE,
            "device_identity": list(_expected_device_hex()),
            "expected_folder_name": preflight.expected_folder_name,
            "usb_transmission_performed": True,
            "device_changing_operation_performed": True,
            "preflight_seal_sha256": preflight.seal_sha256,
            "backup_state_comparison": compare_verified_backups(
                preflight.before_backup,
                before,
            ).to_dict(),
            "candidate": candidate.audit_dict(),
            "authorization": authorization.to_dict(),
            "completion": "0x0000",
            "verification": verification.to_dict(),
            "workflow": {
                "isolated_one_shot_adapter": True,
                "sender_calls": sender_calls,
                "automatic_retry_allowed": False,
                "operation_sequence": sequence,
            },
        }
        write_prepared_library_package_evidence_manifest(
            evidence_manifest_destination,
            preflight=preflight,
            before_backup=before,
            after_backup=after,
            result_audit=audit,
            now=now,
            max_age_seconds=max_age_seconds,
        )
    except Exception as exc:
        raise _failure(
            f"P17-005 post-operation backup/read-back failed: {exc}",
            stage="post_operation_readback",
            state="indeterminate_after_transaction_start",
            sequence=sequence,
            sender_calls=sender_calls,
            write_started=True,
            candidate=candidate,
            authorization=authorization,
            primary_error=str(exc),
        ) from exc

    return PreparedLibraryPackageLiveResult(
        preflight=preflight,
        candidate=candidate,
        authorization=authorization,
        before_backup=before,
        after_backup=after,
        completion=completion,
        verification=verification,
        audit=audit,
    )


def write_prepared_library_package_evidence_manifest(
    destination: Path,
    *,
    preflight: PreparedLibraryPackageLivePreflight,
    before_backup: VerifiedBackup,
    after_backup: VerifiedBackup,
    result_audit: Mapping[str, Any],
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> Path:
    """Write one non-overwriting, hash-only external evidence manifest.

    The backup callback owns the complete before/after archives. This
    companion manifest requires both verified identities plus the hash-only
    result audit and all operation bindings without copying candidate bytes or
    raw evidence into Git.
    """

    preflight.verify_seal()
    path = Path(destination).expanduser().resolve()
    if path.exists():
        raise PreparedLibraryPackageLiveAdapterError(
            f"refusing to replace existing evidence manifest: {path}",
            stage="evidence_manifest",
            state="failed",
        )
    if not isinstance(before_backup, VerifiedBackup):
        raise PreparedLibraryPackageLiveAdapterError(
            "before_backup must be a verified backup",
            stage="evidence_manifest",
            state="failed",
        )
    if not isinstance(after_backup, VerifiedBackup):
        raise PreparedLibraryPackageLiveAdapterError(
            "after_backup must be a verified backup",
            stage="evidence_manifest",
            state="failed",
        )
    if before_backup.directory == after_backup.directory:
        raise PreparedLibraryPackageLiveAdapterError(
            "before and after evidence backups must be distinct",
            stage="evidence_manifest",
            state="failed",
        )
    try:
        verified_before = verify_fresh_backup(
            before_backup.directory,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        verified_after = verify_fresh_backup(
            after_backup.directory,
            now=now,
            max_age_seconds=max_age_seconds,
        )
    except Exception as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"evidence backup re-verification failed: {exc}",
            stage="evidence_manifest",
            state="failed",
        ) from exc
    if (
        _backup_identity(verified_before) != _backup_identity(before_backup)
        or _backup_identity(verified_after) != _backup_identity(after_backup)
        or _backup_identity(verified_before)
        != _backup_identity(preflight.before_backup)
    ):
        raise PreparedLibraryPackageLiveAdapterError(
            "evidence backups differ from the sealed or preserved state",
            stage="evidence_manifest",
            state="failed",
        )
    validated_result_audit = _validate_result_audit(
        result_audit,
        preflight=preflight,
        before_backup=verified_before,
        after_backup=verified_after,
    )
    if (
        verified_before.device_identity != _expected_device_hex()
        or verified_after.device_identity != _expected_device_hex()
        or not _backup_report_matches(
            verified_before,
            validated_result_audit["verification"].get("before_backup"),
        )
        or not _backup_report_matches(
            verified_after,
            validated_result_audit["verification"].get("after_backup"),
        )
    ):
        raise PreparedLibraryPackageLiveAdapterError(
            "evidence backups do not match the exact verified result audit",
            stage="evidence_manifest",
            state="failed",
        )
    try:
        independently_verified = verify_prepared_multi_package_readback(
            replace(preflight.candidate.core, backup=verified_before),
            verified_after.directory,
            completion=0,
            now=now,
            max_age_seconds=max_age_seconds,
        )
    except Exception as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"independent evidence read-back verification failed: {exc}",
            stage="evidence_manifest",
            state="failed",
        ) from exc
    actual_verification = validated_result_audit["verification"]
    expected_verification = independently_verified.to_dict()
    for key in (
        "format",
        "state",
        "success",
        "completion",
        "candidate_blob_sha256",
        "transaction_sha256",
        "shared_path_count",
        "fixed_state_sha256",
        "details",
        "automatic_retry",
    ):
        if actual_verification.get(key) != expected_verification.get(key):
            raise PreparedLibraryPackageLiveAdapterError(
                f"result_audit verification field {key!r} differs from independent read-back",
                stage="evidence_manifest",
                state="failed",
            )
    payload = {
        "format": P17_005_EVIDENCE_MANIFEST_FORMAT,
        "version": 1,
        "runner_format": P17_005_RUNNER_FORMAT,
        "preflight_seal_sha256": preflight.seal_sha256,
        "backup_state_comparison": validated_result_audit[
            "backup_state_comparison"
        ],
        "candidate_blob_sha256": preflight.candidate.candidate_blob_sha256,
        "transaction_sha256": preflight.candidate.transaction_sha256,
        "before_backup": _sealed_backup_dict(verified_before),
        "after_backup": _sealed_backup_dict(verified_after),
        "result_audit": validated_result_audit,
        "external_raw_evidence": True,
        "raw_candidate_bytes_included": False,
        "raw_transaction_bytes_included": False,
        "automatic_retry_allowed": False,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
            handle.write("\n")
    except FileExistsError as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"refusing to replace existing evidence manifest: {path}",
            stage="evidence_manifest",
            state="failed",
        ) from exc
    except OSError as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"could not write evidence manifest: {exc}",
            stage="evidence_manifest",
            state="failed",
        ) from exc
    return path


__all__ = [
    "P17_005_CONFIRMATION",
    "P17_005_DEVICE_IDENTITY",
    "P17_005_EVIDENCE_MANIFEST_FORMAT",
    "P17_005_OWNER_APPROVAL",
    "P17_005_PROFILE",
    "P17_005_RUNNER_FORMAT",
    "P17_005_SUCCESS_SEQUENCE",
    "P17_005_TARGET_FOLDER",
    "PreparedLibraryPackageLiveAdapterError",
    "PreparedLibraryPackageLivePreflight",
    "PreparedLibraryPackageLiveResult",
    "execute_prepared_library_package_live",
    "prepare_prepared_library_package_live_preflight",
    "write_prepared_library_package_evidence_manifest",
]
