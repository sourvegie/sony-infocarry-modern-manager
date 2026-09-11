"""Immutable artifact bundle for the isolated Library-package live boundary.

The production live entrypoint accepts one instance of
``PreparedLibraryPackageOperationBundle`` rather than a manually paired set of
reports, backups, catalogs, templates, and output paths.  This module is
framework-independent: it only validates the hash-bound JSON envelope and
the referenced files.  The P17-005 adapter performs the protocol-specific
reconstruction after this envelope has been accepted.

The bundle is an operation description, not a USB capability.  Creating or
loading one never detects a device, opens USB, constructs a sender, or sends
``0x101b``.  Candidate and transaction bytes are deliberately not stored in
the bundle manifest; their independently computed hashes are bound instead.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Optional


OPERATION_BUNDLE_FORMAT = "infocarry-p17-017-library-package-operation-bundle-v1"
EVIDENCE_OUTPUT_POLICY = MappingProxyType(
    {
        "namespace_scope": "direct_child_atomic_reservation",
        "before_backup_name": "backup-before-0001",
        "post_operation_name": "backup-after-0001",
        "manifest_name": "result-manifest-0001.json",
    }
)
_SHA256_LENGTH = 64


class OperationBundleError(ValueError):
    """Raised when a bundle is incomplete, tampered, or ambiguously bound."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != _SHA256_LENGTH
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise OperationBundleError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _absolute_path(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise OperationBundleError(f"{label} must be a non-empty absolute path")
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise OperationBundleError(f"{label} must be absolute")
    return str(path.resolve())


def _strict_object(path: Path) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise OperationBundleError(f"duplicate JSON key in {path}: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OperationBundleError(f"operation bundle is unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise OperationBundleError("operation bundle must be a JSON object")
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(child) for child in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw(child) for child in value]
    return value


def _require_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OperationBundleError(f"{label} must be a non-negative integer")
    return value


def _require_phrase(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or "\n" in value
        or "\r" in value
    ):
        raise OperationBundleError(f"{label} is invalid")
    return value


@dataclass(frozen=True)
class OperationArtifact:
    """One hash-bound file or directory manifest."""

    path: str
    sha256: str
    basis: str
    size_bytes: Optional[int] = None

    def __post_init__(self) -> None:
        canonical = _absolute_path(self.path, "artifact path")
        object.__setattr__(self, "path", canonical)
        _digest(self.sha256, f"artifact {canonical} hash")
        if self.basis not in {"file_bytes", "backup_manifest_bytes"}:
            raise OperationBundleError("artifact hash basis is unsupported")
        if self.basis == "backup_manifest_bytes" and self.size_bytes is not None:
            _require_nonnegative_int(self.size_bytes, "artifact size_bytes")
        if self.basis == "file_bytes":
            if self.size_bytes is None:
                raise OperationBundleError("file artifact size_bytes is required")
            _require_nonnegative_int(self.size_bytes, "artifact size_bytes")

    @classmethod
    def file(cls, path: Path) -> "OperationArtifact":
        resolved = Path(path).expanduser().resolve()
        try:
            data = resolved.read_bytes()
        except OSError as exc:
            raise OperationBundleError(f"cannot read artifact {resolved}: {exc}") from exc
        return cls(str(resolved), _sha256(data), "file_bytes", len(data))

    @classmethod
    def backup_manifest(cls, directory: Path) -> "OperationArtifact":
        resolved = Path(directory).expanduser().resolve()
        manifest = resolved / "manifest.json"
        try:
            data = manifest.read_bytes()
        except OSError as exc:
            raise OperationBundleError(
                f"cannot read backup manifest {manifest}: {exc}"
            ) from exc
        return cls(str(resolved), _sha256(data), "backup_manifest_bytes", len(data))

    def to_dict(self) -> dict[str, Any]:
        value = {
            "path": self.path,
            "sha256": self.sha256,
            "basis": self.basis,
        }
        if self.size_bytes is not None:
            value["size_bytes"] = self.size_bytes
        return value

    def verify(self) -> None:
        path = Path(self.path)
        try:
            if self.basis == "file_bytes":
                data = path.read_bytes()
                actual_size = len(data)
            else:
                data = (path / "manifest.json").read_bytes()
                actual_size = len(data)
        except OSError as exc:
            raise OperationBundleError(f"bound artifact is unavailable: {path}") from exc
        if self.size_bytes is not None and actual_size != self.size_bytes:
            raise OperationBundleError(f"bound artifact size changed: {path}")
        if _sha256(data) != self.sha256:
            raise OperationBundleError(f"bound artifact hash changed: {path}")


@dataclass(frozen=True)
class PreparedLibraryPackageOperationBundle:
    """Single immutable safety input to the isolated Library live runner."""

    sealed_report: OperationArtifact
    baseline_backup: OperationArtifact
    catalog: OperationArtifact
    template: OperationArtifact
    capacity_response: OperationArtifact
    package_manifest: OperationArtifact
    selected_item_id: str
    device_identity: tuple[str, str]
    expected_folder_name: str
    timestamp_policy: str
    fixed_state_policy: str
    fixed_state_before_sha256: tuple[str, ...]
    fixed_state_candidate_sha256: tuple[str, ...]
    bookmark_binding_sha256: str
    new_record_timestamp_be32: int
    bulk_out_endpoint: int
    owner_approval_phrase: str
    confirmation_phrase: str
    confirmation_policy: str
    baseline_state_identity_sha256: str
    capacity_response_sha256: str
    candidate_audit_sha256: str
    authorization_sha256: str
    expected_post_operation_sha256: str
    candidate_blob_sha256: str
    transaction_sha256: str
    core_preflight_seal_sha256: str
    preflight_seal_sha256: str
    library_binding_sha256: str
    package_children: tuple[Mapping[str, Any], ...]
    expected_post_operation: Mapping[str, Any]
    format: str = OPERATION_BUNDLE_FORMAT
    operation_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.format != OPERATION_BUNDLE_FORMAT:
            raise OperationBundleError("unsupported operation bundle format")
        if self.operation_id is not None:
            _require_phrase(self.operation_id, "operation_id")
        for label, artifact in (
            ("sealed_report", self.sealed_report),
            ("baseline_backup", self.baseline_backup),
            ("catalog", self.catalog),
            ("template", self.template),
            ("capacity_response", self.capacity_response),
            ("package_manifest", self.package_manifest),
        ):
            if not isinstance(artifact, OperationArtifact):
                raise OperationBundleError(f"{label} is not an artifact binding")
        if self.baseline_backup.basis != "backup_manifest_bytes":
            raise OperationBundleError("baseline_backup must bind manifest bytes")
        if not isinstance(self.selected_item_id, str) or not self.selected_item_id:
            raise OperationBundleError("selected_item_id is required")
        if self.device_identity != ("0x054c", "0x001e"):
            raise OperationBundleError("operation bundle device identity is not Sony 054c:001e")
        if not isinstance(self.expected_folder_name, str) or not self.expected_folder_name:
            raise OperationBundleError("expected_folder_name is required")
        if self.timestamp_policy != "one_explicit_frozen_value_for_new_records_only":
            raise OperationBundleError("unsupported timestamp policy")
        if self.fixed_state_policy not in {
            "capture7_exact_all_zero_fixed_state",
            "verified_display_history_0x001b_semantic_rebase_plus_zero_0x001c_to_0x001f",
            "verified_display_history_0x001b_and_bookmark_0x001f_semantic_rebase_plus_zero_count_0x001c_to_0x001e",
        }:
            raise OperationBundleError("unsupported fixed-state policy")
        if len(self.fixed_state_before_sha256) != 5 or len(self.fixed_state_candidate_sha256) != 5:
            raise OperationBundleError("operation bundle must bind five before/candidate fixed-state hashes")
        for label, values in (("before fixed state", self.fixed_state_before_sha256), ("candidate fixed state", self.fixed_state_candidate_sha256)):
            for digest in values:
                _digest(digest, label)
        _digest(self.bookmark_binding_sha256, "bookmark_binding_sha256")
        if (
            isinstance(self.new_record_timestamp_be32, bool)
            or not isinstance(self.new_record_timestamp_be32, int)
            or not 0 <= self.new_record_timestamp_be32 <= 0xFFFFFFFF
        ):
            raise OperationBundleError("new_record_timestamp_be32 is invalid")
        if self.bulk_out_endpoint != 0x01:
            raise OperationBundleError(
                "bulk_out_endpoint differs from the reviewed one-shot boundary"
            )
        _require_phrase(self.owner_approval_phrase, "owner_approval_phrase")
        _require_phrase(self.confirmation_phrase, "confirmation_phrase")
        if not isinstance(self.confirmation_policy, str) or not self.confirmation_policy:
            raise OperationBundleError("confirmation_policy is required")
        for label, digest in (
            ("baseline_state_identity_sha256", self.baseline_state_identity_sha256),
            ("capacity_response_sha256", self.capacity_response_sha256),
            ("candidate_audit_sha256", self.candidate_audit_sha256),
            ("authorization_sha256", self.authorization_sha256),
            ("expected_post_operation_sha256", self.expected_post_operation_sha256),
            ("candidate_blob_sha256", self.candidate_blob_sha256),
            ("transaction_sha256", self.transaction_sha256),
            ("core_preflight_seal_sha256", self.core_preflight_seal_sha256),
            ("preflight_seal_sha256", self.preflight_seal_sha256),
            ("library_binding_sha256", self.library_binding_sha256),
        ):
            _digest(digest, label)
        if not isinstance(self.package_children, tuple) or not self.package_children:
            raise OperationBundleError("package_children must be a non-empty ordered tuple")
        orders = []
        for index, child in enumerate(self.package_children):
            if not isinstance(child, Mapping):
                raise OperationBundleError(f"package child {index} is malformed")
            if child.get("order") != index:
                raise OperationBundleError("package child order is not contiguous")
            orders.append(child.get("order"))
        if orders != list(range(len(self.package_children))):
            raise OperationBundleError("package child order is not deterministic")
        if not isinstance(self.expected_post_operation, Mapping):
            raise OperationBundleError("expected_post_operation is required")
        object.__setattr__(
            self,
            "package_children",
            tuple(_freeze(child) for child in self.package_children),
        )
        object.__setattr__(self, "expected_post_operation", _freeze(self.expected_post_operation))

    @property
    def bundle_sha256(self) -> str:
        return _sha256(_canonical_json(self.to_dict(include_bundle_hash=False)))

    @classmethod
    def from_sealed_report(
        cls,
        sealed_report_path: Path,
        *,
        template_path: Path,
        capacity_response_path: Path,
        operation_id: Optional[str] = None,
    ) -> "PreparedLibraryPackageOperationBundle":
        """Create a bundle from one sealed report and its exact artifacts.

        Values that identify the package, baseline, candidate, transaction,
        policy, and approvals are copied only from the sealed report.  The
        caller supplies only the reviewed template and capacity files.
        Per-attempt evidence destinations are allocated by the live runner and
        are deliberately excluded from this safety identity.
        """

        report_path = Path(sealed_report_path).expanduser().resolve()
        report = _strict_object(report_path)
        try:
            authorization = report["authorization"]
            candidate = report["candidate"]
            library_binding = candidate["library_binding"]
            before_backup = report["before_backup"]
            capacity = report["capacity_response"]
            package = candidate["package"]
        except (KeyError, TypeError) as exc:
            raise OperationBundleError(
                f"sealed report lacks canonical bundle bindings: {exc}"
            ) from exc
        if not isinstance(authorization, Mapping) or not isinstance(candidate, Mapping):
            raise OperationBundleError("sealed report candidate/authorization is malformed")
        if not isinstance(library_binding, Mapping) or not isinstance(before_backup, Mapping):
            raise OperationBundleError("sealed report Library/baseline binding is malformed")
        if not isinstance(capacity, Mapping) or not isinstance(package, Mapping):
            raise OperationBundleError("sealed report capacity/package binding is malformed")
        baseline_path = _absolute_path(before_backup.get("directory"), "baseline backup")
        catalog_path = _absolute_path(library_binding.get("catalog_path"), "catalog")
        package_manifest_path = _absolute_path(
            library_binding.get("manifest_path"), "package manifest"
        )
        children = library_binding.get("ordered_children")
        if not isinstance(children, list):
            raise OperationBundleError("sealed report ordered package children are missing")
        expected_post = candidate.get("expected_post_operation")
        if not isinstance(expected_post, Mapping):
            raise OperationBundleError("sealed report expected post-operation binding is missing")
        try:
            timestamp = int(authorization["new_record_timestamp_be32"])
        except (KeyError, TypeError, ValueError) as exc:
            raise OperationBundleError("sealed report timestamp binding is malformed") from exc
        if "new_record_timestamp_be32" in authorization:
            timestamp = authorization["new_record_timestamp_be32"]
        return cls(
            sealed_report=OperationArtifact.file(report_path),
            baseline_backup=OperationArtifact.backup_manifest(Path(baseline_path)),
            catalog=OperationArtifact.file(Path(catalog_path)),
            template=OperationArtifact.file(Path(template_path)),
            capacity_response=OperationArtifact.file(Path(capacity_response_path)),
            package_manifest=OperationArtifact.file(Path(package_manifest_path)),
            selected_item_id=str(library_binding.get("catalog_item_id")),
            device_identity=tuple(report["device_identity"]),
            expected_folder_name=str(report["expected_folder_name"]),
            timestamp_policy=str(candidate.get("policy", {}).get("timestamp", "")),
            fixed_state_policy=str(authorization["fixed_state_policy"]),
            fixed_state_before_sha256=tuple(authorization["fixed_state_before_sha256"]),
            fixed_state_candidate_sha256=tuple(authorization["fixed_state_candidate_sha256"]),
            bookmark_binding_sha256=str(authorization["bookmark_binding_sha256"]),
            new_record_timestamp_be32=timestamp,
            bulk_out_endpoint=1,
            owner_approval_phrase=str(report["owner_approval_phrase"]),
            confirmation_phrase=str(report["confirmation_phrase"]),
            confirmation_policy=str(report["confirmation_policy"]),
            baseline_state_identity_sha256=str(report["backup_state_identity_sha256"]),
            capacity_response_sha256=str(capacity["raw_response_sha256"]),
            candidate_audit_sha256=_sha256(_canonical_json(candidate)),
            authorization_sha256=_sha256(_canonical_json(authorization)),
            expected_post_operation_sha256=_sha256(_canonical_json(expected_post)),
            candidate_blob_sha256=str(candidate["candidate"]["blob_sha256"]),
            transaction_sha256=str(authorization["candidate_transaction_sha256"]),
            core_preflight_seal_sha256=str(report["core_preflight_seal_sha256"]),
            preflight_seal_sha256=str(report["preflight_seal_sha256"]),
            library_binding_sha256=str(authorization["bridge"]["library_binding_sha256"]),
            package_children=tuple(dict(child) for child in children),
            expected_post_operation=dict(expected_post),
            operation_id=operation_id,
        )

    def to_dict(self, *, include_bundle_hash: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "format": self.format,
            "artifacts": {
                "sealed_report": self.sealed_report.to_dict(),
                "baseline_backup": self.baseline_backup.to_dict(),
                "catalog": self.catalog.to_dict(),
                "template": self.template.to_dict(),
                "capacity_response": self.capacity_response.to_dict(),
                "package_manifest": self.package_manifest.to_dict(),
            },
            "selected_item_id": self.selected_item_id,
            "device_identity": list(self.device_identity),
            "expected_folder_name": self.expected_folder_name,
            "timestamp_policy": self.timestamp_policy,
            "fixed_state_policy": self.fixed_state_policy,
            "fixed_state_before_sha256": list(self.fixed_state_before_sha256),
            "fixed_state_candidate_sha256": list(self.fixed_state_candidate_sha256),
            "bookmark_binding_sha256": self.bookmark_binding_sha256,
            "new_record_timestamp_be32": self.new_record_timestamp_be32,
            "bulk_out_endpoint": self.bulk_out_endpoint,
            "owner_approval_phrase": self.owner_approval_phrase,
            "confirmation_phrase": self.confirmation_phrase,
            "confirmation_policy": self.confirmation_policy,
            "baseline_state_identity_sha256": self.baseline_state_identity_sha256,
            "capacity_response_sha256": self.capacity_response_sha256,
            "candidate_audit_sha256": self.candidate_audit_sha256,
            "authorization_sha256": self.authorization_sha256,
            "expected_post_operation_sha256": self.expected_post_operation_sha256,
            "candidate_blob_sha256": self.candidate_blob_sha256,
            "transaction_sha256": self.transaction_sha256,
            "core_preflight_seal_sha256": self.core_preflight_seal_sha256,
            "preflight_seal_sha256": self.preflight_seal_sha256,
            "library_binding_sha256": self.library_binding_sha256,
            "package_children": [_thaw(child) for child in self.package_children],
            "expected_post_operation": _thaw(self.expected_post_operation),
            "evidence_output_policy": dict(EVIDENCE_OUTPUT_POLICY),
            "safety": {
                "automatic_retry_allowed": False,
                "max_sender_calls": 1,
                "transaction_request": "0x101b",
                "accepted_completion": "0x0000",
            },
        }
        if self.operation_id is not None:
            value["operation_id"] = self.operation_id
        if include_bundle_hash:
            value["bundle_sha256"] = self.bundle_sha256
        return value

    def write(self, destination: Path) -> Path:
        """Write one new hash-only bundle manifest without candidate bytes."""

        path = Path(destination).expanduser().resolve()
        if path.exists():
            raise OperationBundleError(f"refusing to overwrite operation bundle: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=True, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        return path

    def verify_artifacts(self) -> None:
        """Verify all existing artifact members before any runtime callback."""

        for artifact in (
            self.sealed_report,
            self.baseline_backup,
            self.catalog,
            self.template,
            self.capacity_response,
            self.package_manifest,
        ):
            artifact.verify()


def _artifact_from_dict(value: Any, label: str) -> OperationArtifact:
    if not isinstance(value, Mapping):
        raise OperationBundleError(f"{label} artifact is malformed")
    allowed = {"path", "sha256", "basis", "size_bytes"}
    if set(value) - allowed or not {"path", "sha256", "basis"}.issubset(value):
        raise OperationBundleError(f"{label} artifact schema differs")
    return OperationArtifact(
        path=_absolute_path(value["path"], f"{label}.path"),
        sha256=_digest(value["sha256"], f"{label}.sha256"),
        basis=value["basis"],
        size_bytes=value.get("size_bytes"),
    )


def load_operation_bundle(path: Path, *, verify_artifacts: bool = True) -> PreparedLibraryPackageOperationBundle:
    """Strictly load one bundle manifest and optionally verify its artifacts."""

    source = Path(path).expanduser().resolve()
    value = _strict_object(source)
    required = {
        "format",
        "artifacts",
        "selected_item_id",
        "device_identity",
        "expected_folder_name",
        "timestamp_policy",
        "fixed_state_policy",
        "fixed_state_before_sha256",
        "fixed_state_candidate_sha256",
        "bookmark_binding_sha256",
        "new_record_timestamp_be32",
        "bulk_out_endpoint",
        "owner_approval_phrase",
        "confirmation_phrase",
        "confirmation_policy",
        "baseline_state_identity_sha256",
        "capacity_response_sha256",
        "candidate_audit_sha256",
        "authorization_sha256",
        "expected_post_operation_sha256",
        "candidate_blob_sha256",
        "transaction_sha256",
        "core_preflight_seal_sha256",
        "preflight_seal_sha256",
        "library_binding_sha256",
        "package_children",
        "expected_post_operation",
        "evidence_output_policy",
        "safety",
        "bundle_sha256",
    }
    optional = {"operation_id"}
    required_fields = set(value) - optional
    unexpected = required_fields - required
    if required_fields != required or unexpected:
        raise OperationBundleError(
            f"operation bundle schema fields differ: missing={sorted(required - set(value))}, "
            f"unexpected={sorted(unexpected)}"
        )
    expected_hash = _digest(value["bundle_sha256"], "bundle_sha256")
    unsigned = dict(value)
    unsigned.pop("bundle_sha256")
    if _sha256(_canonical_json(unsigned)) != expected_hash:
        raise OperationBundleError("operation bundle self-hash does not match contents")
    artifacts = value["artifacts"]
    if not isinstance(artifacts, Mapping) or set(artifacts) != {
        "sealed_report",
        "baseline_backup",
        "catalog",
        "template",
        "capacity_response",
        "package_manifest",
    }:
        raise OperationBundleError("operation bundle artifact schema differs")
    output_policy = value["evidence_output_policy"]
    if output_policy != EVIDENCE_OUTPUT_POLICY:
        raise OperationBundleError("operation bundle evidence output policy differs")
    safety = value["safety"]
    if safety != {
        "automatic_retry_allowed": False,
        "max_sender_calls": 1,
        "transaction_request": "0x101b",
        "accepted_completion": "0x0000",
    }:
        raise OperationBundleError("operation bundle safety policy differs")
    try:
        bundle = PreparedLibraryPackageOperationBundle(
            sealed_report=_artifact_from_dict(artifacts["sealed_report"], "sealed_report"),
            baseline_backup=_artifact_from_dict(artifacts["baseline_backup"], "baseline_backup"),
            catalog=_artifact_from_dict(artifacts["catalog"], "catalog"),
            template=_artifact_from_dict(artifacts["template"], "template"),
            capacity_response=_artifact_from_dict(artifacts["capacity_response"], "capacity_response"),
            package_manifest=_artifact_from_dict(artifacts["package_manifest"], "package_manifest"),
            selected_item_id=value["selected_item_id"],
            device_identity=tuple(value["device_identity"]),
            expected_folder_name=value["expected_folder_name"],
            timestamp_policy=value["timestamp_policy"],
            fixed_state_policy=value["fixed_state_policy"],
            fixed_state_before_sha256=tuple(value["fixed_state_before_sha256"]),
            fixed_state_candidate_sha256=tuple(value["fixed_state_candidate_sha256"]),
            bookmark_binding_sha256=value["bookmark_binding_sha256"],
            new_record_timestamp_be32=value["new_record_timestamp_be32"],
            bulk_out_endpoint=value["bulk_out_endpoint"],
            owner_approval_phrase=value["owner_approval_phrase"],
            confirmation_phrase=value["confirmation_phrase"],
            confirmation_policy=value["confirmation_policy"],
            baseline_state_identity_sha256=value["baseline_state_identity_sha256"],
            capacity_response_sha256=value["capacity_response_sha256"],
            candidate_audit_sha256=value["candidate_audit_sha256"],
            authorization_sha256=value["authorization_sha256"],
            expected_post_operation_sha256=value["expected_post_operation_sha256"],
            candidate_blob_sha256=value["candidate_blob_sha256"],
            transaction_sha256=value["transaction_sha256"],
            core_preflight_seal_sha256=value["core_preflight_seal_sha256"],
            preflight_seal_sha256=value["preflight_seal_sha256"],
            library_binding_sha256=value["library_binding_sha256"],
            package_children=tuple(value["package_children"]),
            expected_post_operation=value["expected_post_operation"],
            format=value["format"],
            operation_id=value.get("operation_id"),
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, OperationBundleError):
            raise
        raise OperationBundleError(f"operation bundle is malformed: {exc}") from exc
    if bundle.bundle_sha256 != expected_hash:
        raise OperationBundleError("operation bundle hash changed during loading")
    if verify_artifacts:
        bundle.verify_artifacts()
    return bundle


__all__ = [
    "EVIDENCE_OUTPUT_POLICY",
    "OPERATION_BUNDLE_FORMAT",
    "OperationArtifact",
    "OperationBundleError",
    "PreparedLibraryPackageOperationBundle",
    "load_operation_bundle",
]
