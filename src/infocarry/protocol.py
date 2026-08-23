"""Read-only InfoCarry command framing and receive state machine.

This layer is independent of PyUSB so every request can be tested without a
physical device. Commands are denied unless the caller explicitly allowlists
them; the production default is therefore incapable of sending a command.
"""

from dataclasses import dataclass
import struct
import time
from typing import Callable, FrozenSet, Optional, Protocol


CONTROL_OUT_VENDOR_DEVICE = 0x40
CONTROL_IN_VENDOR_DEVICE = 0xC0

REQUEST_BEGIN_RECEIVE = 0x01
REQUEST_TRANSFER_STATE = 0x03
REQUEST_COMPLETION = 0x04

STATUS_READY = 0x0000
STATUS_FAILURE_1 = 0x0001
STATUS_FAILURE_2 = 0x0002
STATUS_BUSY = 0x0003

MAX_BULK_CHUNK = 128 * 1024


class ProtocolError(RuntimeError):
    """Base class for a rejected or failed InfoCarry receive operation."""


class CommandNotAllowedError(ProtocolError):
    """Raised before USB access when a command is not explicitly allowlisted."""


class TransferCancelledError(ProtocolError):
    """Raised when the caller requests cancellation."""


class TransferTimeoutError(ProtocolError):
    """Raised when the device remains busy past the configured deadline."""


class DeviceStatusError(ProtocolError):
    """Raised for a failure, unexpected state, or nonzero completion result."""

    def __init__(self, stage: str, status: int):
        self.stage = stage
        self.status = status
        super().__init__(f"device returned {stage} status 0x{status:04x}")


class TransferLengthError(ProtocolError):
    """Raised when USB returns a short, empty, or oversized transfer."""


class ReadOnlyBackend(Protocol):
    """Minimal USB operations required by the read-only receive protocol."""

    def control_out(
        self,
        request_type: int,
        request: int,
        value: int,
        index: int,
        data: bytes,
        timeout_ms: int,
    ) -> int:
        ...

    def control_in(
        self,
        request_type: int,
        request: int,
        value: int,
        index: int,
        length: int,
        timeout_ms: int,
    ) -> bytes:
        ...

    def bulk_read(self, endpoint: int, length: int, timeout_ms: int) -> bytes:
        ...


def build_command_header(command: int, payload_length: int) -> bytes:
    """Encode the verified six-byte little-endian command header."""

    if not 0 <= command <= 0xFFFF:
        raise ValueError(f"command must fit uint16, got {command!r}")
    if not 0 <= payload_length <= 0xFFFFFFFF:
        raise ValueError(f"payload length must fit uint32, got {payload_length!r}")
    return struct.pack("<HI", command, payload_length)


def _u16le_exact(data: bytes, stage: str) -> int:
    if len(data) != 2:
        raise TransferLengthError(
            f"{stage} control transfer returned {len(data)} bytes; expected exactly 2"
        )
    return int.from_bytes(data, "little")


@dataclass(frozen=True)
class ReceivePolicy:
    control_timeout_ms: int = 1000
    bulk_timeout_ms: int = 5000
    busy_timeout_seconds: float = 100.0
    busy_poll_interval_seconds: float = 0.1
    max_bulk_chunk: int = MAX_BULK_CHUNK

    def __post_init__(self) -> None:
        if self.control_timeout_ms <= 0 or self.bulk_timeout_ms <= 0:
            raise ValueError("USB timeouts must be positive")
        if self.busy_timeout_seconds <= 0:
            raise ValueError("busy timeout must be positive")
        if self.busy_poll_interval_seconds <= 0:
            raise ValueError("busy poll interval must be positive")
        if not 1 <= self.max_bulk_chunk <= MAX_BULK_CHUNK:
            raise ValueError(f"bulk chunk must be between 1 and {MAX_BULK_CHUNK}")


class ReadOnlyReceiver:
    """Execute the verified device-to-host transaction for allowlisted commands."""

    def __init__(
        self,
        backend: ReadOnlyBackend,
        bulk_in_endpoint: int,
        *,
        allowed_commands: FrozenSet[int] = frozenset(),
        policy: ReceivePolicy = ReceivePolicy(),
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 0x80 <= bulk_in_endpoint <= 0x8F:
            raise ValueError(f"0x{bulk_in_endpoint:02x} is not a USB IN endpoint")
        self._backend = backend
        self._bulk_in_endpoint = bulk_in_endpoint
        self._allowed_commands = allowed_commands
        self._policy = policy
        self._clock = clock
        self._sleep = sleep

    def receive(
        self,
        command: int,
        payload_length: int,
        *,
        cancelled: Optional[Callable[[], bool]] = None,
    ) -> bytes:
        if command not in self._allowed_commands:
            raise CommandNotAllowedError(
                f"command 0x{command:04x} is not enabled for this read-only session"
            )
        header = build_command_header(command, payload_length)
        written = self._backend.control_out(
            CONTROL_OUT_VENDOR_DEVICE,
            REQUEST_BEGIN_RECEIVE,
            0,
            0,
            header,
            self._policy.control_timeout_ms,
        )
        if written != len(header):
            raise TransferLengthError(
                f"command header transfer wrote {written} bytes; expected {len(header)}"
            )

        try:
            payload = self._receive_payload(payload_length, cancelled)
        except ProtocolError:
            # The legacy client queries request 4 after an interrupted data
            # phase. Preserve the primary, more useful error if cleanup fails.
            try:
                self._read_completion(require_success=False)
            except ProtocolError:
                pass
            raise

        self._read_completion(require_success=True)
        return payload

    def _receive_payload(
        self, payload_length: int, cancelled: Optional[Callable[[], bool]]
    ) -> bytes:
        received = bytearray()
        while len(received) < payload_length:
            self._raise_if_cancelled(cancelled)
            self._wait_until_ready(cancelled)
            requested = min(
                self._policy.max_bulk_chunk, payload_length - len(received)
            )
            chunk = self._backend.bulk_read(
                self._bulk_in_endpoint, requested, self._policy.bulk_timeout_ms
            )
            if not chunk:
                raise TransferLengthError("bulk-IN transfer returned no data")
            if len(chunk) > requested:
                raise TransferLengthError(
                    f"bulk-IN transfer returned {len(chunk)} bytes after requesting {requested}"
                )
            received.extend(chunk)
        return bytes(received)

    def _wait_until_ready(
        self, cancelled: Optional[Callable[[], bool]]
    ) -> None:
        deadline = self._clock() + self._policy.busy_timeout_seconds
        while True:
            self._raise_if_cancelled(cancelled)
            state = _u16le_exact(
                self._backend.control_in(
                    CONTROL_IN_VENDOR_DEVICE,
                    REQUEST_TRANSFER_STATE,
                    0,
                    0,
                    2,
                    self._policy.control_timeout_ms,
                ),
                "transfer-state",
            )
            if state == STATUS_READY:
                return
            if state != STATUS_BUSY:
                raise DeviceStatusError("transfer-state", state)
            remaining = deadline - self._clock()
            if remaining <= 0:
                raise TransferTimeoutError(
                    f"device remained busy for {self._policy.busy_timeout_seconds:g} seconds"
                )
            self._sleep(min(self._policy.busy_poll_interval_seconds, remaining))

    def _read_completion(self, *, require_success: bool) -> int:
        completion = _u16le_exact(
            self._backend.control_in(
                CONTROL_IN_VENDOR_DEVICE,
                REQUEST_COMPLETION,
                0,
                0,
                2,
                self._policy.control_timeout_ms,
            ),
            "completion",
        )
        if require_success and completion != STATUS_READY:
            raise DeviceStatusError("completion", completion)
        return completion

    @staticmethod
    def _raise_if_cancelled(cancelled: Optional[Callable[[], bool]]) -> None:
        if cancelled is not None and cancelled():
            raise TransferCancelledError("receive operation was cancelled")
