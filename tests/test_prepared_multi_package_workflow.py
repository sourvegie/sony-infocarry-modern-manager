from datetime import datetime, timezone
from pathlib import Path
import unittest

from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.device_info import RawInfoResponse
from infocarry.prepared_multi_package_workflow import (
    GuardedPreparedMultiPackageWorkflow,
    PreparedMultiFakeTransport,
    PreparedMultiPackageWorkflowError,
)
from infocarry.prepared_multi_package_gate import PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE

try:
    import test_prepared_package_multi_candidate as _fixture
    from test_new_txt import _write_archive
except ModuleNotFoundError:
    import tests.test_prepared_package_multi_candidate as _fixture
    from tests.test_new_txt import _write_archive


class PreparedMultiPackageWorkflowTests(unittest.TestCase):
    now = datetime(2026, 8, 27, tzinfo=timezone.utc)

    def _setup(self, sender=None, *, after_blob=None, capture_error=False, mixed=True):
        temporary, package, _backup, candidate, template = _fixture.PreparedMultiCandidateTests()._case(mixed=mixed)
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        baseline_blob = candidate.baseline.data
        zero_state = {command: b"\x00" * 64 for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
        captures = []

        def capture(destination, **_kwargs):
            captures.append(destination)
            if capture_error and len(captures) == 2:
                raise OSError("simulated post-operation backup failure")
            blob = baseline_blob if len(captures) == 1 else (candidate.candidate_blob if after_blob is None else after_blob)
            _write_archive(destination, blob, self.now, fixed_state=zero_state)

        if sender is None:
            sender = lambda _transaction, _authorization, **_kwargs: 0
        transport = PreparedMultiFakeTransport(sender)
        response = candidate.native_capacity_evidence
        workflow = GuardedPreparedMultiPackageWorkflow(
            capture,
            transport,
            template,
            detect_device=lambda: (0x054C, 0x001E),
            query_capacity=lambda: response,
        )
        return {
            "root": root,
            "package": package,
            "candidate": candidate,
            "workflow": workflow,
            "transport": transport,
            "captures": captures,
        }

    def _run(self, setup, **overrides):
        args = {
            "backup_destination": setup["root"] / "before",
            "post_operation_destination": setup["root"] / "after",
            "package": setup["package"],
            "preview": setup["candidate"],
            "new_record_timestamp_be32": 0x6A8ABA6F,
            "confirmation": PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE,
            "fake_transport": True,
            "now": self.now,
            "max_age_seconds": None,
        }
        args.update(overrides)
        return setup["workflow"].run(**args)

    def test_success_uses_one_fake_transaction_and_independent_readback(self):
        setup = self._setup()
        result = self._run(setup)
        self.assertEqual(setup["transport"].calls, 1)
        self.assertTrue(result.verification.success)
        self.assertEqual(
            result.audit["workflow"]["operation_sequence"],
            [
                "fake_transport_asserted",
                "device_detected",
                "capacity_queried_0x0019",
                "fresh_complete_backup",
                "candidate_reconstructed",
                "authorization",
                "single_0x101b_transaction",
                "completion_0x0000",
                "fresh_post_operation_backup",
                "independent_readback_verification",
            ],
        )

    def test_txt_only_success_does_not_require_a_bmp_template(self):
        setup = self._setup(mixed=False)
        result = self._run(setup)
        self.assertTrue(result.verification.success)
        self.assertEqual(setup["transport"].calls, 1)

    def test_unmarked_sender_and_missing_fake_assertion_are_blocked(self):
        temporary, _package, _backup, candidate, template = _fixture.PreparedMultiCandidateTests()._case(mixed=True)
        self.addCleanup(temporary.cleanup)
        with self.assertRaises(TypeError):
            GuardedPreparedMultiPackageWorkflow(
                lambda _destination, **_kwargs: None,
                object(),
                template,
                detect_device=lambda: (0x054C, 0x001E),
                query_capacity=lambda: candidate.native_capacity_evidence,
            )
        setup = self._setup()
        with self.assertRaisesRegex(PreparedMultiPackageWorkflowError, "fake_transport=True"):
            self._run(setup, fake_transport=False)
        self.assertEqual(setup["transport"].calls, 0)

    def test_capacity_response_change_and_wrong_device_stop_before_send(self):
        setup = self._setup()
        original = setup["candidate"].native_capacity_evidence
        changed_raw = bytearray(original.raw_response)
        changed_raw[0x10] ^= 1
        changed = NativeCapacityResponse.from_hardware_response(
            RawInfoResponse(0x0019, "changed", bytes(changed_raw)),
            device_identity=(0x054C, 0x001E),
        )
        setup["workflow"] = GuardedPreparedMultiPackageWorkflow(
            setup["workflow"]._capture,
            setup["transport"],
            setup["workflow"]._template,
            detect_device=lambda: (0x054C, 0x001E),
            query_capacity=lambda: changed,
        )
        with self.assertRaisesRegex(PreparedMultiPackageWorkflowError, "candidate preflight"):
            self._run(setup)
        self.assertEqual(setup["transport"].calls, 0)

        wrong = self._setup()
        wrong["workflow"] = GuardedPreparedMultiPackageWorkflow(
            wrong["workflow"]._capture,
            wrong["transport"],
            wrong["workflow"]._template,
            detect_device=lambda: (0x1234, 0x001E),
            query_capacity=lambda: wrong["candidate"].native_capacity_evidence,
        )
        with self.assertRaises(PreparedMultiPackageWorkflowError):
            self._run(wrong)
        self.assertEqual(wrong["transport"].calls, 0)

    def test_timeout_before_transaction_is_safe_and_after_start_is_indeterminate(self):
        setup = self._setup()
        clock_value = [0.0]

        def clock():
            return clock_value[0]

        def query():
            clock_value[0] = 100.0
            return setup["candidate"].native_capacity_evidence

        setup["workflow"] = GuardedPreparedMultiPackageWorkflow(
            setup["workflow"]._capture,
            setup["transport"],
            setup["workflow"]._template,
            detect_device=lambda: (0x054C, 0x001E),
            query_capacity=query,
        )
        with self.assertRaisesRegex(PreparedMultiPackageWorkflowError, "deadline") as raised:
            self._run(setup, timeout_seconds=10, clock=clock)
        self.assertEqual(raised.exception.state, "timeout_before_transaction")
        self.assertFalse(raised.exception.write_started)
        self.assertEqual(setup["transport"].calls, 0)

        after = self._setup()
        after_clock = [0.0]

        def after_sender(_transaction, _authorization, **_kwargs):
            after_clock[0] = 100.0
            return 0

        after["transport"] = PreparedMultiFakeTransport(after_sender)
        after["workflow"] = GuardedPreparedMultiPackageWorkflow(
            after["workflow"]._capture,
            after["transport"],
            after["workflow"]._template,
            detect_device=lambda: (0x054C, 0x001E),
            query_capacity=lambda: after["candidate"].native_capacity_evidence,
        )
        with self.assertRaisesRegex(PreparedMultiPackageWorkflowError, "deadline") as raised:
            self._run(after, timeout_seconds=10, clock=lambda: after_clock[0])
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertTrue(raised.exception.write_started)
        self.assertEqual(after["transport"].calls, 1)

    def test_cancellation_boundaries_are_distinct(self):
        setup = self._setup()
        checks = [0]

        def cancelled_before_send():
            checks[0] += 1
            return checks[0] >= 4

        with self.assertRaisesRegex(PreparedMultiPackageWorkflowError, "cancelled") as raised:
            self._run(setup, cancelled=cancelled_before_send)
        self.assertEqual(raised.exception.state, "cancelled_before_transaction")
        self.assertFalse(raised.exception.write_started)
        self.assertEqual(setup["transport"].calls, 0)

        after = self._setup()

        def cancelling_sender(_transaction, _authorization, *, cancelled, **_kwargs):
            self.assertIsNotNone(cancelled)
            raise RuntimeError("simulated cancellation after transaction entry")

        after["transport"] = PreparedMultiFakeTransport(cancelling_sender)
        after["workflow"] = GuardedPreparedMultiPackageWorkflow(
            after["workflow"]._capture,
            after["transport"],
            after["workflow"]._template,
            detect_device=lambda: (0x054C, 0x001E),
            query_capacity=lambda: after["candidate"].native_capacity_evidence,
        )
        with self.assertRaises(PreparedMultiPackageWorkflowError) as raised:
            self._run(after)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertTrue(raised.exception.write_started)
        self.assertEqual(after["transport"].calls, 1)

    def test_completion_and_readback_failures_are_terminal_without_retry(self):
        for completion in (1, None, b"\x00"):
            setup = self._setup(sender=lambda *_args, completion=completion, **_kwargs: completion)
            with self.subTest(completion=completion):
                with self.assertRaises(PreparedMultiPackageWorkflowError) as raised:
                    self._run(setup)
                self.assertEqual(raised.exception.stage, "write_completion")
                self.assertEqual(setup["transport"].calls, 1)

        mismatch = bytearray(self._setup()["candidate"].candidate_blob)
        mismatch[-1] ^= 1
        setup = self._setup(after_blob=bytes(mismatch))
        with self.assertRaises(PreparedMultiPackageWorkflowError) as raised:
            self._run(setup)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertEqual(setup["transport"].calls, 1)

        failed_backup = self._setup(capture_error=True)
        with self.assertRaises(PreparedMultiPackageWorkflowError):
            self._run(failed_backup)
        self.assertEqual(failed_backup["transport"].calls, 1)


if __name__ == "__main__":
    unittest.main()
