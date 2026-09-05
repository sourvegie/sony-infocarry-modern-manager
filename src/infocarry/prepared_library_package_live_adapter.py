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
from threading import Lock
from types import MappingProxyType
from typing import Any, Callable, Mapping, NoReturn, Optional
from uuid import uuid4

from .backup_format import ParsedBackupBlob, parse_backup_blob
from .backup_state_identity import (
    BackupStateIdentity,
    compare_verified_backups,
    derive_backup_state_identity,
)
from .capacity_evidence import NativeCapacityResponse
from .device_info import RawInfoResponse
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
from .prepared_library_package_operation_bundle import (
    EVIDENCE_OUTPUT_POLICY,
    OperationBundleError,
    PreparedLibraryPackageOperationBundle,
)
from .prepared_multi_package_gate import (
    PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_EXPLICIT,
    PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_FIXED,
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
P17_009_OWNER_APPROVAL = "APPROVE P17-009 MODERN LIBRARY PACKAGE SMOKE 01"
P17_009_CONFIRMATION = "CONFIRM P17-009 ONE INFOCARRY MULTI-CHILD PACKAGE"
P17_009_CONFIRMATION_POLICY = PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_EXPLICIT
P17_005_RUNNER_FORMAT = "infocarry-p17-005-library-package-live-adapter-v1"
P17_005_EVIDENCE_MANIFEST_FORMAT = (
    "infocarry-p17-005-library-package-evidence-manifest-v1"
)
# This is the exact top-level shape emitted by the P17-012 sealed-preflight
# producer.  Keep it strict: in particular, the prospective transaction hash
# is nested under ``authorization.candidate_transaction_sha256``.  A stale
# top-level alias must not be accepted as a fallback or silently ignored.
P17_012_SEALED_PREFLIGHT_KEYS = frozenset(
    {
        "approval_consumed",
        "authorization",
        "automatic_retry_allowed",
        "backend_write_calls",
        "backup_state_identity",
        "backup_state_identity_sha256",
        "before_backup",
        "candidate",
        "capacity_response",
        "completion",
        "confirmation_phrase",
        "confirmation_policy",
        "core_preflight_seal_sha256",
        "device_changing_operation_performed",
        "device_identity",
        "expected_folder_name",
        "format",
        "hardware_accessed",
        "normal_gui_cli_transfer_exposed",
        "operation_sequence",
        "owner_approval_phrase",
        "preflight_seal_sha256",
        "profile",
        "read_only_hardware_accessed",
        "read_only_preflight",
        "send_count",
        "sender_calls",
        "state",
        "target_absent_from_fresh_backup",
        "usb_transmission_performed",
        "write_started",
        "zero_x101b_transmitted",
    }
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
EvidenceRootAllocator = Callable[[Path], Path]

P17_017_EVIDENCE_OUTPUT_POLICY = EVIDENCE_OUTPUT_POLICY


@dataclass(frozen=True)
class PreparedLibraryPackageAttemptEvidence:
    """Reserved per-attempt output paths, excluded from operation identity."""

    root: Path
    before_backup: Path
    after_backup: Path
    manifest: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "root": str(self.root),
            "before_backup": str(self.before_backup),
            "after_backup": str(self.after_backup),
            "manifest": str(self.manifest),
        }


def _default_evidence_root_allocator(namespace: Path) -> Path:
    return namespace / f"p17-017-attempt-{uuid4().hex}"


def _reserve_attempt_evidence(
    namespace: Path,
    allocator: Optional[EvidenceRootAllocator],
) -> PreparedLibraryPackageAttemptEvidence:
    """Atomically reserve one direct child for this execution attempt."""

    requested_namespace = Path(namespace).expanduser()
    if not requested_namespace.is_absolute():
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-017 evidence namespace must be absolute",
            stage="evidence_outputs",
            state="failed",
        )
    if requested_namespace.is_symlink():
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-017 evidence namespace must not be a symlink",
            stage="evidence_outputs",
            state="failed",
        )
    namespace = requested_namespace
    namespace = namespace.resolve()
    if not namespace.is_dir():
        raise PreparedLibraryPackageLiveAdapterError(
            f"P17-017 evidence namespace is not an existing directory: {namespace}",
            stage="evidence_outputs",
            state="failed",
        )
    repository_root = Path(__file__).resolve().parents[2]
    try:
        namespace.relative_to(repository_root)
    except ValueError:
        pass
    else:
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-017 evidence namespace must be outside the source repository",
            stage="evidence_outputs",
            state="failed",
        )
    allocator = allocator or _default_evidence_root_allocator
    try:
        requested = allocator(namespace)
        candidate = Path(requested).expanduser()
    except Exception as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"P17-017 evidence root allocation failed: {exc}",
            stage="evidence_outputs",
            state="failed",
        ) from exc
    if not candidate.is_absolute():
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-017 evidence root allocation must return an absolute path",
            stage="evidence_outputs",
            state="failed",
        )
    candidate = candidate.resolve()
    if candidate.parent != namespace:
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-017 evidence root must be a direct child of the evidence namespace",
            stage="evidence_outputs",
            state="failed",
        )
    try:
        candidate.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"P17-017 evidence root already exists: {candidate}",
            stage="evidence_outputs",
            state="failed",
        ) from exc
    except OSError as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"P17-017 evidence root could not be reserved: {exc}",
            stage="evidence_outputs",
            state="failed",
        ) from exc
    if any(candidate.iterdir()):
        raise PreparedLibraryPackageLiveAdapterError(
            f"P17-017 reserved evidence root is not empty: {candidate}",
            stage="evidence_outputs",
            state="failed",
        )
    outputs = PreparedLibraryPackageAttemptEvidence(
        root=candidate,
        before_backup=candidate / P17_017_EVIDENCE_OUTPUT_POLICY["before_backup_name"],
        after_backup=candidate / P17_017_EVIDENCE_OUTPUT_POLICY["post_operation_name"],
        manifest=candidate / P17_017_EVIDENCE_OUTPUT_POLICY["manifest_name"],
    )
    if any(path.exists() for path in (outputs.before_backup, outputs.after_backup, outputs.manifest)):
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-017 reserved evidence output collides with an existing child",
            stage="evidence_outputs",
            state="failed",
        )
    return outputs


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


class _OneShotExecutionClaim:
    """In-memory single-use claim for one sealed preflight object."""

    __slots__ = ("_consumed", "_lock")

    def __init__(self) -> None:
        self._consumed = False
        self._lock = Lock()

    def consume(self) -> None:
        with self._lock:
            if self._consumed:
                raise PreparedLibraryPackageLiveAdapterError(
                    "P17-005 sealed preflight already attempted its one transaction",
                    stage="write_guard",
                    state="failed",
                )
            self._consumed = True


_EXECUTION_CLAIMS_LOCK = Lock()
_EXECUTION_CLAIMS: dict[str, _OneShotExecutionClaim] = {}


def _execution_claim_for(seal_sha256: str) -> _OneShotExecutionClaim:
    """Return the process-local single-use claim for one sealed operation."""

    with _EXECUTION_CLAIMS_LOCK:
        return _EXECUTION_CLAIMS.setdefault(seal_sha256, _OneShotExecutionClaim())


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


def _strict_json_object(path: Path) -> dict[str, Any]:
    """Load one JSON object while rejecting duplicate keys at every level."""

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.expanduser().resolve().read_text(encoding="utf-8"),
            object_pairs_hook=object_pairs,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"P17-012 sealed preflight could not be loaded: {exc}",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        ) from exc
    if not isinstance(value, dict):
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-012 sealed preflight must be a JSON object",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        )
    return value


def _require_digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value.lower() != value
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PreparedLibraryPackageLiveAdapterError(
            f"{label} must be a lowercase SHA-256 digest",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        )
    return value


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


def _backup_comparison_for_validation(comparison: Any) -> Any:
    """Ignore only verifier-time churn when replaying a preserved audit.

    ``verified_at_utc`` is acquisition provenance, not raw device state.  A
    later integrity replay necessarily samples that value at a different
    instant, while the original result audit must retain the time observed at
    capture.  All raw-state differences and every other provenance field
    remain exact.
    """

    value = json.loads(json.dumps(comparison, ensure_ascii=True))
    if isinstance(value, dict):
        differences = value.get("provenance_differences")
        if isinstance(differences, list):
            value["provenance_differences"] = [
                entry
                for entry in differences
                if not (
                    isinstance(entry, dict)
                    and entry.get("field") == "verified_at_utc"
                )
            ]
    return value


def _validate_evidence_output_record(outputs: Any) -> dict[str, str]:
    if not isinstance(outputs, Mapping) or set(outputs) != {
        "root",
        "before_backup",
        "after_backup",
        "manifest",
    }:
        raise PreparedLibraryPackageLiveAdapterError(
            "result_audit evidence output record is malformed",
            stage="evidence_manifest",
            state="failed",
        )
    result: dict[str, str] = {}
    for label, value in outputs.items():
        if not isinstance(value, str) or not value:
            raise PreparedLibraryPackageLiveAdapterError(
                f"result_audit evidence output {label} is malformed",
                stage="evidence_manifest",
                state="failed",
            )
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise PreparedLibraryPackageLiveAdapterError(
                f"result_audit evidence output {label} is not absolute",
                stage="evidence_manifest",
                state="failed",
            )
        result[label] = str(path.resolve())
    return result


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
        "approval_consumed",
        "preflight_seal_sha256",
        "backup_state_comparison",
        "candidate",
        "authorization",
        "completion",
        "verification",
        "workflow",
        "evidence_outputs",
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
    _validate_evidence_output_record(value["evidence_outputs"])
    if (
        value["format"] != P17_005_RUNNER_FORMAT
        or value["state"] != "readback_verified"
        or value["profile"] != P17_005_PROFILE
        or value["device_identity"] != list(_expected_device_hex())
        or value["expected_folder_name"] != preflight.expected_folder_name
        or value["usb_transmission_performed"] is not True
        or value["device_changing_operation_performed"] is not True
        or value["approval_consumed"] is not True
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
        _backup_comparison_for_validation(value["backup_state_comparison"]),
        _backup_comparison_for_validation(expected_state_comparison),
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


def _validate_operation_phrase(value: str, label: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or "\n" in value
        or "\r" in value
    ):
        raise PreparedLibraryPackageLiveAdapterError(
            f"{label} is invalid",
            stage="approval",
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
        "owner_approval_phrase": audit.get(
            "owner_approval_phrase", P17_005_OWNER_APPROVAL
        ),
        "confirmation_phrase": audit.get(
            "confirmation_phrase", core.authorization.core.confirmation_phrase
        ),
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

    def _consume_execution_claim(self) -> None:
        """Consume the only sender-attempt claim for this sealed preflight."""

        _execution_claim_for(self.seal_sha256).consume()

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
            or report.get("confirmation_phrase")
            != self.core.authorization.core.confirmation_phrase
            or report.get("confirmation_policy")
            != self.core.authorization.core.confirmation_policy
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


def load_prepared_library_package_live_preflight(
    report_path: Path,
    *,
    catalog: LibraryCatalog,
    selected_item_id: str,
    backup: VerifiedBackup,
    template: ParsedBackupBlob,
    capacity_response: NativeCapacityResponse,
) -> PreparedLibraryPackageLivePreflight:
    """Load and independently reconstruct one sealed P17-012 preflight.

    The sealed JSON is an input to a future live boundary, not an authority
    for candidate bytes.  Its exact schema is checked first, then the
    reviewed Library bridge reconstructs the core candidate from the caller's
    independently verified backup, template, capacity response, and catalog.
    In particular, the transaction binding is accepted only at
    ``authorization.candidate_transaction_sha256``; a top-level alias is an
    unexpected field and fails before any live callback could be reached.
    """

    report = _strict_json_object(Path(report_path))
    missing = sorted(P17_012_SEALED_PREFLIGHT_KEYS - set(report))
    unexpected = sorted(set(report) - P17_012_SEALED_PREFLIGHT_KEYS)
    if missing or unexpected:
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-012 sealed preflight schema fields differ: "
            f"missing={missing}, unexpected={unexpected}",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        )

    expected_scalars = {
        "format": P17_005_RUNNER_FORMAT,
        "state": "ready_for_hardware_test_host_only",
        "profile": P17_005_PROFILE,
        "device_identity": list(_expected_device_hex()),
        "expected_folder_name": P17_005_TARGET_FOLDER,
        "read_only_preflight": True,
        # Detection/capacity/backup are hardware access, but remain strictly
        # read-only.  These flags match the P17-012 sealed-report producer.
        "hardware_accessed": True,
        "read_only_hardware_accessed": True,
        "usb_transmission_performed": False,
        "device_changing_operation_performed": False,
        "target_absent_from_fresh_backup": True,
        "approval_consumed": False,
        "backend_write_calls": 0,
        "sender_calls": 0,
        "send_count": 0,
        "write_started": False,
        "completion": None,
        "zero_x101b_transmitted": True,
        "automatic_retry_allowed": False,
        "normal_gui_cli_transfer_exposed": False,
        "operation_sequence": [
            "read_only_preflight",
            "expected_device_detected",
            "fresh_capacity_queried_0x0019",
            "fresh_complete_backup_verified",
            "library_candidate_reconstructed",
            "hash_only_preview_presented",
            "live_preflight_sealed",
        ],
    }
    boolean_fields = {
        "read_only_preflight",
        "hardware_accessed",
        "read_only_hardware_accessed",
        "usb_transmission_performed",
        "device_changing_operation_performed",
        "target_absent_from_fresh_backup",
        "approval_consumed",
        "write_started",
        "zero_x101b_transmitted",
        "automatic_retry_allowed",
        "normal_gui_cli_transfer_exposed",
    }
    integer_fields = {"backend_write_calls", "sender_calls", "send_count"}
    for key in boolean_fields:
        if type(report.get(key)) is not bool:
            raise PreparedLibraryPackageLiveAdapterError(
                f"P17-012 sealed preflight field {key!r} must be a boolean",
                stage="preflight_load",
                state="failed",
                audit={"operation_sequence": []},
            )
    for key in integer_fields:
        if type(report.get(key)) is not int:
            raise PreparedLibraryPackageLiveAdapterError(
                f"P17-012 sealed preflight field {key!r} must be an integer",
                stage="preflight_load",
                state="failed",
                audit={"operation_sequence": []},
            )
    for key, expected in expected_scalars.items():
        if report.get(key) != expected:
            raise PreparedLibraryPackageLiveAdapterError(
                f"P17-012 sealed preflight field {key!r} is not the reviewed value",
                stage="preflight_load",
                state="failed",
                audit={"operation_sequence": []},
            )

    _require_digest(report["preflight_seal_sha256"], "preflight_seal_sha256")
    _require_digest(
        report["core_preflight_seal_sha256"],
        "core_preflight_seal_sha256",
    )
    if not isinstance(report["owner_approval_phrase"], str):
        raise PreparedLibraryPackageLiveAdapterError(
            "owner_approval_phrase must be a string",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        )
    _validate_operation_phrase(report["owner_approval_phrase"], "owner approval phrase")
    _validate_operation_phrase(report["confirmation_phrase"], "confirmation phrase")
    if report["confirmation_policy"] not in (
        PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_FIXED,
        PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_EXPLICIT,
    ):
        raise PreparedLibraryPackageLiveAdapterError(
            "confirmation_policy is not a supported reviewed policy",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        )

    authorization = report["authorization"]
    if not isinstance(authorization, Mapping):
        raise PreparedLibraryPackageLiveAdapterError(
            "authorization must be a JSON object",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        )
    transaction_sha256 = _require_digest(
        authorization.get("candidate_transaction_sha256"),
        "authorization.candidate_transaction_sha256",
    )
    timestamp = authorization.get("new_record_timestamp_be32")
    if isinstance(timestamp, bool) or not isinstance(timestamp, int) or not (
        0 <= timestamp <= 0xFFFFFFFF
    ):
        raise PreparedLibraryPackageLiveAdapterError(
            "authorization.new_record_timestamp_be32 is invalid",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        )
    if not isinstance(backup, VerifiedBackup):
        raise PreparedLibraryPackageLiveAdapterError(
            "an independently verified backup is required to load a sealed preflight",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        )
    if not isinstance(template, ParsedBackupBlob):
        raise PreparedLibraryPackageLiveAdapterError(
            "the reviewed parsed template is required to load a sealed preflight",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        )
    if not isinstance(capacity_response, NativeCapacityResponse):
        raise PreparedLibraryPackageLiveAdapterError(
            "the parsed native capacity response is required to load a sealed preflight",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        )

    try:
        core = prepare_prepared_library_package_preflight(
            catalog,
            selected_item_id,
            backup,
            template,
            new_record_timestamp_be32=timestamp,
            native_capacity_response=capacity_response,
            template_folder_path=P17_003_TEMPLATE_FOLDER_PATH,
            template_item_paths=P17_003_TEMPLATE_ITEM_PATHS,
            confirmation_phrase=report["confirmation_phrase"],
            confirmation_policy=report["confirmation_policy"],
        )
    except (PreparedLibraryPackageBridgeError, OSError, ValueError, TypeError) as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"P17-012 sealed preflight reconstruction failed: {exc}",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        ) from exc

    if transaction_sha256 != core.candidate.transaction_sha256:
        raise PreparedLibraryPackageLiveAdapterError(
            "authorization.candidate_transaction_sha256 does not match "
            "the independently reconstructed transaction",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        )
    if report["core_preflight_seal_sha256"] != core.seal_sha256:
        raise PreparedLibraryPackageLiveAdapterError(
            "core_preflight_seal_sha256 does not match the reconstructed core",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        )

    preflight = PreparedLibraryPackageLivePreflight(
        core=core,
        expected_folder_name=report["expected_folder_name"],
        seal_sha256=report["preflight_seal_sha256"],
        audit=report,
    )
    try:
        preflight.verify_seal()
    except PreparedLibraryPackageLiveAdapterError as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"P17-012 sealed preflight verification failed: {exc}",
            stage="preflight_load",
            state="failed",
            audit={"operation_sequence": []},
        ) from exc
    return preflight


@dataclass(frozen=True)
class _ResolvedPreparedLibraryPackageOperationBundle:
    """Protocol-specific view of one already verified operation bundle."""

    bundle: PreparedLibraryPackageOperationBundle
    preflight: PreparedLibraryPackageLivePreflight
    catalog: LibraryCatalog
    template: ParsedBackupBlob
    capacity_response: NativeCapacityResponse


def _resolve_prepared_library_package_operation_bundle(
    bundle: PreparedLibraryPackageOperationBundle,
) -> _ResolvedPreparedLibraryPackageOperationBundle:
    """Resolve every artifact from the one immutable bundle before callbacks."""

    if not isinstance(bundle, PreparedLibraryPackageOperationBundle):
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-015 requires one immutable prepared Library operation bundle",
            stage="operation_bundle",
            state="failed",
        )
    try:
        bundle.verify_artifacts()
        report_path = Path(bundle.sealed_report.path)
        report = _strict_json_object(report_path)
        binding = report["candidate"]["library_binding"]
        report_before = report["before_backup"]
        report_capacity = report["capacity_response"]
        report_authorization = report["authorization"]
        candidate_audit = report["candidate"]
        expected_post = candidate_audit["expected_post_operation"]
    except (KeyError, TypeError, OperationBundleError) as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"P17-015 operation bundle bindings are malformed: {exc}",
            stage="operation_bundle",
            state="failed",
        ) from exc

    def require_equal(label: str, actual: Any, expected: Any) -> None:
        if not _json_equivalent(actual, expected):
            raise OperationBundleError(
                f"operation bundle {label} differs from its sealed report"
            )

    try:
        if str(Path(report_before["directory"]).expanduser().resolve()) != bundle.baseline_backup.path:
            raise OperationBundleError(
                "operation bundle baseline backup is not the sealed report baseline"
            )
        if report_before.get("manifest_sha256") != bundle.baseline_backup.sha256:
            raise OperationBundleError("operation bundle baseline manifest hash differs")
        if str(Path(binding["catalog_path"]).expanduser().resolve()) != bundle.catalog.path:
            raise OperationBundleError("operation bundle catalog is not the sealed Library catalog")
        if str(Path(binding["manifest_path"]).expanduser().resolve()) != bundle.package_manifest.path:
            raise OperationBundleError(
                "operation bundle package manifest is not the sealed package manifest"
            )
        require_equal(
            "ordered package children",
            binding["ordered_children"],
            bundle.to_dict()["package_children"],
        )
        require_equal(
            "expected post-operation",
            expected_post,
            bundle.to_dict()["expected_post_operation"],
        )
        if bundle.selected_item_id != binding["catalog_item_id"]:
            raise OperationBundleError("operation bundle selected Library item differs")
        if bundle.expected_folder_name != report["expected_folder_name"]:
            raise OperationBundleError("operation bundle destination differs")
        if tuple(bundle.device_identity) != tuple(report["device_identity"]):
            raise OperationBundleError("operation bundle device identity differs")
        if bundle.owner_approval_phrase != report["owner_approval_phrase"]:
            raise OperationBundleError("operation bundle owner approval differs")
        if bundle.confirmation_phrase != report["confirmation_phrase"]:
            raise OperationBundleError("operation bundle confirmation differs")
        if bundle.confirmation_policy != report["confirmation_policy"]:
            raise OperationBundleError("operation bundle confirmation policy differs")
        if bundle.new_record_timestamp_be32 != report_authorization["new_record_timestamp_be32"]:
            raise OperationBundleError("operation bundle timestamp differs")
        if bundle.timestamp_policy != candidate_audit["policy"]["timestamp"]:
            raise OperationBundleError("operation bundle timestamp policy differs")
        if report_capacity.get("raw_response_sha256") != bundle.capacity_response_sha256:
            raise OperationBundleError("operation bundle capacity response hash differs")
        if report_authorization["candidate_transaction_sha256"] != bundle.transaction_sha256:
            raise OperationBundleError("operation bundle transaction binding differs")
        if candidate_audit["candidate"]["blob_sha256"] != bundle.candidate_blob_sha256:
            raise OperationBundleError("operation bundle candidate binding differs")
        if _sha256(_canonical_json(candidate_audit)) != bundle.candidate_audit_sha256:
            raise OperationBundleError("operation bundle candidate audit hash differs")
        if _sha256(_canonical_json(report_authorization)) != bundle.authorization_sha256:
            raise OperationBundleError("operation bundle authorization hash differs")
        if _sha256(_canonical_json(expected_post)) != bundle.expected_post_operation_sha256:
            raise OperationBundleError("operation bundle expected post-state hash differs")
        if _sha256(_canonical_json(binding)) != bundle.library_binding_sha256:
            raise OperationBundleError("operation bundle Library binding hash differs")
        if report["core_preflight_seal_sha256"] != bundle.core_preflight_seal_sha256:
            raise OperationBundleError("operation bundle core seal differs")
        if report["preflight_seal_sha256"] != bundle.preflight_seal_sha256:
            raise OperationBundleError("operation bundle outer seal differs")
        if report["backup_state_identity_sha256"] != bundle.baseline_state_identity_sha256:
            raise OperationBundleError("operation bundle raw-state identity differs")
        if report_capacity["raw_response_sha256"] != bundle.capacity_response_sha256:
            raise OperationBundleError("operation bundle capacity binding differs")
        report_catalog_hash = binding["catalog_sha256"]
    except (KeyError, TypeError, OperationBundleError) as exc:
        raise PreparedLibraryPackageLiveAdapterError(
            f"P17-015 operation bundle/report binding mismatch: {exc}",
            stage="operation_bundle",
            state="failed",
        ) from exc

    try:
        baseline = verify_fresh_backup(
            Path(bundle.baseline_backup.path),
            now=None,
            max_age_seconds=None,
        )
        if _backup_identity(baseline).sha256 != bundle.baseline_state_identity_sha256:
            raise ValueError("baseline raw-state identity differs from the sealed bundle")
        if _sha256(_canonical_json(LibraryCatalog(Path(bundle.catalog.path)).to_dict())) != report_catalog_hash:
            raise ValueError("catalog model hash differs from the sealed Library binding")
        catalog = LibraryCatalog(Path(bundle.catalog.path))
        template = parse_backup_blob(Path(bundle.template.path).read_bytes())
        capacity_response = NativeCapacityResponse.from_hardware_response(
            RawInfoResponse(0x0019, "operation-bundle", Path(bundle.capacity_response.path).read_bytes()),
            device_identity=P17_005_DEVICE_IDENTITY,
        )
        if capacity_response.to_dict() != report_capacity:
            raise ValueError("capacity response differs from the sealed bundle")
        preflight = load_prepared_library_package_live_preflight(
            report_path,
            catalog=catalog,
            selected_item_id=bundle.selected_item_id,
            backup=baseline,
            template=template,
            capacity_response=capacity_response,
        )
        if _backup_identity(preflight.before_backup).sha256 != bundle.baseline_state_identity_sha256:
            raise ValueError("loaded preflight raw-state identity differs from the bundle")
        if preflight.candidate.candidate_blob_sha256 != bundle.candidate_blob_sha256:
            raise ValueError("loaded candidate differs from the bundle")
        if preflight.candidate.transaction_sha256 != bundle.transaction_sha256:
            raise ValueError("loaded transaction differs from the bundle")
        if preflight.core.seal_sha256 != bundle.core_preflight_seal_sha256:
            raise ValueError("loaded core seal differs from the bundle")
        if preflight.seal_sha256 != bundle.preflight_seal_sha256:
            raise ValueError("loaded outer seal differs from the bundle")
    except Exception as exc:
        if isinstance(exc, PreparedLibraryPackageLiveAdapterError):
            raise
        raise PreparedLibraryPackageLiveAdapterError(
            f"P17-015 operation bundle resolution failed: {exc}",
            stage="operation_bundle",
            state="failed",
        ) from exc

    return _ResolvedPreparedLibraryPackageOperationBundle(
        bundle=bundle,
        preflight=preflight,
        catalog=catalog,
        template=template,
        capacity_response=capacity_response,
    )


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


P17_019_WRAPPER_RESULT_FORMAT = (
    "infocarry-p17-019-library-package-live-result-reconciliation-v1"
)


class PreparedLibraryPackageLiveResultReconciliationError(RuntimeError):
    """Terminal post-run reconciliation failure; no retry is permitted."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        audit: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.automatic_retry_allowed = False
        self.audit = dict(audit or {})
        self.audit.setdefault("automatic_retry_allowed", False)


@dataclass(frozen=True)
class PreparedLibraryPackageLiveWrapperResult:
    """Successful terminal wrapper result after a second disk-only check.

    The production runner remains the source of the device-operation result.
    This record adds only the surrounding wrapper's independent read-back
    conclusion.  It deliberately reports one logical sender operation and a
    separately named low-level bulk-write count; the latter is never treated
    as a sender-call count.
    """

    runner_result: PreparedLibraryPackageLiveResult
    verification: PreparedMultiPackageReadback
    audit: Mapping[str, Any]

    @property
    def state(self) -> str:
        return "readback_verified"

    @property
    def completion(self) -> int:
        return self.runner_result.completion

    def to_dict(self) -> dict[str, Any]:
        return dict(self.audit)


def reconcile_prepared_library_package_live_result(
    result: PreparedLibraryPackageLiveResult,
    *,
    low_level_bulk_write_calls: Optional[int] = None,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> PreparedLibraryPackageLiveWrapperResult:
    """Reconcile one successful runner result without touching hardware.

    This is the reviewed boundary for a surrounding execution/audit wrapper.
    It accepts only the production runner's successful result shape and uses
    ``result.preflight.candidate.core`` for the independent disk verifier.
    Passing the enclosing preflight object is intentionally impossible at
    this boundary.  The runner has already enforced the device, approval,
    one-shot, completion, and post-backup gates; this function never sends,
    retries, or changes device state.
    """

    failure_audit = {
        "format": P17_019_WRAPPER_RESULT_FORMAT,
        "state": "failed",
        "automatic_retry_allowed": False,
    }

    def fail(message: str, stage: str) -> NoReturn:
        failure_audit["stage"] = stage
        raise PreparedLibraryPackageLiveResultReconciliationError(
            message,
            stage=stage,
            audit=failure_audit,
        )

    if not isinstance(result, PreparedLibraryPackageLiveResult):
        fail("runner result is not a PreparedLibraryPackageLiveResult", "result")
    if isinstance(result.completion, bool) or not isinstance(result.completion, int):
        fail("runner completion is missing or malformed", "completion")
    if result.completion != 0:
        fail(
            f"runner completion was 0x{result.completion:04x}; only 0x0000 is accepted",
            "completion",
        )
    if low_level_bulk_write_calls is not None and (
        isinstance(low_level_bulk_write_calls, bool)
        or not isinstance(low_level_bulk_write_calls, int)
        or low_level_bulk_write_calls < 0
    ):
        fail("low-level bulk-write call count is malformed", "accounting")

    try:
        result.preflight.verify_seal()
        result.authorization.require_same_candidate(result.candidate)
    except Exception as exc:
        fail(f"runner result bindings are not sealed: {exc}", "bindings")

    audit = _thaw(result.audit)
    if not isinstance(audit, Mapping):
        fail("runner result audit is malformed", "runner_audit")
    if (
        audit.get("format") != P17_005_RUNNER_FORMAT
        or audit.get("state") != "readback_verified"
        or audit.get("usb_transmission_performed") is not True
        or audit.get("device_changing_operation_performed") is not True
        or audit.get("approval_consumed") is not True
        or audit.get("completion") != "0x0000"
        or audit.get("preflight_seal_sha256") != result.preflight.seal_sha256
    ):
        fail("runner result is not a successful sealed operation", "runner_audit")

    workflow = audit.get("workflow")
    if not isinstance(workflow, Mapping):
        fail("runner workflow audit is malformed", "accounting")
    if (
        workflow.get("isolated_one_shot_adapter") is not True
        or type(workflow.get("sender_calls")) is not int
        or workflow.get("sender_calls") != 1
        or workflow.get("automatic_retry_allowed") is not False
    ):
        fail(
            "runner workflow is not exactly one logical sender call with no retry",
            "accounting",
        )

    candidate_audit = audit.get("candidate")
    if not isinstance(candidate_audit, Mapping):
        fail("runner candidate audit is malformed", "bindings")
    try:
        _require_reconstructed_candidate_matches(
            result.preflight.candidate,
            result.candidate,
        )
    except Exception as exc:
        fail(f"runner candidate does not match the sealed candidate: {exc}", "bindings")
    candidate_details = candidate_audit.get("candidate")
    transaction_details = candidate_audit.get("transaction")
    if not isinstance(candidate_details, Mapping) or not isinstance(
        transaction_details, Mapping
    ) or (
        candidate_details.get("blob_sha256") != result.candidate.candidate_blob_sha256
        or transaction_details.get("sha256") != result.candidate.transaction_sha256
    ):
        fail("runner candidate or transaction hash is inconsistent", "bindings")

    if not isinstance(result.before_backup, VerifiedBackup) or not isinstance(
        result.after_backup, VerifiedBackup
    ):
        fail("runner result does not contain two verified backups", "post_backup")
    if result.before_backup.directory == result.after_backup.directory:
        fail("runner before and after backups must be distinct", "post_backup")
    try:
        before_identity = _backup_identity(result.before_backup)
        sealed_identity = _backup_identity(result.preflight.before_backup)
        candidate_identity = _backup_identity(result.candidate.core.backup)
    except Exception as exc:
        fail(f"runner before backup could not be verified: {exc}", "post_backup")
    if before_identity != sealed_identity:
        fail("runner before backup does not match sealed preflight state", "post_backup")
    if before_identity != candidate_identity:
        fail("runner before backup does not match candidate backup state", "post_backup")
    if not isinstance(result.verification, PreparedMultiPackageReadback):
        fail("runner read-back result is malformed", "readback")
    if (
        not result.verification.success
        or type(result.verification.completion) is not int
        or result.verification.completion != 0
        or result.verification.candidate.candidate_blob_sha256
        != result.candidate.candidate_blob_sha256
        or result.verification.candidate.transaction_sha256
        != result.candidate.transaction_sha256
        or result.verification.before.directory != result.before_backup.directory
        or result.verification.after.directory != result.after_backup.directory
    ):
        fail("runner result does not contain the exact successful read-back", "readback")

    try:
        independent = verify_prepared_multi_package_readback(
            result.preflight.candidate.core,
            result.after_backup.directory,
            completion=result.completion,
            now=now,
            max_age_seconds=max_age_seconds,
        )
    except Exception as exc:
        fail(f"independent disk read-back verification failed: {exc}", "readback")

    wrapper_audit = {
        "format": P17_019_WRAPPER_RESULT_FORMAT,
        "state": "readback_verified",
        "terminal_success": True,
        "completion": "0x0000",
        "write_started": True,
        "approval_consumed": True,
        "preflight_seal_sha256": result.preflight.seal_sha256,
        "candidate_blob_sha256": result.candidate.candidate_blob_sha256,
        "transaction_sha256": result.candidate.transaction_sha256,
        "accounting": {
            "logical_sender_calls": 1,
            "low_level_bulk_write_calls": low_level_bulk_write_calls,
            "definition": (
                "one logical sender call may contain multiple low-level bulk writes; "
                "bulk writes are not sender calls"
            ),
        },
        "post_backup_verified": True,
        "independent_readback_verified": True,
        "verification": {
            "shared_path_count": independent.shared_path_count,
            "details": dict(independent.details),
            "automatic_retry": False,
        },
        "automatic_retry_allowed": False,
    }
    return PreparedLibraryPackageLiveWrapperResult(
        runner_result=result,
        verification=independent,
        audit=wrapper_audit,
    )


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
    evidence_outputs: Optional[PreparedLibraryPackageAttemptEvidence] = None,
    approval_consumed: bool = False,
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
    audit["approval_consumed"] = approval_consumed
    if evidence_outputs is not None:
        audit["evidence_outputs"] = evidence_outputs.to_dict()
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
    owner_approval_phrase: str = P17_005_OWNER_APPROVAL,
    confirmation_phrase: str = P17_005_CONFIRMATION,
    confirmation_policy: str = PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_FIXED,
) -> PreparedLibraryPackageLivePreflight:
    """Run and seal the required fresh, read-only injected preflight.

    The order is fixed: cancellation check, expected-device detection, native
    capacity response, complete backup capture/verification, Library/package
    reconstruction, hash-only preview, then sealing.  No sender is accepted or
    called here.
    """

    _validate_expected_folder(expected_folder_name)
    _validate_operation_phrase(owner_approval_phrase, "owner approval phrase")
    _validate_operation_phrase(confirmation_phrase, "confirmation phrase")
    if confirmation_policy == PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_EXPLICIT and (
        owner_approval_phrase == P17_005_OWNER_APPROVAL
        or confirmation_phrase == P17_005_CONFIRMATION
    ):
        raise PreparedLibraryPackageLiveAdapterError(
            "explicit operation phrases must not reuse expired P17-007 phrases",
            stage="approval",
            state="failed",
        )
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
            # Fresh-backup verification samples its wall clock after capture
            # finalization.  Do not let a caller's pre-capture timestamp become
            # the authoritative freshness reference.
            now=None,
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
            confirmation_phrase=confirmation_phrase,
            confirmation_policy=confirmation_policy,
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
        "hardware_accessed": True,
        "read_only_hardware_accessed": True,
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
        "owner_approval_phrase": owner_approval_phrase,
        "confirmation_phrase": confirmation_phrase,
        "confirmation_policy": confirmation_policy,
        "automatic_retry_allowed": False,
        "normal_gui_cli_transfer_exposed": False,
        "send_count": 0,
        "sender_calls": 0,
        "backend_write_calls": 0,
        "approval_consumed": False,
        "write_started": False,
        "completion": None,
        "zero_x101b_transmitted": True,
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
    operation_bundle: PreparedLibraryPackageOperationBundle,
    *,
    owner_approval: str,
    confirmation: str,
    detect_device: DetectDeviceCallback,
    query_capacity: CapacityQueryCallback,
    backend: Optional[WriteBackend],
    capture: CaptureCallback,
    evidence_namespace: Path,
    evidence_root_allocator: Optional[EvidenceRootAllocator] = None,
    preflight_only: bool = False,
    pre_send_revalidator: Optional[Callable[[], None]] = None,
    policy: WritePolicy = WritePolicy(),
    clock: Clock = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    cancelled: Optional[CancelledCallback] = None,
    progress: Optional[ProgressCallback] = None,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
) -> PreparedLibraryPackageLiveResult:
    """Execute exactly one approved transaction from one immutable bundle.

    The bundle resolves the sealed report, baseline backup, catalog, template,
    capacity evidence, package children, and exact candidate/transaction
    hashes as one hash-bound operation input. Per-attempt evidence outputs are
    reserved beneath ``evidence_namespace`` after bundle resolution and are
    not part of the operation identity. Runtime callbacks are the only
    remaining device boundaries. A live claim is consumed before any device
    callback, while preflight-only mode leaves the claim available for a later
    approved live attempt. A new complete backup is captured and verified
    immediately before the sender call. Any post-start failure is terminal and
    indeterminate; this function has no retry or corrective-write path.
    """

    resolved = _resolve_prepared_library_package_operation_bundle(operation_bundle)
    bundle = resolved.bundle
    preflight = resolved.preflight
    catalog = resolved.catalog
    template = resolved.template
    selected_item_id = bundle.selected_item_id
    evidence_outputs = _reserve_attempt_evidence(
        evidence_namespace,
        evidence_root_allocator,
    )
    _validate_callbacks(
        detect_device=detect_device,
        query_capacity=query_capacity,
        capture=capture,
    )
    if pre_send_revalidator is not None and not callable(pre_send_revalidator):
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-005 pre_send_revalidator must be callable",
            stage="preflight",
            state="failed",
        )
    sequence = ["live_preflight_seal_verified"]
    sender_calls = 0
    approval_consumed = False
    try:
        preflight.verify_seal()
    except PreparedLibraryPackageLiveAdapterError:
        raise

    expected_owner_approval = _thaw(preflight.audit).get(
        "owner_approval_phrase", P17_005_OWNER_APPROVAL
    )
    expected_confirmation = preflight.authorization.core.confirmation_phrase
    if owner_approval != expected_owner_approval:
        raise PreparedLibraryPackageLiveAdapterError(
            "P17-005 owner approval phrase was not accepted; no transaction attempted",
            stage="approval",
            state="failed",
        )
    if confirmation != expected_confirmation:
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

    # A live attempt becomes single-use before any safety-relevant device
    # callback.  Preflight-only mode deliberately does not consume the claim;
    # safe cancellation above is the only live path that may exit without
    # expiring the approval after it has been accepted.
    if not preflight_only:
        preflight._consume_execution_claim()
        approval_consumed = True

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
            now=None,
            max_age_seconds=max_age_seconds,
        )
        if _backup_identity(sealed_before) != _backup_identity(preflight.before_backup):
            raise ValueError("sealed preflight backup changed before execution")
        sequence.append("sealed_preflight_backup_revalidated")
        before = capture_and_verify_fresh_backup(
            evidence_outputs.before_backup,
            lambda destination: capture(
                destination,
                cancelled=cancelled,
                progress=progress,
            ),
            now=None,
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
            evidence_outputs=evidence_outputs,
            approval_consumed=approval_consumed,
        ) from exc

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
            confirmation_policy=preflight.authorization.core.confirmation_policy,
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
            evidence_outputs=evidence_outputs,
            approval_consumed=approval_consumed,
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
            evidence_outputs=evidence_outputs,
            approval_consumed=approval_consumed,
        ) from exc

    if not preflight_only and pre_send_revalidator is not None:
        try:
            pre_send_revalidator()
        except Exception as exc:
            raise _failure(
                f"P17-005 pre-send revalidation failed: {exc}",
                stage="pre_send_revalidation",
                state="failed",
                sequence=sequence,
                sender_calls=sender_calls,
                write_started=False,
                candidate=candidate,
                authorization=authorization,
                primary_error=str(exc),
                evidence_outputs=evidence_outputs,
                approval_consumed=approval_consumed,
            ) from exc

    try:
        if preflight_only:
            raise PreparedLibraryPackageLiveAdapterError(
                "P17-005 preflight-only mode reached the sender boundary without a send",
                stage="sender",
                state="preflight_only_sender_boundary",
                audit={
                    "operation_sequence": sequence,
                    "evidence_outputs": evidence_outputs.to_dict(),
                    "sender_calls": sender_calls,
                    "approval_consumed": approval_consumed,
                    "write_started": False,
                },
            )
        if not all(
            hasattr(backend, name)
            for name in ("control_out", "control_in", "bulk_write")
        ):
            raise PreparedLibraryPackageLiveAdapterError(
                "P17-005 requires a write backend at the approved boundary",
                stage="sender",
                state="failed",
                audit={
                    "operation_sequence": sequence,
                    "evidence_outputs": evidence_outputs.to_dict(),
                    "sender_calls": sender_calls,
                    "approval_consumed": approval_consumed,
                    "write_started": False,
                },
            )
        from .write_protocol import AuthorizedWriteSender as _AuthorizedWriteSender

        sender_impl = _AuthorizedWriteSender(
            backend,
            bundle.bulk_out_endpoint,
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
                    now=None,
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
                evidence_outputs=evidence_outputs,
                approval_consumed=approval_consumed,
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
            evidence_outputs=evidence_outputs,
            approval_consumed=approval_consumed,
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
            evidence_outputs=evidence_outputs,
            approval_consumed=approval_consumed,
        )
    sequence.append("completion_0x0000")

    try:
        after = capture_and_verify_fresh_backup(
            evidence_outputs.after_backup,
            lambda destination: capture(
                destination,
                cancelled=cancelled,
                progress=progress,
            ),
            now=None,
            max_age_seconds=max_age_seconds,
        )
        if after.device_identity != _expected_device_hex():
            raise ValueError("post-operation backup identity differs from Sony 0x054c:0x001e")
        sequence.append("fresh_post_operation_backup_verified")
        verification = verify_prepared_multi_package_readback(
            candidate.core,
            after.directory,
            completion=completion,
            now=None,
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
            "approval_consumed": approval_consumed,
            "preflight_seal_sha256": preflight.seal_sha256,
            "evidence_outputs": evidence_outputs.to_dict(),
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
            evidence_outputs.manifest,
            preflight=preflight,
            before_backup=before,
            after_backup=after,
            result_audit=audit,
            now=None,
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
            evidence_outputs=evidence_outputs,
            approval_consumed=approval_consumed,
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
    output_record = _validate_evidence_output_record(
        validated_result_audit["evidence_outputs"]
    )
    expected_output_record = {
        "root": str(path.parent),
        "before_backup": str(
            path.parent / P17_017_EVIDENCE_OUTPUT_POLICY["before_backup_name"]
        ),
        "after_backup": str(
            path.parent / P17_017_EVIDENCE_OUTPUT_POLICY["post_operation_name"]
        ),
        "manifest": str(path),
    }
    if output_record != expected_output_record:
        raise PreparedLibraryPackageLiveAdapterError(
            "result_audit evidence outputs do not match the manifest destination",
            stage="evidence_manifest",
            state="failed",
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
    "EvidenceRootAllocator",
    "P17_005_CONFIRMATION",
    "P17_005_DEVICE_IDENTITY",
    "P17_005_EVIDENCE_MANIFEST_FORMAT",
    "P17_005_OWNER_APPROVAL",
    "P17_005_PROFILE",
    "P17_005_RUNNER_FORMAT",
    "P17_005_SUCCESS_SEQUENCE",
    "P17_005_TARGET_FOLDER",
    "P17_009_CONFIRMATION",
    "P17_009_CONFIRMATION_POLICY",
    "P17_009_OWNER_APPROVAL",
    "P17_012_SEALED_PREFLIGHT_KEYS",
    "P17_017_EVIDENCE_OUTPUT_POLICY",
    "P17_019_WRAPPER_RESULT_FORMAT",
    "PreparedLibraryPackageAttemptEvidence",
    "PreparedLibraryPackageLiveAdapterError",
    "PreparedLibraryPackageLivePreflight",
    "PreparedLibraryPackageLiveResult",
    "PreparedLibraryPackageLiveResultReconciliationError",
    "PreparedLibraryPackageLiveWrapperResult",
    "execute_prepared_library_package_live",
    "load_prepared_library_package_live_preflight",
    "prepare_prepared_library_package_live_preflight",
    "reconcile_prepared_library_package_live_result",
    "write_prepared_library_package_evidence_manifest",
]
