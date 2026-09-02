"""Explicit device-model profiles for the constrained product boundary.

VID/PID identifies a USB/model match for a session; it is not a proven
physical-unit identity.  This module keeps model capability and session
observations explicit.  In particular, VNW-V10 is a declared product target
but has no inherited VNW-V15 protocol, format, capacity, or write capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .capacity_evidence import NativeCapacityEvidence

DEVICE_MODEL_PROFILE_FORMAT = "infocarry-device-model-profile-v1"
VNW_V15_MODEL_KEY = "sony-vnw-v15"
VNW_V10_MODEL_KEY = "sony-vnw-v10"
VNW_V15_PROFILE_ID = "sony-vnw-v15-reviewed-v1"
VNW_V10_PROFILE_ID = "sony-vnw-v10-uncharacterized-v1"
VNW_V15_CAPABILITY_PROFILE_ID = "experimental-flat-root-folder-txt-bmp-v1"
MODEL_STATUS_VERIFIED = "VERIFIED"
MODEL_STATUS_UNCHARACTERIZED = "UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED"


class DeviceModelProfileError(ValueError):
    """Raised when a model profile is unknown or internally inconsistent."""


KNOWN_DEVICE_MODEL_LOCK_KEYS = frozenset({VNW_V15_MODEL_KEY, VNW_V10_MODEL_KEY})


@dataclass(frozen=True)
class DeviceModelLockKey:
    """Opaque reviewed model namespace used only as diagnostic provenance."""

    value: str

    def __post_init__(self) -> None:
        if type(self.value) is not str or self.value not in KNOWN_DEVICE_MODEL_LOCK_KEYS:
            raise DeviceModelProfileError(
                "lock key is not supplied by a reviewed device-model profile"
            )


def _digest(value: Any, label: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise DeviceModelProfileError(f"{label} must be a lowercase SHA-256 digest")


@dataclass(frozen=True)
class DeviceModelProfile:
    """Reviewed model identity/capability metadata, separate from a session."""

    profile_id: str
    model_key: DeviceModelLockKey
    model_name: str
    capability_status: str
    usb_identity: tuple[str, str] | None
    transfer_capability_profile_id: str | None
    capacity_query: str | None
    capacity_interpreter: str | None
    read_only_discovery_required: bool

    def __post_init__(self) -> None:
        if not isinstance(self.model_key, DeviceModelLockKey):
            raise DeviceModelProfileError("model profile requires a reviewed model key")
        if not self.profile_id or not self.model_name:
            raise DeviceModelProfileError("model profile identity is incomplete")
        expected_keys = {
            VNW_V15_PROFILE_ID: VNW_V15_MODEL_KEY,
            VNW_V10_PROFILE_ID: VNW_V10_MODEL_KEY,
        }
        if (
            self.profile_id not in expected_keys
            or self.model_key.value != expected_keys[self.profile_id]
        ):
            raise DeviceModelProfileError("model profile identity is not reviewed")
        expected_usb = (
            ("0x054c", "0x001e") if self.profile_id == VNW_V15_PROFILE_ID else None
        )
        if self.usb_identity != expected_usb:
            raise DeviceModelProfileError("model USB identity differs from reviewed profile")
        if self.capability_status not in {
            MODEL_STATUS_VERIFIED,
            MODEL_STATUS_UNCHARACTERIZED,
        }:
            raise DeviceModelProfileError("unknown model capability status")
        expected_names = {
            VNW_V15_PROFILE_ID: "Sony InfoCarry VNW-V15",
            VNW_V10_PROFILE_ID: "Sony InfoCarry VNW-V10",
        }
        if self.model_name != expected_names[self.profile_id]:
            raise DeviceModelProfileError("model name differs from reviewed profile")
        expected_status = (
            MODEL_STATUS_VERIFIED
            if self.profile_id == VNW_V15_PROFILE_ID
            else MODEL_STATUS_UNCHARACTERIZED
        )
        if self.capability_status != expected_status:
            raise DeviceModelProfileError("model capability status differs from reviewed profile")
        if self.usb_identity is not None:
            if (
                not isinstance(self.usb_identity, tuple)
                or len(self.usb_identity) != 2
                or not all(isinstance(part, str) and part for part in self.usb_identity)
            ):
                raise DeviceModelProfileError("model USB identity is malformed")
        if self.capability_status == MODEL_STATUS_UNCHARACTERIZED and (
            self.transfer_capability_profile_id is not None
            or self.capacity_query is not None
            or self.capacity_interpreter is not None
            or self.read_only_discovery_required is not True
        ):
            raise DeviceModelProfileError(
                "uncharacterized model cannot carry transfer or capacity capability"
            )
        if self.capability_status == MODEL_STATUS_VERIFIED and (
            not self.transfer_capability_profile_id
            or not self.capacity_query
            or not self.capacity_interpreter
            or self.read_only_discovery_required is not False
        ):
            raise DeviceModelProfileError(
                "verified model profile lacks its reviewed transfer/capacity boundary"
            )
        if self.profile_id == VNW_V15_PROFILE_ID and (
            self.capacity_query != "0x0019"
            or self.capacity_interpreter
            != "64-byte response; big-endian +0x08 total candidate-model capacity"
        ):
            raise DeviceModelProfileError("VNW-V15 capacity interpreter differs from evidence")

    @property
    def lock_key(self) -> DeviceModelLockKey:
        """Return model-key metadata for diagnostic evidence, not lock scope."""

        return self.model_key

    @property
    def transfer_capable(self) -> bool:
        return self.capability_status == MODEL_STATUS_VERIFIED

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": DEVICE_MODEL_PROFILE_FORMAT,
            "profile_id": self.profile_id,
            "model_key": self.model_key.value,
            "model_name": self.model_name,
            "capability_status": self.capability_status,
            "usb_identity": None if self.usb_identity is None else list(self.usb_identity),
            "transfer_capability_profile_id": self.transfer_capability_profile_id,
            "capacity_query": self.capacity_query,
            "capacity_interpreter": self.capacity_interpreter,
            "read_only_discovery_required": self.read_only_discovery_required,
        }


@dataclass(frozen=True)
class CapacityObservation:
    """Fresh session capacity facts bound to an explicit model profile."""

    native_evidence: NativeCapacityEvidence
    model_profile_id: str
    capacity_response_sha256: str
    total_model_bytes: int
    baseline_model_bytes: int
    candidate_model_bytes: int
    candidate_growth_bytes: int
    remaining_growth_bytes: int
    remaining_after_transfer_bytes: int

    def __post_init__(self) -> None:
        if not isinstance(self.native_evidence, NativeCapacityEvidence):
            raise DeviceModelProfileError(
                "capacity observation requires verified parsed 0x0019 evidence"
            )
        if self.model_profile_id != VNW_V15_PROFILE_ID:
            raise DeviceModelProfileError(
                "capacity semantics are not verified for this model profile"
            )
        _digest(self.capacity_response_sha256, "capacity response sha256")
        if self.capacity_response_sha256 != self.native_evidence.raw_response_sha256:
            raise DeviceModelProfileError("capacity response hash differs from native evidence")
        if (
            self.native_evidence.capacity_limit_bytes != self.total_model_bytes
            or self.native_evidence.baseline_model_bytes != self.baseline_model_bytes
            or self.native_evidence.candidate_model_bytes != self.candidate_model_bytes
            or (
                self.native_evidence.candidate_model_bytes
                - self.native_evidence.baseline_model_bytes
                != self.candidate_growth_bytes
            )
            or self.native_evidence.remaining_growth_bytes != self.remaining_growth_bytes
        ):
            raise DeviceModelProfileError(
                "capacity facts differ from verified native evidence"
            )
        values = (
            self.total_model_bytes,
            self.baseline_model_bytes,
            self.candidate_model_bytes,
            self.candidate_growth_bytes,
            self.remaining_growth_bytes,
            self.remaining_after_transfer_bytes,
        )
        if any(type(value) is not int or value < 0 for value in values):
            raise DeviceModelProfileError("capacity values must be non-negative integers")
        if self.candidate_growth_bytes != (
            self.candidate_model_bytes - self.baseline_model_bytes
        ):
            raise DeviceModelProfileError("capacity candidate growth is inconsistent")
        if self.remaining_growth_bytes != (
            self.total_model_bytes - self.baseline_model_bytes
        ):
            raise DeviceModelProfileError("capacity remaining growth is inconsistent")
        if self.candidate_growth_bytes > self.remaining_growth_bytes:
            raise DeviceModelProfileError("candidate growth exceeds remaining capacity")
        if self.remaining_after_transfer_bytes != (
            self.total_model_bytes - self.candidate_model_bytes
        ):
            raise DeviceModelProfileError("capacity remaining margin is inconsistent")
        if self.candidate_model_bytes < self.baseline_model_bytes:
            raise DeviceModelProfileError("candidate model cannot shrink in this profile")
        if self.candidate_model_bytes > self.total_model_bytes:
            raise DeviceModelProfileError("candidate model exceeds total capacity")

    def to_dict(self) -> dict[str, Any]:
        return {
            "native_evidence": self.native_evidence.to_dict(),
            "model_profile_id": self.model_profile_id,
            "capacity_response_sha256": self.capacity_response_sha256,
            "total_model_bytes": self.total_model_bytes,
            "baseline_model_bytes": self.baseline_model_bytes,
            "candidate_model_bytes": self.candidate_model_bytes,
            "candidate_growth_bytes": self.candidate_growth_bytes,
            "remaining_growth_bytes": self.remaining_growth_bytes,
            "remaining_after_transfer_bytes": self.remaining_after_transfer_bytes,
        }


VNW_V15_PROFILE = DeviceModelProfile(
    profile_id=VNW_V15_PROFILE_ID,
    model_key=DeviceModelLockKey(VNW_V15_MODEL_KEY),
    model_name="Sony InfoCarry VNW-V15",
    capability_status=MODEL_STATUS_VERIFIED,
    usb_identity=("0x054c", "0x001e"),
    transfer_capability_profile_id=VNW_V15_CAPABILITY_PROFILE_ID,
    capacity_query="0x0019",
    capacity_interpreter="64-byte response; big-endian +0x08 total candidate-model capacity",
    read_only_discovery_required=False,
)

VNW_V10_PROFILE = DeviceModelProfile(
    profile_id=VNW_V10_PROFILE_ID,
    model_key=DeviceModelLockKey(VNW_V10_MODEL_KEY),
    model_name="Sony InfoCarry VNW-V10",
    capability_status=MODEL_STATUS_UNCHARACTERIZED,
    usb_identity=None,
    transfer_capability_profile_id=None,
    capacity_query=None,
    capacity_interpreter=None,
    read_only_discovery_required=True,
)

_PROFILES: Mapping[str, DeviceModelProfile] = {
    VNW_V15_MODEL_KEY: VNW_V15_PROFILE,
    VNW_V10_MODEL_KEY: VNW_V10_PROFILE,
}


def reviewed_device_model_profile(model_key: str) -> DeviceModelProfile:
    """Resolve only an explicitly declared model key; unknown keys fail closed."""

    if type(model_key) is not str or model_key not in _PROFILES:
        raise DeviceModelProfileError("unknown device-model profile")
    return _PROFILES[model_key]


def validate_actionable_session(
    detected_profiles: Sequence[DeviceModelProfile],
) -> DeviceModelProfile:
    """Validate one freshly rediscovered actionable model without USB I/O."""

    if len(detected_profiles) != 1:
        raise DeviceModelProfileError(
            "an actionable session requires exactly one detected device model"
        )
    profile = detected_profiles[0]
    if not isinstance(profile, DeviceModelProfile):
        raise DeviceModelProfileError("detected model is not a reviewed profile")
    if not profile.transfer_capable:
        raise DeviceModelProfileError(
            "detected model has no reviewed transfer capability"
        )
    return profile


__all__ = [
    "CapacityObservation",
    "DEVICE_MODEL_PROFILE_FORMAT",
    "DeviceModelProfile",
    "DeviceModelProfileError",
    "DeviceModelLockKey",
    "KNOWN_DEVICE_MODEL_LOCK_KEYS",
    "MODEL_STATUS_UNCHARACTERIZED",
    "MODEL_STATUS_VERIFIED",
    "VNW_V10_MODEL_KEY",
    "VNW_V10_PROFILE",
    "VNW_V10_PROFILE_ID",
    "VNW_V15_CAPABILITY_PROFILE_ID",
    "VNW_V15_MODEL_KEY",
    "VNW_V15_PROFILE",
    "VNW_V15_PROFILE_ID",
    "reviewed_device_model_profile",
    "validate_actionable_session",
]
