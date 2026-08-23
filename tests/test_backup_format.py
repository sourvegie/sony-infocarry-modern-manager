import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import (
    BackupExporter,
    BackupFormatError,
    calculate_backup_checksum,
    decode_cp932_with_escapes,
    find_unmapped_cp932_sequences,
    load_complete_backup,
    parse_backup_blob,
    timestamp_utc_iso8601,
)
from infocarry.capture import CaptureError


def make_record(flag, extension, field04, field08, name, field14=0):
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


def make_text_blob(
    payload=b"hello\r\n", file_flag=0xE0, field14=0x200, extension="txt"
):
    root = make_record(0xD0, "", 0x40, 0x80, "root")
    parent = make_record(0xD0, "", 0x40, 0x80, "..")
    file_record = make_record(file_flag, extension, 0, len(payload), "memo", field14)
    metadata = root + parent + file_record
    prefix_length = ((field14 >> 8) & 0xFF) * 16
    content = b"\xff" * prefix_length + payload
    content_start = 0x40 + len(metadata)
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


class BackupFormatTests(unittest.TestCase):
    def test_parses_tree_and_extracts_exact_payload(self):
        payload = "日本語\r\n".encode("cp932")
        parsed = parse_backup_blob(make_text_blob(payload))
        self.assertEqual(parsed.header.record_size, 64)
        self.assertEqual(len(parsed.records), 3)
        self.assertEqual(parsed.paths[0x40], ("root",))
        self.assertEqual(parsed.paths[0xC0], ("root", "memo"))
        self.assertEqual(parsed.parent_record_offsets, (0x80,))
        self.assertEqual(parsed.record_at(0xC0).read_state, "unread")
        self.assertEqual(
            parse_backup_blob(make_text_blob(payload, file_flag=0x20))
            .record_at(0xC0)
            .read_state,
            "read",
        )
        self.assertIsNone(parsed.record_at(0x40).read_state)
        wrapper, extracted = parsed.payload_parts(parsed.record_at(0xC0))
        self.assertEqual(wrapper, b"\xff" * 32)
        self.assertEqual(extracted, payload)

    def test_accepts_high_state_bits_on_known_payload_prefix(self):
        payload = b"manager variant"
        parsed = parse_backup_blob(make_text_blob(payload, field14=0x10200))
        record = parsed.record_at(0xC0)
        self.assertEqual(record.field_14_be32, 0x10200)
        wrapper, extracted = parsed.payload_parts(record)
        self.assertEqual(len(wrapper), 0x20)
        self.assertEqual(extracted, payload)

    def test_rejects_bad_magic_lengths_and_directory_bounds(self):
        valid = bytearray(make_text_blob())
        cases = []
        bad_magic = bytearray(valid)
        bad_magic[0] = 0
        cases.append(bad_magic)
        bad_total = bytearray(valid)
        bad_total[0x38:0x3C] = (1).to_bytes(4, "big")
        cases.append(bad_total)
        bad_directory = bytearray(valid)
        bad_directory[0x44:0x48] = (0xFFFFFFC0).to_bytes(4, "big")
        cases.append(bad_directory)
        for data in cases:
            with self.subTest(data=data[:64].hex()):
                with self.assertRaises(BackupFormatError):
                    parse_backup_blob(bytes(data))

    def test_checksum_matches_and_detects_content_change(self):
        valid = make_text_blob()
        self.assertEqual(
            calculate_backup_checksum(valid), int.from_bytes(valid[0x1C:0x20], "big")
        )
        changed = bytearray(valid)
        changed[-5] ^= 1
        with self.assertRaises(BackupFormatError):
            parse_backup_blob(bytes(changed))

    def test_cp932_decoder_escapes_invalid_source_bytes(self):
        decoded, invalid = decode_cp932_with_escapes(b"A\x81#B")
        self.assertEqual(decoded, "A\\x81#B")
        self.assertEqual(invalid, (1,))
        self.assertEqual(
            find_unmapped_cp932_sequences(b"A\x81#B"),
            (
                {
                    "offset": 1,
                    "raw_hex": "8123",
                    "manual_meaning": "unread file icon",
                },
            ),
        )
        self.assertEqual(
            find_unmapped_cp932_sequences(b"\x82=\x81:\x81;"),
            (
                {
                    "offset": 0,
                    "raw_hex": "823d",
                    "manual_meaning": "delete previous character control",
                },
                {
                    "offset": 2,
                    "raw_hex": "813a",
                    "manual_meaning": "battery level 2 indicator, left component",
                },
                {
                    "offset": 4,
                    "raw_hex": "813b",
                    "manual_meaning": "battery level 2 indicator, right component",
                },
            ),
        )

    def test_timestamp_is_rendered_as_utc_unix_time(self):
        self.assertEqual(
            timestamp_utc_iso8601(1_787_207_892), "2026-08-20T06:38:12Z"
        )

    def test_export_is_exact_deterministic_and_non_overwriting(self):
        payload = b"A\x81#B"
        blob = make_text_blob(payload)
        parsed = parse_backup_blob(blob)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "export"
            manifest = BackupExporter(
                parsed, hashlib.sha256(blob).hexdigest()
            ).export(destination)
            file_entry = next(
                entry for entry in manifest["records"] if entry["kind"] == "file"
            )
            native = destination / file_entry["native_path"]
            decoded = destination / file_entry["decoded_text_path"]
            self.assertEqual(native.read_bytes(), payload)
            self.assertEqual(decoded.read_text(encoding="utf-8"), "A\\x81#B")
            self.assertEqual(file_entry["invalid_byte_offsets"], [1])
            self.assertEqual(file_entry["read_state"], "unread")
            self.assertEqual(
                file_entry["unmapped_cp932_sequences"],
                [
                    {
                        "offset": 1,
                        "raw_hex": "8123",
                        "manual_meaning": "unread file icon",
                    }
                ],
            )
            self.assertEqual(
                manifest["unmapped_cp932_sequence_catalog"],
                [
                    {
                        "raw_hex": "8123",
                        "occurrences": 1,
                        "manual_meaning": "unread file icon",
                    }
                ],
            )
            self.assertEqual(file_entry["timestamp_utc"], "2026-08-20T06:38:12Z")
            self.assertEqual(manifest["summary"]["files"], 1)
            self.assertEqual(
                manifest["summary"]["manual_mapped_private_sequence_types"], 1
            )
            self.assertEqual(
                manifest["summary"]["unresolved_private_sequence_types"], 0
            )
            with self.assertRaises(CaptureError):
                BackupExporter(parsed, "unused").export(destination)

    def test_complete_archive_loader_verifies_hash_and_state(self):
        blob = make_text_blob()
        digest = hashlib.sha256(blob).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "blob.bin").write_bytes(blob)
            manifest = {
                "format": "infocarry-raw-backup-v1",
                "state": "complete",
                "objects": [
                    {
                        "kind": "backup-blob",
                        "filename": "blob.bin",
                        "received_length": len(blob),
                        "sha256": digest,
                    }
                ],
            }
            (root / "manifest.json").write_text(json.dumps(manifest))
            parsed, loaded_digest = load_complete_backup(root)
            self.assertEqual(parsed.header.total_length, len(blob))
            self.assertEqual(loaded_digest, digest)

            manifest["state"] = "incomplete"
            (root / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(BackupFormatError):
                load_complete_backup(root)


if __name__ == "__main__":
    unittest.main()
