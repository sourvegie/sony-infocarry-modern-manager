from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from infocarry.timestamp_validator import (
    EVENT_MAPPING_FORMAT,
    TimestampValidationError,
    validate_timestamp_logs,
    write_validation_report,
)


def _write_stamp(
    root: Path,
    filename_sequence: str,
    utc_dt: datetime,
    *,
    offset_minutes: int = 540,
    sequence_text: str | None = None,
    epoch_ms: int | None = None,
    local_timestamp: str | None = None,
    utc_timestamp: str | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    utc_dt = utc_dt.astimezone(timezone.utc)
    local_dt = utc_dt.astimezone(timezone(timedelta(minutes=offset_minutes)))
    if sequence_text is None:
        sequence_text = str(int(filename_sequence))
    if epoch_ms is None:
        epoch_ms = int(utc_dt.timestamp() * 1000)
    if local_timestamp is None:
        local_timestamp = local_dt.isoformat(timespec="milliseconds")
    if utc_timestamp is None:
        utc_timestamp = utc_dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    text = "\r\n".join(
        (
            "format=infocarry-experiment-timestamp-v1",
            f"sequence={sequence_text}",
            f"local_timestamp={local_timestamp}",
            f"utc_timestamp={utc_timestamp}",
            f"epoch_ms={epoch_ms}",
            f"timezone_offset_minutes={offset_minutes}",
            "computer_name=WIN2000",
            "tool_version=1.0.0",
        )
    ) + "\r\n"
    path = root / f"stamp-{filename_sequence}.txt"
    path.write_bytes(text.encode("utf-8"))
    return path


class TimestampValidatorTests(unittest.TestCase):
    def test_valid_timestamp_hashes_raw_file_and_reports_derived_fields_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "logs"
            path = _write_stamp(root, "0001", datetime(2026, 8, 24, 12, 0, 0, 123000, tzinfo=timezone.utc))
            report = validate_timestamp_logs(root)
            self.assertTrue(report["valid"])
            self.assertEqual(report["sequence_numbers"], [1])
            self.assertEqual(report["files"][0]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertNotIn("format=infocarry-experiment-timestamp-v1", json.dumps(report))

    def test_multiple_setup_attempts_allow_sequence_gaps_and_event_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "logs"
            start = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
            _write_stamp(root, "0001", start)
            _write_stamp(root, "0003", start + timedelta(seconds=2))
            mapping = {
                "format": EVENT_MAPPING_FORMAT,
                "events": {"restart_before": 1, "mutation_after": 3},
            }
            report = validate_timestamp_logs(
                root,
                event_mapping=mapping,
                required_events=("restart_before", "mutation_after"),
            )
            self.assertTrue(report["valid"])
            self.assertEqual(report["sequence_gaps"], [2])
            self.assertEqual(report["event_mapping"]["restart_before"], 1)

    def test_duplicate_sequence_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "logs"
            start = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
            _write_stamp(root, "0001", start)
            _write_stamp(root, "00001", start + timedelta(seconds=1), sequence_text="0001")
            report = validate_timestamp_logs(root)
            self.assertFalse(report["valid"])
            self.assertTrue(any("duplicate sequence" in item for item in report["errors"]))

    def test_malformed_fields_are_hashed_and_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "logs"
            root.mkdir()
            path = root / "stamp-0001.txt"
            path.write_bytes(b"format=wrong\r\n")
            report = validate_timestamp_logs(root)
            self.assertFalse(report["valid"])
            self.assertEqual(report["files"][0]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_inconsistent_utc_and_epoch_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "logs"
            path = _write_stamp(root, "0001", datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc), epoch_ms=0)
            report = validate_timestamp_logs(root)
            self.assertFalse(report["valid"])
            self.assertIn("epoch_ms disagrees", " ".join(report["errors"]))
            self.assertTrue(path.exists())

    def test_inconsistent_utc_and_local_timestamp_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "logs"
            _write_stamp(
                root,
                "0001",
                datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc),
                local_timestamp="2026-08-24T22:01:00.000+09:00",
            )
            report = validate_timestamp_logs(root)
            self.assertFalse(report["valid"])
            self.assertIn("local_timestamp and utc_timestamp disagree", " ".join(report["errors"]))

    def test_incorrect_timezone_offset_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "logs"
            _write_stamp(
                root,
                "0001",
                datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc),
                offset_minutes=480,
                local_timestamp="2026-08-24T21:00:00.000+09:00",
            )
            report = validate_timestamp_logs(root)
            self.assertFalse(report["valid"])
            self.assertIn("timezone_offset_minutes disagrees", " ".join(report["errors"]))

    def test_chronological_reversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "logs"
            start = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
            _write_stamp(root, "0001", start + timedelta(seconds=2))
            _write_stamp(root, "0002", start)
            report = validate_timestamp_logs(root)
            self.assertFalse(report["valid"])
            self.assertIn("clock reversal", " ".join(report["errors"]))

    def test_unreasonable_gap_is_a_warning_not_a_clock_reversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "logs"
            start = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
            _write_stamp(root, "0001", start)
            _write_stamp(root, "0002", start + timedelta(hours=2))
            report = validate_timestamp_logs(root, max_gap_ms=1000)
            self.assertTrue(report["valid"])
            self.assertTrue(any("unreasonable gap" in item for item in report["warnings"]))

    def test_missing_event_mapping_is_rejected_when_events_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "logs"
            _write_stamp(root, "0001", datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))
            report = validate_timestamp_logs(root, required_events=("restart_before",))
            self.assertFalse(report["valid"])
            self.assertIn("event mapping is required", " ".join(report["errors"]))

    def test_missing_mapping_sequence_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "logs"
            _write_stamp(root, "0001", datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))
            report = validate_timestamp_logs(
                root,
                event_mapping={"events": {"restart_before": 2}},
            )
            self.assertFalse(report["valid"])
            self.assertIn("references missing sequence", " ".join(report["errors"]))

    def test_report_output_is_non_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "logs"
            _write_stamp(root, "0001", datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))
            report = validate_timestamp_logs(root)
            output = Path(temporary) / "report.json"
            write_validation_report(output, report)
            original = output.read_bytes()
            with self.assertRaises(TimestampValidationError):
                write_validation_report(output, {"changed": True})
            self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
