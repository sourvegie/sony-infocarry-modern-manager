#!/usr/bin/env python3
"""Prepare an exact two-write nested BMP rehearsal on the host. No USB/write mode.

This is preparation, not a hardware-ready authorization envelope. The bounded
live nested-BMP adapter is deliberately absent. Copied probe/0x0024 simulation
bytes are not predictions of native post-placement responses.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / 'src'))
from infocarry.backup_format import parse_backup_blob
from infocarry.delete_workflow import ROOT_BMP_DELETE_FIXTURE_BYTES, require_external_bmp_output
from infocarry.delete_generalized import build_nested_file_delete_candidate, verify_nested_file_delete_readback
from infocarry.new_bmp import build_new_nested_bmp_add
from infocarry.root_txt_placement import _blob
from infocarry.write_gate import verify_fresh_backup
from prepare_nested_txt_delete import simulated_archive

TARGET = r'root\IC_P18_040_NESTED_20260930_01\Section-A\IC_P18_050_DELETE_A.bmp'


def prepare(backup_directory, output, *, capacity_limit_bytes, timestamp, source_head):
    if (not isinstance(source_head, str) or len(source_head) != 40
            or any(c not in '0123456789abcdef' for c in source_head)):
        raise ValueError('exact source commit required')
    if type(capacity_limit_bytes) is not int or capacity_limit_bytes <= 0:
        raise ValueError('explicit host capacity limit required; this is not fresh native evidence')
    output = require_external_bmp_output(output)
    if output.is_relative_to(REPOSITORY_ROOT):
        raise ValueError('private preparation must remain outside source repository')
    backup = verify_fresh_backup(Path(backup_directory), max_age_seconds=None)
    if backup.device_identity != ('0x054c', '0x001e') or backup.object_count != 8:
        raise ValueError('complete eight-object VNW-V15 backup required')
    if output.is_relative_to(backup.directory):
        raise ValueError('output must not modify the original backup')
    parsed = parse_backup_blob(_blob(backup))
    parent = tuple(TARGET.split('\\')[:-1])
    parents = [o for o,p in parsed.paths.items() if p == parent]
    if len(parents) != 1:
        raise ValueError('exact existing parent is missing or ambiguous')
    templates = []
    for offset in parsed.paths:
        record = parsed.record_at(offset)
        if (record.kind == 'file' and record.extension == 'bmp' and record.flag == 0xe0
                and record.field_10_be32 == 0xffffffff and record.field_14_be32 == 0x100
                and parsed.payload_parts(record)[0] == b'\xff'*16):
            from infocarry.prepared_media_package import validate_bmp_payload
            try: validate_bmp_payload(parsed.payload_parts(record)[1])
            except ValueError: continue
            templates.append(offset)
    if not templates:
        raise ValueError('missing reachable unread BMP template with opaque +0x10=ffffffff, selector +0x14=100 and all-FF16 prefix')
    # Freeze the exact selected source identity separately from resulting bytes.
    template_offset = templates[0]
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    source = output / TARGET.split('\\')[-1]
    source.write_bytes(ROOT_BMP_DELETE_FIXTURE_BYTES)
    placed = build_new_nested_bmp_add(backup.directory, source, source.name,
        target_directory_path=parent, target_directory_offset=parents[0],
        source_template_offset=template_offset,
        available_capacity_bytes=capacity_limit_bytes-len(parsed.data),
        record_timestamp_be32=timestamp, max_age_seconds=None)
    placed_archive = simulated_archive(backup, output/'simulated-placement', placed.candidate_blob, placed.transaction)
    after_parsed = parse_backup_blob(placed.candidate_blob)
    offsets = [o for o,p in after_parsed.paths.items() if p == parent+(source.stem,)]
    if len(offsets) != 1: raise ValueError('prepared target is ambiguous')
    deleted = build_nested_file_delete_candidate(placed_archive.directory, TARGET, offsets[0], max_age_seconds=None)
    # No nested BMP transaction, authorization or sender is created for Delete.
    # Only the archive writer needs ranges; do not construct a Delete transaction.
    from types import SimpleNamespace
    simulation = SimpleNamespace(ranges=(b''.join(deleted.fixed_state.after[:4]),deleted.fixed_state.after[4]))
    final = simulated_archive(placed_archive, output/'simulated-delete', deleted.candidate_blob, simulation)
    verify_nested_file_delete_readback(deleted, final.directory, completion=0, max_age_seconds=None)
    if dict(final.object_sha256_by_key) != dict(backup.object_sha256_by_key):
        raise ValueError('host inverse does not restore the complete original archive')
    report = {
        'format':'infocarry-nested-bmp-host-rehearsal-v1', 'task':'P18-050',
        'status':'host_rehearsal_not_hardware_ready', 'source_head':source_head,
        'device':'Sony VNW-V15', 'target':TARGET, 'parent_record_offset':parents[0],
        'target_record_offset':offsets[0], 'fixture':{'bytes':len(ROOT_BMP_DELETE_FIXTURE_BYTES),
            'sha256':hashlib.sha256(ROOT_BMP_DELETE_FIXTURE_BYTES).hexdigest()},
        'baseline_objects':dict(backup.object_sha256_by_key), 'template':placed.audit['template'],
        'placement_timestamp_be32':timestamp, 'host_capacity_limit_bytes':capacity_limit_bytes,
        'placement_candidate_sha256':hashlib.sha256(placed.candidate_blob).hexdigest(),
        'placement_transaction_sha256':placed.transaction.concatenated_sha256,
        'delete_candidate_sha256':deleted.candidate_blob_sha256,
        'restoration_objects':dict(backup.object_sha256_by_key),
        'maximum_sender_invocations':2, 'extra_setup_or_cleanup_writes':0,
        'operations':['place exact disposable nested BMP once', 'delete same exact BMP once after independent placement verification'],
        'required_before_hardware':['reviewed exact validation adapter through the existing one-shot lifecycle',
            'fresh complete baseline equality and native capacity',
            'immutable reviewed task envelope and one owner approval for entire two-write sequence'],
        'stop_rules':['stop on any identity/provenance/state/capacity mismatch or ambiguity',
            'each sender: fresh guards, one durable claim, marker/global lock, integer native 0x0000, independent complete readback',
            'no retries, recovery, re-placement or extra cleanup',
            'final actual native backup must restore all eight original objects byte-for-byte'],
        'host_inverse_restores_eight_objects':True,
        'simulation_limit':'probe and 0x0024 copied; actual native post-placement values are not predicted',
        'execution_available':False, 'physical_operation_authorized':False, 'usb_operations':0,
    }
    (output/'placement-audit.json').write_text(json.dumps(placed.audit,indent=2,sort_keys=True)+'\n')
    data=(json.dumps(report,indent=2,sort_keys=True)+'\n').encode()
    (output/'rehearsal.json').write_bytes(data)
    return {'report':str(output/'rehearsal.json'),'sha256':hashlib.sha256(data).hexdigest(),
            'status':report['status'],'execution_available':False,'usb_operations':0}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--capacity-limit-bytes',type=int,required=True)
    parser.add_argument('--timestamp',type=lambda s:int(s,0),required=True)
    parser.add_argument('--source-head',required=True)
    args=parser.parse_args(argv)
    print(json.dumps(prepare(args.backup,args.output,capacity_limit_bytes=args.capacity_limit_bytes,
        timestamp=args.timestamp,source_head=args.source_head),indent=2,sort_keys=True))


if __name__=='__main__':
    main()
