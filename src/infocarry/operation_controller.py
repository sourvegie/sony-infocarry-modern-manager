"""Small thread-to-main-thread controller for long-running application work.

The controller is deliberately UI-toolkit neutral.  A caller supplies the
main-thread handoff (``root.after`` for ttk, or a deterministic test queue),
while the worker performs blocking host/read-only work away from that thread.

Every operation owns a monotonically increasing generation.  Invalidating or
superseding an operation makes all late completions inert, even when the
underlying worker cannot stop immediately.  ``close`` also prevents a queued
callback from touching a destroyed window.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import threading
from typing import Callable, Generic, Optional, TypeVar


T = TypeVar("T")


class OperationControllerError(RuntimeError):
    """Base class for controlled application-operation failures."""


class OperationBusyError(OperationControllerError):
    """Raised when a conflicting foreground operation is already active."""


class OperationClosedError(OperationControllerError):
    """Raised when work is requested after the owning UI has closed."""


class OperationStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DISCARDED = "discarded"


@dataclass(frozen=True)
class OperationToken:
    """Identity of one foreground operation generation."""

    generation: int
    name: str


@dataclass(frozen=True)
class OperationProgress:
    """A progress update safe to marshal to the main thread."""

    token: OperationToken
    label: str
    completed: Optional[int] = None
    total: Optional[int] = None


@dataclass(frozen=True)
class OperationOutcome(Generic[T]):
    """Typed terminal outcome delivered on the main thread."""

    token: OperationToken
    status: OperationStatus
    value: Optional[T] = None
    error: Optional[BaseException] = None

    @property
    def succeeded(self) -> bool:
        return self.status is OperationStatus.SUCCEEDED

    @property
    def failed(self) -> bool:
        return self.status is OperationStatus.FAILED

    @property
    def cancelled(self) -> bool:
        return self.status is OperationStatus.CANCELLED


Work = Callable[[threading.Event, Callable[[str, Optional[int], Optional[int]], None]], T]
PostToMain = Callable[[Callable[[], None]], object]
OutcomeCallback = Callable[[OperationOutcome[T]], None]
ProgressCallback = Callable[[OperationProgress], None]


class OperationController(Generic[T]):
    """Run one conflicting foreground operation with stale-result protection.

    ``start`` must be called from the owning UI/main thread.  ``work`` runs on
    a daemon worker thread and receives a cooperative cancellation event.  The
    controller never force-stops a worker and never interprets cancellation as
    evidence about a device-changing operation.
    """

    def __init__(
        self,
        post_to_main: PostToMain,
        *,
        thread_factory: Callable[..., threading.Thread] = threading.Thread,
    ) -> None:
        if not callable(post_to_main):
            raise TypeError("post_to_main must be callable")
        self._post_to_main = post_to_main
        self._thread_factory = thread_factory
        self._lock = threading.RLock()
        self._generation = 0
        self._active: Optional[OperationToken] = None
        self._cancel_event: Optional[threading.Event] = None
        self._closed = False
        self._discarded_generations: set[int] = set()

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._active is not None

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    @property
    def active_token(self) -> Optional[OperationToken]:
        with self._lock:
            return self._active

    def start(
        self,
        name: str,
        work: Work[T],
        *,
        on_complete: OutcomeCallback[T],
        on_progress: Optional[ProgressCallback] = None,
        replace_invalidated: bool = False,
    ) -> OperationToken:
        """Start work and marshal all callbacks through ``post_to_main``.

        A live operation cannot be replaced accidentally.  The caller must
        first call ``invalidate`` when its input/state changed, then pass
        ``replace_invalidated=True`` to start the new generation.  This keeps
        normal UI actions serialized while allowing a cancelled cooperative
        worker to wind down harmlessly.
        """

        if not isinstance(name, str) or not name.strip():
            raise ValueError("operation name is required")
        if not callable(work) or not callable(on_complete):
            raise TypeError("work and on_complete must be callable")
        with self._lock:
            if self._closed:
                raise OperationClosedError("operation controller is closed")
            if self._active is not None:
                if not replace_invalidated or self._active.generation not in self._discarded_generations:
                    raise OperationBusyError("a conflicting foreground operation is already active")
                self._cancel_event_for_active_locked()
            self._generation += 1
            token = OperationToken(self._generation, name.strip())
            cancel_event = threading.Event()
            self._active = token
            self._cancel_event = cancel_event

        def report_progress(label: str, completed: Optional[int] = None, total: Optional[int] = None) -> None:
            if not isinstance(label, str):
                label = str(label)
            update = OperationProgress(token, label, completed, total)
            self._schedule_to_main(
                lambda: self._deliver_progress(token, update, on_progress)
            )

        def run() -> None:
            try:
                value = work(cancel_event, report_progress)
            except BaseException as exc:
                outcome = OperationOutcome(
                    token=token,
                    status=(
                        OperationStatus.CANCELLED
                        if cancel_event.is_set()
                        else OperationStatus.FAILED
                    ),
                    error=exc,
                )
            else:
                outcome = OperationOutcome(
                    token=token,
                    status=(
                        OperationStatus.CANCELLED
                        if cancel_event.is_set()
                        else OperationStatus.SUCCEEDED
                    ),
                    value=value,
                )
            self._schedule_to_main(lambda: self._deliver_outcome(outcome, on_complete))

        try:
            thread = self._thread_factory(
                target=run,
                name=f"infocarry-operation-{token.name}",
                daemon=True,
            )
            thread.start()
        except BaseException as exc:
            # Thread construction/start is normally infallible, but a resource
            # failure must still become a typed terminal outcome. Otherwise
            # the owning UI would remain busy forever with no callback to clear
            # its controls.
            outcome = OperationOutcome(
                token=token,
                status=OperationStatus.FAILED,
                error=exc,
            )
            try:
                self._post_to_main(
                    lambda: self._deliver_outcome(outcome, on_complete)
                )
            except BaseException:
                with self._lock:
                    if self._active == token:
                        self._active = None
                        self._cancel_event = None
                        self._discarded_generations.discard(token.generation)
                    closed = self._closed
                if not closed:
                    on_complete(outcome)
        return token

    def _schedule_to_main(self, callback: Callable[[], None]) -> bool:
        """Schedule a callback, quietly dropping it after owner teardown."""

        try:
            self._post_to_main(callback)
        except BaseException:
            with self._lock:
                if self._closed or self._active is None:
                    return False
            raise
        return True

    def _deliver_progress(
        self,
        token: OperationToken,
        update: OperationProgress,
        callback: Optional[ProgressCallback],
    ) -> None:
        if callback is None:
            return
        with self._lock:
            if self._closed or self._active != token:
                return
        callback(update)

    def _deliver_outcome(
        self,
        outcome: OperationOutcome[T],
        callback: OutcomeCallback[T],
    ) -> None:
        with self._lock:
            if self._closed or self._active != outcome.token:
                return
            self._active = None
            self._cancel_event = None
            self._discarded_generations.discard(outcome.token.generation)
        callback(outcome)

    def _cancel_event_for_active_locked(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()

    def cancel(self) -> bool:
        """Request cooperative cancellation of the current host operation."""

        with self._lock:
            if self._closed or self._active is None:
                return False
            self._cancel_event_for_active_locked()
            return True

    def invalidate(self, *, cancel: bool = True) -> bool:
        """Invalidate the current result because its inputs/state changed."""

        with self._lock:
            if self._active is None:
                return False
            self._discarded_generations.add(self._active.generation)
            if cancel:
                self._cancel_event_for_active_locked()
            self._active = None
            self._cancel_event = None
            return True

    def close(self) -> None:
        """Prevent all future and queued callbacks from touching the UI."""

        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._generation += 1
            self._cancel_event_for_active_locked()
            if self._active is not None:
                self._discarded_generations.add(self._active.generation)
            self._active = None
            self._cancel_event = None


__all__ = [
    "OperationBusyError",
    "OperationClosedError",
    "OperationController",
    "OperationControllerError",
    "OperationOutcome",
    "OperationProgress",
    "OperationStatus",
    "OperationToken",
]
