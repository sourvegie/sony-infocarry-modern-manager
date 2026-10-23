"""Conservative host BMP admission and explicit disposable-only B validation."""
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import replace
import hashlib
import tempfile
import unittest
from unittest.mock import patch

from infocarry.backup_format import parse_backup_blob, calculate_backup_checksum
from infocarry.backup_repack import rename_existing_record
from infocarry.delete_workflow import (
    build_root_bmp_delete, ROOT_BMP_DELETE_EXPANSION_PATH,
    ROOT_BMP_DELETE_EXPANSION_BYTES, ROOT_BMP_DELETE_VALIDATION_FILES,
    ROOT_BMP_DELETE_FIXTURE_BYTES,
    root_bmp_delete_execution_supported, root_bmp_delete_validation_supported,
    prepare_disposable_root_bmp_delete,
)
from infocarry.delete_generalized import authorize_generalized_delete, bind_generalized_delete_sender, DELETE_GENERALIZED_CONFIRMATION_PHRASE
from infocarry.device_library_delete_execution import DeviceLibraryDeleteService, load_verified_delete_result
from infocarry.desktop import DesktopWorkflowModel
from infocarry.prepared_media_package import validate_bmp_payload
from test_root_bmp_delete_model import root_bitmap_library, _checksum
from test_bitmap import make_monochrome_bmp
from test_new_txt import _write_archive
from test_delete_hardening import _make_root_siblings
import test_experimental_root_txt_delete as experimental_helpers


def expansion_library():
    payloads = [f'unchanged {i}'.encode() for i in range(26)]
    payloads[23] = b'Disposable P18-043 root TXT A.\r\n'
    payloads[24] = ROOT_BMP_DELETE_EXPANSION_BYTES
    original = parse_backup_blob(_make_root_siblings(payloads))
    metadata = bytearray(original.data[:original.header.content_start]); content = bytearray()
    for row in original.records:
        if row.kind != 'file':
            continue
        prefix, payload = original.payload_parts(row)
        metadata[row.offset+4:row.offset+8] = len(content).to_bytes(4, 'big')
        if row.offset == 0x6c0:
            metadata[row.offset] = 0xe0; metadata[row.offset+1:row.offset+4] = b'bmp'
            metadata[row.offset+20:row.offset+24] = (0x100).to_bytes(4, 'big')
            prefix = b'\xff'*16
        content.extend(prefix+payload); content.extend(b'\0'*(-len(content)%4))
    total = len(metadata)+len(content)+4
    for offset,value in ((0x18,total-1),(0x34,len(content)),(0x38,total)):
        metadata[offset:offset+4] = value.to_bytes(4,'big')
    blob = _checksum(metadata+content+b'\xff'*4)
    blob = rename_existing_record(parse_backup_blob(blob),0x680,'IC_P18_043_DELETE_A')
    return rename_existing_record(parse_backup_blob(blob),0x6c0,'IC_P18_047_DELETE_B')


class RootBmpExpansionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.sequence=0

    def archive(self,blob,fixed=None):
        self.sequence+=1
        return _write_archive(self.root/str(self.sequence),blob,datetime.now(timezone.utc),
            fixed_state=fixed or {c:bytes(64) for c in range(0x1b,0x20)})

    def test_ordinary_host_admission_names_positions_orientations_and_readback(self):
        for index in range(3):
            for top_down in (False,True):
                for name in ('ordinary','資料_01'):
                    with self.subTest(index=index,top_down=top_down,name=name):
                        blob,offset=root_bitmap_library(index=index,payload=make_monochrome_bmp(237,320,top_down=top_down))
                        blob=rename_existing_record(parse_backup_blob(blob),offset,name)
                        core=build_root_bmp_delete(self.archive(blob),f'root\\{name}.bmp',target_record_offset=offset)
                        self.assertEqual(core.target_record_offset,offset)
                        self.assertTrue(root_bmp_delete_execution_supported(core))
                        self.assertFalse(root_bmp_delete_validation_supported(core))
                        binding=authorize_generalized_delete(core,confirmation=DELETE_GENERALIZED_CONFIRMATION_PHRASE)
                        with self.assertRaisesRegex(RuntimeError,'host-only'):
                            bind_generalized_delete_sender(binding,core)
                        self.assertEqual(core.audit['capability_status'],'host_offline_not_live_enabled')

    def test_unsupported_profiles_native_names_and_payloads_refuse(self):
        for mode in ('read','prefix32','prefix_bytes','opaque','upper','bad_bmp','no_nul','unsafe','missing','wrong_offset'):
            with self.subTest(mode=mode):
                blob,offset=root_bitmap_library(flag=0x20 if mode=='read' else 0xe0,
                    prefix_bytes=32 if mode=='prefix32' else 16)
                raw=bytearray(blob); parsed=parse_backup_blob(blob); target=parsed.record_at(offset)
                path=f'root\\{target.name}.bmp'
                if mode=='prefix_bytes':raw[parsed.header.content_start+target.field_04_be32]=0
                if mode=='opaque':raw[offset+16:offset+20]=bytes(4)
                if mode=='upper':raw[offset+1:offset+4]=b'BMP';path=path[:-3]+'BMP'
                if mode=='bad_bmp':raw[parsed.header.content_start+target.field_04_be32+16]=0
                if mode=='no_nul':raw[offset+24:offset+64]=b'A'*40;path='root\\'+('A'*40)+'.bmp'
                if mode=='unsafe':
                    blob=rename_existing_record(parsed,offset,'a.b');raw=bytearray(blob);path='root\\a.b.bmp'
                if mode=='missing':path='root\\absent.bmp'
                with self.assertRaises((ValueError,RuntimeError)):
                    build_root_bmp_delete(self.archive(_checksum(raw)),path,
                        target_record_offset=offset+64 if mode=='wrong_offset' else offset)

    def test_references_marks_and_wrong_model_refuse(self):
        blob,offset=root_bitmap_library()
        path=f'root\\{parse_backup_blob(blob).record_at(offset).name}.bmp'
        for command in (0x1b,0x1c,0x1f):
            fixed={c:bytes(64) for c in range(0x1b,0x20)};raw=bytearray(64)
            if command==0x1f:
                raw[:4]=(offset-64).to_bytes(4,'big');raw[8:12]=(0x80000000).to_bytes(4,'big')
            else:
                raw[:4]=(1).to_bytes(4,'big');raw[8:12]=(offset-64).to_bytes(4,'big')
            fixed[command]=bytes(raw)
            with self.subTest(command=command),self.assertRaises((ValueError,RuntimeError)):
                build_root_bmp_delete(self.archive(blob,fixed),path)
        import json
        backup=self.archive(blob);p=backup/'manifest.json';d=json.loads(p.read_text());d['device']['product_id']='0x001d';p.write_text(json.dumps(d))
        with self.assertRaises((ValueError,RuntimeError)):build_root_bmp_delete(backup,path)

    def test_expansion_fixture_and_host_preparation_remain_exact(self):
        self.assertEqual(validate_bmp_payload(ROOT_BMP_DELETE_EXPANSION_BYTES)['height'],320)
        self.assertEqual(len(ROOT_BMP_DELETE_EXPANSION_BYTES),10302)
        import json
        manifest=json.loads((Path(__file__).resolve().parents[1]/'analysis/p18-047-disposable-root-bmp-fixture-20261022.json').read_text())
        self.assertEqual(manifest['sha256'],hashlib.sha256(ROOT_BMP_DELETE_EXPANSION_BYTES).hexdigest())
        self.assertFalse(manifest['physical_operations_authorized'])
        self.assertEqual(manifest['path'],ROOT_BMP_DELETE_EXPANSION_PATH)
        self.assertLess(int.from_bytes(ROOT_BMP_DELETE_EXPANSION_BYTES[22:26],'little',signed=True),0)
        blob=expansion_library();before=self.archive(blob)
        prepared=prepare_disposable_root_bmp_delete(before,self.root/'prepared',target_path=ROOT_BMP_DELETE_EXPANSION_PATH)
        core=prepared.verify()
        self.assertFalse(prepared.execution_available)
        self.assertTrue(root_bmp_delete_execution_supported(core))
        self.assertTrue(root_bmp_delete_validation_supported(core))
        parsed=parse_backup_blob(blob);after=parse_backup_blob(core.candidate_blob)
        self.assertEqual(parsed.record_at(0x680).raw_hex,after.record_at(0x680).raw_hex)
        with self.assertRaises((ValueError,RuntimeError,KeyError)):
            replace(prepared,target_path='root\\other.bmp').verify()

    def fake_case(self,**kwargs):
        helper=experimental_helpers.ExperimentalRootTxtDeleteTests('test_exact_candidate_inverse_preserves_timestamps_and_is_claim_free')
        self.addCleanup(helper.doCleanups);case=helper.setup_case(**kwargs)
        case[2]['blob']=expansion_library();case[2]['fixture_blob']=case[2]['blob'];case[2]['fixed']={c:bytes(64) for c in range(0x1b,0x20)}
        model=DesktopWorkflowModel();model.load_backup(self.archive(case[2]['blob']))
        return case,model

    def test_B_placement_uses_existing_frozen_facade_and_refuses_wrong_slot(self):
        import test_root_txt_placement as placement_helpers
        helper=placement_helpers.RootPlacementTests('test_exact_fixture_admitted_frozen_without_sender_or_claim')
        self.addCleanup(helper.doCleanups)
        case=helper.setup_case(media='bmp')
        source=case[0]/'IC_P18_047_DELETE_B.bmp';source.write_bytes(ROOT_BMP_DELETE_EXPANSION_BYTES)
        # Wrong serialized position is rejected before any claim/sender.
        with self.assertRaisesRegex(ValueError,'anchor'):
            case[4].prepare(source,target_path=ROOT_BMP_DELETE_EXPANSION_PATH,
                validation_placement=True,placement_media='bmp')
        self.assertEqual(case[3].calls,[])
        case=helper.setup_case(media='bmp');source=case[0]/'IC_P18_047_DELETE_B.bmp';source.write_bytes(ROOT_BMP_DELETE_EXPANSION_BYTES)
        payloads=[ROOT_BMP_DELETE_FIXTURE_BYTES]+[f'survivor {i}'.encode() for i in range(22)]+[b'Disposable P18-043 root TXT A.\r\n']
        base=parse_backup_blob(_make_root_siblings(payloads));raw=bytearray(base.data[:base.header.content_start]);content=bytearray()
        for r in base.records:
            if r.kind!='file':continue
            prefix,payload=base.payload_parts(r);raw[r.offset+4:r.offset+8]=len(content).to_bytes(4,'big')
            if r.offset==0xc0:
                raw[r.offset+1:r.offset+4]=b'bmp';raw[r.offset+20:r.offset+24]=(0x100).to_bytes(4,'big');prefix=b'\xff'*16
            content.extend(prefix+payload);content.extend(b'\0'*(-len(content)%4))
        total=len(raw)+len(content)+4
        for off,value in ((0x18,total-1),(0x34,len(content)),(0x38,total)):raw[off:off+4]=value.to_bytes(4,'big')
        blob=rename_existing_record(parse_backup_blob(_checksum(raw+content+b'\xff'*4)),0x680,'IC_P18_043_DELETE_A')
        case[2]['blob']=blob
        bundle=case[4].prepare(source,target_path=ROOT_BMP_DELETE_EXPANSION_PATH,
            validation_placement=True,placement_media='bmp');case[2]['bundle']=bundle
        bundle.verify_seal()
        self.assertEqual(bundle.owner_confirmation_phrase,'ADD IC_P18_047_DELETE_B.bmp ONCE')
        self.assertIsNone(case[5].read_claim(bundle.seal_sha256))
        identity=case[4].owner_authorization_identity;case[4].authorize_prepared_operation(identity.approval_phrase)
        result=case[4].execute_once(confirmation_interaction=lambda _:identity.approval_phrase)
        self.assertEqual(result.completion,0);self.assertEqual(result.audit['workflow']['sender_calls'],1)
        final=parse_backup_blob(case[2]['blob'])
        self.assertEqual(final.paths[0x6c0],('root','IC_P18_047_DELETE_B'))
        self.assertEqual(final.payload_parts(final.record_at(0x680))[1],b'Disposable P18-043 root TXT A.\r\n')

    def test_nested_txt_and_bmp_UI_stays_unavailable_without_runtime(self):
        from test_backup_duplicate import make_nested_blob
        for ext,payload,prefix in (('txt',b'nested',32),('bmp',ROOT_BMP_DELETE_EXPANSION_BYTES,16)):
            raw=bytearray(make_nested_blob(payload,prefix_length=prefix));raw[0x141:0x144]=ext.encode()
            model=DesktopWorkflowModel();model.load_backup(self.archive(_checksum(raw)))
            service=DeviceLibraryDeleteService(lambda:self.fail('nested file opened runtime'))
            with self.subTest(ext=ext),self.assertRaises(ValueError):service.select(model,[0x140])

    def test_normal_device_library_admits_supported_B_but_not_multiple_or_root(self):
        case,model=self.fake_case()
        normal=DeviceLibraryDeleteService(lambda:self.fail('unsupported BMP opened runtime'))
        selected = normal.select(model,[0x6c0])
        self.assertTrue(selected.general_bmp)
        self.assertTrue(normal.execution_available(selected))
        with self.assertRaises(ValueError):normal.select(model,[0x680,0x6c0])
        with self.assertRaises(ValueError):normal.select(model,[0x40])
        self.assertEqual(case[3].calls,[])

    def test_B_missing_anchor_wrong_payload_and_wrong_slot_fail_closed(self):
        from infocarry.delete_workflow import build_experimental_root_bmp_delete
        for mode in ('anchor_name','anchor_payload','B_payload','B_slot'):
            raw=bytearray(expansion_library());parsed=parse_backup_blob(raw)
            if mode=='anchor_name':raw=bytearray(rename_existing_record(parsed,0x680,'not_anchor'))
            if mode in ('anchor_payload','B_payload'):
                r=parsed.record_at(0x680 if mode=='anchor_payload' else 0x6c0)
                raw[parsed.header.content_start+r.field_04_be32+r.payload_prefix_length]^=1
            if mode=='B_slot':
                raw=bytearray(rename_existing_record(parsed,0x6c0,'not_B'))
                raw=bytearray(rename_existing_record(parse_backup_blob(raw),0x700,'IC_P18_047_DELETE_B'))
            with self.subTest(mode=mode),self.assertRaises((ValueError,RuntimeError)):
                build_experimental_root_bmp_delete(self.archive(_checksum(raw)),target_path=ROOT_BMP_DELETE_EXPANSION_PATH)

    def test_existing_offline_script_generates_B_without_runtime_and_inspects_ordinary_BMP(self):
        import importlib.util,io,json
        from contextlib import redirect_stdout
        script=Path(__file__).resolve().parents[1]/'scripts/prepare_root_bmp_delete.py'
        spec=importlib.util.spec_from_file_location('prepare_root_bmp_expansion',script)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with patch('infocarry.library_transfer_runtime_provider.ProductionLibraryTransferRuntimeProvider.for_current_application',side_effect=AssertionError('runtime opened')):
            out=io.StringIO()
            with redirect_stdout(out):module.main(['fixture','--target',ROOT_BMP_DELETE_EXPANSION_PATH,'--output',str(self.root/'fixture')])
            result=json.loads(out.getvalue());self.assertFalse(result['execution_available'])
            self.assertEqual(Path(result['file']).read_bytes(),ROOT_BMP_DELETE_EXPANSION_BYTES)
            blob,offset=root_bitmap_library();backup=self.archive(blob)
            out=io.StringIO()
            with redirect_stdout(out):module.main(['inspect','--target',f'root\\{parse_backup_blob(blob).record_at(offset).name}.bmp','--backup',str(backup)])
            self.assertFalse(json.loads(out.getvalue())['execution_available'])

    def test_explicit_validation_B_uses_same_one_sender_readback_and_refresh(self):
        case,model=self.fake_case()
        service=DeviceLibraryDeleteService(lambda:case[4].runtime,validation_target=ROOT_BMP_DELETE_EXPANSION_PATH)
        selection=service.select(model,[0x6c0]);prepared=service.prepare(selection);case[2]['bundle']=prepared.bundle
        self.assertTrue(service.execution_available(selection))
        self.assertEqual(prepared.bundle.owner_confirmation_phrase,'DELETE IC_P18_047_DELETE_B.bmp ONCE')
        self.assertNotIn('SHA',prepared.confirmation_message)
        self.assertIsNone(case[5].read_claim(prepared.bundle.seal_sha256))
        result=service.execute_once(prepared,confirmed=True)
        self.assertEqual(result.completion,0);self.assertEqual(result.audit['workflow']['sender_calls'],1)
        self.assertFalse(result.audit['workflow']['automatic_retry_allowed'])
        self.assertIsNone(case[5].read_sender_in_flight())
        load_verified_delete_result(model,result)
        names=[r.display_name for r in model.rows()]
        self.assertNotIn(ROOT_BMP_DELETE_EXPANSION_PATH,names)
        self.assertIn('root\\IC_P18_043_DELETE_A.txt',names)

    def test_explicit_validation_B_ambiguous_send_locks_without_retry(self):
        case,model=self.fake_case(backend_options={'fail_bulk_at':1})
        service=DeviceLibraryDeleteService(lambda:case[4].runtime,validation_target=ROOT_BMP_DELETE_EXPANSION_PATH)
        prepared=service.prepare(service.select(model,[0x6c0]));case[2]['bundle']=prepared.bundle
        with self.assertRaises(Exception) as raised:service.execute_once(prepared,confirmed=True)
        self.assertEqual(raised.exception.state,'indeterminate_after_transaction_start')
        self.assertIsNotNone(case[5].read_sender_in_flight());self.assertTrue(case[6].read().locked)
        self.assertEqual(sum(c[0]=='control_out' for c in case[3].calls),1)


if __name__=='__main__':unittest.main()
