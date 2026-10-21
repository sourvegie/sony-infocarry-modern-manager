"""Host-only nested leaf removal: structural/state checks and no sender path."""
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from infocarry.backup_format import parse_backup_blob
from infocarry.backup_repack import delete_existing_file, rename_existing_record
from infocarry.delete_model import (
    DeleteModelError, build_one_nested_file_delete_model,
    build_one_txt_delete_model, verify_nested_file_delete_model,
)
from infocarry.delete_generalized import (
    DELETE_GENERALIZED_CONFIRMATION_PHRASE, GeneralizedDeleteError,
    GeneralizedDeleteSenderBinding, GeneralizedDeleteVerificationError,
    authorize_generalized_delete, bind_generalized_delete_sender,
    build_generalized_delete_candidate, build_nested_file_delete_candidate,
    verify_nested_file_delete_readback,
)
from infocarry.delete_workflow import (
    FakeDeleteTransport, GuardedGeneralizedDeleteWorkflow, GeneralizedDeleteWorkflowError,
)
try:
    from test_backup_format import make_record
    from test_backup_duplicate import make_nested_blob
    from test_bitmap import make_monochrome_bmp
    from test_root_bmp_delete_model import _checksum
    from test_prepared_package_multi_candidate import _blob
    from test_new_txt import _write_archive
except ModuleNotFoundError:
    from tests.test_backup_format import make_record
    from tests.test_backup_duplicate import make_nested_blob
    from tests.test_bitmap import make_monochrome_bmp
    from tests.test_root_bmp_delete_model import _checksum
    from tests.test_prepared_package_multi_candidate import _blob
    from tests.test_new_txt import _write_archive


def nested_library(*, prefix=16, flag=0xe0, text=b'target text\r\n'):
    """Two depths, sibling files, separate child-table anchors and markers."""
    content = bytearray()

    def file(name, extension, payload):
        start = len(content)
        content.extend(b'\xff' * prefix + payload)
        content.extend(b'\xa5' * (-len(content) % 4))
        return make_record(flag, extension, start, len(payload), name, prefix // 16 << 8)

    root_file = file('outside', 'txt', b'root survivor\r\n')
    first = file('first', 'txt', text)
    bitmap = file('image', 'bmp', make_monochrome_bmp(237, 320))
    deep = file('deep', 'txt', b'deep survivor\r\n')
    records = [
        make_record(0xd0, '', 0x40, 0xc0, 'root'),
        make_record(0xd0, '', 0, 0x40, '..'),
        make_record(0xd0, '', 0x140, 0x100, 'folder'),
        root_file,
        make_record(0xd0, '', 0x40, 0xc0, '..'),
        make_record(0xd0, '', 0x40, 0xc0, '..'),
        first,
        make_record(0xd0, '', 0x280, 0x80, 'sub'),
        bitmap,
        make_record(0xd0, '', 0xc0, 0x100, '..'),
        make_record(0xd0, '', 0xc0, 0x200, '..'),
        deep,
        make_record(0xd0, '', 0x200, 0x80, '..'),
    ]
    for index, raw in enumerate(records):
        raw = bytearray(raw)
        raw[12:16] = (1792000000 + index).to_bytes(4, 'big')
        records[index] = bytes(raw)
    return _blob(b''.join(records), bytes(content))


class NestedFileDeleteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.count = 0

    def archive(self, blob, fixed=None):
        self.count += 1
        return _write_archive(self.root / str(self.count), blob, self.now,
            fixed_state=fixed if fixed is not None else {c: bytes(64) for c in range(0x1b, 0x20)})

    def candidate(self, blob=None, offset=0x1c0, fixed=None):
        blob = nested_library() if blob is None else blob
        parsed = parse_backup_blob(blob)
        record = parsed.record_at(offset)
        path = '\\'.join(parsed.paths[offset]) + '.' + record.extension
        return build_nested_file_delete_candidate(self.archive(blob, fixed), path, offset,
                                                  now=self.now, max_age_seconds=None)

    def post(self, candidate, blob=None, fixed=None):
        return self.archive(candidate.candidate_blob if blob is None else blob,
            fixed=fixed if fixed is not None else dict(zip(range(0x1b, 0x20), candidate.fixed_state.after)))

    def test_nested_txt_bmp_deep_prefix_state_and_all_txt_alignments(self):
        for offset in (0x1c0, 0x240, 0x300):
            for prefix in (16, 32):
                for flag in (0xe0, 0x20):
                    for remainder in range(4):
                        with self.subTest(offset=offset, prefix=prefix, flag=flag, remainder=remainder):
                            blob = nested_library(prefix=prefix, flag=flag, text=b'x' * remainder)
                            candidate = self.candidate(blob, offset)
                            before = candidate.baseline
                            after = parse_backup_blob(candidate.candidate_blob)
                            self.assertEqual(before.data, blob)
                            self.assertEqual(candidate.candidate_blob, delete_existing_file(before, offset))
                            self.assertEqual(len(after.records), len(before.records) - 1)
                            self.assertEqual(set(before.paths.values()) - set(after.paths.values()),
                                             {before.paths[offset]})
                            for row in before.records:
                                if row.offset == offset:
                                    continue
                                new = after.record_at(row.offset - (64 if row.offset > offset else 0))
                                self.assertEqual(row.timestamp_be32, new.timestamp_be32)
                                if row.kind == 'file':
                                    self.assertEqual(before.payload_parts(row), after.payload_parts(new))
                            result = verify_nested_file_delete_readback(candidate, self.post(candidate),
                                completion=0, now=self.now, max_age_seconds=None)
                            self.assertTrue(result.target_removed)
                            self.assertFalse(hasattr(candidate, 'transaction'))
                            self.assertFalse(candidate.audit['safety']['execution_available'])
                            self.assertFalse(candidate.audit['safety']['authorization_created'])

    def test_sole_nested_leaf_removal_keeps_empty_parent_and_every_marker(self):
        for extension in ('txt', 'bmp'):
            blob = bytearray(make_nested_blob(make_monochrome_bmp(237, 320) if extension == 'bmp' else b'only\r\n'))
            blob[0x141:0x144] = extension.encode('ascii')
            before = parse_backup_blob(_checksum(blob))
            model = build_one_nested_file_delete_model(before, 'root\\folder\\source.' + extension, 0x140)
            after = parse_backup_blob(model.candidate_blob)
            self.assertEqual(after.paths, {0x40: ('root',), 0xc0: ('root', 'folder')})
            self.assertEqual(after.record_at(0xc0).field_08_be32, 64)
            self.assertEqual(sum(r.name == '..' for r in before.records),
                             sum(r.name == '..' for r in after.records))
            self.assertEqual(after.record_at(0x140).name, '..')
            self.assertEqual(after.record_at(0x180).name, '..')

    def test_parent_sibling_order_and_marker_relation_are_preserved(self):
        candidate = self.candidate()
        before, after = candidate.baseline, parse_backup_blob(candidate.candidate_blob)
        self.assertEqual(after.record_at(0xc0).field_08_be32, before.record_at(0xc0).field_08_be32 - 64)
        self.assertEqual(after.record_at(0x40).field_08_be32, before.record_at(0x40).field_08_be32)
        for row in before.records:
            if row.name != '..':
                continue
            new = after.record_at(row.offset - (64 if row.offset > 0x1c0 else 0))
            expected = row.field_08_be32 - (64 if row.field_04_be32 == 0xc0 else 0)
            self.assertEqual(new.field_08_be32, expected)
        self.assertEqual([r.name for r in after.records if r.offset in after.paths],
                         ['root', 'folder', 'outside', 'sub', 'image', 'deep'])

    def test_independent_model_verifier_does_not_call_repacker(self):
        candidate = self.candidate()
        with patch('infocarry.delete_model.delete_existing_file', side_effect=AssertionError('repacker called')):
            verify_nested_file_delete_model(candidate.baseline, candidate.candidate_blob,
                                            candidate.target_path, candidate.target_record_offset)
            verify_nested_file_delete_readback(candidate, self.post(candidate), completion=0,
                                              now=self.now, max_age_seconds=None)

    def test_protected_survivor_references_before_and_after_target_rebase(self):
        for command in (0x1b, 0x1f):
            for offset in (0x100, 0x240, 0x300):
                fixed = {c: bytes(64) for c in range(0x1b, 0x20)}
                raw = bytearray(64)
                if command == 0x1b:
                    raw[:4] = (1).to_bytes(4, 'big')
                    index = 8
                else:
                    raw[8:12] = (0x80000000).to_bytes(4, 'big')
                    index = 0
                raw[index:index+4] = (offset-64).to_bytes(4, 'big')
                fixed[command] = bytes(raw)
                candidate = self.candidate(fixed=fixed)
                expected = bytearray(raw)
                expected[index:index+4] = (offset - 64 - (64 if offset > 0x1c0 else 0)).to_bytes(4, 'big')
                self.assertEqual(candidate.fixed_state.after[command-0x1b], bytes(expected))
                verify_nested_file_delete_readback(candidate, self.post(candidate), completion=0,
                                                  now=self.now, max_age_seconds=None)

    def test_protected_target_active_marks_and_unknown_state_refuse(self):
        for command in range(0x1b, 0x20):
            fixed = {c: bytes(64) for c in range(0x1b, 0x20)}
            raw = bytearray(64)
            if command == 0x1f:
                raw[:4] = (0x1c0-64).to_bytes(4, 'big')
                raw[8:12] = (0x80000000).to_bytes(4, 'big')
            else:
                raw[:4] = (1).to_bytes(4, 'big')
                raw[8:12] = (0x1c0-64).to_bytes(4, 'big')
            fixed[command] = bytes(raw)
            with self.subTest(command=command), self.assertRaises(GeneralizedDeleteError):
                self.candidate(fixed=fixed)
        fixed[0x1b] = b'X' + bytes(63)
        with self.assertRaises(GeneralizedDeleteError):
            self.candidate(fixed=fixed)

    def test_directory_root_wrong_identity_offset_and_unsupported_type_refuse(self):
        blob = nested_library()
        before = parse_backup_blob(blob)
        for path, offset in (('root', 0x40), ('root\\folder', 0xc0),
                             ('root\\outside.txt', 0x100), ('root\\folder\\missing.txt', 0x1c0),
                             ('root\\folder\\first.txt', 0x1c1), ('root\\folder\\first.txt', True)):
            with self.subTest(path=path, offset=offset), self.assertRaises(DeleteModelError):
                build_one_nested_file_delete_model(before, path, offset)
        changed = bytearray(blob); changed[0x1c1:0x1c4] = b'bin'
        with self.assertRaises(DeleteModelError):
            build_one_nested_file_delete_model(parse_backup_blob(_checksum(changed)),
                                              'root\\folder\\first.bin', 0x1c0)

    def test_ambiguous_native_names_invalid_prefix_and_missing_parent_marker_refuse(self):
        blob = nested_library()
        changes = []
        # Same native stem as a sibling BMP, even across extension.
        changed = bytearray(blob); changed[0x1c0+24:0x200] = b'IMAGE' + bytes(35); changes.append(changed)
        changed = bytearray(blob); changed[0xc0+24:0x100] = b'bad/name' + bytes(32); changes.append(changed)
        changed = bytearray(blob); changed[0x1c0+20:0x1c0+24] = (0x10200).to_bytes(4, 'big'); changes.append(changed)
        changed = bytearray(blob); changed[0x180+24:0x1c0] = b'not-marker' + bytes(30); changes.append(changed)
        changed = bytearray(blob); changed[0x1c0+24:0x200] = b'x' * 40; changes.append(changed)
        for changed in changes:
            with self.subTest(sha=hashlib.sha256(changed).hexdigest()), self.assertRaises((DeleteModelError, ValueError)):
                parsed = parse_backup_blob(_checksum(changed))
                target = parsed.record_at(0x1c0)
                path = '\\'.join(parsed.paths[0x1c0]) + '.' + target.extension
                build_one_nested_file_delete_model(parsed, path, 0x1c0)

    def test_overlapping_child_tables_or_missing_marker_reference_refuse(self):
        blob = nested_library()
        changed = bytearray(blob)
        changed[0x200+4:0x200+8] = (0x140).to_bytes(4, "big")
        changed[0x200+8:0x200+12] = (64).to_bytes(4, "big")
        changed[0x300:0x340] = make_record(0xd0, "", 0, 64, "..")
        with self.assertRaisesRegex(DeleteModelError, "overlap"):
            build_one_nested_file_delete_model(parse_backup_blob(_checksum(changed)),
                                              "root\\folder\\first.txt", 0x1c0)
        changed = bytearray(blob)
        changed[0x340+4:0x340+8] = (0xdeadc0de).to_bytes(4, "big")
        with self.assertRaisesRegex(DeleteModelError, "missing record"):
            build_one_nested_file_delete_model(parse_backup_blob(_checksum(changed)),
                                              "root\\folder\\first.txt", 0x1c0)
        changed = bytearray(blob)
        changed[0x200+8:0x200+12] = bytes(4)
        with self.assertRaisesRegex(DeleteModelError, "orphan|leading marker"):
            build_one_nested_file_delete_model(parse_backup_blob(_checksum(changed)),
                                              "root\\folder\\first.txt", 0x1c0)

    def test_extra_payload_timestamp_path_header_padding_marker_changes_fail_verifier(self):
        candidate = self.candidate()
        after = parse_backup_blob(candidate.candidate_blob)
        survivor = next(r for r in after.records if r.kind == 'file')
        variants = [candidate.baseline.data, rename_existing_record(after, survivor.offset, 'other')]
        for offset in (survivor.offset+12, after.header.content_start+survivor.field_04_be32+16,
                       after.header.content_start+survivor.field_04_be32+16+survivor.field_08_be32,
                       0x20, 0x80+12):
            changed = bytearray(candidate.candidate_blob); changed[offset] ^= 1
            variants.append(_checksum(changed))
        for changed in variants:
            with self.subTest(sha=hashlib.sha256(changed).hexdigest()), self.assertRaises(DeleteModelError):
                verify_nested_file_delete_model(candidate.baseline, changed,
                    candidate.target_path, candidate.target_record_offset)
            with self.assertRaises(GeneralizedDeleteVerificationError):
                poisoned = replace(candidate, candidate_model=replace(candidate.candidate_model, candidate_blob=changed))
                verify_nested_file_delete_readback(poisoned, self.post(poisoned), completion=0,
                                                  now=self.now, max_age_seconds=None)
        fixed = dict(zip(range(0x1b, 0x20), candidate.fixed_state.after)); fixed[0x1c] = b'X'+bytes(63)
        with self.assertRaises(GeneralizedDeleteVerificationError):
            verify_nested_file_delete_readback(candidate, self.post(candidate, fixed=fixed), completion=0,
                                              now=self.now, max_age_seconds=None)

    def test_host_candidate_and_existing_nested_txt_cannot_authorize_sender(self):
        nested = self.candidate()
        with self.assertRaisesRegex(GeneralizedDeleteError, 'host-only'):
            authorize_generalized_delete(nested, confirmation=DELETE_GENERALIZED_CONFIRMATION_PHRASE)
        for offset in (0x1c0, 0x300):
            parsed = nested.baseline
            path = '\\'.join(parsed.paths[offset]) + '.txt'
            candidate = build_generalized_delete_candidate(nested.backup.directory, path, offset,
                                                           now=self.now, max_age_seconds=None)
            auth = authorize_generalized_delete(candidate, confirmation=DELETE_GENERALIZED_CONFIRMATION_PHRASE)
            # Normal TXT authorization and arbitrary audit labels never admit nested sending.
            candidate.audit['safety']['execution_available'] = True
            candidate.audit['operation'] = 'delete_one_existing_txt'
            for value in (candidate, nested):
                with self.assertRaisesRegex(GeneralizedDeleteError, 'host-only'):
                    GeneralizedDeleteSenderBinding(auth, value)
                with self.assertRaisesRegex(GeneralizedDeleteError, 'host-only'):
                    bind_generalized_delete_sender(auth, value, now=self.now, max_age_seconds=None)
            binding = object.__new__(GeneralizedDeleteSenderBinding)
            for key, value in (('candidate', candidate), ('authorization', auth), ('now', self.now), ('max_age_seconds', None)):
                object.__setattr__(binding, key, value)
            with self.assertRaisesRegex(GeneralizedDeleteError, 'host-only'):
                binding.revalidate(candidate.transaction)

    def test_guarded_generalized_workflow_refuses_nested_before_fake_sender(self):
        sends = []
        def capture(destination, **_kwargs):
            return _write_archive(destination, nested_library(), self.now,
                                  fixed_state={c: bytes(64) for c in range(0x1b, 0x20)})
        workflow = GuardedGeneralizedDeleteWorkflow(capture, FakeDeleteTransport(lambda *_args, **_kwargs: sends.append(1)))
        with self.assertRaises(GeneralizedDeleteWorkflowError) as raised:
            workflow.run(backup_destination=self.root/'capture', post_delete_destination=self.root/'post',
                target_path='root\\folder\\first.txt', target_record_offset=0x1c0,
                confirmation=DELETE_GENERALIZED_CONFIRMATION_PHRASE, fake_transport=True,
                max_age_seconds=None)
        self.assertEqual(raised.exception.stage, 'authorization')
        self.assertFalse(raised.exception.write_started)
        self.assertEqual(sends, [])

    def test_existing_p18_040_reconstructed_hierarchy_all_five_leaves(self):
        try:
            from test_p18_040_nested_transfer import NestedTransferHostTests
        except ModuleNotFoundError:
            from tests.test_p18_040_nested_transfer import NestedTransferHostTests
        fixture = NestedTransferHostTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        added, _fixed = fixture._candidate()
        parsed = parse_backup_blob(added.candidate_blob)
        counts = {"txt": 0, "bmp": 0}
        for row in parsed.records:
            parts = parsed.paths.get(row.offset, ())
            if row.kind != "file" or len(parts) < 3:
                continue
            path = "\\".join(parts) + "." + row.extension
            model = build_one_nested_file_delete_model(parsed, path, row.offset)
            after = verify_nested_file_delete_model(parsed, model.candidate_blob, path, row.offset)
            self.assertEqual(len(after.records), len(parsed.records) - 1)
            counts[row.extension] += 1
        self.assertEqual(counts, {"txt": 3, "bmp": 2})

    def test_nonzero_missing_completion_and_incomplete_post_backup_refuse(self):
        candidate = self.candidate()
        for completion in (None, True, '0', 1):
            with self.subTest(completion=completion), self.assertRaises(GeneralizedDeleteVerificationError):
                verify_nested_file_delete_readback(candidate, self.root/'absent', completion=completion,
                                                  now=self.now, max_age_seconds=None)
        with self.assertRaises(GeneralizedDeleteVerificationError):
            verify_nested_file_delete_readback(candidate, self.root/'absent', completion=0,
                                              now=self.now, max_age_seconds=None)


if __name__ == '__main__':
    unittest.main()
