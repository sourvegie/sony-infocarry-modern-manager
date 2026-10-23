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
    GeneralizedDeleteError,
    GeneralizedDeleteCandidate,
    GeneralizedDeleteVerification,
    authorize_generalized_delete,
    bind_generalized_delete_sender,
    build_generalized_delete_candidate,
    build_root_bmp_delete_candidate,
    verify_generalized_delete_readback,
)
from .protocol import TransferCancelledError, TransferTimeoutError
from .write_gate import DEFAULT_MAX_AGE_SECONDS, VerifiedBackup, capture_and_verify_fresh_backup

import json
from uuid import uuid4
from types import MappingProxyType
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


ROOT_TXT_DELETE_HOST_PROFILE = "vnw-v15-host-root-txt-delete-v1"
ROOT_TXT_DELETE_LIVE_PROFILE = "vnw-v15-unread-root-txt-delete-v1"
ROOT_TXT_DELETE_VALIDATION_PROFILE = "vnw-v15-disposable-root-txt-delete-validation-v1"
ROOT_BMP_DELETE_LIVE_PROFILE = "vnw-v15-unread-root-bmp-delete-v1"
ROOT_BMP_DELETE_VALIDATION_PROFILE = "vnw-v15-exact-disposable-root-bmp-delete-validation-v1"
ROOT_TXT_DELETE_VALIDATION_FILES = MappingProxyType({
    "root\\IC_P18_043_DELETE_A.txt": b"Disposable P18-043 root TXT A.\r\n",
    "root\\IC_P18_043_DELETE_B.txt": b"Disposable P18-043 root TXT B: alignment case-01.\r\n",
    "root\\IC_P18_045_DELETE_C.txt": b"Disposable P18-045 root TXT C++.\r\n",
})


class RootTxtDeleteAdmissionError(ValueError):
    stage = "admission"


def root_txt_delete_execution_supported(core):
    """P18-041/044/045 prove the unread profile; read TXT remains host-only.

    The supplied core must already pass build_root_txt_delete's model, name,
    reference, allocation and protected-state checks. Position and payload
    length follow those checked invariants, rather than a fixture allowlist.
    """
    return core.baseline.record_at(core.target_record_offset).flag == 0xe0


def _root_bmp_fixture_supported(core, target_paths):
    """Validate a named disposable profile from source bytes, never audit labels."""
    try:
        if (core.target_path not in target_paths or core.target_extension != "bmp"
                or core.target_record_offset != ROOT_BMP_DELETE_VALIDATION_OFFSETS[core.target_path]):
            return False
        target = core.baseline.record_at(core.target_record_offset)
        prefix, payload = core.baseline.payload_parts(target)
        if core.target_path == ROOT_BMP_DELETE_EXPANSION_PATH and not _root_bmp_expansion_anchor_present(core.baseline):
            return False
        return (target.kind == "file" and target.extension == "bmp"
                and target.flag == 0xe0 and target.field_10_be32 == 0xffffffff
                and target.field_14_be32 == 0x100 and prefix == b"\xff" * 16
                and payload == ROOT_BMP_DELETE_VALIDATION_FILES[core.target_path])
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def _root_bmp_expansion_anchor_present(parsed):
    """The already proven disposable TXT anchor fixes B's distinct root slot."""
    try:
        anchor = parsed.record_at(0x680)
        path = ("root", "IC_P18_043_DELETE_A")
        return (parsed.paths.get(0x680) == path
                and sum(p == path for p in parsed.paths.values()) == 1
                and anchor.kind == "file" and anchor.extension == "txt"
                and anchor.flag in (0xe0, 0x20) and anchor.field_14_be32 == 0x200
                and parsed.payload_parts(anchor)[1] == ROOT_TXT_DELETE_VALIDATION_FILES["root\\IC_P18_043_DELETE_A.txt"])
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def root_bmp_delete_execution_supported(core):
    """P18-046/047 support the conservative unread root-BMP envelope.

    Reconstruct from complete source evidence, not mutable audits or parsed
    caches. Filename, payload and position vary within the checked invariants;
    read/32-prefix states and nested files do not enter this live profile.
    """
    try:
        if type(core) is not GeneralizedDeleteCandidate or core.target_extension != "bmp":
            return False
        expected = build_root_bmp_delete(core.backup.directory, core.target_path,
            target_record_offset=core.target_record_offset)
        return (core.baseline.data == expected.baseline.data
                and core.candidate_blob == expected.candidate_blob
                and core.transaction == expected.transaction
                and core.fixed_state == expected.fixed_state
                and core.target_payload_sha256 == expected.target_payload_sha256)
    except (OSError, ValueError, RuntimeError, AttributeError, TypeError):
        return False


def root_bmp_delete_validation_supported(core):
    """Retained exact B experiment, including its required disposable anchor."""
    return _root_bmp_fixture_supported(core, (ROOT_BMP_DELETE_EXPANSION_PATH,))


def build_root_bmp_delete(backup_directory, target_path, *, target_record_offset=None,
                          max_age_seconds=None):
    """Conservative ordinary root-BMP preparation, with no execution authority.

    Admit unique safe CP932 identities and the observed unread/all-FF 16-byte
    native prefix/opaque-field profile. The canonical 237x320 monochrome BMP
    validator and existing candidate/protected-state checks remain authoritative.
    The guarded Device Library bundle separately binds live execution authority.
    """
    backup = verify_fresh_backup(Path(backup_directory), max_age_seconds=max_age_seconds)
    if backup.device_identity != ("0x054c", "0x001e"):
        raise RootTxtDeleteAdmissionError("root BMP Delete requires the characterized VNW-V15 model")
    parsed = parse_backup_blob(_blob(backup))
    if not isinstance(target_path, str) or len(target_path.split("\\")) != 2 or not target_path.startswith("root\\"):
        raise RootTxtDeleteAdmissionError("only one ordinary root-level BMP file is admitted")
    matches = [r for r in parsed.records if parsed.paths.get(r.offset) is not None
               and "\\".join(parsed.paths[r.offset]) + ("." + r.extension if r.extension else "") == target_path]
    if len(matches) != 1:
        raise RootTxtDeleteAdmissionError("root BMP target is missing or ambiguous")
    target = matches[0]
    if (target.kind != "file" or target.extension != "bmp" or target.flag != 0xe0
            or target.field_10_be32 != 0xffffffff or target.field_14_be32 != 0x100
            or parsed.payload_parts(target)[0] != b"\xff" * 16):
        raise RootTxtDeleteAdmissionError("root BMP requires the observed unread/16-byte all-FF prefix profile")
    if target_record_offset is not None and (type(target_record_offset) is not int or target.offset != target_record_offset):
        raise RootTxtDeleteAdmissionError("root BMP selected metadata identity changed")
    try:
        return build_root_bmp_delete_candidate(backup.directory, target_path, target.offset,
                                               max_age_seconds=max_age_seconds)
    except GeneralizedDeleteError as exc:
        raise RootTxtDeleteAdmissionError("Root BMP native identity, payload, protected state or structural invariants are unsupported") from exc


def validate_root_txt_delete_name(name):
    """The established NUL-terminated native name field, with no path syntax."""
    if (not isinstance(name, str) or name in {"", ".", "..", "root"} or name != name.strip()
            or any(ord(c) < 32 or ord(c) == 127 or c in '\\/.:<>"|?*' for c in name)):
        raise ValueError("root TXT name contains unsupported root/system/path syntax")
    try:
        encoded = name.encode("cp932", "strict")
    except UnicodeError as exc:
        raise ValueError("root TXT name is not exactly CP932 representable") from exc
    if not 1 <= len(encoded) <= 39 or encoded.decode("cp932", "strict") != name:
        raise ValueError("root TXT name must roundtrip within the 39-byte native field")
    return encoded


def build_root_txt_delete(backup_directory, target_path, *, target_record_offset=None, max_age_seconds=None):
    """General root-TXT host preparation; not permission to execute it."""
    backup = verify_fresh_backup(Path(backup_directory), max_age_seconds=max_age_seconds)
    if backup.device_identity != ("0x054c", "0x001e"):
        raise RootTxtDeleteAdmissionError("root TXT Delete requires the characterized VNW-V15 model")
    parsed = parse_backup_blob(_blob(backup))
    if not isinstance(target_path, str) or len(target_path.split("\\")) != 2 or not target_path.startswith("root\\"):
        raise RootTxtDeleteAdmissionError("only one ordinary root-level TXT file is admitted")
    def path(record):
        parts = parsed.paths.get(record.offset)
        return "\\".join(parts) + ("." + record.extension if record.extension else "") if parts else None
    matches = [r for r in parsed.records if path(r) == target_path]
    if len(matches) != 1:
        raise RootTxtDeleteAdmissionError("root TXT target is missing or ambiguous")
    target = matches[0]
    if (target.kind != "file" or target.extension != "txt"
            or target.flag not in {0xe0, 0x20} or target.field_14_be32 != 0x200):
        raise RootTxtDeleteAdmissionError("root TXT target requires known read/unread state and the evidenced 32-byte prefix")
    try:
        encoded = validate_root_txt_delete_name(target.name)
    except ValueError as exc:
        raise RootTxtDeleteAdmissionError(str(exc)) from exc
    raw_name = bytes.fromhex(target.raw_hex)[24:64]
    if b"\0" not in raw_name or raw_name.split(b"\0", 1)[0] != encoded:
        raise RootTxtDeleteAdmissionError("root TXT native name is not an exact NUL-terminated CP932 identity")
    folded = target_path.casefold()
    native_identity = tuple(part.casefold() for part in parsed.paths[target.offset])
    if (sum(path(r) is not None and path(r).casefold() == folded for r in parsed.records) != 1
            or sum(tuple(part.casefold() for part in parts) == native_identity for parts in parsed.paths.values()) != 1):
        raise RootTxtDeleteAdmissionError("root TXT target has an ambiguous case-insensitive identity")
    if target_record_offset is not None and (type(target_record_offset) is not int or target.offset != target_record_offset):
        raise RootTxtDeleteAdmissionError("root TXT selected metadata identity changed")
    try:
        return build_generalized_delete_candidate(backup.directory, target_path, target.offset,
            max_age_seconds=max_age_seconds, preserve_unreferenced_auxiliary_state=True)
    except GeneralizedDeleteError as exc:
        raise RootTxtDeleteAdmissionError("Root TXT protected state or structural invariants are unsupported") from exc


@dataclass(frozen=True)
class RootTxtDeleteCandidate:
    backup_directory: Path
    candidate_blob: bytes
    transaction: ProspectiveWriteTransaction
    audit_json: bytes
    target_path: str = FIXTURE_PATH
    target_record_offset: int | None = None
    exact_fixture: bool = True
    target_extension: str = "txt"
    general_bmp: bool = False

    @property
    def core(self):
        # Reconstruct from verified immutable inputs rather than exposing a
        # mutable parsed-tree/audit object as an authorization authority.
        if self.exact_fixture:
            return build_experimental_root_txt_delete(self.backup_directory)
        if self.target_extension == "bmp":
            if self.general_bmp:
                return build_root_bmp_delete(self.backup_directory, self.target_path,
                    target_record_offset=self.target_record_offset)
            return build_experimental_root_bmp_delete(self.backup_directory, target_path=self.target_path)
        return build_root_txt_delete(self.backup_directory, self.target_path,
            target_record_offset=self.target_record_offset)

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
    profile_id: str = EXPERIMENTAL_ROOT_TXT_DELETE_PROFILE

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
        return {"format": ("infocarry-experimental-root-bmp-delete-authorization-v1"
                            if self.core.profile_id in {ROOT_BMP_DELETE_VALIDATION_PROFILE, ROOT_BMP_DELETE_LIVE_PROFILE}
                            else "infocarry-experimental-root-txt-delete-authorization-v1"),
                "profile": self.core.profile_id,
                "confirmation_phrase": self.core.confirmation_phrase,
                "inner_binding": self.core.binding.to_dict()}


@dataclass(frozen=True)
class RootTxtDeleteBundle(RootTxtPlacementBundle):
    """Reuse H2's immutable bundle and execution-equivalence lifecycle."""

    validation_only: bool = False
    validation_bmp_only: bool = False

    @property
    def target_path(self):
        return self.candidate.target_path

    @property
    def expected_folder_name(self):
        return self.target_path.split("\\")[-1]

    @property
    def owner_confirmation_phrase(self):
        return None if self.candidate.exact_fixture else self.authorization.core.confirmation_phrase

    @property
    def execution_available(self):
        if self.candidate.target_extension == "bmp":
            if self.candidate.general_bmp:
                return root_bmp_delete_execution_supported(self.candidate.core)
            return (self.validation_bmp_only
                    and _root_bmp_fixture_supported(self.candidate.core, ROOT_BMP_DELETE_VALIDATION_FILES))
        return root_txt_delete_execution_supported(self.candidate.core)

    def assert_execution_admitted(self):
        self.verify_seal()
        if not self.execution_available:
            raise ValueError("this Delete target is not physically validated; preparation only")

    @property
    def operation_id(self):
        if self.candidate.target_extension == "bmp":
            return "root-bmp-delete-" + self.seal_sha256
        return "root-txt-delete-" + self.seal_sha256

    @property
    def operation_profile(self):
        if self.candidate.target_extension == "bmp":
            return ROOT_BMP_DELETE_LIVE_PROFILE if self.candidate.general_bmp else ROOT_BMP_DELETE_VALIDATION_PROFILE
        return (EXPERIMENTAL_ROOT_TXT_DELETE_PROFILE if self.candidate.exact_fixture else
                ROOT_TXT_DELETE_VALIDATION_PROFILE if self.validation_only else
                ROOT_TXT_DELETE_LIVE_PROFILE if self.execution_available else ROOT_TXT_DELETE_HOST_PROFILE)

    @property
    def result_format(self):
        if self.candidate.target_extension == "bmp":
            return "infocarry-experimental-root-bmp-delete-result-v1"
        return "infocarry-experimental-root-txt-delete-result-v1"

    @property
    def terminal_format(self):
        if self.candidate.target_extension == "bmp":
            return "infocarry-experimental-root-bmp-delete-terminal-resolution-v1"
        return "infocarry-experimental-root-txt-delete-terminal-resolution-v1"

    def verify_execution_equivalence(self, before, capacity):
        self.assert_execution_admitted()
        result = super().verify_execution_equivalence(before, capacity)
        result.pop("target_absent")
        result["target_present_and_exact"] = True
        return result

    def _envelope(self):
        bmp = self.candidate.target_extension == "bmp"
        value = {"format": ("infocarry-experimental-root-bmp-delete-bundle-v1" if bmp
                             else "infocarry-experimental-root-txt-delete-bundle-v1"),
                "profile": self.operation_profile,
                "device": list(self.device_identity), "target": self.target_path,
                "fixture_length": self.source_artifact.size_bytes, "fixture_sha256": self.source_artifact.sha256,
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
                "confirmation_phrase": self.authorization.core.confirmation_phrase,
                "timestamp_policy": "preserve_surviving_timestamps",
                "no_retry": True, "one_sender": True,
                "post_backup": "complete_independent_exact_readback"}
        if bmp:
            value.update({"validation_bmp_only": self.validation_bmp_only,
                          "general_bmp": self.candidate.general_bmp,
                          "capability_status": "exact_disposable_physical_validation",
                          "target_record_offset": self.candidate.target_record_offset,
                          "target_profile": {"flag": "0xe0", "prefix_selector": "0x100",
                                             "prefix_bytes": 16}})
        if not self.candidate.exact_fixture:
            value.update({"validation_only": self.validation_only,
                          "validation_bmp_only": self.validation_bmp_only,
                          "execution_available": self.execution_available,
                          "target_record_offset": self.candidate.target_record_offset,
                          "capability_status": ("experimental_unread_root_bmp" if self.candidate.general_bmp else "exact_disposable_bmp_validation") if bmp else
                          "bounded_disposable_validation" if self.validation_only else
                          "experimental_unread_root_txt" if self.execution_available else "host_not_live_enabled"})
        return value

    def _consume_execution_claim(self, owner):
        self.assert_execution_admitted()
        return super()._consume_execution_claim(owner)

    def _exact_candidate_binding(self):
        core = self.candidate.core
        if self.candidate.audit_json != _json(core.to_dict()):
            raise ValueError("frozen Delete audit differs from independently reconstructed candidate")
        if self.candidate.exact_fixture:
            if core.target_path != FIXTURE_PATH or core.target_payload_sha256 != FIXTURE_SHA256:
                raise ValueError("Delete target differs from exact experimental fixture")
        elif self.candidate.target_extension == "bmp":
            if ((not self.candidate.general_bmp and (not self.validation_bmp_only or core.target_path not in ROOT_BMP_DELETE_VALIDATION_FILES))
                    or core.target_path != self.candidate.target_path
                    or core.target_record_offset != self.candidate.target_record_offset
                    or not self.execution_available):
                raise ValueError("BMP Delete differs from the frozen supported profile")
        elif core.target_path != self.candidate.target_path or core.target_record_offset != self.candidate.target_record_offset:
            raise ValueError("Delete target differs from frozen selected path/record")
        if core.target_payload_sha256 != self.source_artifact.sha256:
            raise ValueError("Delete source payload differs from the selected target")
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
        expected_phrase = ROOT_TXT_DELETE_CONFIRMATION if self.candidate.exact_fixture else f"DELETE {self.expected_folder_name} ONCE"
        if self.authorization.core.confirmation_phrase != expected_phrase:
            raise ValueError("Delete confirmation changed")
        if self.authorization.core.confirmation_policy != "explicit_phrase":
            raise ValueError("Delete requires the exact explicit confirmation policy")
        for artifact in (self.source_artifact, self.candidate_artifact,
                         self.capacity_artifact, self.backup_artifact, self.seal_artifact):
            artifact.verify()
        if (type(self.validation_only) is not bool or type(self.validation_bmp_only) is not bool
                or type(self.candidate.exact_fixture) is not bool or type(self.candidate.general_bmp) is not bool):
            raise ValueError("Delete admission flags must be exact booleans")
        if self.candidate.general_bmp and (self.candidate.target_extension != "bmp"
                or self.candidate.exact_fixture or self.validation_bmp_only or self.validation_only):
            raise ValueError("ordinary BMP scope conflicts with fixture validation")
        if self.candidate.exact_fixture:
            if self.validation_only or self.validation_bmp_only or self.source_path.name != FIXTURE_FILENAME or self.source_path.read_bytes() != FIXTURE_BYTES:
                raise ValueError("deleted fixture source copy or scope changed")
        elif self.candidate.target_extension == "bmp":
            if (self.validation_only or self.source_path.name != self.expected_folder_name
                    or _sha(self.source_path.read_bytes()) != self.candidate.core.target_payload_sha256
                    or (not self.candidate.general_bmp and (not self.validation_bmp_only
                        or self.target_path not in ROOT_BMP_DELETE_VALIDATION_FILES
                        or self.source_path.read_bytes() != ROOT_BMP_DELETE_VALIDATION_FILES[self.target_path]))):
                raise ValueError("BMP source copy or disposable scope changed")
        elif self.source_path.name != "selected-txt.bin" or _sha(self.source_path.read_bytes()) != self.candidate.core.target_payload_sha256:
            raise ValueError("selected TXT source copy changed")
        if self.validation_only:
            expected = ROOT_TXT_DELETE_VALIDATION_FILES.get(self.target_path)
            if expected is None or self.source_path.read_bytes() != expected:
                raise ValueError("validation permits only the predetermined disposable file and exact payload")
        if self.authorization.core.profile_id != self.operation_profile or self.authorization.core.source_path.resolve() != self.source_path:
            raise ValueError("Delete authorization scope or source path changed")
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
        bmp = self.candidate.target_extension == "bmp"
        return {"format": ("infocarry-experimental-root-bmp-delete-review-v1" if bmp
                            else "infocarry-experimental-root-txt-delete-review-v1"),
                "owner_identity": OwnerAuthorizedOperationIdentity.from_bundle(self).to_dict(),
                "device_model": "Sony VNW-V15", "operation": "Delete",
                "target": self.target_path, "fixture_length": self.source_artifact.size_bytes, "fixture_sha256": self.source_artifact.sha256,
                "fixture_verified": True, "fresh_backup_verified": True,
                "candidate_prepared": True, "confirmation_phrase": self.authorization.core.confirmation_phrase,
                "physical_operation_count": 1, "automatic_retry_allowed": False,
                "profile": self.operation_profile,
                "capability_status": ("Experimental unread root BMP" if self.candidate.general_bmp else "exact disposable BMP validation only") if bmp else None}

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
                "only_removed_path": self.target_path, "added_paths": [],
                "surviving_timestamps_preserved": True, "unrelated_payloads_unchanged": True,
                "protected_auxiliary_associations_preserved": True}}))

    def write_operation_report(self, root, audit, after):
        if audit.get("execution_claim", {}).get("sender_marker", {}).get("resolved") is not True:
            raise ValueError("Delete report requires terminal marker resolution")
        bmp = self.candidate.target_extension == "bmp"
        path = Path(root) / ("root-bmp-delete-report.json" if bmp else "root-txt-delete-report.json")
        _write_json(path, {"format": ("infocarry-experimental-root-bmp-delete-result-v1" if bmp
                                      else "infocarry-experimental-root-txt-delete-result-v1"),
                          "operation": "Delete", "target": self.target_path,
                          "profile": self.operation_profile,
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
                max_age_seconds=DEFAULT_MAX_AGE_SECONDS, cancelled=None, progress=None,
                general_txt=False, validation_only=False, validation_bmp_only=False, general_bmp=False):
        if self.stop_approved_rebuild():
            raise ValueError("approved Delete cannot refresh or adopt a new candidate")
        try:
            if self._prepared_operation is not None:
                raise ValueError("discard the previous operation before preparing another")
            if (type(general_txt) is not bool or type(validation_only) is not bool
                    or type(validation_bmp_only) is not bool or type(general_bmp) is not bool):
                raise ValueError("Delete admission flags require exact booleans")
            if general_bmp and (general_txt or validation_only or validation_bmp_only):
                raise ValueError("ordinary BMP cannot adopt another Delete scope")
            if validation_only and (not general_txt or target_path not in ROOT_TXT_DELETE_VALIDATION_FILES):
                raise ValueError("validation requires one predetermined disposable target")
            if validation_bmp_only and (general_txt or validation_only or target_path not in ROOT_BMP_DELETE_VALIDATION_FILES):
                raise ValueError("BMP validation requires only the exact disposable root-BMP target")
            if ((not general_txt and not validation_bmp_only and not general_bmp and target_path != FIXTURE_PATH)
                    or device_model != "VNW-V15"):
                raise ValueError("only the exact VNW-V15 root-TXT fixture or disposable BMP is admitted")
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
            media = "bmp" if validation_bmp_only or general_bmp else "txt"
            root = Path(runtime.evidence_namespace) / (f"prepared-root-{media}-delete-" + uuid4().hex)
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
            if general_bmp:
                core = build_root_bmp_delete(before.directory, target_path, max_age_seconds=max_age_seconds)
            elif validation_bmp_only:
                core = build_experimental_root_bmp_delete(before.directory, target_path=target_path, max_age_seconds=max_age_seconds)
            else:
                core = (build_root_txt_delete(before.directory, target_path, max_age_seconds=max_age_seconds) if general_txt else
                        build_experimental_root_txt_delete(before.directory, max_age_seconds=max_age_seconds))
            parsed = core.baseline
            payload = parsed.payload_parts(parsed.record_at(core.target_record_offset))[1]
            if validation_only and payload != ROOT_TXT_DELETE_VALIDATION_FILES[target_path]:
                raise ValueError("disposable validation target payload changed")
            candidate = RootTxtDeleteCandidate(before.directory, core.candidate_blob,
                core.transaction, _json(core.to_dict()), core.target_path, core.target_record_offset,
                not general_txt and not validation_bmp_only and not general_bmp,
                media, general_bmp)
            source_name = (target_path.rsplit("\\", 1)[-1] if media == "bmp" else
                           "selected-txt.bin" if general_txt else FIXTURE_FILENAME)
            source = root / source_name
            with source.open("xb") as output:
                output.write(payload)
            candidate_path = root / "candidate.bin"
            with candidate_path.open("xb") as output:
                output.write(candidate.candidate_blob)
            transaction_path = root / "transaction"
            candidate.transaction.preserve(transaction_path, source="experimental-exact-root-txt-delete")
            capacity_path = root / "capacity-0019.bin"
            with capacity_path.open("xb") as output:
                output.write(capacity.raw_response)
            binding = authorize_generalized_delete(core, confirmation=DELETE_GENERALIZED_CONFIRMATION_PHRASE)
            phrase = f"DELETE {target_path.split(chr(92))[-1]} ONCE"
            profile = (ROOT_BMP_DELETE_LIVE_PROFILE if general_bmp else
                       ROOT_BMP_DELETE_VALIDATION_PROFILE if validation_bmp_only else
                       EXPERIMENTAL_ROOT_TXT_DELETE_PROFILE if not general_txt else
                       ROOT_TXT_DELETE_VALIDATION_PROFILE if validation_only else
                       ROOT_TXT_DELETE_LIVE_PROFILE if root_txt_delete_execution_supported(core) else ROOT_TXT_DELETE_HOST_PROFILE)
            authorization = RootTxtDeleteAuthorization(RootTxtDeleteAuthorizationCore(binding, before.directory, source,
                confirmation_phrase=phrase, profile_id=profile))
            seal_path = root / "operation-bundle.json"
            provisional = RootTxtDeleteBundle(runtime, before, capacity, candidate, authorization,
                OperationArtifact.file(source), OperationArtifact.file(candidate_path),
                OperationArtifact.file(capacity_path), OperationArtifact.backup_manifest(before.directory),
                OperationArtifact(str(seal_path), "0" * 64, "file_bytes", 0),
                transaction_path, b"", "0" * 64, runtime.session_binding_token, None,
                validation_only, validation_bmp_only)
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


# Exact P18-046 disposable specimen with bounded physical placement/Delete
# evidence. Ordinary BMP execution remains outside this exact-fixture gate.
ROOT_BMP_DELETE_FIXTURE_FILENAME = "IC_P18_046_DELETE_A.bmp"
ROOT_BMP_DELETE_FIXTURE_PATH = "root\\" + ROOT_BMP_DELETE_FIXTURE_FILENAME


def _root_bmp_delete_fixture_bytes():
    """Deterministic 237x320 BI_RGB specimen; border and checkerboard centre."""
    width, height, stride = 237, 320, 32
    payload = bytearray(62 + stride * height)
    payload[:2] = b"BM"
    for offset, value, size in ((2, len(payload), 4), (10, 62, 4), (14, 40, 4),
                              (18, width, 4), (22, height, 4), (26, 1, 2),
                              (28, 1, 2), (34, stride * height, 4), (46, 2, 4)):
        payload[offset:offset + size] = value.to_bytes(size, "little")
    payload[58:62] = b"\xff\xff\xff\0"
    for y in range(height):
        for x in range(width):
            if (x < 4 or x >= width - 4 or y < 4 or y >= height - 4
                    or (64 <= x < 173 and 96 <= y < 224 and (x // 8 + y // 8) % 2)):
                payload[62 + (height - 1 - y) * stride + x // 8] |= 1 << (7 - x % 8)
    return bytes(payload)


ROOT_BMP_DELETE_FIXTURE_BYTES = _root_bmp_delete_fixture_bytes()
ROOT_BMP_DELETE_FIXTURE_SHA256 = _sha(ROOT_BMP_DELETE_FIXTURE_BYTES)

# One additional host-defined disposable experiment, never ordinary BMP authority.
# Different pixels/orientation and serialized position exercise the same opaque
# payload deletion arithmetic with survivors on both sides of the target.
ROOT_BMP_DELETE_EXPANSION_PATH = "root\\IC_P18_047_DELETE_B.bmp"
_expansion_bmp = bytearray(ROOT_BMP_DELETE_FIXTURE_BYTES)
_expansion_bmp[22:26] = (-320).to_bytes(4, "little", signed=True)
_expansion_bmp[62:] = bytes(value ^ 0xff for value in _expansion_bmp[62:])
ROOT_BMP_DELETE_EXPANSION_BYTES = bytes(_expansion_bmp)
del _expansion_bmp
ROOT_BMP_DELETE_VALIDATION_FILES = MappingProxyType({
    ROOT_BMP_DELETE_FIXTURE_PATH: ROOT_BMP_DELETE_FIXTURE_BYTES,
    ROOT_BMP_DELETE_EXPANSION_PATH: ROOT_BMP_DELETE_EXPANSION_BYTES,
})
ROOT_BMP_DELETE_VALIDATION_OFFSETS = MappingProxyType({
    ROOT_BMP_DELETE_FIXTURE_PATH: 0x680, ROOT_BMP_DELETE_EXPANSION_PATH: 0x6c0,
})



def build_experimental_root_bmp_delete(backup_directory, *, target_path=ROOT_BMP_DELETE_FIXTURE_PATH, max_age_seconds=None):
    """Build a named exact disposable BMP validation candidate.

    Both A and B were physically demonstrated in separate authorized experiments. Both bind exact path/payload, unread/prefix and record position;
    B additionally requires the preserved disposable TXT anchor.
    Generalized BMP candidates remain host-only.
    """
    core = build_disposable_root_bmp_delete(backup_directory, target_path=target_path, max_age_seconds=max_age_seconds)
    if not _root_bmp_fixture_supported(core, ROOT_BMP_DELETE_VALIDATION_FILES):
        raise ValueError("the named VNW-V15 disposable BMP profile or required anchor does not match")
    return core


def build_disposable_root_bmp_delete(backup_directory, *, target_path=ROOT_BMP_DELETE_FIXTURE_PATH, max_age_seconds=None):
    """Prepare only the exact unread, 16-byte-prefix specimen, without USB.

    The broader retained BMP model remains host-only. This additional profile
    chooses a reproducible experiment; it conveys no live authorization.
    """
    backup = verify_fresh_backup(Path(backup_directory), max_age_seconds=max_age_seconds)
    if backup.device_identity != ("0x054c", "0x001e"):
        raise ValueError("disposable BMP preparation requires a VNW-V15 backup")
    if target_path not in ROOT_BMP_DELETE_VALIDATION_FILES:
        raise ValueError("only a named disposable root BMP may enter validation")
    parsed = parse_backup_blob(_blob(backup))
    filename = target_path.rsplit("\\", 1)[-1]
    matches = [r for r in parsed.records if parsed.paths.get(r.offset)
               == ("root", Path(filename).stem) and r.extension == "bmp"]
    if len(matches) != 1:
        raise ValueError("exact unique disposable root BMP is absent or ambiguous")
    target = matches[0]
    if target.flag != 0xe0 or target.field_14_be32 != 0x100:
        raise ValueError("disposable BMP requires unread state and a 16-byte native prefix")
    if parsed.payload_parts(target)[1] != ROOT_BMP_DELETE_VALIDATION_FILES[target_path]:
        raise ValueError("disposable BMP payload differs from the exact specimen")
    return build_root_bmp_delete_candidate(backup.directory, target_path,
        target.offset, max_age_seconds=max_age_seconds)


def require_external_bmp_output(path):
    """Keep raw candidates outside Git checkouts, including linked worktrees."""
    path = Path(path).expanduser().resolve()
    if any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise ValueError("BMP preparation output must remain outside a Git checkout")
    return path


@dataclass(frozen=True)
class RootBmpDeletePreparation:
    """Persisted host review using the existing binding, never a live bundle.

    No runtime, owner approval identity, claim or sender can be obtained from
    this object. Every use rebuilds from the complete hash-verified baseline.
    Raw artifacts are local evidence, never release or repository contents.
    """

    authorization: GeneralizedDeleteAuthorization
    artifacts: tuple[OperationArtifact, ...]
    directory: Path
    report_json: bytes
    target_path: str = ROOT_BMP_DELETE_FIXTURE_PATH

    @property
    def execution_available(self):
        return False

    def _report(self):
        return {"format": "infocarry-disposable-root-bmp-delete-preparation-v1",
                "status": "host_prepared_not_live_enabled",
                "execution_available": False, "physical_operation_authorized": False,
                "fresh_for_physical_use": False, "automatic_retry_allowed": False,
                "owner_approval_identity_created": False,
                "fixture": {"path": self.target_path,
                            "bytes": len(ROOT_BMP_DELETE_VALIDATION_FILES[self.target_path]),
                            "sha256": _sha(ROOT_BMP_DELETE_VALIDATION_FILES[self.target_path]),
                            "flag": "0xe0", "native_prefix_bytes": 16},
                "host_binding": self.authorization.to_dict(),
                "artifacts": [artifact.to_dict() for artifact in self.artifacts],
                "missing_proof": (["broader_root_bmp_class_physical_validation"]
                                  if self.target_path == ROOT_BMP_DELETE_FIXTURE_PATH else
                                  ["separately_authorized_expansion_placement_and_delete"])}

    def verify(self):
        if type(self.authorization) is not GeneralizedDeleteAuthorization or self.authorization.target_extension != "bmp":
            raise ValueError("BMP preparation requires the existing host-only BMP binding")
        if self.target_path not in ROOT_BMP_DELETE_VALIDATION_FILES:
            raise ValueError("BMP preparation target is not a named disposable")
        core = build_disposable_root_bmp_delete(self.authorization.baseline.directory, target_path=self.target_path)
        self.authorization.revalidate(core, max_age_seconds=None)
        expected_files = (self.directory / self.target_path.rsplit("\\", 1)[-1],
                          self.directory / "candidate.bin", self.directory / "candidate-audit.json",
                          self.directory / "host-binding.json")
        expected_artifacts = tuple(OperationArtifact.file(p) for p in expected_files) + (
            OperationArtifact.backup_manifest(core.backup.directory),)
        if self.artifacts != expected_artifacts:
            raise ValueError("BMP preparation artifacts changed or were rebound")
        expected_bytes = (ROOT_BMP_DELETE_VALIDATION_FILES[self.target_path], core.candidate_blob,
                          _json(core.to_dict()), _json(self.authorization.to_dict()))
        if any(p.read_bytes() != data for p, data in zip(expected_files, expected_bytes)):
            raise ValueError("BMP preparation differs from independent reconstruction")
        if load_preserved_artifact(self.directory / "transaction") != core.transaction:
            raise ValueError("BMP prepared transaction differs from independent reconstruction")
        if self.report_json != _json(self._report()) or (self.directory / "preparation.json").read_bytes() != self.report_json:
            raise ValueError("BMP host preparation report changed")
        return core

    def verify_readback(self, post_backup, *, completion):
        """Independent complete eight-object verification, not a send/success gate."""
        return verify_generalized_delete_readback(self.verify(), Path(post_backup),
            completion=completion, max_age_seconds=None)


def prepare_disposable_root_bmp_delete(backup_directory, output_directory, *, target_path=ROOT_BMP_DELETE_FIXTURE_PATH):
    """Persist exact host preparation. Existing artifacts are never overwritten."""
    output = require_external_bmp_output(output_directory)
    baseline = Path(backup_directory).expanduser().resolve()
    if output.is_relative_to(baseline):
        raise ValueError("BMP output must not modify the source backup")
    core = build_disposable_root_bmp_delete(baseline, target_path=target_path)
    binding = authorize_generalized_delete(core, confirmation=DELETE_GENERALIZED_CONFIRMATION_PHRASE)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    files = ((target_path.rsplit("\\", 1)[-1], ROOT_BMP_DELETE_VALIDATION_FILES[target_path]),
             ("candidate.bin", core.candidate_blob), ("candidate-audit.json", _json(core.to_dict())),
             ("host-binding.json", _json(binding.to_dict())))
    for filename, data in files:
        with (output / filename).open("xb") as stream:
            stream.write(data)
    core.transaction.preserve(output / "transaction", source="host-only-disposable-root-bmp-delete")
    artifacts = tuple(OperationArtifact.file(output / name) for name, _ in files) + (
        OperationArtifact.backup_manifest(core.backup.directory),)
    provisional = RootBmpDeletePreparation(binding, artifacts, output, b"", target_path)
    report = _json(provisional._report())
    with (output / "preparation.json").open("xb") as stream:
        stream.write(report)
    prepared = replace(provisional, report_json=report)
    prepared.verify()
    return prepared
