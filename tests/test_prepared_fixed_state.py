from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.prepared_fixed_state import (
    CAPTURE7_ZERO_STATE_SHA256,
    PreparedFixedStateError,
    assess_prepared_fixed_state,
)
from infocarry.backup_format import parse_backup_blob
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

    def test_verified_display_history_is_supported_only_by_explicit_opt_in(self):
        state = self._zero_state()
        display_history = bytearray(64)
        display_history[0:4] = (1).to_bytes(4, "big")
        # 0x80 is metadata-relative and resolves to the source file at 0xc0.
        display_history[8:12] = (0x80).to_bytes(4, "big")
        state[0x001B] = bytes(display_history)
        temporary, backup = self._backup(state)
        self.addCleanup(temporary.cleanup)

        rejected = assess_prepared_fixed_state(backup)
        self.assertFalse(rejected.eligible)
        self.assertIn("active offset entries", " ".join(rejected.reasons))

        accepted = assess_prepared_fixed_state(
            backup,
            allow_verified_display_history=True,
        )
        snapshot = accepted.require_supported()
        self.assertTrue(accepted.eligible)
        self.assertEqual(snapshot.display_history_record_offsets, (0x80,))
        self.assertEqual(
            snapshot.display_history_paths,
            ((0x80, ("root", "source")),),
        )
        parsed = parse_backup_blob(
            (backup.directory / backup.object_filename("0x8004:backup-blob")).read_bytes()
        )
        self.assertEqual(
            snapshot.validate_display_history_unshifted(parsed, parsed)["references_unshifted"],
            True,
        )

    def test_display_history_rejects_dangling_reference_and_mark_activity(self):
        state = self._zero_state()
        display_history = bytearray(64)
        display_history[0:4] = (1).to_bytes(4, "big")
        display_history[8:12] = (0x400).to_bytes(4, "big")
        state[0x001B] = bytes(display_history)
        temporary, backup = self._backup(state)
        self.addCleanup(temporary.cleanup)
        assessment = assess_prepared_fixed_state(
            backup,
            allow_verified_display_history=True,
        )
        self.assertFalse(assessment.eligible)
        self.assertIn("dangling", " ".join(assessment.reasons))

        mark_state = self._zero_state()
        mark_state[0x001C] = display_history
        temporary_mark, mark_backup = self._backup(mark_state)
        self.addCleanup(temporary_mark.cleanup)
        mark_assessment = assess_prepared_fixed_state(
            mark_backup,
            allow_verified_display_history=True,
        )
        self.assertFalse(mark_assessment.eligible)
        self.assertIn("active offset entries", " ".join(mark_assessment.reasons))

        tail_state = self._zero_state()
        tail_history = bytearray(display_history)
        tail_history[8:12] = (0x80).to_bytes(4, "big")
        tail_history[-1] = 1
        tail_state[0x001B] = bytes(tail_history)
        temporary_tail, tail_backup = self._backup(tail_state)
        self.addCleanup(temporary_tail.cleanup)
        tail_assessment = assess_prepared_fixed_state(
            tail_backup,
            allow_verified_display_history=True,
        )
        self.assertFalse(tail_assessment.eligible)
        self.assertIn("reserved tail", " ".join(tail_assessment.reasons))

    def test_display_history_reference_must_remain_at_the_same_candidate_offset(self):
        state = self._zero_state()
        display_history = bytearray(64)
        display_history[0:4] = (1).to_bytes(4, "big")
        display_history[8:12] = (0x80).to_bytes(4, "big")
        state[0x001B] = bytes(display_history)
        temporary, backup = self._backup(state)
        self.addCleanup(temporary.cleanup)
        assessment = assess_prepared_fixed_state(
            backup,
            allow_verified_display_history=True,
        )
        snapshot = assessment.require_supported()
        parsed = parse_backup_blob(
            (backup.directory / backup.object_filename("0x8004:backup-blob")).read_bytes()
        )
        shifted_paths = dict(parsed.paths)
        shifted_paths[0xC0] = ("root", "shifted")
        from dataclasses import replace

        shifted = replace(parsed, paths=shifted_paths)
        with self.assertRaisesRegex(PreparedFixedStateError, "shifted"):
            snapshot.validate_display_history_unshifted(parsed, shifted)


if __name__ == "__main__":
    unittest.main()
