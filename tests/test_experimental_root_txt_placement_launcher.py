"""Fixture launcher uses only injected isolated fakes in these tests."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from infocarry.delete_workflow import ROOT_TXT_DELETE_VALIDATION_FILES
from infocarry.root_txt_placement import RootTxtPlacementFacade
from infocarry.write_safety_boundary import PersistentWriteSafetyOwner
try:
    import test_disposable_root_txt_placement as placement_helpers
except ModuleNotFoundError:
    from tests import test_disposable_root_txt_placement as placement_helpers

spec = importlib.util.spec_from_file_location("placement_launcher",
    Path(__file__).resolve().parents[1] / "scripts" / "experimental_root_txt_placement.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class DisposablePlacementLauncherTests(unittest.TestCase):
    def test_missing_explicit_flag_and_wrong_source_never_initialize_runtime(self):
        helper = placement_helpers.DisposablePlacementTests()
        case, target = helper.setup_case()
        self.addCleanup(helper.doCleanups)
        args = ["--target", target, "--source", str(case[1]),
                "--review-output", str(case[0] / "review.json")]
        with patch("infocarry.write_safety_boundary.create_default_application_write_safety_owner") as owner:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                launcher.main(args)
            case[1].write_bytes(b"wrong disposable payload")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                launcher.main(["--allow-write", *args])
            owner.assert_not_called()
        self.assertEqual(case[3].calls, [])

    def run_case(self, target, *, cancel=False, tamper=False):
        helper = placement_helpers.DisposablePlacementTests()
        case, target = helper.setup_case(target)
        self.addCleanup(helper.doCleanups)
        owner = PersistentWriteSafetyOwner(execution_claim_store=case[5], indeterminate_write_lock=case[6])
        provider = Mock()
        provider.create_root_txt_runtime.return_value = case[4].runtime
        class ObservedFacade(RootTxtPlacementFacade):
            def prepare(self, *args, **kwargs):
                bundle = super().prepare(*args, **kwargs)
                case[2]["bundle"] = bundle
                return bundle
        def answer(_prompt):
            if tamper:
                case[2]["bundle"].source_path.write_bytes(b"altered after review")
            return "Cancel" if cancel else f"ADD {case[1].name} ONCE"
        args = ["--allow-write", "--target", target, "--source", str(case[1]),
                "--review-output", str(case[0] / "review.json")]
        with patch("infocarry.write_safety_boundary.create_default_application_write_safety_owner", return_value=owner), \
             patch("infocarry.library_transfer_runtime_provider.ProductionLibraryTransferRuntimeProvider.for_current_application", return_value=provider), \
             patch.object(launcher, "RootTxtPlacementFacade", ObservedFacade), \
             patch("builtins.input", side_effect=answer) as interaction, \
             contextlib.redirect_stdout(io.StringIO()):
            if tamper:
                with self.assertRaises(ValueError): launcher.main(args)
            else:
                self.assertEqual(launcher.main(args), 0)
            interaction.assert_called_once()
        return case

    def test_readable_single_answer_binds_each_exact_fixture_and_sends_once(self):
        for target in ROOT_TXT_DELETE_VALIDATION_FILES:
            with self.subTest(target=target):
                case = self.run_case(target)
                from infocarry.write_protocol import REQUEST_BEGIN_TRANSMIT
                self.assertEqual(sum(call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
                                     for call in case[3].calls), 1)
                self.assertIsNotNone(case[5].read_claim(case[2]["bundle"].seal_sha256))
                self.assertIsNone(case[5].read_sender_in_flight())

    def test_cancel_and_post_answer_artifact_change_do_not_send(self):
        target = next(iter(ROOT_TXT_DELETE_VALIDATION_FILES))
        for kwargs in ({"cancel": True}, {"tamper": True}):
            with self.subTest(**kwargs):
                case = self.run_case(target, **kwargs)
                self.assertEqual(case[3].calls, [])
                self.assertIsNone(case[5].read_claim(case[2]["bundle"].seal_sha256))
                self.assertIsNone(case[5].read_sender_in_flight())
