import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from infocarry.backup import (
    BackupClient,
    BackupObjectSpec,
    BackupProbeError,
    FixedResponseError,
    FIXED_BACKUP_OBJECTS,
    MAX_BACKUP_BLOB_LENGTH,
    RawBackupArchive,
    parse_backup_blob_length,
    parse_grouped_values_response,
    parse_offset_list_response,
)
from infocarry.capture import CaptureError
from infocarry.protocol import (
    ProtocolError,
    TransferCancelledError,
    TransferLengthError,
    TransferTimeoutError,
)


def make_probe(first_length=5, second_length=7, direct_length=0xFFFFFFFF):
    probe = bytearray(64)
    probe[0x30:0x34] = first_length.to_bytes(4, "big")
    probe[0x34:0x38] = second_length.to_bytes(4, "big")
    probe[0x38:0x3C] = direct_length.to_bytes(4, "big")
    return bytes(probe)


class FakeBackupBackend:
    def __init__(self, payloads, *, fail_header_index=None, failure=None):
        self.payloads = list(payloads)
        self.active = b""
        self.headers = []
        self.bulk_requests = []
        self.fail_header_index = fail_header_index
        self.failure = failure

    def control_out(self, request_type, request, value, index, data, timeout_ms):
        self.headers.append(bytes(data))
        if len(self.headers) == self.fail_header_index:
            raise self.failure
        self.active = self.payloads.pop(0)
        return len(data)

    def control_in(self, request_type, request, value, index, length, timeout_ms):
        return b"\x00\x00"

    def bulk_read(self, endpoint, length, timeout_ms):
        self.bulk_requests.append(length)
        chunk, self.active = self.active[:length], self.active[length:]
        return chunk


class BackupTests(unittest.TestCase):
    def make_client(self, payloads):
        backend = FakeBackupBackend(payloads)
        session = SimpleNamespace(
            backend=backend,
            endpoints=SimpleNamespace(bulk_in=0x82),
        )
        return BackupClient(session), backend

    def test_probe_length_matches_legacy_formula(self):
        self.assertEqual(parse_backup_blob_length(make_probe(5, 7)), 16)
        self.assertEqual(parse_backup_blob_length(make_probe(0, 0)), 4)
        self.assertEqual(
            parse_backup_blob_length(make_probe(direct_length=2_050_100)),
            2_050_100,
        )

    def test_probe_rejects_wrong_size_and_unsafe_length(self):
        with self.assertRaises(TransferLengthError):
            parse_backup_blob_length(b"short")
        with self.assertRaises(BackupProbeError):
            parse_backup_blob_length(make_probe(direct_length=0))
        with self.assertRaises(BackupProbeError):
            parse_backup_blob_length(
                make_probe(direct_length=MAX_BACKUP_BLOB_LENGTH + 1)
            )

    def test_fixed_offset_list_response_layout_and_bound(self):
        data = bytearray(64)
        data[0:4] = (3).to_bytes(4, "big")
        data[4:6] = (0x1234).to_bytes(2, "big")
        data[6:8] = (0x5678).to_bytes(2, "big")
        for index, value in enumerate((0x5840, 0x5800, 0x57C0)):
            start = 8 + index * 4
            data[start : start + 4] = value.to_bytes(4, "big")
        parsed = parse_offset_list_response(bytes(data))
        self.assertEqual(parsed.count, 3)
        self.assertEqual(parsed.value_04_be16, 0x1234)
        self.assertEqual(parsed.value_06_be16, 0x5678)
        self.assertEqual(parsed.record_offsets, (0x5840, 0x5800, 0x57C0))
        self.assertEqual(len(bytes.fromhex(parsed.unused_tail_hex)), 44)

        # A live mark-state capture returned count zero with a stale record
        # offset in the first unused slot. It must not become a list entry.
        data[0:4] = (0).to_bytes(4, "big")
        data[8:12] = (0x01C0).to_bytes(4, "big")
        parsed = parse_offset_list_response(bytes(data))
        self.assertEqual(parsed.record_offsets, ())
        self.assertTrue(parsed.unused_tail_hex.startswith("000001c0"))

        data[0:4] = (14).to_bytes(4, "big")
        with self.assertRaises(FixedResponseError):
            parse_offset_list_response(bytes(data))
        with self.assertRaises(TransferLengthError):
            parse_offset_list_response(b"short")

    def test_command_001f_grouped_values_layout(self):
        values = tuple(range(1, 11))
        data = b"".join(value.to_bytes(4, "big") for value in values) + b"\xaa" * 24
        parsed = parse_grouped_values_response(data)
        self.assertEqual(parsed.groups, (values[:5], values[5:]))
        self.assertEqual(parsed.unused_tail_hex, "aa" * 24)

    def test_full_backup_order_lengths_files_and_manifest(self):
        fixed_payloads = [bytes([index]) * 64 for index in range(1, 7)]
        probe = make_probe(5, 7)
        blob = bytes(range(16))
        client, backend = self.make_client(fixed_payloads + [probe, blob])
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "backup"
            archive = RawBackupArchive.create(destination)
            objects = client.backup(archive)

            expected_commands = [spec.command for spec in FIXED_BACKUP_OBJECTS] + [
                0x8004,
                0x8004,
            ]
            actual_commands = [int.from_bytes(header[:2], "little") for header in backend.headers]
            actual_lengths = [int.from_bytes(header[2:], "little") for header in backend.headers]
            self.assertEqual(actual_commands, expected_commands)
            self.assertEqual(actual_lengths, [64] * 7 + [16])
            self.assertEqual(len(objects), 8)
            self.assertEqual((destination / objects[6]["filename"]).read_bytes(), probe)
            self.assertEqual((destination / objects[7]["filename"]).read_bytes(), blob)
            self.assertNotEqual(objects[6]["filename"], objects[7]["filename"])
            self.assertEqual(objects[7]["sha256"], hashlib.sha256(blob).hexdigest())

            manifest = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(manifest["state"], "complete")
            self.assertEqual(manifest["format"], "infocarry-raw-backup-v1")
            self.assertEqual(manifest["objects"], list(objects))

    def test_backup_reports_bounded_progress_and_verifies_archive(self):
        fixed_payloads = [bytes([index]) * 64 for index in range(1, 7)]
        client, unused_backend = self.make_client(
            fixed_payloads + [make_probe(5, 7), bytes(range(16))]
        )
        progress = []
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "backup"
            archive = RawBackupArchive.create(destination)
            client.backup(
                archive,
                progress=lambda label, completed, total: progress.append(
                    (label, completed, total)
                ),
            )
            self.assertEqual(progress[0], ("Reading response-0024", 0, 8))
            self.assertEqual(progress[-1], ("Backup verified", 8, 8))
            self.assertEqual(json.loads((destination / "manifest.json").read_text())["state"], "complete")

    def test_malformed_probe_is_preserved_before_backup_stops(self):
        fixed_payloads = [bytes([index]) * 64 for index in range(1, 7)]
        malformed = make_probe(direct_length=0)
        client, backend = self.make_client(fixed_payloads + [malformed])
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "backup"
            archive = RawBackupArchive.create(destination)
            with self.assertRaises(BackupProbeError):
                client.backup(archive)
            manifest = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(manifest["state"], "incomplete")
            self.assertEqual(len(manifest["objects"]), 7)
            probe_path = destination / manifest["objects"][-1]["filename"]
            self.assertEqual(probe_path.read_bytes(), malformed)
            self.assertEqual(len(backend.headers), 7)

    def test_cancellation_retains_completed_objects(self):
        payloads = [b"a" * 64, b"b" * 64]
        client, unused_backend = self.make_client(payloads)
        checks = iter((False, False, True))
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "backup"
            archive = RawBackupArchive.create(destination)
            with self.assertRaises(TransferCancelledError):
                client.backup(archive, cancelled=lambda: next(checks, True))
            manifest = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(manifest["state"], "incomplete")
            self.assertEqual(len(manifest["objects"]), 1)
            self.assertEqual(manifest["error"]["type"], "TransferCancelledError")

    def test_disconnect_and_timeout_retain_completed_objects(self):
        failures = (
            ProtocolError("simulated cable disconnect"),
            TransferTimeoutError("simulated finite timeout"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                backend = FakeBackupBackend(
                    [b"a" * 64], fail_header_index=2, failure=failure
                )
                session = SimpleNamespace(
                    backend=backend,
                    endpoints=SimpleNamespace(bulk_in=0x82),
                )
                client = BackupClient(session)
                with tempfile.TemporaryDirectory() as temporary:
                    destination = Path(temporary) / "backup"
                    archive = RawBackupArchive.create(destination)
                    with self.assertRaises(type(failure)):
                        client.backup(archive)
                    manifest = json.loads((destination / "manifest.json").read_text())
                    self.assertEqual(manifest["state"], "incomplete")
                    self.assertEqual(len(manifest["objects"]), 1)
                    object_path = destination / manifest["objects"][0]["filename"]
                    self.assertEqual(object_path.read_bytes(), b"a" * 64)

    def test_existing_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "existing"
            destination.mkdir()
            sentinel = destination / "keep.txt"
            sentinel.write_text("keep")
            with self.assertRaises(CaptureError):
                RawBackupArchive.create(destination)
            self.assertEqual(sentinel.read_text(), "keep")

    def test_disk_write_failure_leaves_last_durable_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "backup"
            archive = RawBackupArchive.create(destination)
            original_fsync = os.fsync
            calls = 0

            def fail_first_fsync(fd):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise OSError(28, "No space left on device")
                return original_fsync(fd)

            with patch("infocarry.backup.os.fsync", side_effect=fail_first_fsync):
                with self.assertRaises(CaptureError):
                    archive.save(BackupObjectSpec(0x24, "response-0024"), b"x" * 64)
            manifest = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(manifest["state"], "in_progress")
            self.assertEqual(manifest["objects"], [])


if __name__ == "__main__":
    unittest.main()
