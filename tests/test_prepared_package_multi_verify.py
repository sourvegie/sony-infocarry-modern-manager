from datetime import datetime, timezone
from dataclasses import replace
from copy import deepcopy
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

    def _bookmark_case(self):
        temporary, package, _zero_backup, zero_candidate, template = self._case()
        root = Path(temporary.name)
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        state = {
            command: bytearray(64)
            for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)
        }
        state[0x001B][0:4] = (1).to_bytes(4, "big")
        state[0x001B][8:12] = (0x80).to_bytes(4, "big")
        state[0x001B][60:] = b"HIST"
        bookmark_values = (0x80, 0xC00, 0, 0x14, 0xFFF101C5)
        state[0x001F][:20] = b"".join(
            value.to_bytes(4, "big") for value in bookmark_values
        )
        state[0x001F][40:] = b"B" * 24
        raw_state = {command: bytes(value) for command, value in state.items()}
        before_path = _write_archive(
            root / "bookmark-before",
            zero_candidate.baseline.data,
            now,
            fixed_state=raw_state,
        )
        backup = verify_fresh_backup(before_path, now=now, max_age_seconds=None)
        candidate = _multi_fixture.build_prepared_multi_package_candidate(
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
            allow_verified_bookmarks=True,
        )
        post_state = dict(
            zip(
                (0x001B, 0x001C, 0x001D, 0x001E, 0x001F),
                candidate.fixed_state.candidate_raw_blocks,
            )
        )
        post_path = _write_archive(
            root / "bookmark-after",
            candidate.candidate_blob,
            now,
            fixed_state=post_state,
        )
        return temporary, candidate, post_path, post_state

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

    def test_readback_verifies_the_sealed_bookmark_preservation_policy(self):
        temporary, candidate, post_path, _post_state = self._bookmark_case()
        self.addCleanup(temporary.cleanup)
        result = verify_prepared_multi_package_readback(
            candidate, post_path, completion=0, now=datetime(2026, 8, 27, tzinfo=timezone.utc), max_age_seconds=None
        )
        self.assertTrue(result.success)
        self.assertEqual(result.details["bookmarks"]["groups"][0]["path"], "root\\old")
        self.assertTrue(result.details["bookmarks"]["opaque_values_preserved_exactly"])
        self.assertTrue(result.details["bookmarks"]["unused_tail_preserved_exactly"])
        self.assertTrue(result.details["display_history"]["semantic_preserved"])

    def test_bookmark_and_auxiliary_state_tampering_is_rejected(self):
        temporary, candidate, post_path, post_state = self._bookmark_case()
        self.addCleanup(temporary.cleanup)
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        cases = {
            "altered bookmark pointer": lambda block: block.__setitem__(slice(0, 4), (0xC0).to_bytes(4, "big")),
            "unaligned pointer": lambda block: block.__setitem__(slice(0, 4), (0x81).to_bytes(4, "big")),
            "dangling pointer": lambda block: block.__setitem__(slice(0, 4), (0xFFFFF000).to_bytes(4, "big")),
            "opaque dword mutation": lambda block: block.__setitem__(slice(4, 8), (0xC01).to_bytes(4, "big")),
            "unused-tail mutation": lambda block: block.__setitem__(40, block[40] ^ 1),
            "unexpected active bookmark group": lambda block: block.__setitem__(slice(20, 24), (0x80).to_bytes(4, "big")),
            "altered display-history pointer": lambda block: block.__setitem__(slice(8, 12), (0xC0).to_bytes(4, "big")),
            "nonzero 0x001c": lambda block: block.__setitem__(0, 1),
            "nonzero 0x001d": lambda block: block.__setitem__(0, 1),
            "nonzero 0x001e": lambda block: block.__setitem__(0, 1),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                fixed = {
                    command: bytearray(value)
                    for command, value in post_state.items()
                }
                if name == "nonzero 0x001c":
                    mutate(fixed[0x001C])
                elif name == "nonzero 0x001d":
                    mutate(fixed[0x001D])
                elif name == "nonzero 0x001e":
                    mutate(fixed[0x001E])
                elif name == "altered display-history pointer":
                    mutate(fixed[0x001B])
                else:
                    mutate(fixed[0x001F])
                altered = _write_archive(
                    Path(temporary.name) / f"after-{name.replace(' ', '-')}",
                    candidate.candidate_blob,
                    now,
                    fixed_state={command: bytes(value) for command, value in fixed.items()},
                )
                with self.assertRaises(PreparedMultiVerificationError):
                    verify_prepared_multi_package_readback(
                        candidate, altered, completion=0, now=now, max_age_seconds=None
                    )

    def test_candidate_policy_and_snapshot_binding_tampering_is_rejected(self):
        temporary, candidate, post_path, _post_state = self._bookmark_case()
        self.addCleanup(temporary.cleanup)
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        altered_audit = deepcopy(candidate.audit_dict())
        altered_audit["policy"]["fixed_state"] = "capture7_exact_all_zero_fixed_state"
        with self.assertRaisesRegex(PreparedMultiVerificationError, "policy"):
            verify_prepared_multi_package_readback(
                replace(candidate, audit=altered_audit),
                post_path,
                completion=0,
                now=now,
                max_age_seconds=None,
            )
        altered_snapshot = replace(candidate.fixed_state, bookmark_group_paths=())
        with self.assertRaisesRegex(PreparedMultiVerificationError, "snapshot"):
            verify_prepared_multi_package_readback(
                replace(candidate, fixed_state=altered_snapshot),
                post_path,
                completion=0,
                now=now,
                max_age_seconds=None,
            )
        wrong_path_audit = deepcopy(candidate.audit_dict())
        wrong_path_audit["fixed_state"]["snapshot"]["bookmarks"]["groups"][0][
            "path"
        ] = "root\\wrong"
        with self.assertRaisesRegex(PreparedMultiVerificationError, "audit snapshot"):
            verify_prepared_multi_package_readback(
                replace(candidate, audit=wrong_path_audit),
                post_path,
                completion=0,
                now=now,
                max_age_seconds=None,
            )
        wrong_display_path_audit = deepcopy(candidate.audit_dict())
        wrong_display_path_audit["fixed_state"]["snapshot"]["display_history"][
            "paths"
        ][0]["path"] = "root\\wrong"
        with self.assertRaisesRegex(PreparedMultiVerificationError, "audit snapshot"):
            verify_prepared_multi_package_readback(
                replace(candidate, audit=wrong_display_path_audit),
                post_path,
                completion=0,
                now=now,
                max_age_seconds=None,
            )


if __name__ == "__main__":
    unittest.main()
