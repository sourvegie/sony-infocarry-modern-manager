"""The offline task envelope binds exactly two operations and exact restoration."""
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import tempfile
import unittest

try:
    from test_nested_txt_delete_execution import exact_nested_blob
    from test_new_txt import _write_archive
    from test_prepared_library_package_live_adapter import _response
except ModuleNotFoundError:
    from tests.test_nested_txt_delete_execution import exact_nested_blob
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_library_package_live_adapter import _response
from infocarry.backup_repack import delete_existing_file
from infocarry.backup_format import parse_backup_blob
from infocarry.write_gate import verify_fresh_backup

spec=importlib.util.spec_from_file_location('prepare_nested_txt_delete',Path(__file__).resolve().parents[1]/'scripts/prepare_nested_txt_delete.py')
preparation=importlib.util.module_from_spec(spec);spec.loader.exec_module(preparation)


class NestedTxtExperimentPreparationTests(unittest.TestCase):
    def case(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name)
        blob=delete_existing_file(parse_backup_blob(exact_nested_blob()),0x300)
        backup=_write_archive(root/'baseline',blob,datetime.now(timezone.utc),fixed_state={c:bytes(64) for c in range(0x1b,0x20)})
        capacity=root/'capacity.bin';capacity.write_bytes(_response().raw_response)
        return root,backup,capacity

    def test_two_steps_bound_target_hashes_capacity_and_eight_object_restoration(self):
        root,backup,capacity=self.case()
        before=verify_fresh_backup(backup)
        envelope,digest=preparation.prepare(backup,capacity,root/'frozen',timestamp=1792710000,source_head='a'*40)
        self.assertEqual(len(digest),64)
        self.assertEqual(envelope['maximum_sender_invocations'],2)
        self.assertEqual([x['ordinal'] for x in envelope['operations']],[1,2])
        self.assertEqual([x['sender_invocations'] for x in envelope['operations']],[1,1])
        self.assertEqual(envelope['extra_setup_or_cleanup_writes'],0)
        self.assertEqual(envelope['physical_writes_performed'],0)
        self.assertIsNone(envelope['owner_approval'])
        after=verify_fresh_backup(root/'frozen'/'simulated-delete')
        self.assertEqual(dict(after.object_sha256_by_key),dict(before.object_sha256_by_key))
        self.assertEqual(verify_fresh_backup(backup).manifest_sha256,before.manifest_sha256)

    def test_archive_replay_cannot_be_mistaken_for_fresh_approval_scope(self):
        root,backup,capacity=self.case()
        e,_=preparation.prepare(backup,capacity,root/'replay',timestamp=1792710000,source_head='b'*40,archive_replay=True)
        self.assertEqual(e['status'],'archive_replay_only')
        self.assertIsNone(e['owner_approval'])

    def test_refuse_repository_output_bad_head_and_capacity_without_changing_baseline(self):
        root,backup,capacity=self.case()
        before=verify_fresh_backup(backup)
        for output,head in ((preparation.REPOSITORY_ROOT/'private-evidence','a'*40),(root/'bad','not-a-commit')):
            with self.assertRaises(ValueError):
                preparation.prepare(backup,capacity,output,timestamp=1792710000,source_head=head)
            self.assertFalse(output.exists())
        raw=bytearray(capacity.read_bytes());raw[8:12]=(1).to_bytes(4,'big');capacity.write_bytes(raw)
        with self.assertRaises(ValueError):
            preparation.prepare(backup,capacity,root/'capacity-fail',timestamp=1792710000,source_head='a'*40)
        self.assertEqual(verify_fresh_backup(backup).manifest_sha256,before.manifest_sha256)
