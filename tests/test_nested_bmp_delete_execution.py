"""Exact nested BMP experiment; fake transports and isolated safety stores only."""
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import importlib.util
import sys
import unittest
from unittest.mock import patch

from infocarry.backup_format import parse_backup_blob
from infocarry.backup_repack import rename_existing_record
from infocarry.delete_generalized import bind_generalized_delete_sender
from infocarry.delete_model import verify_nested_file_delete_model
from infocarry.delete_workflow import (
    ExperimentalRootTxtDeleteFacade, build_nested_bmp_validation_delete,
    NESTED_BMP_DELETE_VALIDATION_PATH as TARGET,
    NESTED_BMP_DELETE_VALIDATION_PROFILE as PROFILE,
    ROOT_BMP_DELETE_FIXTURE_BYTES as PAYLOAD,
)
from infocarry.desktop import DesktopWorkflowModel
from infocarry.device_library_delete_execution import DeviceLibraryDeleteService
from infocarry.write_protocol import REQUEST_BEGIN_TRANSMIT
SOURCE_HEAD = 'a' * 40
try:
    from test_nested_file_delete import nested_library
    from test_new_txt import _write_archive
    from test_root_bmp_delete_model import _checksum
    import test_root_txt_placement as placement_helpers
    import test_device_library_delete_ui as ui_helpers
except ModuleNotFoundError:
    from tests.test_nested_file_delete import nested_library
    from tests.test_new_txt import _write_archive
    from tests.test_root_bmp_delete_model import _checksum
    from tests import test_root_txt_placement as placement_helpers
    from tests import test_device_library_delete_ui as ui_helpers


def named_baseline(**kwargs):
    blob = nested_library(**kwargs)
    for offset, name in ((0xc0, 'IC_P18_040_NESTED_20260930_01'), (0x200, 'Section-A')):
        blob = rename_existing_record(parse_backup_blob(blob), offset, name)
    return blob


class NestedBmpDeleteExecutionTests(unittest.TestCase):
    def setup_placement(self, **kwargs):
        helper = placement_helpers.RootPlacementTests()
        self.addCleanup(helper.doCleanups)
        case = helper.setup_case(media='bmp', **kwargs)
        case[2]['blob'] = named_baseline()
        case[2]['fixed'] = {c: bytes(64) for c in range(0x1b, 0x20)}
        source = case[0] / TARGET.rsplit('\\', 1)[-1]
        source.write_bytes(PAYLOAD)
        return (case[0], source, *case[2:])

    def prepare_placement(self, case, *, bind=True, **kwargs):
        values = dict(target_path=TARGET, validation_placement=True,
                      placement_media='bmp', nested_validation=True)
        values.update(kwargs)
        bundle = case[4].prepare(case[1], **values)
        case[2]['bundle'] = bundle
        if 'envelope' not in case[2]:
            scripts = Path(__file__).resolve().parents[1] / 'scripts'
            with patch.object(sys, 'path', [str(scripts), *sys.path]):
                spec = importlib.util.spec_from_file_location('nested_bmp_test_preparation', scripts/'prepare_nested_bmp_validation.py')
                module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
                capacity_path = case[0] / 'capacity.bin'
                capacity_path.write_bytes(case[2]['capacity'].raw_response)
                envelope, _digest = module.prepare_experiment(bundle.before_backup.directory,
                    capacity_path, case[0]/'experiment', timestamp=1791040000,
                    source_head=SOURCE_HEAD, archive_replay=False)
            case[2]['envelope'] = envelope
        if bind:
            case[4].bind_task(case[2]['envelope'], source_head=SOURCE_HEAD)
        return bundle

    def execute(self, case, bundle):
        case[4].authorize_prepared_operation(case[4].owner_authorization_identity.approval_phrase)
        return case[4].execute_once(confirmation_interaction=lambda _: bundle.authorization.core.confirmation_phrase)

    def placed_case(self, **kwargs):
        placement = self.setup_placement()
        added = self.prepare_placement(placement)
        actual = self.execute(placement, added)
        case = self.setup_placement(**kwargs)
        case[2]['blob'] = added.candidate.candidate_blob
        transaction = added.candidate.transaction
        case[2]['fixed'] = dict(zip(range(0x1b, 0x20),
            tuple(transaction.ranges[0][i:i+64] for i in range(0, 256, 64)) + (transaction.ranges[1],)))
        restoration = dict(added.before_backup.object_sha256_by_key)
        case[2]['envelope'] = placement[2]['envelope']
        case[2]['placement_result'] = actual
        return ((*case[:4], ExperimentalRootTxtDeleteFacade(case[4].runtime), *case[5:]),
                restoration, placement, added)

    def prepare(self, case, restoration, *, bind=True, **kwargs):
        values = dict(target_path=TARGET, nested_validation=True, restoration_objects=restoration)
        values.update(kwargs)
        bundle = case[4].prepare(**values)
        case[2]['bundle'] = bundle
        if bind:
            case[4].bind_task(case[2]['envelope'], source_head=SOURCE_HEAD,
                             placement_result=case[2]['placement_result'])
        return bundle

    def archive(self, case, blob=None, fixed=None):
        path = case[0] / ('archive-' + str(len(list(case[0].glob('archive-*')))))
        return _write_archive(path, case[2]['blob'] if blob is None else blob,
                              datetime.now(timezone.utc),
                              fixed_state=case[2]['fixed'] if fixed is None else fixed)

    def no_send(self, case, bundle=None):
        self.assertEqual(case[3].calls, [])
        self.assertIsNone(case[5].read_sender_in_flight())
        if bundle is not None:
            self.assertIsNone(case[5].read_claim(bundle.seal_sha256))

    def test_exact_two_operation_replay_restores_every_native_object(self):
        placement = self.setup_placement(reconnect=True)
        # Active surviving references and opaque tails must survive both writes.
        history=bytearray(64);history[:4]=(1).to_bytes(4,'big')
        history[8:12]=(0x100-64).to_bytes(4,'big');history[-1]=0xa5
        bookmark=bytearray(64);bookmark[:20]=b''.join(v.to_bytes(4,'big') for v in (0x300-64,1,2,3,4))
        bookmark[-1]=0x5a
        placement[2]['fixed'][0x1b]=bytes(history)
        placement[2]['fixed'][0x1f]=bytes(bookmark)
        baseline = placement[2]['blob']
        added = self.prepare_placement(placement)
        added.verify_seal()
        self.no_send(placement, added)
        placement[2]['session'] = 'equivalent-placement-session'
        placed = self.execute(placement, added)
        case = self.setup_placement(reconnect=True)
        case[2]['blob'], case[2]['fixed'] = placement[2]['blob'], placement[2]['fixed']
        case[2]['envelope'], case[2]['placement_result'] = placement[2]['envelope'], placed
        # Both operations use the same installation-wide claims and lock.
        runtime = replace(case[4].runtime, execution_claim_store=placement[5],
                          indeterminate_write_lock=placement[6])
        case = (*case[:4], ExperimentalRootTxtDeleteFacade(runtime), placement[5], placement[6])
        restoration = dict(added.before_backup.object_sha256_by_key)
        deleted = self.prepare(case, restoration)
        self.assertNotEqual(added.seal_sha256, deleted.seal_sha256)
        self.assertNotEqual(added.before_backup.directory, deleted.before_backup.directory)
        self.assertEqual(deleted.candidate.candidate_blob, baseline)
        case[2]['session'] = 'equivalent-delete-session'
        final = self.execute(case, deleted)
        self.assertEqual(dict(final.after_backup.object_sha256_by_key), restoration)
        for index in range(1, 9):
            self.assertEqual((added.before_backup.directory / f'object-{index:02}.bin').read_bytes(),
                             (final.after_backup.directory / f'object-{index:02}.bin').read_bytes())
        for operation, result in ((added, placed), (deleted, final)):
            self.assertEqual(result.completion, 0)
            self.assertEqual(result.audit['workflow']['sender_calls'], 1)
            self.assertIsNotNone(case[5].read_claim(operation.seal_sha256))
        self.assertEqual(sum(c[0] == 'control_out' and c[1] == REQUEST_BEGIN_TRANSMIT
                             for c in placement[3].calls + case[3].calls), 2)
        self.assertIsNone(case[5].read_sender_in_flight())
        self.assertFalse(case[6].path.exists())
        with self.assertRaises(Exception): self.execute(case, deleted)
        self.assertEqual(sum(c[0] == 'control_out' for c in case[3].calls), 1)

    def test_frozen_bundle_exact_native_profile_and_general_sender_stays_closed(self):
        case, restoration, _, _ = self.placed_case()
        bundle = self.prepare(case, restoration)
        bundle.verify_seal()
        core = bundle.candidate.core
        record = core.baseline.record_at(core.target_record_offset)
        self.assertEqual(bundle.operation_profile, PROFILE)
        self.assertEqual(core.target_path, TARGET)
        self.assertEqual(record.extension, 'bmp')
        self.assertEqual((record.flag, record.field_10_be32, record.field_14_be32),
                         (0xe0, 0xffffffff, 0x100))
        self.assertEqual(core.baseline.payload_parts(record), (b'\xff' * 16, PAYLOAD))
        self.assertFalse(core.to_dict()['safety']['execution_available'])
        self.assertEqual(dict(bundle.restoration_objects), restoration)
        with self.assertRaisesRegex(Exception, 'nested'):
            bind_generalized_delete_sender(bundle.authorization.core.binding, core)
        self.no_send(case, bundle)

    def test_placement_template_provenance_matches_actual_candidate_fields(self):
        case = self.setup_placement()
        bundle = self.prepare_placement(case)
        audit = bundle.candidate.audit_dict()
        before = parse_backup_blob(case[2]['blob'])
        after = parse_backup_blob(bundle.candidate.candidate_blob)
        template = before.record_at(int(audit['template']['record_offset_hex'], 16))
        target = after.record_at(int(audit['target']['record_offset_hex'], 16))
        source_raw, target_raw = bytes.fromhex(template.raw_hex), bytes.fromhex(target.raw_hex)
        for start, end in ((0, 4), (16, 24)):
            self.assertEqual(source_raw[start:end], target_raw[start:end])
        self.assertEqual(before.payload_parts(template)[0], after.payload_parts(target)[0])
        self.assertEqual(after.payload_parts(target)[1], PAYLOAD)
        self.assertEqual(audit['template']['copied_record_fields_sha256'],
                         hashlib.sha256(source_raw[:4]+source_raw[16:24]).hexdigest())
        self.assertEqual(audit['template']['record_sha256'],hashlib.sha256(source_raw).hexdigest())
        self.assertEqual(audit['template']['payload_sha256'],
                         hashlib.sha256(before.payload_parts(template)[1]).hexdigest())
        self.assertEqual(audit['template']['prefix_sha256'],
                         hashlib.sha256(before.payload_parts(template)[0]).hexdigest())
        self.assertEqual(target.timestamp_be32, 1791040000)

    def test_missing_or_incomplete_restoration_identity_refuses_before_sender(self):
        for variant in ('none', 'missing', 'wrong', 'bool'):
            with self.subTest(variant=variant):
                case, restoration, _, _ = self.placed_case()
                bad = None if variant == 'none' else dict(restoration)
                if variant == 'missing': bad.pop('0x0024:response-0024')
                elif variant == 'wrong': bad['0x8004:backup-blob'] = '0' * 64
                elif variant == 'bool': bad['0x8004:backup-blob'] = True
                with self.assertRaises(Exception): self.prepare(case, bad)
                self.no_send(case)

    def test_explicit_scope_flags_model_path_and_media_refuse(self):
        for values in ({'nested_validation':False}, {'nested_validation':1},
                       {'general_txt':True}, {'general_bmp':True}, {'general_nested_txt':True},
                       {'validation_bmp_only':True}, {'device_model':'VNW-V10'},
                       {'target_path':TARGET.replace('Section-A', 'Section-B')}):
            with self.subTest(values=values):
                case, restoration, _, _ = self.placed_case()
                with self.assertRaises(Exception): self.prepare(case, restoration, **values)
                self.no_send(case)
        for values in ({'placement_media':'txt'}, {'nested_validation':False},
                       {'validation_placement':False}, {'device_model':'VNW-V10'}):
            with self.subTest(placement=values):
                case = self.setup_placement()
                with self.assertRaises(Exception): self.prepare_placement(case, **values)
                self.no_send(case)

    def test_read_selector_opaque_prefix_payload_name_and_offset_refuse(self):
        case, _, _, _ = self.placed_case()
        blob = case[2]['blob']; parsed = parse_backup_blob(blob)
        target = next(o for o,p in parsed.paths.items() if '\\'.join(p)+'.bmp' == TARGET)
        content = parsed.header.content_start + parsed.record_at(target).field_04_be32
        mutations = {'read':(target,b'\x20'), 'selector':(target+20,(0x200).to_bytes(4,'big')),
                     'opaque':(target+16,bytes(4)), 'prefix':(content,b'\x00'),
                     'payload':(content+16+100,b'\x01'),
                     'name':(target+24,b'X')}
        for label,(offset,value) in mutations.items():
            with self.subTest(label=label):
                changed = bytearray(blob); changed[offset:offset+len(value)] = value
                with self.assertRaises(Exception):
                    build_nested_bmp_validation_delete(self.archive(case,_checksum(changed)),TARGET)
        archive = self.archive(case)
        for wrong in (target+64, target+1, True):
            with self.subTest(offset=wrong), self.assertRaises(Exception):
                build_nested_bmp_validation_delete(archive,TARGET,target_record_offset=wrong)
        changed=bytearray(blob)
        duplicate=TARGET.rsplit('\\',1)[-1][:-4].lower().encode('ascii')
        changed[0x300+24:0x340]=duplicate+bytes(40-len(duplicate))
        with self.assertRaises(Exception):
            build_nested_bmp_validation_delete(self.archive(case,_checksum(changed)),TARGET)
        unsupported=self.archive(case)
        manifest=json.loads((unsupported/'manifest.json').read_bytes())
        manifest['device']['product_id']='0xdead'
        (unsupported/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(Exception):build_nested_bmp_validation_delete(unsupported,TARGET)
        self.no_send(case)

    def test_parent_ownership_markers_allocation_ordering_and_checksum_refuse(self):
        case, _, _, _ = self.placed_case(); blob = case[2]['blob']
        parsed = parse_backup_blob(blob)
        variants = []
        # Missing/foreign parent marker, overlapping child-table ownership,
        # overlapping survivor allocations and a target moved outside its parent.
        for offset,value in ((0x280+4,(0xdead).to_bytes(4,'big')),
                             (0x200+4,(0x140).to_bytes(4,'big')),
                             (0x100+4,parsed.record_at(0x240).field_04_be32.to_bytes(4,'big')),
                             (0x280+24,b'not-marker\0')):
            changed=bytearray(blob);changed[offset:offset+len(value)]=value;variants.append(_checksum(changed))
        target=next(o for o,p in parsed.paths.items() if '\\'.join(p)+'.bmp' == TARGET)
        changed=bytearray(blob);changed[0x240:0x280],changed[target:target+64]=changed[target:target+64],changed[0x240:0x280]
        variants.append(_checksum(changed))
        changed=bytearray(blob);changed[-1]^=1;variants.append(bytes(changed))
        for index,changed in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(Exception):
                build_nested_bmp_validation_delete(self.archive(case,changed),TARGET)
        self.no_send(case)

    def test_target_references_active_marks_and_unknown_protected_state_refuse(self):
        case, _, _, _ = self.placed_case(); parsed=parse_backup_blob(case[2]['blob'])
        target=next(o for o,p in parsed.paths.items() if '\\'.join(p)+'.bmp' == TARGET)
        for command in range(0x1b,0x20):
            with self.subTest(command=command):
                fixed=dict(case[2]['fixed']);raw=bytearray(64)
                if command==0x1f:
                    raw[:4]=(target-64).to_bytes(4,'big');raw[8:12]=(0x80000000).to_bytes(4,'big')
                else:
                    raw[:4]=(1).to_bytes(4,'big');raw[8:12]=(target-64).to_bytes(4,'big')
                fixed[command]=bytes(raw)
                with self.assertRaises(Exception):
                    build_nested_bmp_validation_delete(self.archive(case,fixed=fixed),TARGET)
        self.no_send(case)

    def test_independent_final_verifier_preserves_timestamps_payloads_and_markers(self):
        case, _, _, _ = self.placed_case()
        core=build_nested_bmp_validation_delete(self.archive(case),TARGET)
        final=parse_backup_blob(core.candidate_blob)
        with patch('infocarry.delete_model.delete_existing_file',side_effect=AssertionError('repacker called')):
            verify_nested_file_delete_model(core.baseline,core.candidate_blob,TARGET,core.target_record_offset)
        for offset in (0x100+12,0x280+8,final.header.content_start+16):
            changed=bytearray(core.candidate_blob);changed[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(Exception):
                verify_nested_file_delete_model(core.baseline,_checksum(changed),TARGET,core.target_record_offset)

    def test_changed_frozen_identity_source_and_fresh_state_refuse_unclaimed(self):
        for variant in ('offset','scope','payload','state','owner'):
            with self.subTest(variant=variant):
                case,restoration,_,_=self.placed_case();bundle=self.prepare(case,restoration)
                case[4].authorize_prepared_operation(case[4].owner_authorization_identity.approval_phrase)
                if variant=='offset':case[4]._prepared_operation=replace(bundle,candidate=replace(bundle.candidate,target_record_offset=0x240))
                elif variant=='scope':case[4]._prepared_operation=replace(bundle,candidate=replace(bundle.candidate,nested_validation=False))
                elif variant=='payload':bundle.source_path.write_bytes(PAYLOAD+b'x')
                elif variant=='state':case[2]['blob']=named_baseline()
                else:case[4]._owner_authorized_identity=replace(case[4]._owner_authorized_identity,candidate_blob_sha256='0'*64)
                with self.assertRaises(Exception):case[4].execute_once(confirmation_interaction=lambda _:bundle.authorization.core.confirmation_phrase)
                self.no_send(case,bundle)

    def test_both_operations_require_the_complete_bound_two_write_task(self):
        placement=self.setup_placement();added=self.prepare_placement(placement,bind=False)
        with self.assertRaises(Exception):self.execute(placement,added)
        self.no_send(placement,added)
        case,restoration,_,_=self.placed_case();deleted=self.prepare(case,restoration,bind=False)
        with self.assertRaises(Exception):self.execute(case,deleted)
        self.no_send(case,deleted)

    def test_task_limits_provenance_baseline_and_operation_identity_refuse(self):
        for variant in ('senders','extra','retry','source','archive','parent','timestamp',
                        'candidate','transaction','template','baseline'):
            with self.subTest(variant=variant):
                case=self.setup_placement();bundle=self.prepare_placement(case,bind=False)
                envelope=json.loads(json.dumps(case[2]['envelope']))
                if variant=='senders':envelope['maximum_sender_invocations']=3
                elif variant=='extra':envelope['extra_setup_or_cleanup_writes']=1
                elif variant=='retry':envelope['automatic_retry_allowed']=True
                elif variant=='source':envelope['source_head']='b'*40
                elif variant=='archive':envelope['status']='archive_replay_only'
                elif variant=='parent':envelope['parent_record_offset']+=64
                elif variant=='timestamp':envelope['placement_timestamp_be32']+=1
                elif variant=='candidate':envelope['operations'][0]['candidate_sha256']='0'*64
                elif variant=='transaction':envelope['operations'][0]['transaction_sha256']='0'*64
                elif variant=='template':envelope['operations'][0]['template_offset']+=64
                else:envelope['baseline_objects']['0x0024:response-0024']='0'*64
                with self.assertRaises(Exception):case[4].bind_task(envelope,source_head=SOURCE_HEAD)
                self.no_send(case,bundle)

    def test_delete_requires_untampered_verified_actual_placement_result(self):
        case,restoration,_,_=self.placed_case();bundle=self.prepare(case,restoration,bind=False)
        actual=case[2]['placement_result']
        bad_results=[None,replace(actual,completion=True),replace(actual,completion=1),
                     replace(actual,preflight=bundle),replace(actual,after_backup=actual.before_backup)]
        for field,value in (('state','failed'),('completion','0x0001'),
                            ('workflow',{'sender_calls':2}),
                            ('execution_claim',{'sender_marker':{'resolved':False}})):
            audit=json.loads(json.dumps(actual.audit));audit[field]=value
            bad_results.append(replace(actual,audit=audit))
        for index,bad in enumerate(bad_results):
            with self.subTest(index=index),self.assertRaises(Exception):
                case[4].bind_task(case[2]['envelope'],source_head=SOURCE_HEAD,placement_result=bad)
        self.no_send(case,bundle)

    def test_ambiguous_nonzero_and_bad_readback_stop_after_one_sender(self):
        for mode in ('disconnect','nonzero','readback'):
            with self.subTest(mode=mode):
                options={'fail_bulk_at':1} if mode=='disconnect' else {'completion':(2,)} if mode=='nonzero' else {}
                case,restoration,_,_=self.placed_case(backend_options=options)
                bundle=self.prepare(case,restoration)
                if mode=='readback':case[2]['after_bad']=True
                with self.assertRaises(Exception):self.execute(case,bundle)
                self.assertEqual(sum(c[0]=='control_out' for c in case[3].calls),1)
                self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
                if mode!='nonzero':
                    self.assertTrue(case[6].path.exists());self.assertIsNotNone(case[5].read_sender_in_flight())
                with self.assertRaises(Exception):self.execute(case,bundle)
                self.assertEqual(sum(c[0]=='control_out' for c in case[3].calls),1)

    def test_placement_failure_stops_experiment_after_one_sender(self):
        for mode in ('disconnect','nonzero','readback'):
            with self.subTest(mode=mode):
                options={'fail_bulk_at':1} if mode=='disconnect' else {'completion':(2,)} if mode=='nonzero' else {}
                case=self.setup_placement(backend_options=options);bundle=self.prepare_placement(case)
                if mode=='readback':case[2]['after_bad']=True
                with self.assertRaises(Exception):self.execute(case,bundle)
                self.assertEqual(sum(c[0]=='control_out' for c in case[3].calls),1)
                self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
                if mode!='nonzero':
                    self.assertTrue(case[6].path.exists());self.assertIsNotNone(case[5].read_sender_in_flight())
                with self.assertRaises(Exception):self.execute(case,bundle)
                self.assertEqual(sum(c[0]=='control_out' for c in case[3].calls),1)

    def test_auxiliary_or_probe_drift_stops_after_one_sender_and_keeps_lock(self):
        for key in ('0x0024:response-0024','0x8004:backup-blob-probe'):
            with self.subTest(key=key):
                case,restoration,_,_=self.placed_case();bundle=self.prepare(case,restoration)
                runtime=bundle.runtime;capture=runtime.capture
                def bad_capture(destination,**kwargs):
                    capture(destination,**kwargs)
                    if destination.name=='backup-after-0001':
                        manifest=json.loads((destination/'manifest.json').read_bytes())
                        obj=next(x for x in manifest['objects'] if x['command']+':'+x['kind']==key)
                        path=destination/obj['filename'];path.write_bytes(bytes(64));obj['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
                        (destination/'manifest.json').write_text(json.dumps(manifest))
                object.__setattr__(runtime,'capture',bad_capture)
                with self.assertRaises(Exception):self.execute(case,bundle)
                self.assertEqual(sum(c[0]=='control_out' for c in case[3].calls),1)
                self.assertTrue(case[6].path.exists());self.assertIsNotNone(case[5].read_sender_in_flight())

    def data(self):
        case,restoration,_,_=self.placed_case()
        model=DesktopWorkflowModel();model.load_backup(self.archive(case))
        service=DeviceLibraryDeleteService(lambda:case[4].runtime,validation_target=TARGET,
                                           restoration_objects=restoration)
        original_prepare=service.prepare
        def prepare_and_bind(*args,**kwargs):
            prepared=original_prepare(*args,**kwargs)
            service.bind_deletion_task(prepared,case[2]['envelope'],source_head=SOURCE_HEAD,
                                      placement_result=case[2]['placement_result'])
            return prepared
        service.prepare=prepare_and_bind
        target=next(r.record_offset for r in model.rows() if r.display_name==TARGET)
        return case,model,service.select(model,[target]),service

    def test_normal_library_refuses_and_validation_uses_existing_single_dialog(self):
        case,model,selection,service=self.data()
        normal=DeviceLibraryDeleteService(lambda:case[4].runtime)
        self.assertFalse(normal.execution_available(selection))
        with self.assertRaises(ValueError):normal.select(model,[selection.row.record_offset])
        helper=ui_helpers.DeviceLibraryDeleteUITests();self.addCleanup(helper.doCleanups)
        ui=helper.setup_ui(data_override=(case,model,selection,service));ui.action();ui.drain()
        self.assertEqual(len(ui.dialogs),1);self.assertEqual(len(ui.refreshes),1)
        self.assertIn('Delete complete',ui.statuses.get());self.assertNotIn(TARGET,ui.refreshes[0])

    def test_cancel_has_no_claim_sender_or_marker(self):
        data=self.data();helper=ui_helpers.DeviceLibraryDeleteUITests();self.addCleanup(helper.doCleanups)
        ui=helper.setup_ui(confirmed=False,data_override=data);ui.action();ui.drain()
        self.assertEqual(len(ui.dialogs),1);self.no_send(data[0])


if __name__ == '__main__':
    unittest.main()
