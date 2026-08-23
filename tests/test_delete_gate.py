from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import parse_backup_blob
from infocarry.delete_gate import (
    ATTEMPT02_TRANSMITTED_FIXED_STATE,
    DELETE_ONE_CONFIRMATION_PHRASE,
    DeleteGateError,
    authorize_delete,
    build_delete_candidate,
    verify_post_delete_backup,
)
try:
    from test_new_txt import _make_root_blob, _write_archive
except ModuleNotFoundError:
    from tests.test_new_txt import _make_root_blob, _write_archive


class DeleteGateTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 22, tzinfo=timezone.utc)

    def _case(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        backup = _write_archive(root / "before", _make_root_blob(b"source\r\n"), self.now)
        parsed = parse_backup_blob((backup / "object-08.bin").read_bytes())
        timestamps = {
            record.offset: 0x65000000 + index
            for index, record in enumerate(parsed.records)
            if record.offset != 0xC0
        }
        candidate = build_delete_candidate(
            backup,
            "root\\source.txt",
            0xC0,
            timestamps,
            now=self.now,
            max_age_seconds=None,
        )
        return temporary, root, backup, parsed, timestamps, candidate

    def _post(self, root, candidate, *, fixed_state=None, blob=None, name="after"):
        if fixed_state is None:
            fixed_state = {
                0x001B: candidate.transaction.ranges[0][0x00:0x40],
                0x001C: candidate.transaction.ranges[0][0x40:0x80],
                0x001D: b"\x00" * 64,
                0x001E: candidate.transaction.ranges[0][0xC0:0x100],
                0x001F: candidate.transaction.ranges[1],
            }
        return _write_archive(
            root / name,
            candidate.candidate_blob if blob is None else blob,
            self.now,
            fixed_state=fixed_state,
        )

    def test_attempt02_descriptor_is_hash_documented_without_raw_evidence(self):
        descriptor_path = Path(__file__).parent / "fixtures" / "milestone_h_delete_attempt_02.json"
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        self.assertEqual(descriptor["source_kind"], "hash_and_structure_descriptor_only")
        self.assertEqual(descriptor["target"]["pre_record_offset"], "0x000002c0")
        self.assertEqual(descriptor["target"]["pre_record_count"], 368)
        self.assertEqual(descriptor["target"]["post_record_count"], 367)
        self.assertEqual(descriptor["native_transaction"]["variable_n"], 0)
        self.assertEqual(descriptor["fixed_state_normalization"]["native_value_04"], 1)
        self.assertEqual(descriptor["fixed_state_normalization"]["post_value_04"], 0)

    def test_build_delete_candidate_preserves_unrelated_records_and_is_deterministic(self):
        temporary, _root, backup, parsed, timestamps, candidate = self._case()
        self.addCleanup(temporary.cleanup)
        again = build_delete_candidate(
            backup,
            "root\\source.txt",
            0xC0,
            timestamps,
            now=self.now,
            max_age_seconds=None,
        )
        rebuilt = parse_backup_blob(candidate.candidate_blob)
        self.assertNotIn(("root", "source.txt"), rebuilt.paths.values())
        self.assertEqual(len(rebuilt.records), len(parsed.records) - 1)
        self.assertEqual(candidate.audit, again.audit)
        self.assertEqual(candidate.transaction.concatenated_sha256, again.transaction.concatenated_sha256)
        self.assertEqual(candidate.audit["timestamps"]["classification"], "observed_opaque_map")
        self.assertFalse(candidate.audit["timestamps"]["rule_inferred"])
        self.assertEqual(candidate.transaction.ranges[0x00][0x80:0x86], b"\x00\x00\x00\x00\x00\x01")
        self.assertEqual(
            hashlib.sha256((backup / "object-08.bin").read_bytes()).hexdigest(),
            candidate.baseline.blob_sha256,
        )
        self.assertEqual(
            (backup / "object-08.bin").read_bytes(),
            parsed.data,
        )

    def test_delete_requires_complete_opaque_timestamp_map_and_observed_fixed_state(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        backup = _write_archive(root / "before", _make_root_blob(), self.now)
        parsed = parse_backup_blob((backup / "object-08.bin").read_bytes())
        complete = {record.offset: 1 for record in parsed.records if record.offset != 0xC0}
        with self.assertRaisesRegex(DeleteGateError, "exactly every surviving"):
            build_delete_candidate(
                backup, "root\\source.txt", 0xC0, {}, now=self.now, max_age_seconds=None
            )
        with self.assertRaisesRegex(DeleteGateError, "observed attempt-02"):
            bad_state = type(ATTEMPT02_TRANSMITTED_FIXED_STATE)(
                offset_lists=(b"\x00" * 64,) * 4,
                grouped_values=b"\x00" * 64,
            )

    def test_authorization_binds_phrase_target_offset_payload_and_hashes(self):
        temporary, _root, backup, _parsed, _timestamps, candidate = self._case()
        self.addCleanup(temporary.cleanup)
        authorization = authorize_delete(
            candidate,
            confirmation=DELETE_ONE_CONFIRMATION_PHRASE,
        )
        encoded = authorization.to_dict()
        self.assertEqual(encoded["operation"], "delete_one_root_txt")
        self.assertEqual(encoded["target_record_offset_hex"], "0x000000c0")
        self.assertFalse(encoded["usb_transmission_performed"])
        authorization.revalidate(candidate, now=self.now, max_age_seconds=None)
        altered = object.__new__(type(candidate))
        object.__setattr__(altered, "baseline", candidate.baseline)
        object.__setattr__(altered, "transaction", candidate.transaction)
        object.__setattr__(altered, "target_path", "root\\other.txt")
        object.__setattr__(altered, "target_record_offset", candidate.target_record_offset)
        object.__setattr__(altered, "target_payload_sha256", candidate.target_payload_sha256)
        object.__setattr__(altered, "audit", candidate.audit)
        with self.assertRaisesRegex(DeleteGateError, "target path"):
            authorization.require_same_candidate(altered)

    def test_post_delete_verifier_allows_only_the_observed_001d_normalization(self):
        temporary, root, _backup, _parsed, _timestamps, candidate = self._case()
        self.addCleanup(temporary.cleanup)
        post = self._post(root, candidate)
        result = verify_post_delete_backup(
            candidate,
            post,
            completion=0,
            now=self.now,
            max_age_seconds=None,
        )
        self.assertTrue(result.fixed_state_matches)
        self.assertTrue(result.dynamic_blob_matches)
        self.assertTrue(result.target_removed)
        self.assertEqual(result.allowed_fixed_state_normalization, "0x001d.value_04: 1 -> 0 only")

    def test_post_delete_verifier_rejects_nonzero_completion_and_other_fixed_difference(self):
        temporary, root, _backup, _parsed, _timestamps, candidate = self._case()
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(DeleteGateError, "no retry"):
            verify_post_delete_backup(
                candidate,
                root / "missing-post",
                completion=1,
                now=self.now,
                max_age_seconds=None,
            )
        bad_fixed = {
            0x001B: candidate.transaction.ranges[0][0x00:0x40],
            0x001C: candidate.transaction.ranges[0][0x40:0x80],
            0x001D: b"\x00" * 64,
            0x001E: b"\x01" + candidate.transaction.ranges[0][0xC1:0x100],
            0x001F: candidate.transaction.ranges[1],
        }
        post = self._post(root, candidate, fixed_state=bad_fixed, name="bad-fixed")
        with self.assertRaisesRegex(DeleteGateError, "0x1e"):
            verify_post_delete_backup(
                candidate,
                post,
                completion=0,
                now=self.now,
                max_age_seconds=None,
            )


if __name__ == "__main__":
    unittest.main()
