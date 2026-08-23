from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.prepared_fixed_state import (
    CAPTURE7_ZERO_STATE_SHA256,
    PreparedFixedStateError,
    assess_prepared_fixed_state,
)
from infocarry.write_gate import verify_fresh_backup

try:
    from test_new_txt import _make_root_blob, _write_archive
except ModuleNotFoundError:
    from tests.test_new_txt import _make_root_blob, _write_archive


class PreparedFixedStateTests(unittest.TestCase):
    def _backup(self, fixed_state):
        temporary = tempfile.TemporaryDirectory()
        now = datetime(2026, 8, 23, tzinfo=timezone.utc)
        backup = _write_archive(
            Path(temporary.name) / "backup",
            _make_root_blob(),
            now,
            fixed_state=fixed_state,
        )
        return temporary, verify_fresh_backup(backup, now=now, max_age_seconds=None)

    def _zero_state(self):
        return {command: b"\x00" * 64 for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}

    def test_exact_capture7_all_zero_state_is_eligible_and_raw_bytes_are_preserved(self):
        temporary, backup = self._backup(self._zero_state())
        self.addCleanup(temporary.cleanup)
        assessment = assess_prepared_fixed_state(backup)
        snapshot = assessment.require_supported()
        self.assertTrue(assessment.eligible)
        self.assertEqual(CAPTURE7_ZERO_STATE_SHA256, "f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b")
        self.assertEqual(snapshot.range1, b"\x00" * 0x100)
        self.assertEqual(snapshot.range2, b"\x00" * 0x40)
        self.assertTrue(all(block == b"\x00" * 64 for block in snapshot.raw_blocks))
        self.assertTrue(all(report["supported"] for report in assessment.block_reports))

    def test_each_offset_list_active_entry_is_rejected(self):
        for command in (0x001B, 0x001C, 0x001D, 0x001E):
            with self.subTest(command=command):
                state = self._zero_state()
                raw = bytearray(64)
                raw[0:4] = (1).to_bytes(4, "big")
                raw[8:12] = (0x40).to_bytes(4, "big")
                state[command] = bytes(raw)
                temporary, backup = self._backup(state)
                self.addCleanup(temporary.cleanup)
                assessment = assess_prepared_fixed_state(backup)
                self.assertFalse(assessment.eligible)
                self.assertIn("active offset entries", " ".join(assessment.reasons))
                with self.assertRaises(PreparedFixedStateError):
                    assessment.require_supported()

    def test_each_reserved_or_header_difference_is_rejected(self):
        for command, index in ((0x001B, 4), (0x001C, 6), (0x001D, 63), (0x001E, 20), (0x001F, 40)):
            with self.subTest(command=command, index=index):
                state = self._zero_state()
                raw = bytearray(64)
                raw[index] = 1
                state[command] = bytes(raw)
                temporary, backup = self._backup(state)
                self.addCleanup(temporary.cleanup)
                assessment = assess_prepared_fixed_state(backup)
                self.assertFalse(assessment.eligible)
                with self.assertRaises(PreparedFixedStateError):
                    assessment.require_supported()

    def test_malformed_fixed_state_length_is_rejected(self):
        state = self._zero_state()
        state[0x001F] = b"short"
        temporary, backup = self._backup(state)
        self.addCleanup(temporary.cleanup)
        assessment = assess_prepared_fixed_state(backup)
        self.assertFalse(assessment.eligible)
        self.assertIn("expected 64", " ".join(assessment.reasons))


if __name__ == "__main__":
    unittest.main()
