from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import parse_backup_blob
from infocarry.prepared_multi_package_live_smoke import (
    P15_002_MODERN_MULTI_TXT_CONFIRMATION,
    P15_002_MODERN_MULTI_TXT_OWNER_APPROVAL,
    PreparedMultiPackageLiveSender,
    PreparedMultiPackageLiveSmokeError,
    execute_prepared_multi_package_live_smoke,
    prepare_prepared_multi_package_live_smoke,
)
from infocarry.prepared_multi_text import build_prepared_text_package_set
from infocarry.protocol import REQUEST_COMPLETION, TransferTimeoutError
from infocarry.write_protocol import WritePolicy

try:
    from test_new_txt import _write_archive
    from test_prepared_package_multi_candidate import _template_blobs
    from test_prepared_package_workflow import PackageWorkflowBackend
    import test_prepared_package_multi_candidate as _fixture
except ModuleNotFoundError:
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_package_multi_candidate import _template_blobs
    from tests.test_prepared_package_workflow import PackageWorkflowBackend
    import tests.test_prepared_package_multi_candidate as _fixture


class BeforeHeaderFailureBackend(PackageWorkflowBackend):
    def control_out(self, request_type, request, value, index, data, timeout_ms):
        self.calls.append(("control_out", request, bytes(data)))
        raise OSError("simulated disconnect before request 0x02")


class MalformedCompletionBackend(PackageWorkflowBackend):
    def control_in(self, request_type, request, value, index, length, timeout_ms):
        if request == REQUEST_COMPLETION:
            self.calls.append(("control_in", request))
            return b"\x00"
        return super().control_in(request_type, request, value, index, length, timeout_ms)


class PreparedMultiPackageLiveSmokeTests(unittest.TestCase):
    now = datetime(2026, 8, 30, tzinfo=timezone.utc)

    def _setup(self, *, backend=None, after_blob=None):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        baseline_blob, template_blob = _template_blobs()
        fixed_state = {
            command: b"\x00" * 64
            for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)
        }
        source_specs = []
        for index in range(1, 5):
            source = root / f"chapter-{index:02d}.txt"
            source.write_text(f"chapter {index}\n", encoding="utf-8")
            source_specs.append((source, f"chapter-{index:02d}.txt"))
        package = build_prepared_text_package_set(
            source_specs,
            "IC_P15_MULTI_20260828_02",
        )
        template = parse_backup_blob(template_blob)
        response = _fixture.PreparedMultiCandidateTests()._response()
        current = {"candidate": None}
        captures = []

        def capture(destination, **_kwargs):
            captures.append(Path(destination))
            blob = baseline_blob if len(captures) == 1 else (
                current["candidate"].candidate_blob
                if after_blob is None
                else after_blob
            )
            _write_archive(destination, blob, self.now, fixed_state=fixed_state)

        previewed = []

        def preview_callback(candidate):
            previewed.append(candidate.audit_dict())
            current["candidate"] = candidate

        backend = backend or PackageWorkflowBackend()
        sender = PreparedMultiPackageLiveSender(
            backend,
            0x01,
            policy=WritePolicy(
                busy_timeout_seconds=0.25,
                busy_poll_interval_seconds=0.01,
            ),
        )
        common = {
            "backup_destination": root / "fresh-before",
            "package": package,
            "template": template,
            "template_folder_path": ("root", "Template"),
            "template_item_paths": {"txt": ("root", "Template", "chapter")},
            "new_record_timestamp_be32": 0x6A91A907,
            "expected_folder_name": "IC_P15_MULTI_20260828_02",
            "detect_device": lambda: (0x054C, 0x001E),
            "query_capacity": lambda: response,
            "capture": capture,
            "preview_callback": preview_callback,
            "now": self.now,
            "max_age_seconds": None,
        }
        preflight = prepare_prepared_multi_package_live_smoke(**common)
        current["candidate"] = preflight.candidate
        return {
            "temporary": temporary,
            "root": root,
            "package": package,
            "preflight": preflight,
            "response": response,
            "capture": capture,
            "previewed": previewed,
            "backend": backend,
            "sender": sender,
            "common": common,
            "current": current,
            "captures": captures,
        }

    def _execute(self, setup, **overrides):
        arguments = {
            "post_operation_destination": setup["root"] / "after",
            "owner_approval": P15_002_MODERN_MULTI_TXT_OWNER_APPROVAL,
            "confirmation": P15_002_MODERN_MULTI_TXT_CONFIRMATION,
            "detect_device": setup["common"]["detect_device"],
            "query_capacity": setup["common"]["query_capacity"],
            "capture": setup["capture"],
            "sender": setup["sender"],
            "now": self.now,
            "max_age_seconds": None,
        }
        arguments.update(overrides)
        return execute_prepared_multi_package_live_smoke(
            setup["preflight"],
            **arguments,
        )

    def test_read_only_preflight_is_default_and_seals_absent_four_txt_target(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        preflight = setup["preflight"]
        self.assertEqual(preflight.audit["state"], "preflight_sealed")
        self.assertTrue(preflight.audit["read_only"])
        self.assertTrue(preflight.audit["target_absent_from_fresh_backup"])
        self.assertEqual(len(setup["previewed"]), 1)
        self.assertEqual(setup["sender"].calls, 0)
        self.assertEqual(len(setup["captures"]), 1)
        preflight.verify_seal()

    def test_preflight_seal_ignores_reverification_observation_timestamp(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        preflight = setup["preflight"]
        reverified_backup = replace(
            preflight.before_backup,
            verified_at_utc="2026-08-30T12:34:56+00:00",
        )
        reloaded = replace(preflight, before_backup=reverified_backup)
        reloaded.verify_seal()

    def test_execution_refuses_a_modified_sealed_preflight(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        setup["preflight"].candidate.audit["candidate"]["blob_sha256"] = "0" * 64
        with self.assertRaisesRegex(PreparedMultiPackageLiveSmokeError, "sealed") as raised:
            self._execute(setup)
        self.assertEqual(raised.exception.stage, "preflight_seal")
        self.assertEqual(setup["sender"].calls, 0)
        self.assertEqual(len(setup["captures"]), 1)

    def test_execution_requires_later_owner_approval_and_exact_confirmation(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaisesRegex(PreparedMultiPackageLiveSmokeError, "owner approval"):
            self._execute(setup, owner_approval="APPROVE SOMETHING ELSE")
        self.assertEqual(setup["sender"].calls, 0)
        self.assertEqual(len(setup["captures"]), 1)

        with self.assertRaisesRegex(PreparedMultiPackageLiveSmokeError, "confirmation"):
            self._execute(setup, confirmation="ADD ONE INFOCARRY PACKAGE")
        self.assertEqual(setup["sender"].calls, 0)
        self.assertEqual(len(setup["captures"]), 1)

    def test_success_revalidates_sealed_candidate_sends_once_and_verifies_readback(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        result = self._execute(setup)
        self.assertEqual(result.completion, 0)
        self.assertTrue(result.verification.success)
        self.assertEqual(setup["sender"].calls, 1)
        self.assertEqual(len(setup["captures"]), 2)
        self.assertEqual(
            result.audit["workflow"]["operation_sequence"],
            [
                "preflight_seal_verified",
                "owner_approval",
                "confirmation_phrase",
                "device_revalidated",
                "capacity_revalidated",
                "fresh_backup_revalidated",
                "candidate_reconstructed",
                "authorization_sealed",
                "single_0x101b_transaction",
                "completion_0x0000",
                "fresh_post_operation_backup",
                "independent_readback_verification",
            ],
        )
        self.assertEqual(
            result.authorization.target_paths,
            (
                "root\\IC_P15_MULTI_20260828_02",
                "root\\IC_P15_MULTI_20260828_02\\chapter-01.txt",
                "root\\IC_P15_MULTI_20260828_02\\chapter-02.txt",
                "root\\IC_P15_MULTI_20260828_02\\chapter-03.txt",
                "root\\IC_P15_MULTI_20260828_02\\chapter-04.txt",
            ),
        )
        self.assertFalse(result.audit["workflow"]["automatic_retry_allowed"])

    def test_preserved_capture01_name_is_refused(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        bad_package = replace(setup["package"], folder_name="IC_P15_MULTI_20260828_01")
        with self.assertRaisesRegex(PreparedMultiPackageLiveSmokeError, "_01"):
            common = dict(setup["common"])
            common.update(
                package=bad_package,
                expected_folder_name="IC_P15_MULTI_20260828_01",
                backup_destination=setup["root"] / "bad-before",
            )
            prepare_prepared_multi_package_live_smoke(**common)
        self.assertEqual(len(setup["captures"]), 1)

    def test_cancellation_before_start_is_safe_and_after_start_is_indeterminate(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaisesRegex(PreparedMultiPackageLiveSmokeError, "cancelled") as raised:
            self._execute(setup, cancelled=lambda: True)
        self.assertEqual(raised.exception.state, "cancelled_before_transaction")
        self.assertFalse(raised.exception.write_started)
        self.assertEqual(setup["sender"].calls, 0)

        after = self._setup()
        self.addCleanup(after["temporary"].cleanup)
        cancelled = lambda: any(call[0] == "control_out" for call in after["backend"].calls)
        with self.assertRaisesRegex(PreparedMultiPackageLiveSmokeError, "transaction stopped") as raised:
            self._execute(after, cancelled=cancelled)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertTrue(raised.exception.write_started)
        self.assertEqual(after["sender"].calls, 1)
        self.assertFalse(raised.exception.audit["automatic_retry_allowed"])

    def test_before_start_failure_timeout_and_disconnect_are_terminal_without_retry(self):
        before = self._setup(backend=BeforeHeaderFailureBackend())
        self.addCleanup(before["temporary"].cleanup)
        with self.assertRaises(PreparedMultiPackageLiveSmokeError) as raised:
            self._execute(before)
        self.assertEqual(raised.exception.state, "failed")
        self.assertFalse(raised.exception.write_started)
        self.assertEqual(before["sender"].calls, 1)

        for error in (OSError("disconnect"), TransferTimeoutError("timeout")):
            setup = self._setup(backend=PackageWorkflowBackend(bulk_error=error))
            self.addCleanup(setup["temporary"].cleanup)
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(PreparedMultiPackageLiveSmokeError) as raised:
                    self._execute(setup)
                self.assertEqual(
                    raised.exception.state,
                    "indeterminate_after_transaction_start",
                )
                self.assertTrue(raised.exception.write_started)
                self.assertEqual(setup["sender"].calls, 1)

    def test_nonzero_malformed_completion_and_readback_failure_are_terminal(self):
        nonzero = self._setup(backend=PackageWorkflowBackend(completions=(1, 0)))
        self.addCleanup(nonzero["temporary"].cleanup)
        with self.assertRaises(PreparedMultiPackageLiveSmokeError) as raised:
            self._execute(nonzero)
        self.assertEqual(raised.exception.stage, "write")
        self.assertEqual(raised.exception.state, "failed")
        self.assertEqual(nonzero["sender"].calls, 1)

        malformed = self._setup(backend=MalformedCompletionBackend())
        self.addCleanup(malformed["temporary"].cleanup)
        with self.assertRaises(PreparedMultiPackageLiveSmokeError) as raised:
            self._execute(malformed)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertEqual(malformed["sender"].calls, 1)

        mismatch = self._setup()
        self.addCleanup(mismatch["temporary"].cleanup)
        bad_blob = bytearray(mismatch["preflight"].candidate.candidate_blob)
        bad_blob[-1] ^= 1
        with self.assertRaises(PreparedMultiPackageLiveSmokeError) as raised:
            self._execute(mismatch, post_operation_destination=mismatch["root"] / "after-bad", capture=lambda destination, **kwargs: _write_archive(destination, bytes(bad_blob), self.now, fixed_state={command: b"\x00" * 64 for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}))
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertEqual(mismatch["sender"].calls, 1)


if __name__ == "__main__":
    unittest.main()
