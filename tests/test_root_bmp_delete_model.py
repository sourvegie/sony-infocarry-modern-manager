"""Pure host-only BMP modeling. No transaction, authorization or USB path."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import calculate_backup_checksum, parse_backup_blob
from infocarry.backup_repack import delete_existing_file
from infocarry.delete_model import DeleteModelError, build_one_root_bmp_delete_model, build_one_txt_delete_model
from infocarry.delete_generalized import GeneralizedDeleteError, build_generalized_delete_candidate
from infocarry.delete_state import DeleteStateError, derive_preserved_delete_state
from infocarry.desktop import DesktopWorkflowModel
from infocarry.device_library_delete_execution import DeviceLibraryDeleteError, select_device_library_delete
from infocarry.write_gate import verify_fresh_backup
try:
    from test_bitmap import make_monochrome_bmp
    from test_delete_hardening import _make_root_siblings
    from test_backup_format import make_text_blob
    from test_backup_duplicate import make_nested_blob
    from test_new_txt import _write_archive
except ModuleNotFoundError:
    from tests.test_bitmap import make_monochrome_bmp
    from tests.test_delete_hardening import _make_root_siblings
    from tests.test_backup_format import make_text_blob
    from tests.test_backup_duplicate import make_nested_blob
    from tests.test_new_txt import _write_archive


def _checksum(blob):
    blob = bytearray(blob)
    blob[0x1c:0x20] = calculate_backup_checksum(blob).to_bytes(4, 'big')
    return bytes(blob)


def root_bitmap_library(index=1, *, prefix_bytes=16, flag=0xe0, payload=None):
    payload = make_monochrome_bmp(237, 320) if payload is None else payload
    payloads = [b'first unchanged\r\n', b'second unchanged\r\n', b'third unchanged\r\n']
    payloads[index] = payload
    base = parse_backup_blob(_make_root_siblings(payloads))
    metadata = bytearray(base.data[:base.header.content_start])
    content = bytearray()
    target = 0xc0 + index * 64
    for row in base.records:
        if row.kind != 'file':
            continue
        prefix, data = base.payload_parts(row)
        metadata[row.offset+4:row.offset+8] = len(content).to_bytes(4, 'big')
        metadata[row.offset+12:row.offset+16] = (1791000100 + row.offset).to_bytes(4, 'big')
        if row.offset == target:
            metadata[row.offset] = flag
            metadata[row.offset+1:row.offset+4] = b'bmp'
            metadata[row.offset+20:row.offset+24] = (prefix_bytes // 16 << 8).to_bytes(4, 'big')
            prefix = prefix[:prefix_bytes]
        content.extend(prefix + data)
        content.extend(b'\0' * (-len(content) % 4))
    total = len(metadata) + len(content) + 4
    metadata[0x18:0x1c] = (total-1).to_bytes(4, 'big')
    metadata[0x34:0x38] = len(content).to_bytes(4, 'big')
    metadata[0x38:0x3c] = total.to_bytes(4, 'big')
    return _checksum(metadata + content + b'\xff'*4), target


class RootBitmapDeleteModelTests(unittest.TestCase):
    def model(self, **kwargs):
        blob, offset = root_bitmap_library(**kwargs)
        parsed = parse_backup_blob(blob)
        name = parsed.record_at(offset).name
        result = build_one_root_bmp_delete_model(parsed, f'root\\{name}.bmp', offset)
        return parsed, offset, result

    def test_first_middle_last_read_unread_prefix_variants_preserve_survivors(self):
        for index in range(3):
            for prefix in (16, 32):
                for flag in (0xe0, 0x20):
                    with self.subTest(index=index, prefix=prefix, flag=flag):
                        before, offset, result = self.model(index=index, prefix_bytes=prefix, flag=flag)
                        source = before.data
                        after = parse_backup_blob(result.candidate_blob)
                        self.assertEqual(before.data, source)
                        self.assertEqual(result.candidate_blob, delete_existing_file(before, offset))
                        self.assertEqual(set(before.paths.values())-set(after.paths.values()), {before.paths[offset]})
                        self.assertEqual(set(after.paths.values())-set(before.paths.values()), set())
                        self.assertEqual(len(after.records), len(before.records)-1)
                        for old in before.records:
                            if old.offset == offset:
                                continue
                            new = after.record_at(old.offset-64 if old.offset>offset else old.offset)
                            self.assertEqual(new.timestamp_be32, old.timestamp_be32)
                            old_raw, new_raw = bytes.fromhex(old.raw_hex), bytes.fromhex(new.raw_hex)
                            self.assertEqual(old_raw[:4]+old_raw[12:], new_raw[:4]+new_raw[12:])
                            if old.kind == 'file':
                                self.assertEqual(before.payload_parts(old), after.payload_parts(new))
                                self.assertEqual(old_raw[8:12], new_raw[8:12])
                        self.assertEqual(calculate_backup_checksum(result.candidate_blob), after.header.stored_checksum)
                        self.assertEqual(result.audit['operation'], 'delete_one_existing_bmp')
                        self.assertEqual(result.audit['capability_status'], 'host_offline_not_live_enabled')
                        for key in ('device_accessed', 'authorization_created', 'transaction_constructed', 'execution_available', 'physical_behavior_proven'):
                            self.assertFalse(result.audit['safety'][key])

    def test_sole_root_bitmap_and_top_down_profile(self):
        for prefix in (0x100, 0x200):
            for top_down in (False, True):
                parsed = parse_backup_blob(make_text_blob(make_monochrome_bmp(237,320,top_down=top_down), field14=prefix, extension='bmp'))
                model = build_one_root_bmp_delete_model(parsed, 'root\\memo.bmp', 0xc0)
                after = parse_backup_blob(model.candidate_blob)
                self.assertEqual(after.paths, {0x40: ('root',)})
                self.assertTrue(all(r.kind != 'file' for r in after.records))
                self.assertFalse(model.audit['safety']['execution_available'])

    def test_rejects_txt_nested_root_directory_wrong_offset_and_wrong_path(self):
        parsed = parse_backup_blob(make_text_blob())
        with self.assertRaisesRegex(DeleteModelError, 'BMP'):
            build_one_root_bmp_delete_model(parsed, 'root\\memo.txt', 0xc0)
        for path, offset in (('root',0x40), ('root\\wrong.bmp',0xc0), ('root\\memo.bmp',0xc1), ('root\\memo.bmp',True)):
            with self.subTest(path=path, offset=offset), self.assertRaises(DeleteModelError):
                build_one_root_bmp_delete_model(parsed, path, offset)
        nested = bytearray(make_nested_blob(make_monochrome_bmp(237,320)))
        nested[0x141:0x144] = b'bmp'
        with self.assertRaisesRegex(DeleteModelError, 'root-level'):
            build_one_root_bmp_delete_model(parse_backup_blob(_checksum(nested)), 'root\\folder\\source.bmp', 0x140)

    def test_invalid_bitmap_profiles_rejected(self):
        valid = make_monochrome_bmp(237,320)
        color = bytearray(valid); color[28:30] = (24).to_bytes(2,'little')
        compressed = bytearray(valid); compressed[30:34] = (1).to_bytes(4,'little')
        for payload in (b'not a BMP', valid[:-1], valid+b'trailer'):
            with self.subTest(length=len(payload)), self.assertRaises(ValueError):
                self.model(payload=payload)  # rejected by the complete image parser
        for payload in (make_monochrome_bmp(240,320), bytes(color), bytes(compressed)):
            with self.subTest(length=len(payload)), self.assertRaisesRegex(DeleteModelError, 'payload is unsupported'):
                self.model(payload=payload)

    def test_unknown_prefix_or_file_state_and_overlapping_content_rejected(self):
        before, offset, _ = self.model()
        for value in (0x300, 0x101):
            changed = bytearray(before.data)
            changed[offset+20:offset+24] = value.to_bytes(4,'big')
            with self.subTest(value=value), self.assertRaises(ValueError):
                parsed = parse_backup_blob(_checksum(changed))
                build_one_root_bmp_delete_model(parsed, 'root\\b.bmp', offset)
        changed = bytearray(before.data); changed[offset] = 0x7f
        with self.assertRaises(ValueError):
            parsed = parse_backup_blob(_checksum(changed))
            build_one_root_bmp_delete_model(parsed, 'root\\b.bmp', offset)
        changed = bytearray(before.data)
        changed[0xc4:0xc8] = before.record_at(offset).field_04_be32.to_bytes(4,'big')
        with self.assertRaisesRegex(DeleteModelError, 'overlaps'):
            build_one_root_bmp_delete_model(parse_backup_blob(_checksum(changed)), 'root\\b.bmp', offset)

    def test_ambiguous_native_path_rejected(self):
        before, offset, _ = self.model()
        changed = bytearray(before.data)
        changed[0xc0:0x100] = bytes.fromhex(before.record_at(offset).raw_hex)
        with self.assertRaisesRegex(DeleteModelError, 'ambiguous'):
            build_one_root_bmp_delete_model(parse_backup_blob(_checksum(changed)), 'root\\b.bmp', offset)

    def test_protected_state_rebases_only_survivor_references_and_refuses_target(self):
        before, offset, model = self.model()
        after = parse_backup_blob(model.candidate_blob)
        with tempfile.TemporaryDirectory() as directory:
            for reference, accepted in ((0xc0, True), (0x140, True), (offset, False)):
                fixed = {c: bytes(64) for c in range(0x1b,0x20)}
                history = bytearray(64)
                history[:4] = (1).to_bytes(4,'big')
                history[8:12] = (reference-before.header.metadata_start).to_bytes(4,'big')
                fixed[0x1b] = bytes(history)
                baseline = Path(directory)/f'before-{reference}'
                _write_archive(baseline, before.data, datetime.now(timezone.utc), fixed_state=fixed)
                verified = verify_fresh_backup(baseline, max_age_seconds=None)
                if not accepted:
                    with self.assertRaisesRegex(DeleteStateError, 'referenced'):
                        derive_preserved_delete_state(verified, before, after, target_record_offset=offset)
                else:
                    state = derive_preserved_delete_state(verified, before, after, target_record_offset=offset)
                    expected = reference-before.header.metadata_start-(64 if reference>offset else 0)
                    self.assertEqual(int.from_bytes(state.after[0][8:12],'big'), expected)
                    self.assertEqual(state.after[0][:8]+state.after[0][12:], fixed[0x1b][:8]+fixed[0x1b][12:])
                    self.assertEqual(state.after[1:], tuple(fixed[c] for c in range(0x1c,0x20)))

    def test_new_host_model_cannot_enter_existing_txt_candidate_or_device_ui_gate(self):
        before, offset, model = self.model()
        with self.assertRaisesRegex(DeleteModelError, 'TXT'):
            build_one_txt_delete_model(before, 'root\\b.bmp', offset)
        with tempfile.TemporaryDirectory() as directory:
            baseline=Path(directory)/'before'
            _write_archive(baseline, before.data, datetime.now(timezone.utc), fixed_state={c:bytes(64) for c in range(0x1b,0x20)})
            with self.assertRaisesRegex(GeneralizedDeleteError, 'TXT'):
                build_generalized_delete_candidate(baseline, 'root\\b.bmp', offset, max_age_seconds=None)
            desktop=DesktopWorkflowModel();desktop.load_backup(baseline)
            with self.assertRaises(DeviceLibraryDeleteError):
                select_device_library_delete(desktop, (offset,))
        self.assertFalse(model.audit['safety']['execution_available'])

    def test_deterministic_model_preserves_original_input(self):
        before, offset, first = self.model()
        second=build_one_root_bmp_delete_model(before, 'root\\b.bmp', offset)
        self.assertEqual(first, second)
        self.assertEqual(first.source_blob_sha256, second.source_blob_sha256)


if __name__ == '__main__':
    unittest.main()
