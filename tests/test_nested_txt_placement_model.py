"""Disposable nested TXT placement and inverse-delete replay; host fakes only."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import parse_backup_blob
from infocarry.delete_generalized import build_nested_file_delete_candidate
from infocarry.new_txt import NewTxtAddError, build_new_nested_txt_add
from infocarry.write_protocol import REQUEST_BEGIN_TRANSMIT
try:
    from test_nested_file_delete import nested_library
    from test_new_txt import _write_archive
    import test_root_txt_placement as root_placement_tests
except ModuleNotFoundError:
    from tests.test_nested_file_delete import nested_library
    from tests.test_new_txt import _write_archive
    from tests import test_root_txt_placement as root_placement_tests


class NestedTxtPlacementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.source = self.root / 'new.txt'
        self.source.write_bytes(b'disposable\r\n')
        self.fixed = {command: bytes(64) for command in range(0x1b, 0x20)}
        # Protect a survivor beyond the insertion point and retain opaque tails.
        history = bytearray(64); history[:4] = (1).to_bytes(4, 'big')
        history[8:12] = (0x300 - 0x40).to_bytes(4, 'big'); history[-1] = 0xa5
        self.fixed[0x1b] = bytes(history)
        bookmark = bytearray(64)
        bookmark[:20] = b''.join(value.to_bytes(4, 'big') for value in (0x2c0, 1, 2, 3, 4))
        bookmark[-1] = 0x5a
        self.fixed[0x1f] = bytes(bookmark)
        self.count = 0

    def archive(self, blob, fixed=None):
        self.count += 1
        return _write_archive(self.root / str(self.count), blob, self.now,
                              fixed_state=self.fixed if fixed is None else fixed)

    def build(self, blob=None, **kwargs):
        values = dict(target_directory_path=('root', 'folder'), target_directory_offset=0xc0,
                      source_template_offset=0x1c0, available_capacity_bytes=10000,
                      record_timestamp_be32=1792000123, now=self.now, max_age_seconds=None)
        values.update(kwargs)
        return build_new_nested_txt_add(self.archive(nested_library(prefix=32) if blob is None else blob),
                                        self.source, 'new.txt', **values)

    def test_all_padding_remainders_restore_all_eight_objects_and_protected_state(self):
        for size in range(8):
            self.source.write_bytes(b'x' * size)
            before = nested_library(prefix=32, text=b'y' * (size % 4))
            result = self.build(before)
            transaction = result.transaction
            after_fixed = dict(zip(range(0x1b, 0x20),
                tuple(transaction.ranges[0][i:i+64] for i in range(0, 256, 64)) + (transaction.ranges[1],)))
            post = self.archive(result.candidate_blob, after_fixed)
            delete = build_nested_file_delete_candidate(post, result.audit['target']['path'],
                int(result.audit['target']['record_offset_hex'], 16), max_age_seconds=None)
            self.assertEqual(delete.candidate_blob, before)
            self.assertEqual(delete.fixed_state.after, tuple(self.fixed.values()))
            self.assertEqual(result.audit['allocation']['alignment_padding_bytes'], -size % 4)
            self.assertTrue(result.audit['preservation']['inverse_nested_delete_exact_baseline'])
            restored = self.archive(delete.candidate_blob, dict(zip(range(0x1b, 0x20), delete.fixed_state.after)))
            baseline = self.archive(before)
            # All native objects, including opaque response/probe objects, restore byte-exactly.
            for index in range(1, 9):
                self.assertEqual((baseline / f'object-{index:02}.bin').read_bytes(),
                                 (restored / f'object-{index:02}.bin').read_bytes())

    def test_strict_cp932_authored_payload_and_frozen_timestamp(self):
        self.source.write_bytes('日本語\n'.encode('cp932'))
        result = self.build()
        parsed = parse_backup_blob(result.candidate_blob)
        target = parsed.record_at(int(result.audit['target']['record_offset_hex'], 16))
        self.assertEqual(parsed.payload_parts(target), (b'\xff' * 32, '日本語\r\n'.encode('cp932')))
        self.assertEqual(target.timestamp_be32, 1792000123)
        again = self.build()
        self.assertEqual(result.candidate_blob, again.candidate_blob)
        self.assertEqual(result.transaction, again.transaction)

    def test_wrong_parent_path_offset_template_capacity_and_timestamp_rejected(self):
        cases = [dict(target_directory_path=('root',)),
                 dict(target_directory_offset=0x200), dict(target_directory_offset=True),
                 dict(target_directory_path=('root', 'Folder')),
                 dict(source_template_offset=True), dict(source_template_offset=0xc0),
                 dict(available_capacity_bytes=None), dict(available_capacity_bytes=1),
                 dict(record_timestamp_be32=None), dict(record_timestamp_be32=True)]
        for values in cases:
            with self.subTest(values=values), self.assertRaises(NewTxtAddError):
                self.build(**values)
        for blob in (nested_library(prefix=16), nested_library(prefix=32, flag=0x20)):
            with self.assertRaises(NewTxtAddError):
                self.build(blob)

    def test_native_stem_conflict_and_unsafe_names_rejected(self):
        for filename in ('FIRST.txt', 'sub.txt', 'image.txt', '../new.txt', 'a:b.txt', 'a?.txt', '😀.txt'):
            with self.subTest(filename=filename), self.assertRaises(NewTxtAddError):
                build_new_nested_txt_add(self.archive(nested_library(prefix=32)), self.source, filename,
                    target_directory_path=('root', 'folder'), target_directory_offset=0xc0,
                    source_template_offset=0x1c0, available_capacity_bytes=10000,
                    record_timestamp_be32=1, max_age_seconds=None)


class NestedTxtGuardedPlacementTests(unittest.TestCase):
    def setup_case(self, **kwargs):
        helper = root_placement_tests.RootPlacementTests()
        case = helper.setup_case(**kwargs)
        self.addCleanup(helper.doCleanups)
        from infocarry.backup_repack import rename_existing_record
        from infocarry.delete_workflow import NESTED_TXT_DELETE_VALIDATION_PATH, NESTED_TXT_DELETE_VALIDATION_BYTES
        # Reuse the audited nested grammar with the exact approved existing path.
        blob = nested_library(prefix=32)
        blob = rename_existing_record(parse_backup_blob(blob), 0xc0, 'IC_P18_040_NESTED_20260930_01')
        blob = rename_existing_record(parse_backup_blob(blob), 0x200, 'Section-A')
        case[2]['blob'] = blob
        case[2]['fixed'] = {command: bytes(64) for command in range(0x1b, 0x20)}
        source = case[0] / NESTED_TXT_DELETE_VALIDATION_PATH.split('\\')[-1]
        source.write_bytes(NESTED_TXT_DELETE_VALIDATION_BYTES)
        return (case[0], source, *case[2:])

    def prepare(self, case, **kwargs):
        from infocarry.delete_workflow import NESTED_TXT_DELETE_VALIDATION_PATH
        values = dict(target_path=NESTED_TXT_DELETE_VALIDATION_PATH,
                      validation_placement=True, nested_validation=True)
        values.update(kwargs)
        bundle = case[4].prepare(case[1], **values)
        case[2]['bundle'] = bundle
        return bundle

    def approve(self, case):
        case[4].authorize_prepared_operation(case[4].owner_authorization_identity.approval_phrase)

    def test_exact_sealed_placement_and_inverse_delete_restore_baseline(self):
        case = self.setup_case(reconnect=True)
        baseline = case[2]['blob']
        bundle = self.prepare(case)
        self.assertEqual(case[3].calls, [])
        self.assertIsNone(case[5].read_claim(bundle.seal_sha256))
        self.assertEqual(bundle.operation_profile, 'vnw-v15-disposable-nested-txt-placement-validation-v1')
        self.approve(case)
        case[2]['session'] = 'reconnected-session'
        result = case[4].execute_once(confirmation_interaction=lambda _: bundle.authorization.core.confirmation_phrase)
        self.assertEqual(result.completion, 0)
        self.assertEqual(result.audit['workflow']['sender_calls'], 1)
        self.assertTrue(result.verification.to_dict()['exact_path_and_payload_verification']['inverse_delete_exact_baseline'])
        candidate = build_nested_file_delete_candidate(result.after_backup.directory,
            bundle.placement_target_path, int(bundle.candidate.audit_dict()['target']['record_offset_hex'], 16),
            max_age_seconds=None)
        self.assertEqual(candidate.candidate_blob, baseline)
        self.assertIsNone(case[5].read_sender_in_flight())
        self.assertFalse(case[6].path.exists())
        with self.assertRaises(Exception):
            case[4].execute_once(confirmation_interaction=lambda _: bundle.authorization.core.confirmation_phrase)
        self.assertEqual(sum(c[0] == 'control_out' and c[1] == REQUEST_BEGIN_TRANSMIT for c in case[3].calls), 1)

    def test_explicit_opt_in_wrong_model_or_target_rejects_before_capture(self):
        variants = [dict(nested_validation=False), dict(nested_validation=1),
                    dict(validation_placement=False), dict(validation_placement=1),
                    dict(placement_media='bmp'), dict(device_model='VNW-V10'),
                    dict(target_path='root\\elsewhere\\new.txt')]
        for values in variants:
            case = self.setup_case()
            with self.subTest(values=values), self.assertRaises(Exception):
                self.prepare(case, **values)
            self.assertEqual(case[2]['captures'], [])
            self.assertEqual(case[3].calls, [])

    def test_approved_bundle_tampering_and_changed_baseline_reject_before_sender(self):
        case = self.setup_case()
        bundle = self.prepare(case)
        with self.assertRaises(Exception):
            replace(bundle, nested_validation=False).verify_seal()
        self.approve(case)
        case[2]['blob'] = nested_library(prefix=32)
        with self.assertRaises(Exception):
            case[4].execute_once(confirmation_interaction=lambda _: bundle.authorization.core.confirmation_phrase)
        self.assertEqual(case[3].calls, [])
        self.assertIsNone(case[5].read_claim(bundle.seal_sha256))

    def test_ambiguous_send_sets_lock_without_retry(self):
        case = self.setup_case(backend_options={'fail_bulk_at': 1})
        bundle = self.prepare(case)
        self.approve(case)
        with self.assertRaises(Exception) as raised:
            case[4].execute_once(confirmation_interaction=lambda _: bundle.authorization.core.confirmation_phrase)
        self.assertEqual(raised.exception.state, 'indeterminate_after_transaction_start')
        self.assertTrue(case[6].path.is_file())
        self.assertIsNotNone(case[5].read_sender_in_flight())
        self.assertEqual(sum(c[0] == 'control_out' and c[1] == REQUEST_BEGIN_TRANSMIT for c in case[3].calls), 1)

    def test_nonzero_completion_or_wrong_readback_never_retries(self):
        for mode in ('completion', 'readback'):
            with self.subTest(mode=mode):
                case = self.setup_case(backend_options={'completion': (1,)} if mode == 'completion' else {})
                bundle = self.prepare(case)
                self.approve(case)
                if mode == 'readback':
                    case[2]['after_bad'] = True
                with self.assertRaises(Exception):
                    case[4].execute_once(confirmation_interaction=lambda _: bundle.authorization.core.confirmation_phrase)
                if mode == 'readback':
                    self.assertTrue(case[6].path.is_file())
                self.assertEqual(sum(c[0] == 'control_out' and c[1] == REQUEST_BEGIN_TRANSMIT for c in case[3].calls), 1)

    def test_normal_confirmation_cancel_and_frozen_source_drift_refuse_sender(self):
        for mode in ('cancel', 'source'):
            with self.subTest(mode=mode):
                case = self.setup_case()
                bundle = self.prepare(case)
                self.approve(case)
                if mode == 'source':
                    bundle.source_path.write_bytes(bundle.source_path.read_bytes() + b'x')
                with self.assertRaises(Exception):
                    case[4].execute_once(confirmation_interaction=lambda _: None if mode == 'cancel' else bundle.authorization.core.confirmation_phrase)
                self.assertEqual(case[3].calls, [])
                self.assertIsNone(case[5].read_claim(bundle.seal_sha256))
                self.assertIsNone(case[5].read_sender_in_flight())
