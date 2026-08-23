"""Hash-bound native capacity evidence from one parsed ``0x0019`` response.

The response object is created only from the existing read-only hardware-info
parser.  A second immutable object binds that response to one verified
baseline and candidate model length.  Caller-supplied budgets, Manager UI
values, command ``0x0024``, and unknown ``field_14_be32`` values cannot create
native evidence through this module.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from .constants import INFOCARRY_PRODUCT_ID, SONY_VENDOR_ID
from .device_info import (
    COMMAND_HARDWARE_INFO,
    INFO_RESPONSE_LENGTH,
    RawInfoResponse,
    parse_hardware_info,
)


NATIVE_CAPACITY_EVIDENCE_VERSION = "infocarry-native-capacity-evidence-v1"
NATIVE_CAPACITY_EVIDENCE_SOURCE = "parsed_device_info_0x0019"
NATIVE_CAPACITY_FIELD_OFFSET = 0x08


class NativeCapacityEvidenceError(ValueError):
    """Raised when parsed native capacity evidence is incomplete or unsafe."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_identity(identity: tuple[int, int]) -> tuple[int, int]:
    if (
        not isinstance(identity, tuple)
        or len(identity) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) for value in identity)
    ):
        raise NativeCapacityEvidenceError("native capacity device identity is invalid")
    if identity != (SONY_VENDOR_ID, INFOCARRY_PRODUCT_ID):
        raise NativeCapacityEvidenceError("native capacity evidence is for the wrong device")
    return identity


def _validate_model_lengths(
    capacity_limit_bytes: int,
    baseline_model_bytes: int,
    candidate_model_bytes: int,
    remaining_growth_bytes: int,
) -> None:
    values = (
        ("capacity_limit_bytes", capacity_limit_bytes),
        ("baseline_model_bytes", baseline_model_bytes),
        ("candidate_model_bytes", candidate_model_bytes),
        ("remaining_growth_bytes", remaining_growth_bytes),
    )
    for label, value in values:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise NativeCapacityEvidenceError(f"{label} must be a non-negative integer")
    if candidate_model_bytes < baseline_model_bytes:
        raise NativeCapacityEvidenceError("candidate model is smaller than the baseline model")
    if candidate_model_bytes > capacity_limit_bytes:
        raise NativeCapacityEvidenceError("candidate model exceeds the native total capacity limit")
    if remaining_growth_bytes != capacity_limit_bytes - baseline_model_bytes:
        raise NativeCapacityEvidenceError("remaining growth does not match native capacity evidence")


@dataclass(frozen=True)
class NativeCapacityResponse:
    """Verified parsed response evidence before model lengths are bound."""

    device_identity: tuple[int, int]
    raw_response: bytes
    raw_response_sha256: str
    response_command: int
    field_offset: int
    capacity_limit_bytes: int
    evidence_source: str = NATIVE_CAPACITY_EVIDENCE_SOURCE
    evidence_version: str = NATIVE_CAPACITY_EVIDENCE_VERSION

    def __post_init__(self) -> None:
        _validate_identity(self.device_identity)
        if not isinstance(self.raw_response, bytes) or len(self.raw_response) != INFO_RESPONSE_LENGTH:
            raise NativeCapacityEvidenceError(
                f"native capacity response must be exactly {INFO_RESPONSE_LENGTH} bytes"
            )
        if self.raw_response_sha256 != _sha256(self.raw_response):
            raise NativeCapacityEvidenceError("native capacity raw response hash does not match bytes")
        if self.response_command != COMMAND_HARDWARE_INFO:
            raise NativeCapacityEvidenceError("native capacity evidence must use command 0x0019")
        if self.field_offset != NATIVE_CAPACITY_FIELD_OFFSET:
            raise NativeCapacityEvidenceError("native capacity field offset must be +0x08")
        if self.evidence_source != NATIVE_CAPACITY_EVIDENCE_SOURCE:
            raise NativeCapacityEvidenceError("native capacity source is not a parsed 0x0019 response")
        if self.evidence_version != NATIVE_CAPACITY_EVIDENCE_VERSION:
            raise NativeCapacityEvidenceError("unsupported native capacity evidence version")
        try:
            parsed = parse_hardware_info(self.raw_response)
        except Exception as exc:
            raise NativeCapacityEvidenceError(f"native capacity response is malformed: {exc}") from exc
        if self.capacity_limit_bytes != parsed.field_08_be32:
            raise NativeCapacityEvidenceError("native capacity value differs from parsed response +0x08")
        if isinstance(self.capacity_limit_bytes, bool) or not isinstance(self.capacity_limit_bytes, int) or self.capacity_limit_bytes <= 0:
            raise NativeCapacityEvidenceError("native capacity limit must be a positive integer")

    @classmethod
    def from_hardware_response(
        cls,
        response: RawInfoResponse,
        *,
        device_identity: tuple[int, int],
    ) -> "NativeCapacityResponse":
        if not isinstance(response, RawInfoResponse):
            raise NativeCapacityEvidenceError("capacity response must be a RawInfoResponse")
        if response.command != COMMAND_HARDWARE_INFO:
            raise NativeCapacityEvidenceError("capacity response command must be 0x0019")
        try:
            parsed = parse_hardware_info(response.data)
        except Exception as exc:
            raise NativeCapacityEvidenceError(f"capacity response failed 0x0019 parsing: {exc}") from exc
        raw = bytes(response.data)
        return cls(
            device_identity=_validate_identity(device_identity),
            raw_response=raw,
            raw_response_sha256=_sha256(raw),
            response_command=response.command,
            field_offset=NATIVE_CAPACITY_FIELD_OFFSET,
            capacity_limit_bytes=parsed.field_08_be32,
        )

    def bind_model_lengths(
        self,
        baseline_model_bytes: int,
        candidate_model_bytes: int,
    ) -> "NativeCapacityEvidence":
        if (
            isinstance(baseline_model_bytes, bool)
            or not isinstance(baseline_model_bytes, int)
            or isinstance(candidate_model_bytes, bool)
            or not isinstance(candidate_model_bytes, int)
        ):
            raise NativeCapacityEvidenceError("model lengths must be integers")
        remaining = self.capacity_limit_bytes - baseline_model_bytes
        _validate_model_lengths(
            self.capacity_limit_bytes,
            baseline_model_bytes,
            candidate_model_bytes,
            remaining,
        )
        return NativeCapacityEvidence(
            device_identity=self.device_identity,
            raw_response=self.raw_response,
            raw_response_sha256=self.raw_response_sha256,
            response_command=self.response_command,
            field_offset=self.field_offset,
            capacity_limit_bytes=self.capacity_limit_bytes,
            baseline_model_bytes=baseline_model_bytes,
            candidate_model_bytes=candidate_model_bytes,
            remaining_growth_bytes=remaining,
            evidence_source=self.evidence_source,
            evidence_version=self.evidence_version,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_identity": {
                "vendor_id": self.device_identity[0],
                "product_id": self.device_identity[1],
            },
            "response_command": f"0x{self.response_command:04x}",
            "field_offset": f"0x{self.field_offset:02x}",
            "capacity_limit_bytes": self.capacity_limit_bytes,
            "raw_response_length": len(self.raw_response),
            "raw_response_sha256": self.raw_response_sha256,
            "evidence_source": self.evidence_source,
            "evidence_version": self.evidence_version,
        }


@dataclass(frozen=True)
class NativeCapacityEvidence(NativeCapacityResponse):
    """Native response evidence bound to one baseline and candidate model."""

    baseline_model_bytes: int = 0
    candidate_model_bytes: int = 0
    remaining_growth_bytes: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _validate_model_lengths(
            self.capacity_limit_bytes,
            self.baseline_model_bytes,
            self.candidate_model_bytes,
            self.remaining_growth_bytes,
        )

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result.update(
            {
                "baseline_model_bytes": self.baseline_model_bytes,
                "candidate_model_bytes": self.candidate_model_bytes,
                "candidate_growth_bytes": self.candidate_model_bytes - self.baseline_model_bytes,
                "remaining_growth_bytes": self.remaining_growth_bytes,
            }
        )
        return result


__all__ = [
    "NATIVE_CAPACITY_EVIDENCE_SOURCE",
    "NATIVE_CAPACITY_EVIDENCE_VERSION",
    "NATIVE_CAPACITY_FIELD_OFFSET",
    "NativeCapacityEvidence",
    "NativeCapacityEvidenceError",
    "NativeCapacityResponse",
]
