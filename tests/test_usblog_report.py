import unittest

from infocarry.usblog import Usblog101bCapture
from infocarry.usblog_report import compare_bytes, compare_captures


def _capture(ranges):
    return Usblog101bCapture(
        record_offset=0,
        command_offset=6,
        declared_length=sum(len(item) for item in ranges),
        records=(),
        ranges=tuple(ranges),
    )


class UsblogReportTests(unittest.TestCase):
    def test_compare_bytes_reports_localized_change_and_growth(self):
        report = compare_bytes(b"abc123xyz", b"abc456+xyz")
        self.assertFalse(report["equal"])
        self.assertEqual(report["length_delta"], 1)
        self.assertEqual(report["first_difference"], 3)
        self.assertEqual(report["common_prefix_length"], 3)
        self.assertEqual(report["common_suffix_length"], 3)
        self.assertEqual(report["differing_byte_count"], 7)

    def test_compare_captures_identifies_changed_ranges(self):
        reference = _capture(
            (b"a", b"bb", b"\x00" * 7 + b"\x01", b"", b"dd", b"", b"", b"model")
        )
        candidate = _capture(
            (b"a", b"bb", b"\x00" * 7 + b"\x02", b"", b"dd2", b"", b"", b"model+")
        )
        report = compare_captures(reference, candidate)
        self.assertEqual(report["changed_ranges"], [3, 5, 8])
        self.assertEqual(report["declared_length_delta"], 2)
        self.assertEqual(report["ranges"][0]["equal"], True)
        self.assertEqual(report["ranges"][7]["length_delta"], 1)


if __name__ == "__main__":
    unittest.main()
