"""General root TXT preparation and disposable-only guarded validation."""
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from infocarry.backup_format import parse_backup_blob, calculate_backup_checksum
from infocarry.backup_repack import rename_existing_record, repack_existing_records
from infocarry.delete_workflow import (
    build_root_txt_delete, validate_root_txt_delete_name, ROOT_TXT_DELETE_VALIDATION_FILES,
    ROOT_TXT_DELETE_HOST_PROFILE, ROOT_TXT_DELETE_VALIDATION_PROFILE, ROOT_TXT_DELETE_LIVE_PROFILE,
)
from infocarry.device_library_delete_execution import (
    DeviceLibraryDeleteService, select_device_library_delete, load_verified_delete_result,
)
from infocarry.desktop import DesktopWorkflowModel
from infocarry.experimental_library_transfer import GuardedLibraryExecutionCoordinator
from infocarry.device_model_profile import VNW_V15_PROFILE
try:
    import test_experimental_root_txt_delete as exact_helpers
    import test_device_library_delete_ui as ui_helpers
    from test_new_txt import _write_archive
    from test_delete_hardening import _make_root_siblings
    from test_backup_format import make_text_blob
except ModuleNotFoundError:
    from tests import test_experimental_root_txt_delete as exact_helpers
    from tests import test_device_library_delete_ui as ui_helpers
    from tests.test_new_txt import _write_archive
    from tests.test_delete_hardening import _make_root_siblings
    from tests.test_backup_format import make_text_blob


def _checksum(blob):
    data=bytearray(blob)
    data[0x1c:0x20]=calculate_backup_checksum(data).to_bytes(4,'big')
    return bytes(data)


class RootTxtAdmissionTests(unittest.TestCase):
    def archived(self, blob, fixed=None):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        path=Path(temporary.name)/'archive'
        _write_archive(path,blob,datetime.now(timezone.utc), fixed_state=fixed or {c:bytes(64) for c in range(0x1b,0x20)})
        return path

    def case(self, *, path=None, payload=None, validation=False, options=None, reconnect=False, flag=0xe0):
        helper=exact_helpers.ExperimentalRootTxtDeleteTests('test_exact_candidate_inverse_preserves_timestamps_and_is_claim_free')
        self.addCleanup(helper.doCleanups)
        case=helper.setup_case(backend_options=options, reconnect=reconnect)
        path=path or next(iter(ROOT_TXT_DELETE_VALIDATION_FILES))
        payload=ROOT_TXT_DELETE_VALIDATION_FILES.get(path,b'ordinary unrelated root TXT\r\n') if payload is None else payload
        parsed=parse_backup_blob(case[2]['blob'])
        target=next(r for r in parsed.records if r.name=='IC_P18_041G_CLOCK_01')
        name=path.split('\\')[-1][:-4]
        renamed=parsed.data if name==target.name else rename_existing_record(parsed,target.offset,name)
        case[2]['blob']=repack_existing_records(parse_backup_blob(renamed),{target.offset:payload})
        changed=bytearray(case[2]['blob']);changed[target.offset]=flag
        case[2]['blob']=_checksum(changed)
        case[2]['fixture_blob']=case[2]['blob']
        displayed=case[0]/'displayed-general'
        _write_archive(displayed,case[2]['blob'],datetime.now(timezone.utc),fixed_state=case[2]['fixed'])
        model=DesktopWorkflowModel();model.load_backup(displayed)
        service=DeviceLibraryDeleteService(lambda:case[4].runtime, validation_target=path if validation else None)
        self.addCleanup(service.discard)
        selection=service.select(model,[target.offset])
        return case,model,service,selection

    def prepare(self, data):
        prepared=data[2].prepare(data[3]);data[0][2]['bundle']=prepared.bundle
        return prepared

    def no_send(self,data,prepared=None):
        self.assertEqual(data[0][3].calls,[])
        self.assertIsNone(data[0][5].read_sender_in_flight())
        if prepared:
            self.assertIsNone(data[0][5].read_claim(prepared.bundle.seal_sha256))

    def test_paired_remainder_two_fixture_at_different_serialized_position_is_exact_inverse(self):
        from infocarry.new_txt import build_new_root_txt_add
        from infocarry.delete_generalized import verify_generalized_delete_readback
        try:
            from test_new_txt import _make_root_blob
        except ModuleNotFoundError:
            from tests.test_new_txt import _make_root_blob
        original = _make_root_blob()
        current = self.archived(original)
        added = []
        def archive_transaction(transaction):
            fixed = {c: transaction.ranges[0][(c-0x1b)*64:(c-0x1a)*64] for c in range(0x1b,0x1f)}
            fixed[0x1f] = transaction.ranges[1]
            return self.archived(transaction.ranges[4]+transaction.ranges[7], fixed)
        for target in ('root\\IC_P18_043_DELETE_A.txt', 'root\\IC_P18_045_DELETE_C.txt'):
            source = current.parent / target.split('\\')[-1]
            source.write_bytes(ROOT_TXT_DELETE_VALIDATION_FILES[target])
            result = build_new_root_txt_add(current, source, source.name,
                source_template_offset=0xc0, available_capacity_bytes=10000,
                record_timestamp_be32=1791696600, fresh_new_allocation=True)
            added.append(result)
            current = archive_transaction(result.transaction)
        self.assertEqual(added[0].audit['target']['record_offset_hex'], '0x00000100')
        self.assertEqual(added[1].audit['target']['record_offset_hex'], '0x00000140')
        self.assertEqual(added[1].audit['allocation']['alignment_padding_bytes'], 2)
        self.assertEqual(added[1].audit['allocation']['candidate_growth_bytes'], 132)
        for target, expected_blob in (('root\\IC_P18_045_DELETE_C.txt', added[0].candidate_blob),
                                      ('root\\IC_P18_043_DELETE_A.txt', original)):
            core = build_root_txt_delete(current, target)
            current = archive_transaction(core.transaction)
            verify_generalized_delete_readback(core, current, completion=0)
            self.assertEqual(core.candidate_blob, expected_blob)
        self.assertEqual(parse_backup_blob(original).records, parse_backup_blob(expected_blob).records)

    def test_p18_045_manifest_is_exact_and_c_uses_reviewed_unread_envelope(self):
        from hashlib import sha256
        manifest = json.loads((Path(__file__).resolve().parents[1] / 'analysis' /
            'p18-045-disposable-root-txt-fixtures-20261011.json').read_bytes())
        self.assertFalse(manifest['physical_operations_authorized'])
        for fixture in manifest['fixtures']:
            payload = ROOT_TXT_DELETE_VALIDATION_FILES[fixture['path']]
            self.assertEqual(payload, fixture['payload_ascii'].encode('ascii'))
            self.assertEqual(len(payload), fixture['bytes'])
            self.assertEqual(sha256(payload).hexdigest(), fixture['sha256'])
            self.assertEqual(len(payload)%4, fixture['alignment_remainder'])
        data = self.case(path='root\\IC_P18_045_DELETE_C.txt')
        prepared = self.prepare(data)
        self.assertTrue(data[2].execution_available(data[3]))
        self.assertEqual(prepared.bundle.operation_profile,ROOT_TXT_DELETE_LIVE_PROFILE)
        prepared.bundle.assert_execution_admitted()
        self.no_send(data, prepared)

    def test_first_middle_last_alignment_empty_and_large_payloads(self):
        for index in range(3):
            for length in (0,1,2,3,4,1863,65539):
                with self.subTest(index=index,length=length):
                    payloads=[b'survivor-a',b'survivor-b',b'survivor-c'];payloads[index]=b'x'*length
                    before=parse_backup_blob(_make_root_siblings(payloads))
                    offset=0xc0+index*64;path=f'root\\{chr(97+index)}.txt'
                    core=build_root_txt_delete(self.archived(before.data),path,target_record_offset=offset)
                    after=parse_backup_blob(core.candidate_blob)
                    self.assertEqual(len(after.records),len(before.records)-1)
                    self.assertEqual(core.candidate_model.audit['candidate']['removed_paths'],[path])
                    for old in before.records:
                        if old.offset==offset:continue
                        new=after.record_at(old.offset-64 if old.offset>offset else old.offset)
                        self.assertEqual(new.timestamp_be32,old.timestamp_be32)
                        if old.kind=='file':self.assertEqual(before.payload_parts(old),after.payload_parts(new))
                    start=core.candidate_model.audit['allocation']['content_segment_start']
                    end=core.candidate_model.audit['allocation']['aligned_content_end']
                    content=before.data[before.header.content_start:before.header.content_start+before.header.content_length]
                    self.assertEqual(after.data[after.header.content_start:after.header.content_start+after.header.content_length],content[:start]+content[end:])

    def test_safe_cp932_names_read_and_unread(self):
        for name in ('a','日本語テキスト','x'*39):
            for flag in (0xe0,0x20):
                blob=make_text_blob(b'opaque CP932 payload\xff',file_flag=flag)
                blob=rename_existing_record(parse_backup_blob(blob),0xc0,name)
                core=build_root_txt_delete(self.archived(blob),f'root\\{name}.txt')
                self.assertEqual(core.target_record_offset,0xc0)
                self.assertEqual(core.candidate_model.target_payload_sha256,core.target_payload_sha256)

    def test_unsafe_names_and_nonroundtrip_cp932_refuse(self):
        for name in ('','.','..','root','x'*40,'bad/name','bad\\name','bad\nname','😀','〜',' name','name ','report.v2'):
            with self.subTest(name=name),self.assertRaises(ValueError):
                validate_root_txt_delete_name(name)

    def test_unterminated_or_changed_native_name_identity_refuses(self):
        for raw_name in (b'x'*40,b'memo\0'+b'q'*35):
            # Unknown trailing bytes after the NUL are preserved metadata, not
            # part of the identity. Only the unterminated case is unsupported.
            data=bytearray(make_text_blob());data[0xc0+24:0x100]=raw_name
            archive=self.archived(_checksum(data))
            if b'\0' not in raw_name:
                with self.assertRaises(ValueError):build_root_txt_delete(archive,'root\\'+raw_name.decode()+'.txt')
            else:
                self.assertEqual(build_root_txt_delete(archive,'root\\memo.txt').target_record_offset,0xc0)

    def test_unknown_native_prefix_highbits_state_nested_directory_and_missing_refuse(self):
        for field in (0x100,0x10200):
            blob=make_text_blob(b'data',field14=field)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'32-byte prefix'):
                build_root_txt_delete(self.archived(blob),'root\\memo.txt')
        for path in ('root','root\\nested\\memo.txt','root\\missing.txt'):
            with self.subTest(path=path),self.assertRaises(ValueError):
                build_root_txt_delete(self.archived(make_text_blob()),path)
        with self.assertRaises(ValueError):
            build_root_txt_delete(self.archived(make_text_blob()),'root\\memo.txt',target_record_offset=0x100)

    def test_case_ambiguous_targets_refuse(self):
        data=bytearray(_make_root_siblings((b'a',b'b')))
        data[0xc0+24:0x100]=b'Name'+bytes(36)
        data[0x100+24:0x140]=b'name'+bytes(36)
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            build_root_txt_delete(self.archived(_checksum(data)),'root\\Name.txt')

    def test_referenced_target_and_active_marks_refuse(self):
        for command in (0x1b,0x1c,0x1f):
            fixed={c:bytes(64) for c in range(0x1b,0x20)}
            raw=bytearray(64);ref=0xc0-0x40
            if command==0x1f:
                raw[:4]=ref.to_bytes(4,'big');raw[8:12]=(0x80000000).to_bytes(4,'big')
            else:
                raw[:4]=(1).to_bytes(4,'big');raw[8:12]=ref.to_bytes(4,'big')
            fixed[command]=bytes(raw)
            with self.subTest(command=command),self.assertRaises(Exception):
                build_root_txt_delete(self.archived(make_text_blob(),fixed),'root\\memo.txt')

    def test_read_txt_bundle_prepares_but_every_execution_entry_blocks(self):
        data=self.case(flag=0x20,path='root\\ordinary.txt');prepared=self.prepare(data)
        self.assertEqual(prepared.bundle.operation_profile,ROOT_TXT_DELETE_HOST_PROFILE)
        self.assertFalse(prepared.bundle.execution_available)
        self.assertIn('ordinary.txt',prepared.confirmation_message)
        self.assertEqual(prepared.owner_identity.approval_phrase,'DELETE ordinary.txt ONCE')
        prepared.bundle.verify_seal()
        coordinator=GuardedLibraryExecutionCoordinator(execution_claim_store=data[0][5],indeterminate_write_lock=data[0][6])
        with self.assertRaisesRegex(ValueError,'not physically validated'):
            coordinator.execute(prepared.bundle,plan_report=prepared.bundle.review_dict(),
                confirmation_interaction=lambda _:prepared.owner_identity.approval_phrase,
                owner_authorized_identity=prepared.owner_identity)
        self.no_send(data,prepared)
        with self.assertRaisesRegex(ValueError,'not physically validated'):
            prepared.bundle._consume_execution_claim(None)
        self.no_send(data,prepared)
        with self.assertRaisesRegex(ValueError,'not physically validated|unavailable'):
            data[2].execute_once(prepared,confirmed=True)
        self.no_send(data,prepared)

    def test_ordinary_unread_txt_uses_normal_single_confirmation_and_verified_refresh(self):
        data=self.case(path='root\\ordinary.txt',payload=b'ordinary payload, not a manifest fixture',reconnect=True)
        self.assertTrue(data[2].execution_available(data[3]))
        helper=ui_helpers.DeviceLibraryDeleteUITests('test_delete_confirm_verify_refresh_in_one_dialog')
        self.addCleanup(helper.doCleanups)
        ui=helper.setup_ui(data_override=(data[0],data[1],data[3],data[2]))
        ui.action();ui.drain()
        self.assertEqual(len(ui.dialogs),1)
        self.assertIn('ordinary.txt',ui.dialogs[0])
        self.assertNotIn('fingerprint',ui.dialogs[0])
        self.assertIn('Delete complete',ui.main_status.get())
        self.assertEqual(len(ui.refreshes),1)
        self.assertNotIn('root\\ordinary.txt',ui.refreshes[0])
        self.assertEqual(sum(c[0]=='control_out' for c in data[0][3].calls),1)
        self.assertIsNone(data[0][5].read_sender_in_flight())

    def test_live_ordinary_txt_stale_nonzero_disconnect_bad_readback_never_retry(self):
        for mode in ('stale','nonzero','disconnect','readback'):
            options={'completion':(2,)} if mode=='nonzero' else {'fail_bulk_at':2} if mode=='disconnect' else None
            data=self.case(path='root\\ordinary.txt',options=options);prepared=self.prepare(data)
            self.assertEqual(prepared.bundle.operation_profile,ROOT_TXT_DELETE_LIVE_PROFILE)
            if mode=='stale':data[0][2]['blob']=data[0][2]['original_blob']
            if mode=='readback':data[0][2]['bad_delete_readback']=True
            with self.subTest(mode=mode),self.assertRaises(Exception):data[2].execute_once(prepared,confirmed=True)
            self.assertEqual(sum(c[0]=='control_out' for c in data[0][3].calls),0 if mode=='stale' else 1)
            if mode in ('disconnect','readback'):
                self.assertTrue(data[0][6].read(VNW_V15_PROFILE.lock_key).locked)
                self.assertIsNotNone(data[0][5].read_sender_in_flight())

    def test_unsupported_prefix_or_referenced_target_stays_disabled_before_runtime(self):
        for mode in ('prefix','reference'):
            data=self.case(path='root\\ordinary.txt')
            if mode=='prefix':
                changed=bytearray(data[0][2]['blob']);off=data[3].row.record_offset
                changed[off+20:off+24]=(0x10200).to_bytes(4,'big');data[0][2]['blob']=_checksum(changed)
            else:
                fixed=bytearray(64);fixed[:4]=(1).to_bytes(4,'big')
                fixed[8:12]=(data[3].row.record_offset-0x40).to_bytes(4,'big');data[0][2]['fixed'][0x1b]=bytes(fixed)
            shown=self.archived(data[0][2]['blob'],data[0][2]['fixed'])
            model=DesktopWorkflowModel();model.load_backup(shown)
            selection=data[2].select(model,[data[3].row.record_offset])
            self.assertFalse(data[2].execution_available(selection))
            self.no_send(data)

    def test_missing_or_changed_displayed_archive_disables_delete_before_runtime(self):
        data=self.case(path='root\\ordinary.txt')
        self.assertFalse(data[2].execution_available(replace(data[3],backup_directory=data[0][0]/'absent')))
        (data[3].backup_directory/'manifest.json').write_bytes(b'{}')
        self.assertFalse(data[2].execution_available(data[3]))
        self.no_send(data)

    def test_host_bundle_cannot_turn_into_a_personal_file_validation(self):
        data=self.case(path='root\\personal.txt');prepared=self.prepare(data)
        object.__setattr__(prepared.bundle,'validation_only',True)
        with self.assertRaises(Exception):data[2].execute_once(prepared,confirmed=True)
        self.no_send(data,prepared)

    def test_disposable_guarded_ui_service_verifies_once_and_refreshes(self):
        for path in ROOT_TXT_DELETE_VALIDATION_FILES:
            data=self.case(path=path,validation=True,reconnect=True);prepared=self.prepare(data)
            self.assertEqual(prepared.bundle.operation_profile,ROOT_TXT_DELETE_VALIDATION_PROFILE)
            self.assertTrue(prepared.bundle.execution_available)
            data[0][2]['session']='reconnected'
            result=data[2].execute_once(prepared,confirmed=True)
            self.assertEqual(result.completion,0)
            self.assertEqual(result.audit['workflow']['sender_calls'],1)
            self.assertEqual(sum(c[0]=='control_out' for c in data[0][3].calls),1)
            self.assertIsNone(data[0][5].read_sender_in_flight())
            self.assertIsNotNone(data[0][5].read_claim(prepared.bundle.seal_sha256))
            load_verified_delete_result(data[1],result)
            self.assertNotIn(path,[r.display_name for r in data[1].rows()])
            with self.assertRaises(Exception):data[2].execute_once(prepared,confirmed=True)

    def test_wrong_disposable_payload_missing_authority_and_personal_path_refuse(self):
        path=next(iter(ROOT_TXT_DELETE_VALIDATION_FILES))
        data=self.case(path=path,payload=b'personal content',validation=True)
        self.assertFalse(data[2].execution_available(data[3]))
        with self.assertRaisesRegex(ValueError,'payload has changed'):self.prepare(data)
        self.no_send(data)
        with self.assertRaises(ValueError):DeviceLibraryDeleteService(lambda:None,validation_target='root\\personal.txt')

    def test_named_validation_cannot_admit_the_old_fixture_or_another_target(self):
        data=self.case(path='root\\ordinary.txt')
        restricted=DeviceLibraryDeleteService(lambda:data[0][4].runtime,validation_target=next(iter(ROOT_TXT_DELETE_VALIDATION_FILES)))
        self.assertFalse(restricted.execution_available(data[3]))
        with self.assertRaisesRegex(ValueError,'only its named'):
            restricted.prepare(data[3])
        self.no_send(data)
        from infocarry.p18_041h_experiment import FIXTURE_PATH,FIXTURE_BYTES
        old=self.case(path=FIXTURE_PATH,payload=FIXTURE_BYTES)
        self.assertFalse(restricted.execution_available(old[3]))
        with self.assertRaisesRegex(ValueError,'only its named'):
            restricted.prepare(old[3])
        self.no_send(old)

    def test_disposable_uses_actual_gui_callbacks_and_one_readable_confirmation(self):
        for path in ROOT_TXT_DELETE_VALIDATION_FILES:
            data=self.case(path=path,validation=True)
            helper=ui_helpers.DeviceLibraryDeleteUITests('test_delete_confirm_verify_refresh_in_one_dialog')
            self.addCleanup(helper.doCleanups)
            ui=helper.setup_ui(data_override=(data[0],data[1],data[3],data[2]))
            ui.action();ui.drain()
            self.assertEqual(len(ui.dialogs),1)
            self.assertIn(path.split('\\')[-1],ui.dialogs[0])
            self.assertNotIn('fingerprint',ui.dialogs[0])
            self.assertIn('Delete complete',ui.main_status.get())
            self.assertEqual(len(ui.refreshes),1)
            self.assertNotIn(path,ui.refreshes[0])

    def test_validation_session_cannot_enter_existing_replacement_writer(self):
        data=self.case(validation=True)
        helper=ui_helpers.DeviceLibraryDeleteUITests('test_delete_confirm_verify_refresh_in_one_dialog')
        self.addCleanup(helper.doCleanups)
        ui=helper.setup_ui(data_override=(data[0],data[1],data[3],data[2]))
        ui.replacement_action()
        self.assertIn('only its named disposable Delete',ui.main_status.get())
        self.no_send(data)

    def test_read_ordinary_gui_delete_callback_never_opens_runtime(self):
        data=self.case(flag=0x20,path='root\\ordinary.txt')
        helper=ui_helpers.DeviceLibraryDeleteUITests('test_delete_confirm_verify_refresh_in_one_dialog')
        self.addCleanup(helper.doCleanups)
        ui=helper.setup_ui(data_override=(data[0],data[1],data[3],data[2]))
        captures=len(data[0][2]['captures'])
        ui.action();ui.drain()
        self.assertEqual(ui.dialogs,[])
        self.assertEqual(captures,len(data[0][2]['captures']))
        self.assertIn('unavailable',ui.statuses.get())
        self.no_send(data)

    def test_wrong_target_candidate_source_audit_and_gate_drift_before_claim(self):
        for mutation in ('target','candidate','source','audit','scope','identity'):
            data=self.case(validation=True);prepared=self.prepare(data)
            if mutation=='target':object.__setattr__(prepared.bundle.candidate,'target_path','root\\another.txt')
            elif mutation=='candidate':object.__setattr__(prepared.bundle.candidate,'candidate_blob',b'bad')
            elif mutation=='source':prepared.bundle.source_path.write_bytes(b'changed')
            elif mutation=='audit':object.__setattr__(prepared.bundle.candidate,'audit_json',b'{}')
            elif mutation=='scope':object.__setattr__(prepared.bundle,'validation_only',False)
            else:object.__setattr__(prepared,'owner_identity',replace(prepared.owner_identity,readable_confirmation_phrase='DELETE another.txt ONCE'))
            with self.subTest(mutation=mutation),self.assertRaises(Exception):data[2].execute_once(prepared,confirmed=True)
            self.no_send(data,prepared)

    def test_stale_state_nonzero_disconnect_bad_readback_preserve_no_retry(self):
        for mode in ('stale','nonzero','disconnect','readback'):
            options={'completion':(2,)} if mode=='nonzero' else {'fail_bulk_at':2} if mode=='disconnect' else None
            data=self.case(validation=True,options=options);prepared=self.prepare(data)
            if mode=='stale':data[0][2]['blob']=data[0][2]['original_blob']
            if mode=='readback':data[0][2]['bad_delete_readback']=True
            with self.subTest(mode=mode),self.assertRaises(Exception):data[2].execute_once(prepared,confirmed=True)
            sends=sum(c[0]=='control_out' for c in data[0][3].calls)
            self.assertEqual(sends,0 if mode=='stale' else 1)
            if mode in ('disconnect','readback'):
                self.assertTrue(data[0][6].read(VNW_V15_PROFILE.lock_key).locked)
                self.assertIsNotNone(data[0][5].read_sender_in_flight())


if __name__=='__main__':unittest.main()
