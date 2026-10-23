"""Exact validation route; every transport and safety database is isolated."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import patch
from infocarry.backup_format import parse_backup_blob
from infocarry.backup_repack import rename_existing_record
from infocarry.desktop import DesktopWorkflowModel
from infocarry.delete_workflow import (
    ExperimentalRootTxtDeleteFacade, build_nested_txt_validation_delete,
    NESTED_TXT_DELETE_VALIDATION_PATH as TARGET,
    NESTED_TXT_DELETE_VALIDATION_BYTES as PAYLOAD,
    NESTED_TXT_DELETE_VALIDATION_PROFILE as PROFILE,
)
from infocarry.device_library_delete_execution import DeviceLibraryDeleteService
from infocarry.delete_generalized import bind_generalized_delete_sender
from infocarry.write_protocol import REQUEST_BEGIN_TRANSMIT
try:
    from test_nested_file_delete import nested_library
    from test_new_txt import _write_archive
    import test_root_txt_placement as placement_helpers
    import test_device_library_delete_ui as ui_helpers
except ModuleNotFoundError:
    from tests.test_nested_file_delete import nested_library
    from tests.test_new_txt import _write_archive
    from tests import test_root_txt_placement as placement_helpers
    from tests import test_device_library_delete_ui as ui_helpers


def exact_nested_blob(**kwargs):
    # Swap the two TXT records' payload allocations to place the parameterized
    # target at the deeper level, without inventing a second format fixture.
    kwargs.setdefault("prefix", 32)
    blob = bytearray(nested_library(text=PAYLOAD, **kwargs))
    a, b = bytes(blob[0x1c0:0x200]), bytes(blob[0x300:0x340])
    blob[0x1c0:0x200], blob[0x300:0x340] = b, a
    from infocarry.backup_format import calculate_backup_checksum
    blob[0x1c:0x20] = bytes(4)
    blob[0x1c:0x20] = calculate_backup_checksum(blob).to_bytes(4, 'big')
    for offset, name in ((0xc0,'IC_P18_040_NESTED_20260930_01'),
                         (0x200,'Section-A'), (0x300,'IC_P18_049_DELETE_A')):
        blob = rename_existing_record(parse_backup_blob(bytes(blob)),offset,name)
    return bytes(blob)


class NestedTxtDeleteExecutionTests(unittest.TestCase):
    def setup_case(self, **kwargs):
        helper = placement_helpers.RootPlacementTests()
        self.addCleanup(helper.doCleanups)
        case = helper.setup_case(**kwargs)
        case[2]['blob'] = exact_nested_blob()
        case[2]['fixed'] = {c: bytes(64) for c in range(0x1b,0x20)}
        return (*case[:4], ExperimentalRootTxtDeleteFacade(case[4].runtime), *case[5:])

    def prepare(self, case):
        bundle = case[4].prepare(target_path=TARGET,nested_validation=True)
        case[2]['bundle'] = bundle
        return bundle

    def execute(self, case, bundle):
        case[4].authorize_prepared_operation(case[4].owner_authorization_identity.approval_phrase)
        return case[4].execute_once(confirmation_interaction=lambda _: bundle.authorization.core.confirmation_phrase)

    def data(self, **kwargs):
        case = self.setup_case(**kwargs)
        displayed = _write_archive(case[0]/'displayed',case[2]['blob'],datetime.now(timezone.utc),fixed_state=case[2]['fixed'])
        model = DesktopWorkflowModel(); model.load_backup(displayed)
        service = DeviceLibraryDeleteService(lambda:case[4].runtime,validation_target=TARGET)
        selection = service.select(model,[0x300])
        return case,model,selection,service

    def test_exact_nested_bundle_reconstructs_and_generic_sender_stays_closed(self):
        case = self.setup_case(); bundle=self.prepare(case)
        self.assertEqual(bundle.operation_profile, PROFILE)
        self.assertEqual(bundle.target_path, TARGET)
        self.assertEqual(bundle.candidate.core.target_record_offset,0x300)
        self.assertEqual(case[3].calls,[])
        self.assertIsNone(case[5].read_claim(bundle.seal_sha256))
        with self.assertRaisesRegex(Exception,'nested'):
            bind_generalized_delete_sender(bundle.authorization.core.binding,bundle.candidate.core)
        bundle.verify_seal()
        report=bundle._envelope()
        self.assertTrue(report['nested_validation'])
        self.assertEqual(report['target_profile']['prefix_bytes'],32)

    def test_success_reconnect_single_sender_claim_terminal_and_no_reuse(self):
        case=self.setup_case(reconnect=True); bundle=self.prepare(case)
        case[2]['session']='equivalent-new-session'
        result=self.execute(case,bundle)
        self.assertEqual(result.completion,0)
        self.assertEqual(result.audit['workflow']['sender_calls'],1)
        self.assertEqual(sum(x[0]=='control_out' and x[1]==REQUEST_BEGIN_TRANSMIT for x in case[3].calls),1)
        self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
        self.assertIsNone(case[5].read_sender_in_flight())
        self.assertFalse(case[6].path.exists())
        self.assertNotIn(TARGET, [r.display_name for r in self._model(result.after_backup.directory).rows()])
        with self.assertRaises(Exception): self.execute(case,bundle)
        self.assertEqual(sum(x[0]=='control_out' for x in case[3].calls),1)

    def _model(self, directory):
        model=DesktopWorkflowModel();model.load_backup(directory);return model

    def test_changed_state_scope_and_payload_do_not_enter_sender(self):
        for variant in ('path','payload','read','prefix','offset','scope','model','stale'):
            with self.subTest(variant=variant):
                case=self.setup_case()
                kwargs={'target_path':TARGET,'nested_validation':True}
                if variant=='path':kwargs['target_path']=TARGET.replace('Section-A','Section-B')
                elif variant=='payload':case[2]['blob']=exact_nested_blob().replace(PAYLOAD,b'x'*len(PAYLOAD))
                elif variant=='read':case[2]['blob']=exact_nested_blob(flag=0x20)
                elif variant=='prefix':case[2]['blob']=exact_nested_blob(prefix=16)
                elif variant=='scope':kwargs['general_txt']=True
                elif variant=='model':kwargs['device_model']='VNW-V10'
                if variant in ('offset','stale'):
                    bundle=self.prepare(case)
                    if variant=='offset':case[4]._prepared_operation=replace(bundle,candidate=replace(bundle.candidate,target_record_offset=0x1c0))
                    else:case[2]['blob']=exact_nested_blob(flag=0x20)
                    with self.assertRaises(Exception):self.execute(case,bundle)
                    self.assertIsNone(case[5].read_claim(bundle.seal_sha256))
                else:
                    with self.assertRaises(Exception):case[4].prepare(**kwargs)
                self.assertEqual(case[3].calls,[])
                self.assertIsNone(case[5].read_sender_in_flight())

    def test_ambiguous_native_nonzero_and_bad_readback_never_retry(self):
        for variant in ('disconnect','nonzero','readback'):
            options={'fail_bulk_at':1} if variant=='disconnect' else {'completion':(2,)} if variant=='nonzero' else {}
            case=self.setup_case(backend_options=options);bundle=self.prepare(case)
            if variant=='readback':case[2]['after_bad']=True
            with self.assertRaises(Exception):self.execute(case,bundle)
            self.assertEqual(sum(x[0]=='control_out' for x in case[3].calls),1)
            self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
            if variant!='nonzero':
                self.assertTrue(case[6].path.exists());self.assertIsNotNone(case[5].read_sender_in_flight())

    def test_normal_library_refuses_and_exact_validation_keeps_one_confirmation(self):
        case,model,selection,service=self.data(reconnect=True)
        self.assertTrue(selection.nested_validation)
        normal=DeviceLibraryDeleteService(lambda:case[4].runtime)
        with self.assertRaises(Exception):normal.select(model,[0x300])
        self.assertFalse(normal.execution_available(selection))
        helper=ui_helpers.DeviceLibraryDeleteUITests();self.addCleanup(helper.doCleanups)
        ui=helper.setup_ui(data_override=(case,model,selection,service))
        ui.action();ui.drain()
        self.assertEqual(len(ui.dialogs),1)
        self.assertEqual(len(ui.refreshes),1)
        self.assertIn('Delete complete',ui.statuses.get())
        self.assertNotIn(TARGET,ui.refreshes[0])

    def test_cancel_confirmation_has_no_claim_or_sender(self):
        data=self.data()
        helper=ui_helpers.DeviceLibraryDeleteUITests();self.addCleanup(helper.doCleanups)
        ui=helper.setup_ui(confirmed=False,data_override=data);ui.action();ui.drain()
        self.assertEqual(len(ui.dialogs),1);self.assertEqual(data[0][3].calls,[])
        self.assertIsNone(data[0][5].read_sender_in_flight())
