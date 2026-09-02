"""Machine-enforced capability policy for the first product envelope.

The profile is deliberately narrower than a general ebook promise and is
separate from native proof.  It describes what the product may validate and
review: one new flat root folder containing one to eight ordered strict TXT
or validated one-bit BMP children.  Live execution is explicitly disabled in
this profile; a later R3 boundary must enable a separately reviewed exact
operation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence


CAPABILITY_PROFILE_FORMAT = "infocarry-capability-profile-v1"
INITIAL_EXPERIMENTAL_PROFILE_ID = "experimental-flat-root-folder-txt-bmp-v1"
CAPABILITY_PROFILE_STATUS = "defined_not_live_enabled"
_DIGEST_LENGTH = 64


class CapabilityProfileError(ValueError):
    """Raised when a capability policy or prepared package is unsafe."""


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
    if isinstance(value, list):
        return tuple(_freeze(child) for child in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw(child) for child in value]
    return value


_PROFILE_DOCUMENT: dict[str, Any] = {
    "format": CAPABILITY_PROFILE_FORMAT,
    "profile_id": INITIAL_EXPERIMENTAL_PROFILE_ID,
    "device_model_profile_id": "sony-vnw-v15-reviewed-v1",
    "version": 1,
    "status": CAPABILITY_PROFILE_STATUS,
    "operation": {
        "name": "add_one_new_root_folder",
        "root_folder_count": 1,
        "target_policy": "new_absent_root_folder",
        "conflict_policy": "reject_any_existing_path",
        "overwrite_allowed": False,
        "merge_allowed": False,
        "replace_allowed": False,
        "delete_allowed": False,
        "nesting_allowed": False,
        "package_count": 1,
        "logical_transaction_count": 1,
        "allowed_record_types": ["txt", "bmp"],
    },
    "selection": {
        "local_file_or_folder": True,
        "drag_and_drop": True,
        "explicit_package_grouping": True,
        "automatic_grouping": False,
        "ordering_controls": ["move_up", "move_down"],
    },
    "children": {
        "minimum": 1,
        "maximum": 8,
        "ordered": True,
        "flat_only": True,
        "duplicate_names": "reject_case_insensitive",
        "relative_name_policy": "one_cp932_path_component",
    },
    "limits": {
        "max_folder_name_cp932_bytes": 39,
        "max_child_name_cp932_bytes": 39,
        "max_source_bytes_per_child": 1048576,
        "max_prepared_payload_bytes_per_child": 1048576,
        "max_source_bytes_total": 4194304,
        "max_prepared_payload_bytes_total": 1048576,
    },
    "txt": {
        "source_encoding": "utf-8",
        "prepared_encoding": "cp932",
        "newline_policy": "crlf",
        "replacement_allowed": False,
        "embedded_nul_allowed": False,
        "native_prefix_bytes": 32,
    },
    "bmp": {
        "signature": "BM",
        "width": 237,
        "height": 320,
        "bits_per_pixel": 1,
        "compression": "BI_RGB",
        "palette_entries": 2,
        "orientation": "bottom_up_or_top_down",
        "native_prefix_bytes": 16,
    },
    "capacity": {
        "fresh_complete_backup_required": True,
        "native_capacity_query": "0x0019",
        "exact_candidate_growth_required": True,
        "nonnegative_margin_required": True,
        "unknown_capacity_fails_closed": True,
    },
    "verification": {
        "complete_post_write_backup_required": True,
        "independent_semantic_readback_required": True,
        "allowed_differences": [
            "explicit_new_record_timestamp_policy",
            "derived_checksum_effects",
        ],
        "unlisted_differences": "fail_closed",
    },
    "recovery": {
        "cancel_allowed_before_transmission_only": True,
        "automatic_retry_allowed": False,
        "accepted_completion": "0x0000",
        "indeterminate_write_lock_required": True,
        "backup_is_not_undo": True,
    },
    "exposure": {
        "live_enabled": False,
        "normal_gui_send_exposed": False,
        "normal_cli_send_exposed": False,
        "unsupported_shapes": "preview_only_with_reason",
    },
}

INITIAL_EXPERIMENTAL_CAPABILITY_PROFILE: Mapping[str, Any] = _freeze(
    _PROFILE_DOCUMENT
)


def _is_digest(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != _DIGEST_LENGTH:
        return False
    return value == value.lower() and all(
        character in "0123456789abcdef" for character in value
    )


def _validate_component(value: Any, *, label: str, maximum: int) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CapabilityProfileError(f"{label} must be one trimmed path component")
    if value in {".", ".."} or any(
        character in value for character in ("/", "\\", "\x00")
    ) or any(ord(character) < 0x20 for character in value):
        raise CapabilityProfileError(f"{label} contains an unsafe path character")
    try:
        encoded = value.encode("cp932", errors="strict")
    except UnicodeEncodeError as exc:
        raise CapabilityProfileError(f"{label} is not representable in CP932") from exc
    if len(encoded) > maximum:
        raise CapabilityProfileError(
            f"{label} exceeds the {maximum}-byte CP932 policy limit"
        )


def validate_capability_profile(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the complete immutable initial profile, rejecting drift."""

    if not isinstance(value, Mapping):
        raise CapabilityProfileError("capability profile must be an object")
    normalized = _thaw(value)
    if normalized != _PROFILE_DOCUMENT:
        raise CapabilityProfileError(
            "capability profile differs from the reviewed initial envelope"
        )
    return normalized


@dataclass(frozen=True)
class CapabilityProfile:
    """Validated policy object used by host-only planning boundaries."""

    document: Mapping[str, Any]

    def __post_init__(self) -> None:
        validated = validate_capability_profile(self.document)
        object.__setattr__(self, "document", _freeze(validated))

    @property
    def profile_id(self) -> str:
        return str(self.document["profile_id"])

    @property
    def device_model_profile_id(self) -> str:
        return str(self.document["device_model_profile_id"])

    @property
    def sha256(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_dict())).hexdigest()

    @property
    def live_enabled(self) -> bool:
        return bool(self.document["exposure"]["live_enabled"])

    def to_dict(self) -> dict[str, Any]:
        return _thaw(self.document)

    def validate_package(
        self,
        *,
        folder_name: str,
        children: Sequence[Mapping[str, Any]],
        existing_paths: Iterable[str] = (),
    ) -> tuple[dict[str, Any], ...]:
        """Validate one explicitly ordered flat package against this policy."""

        child_policy = self.document["children"]
        limits = self.document["limits"]
        operation = self.document["operation"]
        if not isinstance(children, Sequence) or isinstance(children, (str, bytes)):
            raise CapabilityProfileError("package children must be an ordered sequence")
        if not child_policy["minimum"] <= len(children) <= child_policy["maximum"]:
            raise CapabilityProfileError("package child count is outside the 1–8 envelope")
        _validate_component(
            folder_name,
            label="package folder name",
            maximum=limits["max_folder_name_cp932_bytes"],
        )
        folder_path = f"root\\{folder_name}"
        existing = {str(path).casefold() for path in existing_paths}
        if folder_path.casefold() in existing:
            raise CapabilityProfileError("package destination folder already exists")

        normalized: list[dict[str, Any]] = []
        names: set[str] = set()
        total_source = 0
        total_prepared = 0
        for index, child in enumerate(children):
            if not isinstance(child, Mapping):
                raise CapabilityProfileError(f"package child {index} is malformed")
            required = {
                "order",
                "kind",
                "name",
                "path",
                "source_sha256",
                "prepared_payload_sha256",
                "source_bytes",
                "prepared_payload_bytes",
            }
            if set(child) != required:
                missing = required - set(child)
                extra = set(child) - required
                raise CapabilityProfileError(
                    f"package child {index} schema differs; missing={sorted(missing)}, "
                    f"extra={sorted(extra)}"
                )
            if (
                isinstance(child["order"], bool)
                or not isinstance(child["order"], int)
                or child["order"] != index
            ):
                raise CapabilityProfileError("package child order is not contiguous")
            kind = child["kind"]
            if kind not in operation["allowed_record_types"]:
                raise CapabilityProfileError(f"package child {index} type is unsupported")
            name = child["name"]
            _validate_component(
                name,
                label=f"package child {index} name",
                maximum=limits["max_child_name_cp932_bytes"],
            )
            extension = ".txt" if kind == "txt" else ".bmp"
            basename = name[: -len(extension)] if name.casefold().endswith(extension) else ""
            if not basename or "." in basename or not name.casefold().endswith(extension):
                raise CapabilityProfileError(
                    f"package child {index} name does not match its type"
                )
            if name.casefold() in names:
                raise CapabilityProfileError("package child names must be unique")
            names.add(name.casefold())
            expected_path = f"{folder_path}\\{name}"
            if child["path"] != expected_path:
                raise CapabilityProfileError(
                    f"package child {index} path is not a flat destination child"
                )
            if expected_path.casefold() in existing:
                raise CapabilityProfileError(
                    f"package child destination already exists: {expected_path}"
                )
            if not _is_digest(child["source_sha256"]):
                raise CapabilityProfileError(f"package child {index} source hash is invalid")
            if not _is_digest(child["prepared_payload_sha256"]):
                raise CapabilityProfileError(
                    f"package child {index} prepared hash is invalid"
                )
            source_bytes = child["source_bytes"]
            prepared_bytes = child["prepared_payload_bytes"]
            if (
                isinstance(source_bytes, bool)
                or not isinstance(source_bytes, int)
                or source_bytes < 0
                or source_bytes > limits["max_source_bytes_per_child"]
            ):
                raise CapabilityProfileError(f"package child {index} source size is invalid")
            if (
                isinstance(prepared_bytes, bool)
                or not isinstance(prepared_bytes, int)
                or prepared_bytes < 0
                or prepared_bytes > limits["max_prepared_payload_bytes_per_child"]
            ):
                raise CapabilityProfileError(
                    f"package child {index} prepared size is invalid"
                )
            total_source += source_bytes
            total_prepared += prepared_bytes
            normalized.append(dict(child))

        if total_source > limits["max_source_bytes_total"]:
            raise CapabilityProfileError("package source aggregate exceeds policy limit")
        if total_prepared > limits["max_prepared_payload_bytes_total"]:
            raise CapabilityProfileError(
                "package prepared aggregate exceeds policy limit"
            )
        return tuple(normalized)


def initial_capability_profile() -> CapabilityProfile:
    """Return the reviewed initial profile without enabling live execution."""

    return CapabilityProfile(INITIAL_EXPERIMENTAL_CAPABILITY_PROFILE)


__all__ = [
    "CAPABILITY_PROFILE_FORMAT",
    "CAPABILITY_PROFILE_STATUS",
    "CapabilityProfile",
    "CapabilityProfileError",
    "INITIAL_EXPERIMENTAL_CAPABILITY_PROFILE",
    "INITIAL_EXPERIMENTAL_PROFILE_ID",
    "initial_capability_profile",
    "validate_capability_profile",
]
