"""Conservative nested TXT admission; all sends and stores are isolated fakes."""
from dataclasses import replace
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from infocarry.backup_format import parse_backup_blob
from infocarry.backup_duplicate import add_file_from_template
from infocarry.backup_repack import rename_existing_record
from infocarry.desktop import DesktopWorkflowModel
from infocarry.delete_workflow import build_nested_txt_delete, NESTED_TXT_DELETE_LIVE_PROFILE, NESTED_TXT_DELETE_NATIVE_PREFIX
from infocarry.delete_generalized import bind_generalized_delete_sender
from infocarry.device_library_delete_execution import DeviceLibraryDeleteService, load_verified_delete_result
import test_nested_txt_delete_execution as nested_helpers
from test_nested_txt_delete_execution import exact_nested_blob
from test_root_bmp_delete_model import _checksum
from test_new_txt import _write_archive
import test_device_library_delete_ui as ui_helpers


def ordinary_nested_blob(payload=b'ordinary nested text\r\n', **kwargs):
    blob = exact_nested_blob(text=payload, **kwargs)
    parsed = parse_backup_blob(blob)
    if parsed.record_at(0x300).payload_prefix_length == 32:
        data = bytearray(blob)
        start = parsed.header.content_start + parsed.record_at(0x300).field_04_be32
        data[start:start+32] = NESTED_TXT_DELETE_NATIVE_PREFIX
        blob = _checksum(data); parsed = parse_backup_blob(blob)
    # Add the surviving sibling before the trailing parent marker.
    blob = add_file_from_template(parsed, 0x200, 0x300, 'sibling', b'keep\r\n',
                                  timestamp_be32=1792000010, fresh_new_allocation=True)
    blob = rename_existing_record(parse_backup_blob(blob), 0x300, '資料_01')
    return blob


class NestedTxtPromotionTests(unittest.TestCase):
    def case(self, *, blob=None, fixed=None, **options):
        helper = nested_helpers.NestedTxtDeleteExecutionTests()
        self.addCleanup(helper.doCleanups)
        case = helper.setup_case(**options)
        case[2]['blob'] = ordinary_nested_blob() if blob is None else blob
        if fixed is not None: case[2]['fixed'] = fixed
        model = DesktopWorkflowModel()
        model.load_backup(_write_archive(case[0]/'displayed', case[2]['blob'], datetime.now(timezone.utc),
                                         fixed_state=case[2]['fixed']))
        service = DeviceLibraryDeleteService(lambda: case[4].runtime)
        self.addCleanup(service.discard)
        return case, model, service

    def data(self, *, offset=0x300, **options):
        case, model, service = self.case(**options)
        return case, model, service.select(model, [offset]), service

    def prepare(self, data):
        prepared = data[3].prepare(data[2]); data[0][2]['bundle'] = prepared.bundle
        return prepared

    def test_all_alignment_remainders_native_name_guarded_success_and_refresh(self):
        for n in range(4):
            data = self.data(blob=ordinary_nested_blob(b'x'*(32+n)))
            case, model, selection, service = data
            self.assertTrue(selection.general_nested_txt)
            self.assertTrue(service.execution_available(selection))
            prepared = self.prepare(data); bundle = prepared.bundle
            self.assertEqual(bundle.operation_profile, NESTED_TXT_DELETE_LIVE_PROFILE)
            self.assertEqual(bundle._envelope()['capability_status'], 'experimental_unread_nested_txt')
            self.assertIn(selection.row.display_name, prepared.confirmation_message)
            for internal in ('SHA', 'fingerprint', 'claim', 'marker', bundle.seal_sha256):
                self.assertNotIn(internal, prepared.confirmation_message)
            self.assertIsNone(case[5].read_claim(bundle.seal_sha256))
            with self.assertRaisesRegex(Exception, 'nested'):
                bind_generalized_delete_sender(bundle.authorization.core.binding, bundle.candidate.core)
            result = service.execute_once(prepared, confirmed=True)
            self.assertEqual(result.completion, 0)
            self.assertEqual(result.audit['workflow']['sender_calls'], 1)
            self.assertEqual(sum(c[0]=='control_out' for c in case[3].calls), 1)
            self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
            self.assertIsNone(case[5].read_sender_in_flight()); self.assertIsNone(case[6].read())
            load_verified_delete_result(model, result)
            self.assertNotIn(selection.row.display_name, [r.display_name for r in model.rows()])
            self.assertTrue(any(r.display_name.endswith('sibling.txt') for r in model.rows()))
            with self.assertRaises(Exception): service.execute_once(prepared, confirmed=True)

    def test_profile_refusals_before_runtime(self):
        variants = [ordinary_nested_blob(flag=0x20), ordinary_nested_blob(prefix=16), exact_nested_blob()]
        baseline = ordinary_nested_blob()
        for offset, value in ((0x300+16, b'\0'*4), (0x300+20,(0x10200).to_bytes(4,'big')),
                              (0x200+24,b'bad/name'+bytes(32)),
                              (0x340+24,'資料_01'.encode('cp932')+bytes(33))):
            blob = bytearray(baseline); blob[offset:offset+len(value)] = value; variants.append(_checksum(blob))
        parsed=parse_backup_blob(baseline);target=parsed.record_at(0x300)
        blob=bytearray(baseline);blob[parsed.header.content_start+target.field_04_be32]^=1;variants.append(_checksum(blob))
        for blob in variants:
            case, model, service = self.case(blob=blob)
            try: selection = service.select(model,[0x300])
            except ValueError: continue
            self.assertFalse(service.execution_available(selection))
            with patch.object(service,'_runtime_factory',side_effect=AssertionError('runtime opened')):
                with self.assertRaises(ValueError): service.prepare(selection)
            self.assertEqual(case[3].calls,[])
        case,model,service=self.case()
        for offsets, model_name in (([0x300,0x340],'VNW-V15'),([0x200],'VNW-V15'),([0x240],'VNW-V15'),([0x300],'VNW-V10')):
            with self.assertRaises(ValueError): service.select(model,offsets,device_model=model_name)

    def test_frozen_scope_tampering_reconnect_and_changed_state(self):
        data=self.data(reconnect=True); prepared=self.prepare(data); bundle=prepared.bundle
        for candidate in (replace(bundle.candidate,general_nested_txt=False),
                          replace(bundle.candidate,nested_validation=True),
                          replace(bundle.candidate,general_nested_txt=1),
                          replace(bundle.candidate,target_path='root\\other.txt'),
                          replace(bundle.candidate,target_extension='bmp'),
                          replace(bundle.candidate,target_record_offset=0x340)):
            with self.assertRaises(Exception): replace(bundle,candidate=candidate).verify_seal()
        result=data[3].execute_once(prepared,confirmed=True)
        self.assertEqual(result.completion,0)
        data=self.data(); prepared=self.prepare(data)
        data[0][2]['blob']=rename_existing_record(parse_backup_blob(data[0][2]['blob']),0x340,'changed')
        with self.assertRaises(Exception):data[3].execute_once(prepared,confirmed=True)
        self.assertEqual(data[0][3].calls,[])

    def test_ui_one_confirmation_cancel_and_verified_refresh(self):
        for confirmed in (False, True):
            data=self.data();helper=ui_helpers.DeviceLibraryDeleteUITests();self.addCleanup(helper.doCleanups)
            ui=helper.setup_ui(confirmed=confirmed,data_override=data);ui.action();ui.drain()
            self.assertEqual(len(ui.dialogs),1)
            self.assertEqual(len(ui.refreshes),int(confirmed))
            self.assertEqual(sum(c[0]=='control_out' for c in data[0][3].calls),int(confirmed))
            self.assertIsNone(data[0][5].read_sender_in_flight())

    def test_indeterminate_nonzero_and_bad_readback_have_one_sender_no_retry(self):
        for options in ({'fail_bulk_at':1},{'completion':(2,)},{}):
            data=self.data(backend_options=options);prepared=self.prepare(data)
            if not options:data[0][2]['after_bad']=True
            with self.assertRaises(Exception):data[3].execute_once(prepared,confirmed=True)
            self.assertEqual(sum(c[0]=='control_out' for c in data[0][3].calls),1)
            self.assertIsNotNone(data[0][5].read_claim(prepared.bundle.seal_sha256))

    def test_exact_validation_session_cannot_adopt_ordinary_nested_scope(self):
        data=self.data();service=DeviceLibraryDeleteService(lambda:data[0][4].runtime,
            validation_target='root\\IC_P18_043_DELETE_A.txt')
        self.assertFalse(service.execution_available(data[2]))
        with self.assertRaises(ValueError):service.prepare(data[2])
        self.assertEqual(data[0][3].calls,[])

    def test_sibling_order_first_last_and_native_prefix_substitution(self):
        blob=ordinary_nested_blob()
        swapped=bytearray(blob);swapped[0x300:0x340],swapped[0x340:0x380]=blob[0x340:0x380],blob[0x300:0x340]
        data=self.data(blob=_checksum(swapped),offset=0x340)
        self.assertTrue(data[3].execution_available(data[2]))
        prepared=self.prepare(data);result=data[3].execute_once(prepared,confirmed=True)
        self.assertEqual(result.completion,0)
        parsed=parse_backup_blob(blob);start=parsed.header.content_start+parsed.record_at(0x300).field_04_be32
        changed=bytearray(blob);changed[start:start+32]=b'\xff'*32
        data=self.data(blob=_checksum(changed))
        self.assertFalse(data[3].execution_available(data[2]))
        self.assertEqual(data[0][3].calls,[])

    def test_referenced_target_and_active_marks_refuse_before_runtime(self):
        for command in range(0x1b,0x20):
            fixed={c:bytes(64) for c in range(0x1b,0x20)};raw=bytearray(64)
            if command==0x1f:
                raw[:4]=(0x2c0).to_bytes(4,'big');raw[8:12]=(0x80000000).to_bytes(4,'big')
            else:
                raw[:4]=(1).to_bytes(4,'big');raw[8:12]=(0x2c0).to_bytes(4,'big')
            fixed[command]=bytes(raw)
            data=self.data(fixed=fixed)
            self.assertFalse(data[3].execution_available(data[2]))
            with patch.object(data[3],'_runtime_factory',side_effect=AssertionError('runtime opened')):
                with self.assertRaises(ValueError):data[3].prepare(data[2])
            self.assertEqual(data[0][3].calls,[])

    def test_unrelated_survivor_overlap_and_alignment_fail_before_runtime(self):
        baseline=ordinary_nested_blob();parsed=parse_backup_blob(baseline)
        for pointer in (parsed.record_at(0x1c0).field_04_be32,1):
            changed=bytearray(baseline);changed[0x104:0x108]=pointer.to_bytes(4,'big')
            data=self.data(blob=_checksum(changed))
            self.assertFalse(data[3].execution_available(data[2]))
            with patch.object(data[3],'_runtime_factory',side_effect=AssertionError('runtime opened')):
                with self.assertRaises(ValueError):data[3].prepare(data[2])
            with self.assertRaises(ValueError):
                build_nested_txt_delete(data[2].backup_directory,data[2].row.display_name,target_record_offset=0x300)
            self.assertEqual(data[0][3].calls,[])
            self.assertIsNone(data[0][5].read_sender_in_flight())
