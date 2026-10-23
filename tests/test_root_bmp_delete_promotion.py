"""Promoted BMP Device Library workflow, using temporary safety stores and USB fakes."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import patch

from infocarry.backup_format import parse_backup_blob
from infocarry.backup_repack import rename_existing_record
from infocarry.desktop import DesktopWorkflowModel
from infocarry.device_library_delete_execution import DeviceLibraryDeleteService, load_verified_delete_result
from infocarry.delete_workflow import ROOT_BMP_DELETE_LIVE_PROFILE, root_bmp_delete_execution_supported
from infocarry.delete_generalized import build_root_bmp_delete_candidate
from infocarry.protocol import TransferCancelledError
from test_root_bmp_delete_model import root_bitmap_library
from test_new_txt import _write_archive
from test_bitmap import make_monochrome_bmp
import test_experimental_root_txt_delete as helpers
import test_device_library_delete_ui as ui_helpers


class RootBmpDeletePromotionTests(unittest.TestCase):
    def case(self, *, index=1, name='資料_01', top_down=True, **options):
        helper = helpers.ExperimentalRootTxtDeleteTests('test_exact_candidate_inverse_preserves_timestamps_and_is_claim_free')
        self.addCleanup(helper.doCleanups)
        case = helper.setup_case(**options)
        payload = bytearray(make_monochrome_bmp(237, 320, top_down=top_down))
        payload[-32:] = bytes(range(32))  # ordinary content, not either physical fixture
        blob, offset = root_bitmap_library(index=index, payload=bytes(payload))
        blob = rename_existing_record(parse_backup_blob(blob), offset, name)
        case[2]['blob'] = blob; case[2]['fixture_blob'] = blob
        case[2]['fixed'] = {c: bytes(64) for c in range(0x1b, 0x20)}
        model = DesktopWorkflowModel()
        model.load_backup(_write_archive(case[0]/'displayed',blob,datetime.now(timezone.utc),fixed_state=case[2]['fixed']))
        service = DeviceLibraryDeleteService(lambda: case[4].runtime)
        self.addCleanup(service.discard)
        selection = service.select(model, [offset])
        return case, model, selection, service

    def prepare(self, data):
        case, model, selection, service = data
        prepared = service.prepare(selection)
        case[2]['bundle'] = prepared.bundle
        return prepared

    def test_first_middle_last_bmp_guarded_execution_readback_and_refresh(self):
        for index in range(3):
            with self.subTest(index=index):
                data=self.case(index=index, top_down=bool(index%2));case,model,selection,service=data
                self.assertTrue(selection.general_bmp)
                self.assertTrue(service.execution_available(selection))
                prepared=self.prepare(data);bundle=prepared.bundle
                self.assertEqual(bundle.operation_profile,ROOT_BMP_DELETE_LIVE_PROFILE)
                self.assertFalse(bundle.validation_bmp_only)
                self.assertEqual(bundle._envelope()['capability_status'],'experimental_unread_root_bmp')
                for internal in ('SHA',bundle.seal_sha256,'claim','marker','fingerprint','0x101b'):
                    self.assertNotIn(internal,prepared.confirmation_message)
                self.assertIsNone(case[5].read_claim(bundle.seal_sha256))
                result=service.execute_once(prepared,confirmed=True)
                self.assertEqual(result.completion,0)
                self.assertEqual(result.audit['workflow']['sender_calls'],1)
                self.assertFalse(result.audit['workflow']['automatic_retry_allowed'])
                self.assertEqual(sum(c[0]=='control_out' for c in case[3].calls),1)
                self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
                self.assertIsNone(case[5].read_sender_in_flight())
                self.assertIsNone(case[6].read())
                load_verified_delete_result(model,result)
                self.assertNotIn(selection.row.display_name,[r.display_name for r in model.rows()])
                self.assertEqual(model.state.source_blob_sha256,bundle.candidate_blob_sha256)
                with self.assertRaises(ValueError):service.execute_once(prepared,confirmed=True)

    def test_approval_binds_target_payload_scope_and_candidate(self):
        data=self.case();prepared=self.prepare(data);bundle=prepared.bundle
        for candidate in (replace(bundle.candidate,target_path='root\\other.bmp'),
                          replace(bundle.candidate,target_record_offset=0xc0),
                          replace(bundle.candidate,candidate_blob=b'wrong'),
                          replace(bundle.candidate,general_bmp=False)):
            with self.subTest(candidate=candidate.target_path),self.assertRaises((ValueError,RuntimeError)):
                replace(bundle,candidate=candidate).verify_seal()
        with self.assertRaises(ValueError):replace(bundle,validation_bmp_only=True).verify_seal()
        bundle.source_path.write_bytes(b'changed')
        with self.assertRaises(ValueError):bundle.verify_seal()
        self.assertEqual(data[0][3].calls,[])

    def test_cancel_before_sender_has_no_claim_marker_or_send(self):
        data=self.case();prepared=self.prepare(data)
        self.assertIsNone(data[3].execute_once(prepared,confirmed=False))
        self.assertIsNone(data[0][5].read_claim(prepared.bundle.seal_sha256))
        self.assertIsNone(data[0][5].read_sender_in_flight());self.assertEqual(data[0][3].calls,[])
        data=self.case()
        with self.assertRaises(TransferCancelledError):data[3].prepare(data[2],cancelled=lambda:True)
        self.assertEqual(data[0][3].calls,[])

    def test_reconnect_equivalent_state_executes_but_changed_device_rejects(self):
        data=self.case(reconnect=True);prepared=self.prepare(data)
        result=data[3].execute_once(prepared,confirmed=True)
        self.assertEqual(result.completion,0)
        data=self.case();prepared=self.prepare(data)
        data[0][2]['blob']=rename_existing_record(parse_backup_blob(data[0][2]['blob']),0xc0,'changed')
        with self.assertRaises(Exception):data[3].execute_once(prepared,confirmed=True)
        self.assertEqual(data[0][3].calls,[])
        self.assertIsNone(data[0][5].read_claim(prepared.bundle.seal_sha256))

    def test_nonzero_and_disconnection_keep_existing_terminal_policy_without_retry(self):
        for options in ({'completion':(1,)},{'fail_bulk_at':1}):
            data=self.case(backend_options=options);prepared=self.prepare(data)
            with self.subTest(options=options),self.assertRaises(Exception):
                data[3].execute_once(prepared,confirmed=True)
            self.assertEqual(sum(c[0]=='control_out' for c in data[0][3].calls),1)
            self.assertIsNotNone(data[0][5].read_claim(prepared.bundle.seal_sha256))
            if 'fail_bulk_at' in options:
                self.assertIsNotNone(data[0][5].read_sender_in_flight())
                self.assertTrue(data[0][6].read().locked)
            else:
                self.assertIsNone(data[0][5].read_sender_in_flight())
                self.assertIsNone(data[0][6].read())

    def test_read_prefix32_and_modified_audit_cannot_promote(self):
        data=self.case();backup=data[1].state.backup_directory
        for flag,prefix in ((0x20,16),(0xe0,32)):
            blob,offset=root_bitmap_library(flag=flag,prefix_bytes=prefix)
            archive=_write_archive(data[0][0]/f'unsupported-{flag}-{prefix}',blob,datetime.now(timezone.utc),fixed_state=data[0][2]['fixed'])
            path='root\\'+parse_backup_blob(blob).record_at(offset).name+'.bmp'
            core=build_root_bmp_delete_candidate(archive,path,offset,max_age_seconds=None)
            core.audit['execution_available']=True
            self.assertFalse(root_bmp_delete_execution_supported(core))
        prepared=self.prepare(data)
        poisoned=replace(prepared.bundle.candidate.core,candidate_model=replace(prepared.bundle.candidate.core.candidate_model,candidate_blob=b'wrong'))
        self.assertFalse(root_bmp_delete_execution_supported(poisoned))

    def test_actual_ttk_callbacks_bmp_confirm_cancel_failure_and_refresh(self):
        harness=ui_helpers.DeviceLibraryDeleteUITests();self.addCleanup(harness.doCleanups)
        for confirm in (False,True):
            data=self.case()
            ui=harness.setup_ui(confirmed=confirm,data_override=data)
            ui.action();ui.drain()
            self.assertEqual(len(ui.dialogs),1)
            self.assertIn(data[2].filename,ui.dialogs[0])
            self.assertEqual(len(ui.refreshes),int(confirm))
            self.assertIn('Delete complete' if confirm else 'cancelled',ui.statuses.get())
        data=self.case(backend_options={'fail_bulk_at':1})
        ui=harness.setup_ui(data_override=data);ui.action();ui.drain()
        self.assertEqual(len(ui.dialogs),1);self.assertEqual(ui.refreshes,[])
        self.assertIn('uncertain',ui.statuses.get())


if __name__=='__main__':unittest.main()
