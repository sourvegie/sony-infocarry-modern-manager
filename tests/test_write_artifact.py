import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from infocarry.write_artifact import (
    ProspectiveWriteTransaction,
    WriteArtifactError,
    build_staging_range,
    load_preserved_artifact,
)


def candidate_transaction() -> ProspectiveWriteTransaction:
    range_4 = b"generated"
    tail = (b"h" * 0x40, b"a" * 2, b"b" * 3, b"c" * 5)
    variable_m = sum(len(part) for part in tail)
    range_3 = build_staging_range(len(range_4), variable_m)
    return ProspectiveWriteTransaction(
        ranges=(b"s" * 0x100, b"t" * 0x40, range_3, range_4) + tail,
        variable_n=len(range_4),
        variable_m=variable_m,
    )


class ProspectiveWriteTransactionTests(unittest.TestCase):
    def test_builds_verified_staging_range_without_usb(self):
        result = build_staging_range(7, 0x123456)
        self.assertEqual(len(result), 0xFEC0)
        self.assertEqual(result[:8], b"\x00\x00\x00\x07\x00\x12\x34\x56")
        self.assertEqual(result[8:], b"\xff" * (0xFEC0 - 8))
        with self.assertRaises(WriteArtifactError):
            build_staging_range(-1, 0)
        with self.assertRaises(WriteArtifactError):
            build_staging_range(0, 0x100000000)

    def test_validates_header_lengths_and_hashes_without_usb(self):
        transaction = candidate_transaction()
        expected_payload = b"".join(transaction.ranges)

        self.assertEqual(transaction.payload_length, len(expected_payload))
        self.assertEqual(transaction.command_header[:2], b"\x1b\x10")
        self.assertEqual(
            int.from_bytes(transaction.command_header[2:], "little"),
            len(expected_payload),
        )
        self.assertEqual(
            transaction.concatenated_sha256,
            hashlib.sha256(expected_payload).hexdigest(),
        )

    def test_rejects_inconsistent_range_or_staging_metadata(self):
        valid = candidate_transaction()
        with self.assertRaises(WriteArtifactError):
            ProspectiveWriteTransaction(valid.ranges[:7], valid.variable_n, valid.variable_m)

        wrong_staging = list(valid.ranges)
        wrong_staging[2] = b"\x00" * 8 + wrong_staging[2][8:]
        with self.assertRaises(WriteArtifactError):
            ProspectiveWriteTransaction(
                tuple(wrong_staging), valid.variable_n, valid.variable_m
            )

        wrong_fill = list(valid.ranges)
        wrong_fill[2] = wrong_fill[2][:-1] + b"\x00"
        with self.assertRaises(WriteArtifactError):
            ProspectiveWriteTransaction(
                tuple(wrong_fill), valid.variable_n, valid.variable_m
            )

        with self.assertRaises(WriteArtifactError):
            ProspectiveWriteTransaction(
                valid.ranges, valid.variable_n, valid.variable_m + 1
            )

    def test_preserves_new_artifact_and_refuses_overwrite(self):
        transaction = candidate_transaction()
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "prospective"
            transaction.preserve(destination, "synthetic unit-test fixture")

            manifest = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(manifest["state"], "offline_only")
            self.assertFalse(manifest["usb_transmission_performed"])
            self.assertEqual(manifest["command"], "0x101b")
            self.assertEqual(len(manifest["ranges"]), 8)
            for entry, expected in zip(manifest["ranges"], transaction.ranges):
                self.assertEqual((destination / entry["filename"]).read_bytes(), expected)

            with self.assertRaises(WriteArtifactError):
                transaction.preserve(destination, "second attempt")

    def test_loads_and_reverifies_preserved_artifact(self):
        transaction = candidate_transaction()
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "prospective"
            transaction.preserve(destination, "synthetic unit-test fixture")
            loaded = load_preserved_artifact(destination)
            self.assertEqual(loaded.ranges, transaction.ranges)
            range_path = destination / "range-08.bin"
            range_path.write_bytes(range_path.read_bytes() + b"tamper")
            with self.assertRaises(WriteArtifactError):
                load_preserved_artifact(destination)


if __name__ == "__main__":
    unittest.main()
