"""Exact host-only preparation boundary for one VNW-V15 four-leaf shape.

This module binds the reviewed four-leaf capability descriptor to the existing
ordered-package candidate builder, authorization gate, transfer foundation,
and independent read-back verifier.  It deliberately contains no transport,
claim, marker, lock, or sender implementation: the exact profile is
validation-only and cannot enable execution.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from .capability_profile import (
    FOUR_LEAF_VALIDATION_PROFILE_ID,
    CapabilityProfileError,
    four_leaf_validation_profile,
)
from .device_model_profile import VNW_V15_PROFILE
from .prepared_content import PreparedContentArtifact, PreparedContentError
from .prepared_media_package import (
    PreparedMediaPackage,
    PreparedMediaPackageError,
    build_prepared_media_package,
)
from .prepared_multi_package_gate import (
    PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_EXPLICIT,
    PreparedMultiPackageAuthorization,
    PreparedMultiPackageGateError,
    authorize_prepared_multi_package,
)
from .prepared_package_multi_candidate import (
    PreparedMultiCandidateError,
    PreparedMultiPackageCandidate,
    build_prepared_multi_package_candidate,
)
from .prepared_package_multi_verify import (
    PreparedMultiPackageReadback,
    PreparedMultiVerificationError,
    verify_prepared_multi_package_readback,
)
from .transfer_foundation import PreparedItem, TransferFoundation, TransferFoundationError
from .capacity_evidence import NativeCapacityResponse
from .backup_format import ParsedBackupBlob
from .write_gate import DEFAULT_MAX_AGE_SECONDS, VerifiedBackup


FOUR_LEAF_VALIDATION_FORMAT = "infocarry-vnw-v15-four-leaf-validation-v1"
FOUR_LEAF_VALIDATION_TARGET = "IC_P18_4LEAF_20260918_01"
FOUR_LEAF_CHILD_NAMES = (
    "01-introduction.txt",
    "02-page-01.bmp",
    "03-ending.txt",
    "04-extra.txt",
)
FOUR_LEAF_CHILD_KINDS = ("txt", "bmp", "txt", "txt")
FOUR_LEAF_VALIDATION_CONFIRMATION = (
    f"VALIDATE {FOUR_LEAF_VALIDATION_TARGET} ONCE"
)


class FourLeafValidationError(ValueError):
    """Raised when the exact validation-only four-leaf shape is not bound."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise FourLeafValidationError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _profile_binding(artifact: PreparedContentArtifact) -> dict[str, Any]:
    profile = four_leaf_validation_profile()
    if artifact.profile_id != profile.profile_id:
        raise FourLeafValidationError(
            "artifact is not bound to the exact four-leaf validation profile"
        )
    if artifact.profile_sha256 != profile.sha256:
        raise FourLeafValidationError(
            "artifact four-leaf validation profile hash differs"
        )
    try:
        profile.validate_package(
            folder_name=artifact.root_name,
            children=artifact.to_legacy_children(),
        )
    except CapabilityProfileError as exc:
        raise FourLeafValidationError(str(exc)) from exc
    return {
        "profile_id": profile.profile_id,
        "profile_sha256": profile.sha256,
        "artifact_identity": artifact.artifact_identity,
        "root_name": artifact.root_name,
        "ordered_kinds": list(FOUR_LEAF_CHILD_KINDS),
        "ordered_names": list(FOUR_LEAF_CHILD_NAMES),
        "live_enabled": False,
        "validation_only": True,
    }


def bind_four_leaf_validation_profile(
    artifact: PreparedContentArtifact,
) -> PreparedContentArtifact:
    """Bind a validated direct-leaf artifact to the exact non-live profile."""

    if not isinstance(artifact, PreparedContentArtifact):
        raise FourLeafValidationError("prepared content artifact is malformed")
    profile = four_leaf_validation_profile()
    try:
        profile.validate_package(
            folder_name=artifact.root_name,
            children=artifact.to_legacy_children(),
        )
    except CapabilityProfileError as exc:
        raise FourLeafValidationError(str(exc)) from exc
    return PreparedContentArtifact(
        root_name=artifact.root_name,
        children=artifact.children,
        profile_id=profile.profile_id,
        profile_sha256=profile.sha256,
    )


def validate_four_leaf_artifact(
    artifact: PreparedContentArtifact,
) -> PreparedContentArtifact:
    """Validate an already profile-bound exact four-leaf artifact."""

    if not isinstance(artifact, PreparedContentArtifact):
        raise FourLeafValidationError("prepared content artifact is malformed")
    _profile_binding(artifact)
    if tuple(child.name for child in artifact.children) != FOUR_LEAF_CHILD_NAMES:
        raise FourLeafValidationError(
            "four-leaf validation artifact names are not the reviewed disposable target order"
        )
    return artifact


def build_four_leaf_validation_package(
    sources: Iterable[tuple[Path, str]],
    *,
    folder_name: str = FOUR_LEAF_VALIDATION_TARGET,
) -> PreparedMediaPackage:
    """Prepare the exact deterministic TXT/BMP/TXT/TXT source sequence."""

    try:
        package = build_prepared_media_package(
            sources,
            folder_name,
            require_mixed_kinds=True,
        )
    except (OSError, PreparedMediaPackageError) as exc:
        raise FourLeafValidationError(str(exc)) from exc
    _validate_exact_package(package, require_target=True)
    return package


def build_four_leaf_validation_artifact(
    sources: Iterable[tuple[Path, str]],
    *,
    folder_name: str = FOUR_LEAF_VALIDATION_TARGET,
) -> PreparedContentArtifact:
    """Create the one canonical profile-bound four-leaf artifact."""

    package = build_four_leaf_validation_package(sources, folder_name=folder_name)
    return bind_four_leaf_validation_profile(package.to_prepared_content_artifact())


def _validate_exact_package(
    package: PreparedMediaPackage,
    *,
    require_target: bool,
) -> PreparedContentArtifact:
    if not isinstance(package, PreparedMediaPackage):
        raise FourLeafValidationError("four-leaf candidate requires a typed media package")
    if len(package.items) != len(FOUR_LEAF_CHILD_KINDS):
        raise FourLeafValidationError("four-leaf validation requires exactly four children")
    if tuple(item.kind for item in package.items) != FOUR_LEAF_CHILD_KINDS:
        raise FourLeafValidationError("four-leaf validation requires TXT/BMP/TXT/TXT order")
    if tuple(item.name for item in package.items) != FOUR_LEAF_CHILD_NAMES:
        raise FourLeafValidationError("four-leaf validation child names differ from the exact target")
    if require_target and package.folder_name != FOUR_LEAF_VALIDATION_TARGET:
        raise FourLeafValidationError("four-leaf candidate target differs from the fresh validation target")
    artifact = bind_four_leaf_validation_profile(package.to_prepared_content_artifact())
    validate_four_leaf_artifact(artifact)
    return artifact


def build_four_leaf_validation_candidate(
    package: PreparedMediaPackage,
    backup: VerifiedBackup,
    template: ParsedBackupBlob,
    *,
    new_record_timestamp_be32: int,
    native_capacity_response: NativeCapacityResponse,
    template_folder_path: tuple[str, str] = ("root", "IC_I_FOLDER_20260823_01"),
    template_item_paths: Optional[Mapping[str, tuple[str, ...]]] = None,
    template_subset_policy_sha256: Optional[str] = None,
    allow_verified_bookmarks: bool = False,
) -> PreparedMultiPackageCandidate:
    """Use the canonical ordered-package builder for the exact four leaves."""

    artifact = _validate_exact_package(package, require_target=True)
    try:
        candidate = build_prepared_multi_package_candidate(
            package,
            backup,
            template,
            new_record_timestamp_be32=new_record_timestamp_be32,
            native_capacity_response=native_capacity_response,
            template_folder_path=template_folder_path,
            template_item_paths=template_item_paths,
            template_subset_policy_sha256=template_subset_policy_sha256,
            allow_verified_bookmarks=allow_verified_bookmarks,
        )
    except (PreparedMultiCandidateError, TypeError) as exc:
        raise FourLeafValidationError(str(exc)) from exc
    audit = dict(candidate.audit)
    audit["validation_profile"] = _profile_binding(artifact)
    return replace(candidate, audit=audit)


def _validate_candidate(candidate: PreparedMultiPackageCandidate) -> dict[str, Any]:
    if not isinstance(candidate, PreparedMultiPackageCandidate):
        raise FourLeafValidationError("four-leaf candidate is malformed")
    artifact = _validate_exact_package(candidate.package, require_target=True)
    expected = _profile_binding(artifact)
    if candidate.audit.get("validation_profile") != expected:
        raise FourLeafValidationError("candidate four-leaf profile binding differs")
    expected_post = candidate.audit.get("expected_post_operation")
    if not isinstance(expected_post, Mapping):
        raise FourLeafValidationError("candidate expected post-operation binding is missing")
    if tuple(expected_post.get("ordered_kinds", ())) != (
        "directory",
        *FOUR_LEAF_CHILD_KINDS,
    ):
        raise FourLeafValidationError("candidate expected child order differs")
    return expected


def derive_four_leaf_operation_id(candidate: PreparedMultiPackageCandidate) -> str:
    """Derive a fresh operation identity from all exact candidate evidence."""

    profile = _validate_candidate(candidate)
    audit = candidate.audit
    allocation = audit.get("allocation")
    evidence = audit.get("capacity_evidence")
    transaction = audit.get("transaction")
    if not isinstance(allocation, Mapping) or not isinstance(evidence, Mapping) or not isinstance(transaction, Mapping):
        raise FourLeafValidationError("candidate evidence binding is incomplete")
    unsigned = {
        "format": FOUR_LEAF_VALIDATION_FORMAT,
        "profile": profile,
        "device_identity": audit.get("device_identity"),
        "baseline": audit.get("baseline"),
        "prepared_manifest_sha256": audit["package"]["prepared_manifest_sha256"],
        "target_paths": audit["package"]["paths"],
        "target_kinds": audit["expected_post_operation"]["ordered_kinds"],
        "candidate_blob_sha256": candidate.candidate_blob_sha256,
        "transaction_sha256": candidate.transaction_sha256,
        "capacity": {
            "response_sha256": evidence.get("raw_response_sha256"),
            "limit_bytes": allocation.get("capacity_limit_bytes"),
            "baseline_model_bytes": allocation.get("baseline_model_bytes"),
            "candidate_model_bytes": allocation.get("candidate_model_bytes"),
            "remaining_growth_bytes": allocation.get("remaining_growth_bytes"),
        },
        "fixed_state_candidate_sha256": transaction.get("fixed_state_hashes"),
    }
    return "vnw-v15-four-leaf-validation-" + _sha256(_canonical_json(unsigned))


@dataclass(frozen=True)
class FourLeafValidationAuthorization:
    """Exact authorization identity for host validation; never an execute token."""

    authorization: PreparedMultiPackageAuthorization
    profile_id: str
    profile_sha256: str
    artifact_identity: str
    operation_id: str
    authorization_identity_sha256: str

    def __post_init__(self) -> None:
        profile = four_leaf_validation_profile()
        if self.profile_id != profile.profile_id or self.profile_sha256 != profile.sha256:
            raise FourLeafValidationError("authorization profile binding differs")
        _digest(self.artifact_identity, "authorization artifact identity")
        if not isinstance(self.authorization, PreparedMultiPackageAuthorization):
            raise FourLeafValidationError("authorization is malformed")
        if not isinstance(self.operation_id, str) or not self.operation_id:
            raise FourLeafValidationError("operation identity is missing")
        expected = _sha256(
            _canonical_json(
                {
                    "format": FOUR_LEAF_VALIDATION_FORMAT,
                    "profile_id": self.profile_id,
                    "profile_sha256": self.profile_sha256,
                    "artifact_identity": self.artifact_identity,
                    "operation_id": self.operation_id,
                    "authorization": self.authorization.to_dict(),
                }
            )
        )
        if self.authorization_identity_sha256 != expected:
            raise FourLeafValidationError("authorization identity hash differs")

    @property
    def execute_once_enabled(self) -> bool:
        return False

    def require_same_candidate(self, candidate: PreparedMultiPackageCandidate) -> None:
        _validate_candidate(candidate)
        if derive_four_leaf_operation_id(candidate) != self.operation_id:
            raise FourLeafValidationError("candidate operation identity differs from authorization")
        try:
            self.authorization.require_same_candidate(candidate)
        except PreparedMultiPackageGateError as exc:
            raise FourLeafValidationError(str(exc)) from exc

    def revalidate(
        self,
        candidate: PreparedMultiPackageCandidate,
        *,
        native_capacity_response: NativeCapacityResponse,
        now: Optional[datetime] = None,
        max_age_seconds: Optional[float] = DEFAULT_MAX_AGE_SECONDS,
    ) -> VerifiedBackup:
        self.require_same_candidate(candidate)
        if not isinstance(native_capacity_response, NativeCapacityResponse):
            raise FourLeafValidationError(
                "fresh parsed native capacity evidence is required"
            )
        expected_identity = tuple(
            int(value, 16) for value in candidate.backup.device_identity
        )
        if (
            native_capacity_response.device_identity != expected_identity
            or native_capacity_response.raw_response_sha256
            != self.authorization.capacity_response_sha256
            or native_capacity_response.capacity_limit_bytes
            != self.authorization.capacity_limit_bytes
        ):
            raise FourLeafValidationError(
                "fresh native capacity evidence differs from the authorized operation"
            )
        try:
            fresh_backup = self.authorization.revalidate(
                candidate,
                now=now,
                max_age_seconds=max_age_seconds,
            )
        except PreparedMultiPackageGateError as exc:
            raise FourLeafValidationError(str(exc)) from exc
        blob_filename = fresh_backup.object_filename("0x8004:backup-blob")
        if blob_filename is None:
            raise FourLeafValidationError(
                "fresh backup dynamic blob identity is missing"
            )
        try:
            fresh_blob = (fresh_backup.directory / blob_filename).read_bytes()
        except OSError as exc:
            raise FourLeafValidationError(
                f"fresh backup dynamic blob could not be reread: {exc}"
            ) from exc
        if (
            fresh_backup.manifest_sha256
            != self.authorization.baseline_manifest_sha256
            or fresh_backup.blob_sha256 != self.authorization.baseline_blob_sha256
            or len(fresh_blob) != self.authorization.baseline_model_bytes
        ):
            raise FourLeafValidationError(
                "fresh backup manifest, dynamic blob, or model length differs "
                "from the authorized baseline"
            )
        if _sha256(fresh_blob) != fresh_backup.blob_sha256:
            raise FourLeafValidationError(
                "fresh backup dynamic blob hash differs from its verified identity"
            )
        return fresh_backup

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": FOUR_LEAF_VALIDATION_FORMAT,
            "state": "authorized_for_host_validation_only",
            "usb_transmission_performed": False,
            "execution_enabled": False,
            "profile_id": self.profile_id,
            "profile_sha256": self.profile_sha256,
            "artifact_identity": self.artifact_identity,
            "operation_id": self.operation_id,
            "authorization_identity_sha256": self.authorization_identity_sha256,
            "authorization": self.authorization.to_dict(),
        }


def authorize_four_leaf_candidate(
    candidate: PreparedMultiPackageCandidate,
    *,
    confirmation: str = FOUR_LEAF_VALIDATION_CONFIRMATION,
) -> FourLeafValidationAuthorization:
    """Bind exact candidate, capacity, backup, transaction, and confirmation."""

    profile = _validate_candidate(candidate)
    try:
        authorization = authorize_prepared_multi_package(
            candidate,
            confirmation=confirmation,
            confirmation_policy=PREPARED_MULTI_PACKAGE_CONFIRMATION_POLICY_EXPLICIT,
        )
    except PreparedMultiPackageGateError as exc:
        raise FourLeafValidationError(str(exc)) from exc
    operation_id = derive_four_leaf_operation_id(candidate)
    artifact_identity = profile["artifact_identity"]
    authorization_identity = _sha256(
        _canonical_json(
            {
                "format": FOUR_LEAF_VALIDATION_FORMAT,
                "profile_id": profile["profile_id"],
                "profile_sha256": profile["profile_sha256"],
                "artifact_identity": artifact_identity,
                "operation_id": operation_id,
                "authorization": authorization.to_dict(),
            }
        )
    )
    return FourLeafValidationAuthorization(
        authorization=authorization,
        profile_id=profile["profile_id"],
        profile_sha256=profile["profile_sha256"],
        artifact_identity=artifact_identity,
        operation_id=operation_id,
        authorization_identity_sha256=authorization_identity,
    )


def build_four_leaf_validation_foundation(
    artifact: PreparedContentArtifact,
    *,
    library_item_id: str = "p18-030-four-leaf-validation",
) -> TransferFoundation:
    """Reuse the canonical host-only transfer foundation without execution."""

    artifact = validate_four_leaf_artifact(artifact)
    try:
        item = PreparedItem.from_prepared_content(
            artifact,
            library_item_id=library_item_id,
            package_manifest_sha256=artifact.artifact_identity,
        )
        return TransferFoundation.from_prepared_items(
            (item,),
            profile=four_leaf_validation_profile(),
            device_model_profile=VNW_V15_PROFILE,
        )
    except (TransferFoundationError, PreparedContentError) as exc:
        raise FourLeafValidationError(str(exc)) from exc


@dataclass(frozen=True)
class FourLeafValidationReadback:
    """Exact-profile view over the existing independent multi-package verifier."""

    verification: PreparedMultiPackageReadback
    profile_id: str
    profile_sha256: str
    artifact_identity: str

    @property
    def success(self) -> bool:
        return self.verification.success

    def to_dict(self) -> dict[str, Any]:
        result = self.verification.to_dict()
        result.update(
            {
                "validation_profile_id": self.profile_id,
                "validation_profile_sha256": self.profile_sha256,
                "validation_artifact_identity": self.artifact_identity,
                "execution_enabled": False,
            }
        )
        return result


def verify_four_leaf_readback(
    candidate: PreparedMultiPackageCandidate,
    post_directory: Path,
    *,
    completion: Any,
    now: Optional[datetime] = None,
    max_age_seconds: Optional[float] = None,
) -> FourLeafValidationReadback:
    """Verify the exact four-child post-state through the shared verifier."""

    profile = _validate_candidate(candidate)
    try:
        result = verify_prepared_multi_package_readback(
            candidate,
            post_directory,
            completion=completion,
            now=now,
            max_age_seconds=max_age_seconds,
        )
    except PreparedMultiVerificationError as exc:
        raise FourLeafValidationError(str(exc)) from exc
    return FourLeafValidationReadback(
        verification=result,
        profile_id=profile["profile_id"],
        profile_sha256=profile["profile_sha256"],
        artifact_identity=profile["artifact_identity"],
    )


__all__ = [
    "FOUR_LEAF_CHILD_KINDS",
    "FOUR_LEAF_CHILD_NAMES",
    "FOUR_LEAF_VALIDATION_CONFIRMATION",
    "FOUR_LEAF_VALIDATION_FORMAT",
    "FOUR_LEAF_VALIDATION_PROFILE_ID",
    "FOUR_LEAF_VALIDATION_TARGET",
    "FourLeafValidationAuthorization",
    "FourLeafValidationError",
    "FourLeafValidationReadback",
    "authorize_four_leaf_candidate",
    "bind_four_leaf_validation_profile",
    "build_four_leaf_validation_artifact",
    "build_four_leaf_validation_candidate",
    "build_four_leaf_validation_foundation",
    "build_four_leaf_validation_package",
    "derive_four_leaf_operation_id",
    "validate_four_leaf_artifact",
    "verify_four_leaf_readback",
]
