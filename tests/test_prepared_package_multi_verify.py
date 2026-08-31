from datetime import datetime, timezone
from pathlib import Path
import unittest

from infocarry.prepared_package_multi_verify import (
    PreparedMultiVerificationError,
    verify_prepared_multi_package_readback,
)
from infocarry.prepared_package_multi_candidate import build_prepared_multi_package_candidate
from infocarry.write_gate import verify_fresh_backup

try:
    import test_prepared_package_multi_candidate as _multi_fixture
    from test_new_txt import _write_archive
except ModuleNotFoundError:
    import tests.test_prepared_package_multi_candidate as _multi_fixture
    from tests.test_new_txt import _write_archive


class PreparedMultiVerifyTests(unittest.TestCase):
    def _case(self):
        return _multi_fixture.PreparedMultiCandidateTests()._case(mixed=True)

    def test_complete_readback_verifies_order_types_and_preservation(self):
        temporary, _package, _backup, candidate, _template = self._case()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        zero_state = {command: b"\x00" * 64 for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
        post = _write_archive(root / "after", candidate.candidate_blob, now, fixed_state=zero_state)
        result = verify_prepared_multi_package_readback(
            candidate, post, completion=0, now=now, max_age_seconds=None
        )
        self.assertTrue(result.success)
        self.assertEqual(result.details["ordered_children_verified"], True)
        self.assertEqual(result.details["removed_paths"], [])
        self.assertFalse(result.to_dict()["automatic_retry"])

    def test_nonzero_or_missing_completion_is_terminal(self):
        temporary, _package, _backup, candidate, _template = self._case()
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(PreparedMultiVerificationError, "only 0x0000"):
            verify_prepared_multi_package_readback(candidate, Path("unused"), completion=1)
        with self.assertRaisesRegex(PreparedMultiVerificationError, "missing or malformed"):
            verify_prepared_multi_package_readback(candidate, Path("unused"), completion=None)

    def test_malformed_or_mismatched_post_blob_is_terminal(self):
        temporary, _package, _backup, candidate, _template = self._case()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        post = _write_archive(root / "after", candidate.candidate_blob[:-1], now)
        with self.assertRaisesRegex(PreparedMultiVerificationError, "backup|dynamic blob"):
            verify_prepared_multi_package_readback(
                candidate, post, completion=0, now=now, max_age_seconds=None
            )

    def test_fixed_state_difference_is_terminal(self):
        temporary, _package, _backup, candidate, _template = self._case()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        state = {command: b"\x00" * 64 for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
        state[0x001C] = b"\x01" + b"\x00" * 63
        post = _write_archive(root / "fixed-mismatch", candidate.candidate_blob, now, fixed_state=state)
        with self.assertRaisesRegex(PreparedMultiVerificationError, "fixed-state"):
            verify_prepared_multi_package_readback(
                candidate, post, completion=0, now=now, max_age_seconds=None
            )

    def test_readback_verifies_preserved_display_history_and_zero_mark_state(self):
        temporary, package, _zero_backup, zero_candidate, template = self._case()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        state = {
            command: b"\x00" * 64
            for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)
        }
        display_history = bytearray(64)
        display_history[0:4] = (1).to_bytes(4, "big")
        display_history[8:12] = (0x80).to_bytes(4, "big")
        state[0x001B] = bytes(display_history)
        baseline_path = _write_archive(
            root / "display-history-before",
            zero_candidate.baseline.data,
            now,
            fixed_state=state,
        )
        backup = verify_fresh_backup(baseline_path, now=now, max_age_seconds=None)
        candidate = build_prepared_multi_package_candidate(
            package,
            backup,
            template,
            new_record_timestamp_be32=0x6A8ABA6F,
            native_capacity_response=_multi_fixture.PreparedMultiCandidateTests()._response(),
            template_folder_path=("root", "Template"),
            template_item_paths={
                "txt": ("root", "Template", "chapter"),
                "bmp": ("root", "Template", "page"),
            },
        )
        post = _write_archive(
            root / "display-history-after",
            candidate.candidate_blob,
            now,
            fixed_state=state,
        )
        result = verify_prepared_multi_package_readback(
            candidate,
            post,
            completion=0,
            now=now,
            max_age_seconds=None,
        )
        self.assertTrue(result.success)
        self.assertTrue(result.details["display_history"]["semantic_preserved"])
        self.assertEqual(result.details["display_history"]["references_rebased"], 0)

    def test_readback_requires_exact_semantic_rebase_and_same_path_resolution(self):
        temporary, package, _zero_backup, _zero_candidate, template = self._case()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        state = {
            command: b"\x00" * 64
            for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)
        }
        display_history = bytearray(64)
        display_history[0:4] = (3).to_bytes(4, "big")
        for index, offset in enumerate((0x80, 0x140, 0x180)):
            display_history[8 + index * 4 : 12 + index * 4] = offset.to_bytes(4, "big")
        state[0x001B] = bytes(display_history)
        before_path = _write_archive(
            root / "semantic-rebase-before",
            template.data,
            now,
            fixed_state=state,
        )
        backup = verify_fresh_backup(before_path, now=now, max_age_seconds=None)
        candidate = build_prepared_multi_package_candidate(
            package,
            backup,
            template,
            new_record_timestamp_be32=0x6A8ABA6F,
            native_capacity_response=_multi_fixture.PreparedMultiCandidateTests()._response(),
            template_folder_path=("root", "Template"),
            template_item_paths={
                "txt": ("root", "Template", "chapter"),
                "bmp": ("root", "Template", "page"),
            },
        )
        post_state = dict(
            zip(
                (0x001B, 0x001C, 0x001D, 0x001E, 0x001F),
                candidate.fixed_state.candidate_raw_blocks,
            )
        )
        post = _write_archive(
            root / "semantic-rebase-after",
            candidate.candidate_blob,
            now,
            fixed_state=post_state,
        )
        result = verify_prepared_multi_package_readback(
            candidate, post, completion=0, now=now, max_age_seconds=None
        )
        self.assertTrue(result.details["display_history"]["semantic_preserved"])
        self.assertEqual(result.details["display_history"]["references_rebased"], 2)
        self.assertFalse(result.details["display_history"]["raw_preserved_exactly"])

        unrebased_post = _write_archive(
            root / "semantic-rebase-unexpected",
            candidate.candidate_blob,
            now,
            fixed_state=state,
        )
        with self.assertRaisesRegex(PreparedMultiVerificationError, "fixed-state"):
            verify_prepared_multi_package_readback(
                candidate, unrebased_post, completion=0, now=now, max_age_seconds=None
            )


if __name__ == "__main__":
    unittest.main()
