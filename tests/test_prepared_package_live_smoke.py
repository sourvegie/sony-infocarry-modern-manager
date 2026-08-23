import unittest

from infocarry.prepared_package_gate import PREPARED_PACKAGE_CONFIRMATION_PHRASE
from infocarry.prepared_package_live_smoke import (
    PREPARED_PACKAGE_LIVE_SMOKE_OWNER_APPROVAL,
    PreparedPackageLiveSmokeError,
    run_prepared_package_live_smoke,
)

try:
    from test_prepared_package_native_workflow import PackageWorkflowBackend
    import test_prepared_package_native_workflow as _native_workflow_fixture
except ModuleNotFoundError:
    from tests.test_prepared_package_native_workflow import PackageWorkflowBackend
    import tests.test_prepared_package_native_workflow as _native_workflow_fixture


class PreparedPackageLiveSmokeTests(unittest.TestCase):
    def _setup(self, *, backend=None):
        helper = _native_workflow_fixture.PreparedPackageNativeWorkflowTests()
        setup = helper._native_setup(backend=backend)
        self.addCleanup(setup["temporary"].cleanup)
        old_workflow = setup["workflow"]
        previewed = []

        def preview_callback(candidate):
            previewed.append(candidate.audit_dict())

        return setup, old_workflow, previewed, preview_callback

    def _run(self, setup, old_workflow, previewed, preview_callback, **overrides):
        arguments = {
            "backup_destination": setup["root"] / "live-before",
            "post_operation_destination": setup["root"] / "live-after",
            "package": setup["package"],
            "template": old_workflow._template,
            "new_record_timestamp_be32": 0x6A8ABA6F,
            "confirmation": PREPARED_PACKAGE_CONFIRMATION_PHRASE,
            "owner_approval": PREPARED_PACKAGE_LIVE_SMOKE_OWNER_APPROVAL,
            "detect_device": old_workflow._detect_device,
            "query_capacity": old_workflow._query_capacity,
            "capture": old_workflow._capture,
            "send": old_workflow._send,
            "preview": setup["preview"].candidate,
            "preview_callback": preview_callback,
            "now": setup["now"],
            "max_age_seconds": None,
        }
        arguments.update(overrides)
        return run_prepared_package_live_smoke(**arguments)

    def test_fake_smoke_requires_both_approval_values_before_capture(self):
        setup, old_workflow, previewed, preview_callback = self._setup()
        with self.assertRaises(PreparedPackageLiveSmokeError) as raised:
            self._run(
                setup,
                old_workflow,
                previewed,
                preview_callback,
                owner_approval="APPROVE SOMETHING ELSE",
            )
        self.assertEqual(raised.exception.stage, "approval")
        self.assertFalse((setup["root"] / "live-before").exists())
        self.assertEqual(previewed, [])

    def test_fake_smoke_runs_exact_sequence_once_and_verifies_readback(self):
        setup, old_workflow, previewed, preview_callback = self._setup()
        result = self._run(setup, old_workflow, previewed, preview_callback)
        self.assertEqual(result.completion, 0)
        self.assertTrue(result.verification.success)
        self.assertEqual(len(previewed), 1)
        self.assertFalse(result.audit["workflow"]["automatic_retry_allowed"])
        self.assertEqual(
            result.audit["workflow"]["sequence"],
            [
                "owner_approval",
                "confirmation_phrase",
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
        self.assertEqual(len(setup["send_calls"]), 1)

    def test_displayed_candidate_change_stops_before_send(self):
        setup, old_workflow, previewed, preview_callback = self._setup()
        changed = setup["preview"].candidate
        changed.audit["allocation"]["candidate_model_bytes"] += 1
        with self.assertRaisesRegex(PreparedPackageLiveSmokeError, "differs"):
            self._run(
                setup,
                old_workflow,
                previewed,
                preview_callback,
                preview=changed,
            )
        self.assertEqual(setup["send_calls"], [])
        self.assertEqual(previewed, [])

    def test_disconnect_after_transaction_is_indeterminate_and_not_retried(self):
        setup, old_workflow, previewed, preview_callback = self._setup(
            backend=PackageWorkflowBackend(bulk_error=OSError("disconnect"))
        )
        with self.assertRaises(PreparedPackageLiveSmokeError) as raised:
            self._run(setup, old_workflow, previewed, preview_callback)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertTrue(raised.exception.write_started)
        self.assertFalse(raised.exception.audit["automatic_retry_allowed"])
        self.assertEqual(len(setup["send_calls"]), 1)


if __name__ == "__main__":
    unittest.main()
