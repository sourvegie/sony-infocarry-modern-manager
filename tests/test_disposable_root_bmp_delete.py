"""Exact BMP host preparation, tamper refusal and retained live boundaries."""
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from infocarry.backup_format import parse_backup_blob
from infocarry.backup_repack import rename_existing_record
from infocarry.delete_generalized import (
    GeneralizedDeleteError, GeneralizedDeleteSenderBinding,
    GeneralizedDeleteVerificationError, bind_generalized_delete_sender,
)
from infocarry.delete_workflow import (
    ROOT_BMP_DELETE_FIXTURE_BYTES, ROOT_BMP_DELETE_FIXTURE_FILENAME,
    ROOT_BMP_DELETE_FIXTURE_PATH, ROOT_BMP_DELETE_FIXTURE_SHA256,
    build_disposable_root_bmp_delete, prepare_disposable_root_bmp_delete,
    require_external_bmp_output,
)
from infocarry.desktop import DesktopWorkflowModel
from infocarry.device_library_delete_execution import DeviceLibraryDeleteService
from infocarry.prepared_media_package import validate_bmp_payload
from infocarry.write_gate import WriteGateError
try:
    from test_root_bmp_delete_model import root_bitmap_library, _checksum
    from test_new_txt import _write_archive
except ModuleNotFoundError:
    from tests.test_root_bmp_delete_model import root_bitmap_library, _checksum
    from tests.test_new_txt import _write_archive


class DisposableRootBmpDeleteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.now = datetime.now(timezone.utc).replace(microsecond=0)
        self.sequence = 0

    def archive(self, blob, *, fixed=None):
        self.sequence += 1
        return _write_archive(self.root / f"backup-{self.sequence}", blob, self.now,
            fixed_state=fixed if fixed is not None else {c: bytes(64) for c in range(0x1b, 0x20)})

    def specimen(self, *, index=1, **kwargs):
        blob, offset = root_bitmap_library(index=index, payload=ROOT_BMP_DELETE_FIXTURE_BYTES, **kwargs)
        return rename_existing_record(parse_backup_blob(blob), offset,
            Path(ROOT_BMP_DELETE_FIXTURE_FILENAME).stem), offset

    def prepare(self, **kwargs):
        blob, _ = self.specimen(**kwargs)
        return prepare_disposable_root_bmp_delete(self.archive(blob), self.root / "prepared")

    def post(self, prepared, *, blob=None, fixed=None):
        core = prepared.verify()
        return self.archive(core.candidate_blob if blob is None else blob,
            fixed=dict(zip(range(0x1b, 0x20), core.fixed_state.after)) if fixed is None else fixed)

    def test_fixture_is_exact_supported_bitmap(self):
        details = validate_bmp_payload(ROOT_BMP_DELETE_FIXTURE_BYTES)
        self.assertEqual((details['width'], details['height'], details['bits_per_pixel']), (237, 320, 1))
        self.assertEqual(len(ROOT_BMP_DELETE_FIXTURE_BYTES), 10302)
        self.assertEqual(hashlib.sha256(ROOT_BMP_DELETE_FIXTURE_BYTES).hexdigest(), ROOT_BMP_DELETE_FIXTURE_SHA256)
        manifest = json.loads((Path(__file__).resolve().parents[1] / 'analysis' /
            'p18-046-disposable-root-bmp-fixture-20261016.json').read_bytes())
        self.assertEqual(manifest['path'], ROOT_BMP_DELETE_FIXTURE_PATH)
        self.assertEqual(manifest['bytes'], len(ROOT_BMP_DELETE_FIXTURE_BYTES))
        self.assertEqual(manifest['sha256'], ROOT_BMP_DELETE_FIXTURE_SHA256)
        self.assertFalse(manifest['physical_operations_authorized'])
        self.assertFalse(manifest['live_adapter_available'])
        self.assertEqual(ROOT_BMP_DELETE_FIXTURE_BYTES[58:62], b'\xff\xff\xff\0')
        self.assertGreater(len(set(ROOT_BMP_DELETE_FIXTURE_BYTES[62:])), 2)

    def test_first_middle_last_exact_transaction_and_readback(self):
        for index in range(3):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                blob, offset = self.specimen(index=index)
                before = self.archive(blob)
                snapshot = {p.name: p.read_bytes() for p in before.iterdir()}
                prepared = prepare_disposable_root_bmp_delete(before, Path(directory) / 'prepared')
                core = prepared.verify()
                self.assertEqual(core.target_path, ROOT_BMP_DELETE_FIXTURE_PATH)
                self.assertEqual(core.target_record_offset, offset)
                self.assertEqual(len(core.transaction.ranges), 8)
                self.assertEqual(core.transaction.ranges[4] + core.transaction.ranges[7], core.candidate_blob)
                self.assertEqual(len(blob) - len(core.candidate_blob), 64 + 16 + 10302 + 2)
                result = prepared.verify_readback(self.post(prepared), completion=0)
                self.assertTrue(result.target_removed and result.unrelated_payloads_unchanged)
                self.assertTrue(result.unrelated_objects_unchanged)
                self.assertEqual(snapshot, {p.name: p.read_bytes() for p in before.iterdir()})

    def test_no_runtime_or_production_safety_access_and_all_live_seams_closed(self):
        with patch('infocarry.write_safety_boundary.create_default_application_write_safety_owner',
                   side_effect=AssertionError('production safety access')), patch(
                   'infocarry.library_transfer_runtime_provider.ProductionLibraryTransferRuntimeProvider.for_current_application',
                   side_effect=AssertionError('production runtime access')):
            prepared = self.prepare()
            core = prepared.verify()
            self.assertFalse(prepared.execution_available)
            self.assertFalse(hasattr(prepared, 'runtime'))
            report = json.loads(prepared.report_json)
            self.assertFalse(report['physical_operation_authorized'])
            self.assertFalse(report['owner_approval_identity_created'])
            self.assertEqual(report['host_binding']['state'], 'authorized_for_host_review_only')
            for binding in (prepared.authorization, replace(prepared.authorization, target_extension='txt')):
                with self.assertRaisesRegex(GeneralizedDeleteError, 'host-only'):
                    GeneralizedDeleteSenderBinding(binding, core)
                with self.assertRaisesRegex(GeneralizedDeleteError, 'host-only'):
                    bind_generalized_delete_sender(binding, core)
            model = DesktopWorkflowModel(); model.load_backup(core.backup.directory)
            service = DeviceLibraryDeleteService(lambda: self.fail('BMP opened a runtime'))
            selection = service.select(model, [core.target_record_offset])
            self.assertTrue(selection.general_bmp)
            self.assertTrue(service.execution_available(selection))
            # The standalone host preparation still grants no sender/runtime;
            # ordinary UI admission requires a newly frozen guarded operation.

    def test_absent_wrong_name_read_state_and_prefix_refuse_before_output(self):
        for mode in ('absent', 'wrong_name', 'read', 'prefix32'):
            blob, offset = self.specimen(flag=0x20 if mode == 'read' else 0xe0,
                                         prefix_bytes=32 if mode == 'prefix32' else 16)
            if mode in ('absent', 'wrong_name'):
                blob = rename_existing_record(parse_backup_blob(blob), offset, 'other')
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                prepare_disposable_root_bmp_delete(self.archive(blob), self.root / mode)
            self.assertFalse((self.root / mode).exists())

    def test_changed_payload_refuses(self):
        blob, offset = self.specimen()
        parsed = parse_backup_blob(blob); target = parsed.record_at(offset)
        changed = bytearray(blob)
        changed[parsed.header.content_start + target.field_04_be32 + 16 + 70] ^= 1
        with self.assertRaisesRegex(ValueError, 'payload'):
            build_disposable_root_bmp_delete(self.archive(_checksum(changed)))

    def test_v10_identity_refuses(self):
        blob, _ = self.specimen(); archive = self.archive(blob)
        manifest = json.loads((archive / 'manifest.json').read_text())
        manifest['device']['product_id'] = '0x001d'
        (archive / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises((ValueError, WriteGateError)):
            build_disposable_root_bmp_delete(archive)

    def test_target_reference_active_marks_and_ambiguous_identity_refuse(self):
        blob, offset = self.specimen()
        for mode in ('history', 'mark', 'bookmark', 'ambiguous'):
            fixed = {c: bytes(64) for c in range(0x1b, 0x20)}
            changed = blob
            if mode == 'ambiguous':
                changed = rename_existing_record(parse_backup_blob(blob), 0xc0,
                    Path(ROOT_BMP_DELETE_FIXTURE_FILENAME).stem.lower())
            else:
                raw = bytearray(64)
                if mode in ('history', 'mark'):
                    raw[:4] = (1).to_bytes(4, 'big'); raw[8:12] = (offset - 64).to_bytes(4, 'big')
                    fixed[0x1b if mode == 'history' else 0x1c] = bytes(raw)
                else:
                    raw[:4] = (offset - 64).to_bytes(4, 'big')
                    raw[8:12] = (0x80000000).to_bytes(4, 'big'); fixed[0x1f] = bytes(raw)
            with self.subTest(mode=mode), self.assertRaises(GeneralizedDeleteError):
                prepare_disposable_root_bmp_delete(self.archive(changed, fixed=fixed), self.root / mode)

    def test_every_persisted_artifact_and_report_tamper_refuses(self):
        prepared = self.prepare()
        paths = [prepared.directory / name for name in (ROOT_BMP_DELETE_FIXTURE_FILENAME,
            'candidate.bin', 'candidate-audit.json', 'host-binding.json', 'preparation.json')]
        paths += [p for p in (prepared.directory / 'transaction').iterdir() if p.is_file()]
        for path in paths:
            original = path.read_bytes()
            path.write_bytes(original + b'X')
            with self.subTest(path=path.name), self.assertRaises((ValueError, RuntimeError)):
                prepared.verify()
            path.write_bytes(original)
        prepared.verify()

    def test_rebound_host_binding_report_and_source_backup_refuse(self):
        prepared = self.prepare()
        with self.assertRaises(ValueError):
            replace(prepared, authorization=replace(prepared.authorization, target_extension='txt')).verify()
        with self.assertRaises(ValueError):
            replace(prepared, report_json=b'{}').verify()
        core = prepared.verify()
        obj = core.backup.directory / core.backup.object_filename('0x8004:backup-blob')
        obj.write_bytes(obj.read_bytes() + b'X')
        with self.assertRaises((ValueError, RuntimeError)):
            prepared.verify()

    def test_post_readback_refuses_ambiguous_completion_wrong_state_and_survivor_changes(self):
        prepared = self.prepare()
        for completion in (None, True, '0', 1):
            with self.subTest(completion=completion), self.assertRaises(GeneralizedDeleteVerificationError):
                prepared.verify_readback(self.root / 'absent', completion=completion)
        core = prepared.verify()
        for blob in (core.baseline.data, rename_existing_record(parse_backup_blob(core.candidate_blob), 0xc0, 'changed')):
            with self.assertRaises(GeneralizedDeleteVerificationError):
                prepared.verify_readback(self.post(prepared, blob=blob), completion=0)
        fixed = dict(zip(range(0x1b, 0x20), core.fixed_state.after)); fixed[0x1d] = b'X' + bytes(63)
        with self.assertRaises(GeneralizedDeleteVerificationError):
            prepared.verify_readback(self.post(prepared, fixed=fixed), completion=0)

    def test_output_never_overwrites_or_modifies_source_or_git_checkout(self):
        prepared = self.prepare()
        backup = prepared.authorization.baseline.directory
        original = prepared.report_json
        for output in (prepared.directory, backup / 'new-output', Path(__file__).resolve().parents[1] / 'raw-bmp-test'):
            with self.subTest(output=output), self.assertRaises((ValueError, FileExistsError)):
                prepare_disposable_root_bmp_delete(backup, output)
        self.assertEqual((prepared.directory / 'preparation.json').read_bytes(), original)
        self.assertFalse((backup / 'new-output').exists())
        link = self.root / 'linked-checkout'; link.symlink_to(Path(__file__).resolve().parents[1], target_is_directory=True)
        with self.assertRaises(ValueError):
            require_external_bmp_output(link / 'raw-bmp-test')

    def launcher(self):
        spec = importlib.util.spec_from_file_location('prepare_root_bmp_delete',
            Path(__file__).resolve().parents[1] / 'scripts' / 'prepare_root_bmp_delete.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def test_cli_fixture_prepare_and_optional_offline_readback(self):
        launcher = self.launcher()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(launcher.main(['fixture', '--output', str(self.root / 'fixture')]), 0)
        self.assertEqual((self.root / 'fixture' / ROOT_BMP_DELETE_FIXTURE_FILENAME).read_bytes(), ROOT_BMP_DELETE_FIXTURE_BYTES)
        prepared = self.prepare(); post = self.post(prepared)
        with redirect_stdout(io.StringIO()) as captured:
            self.assertEqual(launcher.main(['prepare', '--backup', str(prepared.authorization.baseline.directory),
                '--output', str(self.root / 'cli-prepare'), '--post-backup', str(post), '--completion', '0x0000']), 0)
        result = json.loads(captured.getvalue())
        self.assertTrue(result['offline_readback_verified'])
        self.assertEqual(result['usb_operations'], 0)

    def test_cli_has_no_write_option_or_implicit_completion(self):
        launcher = self.launcher()
        for args in (['fixture', '--output', str(self.root / 'rejected'), '--allow-write'],
                     ['prepare', '--backup', 'missing', '--output', str(self.root / 'rejected'), '--post-backup', 'missing']):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                launcher.main(args)
            self.assertFalse((self.root / 'rejected').exists())


if __name__ == '__main__':
    unittest.main()
