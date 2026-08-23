"""Explicitly authorized host-to-device ``0x101b`` sender.

Unlike the read-only protocol, this module can change device state.  It is
kept out of the normal CLI and requires a backup-bound
``WriteAuthorization`` before issuing the first control transfer.  The
sender implements only the ordinary segmented transaction recovered from the
legacy manager; it does not implement the separate unlock/``0x101d`` path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time
from typing import Callable, Optional, Protocol

from .protocol import (
    CONTROL_IN_VENDOR_DEVICE,
    CONTROL_OUT_VENDOR_DEVICE,
    MAX_BULK_CHUNK,
    STATUS_BUSY,
    STATUS_READY,
    DeviceStatusError,
    ProtocolError,
    TransferCancelledError,
    TransferTimeoutError,
)
from .write_artifact import ProspectiveWriteTransaction
from .write_gate import PostWriteVerification, verify_post_write_backup


REQUEST_BEGIN_TRANSMIT = 0x02
REQUEST_TRANSFER_STATE = 0x03
REQUEST_COMPLETION = 0x04


# Progress is deliberately transport-level and unit-based rather than a GUI
# concern.  ``completed`` counts payload bytes that the backend has confirmed
# written; ``total`` is the bounded transaction payload length.
ProgressCallback = Callable[[str, int, int], None]


class WriteProtocolError(ProtocolError):
    """Raised when a live host-to-device transaction cannot complete."""


class WriteTransferLengthError(WriteProtocolError):
    """Raised when a control or bulk-OUT transfer reports an invalid length."""


@dataclass(frozen=True)
class WriteFailureAssessment:
    """Safety classification attached to one failed write attempt.

    ``indeterminate`` deliberately means only that the device outcome cannot
    be inferred from the host-side failure.  It is not a claim that the
    device rolled back or committed atomically.
    """

    primary_error: str
    write_started: bool
    device_outcome: str
    automatic_retry_allowed: bool = False
    read_only_assessment_allowed: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "primary_error": self.primary_error,
            "write_started": self.write_started,
            "device_outcome": self.device_outcome,
            "automatic_retry_allowed": self.automatic_retry_allowed,
            "read_only_assessment_allowed": self.read_only_assessment_allowed,
        }


def assess_write_failure(error: BaseException) -> WriteFailureAssessment:
    """Return the sender's R15 classification, or a safe pre-start default."""

    assessment = getattr(error, "write_failure_assessment", None)
    if isinstance(assessment, WriteFailureAssessment):
        return assessment
    return WriteFailureAssessment(
        primary_error=str(error),
        write_started=False,
        device_outcome="not_started",
    )


def _annotate_write_failure(
    error: BaseException,
    *,
    write_started: bool,
    device_outcome: str,
) -> None:
    """Attach a non-invasive assessment while preserving the primary error."""

    assessment = WriteFailureAssessment(
        primary_error=str(error),
        write_started=write_started,
        device_outcome=device_outcome,
    )
    try:
        setattr(error, "write_failure_assessment", assessment)
    except Exception:
        # Exception subclasses supplied by an injected backend may use slots.
        # The original exception remains the primary result in that case.
        pass


class WriteBackend(Protocol):
    """USB operations required by the explicitly authorized write sender."""

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

    def bulk_write(self, endpoint: int, data: bytes, timeout_ms: int) -> int:
        ...


@dataclass(frozen=True)
class WritePolicy:
    """Finite transport limits for one ordinary write transaction."""

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


def _u16le_exact(data: bytes, stage: str) -> int:
    if len(data) != 2:
        raise WriteTransferLengthError(
            f"{stage} control transfer returned {len(data)} bytes; expected exactly 2"
        )
    return int.from_bytes(data, "little")


class AuthorizedWriteSender:
    """Send one authorized ordinary ``0x101b`` transaction.

    The caller must provide a candidate transaction and an authorization
    returned by :func:`infocarry.write_gate.authorize_write_session`.  The
    authorization is revalidated before request 2, tying the bytes about to be
    sent to the unchanged fresh backup.  This class is not imported by the
    normal read-only CLI.
    """

    def __init__(
        self,
        backend: WriteBackend,
        bulk_out_endpoint: int,
        *,
        policy: WritePolicy = WritePolicy(),
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 0x01 <= bulk_out_endpoint <= 0x0F:
            raise ValueError(f"0x{bulk_out_endpoint:02x} is not a USB OUT endpoint")
        self._backend = backend
        self._bulk_out_endpoint = bulk_out_endpoint
        self._policy = policy
        self._clock = clock
        self._sleep = sleep

    def send(
        self,
        transaction: ProspectiveWriteTransaction,
        authorization: object,
        *,
        cancelled: Optional[Callable[[], bool]] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> int:
        """Transmit one candidate and return the successful completion word.

        ``authorization`` is intentionally checked by capability rather than
        imported as a concrete class, keeping this transport testable without
        importing filesystem code.  Production callers must pass a
        ``WriteAuthorization``; its ``revalidate`` method is invoked before
        any USB access.
        """

        if not isinstance(transaction, ProspectiveWriteTransaction):
            raise WriteProtocolError("transaction must be a ProspectiveWriteTransaction")
        revalidate = getattr(authorization, "revalidate", None)
        if not callable(revalidate):
            raise WriteProtocolError("a WriteAuthorization with revalidate() is required")
        try:
            revalidate(transaction)
        except Exception as exc:
            if isinstance(exc, ProtocolError):
                raise
            raise WriteProtocolError(f"write authorization failed: {exc}") from exc

        total = transaction.payload_length
        _notify_progress(progress, "Write authorized", 0, total)
        header = transaction.command_header
        # This check is intentionally before request 0x02.  Cancellation here
        # is ordinary and safe; after the header is accepted, interruption is
        # an indeterminate device outcome.
        self._raise_if_cancelled(cancelled)
        try:
            written = self._backend.control_out(
                CONTROL_OUT_VENDOR_DEVICE,
                REQUEST_BEGIN_TRANSMIT,
                0,
                0,
                header,
                self._policy.control_timeout_ms,
            )
        except Exception as exc:
            _annotate_write_failure(
                exc, write_started=False, device_outcome="not_started"
            )
            raise
        if written != len(header):
            error = WriteTransferLengthError(
                f"command header transfer wrote {written} bytes; expected {len(header)}"
            )
            _annotate_write_failure(
                error, write_started=False, device_outcome="not_started"
            )
            raise error
        _notify_progress(progress, "Header sent", 0, total)

        try:
            completed = 0
            for data in transaction.ranges:
                if not data:
                    continue
                completed = self._send_range(
                    data,
                    cancelled=cancelled,
                    completed=completed,
                    total=total,
                    progress=progress,
                )
            completion = self._read_completion(require_success=True)
            _notify_progress(progress, "Write complete", total, total)
            return completion
        except Exception as exc:
            # The legacy worker makes a best-effort request-4 query after a
            # failure once request 2 has started. Preserve the primary error.
            try:
                self._read_completion(require_success=False)
            except Exception:
                pass
            device_outcome = (
                "completed_with_error"
                if isinstance(exc, DeviceStatusError)
                and exc.stage == "write completion"
                else "indeterminate"
            )
            _annotate_write_failure(
                exc, write_started=True, device_outcome=device_outcome
            )
            if isinstance(exc, ProtocolError):
                raise
            wrapped = WriteProtocolError(str(exc))
            assessment = getattr(exc, "write_failure_assessment", None)
            if isinstance(assessment, WriteFailureAssessment):
                try:
                    setattr(wrapped, "write_failure_assessment", assessment)
                except Exception:
                    pass
            raise wrapped from exc

    def send_and_verify(
        self,
        transaction: ProspectiveWriteTransaction,
        authorization: object,
        post_write_backup: Path,
        *,
        cancelled: Optional[Callable[[], bool]] = None,
        progress: Optional[ProgressCallback] = None,
        now: Optional[datetime] = None,
        max_age_seconds: Optional[float] = None,
    ) -> PostWriteVerification:
        """Send once, then verify a caller-provided fresh read-back archive.

        The backup must be captured by the caller after ``send`` returns. This
        method deliberately does not perform a second USB operation itself;
        it makes the required post-write comparison unavoidable for callers
        that want a verified result.
        """

        self.send(
            transaction,
            authorization,
            cancelled=cancelled,
            progress=progress,
        )
        kwargs = {}
        if now is not None:
            kwargs["now"] = now
        if max_age_seconds is not None:
            kwargs["max_age_seconds"] = max_age_seconds
        try:
            before = authorization.backup
        except AttributeError as exc:
            raise WriteProtocolError(
                "send_and_verify requires a backup-bound authorization"
            ) from exc
        try:
            return verify_post_write_backup(
                before, post_write_backup, transaction, **kwargs
            )
        except Exception as exc:
            # A failed read-back is a terminal safety result.  Never retry the
            # device write after bytes have been sent; the caller must inspect
            # the preserved post-write archive and resolve the discrepancy.
            if isinstance(exc, WriteProtocolError):
                raise
            raise WriteProtocolError(
                f"post-write read-back verification failed; no retry attempted: {exc}"
            ) from exc

    def _send_range(
        self,
        data: bytes,
        *,
        cancelled: Optional[Callable[[], bool]],
        completed: int,
        total: int,
        progress: Optional[ProgressCallback],
    ) -> int:
        offset = 0
        while offset < len(data):
            self._raise_if_cancelled(cancelled)
            self._wait_until_ready(cancelled)
            chunk = data[offset : offset + self._policy.max_bulk_chunk]
            written = self._backend.bulk_write(
                self._bulk_out_endpoint, chunk, self._policy.bulk_timeout_ms
            )
            if not isinstance(written, int) or written <= 0 or written > len(chunk):
                raise WriteTransferLengthError(
                    f"bulk-OUT transfer reported {written!r} bytes for a {len(chunk)}-byte chunk"
                )
            offset += written
            completed += written
            _notify_progress(progress, "Sending payload", completed, total)
        return completed

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
                raise DeviceStatusError("write transfer-state", state)
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
            raise DeviceStatusError("write completion", completion)
        return completion

    @staticmethod
    def _raise_if_cancelled(cancelled: Optional[Callable[[], bool]]) -> None:
        if cancelled is not None and cancelled():
            raise TransferCancelledError("write operation was cancelled")


def _notify_progress(
    progress: Optional[ProgressCallback], label: str, completed: int, total: int
) -> None:
    """Emit bounded progress only for internally confirmed byte counts."""

    if progress is None:
        return
    if not 0 <= completed <= total:
        raise WriteProtocolError(
            f"write progress {completed} is outside the bounded range 0..{total}"
        )
    progress(label, completed, total)


__all__ = [
    "AuthorizedWriteSender",
    "REQUEST_BEGIN_TRANSMIT",
    "REQUEST_COMPLETION",
    "REQUEST_TRANSFER_STATE",
    "WriteBackend",
    "ProgressCallback",
    "WritePolicy",
    "WriteFailureAssessment",
    "WriteProtocolError",
    "WriteTransferLengthError",
    "assess_write_failure",
]
