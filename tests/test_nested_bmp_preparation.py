"""Host-only nested BMP insertion/inverse; no live nested BMP admission."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
from infocarry.backup_format import parse_backup_blob
from infocarry.delete_generalized import build_nested_file_delete_candidate, verify_nested_file_delete_readback, authorize_generalized_delete, GeneralizedDeleteError, GeneralizedDeleteVerificationError
from infocarry.delete_workflow import ROOT_BMP_DELETE_FIXTURE_BYTES, DELETE_GENERALIZED_CONFIRMATION_PHRASE
from infocarry.new_bmp import build_new_nested_bmp_add
from infocarry.desktop import DesktopWorkflowModel
from infocarry.device_library_delete_execution import DeviceLibraryDeleteService
from test_nested_file_delete import nested_library
from test_new_txt import _write_archive
from test_root_bmp_delete_model import _checksum


class NestedBmpPreparationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.now=datetime.now(timezone.utc)
        self.blob=nested_library()
        self.fixed={c:bytes(64) for c in range(0x1b,0x20)}
        self.source=self.root/'disposable.bmp';self.source.write_bytes(ROOT_BMP_DELETE_FIXTURE_BYTES)
        self.count=0

    def archive(self, blob=None, fixed=None):
        self.count+=1
        return _write_archive(self.root/str(self.count),self.blob if blob is None else blob,self.now,
            fixed_state=self.fixed if fixed is None else fixed)

    def build(self, **changes):
        args=dict(backup_directory=self.archive(),source_path=self.source,target_filename='disposable.bmp',
            target_directory_path=('root','folder','sub'),target_directory_offset=0x200,
            source_template_offset=0x240,available_capacity_bytes=20000,
            record_timestamp_be32=1792000030,max_age_seconds=None)
        args.update(changes)
        return build_new_nested_bmp_add(**args)

    def test_host_model_stays_sender_free_and_ordinary_service_admits_reviewed_profile(self):
        placed=self.build();after=parse_backup_blob(placed.candidate_blob)
        target=next(o for o,p in after.paths.items() if p==('root','folder','sub','disposable'))
        post=self.archive(placed.candidate_blob,dict(zip(range(0x1b,0x20),
            tuple(placed.transaction.ranges[0][i:i+64] for i in range(0,256,64))+(placed.transaction.ranges[1],))))
        host=build_nested_file_delete_candidate(post,r'root\folder\sub\disposable.bmp',target,max_age_seconds=None)
        self.assertEqual(host.candidate_blob,self.blob)
        self.assertEqual(host.fixed_state.after,tuple(self.fixed.values()))
        self.assertFalse(hasattr(host,'transaction'))
        with self.assertRaises(GeneralizedDeleteError):authorize_generalized_delete(host,confirmation=DELETE_GENERALIZED_CONFIRMATION_PHRASE)
        final=self.archive(host.candidate_blob,dict(zip(range(0x1b,0x20),host.fixed_state.after)))
        verify_nested_file_delete_readback(host,final,completion=0,max_age_seconds=None)
        model=DesktopWorkflowModel();model.load_backup(post)
        service=DeviceLibraryDeleteService(lambda: (_ for _ in ()).throw(AssertionError('runtime opened')))
        selection=service.select(model,[target])
        self.assertTrue(selection.general_nested_bmp)
        self.assertTrue(service.execution_available(selection))
        self.assertTrue(placed.audit['preservation']['inverse_nested_delete_exact_baseline'])
        self.assertEqual(placed.audit['template']['record_offset_hex'],'0x00000240')
        self.assertIn('copied_record_fields_sha256',placed.audit['template'])

    def test_parent_template_conflicts_names_capacity_and_payload_refuse(self):
        for changes in ({'target_directory_offset':0xc0}, {'target_directory_path':('root',)},
                        {'target_filename':'deep.bmp'}, {'target_filename':'bad:name.bmp'},
                        {'available_capacity_bytes':0}, {'source_template_offset':0x1c0},
                        {'record_timestamp_be32':True}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.build(**changes)
        self.source.write_bytes(b'not a bitmap')
        with self.assertRaises(ValueError):self.build()

    def test_opaque_prefix_and_active_marks_refuse_without_guessing(self):
        for offset in (0x240+16,0x240+20):
            blob=bytearray(self.blob);blob[offset:offset+4]=bytes(4)
            with self.assertRaises(ValueError):self.build(backup_directory=self.archive(_checksum(blob)))
        blob=bytearray(self.blob);parsed=parse_backup_blob(self.blob)
        blob[parsed.header.content_start+parsed.record_at(0x240).field_04_be32]=0
        with self.assertRaises(ValueError):self.build(backup_directory=self.archive(_checksum(blob)))
        marks=bytearray(64);marks[:4]=(1).to_bytes(4,'big');marks[8:12]=(0x200).to_bytes(4,'big')
        fixed=dict(self.fixed);fixed[0x1c]=bytes(marks)
        with self.assertRaises(ValueError):self.build(backup_directory=self.archive(fixed=fixed))

    def test_survivor_references_before_after_insertion_rebase_and_restore(self):
        for offset in (0x100,0x300):
            raw=bytearray(64);raw[:4]=(1).to_bytes(4,'big');raw[8:12]=(offset-64).to_bytes(4,'big')
            fixed=dict(self.fixed);fixed[0x1b]=bytes(raw)
            placed=self.build(backup_directory=self.archive(fixed=fixed))
            self.assertEqual(int.from_bytes(placed.transaction.ranges[0][8:12],'big'),offset-64)
            after=parse_backup_blob(placed.candidate_blob)
            target=next(o for o,p in after.paths.items() if p[-1]=='disposable')
            blocks=tuple(placed.transaction.ranges[0][i:i+64] for i in range(0,256,64))+(placed.transaction.ranges[1],)
            host=build_nested_file_delete_candidate(self.archive(placed.candidate_blob,dict(zip(range(0x1b,0x20),blocks))),
                r'root\folder\sub\disposable.bmp',target,max_age_seconds=None)
            self.assertEqual(host.fixed_state.after,tuple(fixed.values()))

    def test_independent_nested_verifier_rejects_marker_payload_and_timestamp_drift(self):
        placed=self.build();after=parse_backup_blob(placed.candidate_blob)
        target=next(o for o,p in after.paths.items() if p[-1]=='disposable')
        blocks=tuple(placed.transaction.ranges[0][i:i+64] for i in range(0,256,64))+(placed.transaction.ranges[1],)
        host=build_nested_file_delete_candidate(self.archive(placed.candidate_blob,dict(zip(range(0x1b,0x20),blocks))),
            r'root\folder\sub\disposable.bmp',target,max_age_seconds=None)
        for offset in (0x300+12,0x340+8,parse_backup_blob(self.blob).header.content_start):
            drift=bytearray(self.blob);drift[offset]^=1
            with self.assertRaises(GeneralizedDeleteVerificationError):verify_nested_file_delete_readback(host,self.archive(_checksum(drift)),completion=0,max_age_seconds=None)
        with patch('infocarry.delete_model.delete_existing_file',side_effect=AssertionError('repacker called')):
            verify_nested_file_delete_readback(host,self.archive(),completion=0,max_age_seconds=None)

    def test_exact_host_rehearsal_reports_no_authority_and_preserves_original_input(self):
        import sys,json,hashlib,importlib.util
        scripts=Path(__file__).resolve().parents[1]/'scripts'
        with patch.object(sys,'path',[str(scripts),*sys.path]):
            spec=importlib.util.spec_from_file_location('nested_bmp_rehearsal',scripts/'prepare_nested_bmp_validation.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        from infocarry.backup_repack import rename_existing_record
        blob=rename_existing_record(parse_backup_blob(self.blob),0xc0,'IC_P18_040_NESTED_20260930_01')
        blob=rename_existing_record(parse_backup_blob(blob),0x200,'Section-A')
        archive=self.archive(blob);manifest=(archive/'manifest.json').read_bytes()
        with patch('infocarry.library_transfer_runtime_provider.ProductionLibraryTransferRuntimeProvider.for_current_application',
                   side_effect=AssertionError('runtime opened')):
            result=module.prepare(archive,self.root/'rehearsal',capacity_limit_bytes=3145728,
                                  timestamp=1792000040,source_head='a'*40)
        report=json.loads(Path(result['report']).read_bytes())
        self.assertEqual(report['maximum_sender_invocations'],2)
        self.assertEqual(report['status'],'host_rehearsal_not_hardware_ready')
        self.assertEqual(report['fixture']['bytes'],10302)
        self.assertEqual(result['sha256'],hashlib.sha256(Path(result['report']).read_bytes()).hexdigest())
        self.assertFalse(report['execution_available']);self.assertFalse(report['physical_operation_authorized'])
        self.assertEqual(report['usb_operations'],0)
        self.assertEqual((archive/'manifest.json').read_bytes(),manifest)
        with self.assertRaises(ValueError):module.prepare(archive,archive/'bad',capacity_limit_bytes=3145728,
                                                        timestamp=1792000040,source_head='a'*40)
