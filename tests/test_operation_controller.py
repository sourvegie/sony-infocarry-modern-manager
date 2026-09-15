import queue
import threading
import time
import unittest

from infocarry.operation_controller import (
    OperationBusyError,
    OperationController,
    OperationStatus,
)


class OperationControllerTests(unittest.TestCase):
    def setUp(self):
        self.callbacks = queue.Queue()
        self.controller = OperationController(self.callbacks.put)
        self.outcomes = []
        self.progress = []
        self.main_thread = threading.get_ident()

    def tearDown(self):
        self.controller.close()

    def drain(self):
        while True:
            try:
                self.callbacks.get_nowait()()
            except queue.Empty:
                return

    @staticmethod
    def wait_for(event):
        if not event.wait(2):
            raise AssertionError("worker did not reach its barrier")

    def test_blocking_work_runs_off_ui_thread_and_completion_is_marshaled(self):
        started = threading.Event()
        release = threading.Event()
        worker_thread = []

        def work(cancelled, progress):
            worker_thread.append(threading.get_ident())
            started.set()
            release.wait(2)
            return "prepared"

        self.controller.start(
            "prepare",
            work,
            on_complete=self.outcomes.append,
            on_progress=self.progress.append,
        )
        self.wait_for(started)
        self.assertNotEqual(worker_thread[0], self.main_thread)
        self.assertEqual(self.outcomes, [])
        release.set()
        for _ in range(20):
            if not self.callbacks.empty():
                break
            time.sleep(0.01)
        self.drain()
        self.assertEqual(len(self.outcomes), 1)
        self.assertTrue(self.outcomes[0].succeeded)
        self.assertEqual(self.outcomes[0].value, "prepared")

    def test_progress_is_marshaled_and_current_only(self):
        started = threading.Event()
        release = threading.Event()

        def work(cancelled, progress):
            progress("working", 1, 2)
            started.set()
            release.wait(2)
            return None

        self.controller.start(
            "review",
            work,
            on_complete=self.outcomes.append,
            on_progress=self.progress.append,
        )
        self.wait_for(started)
        self.assertEqual(self.progress, [])
        self.drain()
        self.assertEqual(self.progress[0].label, "working")
        release.set()
        time.sleep(0.02)
        self.drain()

    def test_conflicting_second_operation_is_rejected(self):
        started = threading.Event()
        release = threading.Event()

        def work(cancelled, progress):
            started.set()
            release.wait(2)

        self.controller.start("first", work, on_complete=self.outcomes.append)
        self.wait_for(started)
        with self.assertRaises(OperationBusyError):
            self.controller.start("second", work, on_complete=self.outcomes.append)
        release.set()
        time.sleep(0.02)
        self.drain()
        self.assertEqual(len(self.outcomes), 1)

    def test_invalidated_late_result_is_discarded(self):
        started = threading.Event()
        release = threading.Event()

        def work(cancelled, progress):
            started.set()
            release.wait(2)
            return "stale"

        self.controller.start("old", work, on_complete=self.outcomes.append)
        self.wait_for(started)
        self.assertTrue(self.controller.invalidate())
        self.assertFalse(self.controller.busy)
        release.set()
        time.sleep(0.02)
        self.drain()
        self.assertEqual(self.outcomes, [])

    def test_newer_operation_wins_after_input_revision_change(self):
        old_started = threading.Event()
        old_release = threading.Event()
        new_started = threading.Event()
        new_release = threading.Event()

        def old_work(cancelled, progress):
            old_started.set()
            old_release.wait(2)
            return "old"

        def new_work(cancelled, progress):
            new_started.set()
            new_release.wait(2)
            return "new"

        self.controller.start("old", old_work, on_complete=self.outcomes.append)
        self.wait_for(old_started)
        self.controller.invalidate()
        self.controller.start("new", new_work, on_complete=self.outcomes.append)
        self.wait_for(new_started)
        new_release.set()
        time.sleep(0.02)
        self.drain()
        old_release.set()
        time.sleep(0.02)
        self.drain()
        self.assertEqual([outcome.value for outcome in self.outcomes], ["new"])

    def test_safe_host_cancellation_returns_cancelled_outcome(self):
        started = threading.Event()
        release = threading.Event()

        def work(cancelled, progress):
            started.set()
            release.wait(2)
            return "ignored after cancellation"

        self.controller.start("host-read", work, on_complete=self.outcomes.append)
        self.wait_for(started)
        self.assertTrue(self.controller.cancel())
        release.set()
        time.sleep(0.02)
        self.drain()
        self.assertEqual(self.outcomes[0].status, OperationStatus.CANCELLED)

    def test_worker_exception_is_typed_failed_outcome(self):
        def work(cancelled, progress):
            raise ValueError("bad prepared input")

        self.controller.start("prepare", work, on_complete=self.outcomes.append)
        time.sleep(0.02)
        self.drain()
        self.assertEqual(len(self.outcomes), 1)
        self.assertEqual(self.outcomes[0].status, OperationStatus.FAILED)
        self.assertIsInstance(self.outcomes[0].error, ValueError)

    def test_thread_start_failure_is_typed_and_clears_busy(self):
        pending = []
        outcomes = []

        class FailingThread:
            def __init__(self, **_kwargs):
                raise RuntimeError("thread creation failed")

        controller = OperationController(
            pending.append,
            thread_factory=FailingThread,
        )
        controller.start(
            "thread-start-failure",
            lambda _cancelled, _progress: "unreachable",
            on_complete=outcomes.append,
        )
        self.assertTrue(controller.busy)
        self.assertEqual(len(pending), 1)
        pending.pop()()
        self.assertFalse(controller.busy)
        self.assertEqual(outcomes[0].status, OperationStatus.FAILED)
        self.assertIsInstance(outcomes[0].error, RuntimeError)

    def test_close_discards_queued_callbacks_for_destroyed_ui(self):
        started = threading.Event()
        release = threading.Event()

        def work(cancelled, progress):
            started.set()
            release.wait(2)
            return "late"

        self.controller.start("prepare", work, on_complete=self.outcomes.append)
        self.wait_for(started)
        self.controller.close()
        release.set()
        time.sleep(0.02)
        self.drain()
        self.assertEqual(self.outcomes, [])
        self.assertTrue(self.controller.closed)


if __name__ == "__main__":
    unittest.main()
