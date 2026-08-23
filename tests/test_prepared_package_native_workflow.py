from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import unittest

from infocarry.capacity_evidence import (
    NativeCapacityEvidenceError,
    NativeCapacityResponse,
)
from infocarry.device_info import RawInfoResponse
from infocarry.prepared_package_candidate import build_prepared_package_candidate
from infocarry.prepared_package_workflow import (
    GuardedPreparedPackageWorkflow,
    PreparedPackageOfflinePreview,
    PreparedPackageWorkflowError,
)
from infocarry.protocol import TransferTimeoutError
from infocarry.write_protocol import (
    REQUEST_COMPLETION,
    AuthorizedWriteSender,
    WritePolicy,
)

try:
    from test_prepared_package_workflow import (
        PackageWorkflowBackend,
    )
    import test_prepared_package_workflow as _package_workflow_fixture
except ModuleNotFoundError:
    from tests.test_prepared_package_workflow import (
        PackageWorkflowBackend,
    )
    import tests.test_prepared_package_workflow as _package_workflow_fixture


class FailingBeforeTransactionBackend(PackageWorkflowBackend):
    def control_out(self, request_type, request, value, index, data, timeout_ms):
        self.calls.append(("control_out", request, bytes(data)))
        raise OSError("simulated disconnect before 0x101b begins")


class MalformedCompletionBackend(PackageWorkflowBackend):
    def control_in(self, request_type, request, value, index, length, timeout_ms):
        if request == REQUEST_COMPLETION:
            self.calls.append(("control_in", request))
            return b"\x00"
        return super().control_in(request_type, request, value, index, length, timeout_ms)


class PreparedPackageNativeWorkflowTests(unittest.TestCase):
    @staticmethod
    def _response() -> NativeCapacityResponse:
        fixture = json.loads(
            (Path(__file__).parent / "fixtures" / "infocarry_info_responses.json").read_text(
                encoding="utf-8"
            )
        )
        return NativeCapacityResponse.from_hardware_response(
            RawInfoResponse(
                0x0019,
                "hardware",
                bytes.fromhex(fixture["hardware"]["response_hex"]),
            ),
            device_identity=(0x054C, 0x001E),
        )

    def _native_setup(self, *, backend=None, after_mode="normal"):
        base = _package_workflow_fixture.PreparedPackageWorkflowTests()
        setup = base._setup(backend=backend, after_mode=after_mode)
        response_box = [self._response()]
        sequence = []
        old_workflow = setup["workflow"]
        candidate = build_prepared_package_candidate(
            setup["package"],
            setup["preview"].candidate.backup,
            old_workflow._template,
            new_record_timestamp_be32=0x6A8ABA6F,
            native_capacity_response=response_box[0],
        )

        def detect_device():
            sequence.append("detect")
            return (0x054C, 0x001E)

        def query_capacity():
            sequence.append("query")
            return response_box[0]

        setup["preview"] = PreparedPackageOfflinePreview(candidate)
        setup["workflow"] = GuardedPreparedPackageWorkflow(
            old_workflow._capture,
            old_workflow._send,
            old_workflow._template,
            detect_device=detect_device,
            query_capacity=query_capacity,
        )
        setup["response_box"] = response_box
        setup["sequence"] = sequence
        return setup

    def _run(self, setup, **overrides):
        arguments = {
            "backup_destination": setup["root"] / "before",
            "post_operation_destination": setup["root"] / "after",
            "package": setup["package"],
            "preview": setup["preview"],
            "new_record_timestamp_be32": 0x6A8ABA6F,
            "confirmation": "ADD ONE INFOCARRY TEXT PACKAGE",
            "fake_transport": True,
            "require_native_capacity_evidence": True,
            "now": setup["now"],
            "max_age_seconds": None,
        }
        arguments.update(overrides)
        return setup["workflow"].run(**arguments)

    def test_native_workflow_order_and_single_transaction(self):
        setup = self._native_setup()
        self.addCleanup(setup["temporary"].cleanup)
        result = self._run(setup)
        self.assertEqual(result.completion, 0)
        self.assertEqual(setup["sequence"], ["detect", "query"])
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
                "fresh_post_operation_backup",
                "independent_readback_verification",
            ],
        )
        self.assertTrue(result.authorization.live_eligible)
        self.assertEqual(len(setup["send_calls"]), 1)

    def test_capacity_response_change_invalidates_displayed_candidate_before_sender(self):
        setup = self._native_setup()
        self.addCleanup(setup["temporary"].cleanup)
        raw = bytearray(setup["response_box"][0].raw_response)
        raw[0x08:0x0C] = (3_145_729).to_bytes(4, "big")
        setup["response_box"][0] = NativeCapacityResponse.from_hardware_response(
            RawInfoResponse(0x0019, "hardware", bytes(raw)),
            device_identity=(0x054C, 0x001E),
        )
        with self.assertRaisesRegex(PreparedPackageWorkflowError, "no longer matches") as raised:
            self._run(setup)
        self.assertEqual(raised.exception.stage, "preview_revalidation")
        self.assertEqual(setup["send_calls"], [])

    def test_wrong_device_and_malformed_capacity_stop_before_backup(self):
        setup = self._native_setup()
        self.addCleanup(setup["temporary"].cleanup)
        old = setup["workflow"]
        setup["workflow"] = GuardedPreparedPackageWorkflow(
            old._capture,
            old._send,
            old._template,
            detect_device=lambda: (0x054C, 0x001F),
            query_capacity=lambda: setup["response_box"][0],
        )
        with self.assertRaisesRegex(PreparedPackageWorkflowError, "identity"):
            self._run(setup)
        self.assertFalse((setup["root"] / "before").exists())

        setup = self._native_setup()
        self.addCleanup(setup["temporary"].cleanup)
        old = setup["workflow"]
        setup["workflow"] = GuardedPreparedPackageWorkflow(
            old._capture,
            old._send,
            old._template,
            detect_device=lambda: (0x054C, 0x001E),
            query_capacity=lambda: (_ for _ in ()).throw(
                NativeCapacityEvidenceError("truncated 0x0019 response")
            ),
        )
        with self.assertRaisesRegex(PreparedPackageWorkflowError, "capacity query"):
            self._run(setup)
        self.assertFalse((setup["root"] / "before").exists())

    def test_disconnect_before_transaction_is_failed_and_not_retried(self):
        setup = self._native_setup(backend=FailingBeforeTransactionBackend())
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaises(PreparedPackageWorkflowError) as raised:
            self._run(setup)
        self.assertEqual(raised.exception.state, "failed")
        self.assertFalse(raised.exception.write_started)
        self.assertFalse(raised.exception.audit["automatic_retry_allowed"])
        self.assertEqual(len(setup["send_calls"]), 1)

    def test_disconnect_after_transaction_is_indeterminate_once(self):
        setup = self._native_setup(backend=PackageWorkflowBackend(bulk_error=OSError("disconnect")))
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaisesRegex(PreparedPackageWorkflowError, "no automatic retry") as raised:
            self._run(setup)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertTrue(raised.exception.write_started)
        self.assertEqual(len(setup["send_calls"]), 1)

    def test_timeout_and_malformed_completion_are_terminal_once(self):
        setup = self._native_setup(backend=PackageWorkflowBackend(bulk_error=TransferTimeoutError("timeout")))
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaisesRegex(PreparedPackageWorkflowError, "no automatic retry") as raised:
            self._run(setup)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertEqual(len(setup["send_calls"]), 1)

        setup = self._native_setup(backend=MalformedCompletionBackend())
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaisesRegex(PreparedPackageWorkflowError, "no automatic retry") as raised:
            self._run(setup)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertEqual(len(setup["send_calls"]), 1)

    def test_nonzero_missing_and_readback_mismatch_are_terminal(self):
        setup = self._native_setup(backend=PackageWorkflowBackend(completions=(1, 0)))
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaisesRegex(PreparedPackageWorkflowError, "no automatic retry"):
            self._run(setup)
        self.assertEqual(len(setup["send_calls"]), 1)

        setup = self._native_setup()
        self.addCleanup(setup["temporary"].cleanup)
        old = setup["workflow"]

        def missing_completion(transaction, authorization, *, cancelled, progress):
            old._send(transaction, authorization, cancelled=cancelled, progress=progress)
            return None

        setup["workflow"] = GuardedPreparedPackageWorkflow(
            old._capture,
            missing_completion,
            old._template,
            detect_device=old._detect_device,
            query_capacity=old._query_capacity,
        )
        with self.assertRaisesRegex(PreparedPackageWorkflowError, "unacceptable completion"):
            self._run(setup)
        self.assertEqual(len(setup["send_calls"]), 1)

        setup = self._native_setup(after_mode="mismatch")
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaisesRegex(PreparedPackageWorkflowError, "no automatic retry") as raised:
            self._run(setup)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertEqual(len(setup["send_calls"]), 1)


if __name__ == "__main__":
    unittest.main()
