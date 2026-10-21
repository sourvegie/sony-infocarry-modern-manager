"""Host fakes only; persistent safety state is isolated in temporary roots."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from infocarry.execution_claim_store import PersistentExecutionClaimStore
from infocarry.indeterminate_write_lock import PersistentIndeterminateWriteLock
from infocarry.library_transfer_runtime_provider import PinnedRootTxtRuntime
from infocarry.library_transfer_execution import OwnerAuthorizedOperationIdentity
from infocarry.root_txt_placement import (
    RootTxtPlacementFacade, CONFIRMATION, FIXTURE_FILENAME, FIXTURE_PATH, FIXTURE_BYTES,
)
from infocarry.delete_workflow import ROOT_BMP_DELETE_FIXTURE_BYTES, ROOT_BMP_DELETE_FIXTURE_FILENAME, ROOT_BMP_DELETE_FIXTURE_PATH
from infocarry.backup_format import calculate_backup_checksum
from infocarry.p18_041h_experiment import _validate_fixture_prestage_report
from infocarry.write_protocol import REQUEST_COMPLETION, REQUEST_BEGIN_TRANSMIT
try:
    from test_new_txt import _make_root_blob, _write_archive
    from test_new_txt_workflow import WorkflowBackend
    from test_prepared_library_package_live_adapter import _response
except ModuleNotFoundError:
    from tests.test_new_txt import _make_root_blob, _write_archive
    from tests.test_new_txt_workflow import WorkflowBackend
    from tests.test_prepared_library_package_live_adapter import _response


class RootPlacementTests(unittest.TestCase):
    def setup_case(self, *, backend_options=None, reconnect=False, equivalence_device=None, media="txt"):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        blob = _make_root_blob()
        if media == "bmp":
            from test_backup_duplicate import make_nested_blob
            bmp_blob = bytearray(make_nested_blob(ROOT_BMP_DELETE_FIXTURE_BYTES, prefix_length=16))
            bmp_blob[0x141:0x144] = b"bmp"
            bmp_blob[0x1c:0x20] = bytes(4)
            bmp_blob[0x1c:0x20] = calculate_backup_checksum(bmp_blob).to_bytes(4, "big")
            blob = bytes(bmp_blob)
        bmp_zero_state = ({command: bytes(64) for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
                          if media == "bmp" else None)
        state = {"blob": blob, "fixed": bmp_zero_state, "closed": False,
                 "session": "selected-session-A", "captures": [], "capacity": _response(),
                 "after_bad": False, "timestamp_calls": 0}
        class Backend(WorkflowBackend):
            def control_in(self, *args):
                output = super().control_in(*args)
                if args[1] == REQUEST_COMPLETION:
                    transaction = state["bundle"].candidate.transaction
                    state["blob"] = transaction.ranges[4] + transaction.ranges[7]
                    state["fixed"] = {0x001B: transaction.ranges[0][:64],
                        0x001C: transaction.ranges[0][64:128], 0x001D: transaction.ranges[0][128:192],
                        0x001E: transaction.ranges[0][192:256], 0x001F: transaction.ranges[1]}
                return output
            def close(self):
                state["backend_closed"] = True
        backend = Backend(**(backend_options or {}))
        source = root / (ROOT_BMP_DELETE_FIXTURE_FILENAME if media == "bmp" else FIXTURE_FILENAME)
        source.write_bytes(ROOT_BMP_DELETE_FIXTURE_BYTES if media == "bmp" else FIXTURE_BYTES)
        claims = PersistentExecutionClaimStore(root / "claims.sqlite3")
        lock = PersistentIndeterminateWriteLock(root / "lock.json")
        def same(token):
            if state["closed"] or (not reconnect and token != state["session"]):
                raise ValueError("selected session lost")
        def capture(destination, **kwargs):
            same("selected-session-A")
            state["captures"].append(destination)
            blob = state["blob"]
            if destination.name == "backup-after-0001" and state["after_bad"]:
                blob = _make_root_blob()
            _write_archive(destination, blob, datetime.now(timezone.utc), fixed_state=state["fixed"])
        def timestamp():
            state["timestamp_calls"] += 1
            return 1791040000
        callbacks = {}
        if reconnect or equivalence_device is not None:
            callbacks["execution_equivalence"] = lambda token: (
                equivalence_device or (0x054c, 0x001e), state["capacity"], 2
            )
            callbacks["arm_sender"] = lambda generation: state.update(armed_generation=generation)
        runtime = PinnedRootTxtRuntime(root / "evidence", lambda: (0x054c,0x001e),
            lambda: state["capacity"], capture,backend,claims,lock,"selected-session-A",same,
            lambda: state.update(closed=True),timestamp, **callbacks)
        facade = RootTxtPlacementFacade(runtime)
        return root, source, state, backend, facade, claims, lock

    def prepare_bmp(self, case):
        case[2]["bundle"] = case[4].prepare(
            case[1], target_path=ROOT_BMP_DELETE_FIXTURE_PATH,
            validation_placement=True, placement_media="bmp")
        return case[2]["bundle"]

    def prepare(self, case):
        case[2]["bundle"] = case[4].prepare(case[1])
        return case[2]["bundle"]

    def approve(self, case):
        identity = case[4].owner_authorization_identity
        case[4].authorize_prepared_operation(identity.approval_phrase)
        return identity

    def no_send_or_claim(self, case, bundle=None):
        self.assertEqual(case[3].calls, [])
        if bundle is not None:
            self.assertIsNone(case[5].read_claim(bundle.seal_sha256))
        self.assertIsNone(case[5].read_sender_in_flight())

    def test_exact_fixture_admitted_frozen_without_sender_or_claim(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        self.assertEqual(bundle.candidate.core.audit["target"]["path"], FIXTURE_PATH)
        self.assertEqual(bundle.source_path.read_bytes(), FIXTURE_BYTES)
        self.assertEqual(case[2]["timestamp_calls"], 1)
        bundle.verify_seal()
        self.no_send_or_claim(case,bundle)
        case[4].discard_prepared_operation()
        self.assertTrue(case[2]["closed"])

    def test_experimental_root_bmp_bundle_is_sealed_and_scoped_to_one_file(self):
        case = self.setup_case(media="bmp")
        bundle = self.prepare_bmp(case)
        bundle.verify_seal()
        self.assertEqual(bundle.operation_profile,
                         "vnw-v15-disposable-root-bmp-placement-validation-v1")
        self.assertEqual(bundle.owner_confirmation_phrase,
                         f"ADD {ROOT_BMP_DELETE_FIXTURE_FILENAME} ONCE")
        self.assertEqual(bundle.candidate.core.audit["target"]["path"], ROOT_BMP_DELETE_FIXTURE_PATH)
        self.assertEqual(bundle.candidate.core.audit["target"]["native_prefix_length"], 16)
        self.assertEqual(bundle.authorization.to_dict()["format"],
                         "infocarry-disposable-root-bmp-placement-authorization-v1")
        self.assertEqual(bundle.review_dict()["fixture"]["sha256"],
                         __import__("hashlib").sha256(ROOT_BMP_DELETE_FIXTURE_BYTES).hexdigest())
        self.no_send_or_claim(case, bundle)

    def test_experimental_root_bmp_uses_existing_one_shot_guard_and_readback(self):
        case = self.setup_case(media="bmp")
        bundle = self.prepare_bmp(case)
        identity = case[4].owner_authorization_identity
        self.assertEqual(identity.approval_phrase,
                         f"ADD {ROOT_BMP_DELETE_FIXTURE_FILENAME} ONCE")
        case[4].authorize_prepared_operation(identity.approval_phrase)
        confirmation = f"ADD {ROOT_BMP_DELETE_FIXTURE_FILENAME} ONCE"
        result = case[4].execute_once(confirmation_interaction=lambda _: confirmation)
        self.assertEqual(result.completion, 0)
        self.assertEqual(result.audit["workflow"]["sender_calls"], 1)
        self.assertEqual(sum(call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
                             for call in case[3].calls), 1)
        self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
        self.assertIsNone(case[5].read_sender_in_flight())
        verification = result.verification.to_dict()["exact_path_and_payload_verification"]
        self.assertEqual(verification["only_path_delta"], ROOT_BMP_DELETE_FIXTURE_PATH)
        self.assertTrue(verification["unrelated_payloads_unchanged"])
        self.assertTrue(verification["surviving_timestamps_unchanged"])

    def test_experimental_root_bmp_ambiguous_sender_sets_global_lock_without_retry(self):
        case = self.setup_case(media="bmp", backend_options={"fail_bulk_at": 1})
        bundle = self.prepare_bmp(case)
        self.approve(case)
        with self.assertRaises(Exception) as raised:
            case[4].execute_once(confirmation_interaction=lambda _: bundle.authorization.core.confirmation_phrase)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertTrue(case[6].path.is_file())
        self.assertEqual(sum(call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
                             for call in case[3].calls), 1)
        self.assertIsNotNone(case[5].read_sender_in_flight())

    def test_changed_name_payload_nested_model_rejected(self):
        variants = ["name", "payload", "nested", "model"]
        for variant in variants:
            with self.subTest(variant=variant):
                case = self.setup_case()
                kwargs = {}
                if variant == "name":
                    case[1].rename(case[0]/"changed.txt")
                    case = (case[0],case[0]/"changed.txt",*case[2:])
                elif variant == "payload":
                    case[1].write_bytes(FIXTURE_BYTES + b"x")
                elif variant == "nested":
                    kwargs["target_path"] = "root\\nested\\" + FIXTURE_FILENAME
                else:
                    kwargs["device_model"] = "VNW-V10"
                with self.assertRaises(ValueError):
                    case[4].prepare(case[1], **kwargs)
                self.assertEqual(case[2]["captures"], [])
                self.no_send_or_claim(case)

    def test_target_already_present_rejected(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        case2 = self.setup_case()
        case2[2]["blob"] = bundle.candidate.candidate_blob
        case2[2]["fixed"] = {0x001B: bundle.candidate.transaction.ranges[0][:64],
            0x001C:b"\0"*64,0x001D:b"\0"*64,0x001E:b"\0"*64,
            0x001F:bundle.candidate.transaction.ranges[1]}
        with self.assertRaisesRegex(ValueError, "duplicate|reuse|absent|target"):
            self.prepare(case2)
        self.no_send_or_claim(case2)

    def test_elapsed_time_alone_does_not_invalidate_approved_state(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        self.approve(case)
        # H2 invalidates on state mismatch, not wall-clock age alone.
        bundle.verify_seal()
        result = case[4].execute_once(confirmation_interaction=lambda _:CONFIRMATION)
        self.assertEqual(result.completion, 0)

    def test_stale_approval_rejected(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        identity = self.approve(case)
        case[4]._owner_authorized_identity = replace(identity, candidate_blob_sha256="a"*64)
        with self.assertRaisesRegex(Exception,"stale owner"):
            case[4].execute_once(confirmation_interaction=lambda _:CONFIRMATION)
        self.no_send_or_claim(case,bundle)

    def test_approve_a_then_refresh_b_rejected_before_read_callbacks(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        self.approve(case)
        captures = len(case[2]["captures"])
        with self.assertRaisesRegex(Exception,"cannot refresh"):
            case[4].prepare(case[1])
        self.assertEqual(len(case[2]["captures"]), captures)
        self.assertIsNone(case[4].owner_authorization_identity)
        self.no_send_or_claim(case,bundle)

    def test_approve_a_then_adopt_b_rejected(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        other = self.setup_case()
        bundle_b = self.prepare(other)
        self.approve(case)
        with self.assertRaisesRegex(Exception,"cannot adopt"):
            case[4].adopt_prepared_operation(bundle_b)
        self.assertIsNone(case[4].owner_authorization_identity)
        self.no_send_or_claim(case,bundle)


    def test_reconnect_with_identical_approved_state_succeeds(self):
        case = self.setup_case(reconnect=True)
        bundle = self.prepare(case)
        self.approve(case)
        case[2]["session"] = "reconnected-session-B"
        result = case[4].execute_once(confirmation_interaction=lambda _:CONFIRMATION)
        self.assertEqual(result.completion, 0)
        self.assertEqual(case[2]["armed_generation"], 2)
        self.assertEqual(sum(call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT for call in case[3].calls), 1)

    def test_reconnect_with_changed_device_state_fails_before_claim_or_sender(self):
        case = self.setup_case(reconnect=True, equivalence_device=(0x054c, 0x001d))
        bundle = self.prepare(case)
        self.approve(case)
        case[2]["session"] = "reconnected-session-B"
        with self.assertRaisesRegex(Exception, "equivalence device|VNW-V15"):
            case[4].execute_once(confirmation_interaction=lambda _:CONFIRMATION)
        self.no_send_or_claim(case, bundle)
        self.assertIsNone(case[2].get("armed_generation"))

    def test_frozen_artifact_and_session_changes_consume_no_claim(self):
        for mutation in ("source", "candidate", "transaction", "capacity", "backup", "seal", "session"):
            with self.subTest(mutation=mutation):
                case = self.setup_case()
                bundle = self.prepare(case)
                self.approve(case)
                if mutation == "source":
                    bundle.source_path.write_bytes(b"changed")
                elif mutation == "candidate":
                    Path(bundle.candidate_artifact.path).write_bytes(b"changed")
                elif mutation == "transaction":
                    paths = list(bundle.transaction_directory.glob("*.bin"))
                    paths[0].write_bytes(b"changed")
                elif mutation == "capacity":
                    Path(bundle.capacity_artifact.path).write_bytes(b"changed")
                elif mutation == "backup":
                    (bundle.before_backup.directory / "object-01.bin").write_bytes(b"changed")
                elif mutation == "seal":
                    Path(bundle.seal_artifact.path).write_bytes(b"changed")
                else:
                    case[2]["session"] = "session-B"
                with self.assertRaises(Exception):
                    case[4].execute_once(confirmation_interaction=lambda _:CONFIRMATION)
                self.no_send_or_claim(case,bundle)

    def test_fresh_backup_drift_consumes_no_claim(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        self.approve(case)
        case[2]["blob"] = _make_root_blob(b"different\r\n")
        with self.assertRaisesRegex(Exception,"fresh pre-write backup differs"):
            case[4].execute_once(confirmation_interaction=lambda _:CONFIRMATION)
        self.no_send_or_claim(case,bundle)

    def test_bad_final_confirmation_consumes_no_claim(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        self.approve(case)
        with self.assertRaises(Exception):
            case[4].execute_once(confirmation_interaction=lambda _:"wrong")
        self.no_send_or_claim(case,bundle)

    def test_no_owner_approval_consumes_no_claim(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        with self.assertRaisesRegex(Exception,"owner approval"):
            case[4].execute_once(confirmation_interaction=lambda _:CONFIRMATION)
        self.no_send_or_claim(case,bundle)

    def test_guarded_fake_success_produces_canonical_h_report(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        identity = self.approve(case)
        with patch("infocarry.root_txt_placement.build_new_root_txt_add", side_effect=AssertionError("candidate rebuilt after approval")):
            result = case[4].execute_once(confirmation_interaction=lambda review:CONFIRMATION)
        self.assertIs(result.candidate,bundle.candidate)
        self.assertEqual(result.completion, 0)
        self.assertEqual(case[2]["timestamp_calls"],1)
        self.assertEqual(result.audit["workflow"]["sender_calls"],1)
        self.assertEqual(result.audit["execution_equivalence"]["claim"], "none_before_equivalence")
        self.assertEqual(sum(call[0]=="control_out" and call[1]==REQUEST_BEGIN_TRANSMIT for call in case[3].calls),1)
        self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
        self.assertIsNone(case[5].read_sender_in_flight())
        path = Path(result.audit["evidence_outputs"]["root"])/"01-fixture-prestage"/"placement-readback-or-backup-report.json"
        report, _ = _validate_fixture_prestage_report(path)
        self.assertEqual(report["owner_authorization_fingerprint"],identity.identity_sha256)
        self.assertEqual(report["post_placement_backup"]["blob_sha256"],bundle.candidate_blob_sha256)
        self.assertEqual(report["verification"]["exact_path_and_payload_verification"]["fixture_count_at_root"],1)
        self.assertTrue(case[2]["closed"])
        self.assertIsNone(case[4].owner_authorization_identity)

    def test_post_readback_failure_locks_globally_no_retry_no_success_report(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        self.approve(case)
        case[2]["after_bad"] = True
        with self.assertRaises(Exception) as raised:
            case[4].execute_once(confirmation_interaction=lambda _:CONFIRMATION)
        self.assertEqual(raised.exception.state,"indeterminate_after_transaction_start")
        self.assertEqual(sum(call[0]=="control_out" for call in case[3].calls),1)
        self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
        self.assertTrue(case[6].path.is_file())
        self.assertEqual(list(case[0].rglob("placement-readback-or-backup-report.json")),[])
        self.assertTrue(case[2]["closed"])

    def test_disconnected_bulk_locks_globally_no_retry(self):
        case = self.setup_case(backend_options={"fail_bulk_at":1})
        bundle = self.prepare(case)
        self.approve(case)
        with self.assertRaises(Exception) as raised:
            case[4].execute_once(confirmation_interaction=lambda _:CONFIRMATION)
        self.assertEqual(raised.exception.state,"indeterminate_after_transaction_start")
        self.assertTrue(case[6].path.is_file())
        self.assertEqual(sum(call[0]=="control_out" for call in case[3].calls),1)

    def test_nonzero_completion_cannot_produce_report(self):
        case = self.setup_case(backend_options={"completion":(2,)})
        self.prepare(case)
        self.approve(case)
        with self.assertRaises(Exception):
            case[4].execute_once(confirmation_interaction=lambda _:CONFIRMATION)
        self.assertEqual(list(case[0].rglob("placement-readback-or-backup-report.json")),[])
        self.assertEqual(sum(call[0]=="control_out" for call in case[3].calls),1)
