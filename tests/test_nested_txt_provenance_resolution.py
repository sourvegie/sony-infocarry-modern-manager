"""Provenance is bound separately from byte equality; Delete restores all eight."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from infocarry.backup_format import parse_backup_blob
from infocarry.delete_workflow import build_nested_txt_validation_delete
from infocarry.root_txt_placement import (_blob, _select_nested_txt_template,
    _nested_txt_template_provenance, require_nested_placement_provenance)
from infocarry.device_library_delete_execution import DeviceLibraryDeleteService
from infocarry.desktop import DesktopWorkflowModel
from infocarry.write_gate import verify_fresh_backup
try:
    import test_nested_txt_delete_execution as helpers
    import test_nested_txt_experiment_preparation as preparation_helpers
    import test_nested_txt_placement_model as placement_helpers
    from test_new_txt import _write_archive
except ModuleNotFoundError:
    from tests import test_nested_txt_delete_execution as helpers
    from tests import test_nested_txt_experiment_preparation as preparation_helpers
    from tests import test_nested_txt_placement_model as placement_helpers
    from tests.test_new_txt import _write_archive
prep=preparation_helpers.preparation


class ProvenanceBindingTests(unittest.TestCase):
    def test_shared_template_selection_and_full_identity_agree_across_traversal_orders(self):
        helper=placement_helpers.NestedTxtGuardedPlacementTests();self.addCleanup(helper.doCleanups)
        case=helper.setup_case();bundle=helper.prepare(case)
        parsed=parse_backup_blob(_blob(bundle.before_backup))
        selected=_select_nested_txt_template(parsed)
        first=next(r.offset for r in parsed.records if r.kind=='file' and r.extension=='txt')
        self.assertNotEqual(selected,first) # This is the original failure trigger.
        from infocarry.new_txt import build_new_nested_txt_add
        from infocarry.root_txt_placement import _nested_parent
        parent,offset=_nested_parent(parsed,helpers.TARGET)
        other=build_new_nested_txt_add(bundle.before_backup.directory,case[1],case[1].name,
            target_directory_path=parent,target_directory_offset=offset,source_template_offset=first,
            available_capacity_bytes=bundle.capacity_response.capacity_limit_bytes-len(parsed.data),
            record_timestamp_be32=bundle.candidate.audit_dict()['disposable_placement']['record_timestamp_be32'])
        self.assertEqual(other.candidate_blob,bundle.candidate.candidate_blob)
        self.assertEqual(other.transaction,bundle.candidate.transaction)
        self.assertNotEqual(other.audit_dict()['template'],bundle.candidate.audit_dict()['template'])
        identity=_nested_txt_template_provenance(parsed,selected)
        op={'template_offset':selected,'template_provenance':identity}
        require_nested_placement_provenance(parsed,op,bundle.candidate.audit_dict())
        for key,value in [('template_offset',first),('template_provenance',_nested_txt_template_provenance(parsed,first))]:
            bad=deepcopy(op);bad[key]=value
            with self.assertRaisesRegex(ValueError,'provenance'):
                require_nested_placement_provenance(parsed,bad,bundle.candidate.audit_dict())
        bad=deepcopy(op);bad['template_provenance']['payload_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'provenance'):
            require_nested_placement_provenance(parsed,bad,bundle.candidate.audit_dict())
        envelope,_=prep.prepare(bundle.before_backup.directory,Path(bundle.capacity_artifact.path),case[0]/'replay',timestamp=1792000000,source_head='a'*40)
        self.assertEqual(envelope['operations'][0]['template_offset'],selected)
        self.assertEqual(envelope['operations'][0]['template_provenance'],identity)


class DeletionOnlyPreparationTests(unittest.TestCase):
    def case(self, *, after_mutation=None):
        helper=helpers.NestedTxtDeleteExecutionTests();self.addCleanup(helper.doCleanups)
        case=helper.setup_case(reconnect=True)
        root=case[0];now=datetime.now(timezone.utc)
        placed=_write_archive(root/'placed',case[2]['blob'],now,fixed_state=case[2]['fixed'])
        core=build_nested_txt_validation_delete(placed,helpers.TARGET)
        restored=_write_archive(root/'restored',core.candidate_blob,now,fixed_state=dict(zip(range(0x1b,0x20),core.fixed_state.after)))
        restoration=dict(verify_fresh_backup(restored).object_sha256_by_key)
        capacity=root/'capacity.bin';capacity.write_bytes(case[2]['capacity'].raw_response)
        original={'task':'P18-049','target':helpers.TARGET,'target_record_offset':0x300,
            'baseline_objects':restoration,'capacity':case[2]['capacity'].to_dict(),
            'operations':[{'candidate_sha256':verify_fresh_backup(placed).blob_sha256,'transaction_sha256':'f'*64},
                          {'transaction_sha256':core.transaction_sha256}]}
        original_path=root/'original.json';original_path.write_text(json.dumps(original))
        original_sha=hashlib.sha256(original_path.read_bytes()).hexdigest()
        result={'ordinal':1,'completion':0,'sender_calls':1,'automatic_retries':0,
            'after_backup':str(placed),'after_manifest_sha256':verify_fresh_backup(placed).manifest_sha256,
            'after_objects':dict(verify_fresh_backup(placed).object_sha256_by_key),'transaction_sha256':'f'*64,
            'envelope_sha256':original_sha,'audit':{'state':'readback_verified','completion':'0x0000',
                'workflow':{'sender_calls':1},'execution_claim':{'sender_marker':{'resolved':True}}}}
        result_path=root/'placement.json';result_path.write_text(json.dumps(result))
        resolution=root/'resolution.json';resolution.write_text(json.dumps({'status':'RESOLVED_FOR_NEW_DELETION_TASK',
            'original_envelope_sha256':original_sha,'original_authority_reused':False}))
        self.enterContext(patch.object(prep,'PLACEMENT_ENVELOPE_SHA256',original_sha))
        self.enterContext(patch.object(prep,'PLACEMENT_RESULT_SHA256',hashlib.sha256(result_path.read_bytes()).hexdigest()))
        return case,placed,restored,capacity,original_path,result_path,resolution

    def freeze(self,data,**kw):
        case,placed,restored,capacity,original,result,resolution=data
        values=dict(source_head='a'*40,restoration_backup=restored,placement_result=result,
                    original_envelope=original,resolution_record=resolution);values.update(kw)
        return prep.prepare_delete_only(placed,capacity,case[0]/'deletion-only',**values)

    def prepared(self,data):
        case,placed,restored,*_=data
        model=DesktopWorkflowModel();model.load_backup(placed)
        service=DeviceLibraryDeleteService(lambda:case[4].runtime,validation_target=helpers.TARGET,
            restoration_objects=dict(verify_fresh_backup(restored).object_sha256_by_key))
        prepared=service.prepare(service.select(model,[0x300]));case[2]['bundle']=prepared.bundle
        return service,prepared

    def test_only_one_delete_existing_target_no_placement_and_strict_original_restoration(self):
        data=self.case();envelope,digest=self.freeze(data)
        self.assertEqual(len(digest),64)
        self.assertEqual(envelope['maximum_sender_invocations'],1)
        self.assertEqual([x['operation'] for x in envelope['operations']],['delete_existing_nested_txt'])
        self.assertIsNone(envelope['owner_approval']);self.assertEqual(envelope['physical_writes_performed'],0)
        service,prepared=self.prepared(data)
        service.bind_deletion_task(prepared,envelope,source_head='a'*40)
        result=service.execute_once(prepared,confirmed=True)
        self.assertEqual(result.audit['workflow']['sender_calls'],1)
        self.assertEqual(dict(result.after_backup.object_sha256_by_key),envelope['restoration_objects'])
        self.assertIsNone(data[0][5].read_sender_in_flight())
        with self.assertRaises(Exception):service.execute_once(prepared,confirmed=True)

    def test_cannot_execute_restoration_profile_without_binding_task(self):
        data=self.case();service,prepared=self.prepared(data)
        with self.assertRaisesRegex(Exception,'task must be bound'):
            service.execute_once(prepared,confirmed=True)
        self.assertEqual(data[0][3].calls,[])
        self.assertIsNone(data[0][5].read_claim(prepared.bundle.seal_sha256))

    def test_task_drift_cannot_be_hidden_by_equal_candidate_hash(self):
        for mutation in ('target','offset','source','capacity','native_record','restoration','extra_write','baseline','retry'):
            with self.subTest(mutation=mutation):
                data=self.case();envelope,_=self.freeze(data);service,prepared=self.prepared(data)
                bad=deepcopy(envelope)
                if mutation=='target':bad['target']='root\\other.txt'
                elif mutation=='offset':bad['operations'][0]['target_record_offset']+=64
                elif mutation=='source':bad['source_head']='b'*40
                elif mutation=='capacity':bad['capacity']['capacity_limit_bytes']+=4
                elif mutation=='native_record':bad['target_profile']['record_sha256']='0'*64
                elif mutation=='restoration':bad['restoration_objects']['0x0024:response-0024']='0'*64
                elif mutation=='extra_write':bad['operations'].append(deepcopy(bad['operations'][0]))
                elif mutation=='baseline':bad['baseline_objects']['0x8004:backup-blob-probe']='0'*64
                else:bad['automatic_retry_allowed']=True
                with self.assertRaises(ValueError):service.bind_deletion_task(prepared,bad,source_head='a'*40)
                self.assertEqual(data[0][3].calls,[])
                self.assertIsNone(data[0][5].read_claim(prepared.bundle.seal_sha256))
                service.discard()

    def test_payload_dependent_object_failure_keeps_lock_after_single_sender(self):
        for key in ('0x0024:response-0024','0x8004:backup-blob-probe'):
            with self.subTest(key=key):
                data=self.case();envelope,_=self.freeze(data);service,prepared=self.prepared(data)
                runtime=prepared.bundle.runtime;capture=runtime.capture
                def bad_capture(destination, **kw):
                    capture(destination,**kw)
                    if destination.name=='backup-after-0001':
                        manifest=json.loads((destination/'manifest.json').read_bytes())
                        obj=next(x for x in manifest['objects'] if x['command']+':'+x['kind']==key)
                        p=destination/obj['filename'];p.write_bytes(bytes(64));obj['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
                        (destination/'manifest.json').write_text(json.dumps(manifest))
                object.__setattr__(runtime,'capture',bad_capture)
                service.bind_deletion_task(prepared,envelope,source_head='a'*40)
                with self.assertRaises(Exception):service.execute_once(prepared,confirmed=True)
                self.assertEqual(sum(x[0]=='control_out' for x in data[0][3].calls),1)
                self.assertTrue(data[0][6].path.exists())
                self.assertIsNotNone(data[0][5].read_sender_in_flight())

    def test_original_identity_resolution_and_fresh_state_drift_refuse(self):
        for mutation in ('original','placement','resolution','fresh'):
            data=self.case();case,placed,restored,capacity,original,result,resolution=data
            if mutation=='original':original.write_text(original.read_text()+' ')
            elif mutation=='placement':result.write_text(result.read_text()+' ')
            elif mutation=='resolution':
                d=json.loads(resolution.read_bytes());d['original_authority_reused']=True;resolution.write_text(json.dumps(d))
            else:
                d=json.loads((placed/'manifest.json').read_bytes());d['objects'][0]['sha256']='0'*64;(placed/'manifest.json').write_text(json.dumps(d))
            with self.assertRaises(Exception):self.freeze(data)
            self.assertEqual(case[3].calls,[])
