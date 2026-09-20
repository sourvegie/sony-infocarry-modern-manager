"""Read-only Device Home inspection and capacity presentation."""

from __future__ import annotations

from dataclasses import dataclass
import errno
from typing import Any, Callable, Optional, Sequence

from .capacity_evidence import NativeCapacityResponse
from .constants import INFOCARRY_PRODUCT_ID, SONY_VENDOR_ID
from .device_info import DeviceInfoClient
from .device_model_profile import VNW_V15_PROFILE
from .protocol import TransferLengthError
from .transport import InfoCarrySession
from .usb_access import DeviceAccessError, describe_device, find_sony_devices


@dataclass(frozen=True)
class DeviceHomeSnapshot:
    """User-facing read-only connection state and hidden technical details."""

    state: str
    heading: str
    message: str
    capacity_bytes: Optional[int] = None
    technical_details: str = ""


def classify_device_error(error: BaseException) -> tuple[str, str]:
    """Map common read-only USB failures to a useful product message."""

    detail = str(error).strip() or type(error).__name__
    lower = detail.casefold()
    codes: list[int] = []
    for candidate in (error, error.__cause__, error.__context__):
        if candidate is None:
            continue
        for attribute in ("errno", "backend_error_code"):
            value = getattr(candidate, attribute, None)
            if isinstance(value, int) and not isinstance(value, bool):
                codes.append(value)

    if any(word in lower for word in ("libusb", "backend unavailable", "could not be located")):
        return (
            "backend_unavailable",
            "USB support is unavailable. Reinstall InfoCarry Manager or contact support.",
        )
    if (
        errno.EACCES in codes
        or errno.EPERM in codes
        or any(word in lower for word in ("access denied", "permission denied", "not permitted"))
    ):
        return (
            "access_denied",
            "macOS could not access this USB device. Close other USB software and reconnect it.",
        )
    if errno.EBUSY in codes or any(word in lower for word in ("device busy", "resource busy", "busy")):
        return (
            "device_busy",
            "Another application is using the device. Close it, then refresh Device Home.",
        )
    if (
        errno.ENODEV in codes
        or any(word in lower for word in ("no device", "disconnected", "not connected", "device vanished"))
    ):
        return (
            "disconnected_during_read",
            "The device disconnected while being read. Reconnect it before trying again.",
        )
    if isinstance(error, TransferLengthError) or any(
        word in lower for word in ("malformed", "wrong length", "expected 64 bytes", "response is")
    ):
        return (
            "unrecognized_response",
            "The device returned data InfoCarry could not recognize. No write was attempted.",
        )
    if isinstance(error, DeviceAccessError) and "not found" in lower:
        return ("disconnected", "No supported InfoCarry is connected.")
    return (
        "read_failed",
        "InfoCarry could not finish the read. Check the cable and connection, then refresh.",
    )


class DeviceHomeService:
    """Inspect only a reviewed VNW-V15 and its established read-only capacity."""

    def __init__(
        self,
        *,
        discover: Callable[[], Sequence[Any]] = find_sony_devices,
        open_session: Callable[..., InfoCarrySession] = InfoCarrySession.open,
    ) -> None:
        self._discover = discover
        self._open_session = open_session

    def inspect(self) -> DeviceHomeSnapshot:
        try:
            devices = tuple(self._discover())
        except Exception as exc:
            code, message = classify_device_error(exc)
            return DeviceHomeSnapshot(
                state=code,
                heading="Device status unavailable",
                message=message,
                technical_details=f"USB discovery failed: {type(exc).__name__}: {exc}",
            )

        if not devices:
            return DeviceHomeSnapshot(
                state="disconnected",
                heading="Device disconnected",
                message="Connect a Sony InfoCarry VNW-V15, then refresh Device Home.",
            )
        if len(devices) != 1:
            return DeviceHomeSnapshot(
                state="ambiguous",
                heading="More than one Sony USB device found",
                message="Connect one reviewed VNW-V15 at a time, then refresh Device Home.",
                technical_details=f"Sony USB devices found: {len(devices)}",
            )

        try:
            observed = describe_device(devices[0])
        except (AttributeError, TypeError, ValueError) as exc:
            return DeviceHomeSnapshot(
                state="unrecognized_device",
                heading="Unsupported USB device",
                message="This Sony USB device is not a reviewed InfoCarry model.",
                technical_details=f"USB identity could not be read: {type(exc).__name__}: {exc}",
            )
        technical = (
            f"Reviewed model profile: {VNW_V15_PROFILE.profile_id}\n"
            f"Session VID/PID: 0x{observed.vendor_id:04x}:0x{observed.product_id:04x}\n"
            f"Session bus/address: {observed.bus!r}/{observed.address!r}\n"
            "Physical-unit identity: not established"
        )
        if (observed.vendor_id, observed.product_id) != (SONY_VENDOR_ID, INFOCARRY_PRODUCT_ID):
            return DeviceHomeSnapshot(
                state="unsupported_device",
                heading="Unsupported Sony USB device",
                message="This device is not the reviewed VNW-V15. No InfoCarry query was sent.",
                technical_details=technical,
            )

        try:
            with self._open_session(devices[0]) as session:
                response = DeviceInfoClient(session).read_hardware()
            capacity = NativeCapacityResponse.from_hardware_response(
                response,
                device_identity=(observed.vendor_id, observed.product_id),
            )
        except Exception as exc:
            code, message = classify_device_error(exc)
            return DeviceHomeSnapshot(
                state=code,
                heading="Sony InfoCarry VNW-V15",
                message=message,
                technical_details=f"{technical}\nRead-only 0x0019 query failed: {type(exc).__name__}: {exc}",
            )

        return DeviceHomeSnapshot(
            state="connected",
            heading="Sony InfoCarry VNW-V15 connected",
            message="VNW-V15 matched the reviewed read-only profile for this session.",
            capacity_bytes=capacity.capacity_limit_bytes,
            technical_details=(
                f"{technical}\n"
                f"Capacity query: 0x{capacity.response_command:04x}, "
                f"response bytes: {len(capacity.raw_response)}, "
                f"SHA-256: {capacity.raw_response_sha256}"
            ),
        )


def format_capacity_summary(
    *,
    total_model_bytes: Optional[int],
    baseline_model_bytes: Optional[int],
    backup_timestamp: Optional[str],
    required_candidate_growth_bytes: Optional[int] = None,
    metadata_overhead_bytes: Optional[int] = None,
) -> str:
    """Present canonical total/baseline/growth quantities without free-space claims."""

    def _size(value: Optional[int]) -> str:
        if value is None:
            return "Not evaluated"
        if type(value) is not int or value < 0:
            raise ValueError("capacity display values must be non-negative integers")
        return f"{value:,} bytes ({value / (1024 * 1024):,.1f} MiB)"

    lines = [f"Total model capacity: {_size(total_model_bytes)}"]
    if baseline_model_bytes is None:
        lines.append("Current baseline from a complete backup: Not evaluated")
        lines.append("Remaining growth capacity: Not evaluated")
    else:
        when = f" ({backup_timestamp})" if backup_timestamp else ""
        lines.append(
            f"Current baseline from loaded complete backup{when}: {_size(baseline_model_bytes)}"
        )
        if total_model_bytes is None:
            lines.append("Remaining growth capacity against this snapshot: Not evaluated")
        elif baseline_model_bytes > total_model_bytes:
            lines.append("Remaining growth capacity against this snapshot: Not evaluated")
        else:
            lines.append(
                "Remaining growth capacity against this snapshot: "
                f"{_size(total_model_bytes - baseline_model_bytes)}"
            )
    lines.append(f"Required candidate growth: {_size(required_candidate_growth_bytes)}")
    if metadata_overhead_bytes is None:
        lines.append(
            "Metadata overhead: included in whole-candidate sizing during transfer review"
        )
    else:
        lines.append(f"Candidate metadata overhead: {_size(metadata_overhead_bytes)}")
    lines.append("A saved backup is a snapshot; refresh it before relying on current contents.")
    return "\n".join(lines)


__all__ = [
    "DeviceHomeService",
    "DeviceHomeSnapshot",
    "classify_device_error",
    "format_capacity_summary",
]
