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
from infocarry.root_txt_placement import _blob, _json, _nested_parent, _nested_disposable_delta, _write_json
from infocarry.prepared_library_package_live_adapter import _backup_identity
from infocarry.write_gate import verify_fresh_backup


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
    templates = [r for r in parsed.records if r.kind=='file' and r.extension=='txt'
                 and r.flag==0xe0 and r.field_10_be32==0xffffffff and r.field_14_be32==0x200]
    if not templates:
        raise ValueError('no observed unread 32-prefix TXT template')
    output.mkdir(parents=True,exist_ok=False)
    source = output / TARGET.split('\\')[-1];source.write_bytes(PAYLOAD)
    placed = build_new_nested_txt_add(baseline.directory,source,source.name,
        target_directory_path=parent_path,target_directory_offset=parent_offset,
        source_template_offset=templates[0].offset,
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
             'template_offset':templates[0].offset,'candidate_sha256':hashlib.sha256(placed.candidate_blob).hexdigest(),
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
    _write_json(output/'task-envelope.json',envelope)
    return envelope,hashlib.sha256(_json(envelope)).hexdigest()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backup',required=True,type=Path);p.add_argument('--capacity-response',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path);p.add_argument('--timestamp',required=True,type=int)
    p.add_argument('--source-head',required=True);p.add_argument('--archive-replay',action='store_true')
    a=p.parse_args(argv)
    e,h=prepare(a.backup,a.capacity_response,a.output,timestamp=a.timestamp,source_head=a.source_head,archive_replay=a.archive_replay)
    print(json.dumps({'status':e['status'],'envelope_sha256':h,'maximum_sender_invocations':2,
                      'all_eight_return_to_baseline':True,'physical_writes_performed':0},indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
