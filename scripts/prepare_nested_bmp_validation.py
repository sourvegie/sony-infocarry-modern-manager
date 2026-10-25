#!/usr/bin/env python3
"""Prepare nested BMP host rehearsals and frozen experiments. No USB/write mode.

The legacy default remains the P18-050 host-only rehearsal. --experiment freezes
the bounded P18-051 placement/deletion pair for independent review. Neither mode
grants hardware authority. Copied probe/0x0024 simulation bytes are not
predictions of native post-placement responses.
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


def prepare_experiment(backup_directory, capacity_path, output, *, timestamp,
                       source_head, archive_replay=False):
    """Freeze exactly two operations; construct and independently replay offline.

    Native evidence must be fresh unless explicitly labeled archive replay.
    All raw derived archives, transactions and audits remain outside Git. No
    runtime, approval, execution claim, marker or sender is opened here.
    """
    from infocarry.capacity_evidence import NativeCapacityResponse
    from infocarry.device_info import RawInfoResponse
    from infocarry.delete_workflow import (
        NESTED_BMP_DELETE_VALIDATION_PATH as target_path,
        build_nested_bmp_validation_delete,
    )
    from infocarry.prepared_library_package_live_adapter import _backup_identity
    from infocarry.root_txt_placement import (
        _json, _write_json, _nested_parent, _nested_disposable_delta,
        _select_nested_bmp_template, _nested_txt_template_provenance,
        require_nested_placement_provenance,
    )

    if (type(source_head) is not str or len(source_head) != 40
            or any(c not in '0123456789abcdef' for c in source_head)):
        raise ValueError('source head must identify the independently reviewed exact commit')
    if type(archive_replay) is not bool:
        raise ValueError('archive replay must be an explicit boolean')
    if type(timestamp) is not int or not 0 <= timestamp <= 0xffffffff:
        raise ValueError('placement timestamp must fit uint32')
    output = require_external_bmp_output(output)
    if output.is_relative_to(REPOSITORY_ROOT):
        raise ValueError('private preparation must remain outside source repository')
    max_age = None if archive_replay else 300
    baseline = verify_fresh_backup(Path(backup_directory), max_age_seconds=max_age)
    if baseline.device_identity != ('0x054c', '0x001e') or baseline.object_count != 8:
        raise ValueError('complete eight-object VNW-V15 baseline required')
    if output.is_relative_to(baseline.directory):
        raise ValueError('output must not modify the original backup')
    capacity_raw = Path(capacity_path).read_bytes()
    capacity = NativeCapacityResponse.from_hardware_response(
        RawInfoResponse(0x0019, 'hardware-info', capacity_raw),
        device_identity=(0x054c, 0x001e))
    parsed = parse_backup_blob(_blob(baseline))
    parent_path, parent_offset = _nested_parent(parsed, target_path)
    template_offset = _select_nested_bmp_template(parsed)
    # Validate native capacity before materializing any preparation output.
    capacity.bind_model_lengths(len(parsed.data), len(parsed.data))
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    source = output / target_path.split('\\')[-1]
    source.write_bytes(ROOT_BMP_DELETE_FIXTURE_BYTES)
    placed = build_new_nested_bmp_add(
        baseline.directory, source, source.name,
        target_directory_path=parent_path, target_directory_offset=parent_offset,
        source_template_offset=template_offset,
        available_capacity_bytes=capacity.capacity_limit_bytes-len(parsed.data),
        record_timestamp_be32=timestamp, max_age_seconds=max_age)
    capacity.bind_model_lengths(len(parsed.data), len(placed.candidate_blob))
    delta = _nested_disposable_delta(parsed.data, placed.candidate_blob,
                                      target_path, media_type='bmp')
    placed_backup = simulated_archive(baseline, output/'simulated-placement',
                                      placed.candidate_blob, placed.transaction)
    after = parse_backup_blob(placed.candidate_blob)
    target_offsets = [offset for offset, path in after.paths.items()
                      if path == parent_path + (source.stem,)]
    if len(target_offsets) != 1:
        raise ValueError('prepared nested BMP target is missing or ambiguous')
    removed = build_nested_bmp_validation_delete(
        placed_backup.directory, target_path,
        target_record_offset=target_offsets[0], max_age_seconds=300)
    if max(len(placed.candidate_blob), len(removed.candidate_blob)) > capacity.capacity_limit_bytes:
        raise ValueError('nested BMP deletion exceeds the frozen native capacity')
    final = simulated_archive(placed_backup, output/'simulated-delete',
                              removed.candidate_blob, removed.transaction)
    # Separate host-only reconstruction and verifier do not trust the adapter's
    # audit or a placement builder's assertion of inverse preservation.
    host = build_nested_file_delete_candidate(
        placed_backup.directory, target_path, removed.target_record_offset,
        max_age_seconds=300)
    if (host.candidate_blob != removed.candidate_blob
            or host.fixed_state != removed.fixed_state):
        raise ValueError('validation adapter differs from independent nested model')
    verify_nested_file_delete_readback(host, final.directory, completion=0,
                                       max_age_seconds=300)
    baseline_objects = dict(baseline.object_sha256_by_key)
    if dict(final.object_sha256_by_key) != baseline_objects:
        raise ValueError('two-operation replay did not restore all eight native objects exactly')
    target = after.record_at(removed.target_record_offset)
    prefix, payload = after.payload_parts(target)
    if (payload != ROOT_BMP_DELETE_FIXTURE_BYTES or prefix != b'\xff'*16
            or target.flag != 0xe0 or target.field_10_be32 != 0xffffffff
            or target.field_14_be32 != 0x100 or target.timestamp_be32 != timestamp):
        raise ValueError('prepared BMP native profile differs from the exact fixture')
    unpredicted_keys = ('0x0024:response-0024', '0x8004:backup-blob-probe')
    envelope = {
        'format':'infocarry-nested-bmp-delete-task-envelope-v1', 'task':'P18-051',
        'status':'archive_replay_only' if archive_replay else 'prepared_for_independent_review',
        'source_head':source_head, 'model':'VNW-V15', 'vendor_id':'0x054c', 'product_id':'0x001e',
        'baseline_manifest_sha256':baseline.manifest_sha256,
        'baseline_state_identity_sha256':_backup_identity(baseline).sha256,
        'baseline_objects':baseline_objects, 'restoration_objects':baseline_objects,
        'restoration_state_identity_sha256':_backup_identity(baseline).sha256,
        'target':target_path, 'parent_record_offset':parent_offset,
        'parent_path':'\\'.join(parent_path), 'target_record_offset':target.offset,
        'fixture':{'bytes':len(payload), 'sha256':hashlib.sha256(payload).hexdigest()},
        'native_profile':{'flag':'0xe0', 'opaque':'0xffffffff', 'selector':'0x100',
            'prefix_bytes':16, 'prefix_sha256':hashlib.sha256(prefix).hexdigest(),
            'target_record_sha256':hashlib.sha256(bytes.fromhex(target.raw_hex)).hexdigest(),
            'timestamp_be32':timestamp},
        'capacity':capacity.to_dict(), 'placement_timestamp_be32':timestamp,
        'placement_expected_objects':{key:value for key,value in placed_backup.object_sha256_by_key
                                      if key not in unpredicted_keys},
        'placement_unpredicted_objects':list(unpredicted_keys),
        'operations':[
            {'ordinal':1, 'operation':'place_exact_nested_bmp', 'target':target_path,
             'target_record_offset':target.offset, 'template_offset':template_offset,
             'template_provenance':_nested_txt_template_provenance(parsed, template_offset),
             'candidate_sha256':hashlib.sha256(placed.candidate_blob).hexdigest(),
             'transaction_sha256':placed.transaction.concatenated_sha256,
             'growth_bytes':len(placed.candidate_blob)-len(parsed.data),
             'expected_added_paths':[target_path], 'expected_removed_paths':[], 'sender_invocations':1},
            {'ordinal':2, 'operation':'delete_same_nested_bmp', 'target':target_path,
             'target_record_offset':target.offset, 'candidate_sha256':removed.candidate_blob_sha256,
             'transaction_sha256':removed.transaction_sha256,
             'expected_added_paths':[], 'expected_removed_paths':[target_path], 'sender_invocations':1},
        ],
        'maximum_sender_invocations':2, 'automatic_retry_allowed':False,
        'extra_setup_or_cleanup_writes':0,
        'replay':{'eight_objects_return_to_baseline':True, 'protected_state_preserved':True,
                  'placement_delta':delta,
                  'simulation_limit':'probe and 0x0024 copied; native post-placement values are unpredicted'},
        'execution_policy':{
            'operation_identities':'freeze each existing operation bundle just in time; require exact envelope candidates/transactions and full prior verified state',
            'each_write':'fresh eight-object backup/native capacity; existing exact owner binding, durable claim, marker, global lock; one sender; native integer zero; independent complete post-backup',
            'abort':'stop on any mismatch, unsupported state, nonzero/malformed/missing completion, disconnect, ambiguity, backup or verification failure; no retry, recovery, cleanup or extra write',
            'final_state':'all eight native objects byte-identical to baseline; target absent; parent/siblings/markers/references/payloads/timestamps preserved',
        },
        'physical_writes_performed':0, 'owner_approval':None,
    }
    require_nested_placement_provenance(parsed, envelope['operations'][0],
                                       placed.audit_dict(), media_type='bmp')
    # Preserve exactly the bytes and audits checked above, outside the source.
    (output/'capacity-response.bin').write_bytes(capacity_raw)
    (output/'placement-candidate.bin').write_bytes(placed.candidate_blob)
    (output/'deletion-candidate.bin').write_bytes(removed.candidate_blob)
    placed.transaction.preserve(output/'placement-transaction', source='offline-nested-bmp-placement')
    removed.transaction.preserve(output/'deletion-transaction', source='offline-nested-bmp-delete')
    _write_json(output/'placement-audit.json', placed.audit_dict())
    _write_json(output/'deletion-audit.json', removed.to_dict())
    _write_json(output/'task-envelope.json', envelope)
    return envelope, hashlib.sha256(_json(envelope)).hexdigest()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--capacity-limit-bytes',type=int)
    parser.add_argument('--experiment',action='store_true')
    parser.add_argument('--capacity-response',type=Path)
    parser.add_argument('--archive-replay',action='store_true')
    parser.add_argument('--timestamp',type=lambda s:int(s,0),required=True)
    parser.add_argument('--source-head',required=True)
    args=parser.parse_args(argv)
    if args.experiment:
        if args.capacity_response is None or args.capacity_limit_bytes is not None:
            parser.error('--experiment requires --capacity-response and does not accept a host capacity limit')
        envelope,digest=prepare_experiment(args.backup,args.capacity_response,args.output,
            timestamp=args.timestamp,source_head=args.source_head,archive_replay=args.archive_replay)
        print(json.dumps({'status':envelope['status'],'envelope_sha256':digest,
            'maximum_sender_invocations':2,'all_eight_return_to_baseline':True,
            'physical_writes_performed':0},indent=2,sort_keys=True))
        return 0
    if args.capacity_limit_bytes is None or args.capacity_response is not None or args.archive_replay:
        parser.error('legacy host rehearsal requires --capacity-limit-bytes; native evidence and archive replay require --experiment')
    print(json.dumps(prepare(args.backup,args.output,capacity_limit_bytes=args.capacity_limit_bytes,
        timestamp=args.timestamp,source_head=args.source_head),indent=2,sort_keys=True))


if __name__=='__main__':
    main()
