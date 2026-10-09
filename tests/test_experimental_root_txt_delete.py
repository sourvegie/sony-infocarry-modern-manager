"""Portable host-only exact Delete tests; all safety state is temporary."""
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
import importlib.util
import io
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from infocarry.backup_format import parse_backup_blob, calculate_backup_checksum
from infocarry.backup_repack import rename_existing_record, delete_existing_file
from infocarry.delete_workflow import (
    ExperimentalRootTxtDeleteFacade, ROOT_TXT_DELETE_CONFIRMATION,
    EXPERIMENTAL_ROOT_TXT_DELETE_PROFILE, build_experimental_root_txt_delete,
)
from infocarry.p18_041h_experiment import FIXTURE_FILENAME, FIXTURE_PATH, FIXTURE_BYTES
from infocarry.write_protocol import REQUEST_BEGIN_TRANSMIT
from infocarry.device_model_profile import VNW_V15_PROFILE
from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.device_info import RawInfoResponse
try:
    import test_root_txt_placement as placement_helpers
    from test_new_txt import _make_root_blob, _write_archive
    from test_backup_repack import make_aligned_delete_blob
except ModuleNotFoundError:
    from tests import test_root_txt_placement as placement_helpers
    from tests.test_new_txt import _make_root_blob, _write_archive
    from tests.test_backup_repack import make_aligned_delete_blob


class ExperimentalRootTxtDeleteTests(unittest.TestCase):
    def setup_case(self, **kwargs):
        helper = placement_helpers.RootPlacementTests(
            "test_exact_fixture_admitted_frozen_without_sender_or_claim")
        self.addCleanup(helper.doCleanups)
        case = helper.setup_case(**kwargs)
        addition = helper.prepare(case)
        self.assertEqual(case[3].calls, [])
        state = case[2]
        state["original_blob"] = state["blob"]
        state["blob"] = addition.candidate.candidate_blob
        state["fixed"] = {0x001b: addition.candidate.transaction.ranges[0][:64],
            0x001c: addition.candidate.transaction.ranges[0][64:128],
            0x001d: addition.candidate.transaction.ranges[0][128:192],
            0x001e: addition.candidate.transaction.ranges[0][192:256],
            0x001f: addition.candidate.transaction.ranges[1]}
        # Older add fakes contain synthetic unresolved pointers. Delete
        # tests begin with supported zero state and add valid refs explicitly.
        state["fixed"] = {c: b"\0" * 64 for c in range(0x001b, 0x0020)}
        state["fixture_blob"] = state["blob"]
        state["bad_delete_readback"] = False
        old_capture = case[4].runtime.capture
        def capture(destination, **kwargs):
            if destination.name == "backup-after-0001" and state["bad_delete_readback"]:
                _write_archive(destination, state["fixture_blob"], datetime.now(timezone.utc),
                               fixed_state=state["fixed"])
            else:
                old_capture(destination, **kwargs)
        runtime = replace(case[4].runtime, capture=capture)
        facade = ExperimentalRootTxtDeleteFacade(runtime)
        return (*case[:4], facade, *case[5:])

    def prepare(self, case):
        case[2]["bundle"] = case[4].prepare()
        return case[2]["bundle"]

    def approve(self, case):
        identity = case[4].owner_authorization_identity
        self.assertEqual(identity.approval_phrase, ROOT_TXT_DELETE_CONFIRMATION)
        case[4].authorize_prepared_operation(ROOT_TXT_DELETE_CONFIRMATION)
        return identity

    def no_send_or_claim(self, case, bundle=None):
        self.assertEqual(case[3].calls, [])
        self.assertIsNone(case[5].read_sender_in_flight())
        if bundle is not None:
            self.assertIsNone(case[5].read_claim(bundle.seal_sha256))

    def execute(self, case):
        return case[4].execute_once(confirmation_interaction=lambda _: ROOT_TXT_DELETE_CONFIRMATION)

    def test_exact_candidate_inverse_preserves_timestamps_and_is_claim_free(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        self.assertEqual(bundle.candidate.candidate_blob, case[2]["original_blob"])
        self.assertEqual(case[2]["timestamp_calls"], 1)  # only fixture construction, not Delete
        self.assertEqual(bundle.candidate.core.target_path, FIXTURE_PATH)
        self.assertEqual(bundle.candidate.core.audit["policy"]["timestamps"], "preserve_surviving_timestamps")
        bundle.verify_seal()
        self.no_send_or_claim(case, bundle)

    def test_wrong_model_path_nested_target_rejected_before_callbacks(self):
        for kwargs in ({"device_model": "VNW-V10"}, {"target_path": "root\\different.txt"},
                       {"target_path": "root\\folder\\" + FIXTURE_FILENAME}):
            with self.subTest(kwargs=kwargs):
                case = self.setup_case()
                captures = len(case[2]["captures"])
                with self.assertRaises(ValueError):
                    case[4].prepare(**kwargs)
                self.assertEqual(len(case[2]["captures"]), captures)
                self.no_send_or_claim(case)

    def test_absent_target_rejected(self):
        case = self.setup_case()
        case[2]["blob"] = case[2]["original_blob"]
        with self.assertRaisesRegex(ValueError, "fixture"):
            self.prepare(case)
        self.no_send_or_claim(case)

    def test_target_referenced_by_history_or_bookmark_rejected(self):
        for command in (0x001b, 0x001f):
            with self.subTest(command=command):
                case = self.setup_case()
                parsed = parse_backup_blob(case[2]["blob"])
                offset = next(off for off, path in parsed.paths.items()
                              if path == ("root", Path(FIXTURE_FILENAME).stem))
                ref = offset - parsed.header.metadata_start
                raw = bytearray(64)
                if command == 0x001b:
                    raw[:4] = (1).to_bytes(4, "big")
                    raw[8:12] = ref.to_bytes(4, "big")
                else:
                    raw[:4] = ref.to_bytes(4, "big")
                    raw[8:12] = (0x80000000).to_bytes(4, "big")
                case[2]["fixed"][command] = bytes(raw)
                with self.assertRaisesRegex(Exception, "referenced"):
                    self.prepare(case)
                self.no_send_or_claim(case)

    def test_active_marks_or_unresolved_history_rejected(self):
        for command in (0x001c, 0x001b):
            with self.subTest(command=command):
                case = self.setup_case()
                raw = bytearray(64)
                raw[:4] = (1).to_bytes(4, "big")
                raw[8:12] = (0xffffffc0).to_bytes(4, "big")
                case[2]["fixed"][command] = bytes(raw)
                with self.assertRaises(Exception):
                    self.prepare(case)
                self.no_send_or_claim(case)

    def test_protected_unrelated_history_and_bookmark_survive_inverse_rebase(self):
        case = self.setup_case()
        parsed = parse_backup_blob(case[2]["blob"])
        target_offset = next(off for off, path in parsed.paths.items()
                             if path == ("root", Path(FIXTURE_FILENAME).stem))
        survivor = next(r for r in parsed.records if r.kind == "file" and r.offset != target_offset)
        ref = survivor.offset - parsed.header.metadata_start
        history = bytearray(64)
        history[:4] = (1).to_bytes(4, "big")
        history[8:12] = ref.to_bytes(4, "big")
        bookmark = bytearray(64)
        bookmark[:4] = ref.to_bytes(4, "big")
        bookmark[4:20] = bytes.fromhex("00000c000000000000000014fff101c5")
        case[2]["fixed"][0x001b] = bytes(history)
        case[2]["fixed"][0x001f] = bytes(bookmark)
        bundle = self.prepare(case)
        state = bundle.candidate.core.fixed_state
        expected = ref - 64 if survivor.offset > target_offset else ref
        self.assertEqual(int.from_bytes(state.after[0][8:12], "big"), expected)
        self.assertEqual(int.from_bytes(state.after[4][:4], "big"), expected)
        self.assertEqual(state.after[4][4:], bytes(bookmark)[4:])
        self.assertTrue(state.audit["opaque_bytes_preserved_exactly"])
        self.approve(case)
        result = self.execute(case)
        self.assertTrue(result.verification.to_dict()["exact_path_and_payload_verification"]["protected_auxiliary_associations_preserved"])

    def test_signed_after_rebase_preserves_opaque_tails(self):
        case = self.setup_case()
        blob = bytearray(make_aligned_delete_blob(FIXTURE_BYTES))
        # The helper's source prefix starts after the aligned target segment.
        blob[0x180 + 4:0x180 + 8] = (64).to_bytes(4, "big")
        blob[0x1c:0x20] = calculate_backup_checksum(blob).to_bytes(4, "big")
        blob = rename_existing_record(parse_backup_blob(blob), 0x100,
                                      Path(FIXTURE_FILENAME).stem)
        parsed = parse_backup_blob(blob)
        original = delete_existing_file(parsed, 0x100)
        case[2]["original_blob"] = original
        case[2]["blob"] = blob
        case[2]["fixture_blob"] = blob
        right = 0x180 - 64
        history = bytearray(64)
        history[:4] = (1).to_bytes(4, "big")
        history[8:12] = right.to_bytes(4, "big")
        history[60:] = b"TAIL"
        bookmark = bytearray(64)
        bookmark[:4] = right.to_bytes(4, "big")
        bookmark[4:20] = bytes.fromhex("00000c000000000000000014fff101c5")
        bookmark[60:] = b"KEEP"
        case[2]["fixed"][0x1b], case[2]["fixed"][0x1f] = bytes(history), bytes(bookmark)
        # An authoritative zero-count Mark may retain opaque unused bytes.
        mark = bytearray(64)
        mark[60:] = b"MARK"
        case[2]["fixed"][0x1c] = bytes(mark)
        bundle = self.prepare(case)
        after = bundle.candidate.core.fixed_state.after
        self.assertEqual(bundle.candidate.candidate_blob, original)
        self.assertEqual(after[0][8:12], (right - 64).to_bytes(4, "big"))
        self.assertEqual(after[4][:4], (right - 64).to_bytes(4, "big"))
        self.assertEqual(after[0][12:], bytes(history)[12:])
        self.assertEqual(after[4][4:], bytes(bookmark)[4:])
        self.assertEqual(after[1], bytes(mark))

    def test_fake_success_has_one_sender_with_marker_before_first_byte(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        self.approve(case)
        original = case[3].control_out
        def check(*args):
            self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
            self.assertIsNotNone(case[5].read_sender_in_flight())
            return original(*args)
        case[3].control_out = check
        result = self.execute(case)
        self.assertEqual(result.completion, 0)
        self.assertEqual(result.audit["profile"], EXPERIMENTAL_ROOT_TXT_DELETE_PROFILE)
        self.assertTrue(result.audit["execution_equivalence"]["target_present_and_exact"])
        self.assertEqual(sum(c[0] == "control_out" and c[1] == REQUEST_BEGIN_TRANSMIT for c in case[3].calls), 1)
        self.assertIsNone(case[5].read_sender_in_flight())
        self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
        root = Path(result.audit["evidence_outputs"]["root"])
        self.assertTrue((root / "root-txt-delete-report.json").is_file())
        self.assertFalse((root / "01-fixture-prestage").exists())
        with self.assertRaises(Exception):
            self.execute(case)
        self.assertEqual(sum(c[0] == "control_out" for c in case[3].calls), 1)

    def test_no_owner_or_wrong_confirmation_exposes_no_sender(self):
        for mode in ("no_owner", "wrong_confirmation", "wrong_owner_phrase"):
            with self.subTest(mode=mode):
                case = self.setup_case()
                bundle = self.prepare(case)
                if mode == "wrong_owner_phrase":
                    with self.assertRaises(Exception):
                        case[4].authorize_prepared_operation("DELETE ONE INFOCARRY ITEM")
                else:
                    if mode == "wrong_confirmation":
                        self.approve(case)
                    with self.assertRaises(Exception):
                        case[4].execute_once(confirmation_interaction=lambda _: "wrong")
                self.no_send_or_claim(case, bundle)

    def test_approval_refresh_and_rebinding_rejected(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        self.approve(case)
        reads = len(case[2]["captures"])
        with self.assertRaisesRegex(Exception, "cannot refresh"):
            case[4].prepare()
        self.assertEqual(len(case[2]["captures"]), reads)
        self.no_send_or_claim(case, bundle)

    def test_stale_approval_rejected(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        identity = self.approve(case)
        case[4]._owner_authorized_identity = replace(identity, transaction_sha256="a" * 64)
        with self.assertRaises(Exception):
            self.execute(case)
        self.no_send_or_claim(case, bundle)

    def test_frozen_artifact_drift_consumes_no_claim(self):
        for name in ("source_artifact", "candidate_artifact", "capacity_artifact", "backup_artifact", "seal_artifact"):
            with self.subTest(name=name):
                case = self.setup_case()
                bundle = self.prepare(case)
                self.approve(case)
                path = Path(getattr(bundle, name).path)
                if name == "backup_artifact":
                    path = path / "manifest.json"
                path.write_bytes(b"changed")
                with self.assertRaises(Exception):
                    self.execute(case)
                self.no_send_or_claim(case, bundle)

    def test_candidate_audit_drift_rejected_before_claim(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        self.approve(case)
        changed = replace(bundle.candidate, audit_json=b'{"operation":"NOT_DELETE"}')
        object.__setattr__(bundle, "candidate", changed)
        with self.assertRaises(Exception):
            self.execute(case)
        self.no_send_or_claim(case, bundle)

    def test_execution_backup_drift_consumes_no_claim(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        self.approve(case)
        case[2]["blob"] = case[2]["original_blob"]
        with self.assertRaisesRegex(Exception, "backup differs"):
            self.execute(case)
        self.no_send_or_claim(case, bundle)

    def test_identical_reconnect_succeeds_and_wrong_model_reconnect_fails(self):
        for identity in ((0x054c, 0x001e), (0x054c, 0x001d)):
            with self.subTest(identity=identity):
                case = self.setup_case(reconnect=True, equivalence_device=identity)
                bundle = self.prepare(case)
                self.approve(case)
                case[2]["session"] = "reconnected-session-B"
                if identity == (0x054c, 0x001e):
                    self.assertEqual(self.execute(case).completion, 0)
                    self.assertEqual(case[2]["armed_generation"], 2)
                else:
                    with self.assertRaises(Exception):
                        self.execute(case)
                    self.no_send_or_claim(case, bundle)

    def test_poststart_disconnect_sets_global_lock_and_never_retries(self):
        case = self.setup_case(backend_options={"fail_bulk_at": 2})
        bundle = self.prepare(case)
        self.approve(case)
        with self.assertRaises(Exception) as error:
            self.execute(case)
        self.assertEqual(error.exception.state, "indeterminate_after_transaction_start")
        self.assertTrue(case[6].read(VNW_V15_PROFILE.lock_key).locked)
        self.assertIsNotNone(case[5].read_sender_in_flight())
        self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
        self.assertEqual(sum(c[0] == "control_out" for c in case[3].calls), 1)

    def test_nonzero_completion_is_terminal_with_consumed_claim(self):
        case = self.setup_case(backend_options={"completion": (2,)})
        bundle = self.prepare(case)
        self.approve(case)
        with self.assertRaises(Exception) as error:
            self.execute(case)
        self.assertEqual(error.exception.state, "failed")
        self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
        self.assertIsNone(case[5].read_sender_in_flight())
        self.assertEqual(sum(c[0] == "control_out" for c in case[3].calls), 1)
        self.assertFalse(list(case[0].rglob("root-txt-delete-report.json")))

    def test_bad_complete_readback_retains_global_lock(self):
        case = self.setup_case()
        self.prepare(case)
        self.approve(case)
        case[2]["bad_delete_readback"] = True
        with self.assertRaises(Exception):
            self.execute(case)
        self.assertTrue(case[6].read(VNW_V15_PROFILE.lock_key).locked)
        self.assertIsNotNone(case[5].read_sender_in_flight())
        self.assertFalse(list(case[0].rglob("root-txt-delete-report.json")))

    def test_capacity_drift_before_claim_does_not_arm_sender(self):
        case = self.setup_case(reconnect=True)
        bundle = self.prepare(case)
        self.approve(case)
        raw = bytearray(case[2]["capacity"].raw_response)
        raw[8:12] = (3145727).to_bytes(4, "big")
        case[2]["capacity"] = NativeCapacityResponse.from_hardware_response(
            RawInfoResponse(0x0019, "hardware", bytes(raw)), device_identity=(0x054c, 0x001e))
        with self.assertRaises(Exception):
            self.execute(case)
        self.no_send_or_claim(case, bundle)
        self.assertNotIn("armed_generation", case[2])

    def test_malformed_completion_retains_marker_and_global_lock(self):
        for completion in (False, None, "0x0000"):
            with self.subTest(completion=completion):
                case = self.setup_case()
                bundle = self.prepare(case)
                self.approve(case)
                with patch("infocarry.write_protocol.AuthorizedWriteSender.send", return_value=completion):
                    with self.assertRaises(Exception) as error:
                        self.execute(case)
                self.assertEqual(error.exception.state, "indeterminate_after_transaction_start")
                self.assertTrue(case[6].read(VNW_V15_PROFILE.lock_key).locked)
                self.assertIsNotNone(case[5].read_sender_in_flight())
                self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
                self.assertFalse(list(case[0].rglob("root-txt-delete-report.json")))

    def test_transaction_artifact_and_review_drift_rejected(self):
        for mode in ("transaction", "review"):
            with self.subTest(mode=mode):
                case = self.setup_case()
                bundle = self.prepare(case)
                self.approve(case)
                if mode == "transaction":
                    next(bundle.transaction_directory.glob("*.bin")).write_bytes(b"changed")
                    with self.assertRaises(Exception):
                        self.execute(case)
                else:
                    def confirmation(review):
                        object.__setattr__(bundle, "candidate_artifact",
                                           replace(bundle.candidate_artifact, sha256="a" * 64))
                        return ROOT_TXT_DELETE_CONFIRMATION
                    with self.assertRaises(Exception):
                        case[4].execute_once(confirmation_interaction=confirmation)
                self.no_send_or_claim(case, bundle)

    def test_existing_placement_bundle_cannot_be_adopted_for_delete(self):
        helper = placement_helpers.RootPlacementTests("test_exact_fixture_admitted_frozen_without_sender_or_claim")
        self.addCleanup(helper.doCleanups)
        addition_case = helper.setup_case()
        addition = helper.prepare(addition_case)
        case = self.setup_case()
        with self.assertRaises(Exception):
            case[4].adopt_prepared_operation(addition)
        self.no_send_or_claim(case)

    def _script(self):
        path = Path(__file__).resolve().parents[1] / "scripts" / "experimental_root_txt_delete.py"
        spec = importlib.util.spec_from_file_location("experimental_delete_script_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_script_requires_write_flag_and_rejects_stale_offline_inputs(self):
        script = self._script()
        with patch("infocarry.write_safety_boundary.create_default_application_write_safety_owner") as owner:
            for arguments in ([], ["--allow-write", "--backup", "old", "--output", "old"]):
                with self.subTest(arguments=arguments), redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        script.main(arguments)
            owner.assert_not_called()

    def test_script_asks_once_and_uses_canonical_fake_guarded_lifecycle(self):
        case = self.setup_case()
        script = self._script()
        original = ExperimentalRootTxtDeleteFacade.prepare
        def prepare(facade):
            bundle = original(facade)
            case[2]["bundle"] = bundle
            return bundle
        output = io.StringIO()
        with patch("infocarry.write_safety_boundary.create_default_application_write_safety_owner"), \
             patch("infocarry.library_transfer_runtime_provider.ProductionLibraryTransferRuntimeProvider.for_current_application") as provider, \
             patch.object(ExperimentalRootTxtDeleteFacade, "prepare", prepare), \
             patch("builtins.input", return_value=ROOT_TXT_DELETE_CONFIRMATION) as prompt, \
             redirect_stdout(output):
            provider.return_value.create_root_txt_runtime.return_value = case[4].runtime
            self.assertEqual(script.main(["--allow-write"]), 0)
        prompt.assert_called_once()
        self.assertNotIn(case[2]["bundle"].seal_sha256, output.getvalue())
        self.assertEqual(sum(c[0] == "control_out" for c in case[3].calls), 1)
        self.assertIsNone(case[5].read_sender_in_flight())


if __name__ == "__main__":
    unittest.main()
