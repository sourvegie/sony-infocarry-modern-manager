"""Root BMP offline transaction/authorization/readback; sender remains blocked."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import parse_backup_blob
from infocarry.backup_repack import rename_existing_record
from infocarry.delete_generalized import (
    DELETE_GENERALIZED_CONFIRMATION_PHRASE, GeneralizedDeleteError,
    GeneralizedDeleteSenderBinding, GeneralizedDeleteVerificationError,
    authorize_generalized_delete, bind_generalized_delete_sender,
    build_root_bmp_delete_candidate, verify_generalized_delete_readback,
)
from infocarry.write_artifact import build_staging_range
try:
    from test_root_bmp_delete_model import root_bitmap_library, _checksum
    from test_bitmap import make_monochrome_bmp
    from test_backup_duplicate import make_nested_blob
    from test_new_txt import _write_archive
except ModuleNotFoundError:
    from tests.test_root_bmp_delete_model import root_bitmap_library, _checksum
    from tests.test_bitmap import make_monochrome_bmp
    from tests.test_backup_duplicate import make_nested_blob
    from tests.test_new_txt import _write_archive


class RootBitmapDeletePreparationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.count = 0

    def archive(self, blob, *, fixed=None, created=None):
        self.count += 1
        return _write_archive(self.root / str(self.count), blob, created or self.now,
                              fixed_state=fixed or {c: bytes(64) for c in range(0x1b, 0x20)})

    def prepare(self, *, blob=None, offset=None, fixed=None, **options):
        if blob is None:
            blob, offset = root_bitmap_library(**options)
        parsed = parse_backup_blob(blob)
        path = '\\'.join(parsed.paths[offset]) + '.' + parsed.record_at(offset).extension
        return build_root_bmp_delete_candidate(self.archive(blob, fixed=fixed), path,
                                               offset, now=self.now, max_age_seconds=None)

    def authorize(self, candidate):
        return authorize_generalized_delete(candidate, confirmation=DELETE_GENERALIZED_CONFIRMATION_PHRASE)

    def post(self, candidate, *, blob=None, fixed=None):
        return self.archive(candidate.candidate_blob if blob is None else blob,
                            fixed=fixed or dict(zip(range(0x1b, 0x20), candidate.fixed_state.after)))

    def test_first_middle_last_prefix_read_state_exact_eight_ranges_and_readback(self):
        for index in range(3):
            for prefix in (16, 32):
                for flag in (0x20, 0xe0):
                    with self.subTest(index=index, prefix=prefix, flag=flag):
                        candidate = self.prepare(index=index, prefix_bytes=prefix, flag=flag)
                        tx = candidate.transaction
                        self.assertEqual(tx.ranges, (candidate.fixed_state.range1,
                            candidate.fixed_state.grouped_values,
                            build_staging_range(0, len(candidate.candidate_blob)), b'',
                            candidate.candidate_blob[:64], b'', b'', candidate.candidate_blob[64:]))
                        self.assertEqual(tx.payload_length, 0x10000 + len(candidate.candidate_blob))
                        self.assertEqual(tx.concatenated_sha256,
                                         hashlib.sha256(b''.join(tx.ranges)).hexdigest())
                        auth = self.authorize(candidate)
                        self.assertEqual(auth.target_extension, 'bmp')
                        auth.revalidate(candidate, now=self.now, max_age_seconds=None)
                        self.assertEqual(auth.to_dict()['state'], 'authorized_for_host_review_only')
                        self.assertFalse(auth.to_dict()['execution_available'])
                        self.assertEqual(candidate.audit['operation'], 'delete_one_existing_bmp')
                        self.assertFalse(candidate.audit['safety']['execution_available'])
                        result = verify_generalized_delete_readback(candidate, self.post(candidate),
                            completion=0, now=self.now, max_age_seconds=None)
                        self.assertTrue(result.target_removed)
                        self.assertTrue(result.unrelated_payloads_unchanged)
                        self.assertTrue(result.unrelated_objects_unchanged)
                        after = parse_backup_blob(candidate.candidate_blob)
                        for old in candidate.baseline.records:
                            if old.offset == candidate.target_record_offset:
                                continue
                            new = after.record_at(old.offset - 64 if old.offset > candidate.target_record_offset else old.offset)
                            self.assertEqual(old.timestamp_be32, new.timestamp_be32)
                            if old.kind == 'file':
                                self.assertEqual(candidate.baseline.payload_parts(old), after.payload_parts(new))

    def test_safe_cp932_names_and_exact_known_prefixes(self):
        blob, offset = root_bitmap_library()
        for name in ('z', '日本語画像', 'x' * 39):
            changed = rename_existing_record(parse_backup_blob(blob), offset, name)
            candidate = self.prepare(blob=changed, offset=offset)
            self.assertEqual(candidate.target_path, 'root\\' + name + '.bmp')

    def test_native_name_and_path_ambiguities_refuse(self):
        blob, offset = root_bitmap_library()
        for native in (b'x' * 40, b'bad.name\0' + bytes(31), b' root\0' + bytes(34),
                       b'root\0' + bytes(35), b'bad/name\0' + bytes(31)):
            changed = bytearray(blob)
            changed[offset+24:offset+64] = native
            with self.subTest(native=native), self.assertRaises(GeneralizedDeleteError):
                self.prepare(blob=_checksum(changed), offset=offset)
        for extension in (b'txt', b'bmp'):
            changed = bytearray(blob)
            if extension == b'bmp':
                changed[0xc0:0x100] = changed[offset:offset+64]
            changed[0xc1:0xc4] = extension
            changed[0xc0+24:0x100] = b'B' + bytes(39)
            with self.subTest(extension=extension), self.assertRaisesRegex(GeneralizedDeleteError, 'ambiguous'):
                self.prepare(blob=_checksum(changed), offset=offset)

    def test_unsupported_prefix_state_and_bitmap_refuse(self):
        blob, offset = root_bitmap_library()
        for selector in (0x101, 0x10200, 0x300):
            changed = bytearray(blob)
            changed[offset+20:offset+24] = selector.to_bytes(4, 'big')
            with self.subTest(selector=selector), self.assertRaises(GeneralizedDeleteError):
                build_root_bmp_delete_candidate(self.archive(_checksum(changed)), 'root\\b.bmp', offset,
                                               now=self.now, max_age_seconds=None)
        changed = bytearray(blob); changed[offset] = 0x7f
        with self.assertRaises(GeneralizedDeleteError):
            self.prepare(blob=_checksum(changed), offset=offset)
        for payload in (b'bad', make_monochrome_bmp(240, 320)):
            changed, offset = root_bitmap_library(payload=payload)
            with self.subTest(length=len(payload)), self.assertRaises(GeneralizedDeleteError):
                build_root_bmp_delete_candidate(self.archive(changed), 'root\\b.bmp', offset,
                                               now=self.now, max_age_seconds=None)

    def test_nested_directory_missing_and_wrong_offset_refuse(self):
        blob, offset = root_bitmap_library()
        archive = self.archive(blob)
        for path, bound in (('root', 0x40), ('root\\missing.bmp', offset),
                            ('root\\b.bmp', offset+1), ('root\\b.bmp', True),
                            ('root\\b.bmp', 0xffffffc0)):
            with self.subTest(path=path, bound=bound), self.assertRaises(GeneralizedDeleteError):
                build_root_bmp_delete_candidate(archive, path, bound, now=self.now, max_age_seconds=None)
        nested = bytearray(make_nested_blob(make_monochrome_bmp(237, 320)))
        nested[0x141:0x144] = b'bmp'
        with self.assertRaisesRegex(GeneralizedDeleteError, 'root-level'):
            build_root_bmp_delete_candidate(self.archive(_checksum(nested)), 'root\\folder\\source.bmp',
                                           0x140, now=self.now, max_age_seconds=None)

    def test_protected_survivor_references_rebase_without_other_changes(self):
        blob, offset = root_bitmap_library()
        for command in (0x1b, 0x1f):
            for ref in (0xc0, 0x140):
                fixed = {c: bytes(64) for c in range(0x1b, 0x20)}
                state = bytearray(64)
                relative = ref - 0x40
                if command == 0x1f:
                    state[:4] = relative.to_bytes(4, 'big')
                    state[8:12] = (0x80000000).to_bytes(4, 'big')
                    index = 0
                else:
                    state[:4] = (1).to_bytes(4, 'big')
                    state[8:12] = relative.to_bytes(4, 'big')
                    index = 8
                fixed[command] = bytes(state)
                candidate = self.prepare(blob=blob, offset=offset, fixed=fixed)
                expected = bytearray(state)
                expected[index:index+4] = (relative-(64 if ref > offset else 0)).to_bytes(4, 'big')
                self.assertEqual(candidate.fixed_state.after[command-0x1b], bytes(expected))
                for c in range(0x1b, 0x20):
                    if c != command:
                        self.assertEqual(candidate.fixed_state.after[c-0x1b], fixed[c])
                verify_generalized_delete_readback(candidate, self.post(candidate), completion=0,
                                                  now=self.now, max_age_seconds=None)

    def test_protected_target_and_active_marks_refuse(self):
        for command in (0x1b, 0x1c, 0x1d, 0x1e, 0x1f):
            fixed = {c: bytes(64) for c in range(0x1b, 0x20)}
            raw = bytearray(64)
            if command == 0x1f:
                raw[:4] = (0x100-0x40).to_bytes(4, 'big')
                raw[8:12] = (0x80000000).to_bytes(4, 'big')
            else:
                raw[:4] = (1).to_bytes(4, 'big')
                raw[8:12] = (0x100-0x40).to_bytes(4, 'big')
            fixed[command] = bytes(raw)
            with self.subTest(command=command), self.assertRaises(GeneralizedDeleteError):
                self.prepare(fixed=fixed)

    def test_authorization_binds_candidate_target_type_state_and_transaction(self):
        candidate = self.prepare()
        auth = self.authorize(candidate)
        for field, value in (('target_path', 'root\\other.bmp'), ('target_record_offset', 0xc0),
                             ('target_payload_sha256', '0'*64), ('candidate_blob_sha256', '0'*64),
                             ('transaction_sha256', '0'*64), ('baseline_manifest_sha256', '0'*64),
                             ('baseline_blob_sha256', '0'*64), ('target_extension', 'txt')):
            with self.subTest(field=field), self.assertRaises(GeneralizedDeleteError):
                replace(auth, **{field:value}).require_same_candidate(candidate)
        with self.assertRaises(GeneralizedDeleteError):
            authorize_generalized_delete(candidate, confirmation='DELETE OTHER ITEM')
        changed = replace(candidate.candidate_model, target_payload_sha256='0'*64)
        with self.assertRaises(GeneralizedDeleteError):
            auth.require_same_candidate(replace(candidate, candidate_model=changed))
        ranges = list(candidate.transaction.ranges)
        ranges[0] = b'X' + ranges[0][1:]
        altered = replace(candidate, transaction=replace(candidate.transaction, ranges=tuple(ranges)))
        with self.assertRaises(GeneralizedDeleteError):
            auth.require_same_candidate(altered)

    def test_invalid_bmp_candidate_cannot_be_authorized_before_freezing(self):
        candidate = self.prepare()
        for changed_model in (
            replace(candidate.candidate_model, target_payload_sha256='0'*64),
            replace(candidate.candidate_model, candidate_blob=candidate.candidate_blob+b'X'),
        ):
            with self.assertRaises(GeneralizedDeleteError):
                self.authorize(replace(candidate, candidate_model=changed_model))
        ranges = list(candidate.transaction.ranges); ranges[0] = b'X'+ranges[0][1:]
        with self.assertRaises(GeneralizedDeleteError):
            self.authorize(replace(candidate, transaction=replace(candidate.transaction, ranges=tuple(ranges))))

    def test_stale_changed_backup_and_poisoned_baseline_refuse(self):
        candidate = self.prepare()
        auth = self.authorize(candidate)
        with self.assertRaisesRegex(GeneralizedDeleteError, 'revalidation'):
            auth.revalidate(candidate, now=self.now+timedelta(days=1), max_age_seconds=1)
        altered = bytearray(candidate.baseline.data)
        altered[0xc0+12:0xc0+16] = bytes(4)
        with self.assertRaisesRegex(GeneralizedDeleteError, 'baseline target identity'):
            auth.require_same_candidate(replace(candidate, baseline=parse_backup_blob(_checksum(altered))))
        object_file = candidate.backup.directory / candidate.backup.object_filename('0x8004:backup-blob')
        object_file.write_bytes(object_file.read_bytes()+b'X')
        with self.assertRaises(GeneralizedDeleteError):
            auth.revalidate(candidate, now=self.now, max_age_seconds=None)

    def test_bmp_sender_binding_rejects_constructor_helper_and_direct_revalidate(self):
        candidate = self.prepare()
        auth = self.authorize(candidate)
        # An audit label is deliberately not the execution authority.
        candidate.audit['operation'] = 'delete_one_existing_txt'
        candidate.audit['safety']['execution_available'] = True
        for approval in (auth, replace(auth, target_extension='txt')):
            with self.assertRaisesRegex(GeneralizedDeleteError, 'host-only'):
                GeneralizedDeleteSenderBinding(approval, candidate)
            with self.assertRaisesRegex(GeneralizedDeleteError, 'host-only'):
                bind_generalized_delete_sender(approval, candidate, now=self.now, max_age_seconds=None)
        binding = object.__new__(GeneralizedDeleteSenderBinding)
        for name, value in (('authorization', auth), ('candidate', candidate),
                            ('now', self.now), ('max_age_seconds', None)):
            object.__setattr__(binding, name, value)
        with self.assertRaisesRegex(GeneralizedDeleteError, 'host-only'):
            binding.revalidate(candidate.transaction)

    def test_missing_malformed_nonzero_completion_and_post_backup_never_retry(self):
        candidate = self.prepare()
        for completion in (None, True, '0', 1, 0x10001):
            with self.subTest(completion=completion), self.assertRaises(GeneralizedDeleteVerificationError) as raised:
                verify_generalized_delete_readback(candidate, self.root/'missing', completion=completion,
                                                  now=self.now, max_age_seconds=None)
            self.assertFalse(raised.exception.automatic_retry_allowed)
        with self.assertRaises(GeneralizedDeleteVerificationError):
            verify_generalized_delete_readback(candidate, self.root/'missing', completion=0,
                                              now=self.now, max_age_seconds=None)

    def test_changed_path_payload_timestamp_checksum_or_state_fail_readback(self):
        candidate = self.prepare()
        after = parse_backup_blob(candidate.candidate_blob)
        first_file = next(r for r in after.records if r.kind=='file')
        bad = []
        bad.append(candidate.baseline.data)  # target still present
        bad.append(rename_existing_record(after, first_file.offset, 'changed'))
        data = bytearray(candidate.candidate_blob)
        data[first_file.offset+12:first_file.offset+16] = bytes(4)
        bad.append(_checksum(data))
        data = bytearray(candidate.candidate_blob)
        data[after.header.content_start+first_file.field_04_be32+first_file.payload_prefix_length] ^= 1
        bad.append(_checksum(data))
        data = bytearray(candidate.candidate_blob); data[0x1c] ^= 1
        bad.append(bytes(data))
        for blob in bad:
            with self.subTest(sha=hashlib.sha256(blob).hexdigest()), self.assertRaises(GeneralizedDeleteVerificationError):
                verify_generalized_delete_readback(candidate, self.post(candidate, blob=blob), completion=0,
                                                  now=self.now, max_age_seconds=None)
        fixed = dict(zip(range(0x1b, 0x20), candidate.fixed_state.after)); fixed[0x1b]=b'X'+bytes(63)
        with self.assertRaisesRegex(GeneralizedDeleteVerificationError, 'fixed state'):
            verify_generalized_delete_readback(candidate, self.post(candidate, fixed=fixed), completion=0,
                                              now=self.now, max_age_seconds=None)
        post = self.post(candidate)
        manifest = json.loads((post/'manifest.json').read_text())
        manifest['state'] = 'incomplete'
        (post/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(GeneralizedDeleteVerificationError):
            verify_generalized_delete_readback(candidate, post, completion=0,
                                              now=self.now, max_age_seconds=None)


if __name__ == '__main__':
    unittest.main()
