import struct
import unittest

from infocarry.usblog import (
    UsblogParseError,
    extract_101b,
    find_101b_headers,
)


def _native_payload(payload: bytes, flags: int = 1) -> bytes:
    record = bytearray(0x1A)
    record[:4] = b"\x48\x00\x09\x00"
    struct.pack_into("<H", record, 0x14, len(payload))
    struct.pack_into("<H", record, 0x18, flags)
    record.extend(payload)

    completion = bytearray(0x1A)
    completion[:4] = b"\x48\x00\x09\x00"
    struct.pack_into("<H", completion, 0x14, 2)
    struct.pack_into("<H", completion, 0x18, len(payload))
    record.extend(completion)
    return bytes(record)


def _synthetic_101b() -> bytes:
    range1 = b"A" * 0x100
    range2 = b"B" * 0x40
    range8 = b"Z" * 0x1000
    m = 0x40 + len(range8)
    range3_length = 0x10000 - len(range1) - len(range2)
    range3 = struct.pack(">II", 0, m) + b"\xff" * (range3_length - 8)
    range5 = b"infoCarry 2.00" + b"\x00" * (0x40 - len(b"infoCarry 2.00"))
    payloads = [
        range1,
        range2,
        range3[:0x1000],
        *[b"\xff" * 0x1000 for _ in range(14)],
        b"\xff" * (range3_length - 15 * 0x1000),
        range5,
        range8,
    ]
    declared = 0x10000 + m
    header = b"\x06\x00\x00\x00\x01\x00" + struct.pack("<HI", 0x101B, declared)
    return header + b"\x00" * 32 + b"".join(_native_payload(item) for item in payloads)


class UsblogTests(unittest.TestCase):
    def test_extracts_verified_ranges_and_staging_fields(self):
        capture_bytes = _synthetic_101b()
        self.assertEqual(find_101b_headers(capture_bytes), (0,))

        capture = extract_101b(capture_bytes, 0)
        self.assertEqual(capture.command_offset, 6)
        self.assertEqual(capture.declared_length, 0x10000 + 0x1040)
        self.assertEqual(len(capture.records), 20)
        self.assertEqual(capture.range_lengths, (0x100, 0x40, 0xFEC0, 0, 0x40, 0, 0, 0x1000))
        self.assertEqual(capture.range3_n, 0)
        self.assertEqual(capture.range3_m, 0x1040)
        self.assertEqual(capture.ranges[0], b"A" * 0x100)
        self.assertEqual(capture.ranges[7], b"Z" * 0x1000)

    def test_rejects_a_declared_length_mismatch(self):
        capture_bytes = bytearray(_synthetic_101b())
        struct.pack_into("<I", capture_bytes, 8, 0x1041)
        with self.assertRaises(UsblogParseError):
            extract_101b(capture_bytes, 0)


if __name__ == "__main__":
    unittest.main()
