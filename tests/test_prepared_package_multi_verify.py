from datetime import datetime, timezone
from pathlib import Path
import unittest

from infocarry.prepared_package_multi_verify import (
    PreparedMultiVerificationError,
    verify_prepared_multi_package_readback,
)

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


if __name__ == "__main__":
    unittest.main()
