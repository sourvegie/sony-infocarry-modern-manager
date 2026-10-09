"""Offline deletion simulation and one bounded guarded root-TXT experiment.

The offline generalized workflow requires injected fake callbacks. A caller must
inject both backup and sender callbacks and explicitly pass ``fake_transport``
as the boolean ``True``.  The workflow sends at most once and preserves the
R15 distinction between safe pre-start cancellation and an indeterminate
post-start interruption.  Its finite deadline is cooperative: it is checked
at workflow boundaries and passed to the fake callback, but it cannot forcibly
interrupt an arbitrary Python callback that never returns.  Bounded USB-call
timeouts belong to the established canonical sender. The separate exact
experimental facade below uses that sender, durable owner and pinned runtime;
Device Library delegates only the same exact gated operation.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import math
from pathlib import Path
import time
from typing import Any, Callable, ClassVar, Mapping, Optional

from .delete_generalized import (
    DELETE_GENERALIZED_CONFIRMATION_PHRASE,
    GeneralizedDeleteAuthorization,
    GeneralizedDeleteCandidate,
    GeneralizedDeleteVerification,
    authorize_generalized_delete,
    bind_generalized_delete_sender,
    build_generalized_delete_candidate,
    verify_generalized_delete_readback,
)
from .protocol import TransferCancelledError, TransferTimeoutError
from .write_gate import DEFAULT_MAX_AGE_SECONDS, VerifiedBackup, capture_and_verify_fresh_backup

import json
from uuid import uuid4
from .root_txt_placement import (
    RootTxtPlacementBundle, RootTxtPlacementFacade, RootTxtReadback,
    _blob, _json, _sha, _write_json,
)
from .backup_format import parse_backup_blob
from .write_gate import verify_fresh_backup
from .capacity_evidence import NativeCapacityResponse
from .library_transfer_execution import OwnerAuthorizedOperationIdentity
from .library_transfer_runtime_provider import PinnedRootTxtRuntime
from .prepared_library_package_operation_bundle import OperationArtifact
from .write_artifact import ProspectiveWriteTransaction, load_preserved_artifact
from .write_safety_boundary import PersistentWriteSafetyOwner
from .p18_041h_experiment import FIXTURE_FILENAME, FIXTURE_PATH, FIXTURE_BYTES, FIXTURE_SHA256


ProgressCallback = Callable[[str, int, int], None]
CancelledCallback = Callable[[], bool]
CaptureCallback = Callable[..., None]
SendCallback = Callable[..., int]


@dataclass(frozen=True)
class FakeDeleteTransport:
    """Explicit capability wrapper for the offline delete workflow.

    The wrapper is intentionally a test/simulation boundary, not a security
    boundary.  It has no USB imports or discovery path.  Requiring this
    concrete type at the workflow boundary makes accidentally passing the
    production sender harder and makes the simulated call auditable.
    """

    sender: SendCallback
    capability: ClassVar[str] = "infocarry-fake-delete-transport-v1"

    def __post_init__(self) -> None:
        if not callable(self.sender):
            raise TypeError("fake delete transport requires a callable sender")

    def send(
        self,
        transaction: Any,
        binding: Any,
        *,
        deadline: float,
        cancelled: Optional[CancelledCallback],
        progress: Optional[ProgressCallback],
    ) -> int:
        if not isinstance(deadline, (int, float)) or isinstance(deadline, bool) or not math.isfinite(deadline):
            raise ValueError("fake delete transport requires a finite deadline")
        return self.sender(
            transaction,
            binding,
            deadline=deadline,
            cancelled=cancelled,
            progress=progress,
        )


class GeneralizedDeleteWorkflowError(RuntimeError):
    """Terminal workflow error carrying durable stage and retry information."""

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
        self.audit = dict(audit or {})
        self.audit.setdefault("automatic_retry_allowed", False)


@dataclass(frozen=True)
class GeneralizedDeleteWorkflowResult:
    candidate: GeneralizedDeleteCandidate
    authorization: GeneralizedDeleteAuthorization
    before_backup: VerifiedBackup
    after_backup: VerifiedBackup
    completion: int
    verification: GeneralizedDeleteVerification
    audit: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return dict(self.audit)


def _check_cancelled(cancelled: Optional[CancelledCallback]) -> None:
    if cancelled is not None and cancelled():
        raise TransferCancelledError("delete workflow cancelled before device change")


def _same_preview(left: GeneralizedDeleteCandidate, right: GeneralizedDeleteCandidate) -> bool:
    return left.to_dict() == right.to_dict()


def _safe_cancel_error(exc: BaseException, stage: str) -> GeneralizedDeleteWorkflowError:
    return GeneralizedDeleteWorkflowError(
        str(exc),
        stage=stage,
        state="cancelled_before_transaction",
        write_started=False,
        audit={
            "state": "cancelled_before_transaction",
            "stage": stage,
            "device_change": "none_started",
            "automatic_retry_allowed": False,
        },
    )


class GuardedGeneralizedDeleteWorkflow:
    """Run one complete fake deletion sequence with no live transport access.

    The injected fake transport must cooperate with the supplied deadline.
    This class does not claim to forcibly stop a callback that hangs forever.
    """

    def __init__(
        self,
        capture: CaptureCallback,
        transport: FakeDeleteTransport,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not callable(capture) or not isinstance(transport, FakeDeleteTransport):
            raise TypeError("capture and an explicit FakeDeleteTransport are required")
        if not callable(clock):
            raise TypeError("fake workflow clock must be callable")
        self._capture = capture
        self._transport = transport
        self._clock = clock

    def run(
        self,
        *,
        backup_destination: Path,
        post_delete_destination: Path,
        target_path: str,
        target_record_offset: int,
        confirmation: str,
        preview: Optional[GeneralizedDeleteCandidate] = None,
        fake_transport: bool = False,
        cancelled: Optional[CancelledCallback] = None,
        progress: Optional[ProgressCallback] = None,
        now: Optional[datetime] = None,
        max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
        timeout_seconds: float = 30.0,
    ) -> GeneralizedDeleteWorkflowResult:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise GeneralizedDeleteWorkflowError(
                "fake delete workflow requires a finite positive timeout",
                stage="transport",
                state="failed",
            )
        if fake_transport is not True:
            raise GeneralizedDeleteWorkflowError(
                "guarded generalized delete requires fake_transport=True",
                stage="transport",
                state="failed",
            )
        try:
            _check_cancelled(cancelled)
        except TransferCancelledError as exc:
            raise _safe_cancel_error(exc, "preparation") from exc

        try:
            before = capture_and_verify_fresh_backup(
                backup_destination,
                lambda destination: self._capture(
                    destination, cancelled=cancelled, progress=progress
                ),
                now=None,
                max_age_seconds=max_age_seconds,
            )
        except Exception as exc:
            if isinstance(exc, TransferCancelledError) or isinstance(exc.__cause__, TransferCancelledError):
                cause = exc if isinstance(exc, TransferCancelledError) else exc.__cause__
                raise _safe_cancel_error(cause, "fresh_backup") from exc
            raise GeneralizedDeleteWorkflowError(
                f"fresh backup failed; no transaction started: {exc}",
                stage="fresh_backup",
                state="failed",
                audit={"state": "failed", "device_change": "none_started"},
            ) from exc

        try:
            _check_cancelled(cancelled)
            current = build_generalized_delete_candidate(
                before.directory,
                target_path,
                target_record_offset,
                now=None,
                max_age_seconds=max_age_seconds,
            )
        except TransferCancelledError as exc:
            raise _safe_cancel_error(exc, "candidate") from exc
        except Exception as exc:
            raise GeneralizedDeleteWorkflowError(
                f"offline delete candidate failed: {exc}",
                stage="candidate",
                state="failed",
                audit={"state": "failed", "device_change": "none_started"},
            ) from exc

        if preview is not None and not _same_preview(preview, current):
            raise GeneralizedDeleteWorkflowError(
                "fresh backup or target no longer matches the displayed preview",
                stage="preview_revalidation",
                state="failed",
                audit={
                    "state": "failed",
                    "device_change": "none_started",
                    "preview": preview.to_dict(),
                    "fresh_candidate": current.to_dict(),
                },
            )

        try:
            _check_cancelled(cancelled)
            authorization = authorize_generalized_delete(
                current,
                confirmation=confirmation,
            )
            binding = bind_generalized_delete_sender(
                authorization,
                current,
                now=None,
                max_age_seconds=max_age_seconds,
            )
        except TransferCancelledError as exc:
            raise _safe_cancel_error(exc, "authorization") from exc
        except Exception as exc:
            raise GeneralizedDeleteWorkflowError(
                f"delete authorization failed: {exc}",
                stage="authorization",
                state="failed",
                audit={"state": "failed", "device_change": "none_started", "candidate": current.to_dict()},
            ) from exc

        if progress is not None:
            progress("Delete authorized; sending once through fake transport", 0, current.transaction.payload_length)
        try:
            deadline = self._clock() + timeout_seconds
            if not math.isfinite(deadline) or self._clock() > deadline:
                raise TransferTimeoutError("delete transaction deadline expired before transmission")
        except Exception as exc:
            raise GeneralizedDeleteWorkflowError(
                f"delete transfer did not start before its deadline: {exc}",
                stage="write",
                state="failed",
                write_started=False,
                audit={
                    "state": "failed",
                    "stage": "write",
                    "device_change": "none_started",
                    "write_started": False,
                    "primary_error": str(exc),
                    "automatic_retry_allowed": False,
                },
            ) from exc
        try:
            completion = self._transport.send(
                current.transaction,
                binding,
                deadline=deadline,
                cancelled=cancelled,
                progress=progress,
            )
            if isinstance(completion, bool) or not isinstance(completion, int):
                raise RuntimeError("fake sender returned missing or malformed completion")
            if completion != 0:
                raise RuntimeError(f"fake sender returned nonzero completion 0x{completion:04x}")
            if self._clock() > deadline:
                raise TransferTimeoutError("delete transaction exceeded its finite deadline")
        except Exception as exc:
            assessment = getattr(exc, "write_failure_assessment", None)
            has_assessment = assessment is not None
            # A callback was invoked after authorization.  Unless it explicitly
            # proves that the first request was not issued, its device outcome
            # is conservatively indeterminate.
            started = bool(getattr(assessment, "write_started", False)) if has_assessment else True
            state = "indeterminate_after_transaction_start" if started else "failed"
            raise GeneralizedDeleteWorkflowError(
                f"fake delete transfer stopped; no automatic retry: {exc}",
                stage="write",
                state=state,
                write_started=started,
                audit={
                    "state": state,
                    "stage": "write",
                    "device_change": getattr(assessment, "device_outcome", "indeterminate" if started else "not_started"),
                    "write_started": started,
                    "primary_error": getattr(assessment, "primary_error", str(exc)),
                    "automatic_retry_allowed": False,
                    "candidate": current.to_dict(),
                    "authorization": authorization.to_dict(),
                },
            ) from exc

        try:
            after = capture_and_verify_fresh_backup(
                post_delete_destination,
                lambda destination: self._capture(
                    destination, cancelled=cancelled, progress=progress
                ),
                now=None,
                max_age_seconds=max_age_seconds,
            )
            verification = verify_generalized_delete_readback(
                current,
                after.directory,
                completion=completion,
                now=None,
                max_age_seconds=max_age_seconds,
            )
        except Exception as exc:
            raise GeneralizedDeleteWorkflowError(
                f"post-delete read-back failed; no automatic retry: {exc}",
                stage="post_delete_readback",
                state="indeterminate_after_transaction_start",
                write_started=True,
                audit={
                    "state": "indeterminate_after_transaction_start",
                    "stage": "post_delete_readback",
                    "device_change": "indeterminate",
                    "write_started": True,
                    "completion": completion,
                    "primary_error": str(exc),
                    "automatic_retry_allowed": False,
                    "candidate": current.to_dict(),
                    "authorization": authorization.to_dict(),
                },
            ) from exc

        audit = current.to_dict()
        audit.update(
            {
                "state": "readback_verified",
                "workflow": {
                    "states": [
                        "previewed",
                        "authorized",
                        "simulated_transfer_completed",
                        "readback_verified",
                    ],
                    "fake_transport": True,
                    "device_change": "simulated_only",
                    "automatic_retry_allowed": False,
                },
                "authorization": authorization.to_dict(),
                "completion": f"0x{completion:04x}",
                "verification": verification.to_dict(),
            }
        )
        if progress is not None:
            progress("Delete fake read-back verified", 1, 1)
        return GeneralizedDeleteWorkflowResult(
            candidate=current,
            authorization=authorization,
            before_backup=before,
            after_backup=after,
            completion=completion,
            verification=verification,
            audit=audit,
        )


__all__ = [
    "FakeDeleteTransport",
    "GuardedGeneralizedDeleteWorkflow",
    "GeneralizedDeleteWorkflowError",
    "GeneralizedDeleteWorkflowResult",
]


# The exact experimental root-TXT operation uses the existing sealed root
# operation interface and canonical coordinator. It implements no transport,
# claim store, marker or lock. Device Library reuses this exact gate.


EXPERIMENTAL_ROOT_TXT_DELETE_PROFILE = "vnw-v15-experimental-exact-root-txt-delete-v1"
ROOT_TXT_DELETE_CONFIRMATION = f"DELETE {FIXTURE_FILENAME} ONCE"


def build_experimental_root_txt_delete(backup_directory, *, max_age_seconds=None):
    """Offline exact fixture admission; no device or safety-state access."""
    backup = verify_fresh_backup(Path(backup_directory), max_age_seconds=max_age_seconds)
    parsed = parse_backup_blob(_blob(backup))
    matches = [r for r in parsed.records
               if parsed.paths.get(r.offset) == ("root", Path(FIXTURE_FILENAME).stem)
               and r.extension == "txt"]
    if len(matches) != 1 or matches[0].kind != "file":
        raise ValueError("exact unique ordinary root-TXT fixture is required")
    target = matches[0]
    if parsed.payload_parts(target)[1] != FIXTURE_BYTES:
        raise ValueError("fixture is not the exact 29-byte payload")
    return build_generalized_delete_candidate(
        backup.directory, FIXTURE_PATH, target.offset, max_age_seconds=max_age_seconds,
        preserve_unreferenced_auxiliary_state=True,
    )


@dataclass(frozen=True)
class RootTxtDeleteCandidate:
    backup_directory: Path
    candidate_blob: bytes
    transaction: ProspectiveWriteTransaction
    audit_json: bytes

    @property
    def core(self):
        # Reconstruct from verified immutable inputs rather than exposing a
        # mutable parsed-tree/audit object as an authorization authority.
        return build_experimental_root_txt_delete(self.backup_directory)

    @property
    def candidate_blob_sha256(self):
        return _sha(self.candidate_blob)

    @property
    def transaction_sha256(self):
        return self.transaction.concatenated_sha256

    def audit_dict(self):
        return json.loads(self.audit_json)


@dataclass(frozen=True)
class RootTxtDeleteAuthorizationCore:
    binding: GeneralizedDeleteAuthorization
    backup_directory: Path
    source_path: Path
    confirmation_phrase: str = ROOT_TXT_DELETE_CONFIRMATION
    confirmation_policy: str = "explicit_phrase"

    def revalidate(self, candidate, *, now=None, max_age_seconds=DEFAULT_MAX_AGE_SECONDS):
        self.binding.revalidate(candidate, now=now, max_age_seconds=max_age_seconds)


@dataclass(frozen=True)
class RootTxtDeleteAuthorization:
    core: RootTxtDeleteAuthorizationCore

    def require_same_candidate(self, candidate):
        self.core.binding.require_same_candidate(candidate.core)
        if (candidate.candidate_blob != candidate.core.candidate_blob
                or candidate.transaction != candidate.core.transaction):
            raise ValueError("frozen Delete differs from independently reconstructed candidate")

    def to_dict(self):
        return {"format": "infocarry-experimental-root-txt-delete-authorization-v1",
                "profile": EXPERIMENTAL_ROOT_TXT_DELETE_PROFILE,
                "confirmation_phrase": ROOT_TXT_DELETE_CONFIRMATION,
                "inner_binding": self.core.binding.to_dict()}


@dataclass(frozen=True)
class RootTxtDeleteBundle(RootTxtPlacementBundle):
    """Reuse H2's immutable bundle and execution-equivalence lifecycle."""

    @property
    def operation_id(self):
        return "root-txt-delete-" + self.seal_sha256

    @property
    def operation_profile(self):
        return EXPERIMENTAL_ROOT_TXT_DELETE_PROFILE

    @property
    def result_format(self):
        return "infocarry-experimental-root-txt-delete-result-v1"

    @property
    def terminal_format(self):
        return "infocarry-experimental-root-txt-delete-terminal-resolution-v1"

    def verify_execution_equivalence(self, before, capacity):
        result = super().verify_execution_equivalence(before, capacity)
        result.pop("target_absent")
        result["target_present_and_exact"] = True
        return result

    def _envelope(self):
        return {"format": "infocarry-experimental-root-txt-delete-bundle-v1",
                "profile": EXPERIMENTAL_ROOT_TXT_DELETE_PROFILE,
                "device": list(self.device_identity), "target": FIXTURE_PATH,
                "fixture_length": 29, "fixture_sha256": FIXTURE_SHA256,
                "source_artifact": self.source_artifact.to_dict(),
                "backup_artifact": self.backup_artifact.to_dict(),
                "baseline_state_identity_sha256": self.baseline_state_identity_sha256,
                "capacity_artifact": self.capacity_artifact.to_dict(),
                "capacity_response_sha256": self.capacity_response_sha256,
                "candidate_artifact": self.candidate_artifact.to_dict(),
                "candidate_sha256": self.candidate_blob_sha256,
                "candidate_audit_sha256": _sha(self.candidate.audit_json),
                "transaction_sha256": self.transaction_sha256,
                "authorization_sha256": self.authorization_sha256,
                "confirmation_phrase": ROOT_TXT_DELETE_CONFIRMATION,
                "timestamp_policy": "preserve_surviving_timestamps",
                "no_retry": True, "one_sender": True,
                "post_backup": "complete_independent_exact_readback"}

    def _exact_candidate_binding(self):
        core = self.candidate.core
        if self.candidate.audit_json != _json(core.to_dict()):
            raise ValueError("frozen Delete audit differs from independently reconstructed candidate")
        if core.target_path != FIXTURE_PATH or core.target_payload_sha256 != FIXTURE_SHA256:
            raise ValueError("Delete target differs from exact experimental fixture")
        if self.candidate.candidate_blob != core.candidate_blob or self.candidate.transaction != core.transaction:
            raise ValueError("sealed candidate or transaction differs from derived Delete")
        if self.candidate_artifact.sha256 != self.candidate_blob_sha256:
            raise ValueError("Delete candidate artifact differs")
        self.authorization.require_same_candidate(self.candidate)

    def verify_seal(self):
        if type(self.runtime) is not PinnedRootTxtRuntime:
            raise ValueError("Delete requires the established pinned runtime")
        if type(self.candidate) is not RootTxtDeleteCandidate or type(self.authorization) is not RootTxtDeleteAuthorization:
            raise ValueError("Delete bundle contains a different operation type")
        if type(self.capacity_response) is not NativeCapacityResponse:
            raise ValueError("Delete requires verified native capacity evidence")
        if self.authorization.core.confirmation_phrase != ROOT_TXT_DELETE_CONFIRMATION:
            raise ValueError("Delete confirmation changed")
        if self.authorization.core.confirmation_policy != "explicit_phrase":
            raise ValueError("Delete requires the exact explicit confirmation policy")
        for artifact in (self.source_artifact, self.candidate_artifact,
                         self.capacity_artifact, self.backup_artifact, self.seal_artifact):
            artifact.verify()
        if self.source_path.name != FIXTURE_FILENAME or self.source_path.read_bytes() != FIXTURE_BYTES:
            raise ValueError("deleted fixture source copy changed")
        if self.candidate.backup_directory != self.before_backup.directory or self.authorization.core.backup_directory != self.before_backup.directory:
            raise ValueError("Delete baseline was rebound")
        if self.capacity_artifact.sha256 != _sha(self.capacity_response.raw_response):
            raise ValueError("Delete native capacity changed")
        if load_preserved_artifact(self.transaction_directory) != self.candidate.transaction:
            raise ValueError("preserved Delete transaction changed")
        if _json(self._envelope()) != self.envelope_json or _sha(self.envelope_json) != self.seal_sha256 or self.seal_artifact.sha256 != self.seal_sha256:
            raise ValueError("frozen Delete identity changed")
        self._exact_candidate_binding()
        # Deletion shrinks the image; the additive capacity-length helper
        # deliberately rejects shrinkage and is not used to assert growth.
        if max(len(_blob(self.before_backup)), len(self.candidate.candidate_blob)) > self.capacity_response.capacity_limit_bytes:
            raise ValueError("Delete baseline/candidate exceeds native capacity")
        self.authorization.core.revalidate(self.candidate.core, max_age_seconds=None)

    def review_dict(self):
        return {"format": "infocarry-experimental-root-txt-delete-review-v1",
                "owner_identity": OwnerAuthorizedOperationIdentity.from_bundle(self).to_dict(),
                "device_model": "Sony VNW-V15", "operation": "Delete",
                "target": FIXTURE_PATH, "fixture_length": 29, "fixture_sha256": FIXTURE_SHA256,
                "fixture_verified": True, "fresh_backup_verified": True,
                "candidate_prepared": True, "confirmation_phrase": ROOT_TXT_DELETE_CONFIRMATION,
                "physical_operation_count": 1, "automatic_retry_allowed": False,
                "profile": EXPERIMENTAL_ROOT_TXT_DELETE_PROFILE}

    def verify_readback(self, after, *, completion, now=None, max_age_seconds=None):
        self.verify_seal()
        verification = verify_generalized_delete_readback(
            self.candidate.core, after.directory, completion=completion,
            now=now, max_age_seconds=max_age_seconds,
        )
        # The existing verifier requires byte-exact candidate model and
        # fixed-state blocks, thereby checking every survivor timestamp too.
        report = verification.to_dict()
        report["before_backup"] = self.before_backup.to_dict()
        report["after_backup"] = after.to_dict()
        return RootTxtReadback(_json({"independent_complete_backup_verification": report,
            "exact_path_and_payload_verification": {
                "only_removed_path": FIXTURE_PATH, "added_paths": [],
                "surviving_timestamps_preserved": True, "unrelated_payloads_unchanged": True,
                "protected_auxiliary_associations_preserved": True}}))

    def write_operation_report(self, root, audit, after):
        if audit.get("execution_claim", {}).get("sender_marker", {}).get("resolved") is not True:
            raise ValueError("Delete report requires terminal marker resolution")
        path = Path(root) / "root-txt-delete-report.json"
        _write_json(path, {"format": "infocarry-experimental-root-txt-delete-result-v1",
                          "operation": "Delete", "target": FIXTURE_PATH,
                          "profile": EXPERIMENTAL_ROOT_TXT_DELETE_PROFILE,
                          "verification": self.verify_readback(after, completion=0).to_dict()})
        return path

    def reconcile_result(self, result):
        if result.preflight is not self or result.candidate is not self.candidate or result.authorization is not self.authorization:
            raise ValueError("Delete result differs from frozen operation")
        if result.audit.get("workflow", {}).get("sender_calls") != 1:
            raise ValueError("Delete sender count is not exactly one")
        expected = self.verify_readback(result.after_backup, completion=result.completion).to_dict()
        def stable(value):
            copy = json.loads(_json(value))
            report = copy.get("independent_complete_backup_verification", {})
            for label in ("before_backup", "after_backup"):
                report.get(label, {}).pop("verified_at_utc", None)
            return copy
        if stable(result.verification.to_dict()) != stable(expected) or stable(result.audit["verification"]) != stable(expected):
            raise ValueError("Delete independent readback reconciliation differs")
        return result


class ExperimentalRootTxtDeleteFacade(RootTxtPlacementFacade):
    """Exact Delete admission, using the existing owner/coordinator/sender."""

    def prepare(self, *, target_path=FIXTURE_PATH, device_model="VNW-V15",
                max_age_seconds=DEFAULT_MAX_AGE_SECONDS, cancelled=None, progress=None):
        if self.stop_approved_rebuild():
            raise ValueError("approved Delete cannot refresh or adopt a new candidate")
        try:
            if self._prepared_operation is not None:
                raise ValueError("discard the previous operation before preparing another")
            if target_path != FIXTURE_PATH or device_model != "VNW-V15":
                raise ValueError("only the exact VNW-V15 root-TXT fixture deletion is admitted")
            if max_age_seconds != DEFAULT_MAX_AGE_SECONDS:
                raise ValueError("Delete preparation requires the established fresh-backup policy")
            if cancelled is not None and cancelled():
                raise TransferCancelledError("Delete cancelled before preparation")
            runtime = self.runtime
            owner = PersistentWriteSafetyOwner(execution_claim_store=runtime.execution_claim_store,
                indeterminate_write_lock=runtime.indeterminate_write_lock)
            owner.inspect_execution_boundary()
            if runtime.detect_device() != (0x054c, 0x001e):
                raise ValueError("Delete device is not VNW-V15")
            capacity = runtime.query_capacity()
            if not isinstance(capacity, NativeCapacityResponse):
                raise ValueError("fresh native capacity is required")
            root = Path(runtime.evidence_namespace) / ("prepared-root-txt-delete-" + uuid4().hex)
            root.mkdir(parents=True)
            if progress is not None:
                progress("Preparing backup", 0, 1)
            before = capture_and_verify_fresh_backup(root / "backup-baseline",
                lambda destination: runtime.capture(destination, cancelled=cancelled, progress=progress))
            if cancelled is not None and cancelled():
                raise TransferCancelledError("Delete cancelled after backup, before approval")
            if progress is not None:
                progress("Validating operation", 0, 1)
            runtime.assert_same_session(runtime.session_binding_token)
            core = build_experimental_root_txt_delete(before.directory, max_age_seconds=max_age_seconds)
            candidate = RootTxtDeleteCandidate(before.directory, core.candidate_blob,
                core.transaction, _json(core.to_dict()))
            source = root / FIXTURE_FILENAME
            with source.open("xb") as output:
                output.write(FIXTURE_BYTES)
            candidate_path = root / "candidate.bin"
            with candidate_path.open("xb") as output:
                output.write(candidate.candidate_blob)
            transaction_path = root / "transaction"
            candidate.transaction.preserve(transaction_path, source="experimental-exact-root-txt-delete")
            capacity_path = root / "capacity-0019.bin"
            with capacity_path.open("xb") as output:
                output.write(capacity.raw_response)
            binding = authorize_generalized_delete(core, confirmation=DELETE_GENERALIZED_CONFIRMATION_PHRASE)
            authorization = RootTxtDeleteAuthorization(RootTxtDeleteAuthorizationCore(binding, before.directory, source))
            seal_path = root / "operation-bundle.json"
            provisional = RootTxtDeleteBundle(runtime, before, capacity, candidate, authorization,
                OperationArtifact.file(source), OperationArtifact.file(candidate_path),
                OperationArtifact.file(capacity_path), OperationArtifact.backup_manifest(before.directory),
                OperationArtifact(str(seal_path), "0" * 64, "file_bytes", 0),
                transaction_path, b"", "0" * 64, runtime.session_binding_token, None)
            envelope = _json(provisional._envelope())
            with seal_path.open("xb") as output:
                output.write(envelope)
            bundle = replace(provisional, envelope_json=envelope, seal_sha256=_sha(envelope),
                             seal_artifact=OperationArtifact.file(seal_path))
            bundle.verify_seal()
            if cancelled is not None and cancelled():
                raise TransferCancelledError("Delete cancelled before approval")
            self._prepared_operation = bundle
            return bundle
        except BaseException:
            self.discard_prepared_operation()
            raise

    def adopt_prepared_operation(self, prepared):
        if self.owner_approval_accepted or type(prepared) is not RootTxtDeleteBundle or prepared.runtime is not self.runtime:
            self.discard_prepared_operation()
            raise ValueError("Delete cannot adopt a different or already-approved operation")
        prepared.verify_seal()
        self._prepared_operation = prepared
