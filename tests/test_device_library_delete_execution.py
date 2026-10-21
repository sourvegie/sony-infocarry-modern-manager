"""Host-only Device Library Delete integration; USB and safety stores are fakes."""
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from infocarry.desktop import DesktopWorkflowModel, InventoryRow
from infocarry.device_library_delete_execution import (
    DeviceLibraryDeleteError, DeviceLibraryDeleteService, select_device_library_delete,
    load_verified_delete_result, delete_failure_message,
)
from infocarry.delete_workflow import (
    ROOT_TXT_DELETE_CONFIRMATION, ROOT_BMP_DELETE_FIXTURE_BYTES,
    ROOT_BMP_DELETE_FIXTURE_PATH, ROOT_BMP_DELETE_FIXTURE_SHA256,
)
from infocarry.backup_format import calculate_backup_checksum, parse_backup_blob
from infocarry.backup_repack import rename_existing_record
from infocarry.device_model_profile import VNW_V15_PROFILE
from infocarry.p18_041h_experiment import FIXTURE_PATH, FIXTURE_SHA256
from infocarry.protocol import TransferCancelledError
from infocarry.usb_access import DeviceAccessError
try:
    import test_experimental_root_txt_delete as experimental_helpers
    from test_new_txt import _write_archive
except ModuleNotFoundError:
    from tests import test_experimental_root_txt_delete as experimental_helpers
    from tests.test_new_txt import _write_archive
try:
    from test_delete_hardening import _make_root_siblings
except ModuleNotFoundError:
    from tests.test_delete_hardening import _make_root_siblings


def _bmp_delete_fixture_at_supported_offset():
    """Build the exact disposable BMP at native record offset 0x680."""
    payloads = [f"unrelated {index:02d}\r\n".encode() for index in range(24)]
    payloads[-1] = ROOT_BMP_DELETE_FIXTURE_BYTES
    parsed = parse_backup_blob(_make_root_siblings(payloads))
    metadata = bytearray(parsed.data[:parsed.header.content_start])
    content = bytearray()
    for row in parsed.records:
        if row.kind != 'file':
            continue
        prefix, payload = parsed.payload_parts(row)
        metadata[row.offset + 4:row.offset + 8] = len(content).to_bytes(4, 'big')
        if row.offset == 0x680:
            metadata[row.offset] = 0xe0
            metadata[row.offset + 1:row.offset + 4] = b'bmp'
            metadata[row.offset + 20:row.offset + 24] = (0x100).to_bytes(4, 'big')
            prefix = prefix[:16]
        content.extend(prefix + payload)
        content.extend(b'\0' * (-len(content) % 4))
    total = len(metadata) + len(content) + 4
    metadata[0x18:0x1c] = (total - 1).to_bytes(4, 'big')
    metadata[0x34:0x38] = len(content).to_bytes(4, 'big')
    metadata[0x38:0x3c] = total.to_bytes(4, 'big')
    blob = bytearray(metadata + content + b'\xff' * 4)
    blob[0x1c:0x20] = calculate_backup_checksum(blob).to_bytes(4, 'big')
    result = rename_existing_record(parse_backup_blob(bytes(blob)), 0x680,
                                    ROOT_BMP_DELETE_FIXTURE_PATH.rsplit('\\', 1)[-1][:-4])
    target = parse_backup_blob(result).record_at(0x680)
    assert parse_backup_blob(result).paths[0x680] == ('root', 'IC_P18_046_DELETE_A')
    assert parse_backup_blob(result).payload_parts(target)[1] == ROOT_BMP_DELETE_FIXTURE_BYTES
    assert ROOT_BMP_DELETE_FIXTURE_SHA256 == __import__('hashlib').sha256(ROOT_BMP_DELETE_FIXTURE_BYTES).hexdigest()
    return result


class DeviceLibraryDeleteExecutionTests(unittest.TestCase):
    def setup_case(self, **kwargs):
        helper = experimental_helpers.ExperimentalRootTxtDeleteTests('test_exact_candidate_inverse_preserves_timestamps_and_is_claim_free')
        self.addCleanup(helper.doCleanups)
        case = helper.setup_case(**kwargs)
        baseline = case[0] / 'displayed-backup'
        _write_archive(baseline, case[2]['blob'], datetime.now(timezone.utc), fixed_state=case[2]['fixed'])
        model = DesktopWorkflowModel()
        model.load_backup(baseline)
        offsets = [r.record_offset for r in model.rows() if r.display_name == FIXTURE_PATH]
        selected = select_device_library_delete(model, offsets)
        service = DeviceLibraryDeleteService(lambda: case[4].runtime)
        self.addCleanup(service.discard)
        return case, model, selected, service

    def prepare(self, data, **kwargs):
        case, model, selected, service = data
        prepared = service.prepare(selected, **kwargs)
        case[2]['bundle'] = prepared.bundle
        return prepared

    def assert_no_send(self, data):
        case = data[0]
        self.assertEqual(case[3].calls, [])
        self.assertIsNone(case[5].read_sender_in_flight())

    def test_supported_selection_and_single_readable_review(self):
        data = self.setup_case()
        prepared = self.prepare(data)
        message = prepared.confirmation_message
        for expected in ('IC_P18_041G_CLOCK_01.txt', 'VNW-V15', 'Delete', 'modifies device storage', 'Experimental'):
            self.assertIn(expected, message)
        for private in ('SHA', prepared.bundle.seal_sha256, 'claim', 'marker', 'fingerprint', '0x101b'):
            self.assertNotIn(private, message)
        self.assert_no_send(data)

    def test_selection_rejects_root_directory_nested_bmp_missing_multiple_and_general_txt(self):
        _, model, selection, _ = self.setup_case()
        row = selection.row
        variants = (
            replace(row, kind='directory', path='root'),
            replace(row, kind='directory'),
            replace(row, path='root\\nested\\IC_P18_041G_CLOCK_01'),
            replace(row, extension='bmp'),
            replace(row, path='root\\ordinary'),
            replace(row, payload_sha256='a' * 64),
            replace(row, payload_bytes=30),
            replace(row, path='root\\..'),
        )
        for variant in variants:
            with self.subTest(variant=variant), patch.object(model, 'rows', return_value=(variant,)):
                with self.assertRaises(DeviceLibraryDeleteError):
                    select_device_library_delete(model, (variant.record_offset,))
        for offsets in ((), (row.record_offset, row.record_offset), (0xffffff,)):
            with self.subTest(offsets=offsets), self.assertRaises(DeviceLibraryDeleteError):
                select_device_library_delete(model, offsets)
        with self.assertRaises(DeviceLibraryDeleteError):
            select_device_library_delete(model, (row.record_offset,), device_model='VNW-V10')

    def test_exact_disposable_bmp_uses_one_guarded_delete_and_refreshes_library(self):
        helper = experimental_helpers.ExperimentalRootTxtDeleteTests(
            'test_exact_candidate_inverse_preserves_timestamps_and_is_claim_free')
        self.addCleanup(helper.doCleanups)
        case = helper.setup_case()
        state, backend = case[2], case[3]
        state['blob'] = _bmp_delete_fixture_at_supported_offset()
        state['fixture_blob'] = state['blob']
        state['fixed'] = {command: bytes(64) for command in range(0x1b, 0x20)}
        baseline = case[0] / 'displayed-bmp-backup'
        _write_archive(baseline, state['blob'], datetime.now(timezone.utc), fixed_state=state['fixed'])
        model = DesktopWorkflowModel()
        model.load_backup(baseline)
        selection = select_device_library_delete(model, (0x680,), allow_exact_bmp=True)
        self.assertEqual(selection.row.display_name, ROOT_BMP_DELETE_FIXTURE_PATH)
        self.assertEqual(selection.row.payload_sha256, ROOT_BMP_DELETE_FIXTURE_SHA256)
        self.assertTrue(selection.validation_bmp)
        service = DeviceLibraryDeleteService(lambda: case[4].runtime)
        self.addCleanup(service.discard)
        self.assertTrue(service.execution_available(selection))
        prepared = service.prepare(selection)
        state['bundle'] = prepared.bundle
        self.assertEqual(prepared.confirmation_message.splitlines()[0],
                         'Delete IC_P18_046_DELETE_A.bmp from Sony InfoCarry VNW-V15?')
        for visible in ('Operation: Delete', 'Deletion modifies device storage', 'Backup is not undo'):
            self.assertIn(visible, prepared.confirmation_message)
        for internal in ('SHA-256', prepared.bundle.seal_sha256, 'claim', 'marker', '0x101b'):
            self.assertNotIn(internal, prepared.confirmation_message)
        self.assertEqual(prepared.bundle.operation_profile,
                         'vnw-v15-exact-disposable-root-bmp-delete-validation-v1')
        self.assertEqual(prepared.bundle.candidate.core.target_record_offset, 0x680)
        result = service.execute_once(prepared, confirmed=True)
        self.assertEqual(result.completion, 0)
        self.assertEqual(result.audit['workflow']['sender_calls'], 1)
        self.assertEqual(sum(call[0] == 'control_out' for call in backend.calls), 1)
        self.assertIsNone(case[5].read_sender_in_flight())
        self.assertIsNotNone(case[5].read_claim(prepared.bundle.seal_sha256))
        self.assertIsNone(case[6].read(VNW_V15_PROFILE.lock_key))
        summary = load_verified_delete_result(model, result)
        self.assertEqual(summary.directory, result.after_backup.directory)
        self.assertNotIn(ROOT_BMP_DELETE_FIXTURE_PATH, [row.display_name for row in model.rows()])
        self.assertEqual(model.state.source_blob_sha256, prepared.bundle.candidate_blob_sha256)
        verification = result.verification.to_dict()['exact_path_and_payload_verification']
        self.assertEqual(verification['only_removed_path'], ROOT_BMP_DELETE_FIXTURE_PATH)
        self.assertTrue(verification['surviving_timestamps_preserved'])
        self.assertTrue(verification['unrelated_payloads_unchanged'])

    def test_bmp_disconnect_after_sender_start_is_single_attempt_and_keeps_global_lock(self):
        helper = experimental_helpers.ExperimentalRootTxtDeleteTests(
            'test_exact_candidate_inverse_preserves_timestamps_and_is_claim_free')
        self.addCleanup(helper.doCleanups)
        case = helper.setup_case(backend_options={'fail_bulk_at': 2})
        state, backend = case[2], case[3]
        state['blob'] = _bmp_delete_fixture_at_supported_offset()
        state['fixed'] = {command: bytes(64) for command in range(0x1b, 0x20)}
        baseline = case[0] / 'displayed-bmp-disconnect-backup'
        _write_archive(baseline, state['blob'], datetime.now(timezone.utc), fixed_state=state['fixed'])
        model = DesktopWorkflowModel(); model.load_backup(baseline)
        selection = select_device_library_delete(model, (0x680,), allow_exact_bmp=True)
        service = DeviceLibraryDeleteService(lambda: case[4].runtime)
        self.addCleanup(service.discard)
        prepared = service.prepare(selection)
        state['bundle'] = prepared.bundle
        with self.assertRaises(Exception) as error:
            service.execute_once(prepared, confirmed=True)
        self.assertEqual(error.exception.state, 'indeterminate_after_transaction_start')
        self.assertEqual(sum(call[0] == 'control_out' for call in backend.calls), 1)
        self.assertIsNotNone(case[5].read_claim(prepared.bundle.seal_sha256))
        self.assertIsNotNone(case[5].read_sender_in_flight())
        self.assertIsNotNone(case[6].read(VNW_V15_PROFILE.lock_key))
        self.assertIn(ROOT_BMP_DELETE_FIXTURE_PATH, [row.display_name for row in model.rows()])

    def test_exact_bmp_ui_admission_rejects_changed_payload_path_offset_or_read_state(self):
        data = self.setup_case()
        _, model, _, _ = data
        from infocarry.desktop import InventoryRow
        row = InventoryRow(record_offset=0x680, path='root\\IC_P18_046_DELETE_A', kind='file', extension='bmp',
            payload_bytes=len(ROOT_BMP_DELETE_FIXTURE_BYTES), payload_sha256=ROOT_BMP_DELETE_FIXTURE_SHA256,
            read_state='unread')
        for changed in (replace(row, payload_sha256='0' * 64), replace(row, record_offset=0x6c0),
                        replace(row, path='root\\nested\\IC_P18_046_DELETE_A.bmp'),
                        replace(row, read_state='read')):
            with patch.object(model, 'rows', return_value=(changed,)), self.assertRaises(DeviceLibraryDeleteError):
                select_device_library_delete(model, (changed.record_offset,), allow_exact_bmp=True)

    def test_ambiguous_path_and_offset_rejected(self):
        _, model, selection, _ = self.setup_case()
        for duplicate in (selection.row, replace(selection.row, record_offset=selection.row.record_offset+64)):
            with patch.object(model, 'rows', return_value=(selection.row, duplicate)):
                with self.assertRaises(DeviceLibraryDeleteError):
                    select_device_library_delete(model, (selection.row.record_offset,))

    def test_forged_selection_rejected_before_runtime(self):
        _, _, selection, _ = self.setup_case()
        calls = []
        service = DeviceLibraryDeleteService(lambda: calls.append(True))
        for changed in (replace(selection, baseline_blob_sha256='a'*64),
                        replace(selection, row=replace(selection.row, path='root\\another'))):
            with self.assertRaises(DeviceLibraryDeleteError):
                service.prepare(changed)
        self.assertEqual(calls, [])

    def test_changed_selected_device_state_is_not_adopted(self):
        data = self.setup_case()
        data[0][2]['blob'] = data[0][2]['original_blob']
        with self.assertRaises(Exception):
            self.prepare(data)
        self.assert_no_send(data)

    def test_auxiliary_drift_between_display_and_fresh_backup_invalidates_review(self):
        data = self.setup_case()
        raw = bytearray(64)
        from infocarry.backup_format import parse_backup_blob
        parsed = parse_backup_blob(data[0][2]['blob'])
        survivor = next(r for r in parsed.records if r.kind == 'file' and r.offset != data[2].row.record_offset)
        raw[:4] = (1).to_bytes(4, 'big')
        raw[8:12] = (survivor.offset - parsed.header.metadata_start).to_bytes(4, 'big')
        data[0][2]['fixed'][0x001b] = bytes(raw)
        with self.assertRaisesRegex(DeviceLibraryDeleteError, 'changed'):
            self.prepare(data)
        self.assert_no_send(data)

    def test_cancel_before_runtime(self):
        data = self.setup_case()
        with self.assertRaises(TransferCancelledError):
            self.prepare(data, cancelled=lambda: True)
        self.assert_no_send(data)
        self.assertTrue(data[0][2]['closed'] is False)

    def test_cancel_during_backup_preserves_archive_and_never_authorizes(self):
        data = self.setup_case()
        calls = []
        def cancelled():
            calls.append(True)
            return len(calls) >= 3
        with self.assertRaises(TransferCancelledError):
            self.prepare(data, cancelled=cancelled)
        self.assert_no_send(data)
        self.assertTrue(list(data[0][0].rglob('manifest.json')))
        self.assertTrue(data[0][2]['closed'])

    def test_preparation_progress_and_cancel_confirmation(self):
        data = self.setup_case()
        labels = []
        prepared = self.prepare(data, progress=lambda label, *_: labels.append(label))
        self.assertIn('Preparing backup', labels)
        self.assertIn('Validating operation', labels)
        self.assertIsNone(data[3].execute_once(prepared, confirmed=False))
        self.assert_no_send(data)
        self.assertIsNone(data[0][5].read_claim(prepared.bundle.seal_sha256))
        with self.assertRaises(DeviceLibraryDeleteError):
            data[3].execute_once(prepared, confirmed=True)

    def test_wrong_prepared_operation_and_nonboolean_approval_rejected(self):
        for mode in ('other', 'nonboolean'):
            data = self.setup_case()
            prepared = self.prepare(data)
            with self.assertRaises(DeviceLibraryDeleteError):
                data[3].execute_once(replace(prepared) if mode == 'other' else prepared,
                                     confirmed='yes' if mode == 'nonboolean' else True)
            self.assert_no_send(data)

    def test_cannot_refresh_an_existing_review(self):
        data = self.setup_case()
        self.prepare(data)
        captures = len(data[0][2]['captures'])
        with self.assertRaises(DeviceLibraryDeleteError):
            self.prepare(data)
        self.assertEqual(captures, len(data[0][2]['captures']))
        self.assert_no_send(data)

    def test_changed_frozen_candidate_rejected_before_claim(self):
        data = self.setup_case()
        prepared = self.prepare(data)
        changed = replace(prepared.bundle.candidate, candidate_blob=prepared.bundle.candidate.candidate_blob + b'x')
        object.__setattr__(prepared.bundle, 'candidate', changed)
        with self.assertRaises(Exception):
            data[3].execute_once(prepared, confirmed=True)
        self.assert_no_send(data)
        self.assertIsNone(data[0][5].read_claim(prepared.bundle.seal_sha256))

    def test_changed_owner_identity_is_rejected(self):
        data = self.setup_case()
        prepared = self.prepare(data)
        object.__setattr__(prepared, 'owner_identity', replace(prepared.owner_identity, candidate_blob_sha256='a'*64))
        with self.assertRaises(DeviceLibraryDeleteError):
            data[3].execute_once(prepared, confirmed=True)
        self.assert_no_send(data)

    def test_execution_drift_rejected_before_claim(self):
        data = self.setup_case()
        prepared = self.prepare(data)
        data[0][2]['blob'] = data[0][2]['original_blob']
        with self.assertRaises(Exception):
            data[3].execute_once(prepared, confirmed=True)
        self.assert_no_send(data)
        self.assertIsNone(data[0][5].read_claim(prepared.bundle.seal_sha256))

    def test_one_sender_complete_verification_and_library_refresh(self):
        data = self.setup_case(reconnect=True)
        prepared = self.prepare(data)
        data[0][2]['session'] = 'reconnected-B'
        labels = []
        result = data[3].execute_once(prepared, confirmed=True, progress=lambda label, *_: labels.append(label))
        self.assertEqual(result.completion, 0)
        self.assertEqual(result.audit['workflow']['sender_calls'], 1)
        self.assertIn('Write complete', labels)
        self.assertEqual(sum(c[0] == 'control_out' for c in data[0][3].calls), 1)
        self.assertIsNone(data[0][5].read_sender_in_flight())
        self.assertIsNotNone(data[0][5].read_claim(prepared.bundle.seal_sha256))
        self.assertIsNone(data[0][6].read(VNW_V15_PROFILE.lock_key))
        summary = load_verified_delete_result(data[1], result)
        self.assertEqual(summary.directory, result.after_backup.directory)
        self.assertNotIn(FIXTURE_PATH, [r.display_name for r in data[1].rows()])
        self.assertEqual(data[1].state.source_blob_sha256, prepared.bundle.candidate_blob_sha256)
        calls = len(data[0][3].calls)
        with self.assertRaises(DeviceLibraryDeleteError):
            data[3].execute_once(prepared, confirmed=True)
        self.assertEqual(calls, len(data[0][3].calls))

    def test_disconnect_and_nonzero_never_retry(self):
        for options, state in (({'fail_bulk_at': 2}, 'indeterminate_after_transaction_start'),
                               ({'completion': (2,)}, 'failed')):
            data = self.setup_case(backend_options=options)
            prepared = self.prepare(data)
            with self.assertRaises(Exception) as error:
                data[3].execute_once(prepared, confirmed=True)
            self.assertEqual(error.exception.state, state)
            self.assertEqual(sum(c[0]=='control_out' for c in data[0][3].calls), 1)
            self.assertIsNotNone(data[0][5].read_claim(prepared.bundle.seal_sha256))
            self.assertEqual(data[0][6].read(VNW_V15_PROFILE.lock_key) is not None, state.startswith('indeterminate'))
            self.assertEqual(any(r.display_name == FIXTURE_PATH for r in data[1].rows()), True)
            self.assertIn('retry', delete_failure_message(error.exception))

    def test_bad_readback_and_missing_post_backup_do_not_refresh(self):
        data = self.setup_case()
        prepared = self.prepare(data)
        data[0][2]['bad_delete_readback'] = True
        with self.assertRaises(Exception) as error:
            data[3].execute_once(prepared, confirmed=True)
        self.assertTrue(data[0][6].read(VNW_V15_PROFILE.lock_key).locked)
        self.assertIn('uncertain', delete_failure_message(error.exception))
        self.assertTrue(any(r.display_name == FIXTURE_PATH for r in data[1].rows()))
        with self.assertRaises(DeviceLibraryDeleteError):
            load_verified_delete_result(data[1], object())

    def test_corrupted_result_cannot_remove_displayed_file(self):
        for mutation in ('completion', 'audit', 'after'):
            data = self.setup_case()
            prepared = self.prepare(data)
            result = data[3].execute_once(prepared, confirmed=True)
            if mutation == 'completion':
                result = replace(result, completion=True)
            elif mutation == 'audit':
                result = replace(result, audit={**result.audit, 'state': 'failed'})
            else:
                dynamic = result.after_backup.directory / result.after_backup.object_filename('0x8004:backup-blob')
                dynamic.write_bytes(dynamic.read_bytes() + b'x')
            with self.assertRaises(Exception):
                load_verified_delete_result(data[1], result)
            self.assertTrue(any(r.display_name == FIXTURE_PATH for r in data[1].rows()))

    def test_complete_post_backup_failure_retains_marker_and_global_lock(self):
        data = self.setup_case()
        prepared = self.prepare(data)
        original = data[0][4].runtime.capture
        def broken_capture(destination, **kwargs):
            if destination.name == 'backup-after-0001':
                raise OSError('disconnected during readback')
            original(destination, **kwargs)
        object.__setattr__(prepared.bundle.runtime, 'capture', broken_capture)
        with self.assertRaises(Exception) as error:
            data[3].execute_once(prepared, confirmed=True)
        self.assertEqual(error.exception.state, 'indeterminate_after_transaction_start')
        self.assertIsNotNone(data[0][5].read_sender_in_flight())
        self.assertTrue(data[0][6].read(VNW_V15_PROFILE.lock_key).locked)
        self.assertEqual(sum(c[0]=='control_out' for c in data[0][3].calls), 1)
        self.assertTrue(any(r.display_name == FIXTURE_PATH for r in data[1].rows()))

    def test_global_lock_blocks_new_preparation_before_device_callbacks(self):
        data = self.setup_case()
        from infocarry.indeterminate_write_lock import PersistentIndeterminateWriteLock
        lock = data[0][6]
        lock.record_indeterminate(model_key=VNW_V15_PROFILE.lock_key, incident_id='prior-incident', attempt_id='prior-attempt', reason='test', evidence_root=str(data[0][0]))
        captures = len(data[0][2]['captures'])
        with self.assertRaises(Exception):
            self.prepare(data)
        self.assertEqual(captures, len(data[0][2]['captures']))
        self.assert_no_send(data)
        self.assertTrue(lock.read(VNW_V15_PROFILE.lock_key).locked)

    def test_closed_preparation_never_opens_runtime(self):
        data = self.setup_case()
        data[3].close_preparation()
        with self.assertRaises(TransferCancelledError):
            self.prepare(data)
        self.assert_no_send(data)

    def test_friendly_failure_categories(self):
        self.assertIn('disconnected', delete_failure_message(DeviceAccessError('test')))
        self.assertIn('backup failed', delete_failure_message(OSError('test')))
        for stage, term in (('write', 'transfer failed'), ('verification', 'verification failed'),
                            ('approval', 'invalidated'), ('write_guard', 'write-safety')):
            self.assertIn(term, delete_failure_message(DeviceLibraryDeleteError('test', stage=stage)))


if __name__ == '__main__':
    unittest.main()
