from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import struct
import tempfile
import unittest

from infocarry.backup_format import parse_backup_blob
from infocarry.delete_generalized import (
    DELETE_GENERALIZED_CONFIRMATION_PHRASE,
    GeneralizedDeleteError,
    GeneralizedDeleteVerificationError,
    authorize_generalized_delete,
    bind_generalized_delete_sender,
    build_generalized_delete_candidate,
    verify_generalized_delete_readback,
)

try:
    from test_new_txt import _make_root_blob, _write_archive
except ModuleNotFoundError:
    from tests.test_new_txt import _make_root_blob, _write_archive


def _offset_list(offset):
    data = bytearray(64)
    struct.pack_into(">I", data, 0, 1)
    struct.pack_into(">I", data, 8, offset)
    return bytes(data)


def _bookmark(offset):
    data = bytearray(64)
    struct.pack_into(">IIIII", data, 0, offset, 0, 0x80000000, 0, 0)
    return bytes(data)


class GeneralizedDeleteTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 25, tzinfo=timezone.utc)

    def _case(self, *, stateful=False):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        target_ref = 0xC0 - 0x40
        if stateful:
            fixed = {
                0x001B: _offset_list(target_ref),
                0x001C: _offset_list(target_ref),
                0x001D: bytes(64),
                0x001E: bytes(64),
                0x001F: _bookmark(target_ref),
            }
        else:
            fixed = {command: bytes(64) for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
        backup = _write_archive(
            root / "before",
            _make_root_blob(b"source\r\n"),
            self.now,
            fixed_state=fixed,
        )
        candidate = build_generalized_delete_candidate(
            backup,
            "root\\source.txt",
            0xC0,
            now=self.now,
            max_age_seconds=None,
        )
        return temporary, root, backup, candidate

    def _post(self, root, candidate, *, name="after", fixed_state=None, blob=None):
        if fixed_state is None:
            fixed_state = dict(
                zip((0x001B, 0x001C, 0x001D, 0x001E, 0x001F), candidate.fixed_state.after)
            )
        return _write_archive(
            root / name,
            candidate.candidate_blob if blob is None else blob,
            self.now,
            fixed_state=fixed_state,
        )

    def test_all_zero_state_candidate_preserves_timestamps_and_binds_exact_transaction(self):
        temporary, _root, _backup, candidate = self._case()
        self.addCleanup(temporary.cleanup)
        self.assertEqual(candidate.fixed_state.changed_commands, ())
        self.assertEqual(candidate.candidate_model.audit["timestamps"]["policy"], "preserve_surviving_timestamps")
        candidate_blob = parse_backup_blob(candidate.candidate_blob)
        self.assertEqual(
            candidate_blob.record_at(0x40).timestamp_be32,
            candidate.baseline.record_at(0x40).timestamp_be32,
        )
        authorization = authorize_generalized_delete(
            candidate,
            confirmation=DELETE_GENERALIZED_CONFIRMATION_PHRASE,
        )
        self.assertEqual(authorization.to_dict()["target_path"], "root\\source.txt")
        self.assertEqual(authorization.transaction_sha256, candidate.transaction_sha256)
        bind_generalized_delete_sender(authorization, candidate, now=self.now, max_age_seconds=None)

    def test_proven_target_references_are_cleared_without_attempt02_constants(self):
        temporary, _root, _backup, candidate = self._case(stateful=True)
        self.addCleanup(temporary.cleanup)
        self.assertEqual(candidate.fixed_state.changed_commands, (0x001B, 0x001C, 0x001F))
        self.assertEqual(candidate.fixed_state.after, (bytes(64),) * 5)
        self.assertEqual(candidate.audit["fixed_state"]["derivation"]["policy"], "exact_target_reference_clear_only")

    def test_authorization_rejects_each_bound_candidate_mutation(self):
        temporary, _root, _backup, candidate = self._case()
        self.addCleanup(temporary.cleanup)
        authorization = authorize_generalized_delete(
            candidate,
            confirmation=DELETE_GENERALIZED_CONFIRMATION_PHRASE,
        )
        mutations = (
            ("backup", replace(candidate, backup=replace(candidate.backup, blob_sha256="0" * 64))),
            ("target", replace(candidate.candidate_model, target_path="root\\other.txt")),
            ("candidate", replace(candidate.candidate_model, candidate_blob=b"changed")),
        )
        for label, altered in mutations:
            with self.subTest(label=label):
                if label == "target":
                    altered_candidate = replace(candidate, candidate_model=altered)
                elif label == "candidate":
                    altered_candidate = replace(candidate, candidate_model=altered)
                else:
                    altered_candidate = altered
                with self.assertRaises(GeneralizedDeleteError):
                    authorization.require_same_candidate(altered_candidate)

    def test_exact_post_readback_is_verified(self):
        temporary, root, _backup, candidate = self._case(stateful=True)
        self.addCleanup(temporary.cleanup)
        result = verify_generalized_delete_readback(
            candidate,
            self._post(root, candidate),
            completion=0,
            now=self.now,
            max_age_seconds=None,
        )
        self.assertTrue(result.fixed_state_matches)
        self.assertTrue(result.target_removed)
        self.assertEqual(result.details["record_count_after"], result.details["record_count_before"] - 1)

    def test_nonzero_completion_and_bad_readback_are_terminal_without_retry(self):
        temporary, root, _backup, candidate = self._case()
        self.addCleanup(temporary.cleanup)
        with self.assertRaises(GeneralizedDeleteVerificationError) as raised:
            verify_generalized_delete_readback(
                candidate,
                root / "missing-post",
                completion=1,
                now=self.now,
                max_age_seconds=None,
            )
        self.assertFalse(raised.exception.automatic_retry_allowed)
        with self.assertRaisesRegex(GeneralizedDeleteVerificationError, "fixed state"):
            bad = dict(zip((0x001B, 0x001C, 0x001D, 0x001E, 0x001F), candidate.fixed_state.after))
            bad[0x001B] = b"\x01" + bytes(63)
            verify_generalized_delete_readback(
                candidate,
                self._post(root, candidate, name="bad-state", fixed_state=bad),
                completion=0,
                now=self.now,
                max_age_seconds=None,
            )


if __name__ == "__main__":
    unittest.main()
