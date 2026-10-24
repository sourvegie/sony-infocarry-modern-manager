#!/usr/bin/env python3
"""Freeze the two-write nested TXT experiment offline. Never opens USB or sends.

Input must be a fresh complete read-only backup and native capacity response.
--archive-replay labels older evidence as simulation only; it cannot produce a
hardware approval request. Raw derived archives stay outside the repository.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / 'src'))
from infocarry.backup_format import parse_backup_blob
from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.device_info import RawInfoResponse
from infocarry.delete_workflow import (
    NESTED_TXT_DELETE_VALIDATION_PATH as TARGET,
    NESTED_TXT_DELETE_VALIDATION_BYTES as PAYLOAD,
    build_nested_txt_validation_delete,
)
from infocarry.delete_generalized import build_nested_file_delete_candidate, verify_nested_file_delete_readback
from infocarry.new_txt import build_new_nested_txt_add
from infocarry.root_txt_placement import (
    _blob, _json, _nested_parent, _nested_disposable_delta, _write_json,
    _select_nested_txt_template, _nested_txt_template_provenance, require_nested_placement_provenance,
)
from infocarry.prepared_library_package_live_adapter import _backup_identity
from infocarry.write_gate import verify_fresh_backup


PLACEMENT_ENVELOPE_SHA256 = 'eae6909886fbbfc10ab2e21d7e773c71ea9624ab1843f837960d7466648200a5'
PLACEMENT_RESULT_SHA256 = 'be977c0ab9fd97dd49c43d414ce0a0fe0c72d96714080fb7a76aec27efab450b'

def simulated_archive(source, destination, candidate_blob, transaction):
    """Copy all eight verified objects; replace only derived dynamic/fixed bytes."""
    destination.mkdir()
    manifest = json.loads((source.directory / 'manifest.json').read_bytes())
    fixed = {0x1b: transaction.ranges[0][:64], 0x1c: transaction.ranges[0][64:128],
             0x1d: transaction.ranges[0][128:192], 0x1e: transaction.ranges[0][192:256],
             0x1f: transaction.ranges[1]}
    for entry in manifest['objects']:
        command = int(entry['command'], 16)
        data = (source.directory / entry['filename']).read_bytes()
        if entry['kind'] == 'backup-blob':
            data = candidate_blob
        elif command in fixed:
            data = fixed[command]
        (destination / entry['filename']).write_bytes(data)
        entry.update(sha256=hashlib.sha256(data).hexdigest(), requested_length=len(data), received_length=len(data))
    manifest['created_at_utc'] = manifest['updated_at_utc'] = datetime.now(timezone.utc).isoformat()
    (destination / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    return verify_fresh_backup(destination)


def prepare(backup_directory, capacity_path, output, *, timestamp, source_head, archive_replay=False):
    if not isinstance(source_head, str) or len(source_head) != 40 or any(c not in '0123456789abcdef' for c in source_head):
        raise ValueError('source head must identify the independently reviewed exact commit')
    output = Path(output).expanduser().resolve()
    if output == REPOSITORY_ROOT or REPOSITORY_ROOT in output.parents:
        raise ValueError('raw simulation and frozen evidence must remain outside the source repository')
    baseline = verify_fresh_backup(Path(backup_directory), max_age_seconds=None if archive_replay else 300)
    if baseline.device_identity != ('0x054c','0x001e') or baseline.object_count != 8:
        raise ValueError('complete eight-object VNW-V15 baseline required')
    capacity = NativeCapacityResponse.from_hardware_response(
        RawInfoResponse(0x0019,'hardware-info',Path(capacity_path).read_bytes()),device_identity=(0x054c,0x001e))
    parsed = parse_backup_blob(_blob(baseline))
    parent_path,parent_offset = _nested_parent(parsed,TARGET)
    template_offset = _select_nested_txt_template(parsed)
    output.mkdir(parents=True,exist_ok=False)
    source = output / TARGET.split('\\')[-1];source.write_bytes(PAYLOAD)
    placed = build_new_nested_txt_add(baseline.directory,source,source.name,
        target_directory_path=parent_path,target_directory_offset=parent_offset,
        source_template_offset=template_offset,
        available_capacity_bytes=capacity.capacity_limit_bytes-len(parsed.data),
        record_timestamp_be32=timestamp,max_age_seconds=None if archive_replay else 300)
    capacity.bind_model_lengths(len(parsed.data),len(placed.candidate_blob))
    delta = _nested_disposable_delta(parsed.data,placed.candidate_blob,TARGET)
    placed_backup = simulated_archive(baseline,output/'simulated-placement',placed.candidate_blob,placed.transaction)
    removed = build_nested_txt_validation_delete(placed_backup.directory,TARGET)
    final = simulated_archive(placed_backup,output/'simulated-delete',removed.candidate_blob,removed.transaction)
    host = build_nested_file_delete_candidate(placed_backup.directory,TARGET,removed.target_record_offset)
    verify_nested_file_delete_readback(host,final.directory,completion=0)
    if dict(final.object_sha256_by_key) != dict(baseline.object_sha256_by_key):
        raise ValueError('two-operation replay did not restore all eight native objects exactly')
    target = parse_backup_blob(placed.candidate_blob).record_at(removed.target_record_offset)
    prefix = parse_backup_blob(placed.candidate_blob).payload_parts(target)[0]
    envelope = {
        'format':'infocarry-nested-txt-delete-task-envelope-v1','task':'P18-049',
        'status':'archive_replay_only' if archive_replay else 'prepared_for_independent_review',
        'source_head':source_head,'model':'VNW-V15','vendor_id':'0x054c','product_id':'0x001e',
        'baseline_manifest_sha256':baseline.manifest_sha256,
        'baseline_state_identity_sha256':_backup_identity(baseline).sha256,
        'baseline_objects':dict(baseline.object_sha256_by_key),
        'capacity':capacity.to_dict(),'target':TARGET,
        'parent_record_offset':parent_offset,'target_record_offset':target.offset,
        'fixture':{'bytes':len(PAYLOAD),'sha256':hashlib.sha256(PAYLOAD).hexdigest()},
        'native_profile':{'flag':'0xe0','opaque':'0xffffffff','selector':'0x200',
                          'prefix_bytes':len(prefix),'prefix_sha256':hashlib.sha256(prefix).hexdigest()},
        'placement_timestamp_be32':timestamp,
        'operations':[
            {'ordinal':1,'operation':'place_exact_nested_txt','target':TARGET,
             'template_offset':template_offset,
             'template_provenance':_nested_txt_template_provenance(parsed,template_offset),'candidate_sha256':hashlib.sha256(placed.candidate_blob).hexdigest(),
             'transaction_sha256':placed.transaction.concatenated_sha256,
             'growth_bytes':len(placed.candidate_blob)-len(parsed.data),'expected_added_paths':[TARGET],
             'expected_removed_paths':[],'sender_invocations':1},
            {'ordinal':2,'operation':'delete_same_nested_txt','target':TARGET,
             'candidate_sha256':removed.candidate_blob_sha256,'transaction_sha256':removed.transaction_sha256,
             'expected_added_paths':[],'expected_removed_paths':[TARGET],'sender_invocations':1},
        ],
        'maximum_sender_invocations':2,'extra_setup_or_cleanup_writes':0,
        'replay':{'eight_objects_return_to_baseline':True,'protected_state_preserved':True,'placement_delta':delta},
        'execution_policy':{
            'operation_identities':'freeze each existing operation bundle just in time; require exact envelope candidates/transactions and full prior verified state',
            'each_write':'fresh eight-object backup/native capacity; existing exact owner binding, durable claim, marker, global lock; one sender; native integer 0; independent complete post-backup',
            'abort':'stop on any mismatch, unsupported state, nonzero/malformed/missing completion, disconnect, ambiguity, backup or verification failure; no retry, recovery, cleanup or extra write',
            'final_state':'all eight native objects byte-identical to baseline; target absent; parent/siblings/markers/references/payloads/timestamps preserved',
        },
        'physical_writes_performed':0,'owner_approval':None,
    }
    require_nested_placement_provenance(parsed,envelope['operations'][0],placed.audit_dict())
    _write_json(output/'task-envelope.json',envelope)
    return envelope,hashlib.sha256(_json(envelope)).hexdigest()


def prepare_delete_only(backup_directory, capacity_path, output, *, source_head,
                        restoration_backup, placement_result, original_envelope,
                        resolution_record):
    """Prepare one Delete from actual placement evidence; never place or send."""
    if (type(source_head) is not str or len(source_head) != 40
            or any(c not in '0123456789abcdef' for c in source_head)):
        raise ValueError('reviewed source must be an exact commit')
    output = Path(output).expanduser().resolve()
    if output == REPOSITORY_ROOT or REPOSITORY_ROOT in output.parents:
        raise ValueError('private evidence must remain outside the repository')
    original_path = Path(original_envelope)
    original = json.loads(original_path.read_bytes())
    original_sha = hashlib.sha256(original_path.read_bytes()).hexdigest()
    if original_sha != PLACEMENT_ENVELOPE_SHA256:
        raise ValueError('original frozen experiment identity changed')
    resolution_path = Path(resolution_record)
    resolution = json.loads(resolution_path.read_bytes())
    if (original.get('task') != 'P18-049' or original.get('target') != TARGET
            or resolution.get('status') != 'RESOLVED_FOR_NEW_DELETION_TASK'
            or resolution.get('original_envelope_sha256') != original_sha
            or resolution.get('original_authority_reused') is not False):
        raise ValueError('separate reviewed provenance resolution is required; original authority cannot resume')
    result_path = Path(placement_result)
    if hashlib.sha256(result_path.read_bytes()).hexdigest() != PLACEMENT_RESULT_SHA256:
        raise ValueError('independently verified original placement result changed')
    result = json.loads(result_path.read_bytes())
    audit = result['audit']
    if (result.get('ordinal') != 1 or type(result.get('completion')) is not int or result['completion'] != 0
            or result.get('sender_calls') != 1 or result.get('automatic_retries') != 0
            or audit.get('state') != 'readback_verified' or audit.get('completion') != '0x0000'
            or audit.get('workflow', {}).get('sender_calls') != 1
            or audit.get('execution_claim', {}).get('sender_marker', {}).get('resolved') is not True
            or result.get('envelope_sha256') != original_sha):
        raise ValueError('preserved placement lacks verified native-zero one-shot evidence')
    restored = verify_fresh_backup(Path(restoration_backup), max_age_seconds=None)
    placed = verify_fresh_backup(Path(result['after_backup']), max_age_seconds=None)
    baseline = verify_fresh_backup(Path(backup_directory))
    if (dict(restored.object_sha256_by_key) != original['baseline_objects']
            or dict(placed.object_sha256_by_key) != result['after_objects']
            or placed.manifest_sha256 != result['after_manifest_sha256']
            or dict(baseline.object_sha256_by_key) != dict(placed.object_sha256_by_key)
            or any(x.object_count != 8 or x.device_identity != ('0x054c','0x001e')
                   for x in (baseline,placed,restored))):
        raise ValueError('fresh native state, verified placement or original restoration identity differs')
    if (placed.blob_sha256 != original['operations'][0]['candidate_sha256']
            or result['transaction_sha256'] != original['operations'][0]['transaction_sha256']):
        raise ValueError('preserved placement differs from approved native bytes')
    _nested_disposable_delta(_blob(restored), _blob(placed), TARGET)
    capacity = NativeCapacityResponse.from_hardware_response(
        RawInfoResponse(0x0019,'hardware-info',Path(capacity_path).read_bytes()),device_identity=(0x054c,0x001e))
    if capacity.to_dict() != original['capacity']:
        raise ValueError('native capacity changed')
    core = build_nested_txt_validation_delete(baseline.directory,TARGET,
                                              target_record_offset=original['target_record_offset'])
    if (core.candidate_blob_sha256 != restored.blob_sha256
            or core.transaction_sha256 != original['operations'][1]['transaction_sha256']
            or max(len(core.baseline.data),len(core.candidate_blob)) > capacity.capacity_limit_bytes):
        raise ValueError('exact existing-target Delete does not restore the approved native baseline')
    host = build_nested_file_delete_candidate(baseline.directory,TARGET,core.target_record_offset)
    verify_nested_file_delete_readback(host,restored.directory,completion=0,max_age_seconds=None)
    record = core.baseline.record_at(core.target_record_offset)
    prefix,payload = core.baseline.payload_parts(record)
    _,parent_offset = _nested_parent(core.baseline,TARGET)
    operation = {'ordinal':1,'operation':'delete_existing_nested_txt','target':TARGET,
                 'target_record_offset':record.offset,'candidate_sha256':core.candidate_blob_sha256,
                 'transaction_sha256':core.transaction_sha256,'expected_added_paths':[],
                 'expected_removed_paths':[TARGET],'sender_invocations':1}
    envelope = {
        'format':'infocarry-nested-txt-deletion-only-task-v1','task':'P18-049-final-delete',
        'status':'prepared_for_independent_review','source_head':source_head,'model':'VNW-V15',
        'target':TARGET,'parent_record_offset':parent_offset,
        'target_profile':{'flag':record.flag,'opaque':record.field_10_be32,'selector':record.field_14_be32,
            'prefix_bytes':len(prefix),'prefix_sha256':hashlib.sha256(prefix).hexdigest(),
            'record_sha256':hashlib.sha256(bytes.fromhex(record.raw_hex)).hexdigest(),
            'payload_bytes':len(payload),'payload_sha256':hashlib.sha256(payload).hexdigest()},
        'baseline_manifest_sha256':baseline.manifest_sha256,
        'baseline_objects':dict(baseline.object_sha256_by_key),
        'baseline_state_identity_sha256':_backup_identity(baseline).sha256,
        'placement_after_objects':dict(placed.object_sha256_by_key),
        'restoration_manifest_sha256':restored.manifest_sha256,
        'restoration_objects':dict(restored.object_sha256_by_key),'capacity':capacity.to_dict(),
        'operations':[operation],'maximum_sender_invocations':1,'automatic_retry_allowed':False,
        'extra_setup_or_cleanup_writes':0,'owner_approval':None,'physical_writes_performed':0,
        'antecedents':{'original_envelope_sha256':original_sha,
            'placement_result_sha256':hashlib.sha256(result_path.read_bytes()).hexdigest(),
            'resolution_record_sha256':hashlib.sha256(resolution_path.read_bytes()).hexdigest()},
        'execution_policy':{
            'scope':'only delete the existing exact unread unreferenced TXT; no placement, retry, restore or extra write',
            'preflight':'fresh native capacity and eight objects must match the verified placement; freeze and bind the new task through existing service before confirmation',
            'readback':'native integer zero, one sender, complete independent backup; all eight objects must equal original restoration hashes inside canonical verification',
            'abort':'stop on any mismatch, failed verification, ambiguity, nonzero/missing completion or safety inconsistency; no retry or automatic recovery',
        },
    }
    output.mkdir(parents=True,exist_ok=False)
    core.transaction.preserve(output/'transaction',source='offline-nested-txt-deletion-only')
    (output/'candidate.bin').write_bytes(core.candidate_blob)
    _write_json(output/'task-envelope.json',envelope)
    return envelope,hashlib.sha256(_json(envelope)).hexdigest()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backup',required=True,type=Path);p.add_argument('--capacity-response',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--timestamp',type=int)
    p.add_argument('--source-head',required=True);p.add_argument('--archive-replay',action='store_true')
    p.add_argument('--delete-only',action='store_true')
    p.add_argument('--restoration-backup',type=Path);p.add_argument('--placement-result',type=Path)
    p.add_argument('--original-envelope',type=Path);p.add_argument('--resolution-record',type=Path)
    a=p.parse_args(argv)
    if a.delete_only:
        if a.timestamp is not None or a.archive_replay or not all((a.restoration_backup,a.placement_result,a.original_envelope,a.resolution_record)):
            p.error('deletion-only requires preserved restoration/placement/envelope/resolution evidence; no placement timestamp or archive replay')
        e,h=prepare_delete_only(a.backup,a.capacity_response,a.output,source_head=a.source_head,
            restoration_backup=a.restoration_backup,placement_result=a.placement_result,
            original_envelope=a.original_envelope,resolution_record=a.resolution_record)
        print(json.dumps({'status':e['status'],'envelope_sha256':h,'maximum_sender_invocations':1,'physical_writes_performed':0},indent=2))
        return 0
    if a.timestamp is None:
        p.error('two-write archive/preparation mode requires an explicit placement timestamp')
    e,h=prepare(a.backup,a.capacity_response,a.output,timestamp=a.timestamp,source_head=a.source_head,archive_replay=a.archive_replay)
    print(json.dumps({'status':e['status'],'envelope_sha256':h,'maximum_sender_invocations':2,
                      'all_eight_return_to_baseline':True,'physical_writes_performed':0},indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
