import struct
from pathlib import Path
import tempfile
import unittest

from infocarry.capture_artifact import CaptureArtifactError, preserve_capture_artifact
from infocarry.payload_builder import build_offline_payload
from infocarry.write_artifact import load_preserved_artifact


def _native_payload(payload: bytes) -> bytes:
    record = bytearray(0x1A)
    record[:4] = b"\x48\x00\x09\x00"
    struct.pack_into("<H", record, 0x14, len(payload))
    struct.pack_into("<H", record, 0x18, 1)
    record.extend(payload)
    completion = bytearray(0x1A)
    completion[:4] = b"\x48\x00\x09\x00"
    struct.pack_into("<H", completion, 0x14, 2)
    struct.pack_into("<H", completion, 0x18, len(payload))
    return bytes(record + completion)


def _capture_bytes():
    states = tuple(
        type("State", (), {
            "count": 1,
            "value_04_be16": index,
            "value_06_be16": index + 1,
            "record_offsets": (0x100 + index,),
        })()
        for index in range(4)
    )
    grouped = type("Grouped", (), {"groups": ((1, 2, 3, 4, 5), (6, 7, 8, 9, 10))})()
    transaction = build_offline_payload(
        states,
        grouped,
        range5_source=bytes(range(0x40)),
        range8=b"model-range",
    )
    payloads = [transaction.ranges[0], transaction.ranges[1]]
    range3 = transaction.ranges[2]
    payloads.extend(range3[offset : offset + 0x1000] for offset in range(0, len(range3), 0x1000))
    payloads.extend((transaction.ranges[4], transaction.ranges[7]))
    header = b"\x06\x00\x00\x00\x01\x00" + struct.pack(
        "<HI", 0x101B, transaction.payload_length
    )
    return header + b"".join(_native_payload(payload) for payload in payloads)


class CaptureArtifactTests(unittest.TestCase):
    def test_extracts_and_reverifies_one_offline_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capture = root / "capture.usblog"
            destination = root / "artifact"
            capture.write_bytes(_capture_bytes())
            artifact = preserve_capture_artifact(capture, destination)
            loaded = load_preserved_artifact(artifact)
            self.assertEqual(loaded.ranges[7], b"model-range")
            self.assertEqual(loaded.payload_length, 0x10000 + 0x40 + len(b"model-range"))

    def test_rejects_missing_transaction_without_writing_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capture = root / "capture.usblog"
            destination = root / "artifact"
            capture.write_bytes(_capture_bytes())
            with self.assertRaises(CaptureArtifactError):
                preserve_capture_artifact(capture, destination, transaction_index=1)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
