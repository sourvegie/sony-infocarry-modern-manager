"""Experimental nested BMP admission; temporary safety stores and USB fakes only."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import unittest
from unittest.mock import patch

from infocarry.backup_duplicate import add_file_from_template
from infocarry.backup_format import parse_backup_blob
from infocarry.backup_repack import delete_existing_file, rename_existing_record
from infocarry.delete_generalized import bind_generalized_delete_sender
from infocarry.delete_model import verify_nested_file_delete_model
from infocarry.delete_workflow import (
    build_nested_bmp_delete, NESTED_BMP_DELETE_LIVE_PROFILE,
    NESTED_BMP_DELETE_VALIDATION_PATH, ROOT_BMP_DELETE_FIXTURE_BYTES,
)
from infocarry.desktop import DesktopWorkflowModel
from infocarry.device_library_delete_execution import DeviceLibraryDeleteService, load_verified_delete_result
from infocarry.protocol import TransferCancelledError
from infocarry.write_gate import verify_fresh_backup
from test_bitmap import make_monochrome_bmp
from test_nested_file_delete import nested_library
from test_new_txt import _write_archive
from test_root_bmp_delete_model import _checksum
import test_device_library_delete_ui as ui_helpers
import test_root_txt_placement as placement_helpers


def ordinary_nested_bmp(*, name='資料_01', top_down=False, first=False):
    payload = bytearray(make_monochrome_bmp(237, 320, top_down=top_down))
    payload[-32:] = bytes(range(32))  # Deliberately distinct from the physical fixture.
    blob = add_file_from_template(parse_backup_blob(nested_library()), 0x200, 0x240,
                                  name, bytes(payload), timestamp_be32=1792000100,
                                  fresh_new_allocation=True)
    target = 0x340
    if first:
        changed = bytearray(blob)
        changed[0x300:0x340], changed[0x340:0x380] = blob[0x340:0x380], blob[0x300:0x340]
        blob, target = _checksum(changed), 0x300
    return blob, target


def changed_bytes(blob, offset, value, *, checksum=True):
    changed = bytearray(blob)
    changed[offset:offset+len(value)] = value
    return _checksum(changed) if checksum else bytes(changed)


class NestedBmpPromotionTests(unittest.TestCase):
    def data(self, *, blob=None, offset=None, fixed=None, **options):
        helper = placement_helpers.RootPlacementTests()
        self.addCleanup(helper.doCleanups)
        case = helper.setup_case(media='bmp', **options)
        if blob is None:
            blob, default_offset = ordinary_nested_bmp()
        else:
            default_offset = 0x340
        case[2]['blob'] = blob
        if fixed is not None:
            case[2]['fixed'] = fixed
        model = DesktopWorkflowModel()
        model.load_backup(_write_archive(case[0]/'displayed', blob, datetime.now(timezone.utc),
                                         fixed_state=case[2]['fixed']))
        service = DeviceLibraryDeleteService(lambda: case[4].runtime)
        self.addCleanup(service.discard)
        selection = service.select(model, [default_offset if offset is None else offset])
        return case, model, selection, service

    def prepare(self, data):
        prepared = data[3].prepare(data[2])
        data[0][2]['bundle'] = prepared.bundle
        return prepared

    def assert_refused(self, blob, *, offset=0x340, fixed=None):
        helper = placement_helpers.RootPlacementTests()
        self.addCleanup(helper.doCleanups)
        case = helper.setup_case(media='bmp')
        archive = _write_archive(case[0]/'rejected', blob, datetime.now(timezone.utc),
                                 fixed_state=fixed or case[2]['fixed'])
        # The full builder must independently refuse even if UI admission is cheap.
        try:
            parsed = parse_backup_blob(blob)
            parts = parsed.paths.get(offset, ('root', 'folder', 'sub', '資料_01'))
        except ValueError:
            parts = ('root', 'folder', 'sub', '資料_01')
        path = '\\'.join(parts) + '.bmp'
        with self.assertRaises((ValueError, RuntimeError)):
            build_nested_bmp_delete(archive, path, target_record_offset=offset)
        model = DesktopWorkflowModel()
        try:
            model.load_backup(archive)
        except (ValueError, RuntimeError):
            return
        service = DeviceLibraryDeleteService(lambda: (_ for _ in ()).throw(AssertionError('runtime opened')))
        try:
            selection = service.select(model, [offset])
        except ValueError:
            return
        self.assertFalse(service.execution_available(selection))
        with self.assertRaises(ValueError):
            service.prepare(selection)
        self.assertEqual(case[3].calls, [])

    def test_cp932_pixels_orientation_and_native_position_guarded_success(self):
        for top_down, first, name in ((False, False, '資料_01'), (True, True, 'x'*39)):
            with self.subTest(top_down=top_down, first=first, name=name):
                blob, offset = ordinary_nested_bmp(name=name, top_down=top_down, first=first)
                data = self.data(blob=blob, offset=offset)
                case, model, selection, service = data
                self.assertTrue(selection.general_nested_bmp)
                self.assertTrue(service.execution_available(selection))
                prepared = self.prepare(data)
                bundle = prepared.bundle
                self.assertEqual(bundle.operation_profile, NESTED_BMP_DELETE_LIVE_PROFILE)
                self.assertEqual(bundle._envelope()['capability_status'], 'experimental_unread_nested_bmp')
                self.assertNotEqual(bundle.source_path.read_bytes(), ROOT_BMP_DELETE_FIXTURE_BYTES)
                self.assertIsNone(bundle.restoration_objects)
                self.assertEqual(bundle.before_backup.object_count, 8)
                self.assertIsNone(case[5].read_claim(bundle.seal_sha256))
                with self.assertRaisesRegex(Exception, 'nested'):
                    bind_generalized_delete_sender(bundle.authorization.core.binding, bundle.candidate.core)
                result = service.execute_once(prepared, confirmed=True)
                self.assertEqual(result.completion, 0)
                self.assertEqual(result.after_backup.object_count, 8)
                self.assertEqual(result.audit['workflow']['sender_calls'], 1)
                self.assertFalse(result.audit['workflow']['automatic_retry_allowed'])
                self.assertEqual(sum(c[0] == 'control_out' for c in case[3].calls), 1)
                self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
                self.assertIsNone(case[5].read_sender_in_flight())
                self.assertIsNone(case[6].read())
                load_verified_delete_result(model, result)
                self.assertNotIn(selection.row.display_name, [r.display_name for r in model.rows()])
                self.assertTrue(any(r.display_name.endswith('deep.txt') for r in model.rows()))
                self.assertEqual(model.state.source_blob_sha256, bundle.candidate_blob_sha256)
                with self.assertRaises(Exception):
                    service.execute_once(prepared, confirmed=True)

    def test_confirmation_names_full_path_and_hides_internal_identity(self):
        data = self.data()
        prepared = self.prepare(data)
        self.assertIn(data[2].row.display_name, prepared.confirmation_message)
        for internal in ('SHA', 'fingerprint', 'claim', 'marker', prepared.bundle.seal_sha256):
            self.assertNotIn(internal, prepared.confirmation_message)
        for offsets, model_name in (([0x300, 0x340], 'VNW-V15'), ([0x200], 'VNW-V15'),
                                    ([0x340], 'VNW-V10')):
            with self.assertRaises(ValueError):
                data[3].select(data[1], offsets, device_model=model_name)

    def test_native_unread_prefix_selector_and_opaque_fields_required(self):
        blob, target = ordinary_nested_bmp()
        parsed = parse_backup_blob(blob)
        start = parsed.header.content_start + parsed.record_at(target).field_04_be32
        for offset, value in ((target, b'\x20'), (target+16, bytes(4)),
                              (target+20, (0x200).to_bytes(4, 'big')), (start, b'\x00')):
            with self.subTest(offset=offset):
                self.assert_refused(changed_bytes(blob, offset, value))

    def test_noncanonical_bmp_headers_dimensions_and_payload_length_refuse(self):
        blob, target = ordinary_nested_bmp()
        parsed = parse_backup_blob(blob)
        payload = parsed.header.content_start + parsed.record_at(target).field_04_be32 + 16
        for offset, value in ((payload, b'ZZ'), (payload+18, (236).to_bytes(4, 'little')),
                              (payload+22, (319).to_bytes(4, 'little')),
                              (payload+28, (24).to_bytes(2, 'little')),
                              (payload+30, (1).to_bytes(4, 'little')),
                              (payload+10, (66).to_bytes(4, 'little')),
                              (target+8, (10301).to_bytes(4, 'big'))):
            with self.subTest(offset=offset):
                self.assert_refused(changed_bytes(blob, offset, value))

    def test_unsafe_cp932_names_ancestors_and_ambiguous_native_stems_refuse(self):
        blob, target = ordinary_nested_bmp()
        for offset, value in ((target+24, b'bad/name'+bytes(32)),
                              (target+24, b'x'*40), (target+24, b'\x81\0'+bytes(38)),
                              (0x200+24, b'bad.name'+bytes(32)),
                              (0x300+24, '資料_01'.encode('cp932')+bytes(33))):
            with self.subTest(offset=offset, value=value[:10]):
                self.assert_refused(changed_bytes(blob, offset, value))

    def test_unsupported_depth_and_last_child_removal_refuse(self):
        blob, _target = ordinary_nested_bmp()
        self.assert_refused(blob, offset=0x240)  # One ancestor instead of two.
        empty_parent = delete_existing_file(parse_backup_blob(blob), 0x300)
        self.assert_refused(empty_parent, offset=0x300)

    def test_parent_marker_ownership_ordering_and_graph_refuse(self):
        blob, _target = ordinary_nested_bmp()
        for offset, value in ((0x280+4, (0xdead).to_bytes(4, 'big')),
                              (0x200+4, (0x140).to_bytes(4, 'big')),
                              (0x280+24, b'not-marker'+bytes(30)),
                              (0x380+4, (0x201).to_bytes(4, 'big'))):
            with self.subTest(offset=offset):
                self.assert_refused(changed_bytes(blob, offset, value))

    def test_survivor_overlap_alignment_target_geometry_and_checksum_refuse(self):
        blob, target = ordinary_nested_bmp()
        parsed = parse_backup_blob(blob)
        for offset, value in ((0x104, parsed.record_at(0x1c0).field_04_be32.to_bytes(4, 'big')),
                              (0x104, (1).to_bytes(4, 'big')),
                              (target+4, (len(blob)).to_bytes(4, 'big'))):
            with self.subTest(offset=offset, value=value):
                self.assert_refused(changed_bytes(blob, offset, value))
        self.assert_refused(changed_bytes(blob, len(blob)-1, bytes([blob[-1]^1]), checksum=False))

    def test_target_references_active_marks_and_unknown_protected_state_refuse(self):
        blob, target = ordinary_nested_bmp()
        for command in range(0x1b, 0x20):
            fixed = {c: bytes(64) for c in range(0x1b, 0x20)}
            raw = bytearray(64)
            if command == 0x1f:
                raw[:4] = (target-64).to_bytes(4, 'big')
                raw[8:12] = (0x80000000).to_bytes(4, 'big')
            else:
                raw[:4] = (1).to_bytes(4, 'big')
                raw[8:12] = (target-64).to_bytes(4, 'big')
            fixed[command] = bytes(raw)
            with self.subTest(command=command):
                self.assert_refused(blob, fixed=fixed)
        fixed = {c: bytes(64) for c in range(0x1b, 0x20)}
        marks = bytearray(64)
        marks[:4] = (1).to_bytes(4, 'big')
        marks[8:12] = (0x100-64).to_bytes(4, 'big')
        fixed[0x1c] = bytes(marks)  # Active Marks refuse even on an unrelated survivor.
        self.assert_refused(blob, fixed=fixed)
        fixed = {c: bytes(64) for c in range(0x1b, 0x20)}
        fixed[0x1b] = b'X'+bytes(63)
        self.assert_refused(blob, fixed=fixed)

    def test_survivor_references_rebase_and_opaque_tails_preserve(self):
        blob, target = ordinary_nested_bmp(first=True)
        fixed = {c: bytes(64) for c in range(0x1b, 0x20)}
        history = bytearray(64)
        history[:4] = (1).to_bytes(4, 'big')
        history[8:12] = (0x100-64).to_bytes(4, 'big')
        history[-1] = 0xa5
        grouped = bytearray(64)
        grouped[:20] = b''.join(v.to_bytes(4, 'big') for v in (0x340-64, 1, 2, 3, 4))
        grouped[-1] = 0x5a
        fixed[0x1b], fixed[0x1f] = bytes(history), bytes(grouped)
        data = self.data(blob=blob, offset=target, fixed=fixed)
        prepared = self.prepare(data)
        after_state = prepared.bundle.candidate.core.fixed_state.after
        self.assertEqual(after_state[0], bytes(history))
        expected = bytearray(grouped)
        expected[:4] = (0x340-128).to_bytes(4, 'big')
        self.assertEqual(after_state[4], bytes(expected))
        result = data[3].execute_once(prepared, confirmed=True)
        self.assertEqual(result.completion, 0)

    def test_independent_verifier_preserves_all_survivor_raw_fields_payloads_timestamps(self):
        data = self.data()
        core = build_nested_bmp_delete(data[2].backup_directory, data[2].row.display_name,
                                       target_record_offset=0x340)
        before, after = core.baseline, parse_backup_blob(core.candidate_blob)
        with patch('infocarry.delete_model.delete_existing_file', side_effect=AssertionError('repacker called')):
            verify_nested_file_delete_model(before, core.candidate_blob, core.target_path, core.target_record_offset)
        for record in before.records:
            if record.offset == core.target_record_offset:
                continue
            survivor = after.record_at(record.offset - (64 if record.offset > core.target_record_offset else 0))
            self.assertEqual(record.timestamp_be32, survivor.timestamp_be32)
            old_raw, new_raw = bytes.fromhex(record.raw_hex), bytes.fromhex(survivor.raw_hex)
            self.assertEqual(old_raw[:4], new_raw[:4])
            self.assertEqual(old_raw[12:], new_raw[12:])
            if record.kind == 'file':
                self.assertEqual(old_raw[8:12], new_raw[8:12])
                self.assertEqual(before.payload_parts(record), after.payload_parts(survivor))
        for offset in (0x100+12, 0x280+8, after.header.content_start+16):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                poisoned = changed_bytes(core.candidate_blob, offset, bytes([core.candidate_blob[offset]^1]))
                verify_nested_file_delete_model(before, poisoned, core.target_path, core.target_record_offset)

    def test_frozen_scope_path_offset_source_and_identity_tampering_refuse(self):
        data = self.data()
        prepared = self.prepare(data)
        bundle = prepared.bundle
        for candidate in (replace(bundle.candidate, general_nested_bmp=False),
                          replace(bundle.candidate, general_nested_bmp=1),
                          replace(bundle.candidate, nested_validation=True),
                          replace(bundle.candidate, general_bmp=True),
                          replace(bundle.candidate, target_path='root\\other.bmp'),
                          replace(bundle.candidate, target_record_offset=0x300),
                          replace(bundle.candidate, candidate_blob=b'wrong')):
            with self.subTest(candidate=candidate.target_path), self.assertRaises(Exception):
                replace(bundle, candidate=candidate).verify_seal()
        bundle.source_path.write_bytes(b'changed')
        with self.assertRaises(Exception):
            bundle.verify_seal()
        self.assertEqual(data[0][3].calls, [])
        self.assertIsNone(data[0][5].read_claim(bundle.seal_sha256))

    def test_equivalent_reconnect_and_changed_fresh_state(self):
        data = self.data(reconnect=True)
        prepared = self.prepare(data)
        data[0][2]['session'] = 'equivalent-new-session'
        self.assertEqual(data[3].execute_once(prepared, confirmed=True).completion, 0)
        data = self.data()
        prepared = self.prepare(data)
        data[0][2]['blob'] = rename_existing_record(parse_backup_blob(data[0][2]['blob']), 0x300, 'changed')
        with self.assertRaises(Exception):
            data[3].execute_once(prepared, confirmed=True)
        self.assertEqual(data[0][3].calls, [])
        self.assertIsNone(data[0][5].read_claim(prepared.bundle.seal_sha256))

    def test_cancel_before_sender_has_no_claim_or_marker(self):
        data = self.data()
        prepared = self.prepare(data)
        self.assertIsNone(data[3].execute_once(prepared, confirmed=False))
        self.assertEqual(data[0][3].calls, [])
        self.assertIsNone(data[0][5].read_claim(prepared.bundle.seal_sha256))
        self.assertIsNone(data[0][5].read_sender_in_flight())
        data = self.data()
        with self.assertRaises(TransferCancelledError):
            data[3].prepare(data[2], cancelled=lambda: True)
        self.assertEqual(data[0][3].calls, [])

    def test_actual_ttk_one_confirmation_cancel_complete_refresh_and_failure(self):
        for confirmed in (False, True):
            data = self.data()
            helper = ui_helpers.DeviceLibraryDeleteUITests()
            self.addCleanup(helper.doCleanups)
            ui = helper.setup_ui(confirmed=confirmed, data_override=data)
            ui.action(); ui.drain()
            self.assertEqual(len(ui.dialogs), 1)
            self.assertIn(data[2].row.display_name, ui.dialogs[0])
            self.assertEqual(len(ui.refreshes), int(confirmed))
            self.assertIn('Delete complete' if confirmed else 'cancelled', ui.statuses.get())
            self.assertEqual(sum(c[0] == 'control_out' for c in data[0][3].calls), int(confirmed))
        data = self.data(backend_options={'fail_bulk_at': 1})
        helper = ui_helpers.DeviceLibraryDeleteUITests()
        self.addCleanup(helper.doCleanups)
        ui = helper.setup_ui(data_override=data)
        ui.action(); ui.drain()
        self.assertEqual(len(ui.dialogs), 1)
        self.assertEqual(ui.refreshes, [])
        self.assertIn('uncertain', ui.statuses.get())

    def test_indeterminate_nonzero_failed_readback_one_sender_no_retry(self):
        for options in ({'fail_bulk_at': 1}, {'completion': (2,)}, {}):
            with self.subTest(options=options):
                data = self.data(backend_options=options)
                prepared = self.prepare(data)
                if not options:
                    data[0][2]['after_bad'] = True
                with self.assertRaises(Exception):
                    data[3].execute_once(prepared, confirmed=True)
                self.assertEqual(sum(c[0] == 'control_out' for c in data[0][3].calls), 1)
                self.assertIsNotNone(data[0][5].read_claim(prepared.bundle.seal_sha256))
                if 'completion' not in options:
                    self.assertIsNotNone(data[0][5].read_sender_in_flight())
                    self.assertTrue(data[0][6].read().locked)

    def test_exact_validation_mode_and_wrong_identity_cannot_adopt_ordinary_selection(self):
        data = self.data()
        restoration = dict(verify_fresh_backup(data[2].backup_directory,
                                               max_age_seconds=None).object_sha256_by_key)
        service = DeviceLibraryDeleteService(lambda: data[0][4].runtime,
                                              validation_target=NESTED_BMP_DELETE_VALIDATION_PATH,
                                              restoration_objects=restoration)
        self.assertFalse(service.execution_available(data[2]))
        with self.assertRaises(ValueError):
            service.prepare(data[2])
        self.assertEqual(data[0][3].calls, [])
        manifest = data[2].backup_directory/'manifest.json'
        raw = json.loads(manifest.read_bytes())
        raw['device']['product_id'] = '0xdead'
        manifest.write_text(json.dumps(raw))
        self.assertFalse(data[3].execution_available(data[2]))
        with self.assertRaises((ValueError, RuntimeError)):
            build_nested_bmp_delete(data[2].backup_directory, data[2].row.display_name)


if __name__ == '__main__':
    unittest.main()
