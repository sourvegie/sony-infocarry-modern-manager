from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from infocarry.app_paths import application_paths
from infocarry.backup import BackupObjectSpec, RawBackupArchive
from infocarry.backup_history import (
    BackupHistoryError,
    latest_complete_backup,
    remember_complete_backup,
    summarize_complete_backup,
)
from infocarry.backup_format import calculate_backup_checksum


def make_text_blob(payload: bytes) -> bytes:
    def record(flag: int, extension: str, field04: int, field08: int, name: str, field14: int = 0) -> bytes:
        raw = bytearray(64)
        raw[0] = flag
        raw[1:4] = extension.encode("ascii").ljust(3, b"\x00")
        raw[4:8] = field04.to_bytes(4, "big")
        raw[8:12] = field08.to_bytes(4, "big")
        raw[12:16] = (1_787_207_892).to_bytes(4, "big")
        raw[16:20] = (0xFFFFFFFF).to_bytes(4, "big")
        raw[20:24] = field14.to_bytes(4, "big")
        encoded = name.encode("cp932")
        raw[24 : 24 + len(encoded)] = encoded
        return bytes(raw)

    metadata = (
        record(0xD0, "", 0x40, 0x80, "root")
        + record(0xD0, "", 0x40, 0x80, "..")
        + record(0xE0, "txt", 0, len(payload), "memo", 0x200)
    )
    content_start = 0x40 + len(metadata)
    content = b"\xff" * 32 + payload
    content += b"\x00" * (-(content_start + len(content)) % 4)
    total_length = content_start + len(content) + 4
    header = bytearray(64)
    header[:14] = b"infoCarry 2.00"
    header[14:16] = b"\x01\x00"
    header[16:18] = (64).to_bytes(2, "big")
    header[0x14:0x18] = (0x20).to_bytes(4, "big")
    header[0x18:0x1C] = (total_length - 1).to_bytes(4, "big")
    header[0x28:0x2C] = (0x40).to_bytes(4, "big")
    header[0x2C:0x30] = len(metadata).to_bytes(4, "big")
    header[0x30:0x34] = content_start.to_bytes(4, "big")
    header[0x34:0x38] = len(content).to_bytes(4, "big")
    header[0x38:0x3C] = total_length.to_bytes(4, "big")
    header[0x3C:0x40] = b"\xff" * 4
    blob = bytearray(bytes(header) + metadata + content + b"\xff" * 4)
    blob[0x1C:0x20] = calculate_backup_checksum(blob).to_bytes(4, "big")
    return bytes(blob)


def make_complete_backup(directory: Path) -> Path:
    archive = RawBackupArchive.create(directory)
    blob = make_text_blob("Snapshot 日本語\r\n".encode("cp932"))
    archive.save(BackupObjectSpec(0x8004, "backup-blob", len(blob)), blob)
    archive.finalize()
    return directory


class BackupHistoryTests(unittest.TestCase):
    def test_complete_app_backup_is_registered_and_revalidated(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = application_paths(home=Path(temporary), platform="darwin", os_name="posix")
            destination = paths.backup_root / "InfoCarry-backup-日本語"
            make_complete_backup(destination)

            stored = remember_complete_backup(paths, destination)
            loaded = latest_complete_backup(paths)

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded, stored)
            self.assertEqual(loaded, summarize_complete_backup(destination))
            self.assertEqual(
                loaded.model_bytes,
                len(make_text_blob("Snapshot 日本語\r\n".encode("cp932"))),
            )
            record = json.loads(paths.latest_backup_record.read_text(encoding="utf-8"))
            self.assertEqual(record["directory"], str(destination.resolve()))
            self.assertEqual(record["blob_sha256"], loaded.blob_sha256)

    def test_external_backup_can_be_summarized_but_not_registered(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "home"
            paths = application_paths(home=home, platform="darwin", os_name="posix")
            outside = Path(temporary) / "External Backup"
            make_complete_backup(outside)

            self.assertEqual(summarize_complete_backup(outside).directory, outside.resolve())
            with self.assertRaises(BackupHistoryError):
                remember_complete_backup(paths, outside)

    def test_latest_backup_pointer_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            paths = application_paths(home=Path(temporary), platform="darwin", os_name="posix")
            destination = paths.backup_root / "backup"
            make_complete_backup(destination)
            remember_complete_backup(paths, destination)

            record = json.loads(paths.latest_backup_record.read_text(encoding="utf-8"))
            record["model_bytes"] += 1
            paths.latest_backup_record.write_text(json.dumps(record), encoding="utf-8")

            with self.assertRaisesRegex(BackupHistoryError, "does not match"):
                latest_complete_backup(paths)


if __name__ == "__main__":
    unittest.main()
