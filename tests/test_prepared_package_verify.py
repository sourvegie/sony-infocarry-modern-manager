from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import parse_backup_blob
from infocarry.prepared_package_candidate import build_prepared_package_candidate
from infocarry.prepared_package_gate import (
    PREPARED_PACKAGE_CONFIRMATION_PHRASE,
    authorize_prepared_package,
)
from infocarry.prepared_package_verify import (
    PreparedPackageVerificationError,
    verify_prepared_package_readback,
)
from infocarry.prepared_package import build_prepared_text_package
from infocarry.write_gate import verify_fresh_backup

try:
    from test_new_txt import _write_archive
    from test_prepared_folder import make_folder_fixtures
except ModuleNotFoundError:
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_folder import make_folder_fixtures


class PreparedPackageVerificationTests(unittest.TestCase):
    def _case(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        baseline_blob, template_blob = make_folder_fixtures()
        zero_state = {command: b"\x00" * 64 for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
        now = datetime(2026, 8, 23, tzinfo=timezone.utc)
        before_path = _write_archive(root / "before", baseline_blob, now, fixed_state=zero_state)
        source = root / "source.txt"
        source.write_text("A\nB", encoding="utf-8")
        package = build_prepared_text_package(source, "Package", "chapter.txt")
        before = verify_fresh_backup(before_path, now=now, max_age_seconds=None)
        candidate = build_prepared_package_candidate(
            package,
            before,
            parse_backup_blob(template_blob),
            new_record_timestamp_be32=0x6A8ABA6F,
            available_capacity_bytes=10_000,
        )
        authorization = authorize_prepared_package(
            candidate,
            confirmation=PREPARED_PACKAGE_CONFIRMATION_PHRASE,
        )
        return temporary, root, now, zero_state, candidate, authorization

    def _post(self, root, name, blob, now, fixed_state):
        return _write_archive(root / name, blob, now, fixed_state=fixed_state)

    def test_exact_candidate_and_zero_completion_verify_successfully(self):
        temporary, root, now, zero_state, candidate, authorization = self._case()
        self.addCleanup(temporary.cleanup)
        post = self._post(root, "after", candidate.candidate_blob, now, zero_state)
        result = verify_prepared_package_readback(
            authorization,
            candidate,
            post,
            completion=0,
            now=now,
            max_age_seconds=None,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.completion, 0)
        self.assertEqual(result.details["removed_paths"], [])
        self.assertTrue(result.details["shared_timestamps_unchanged"])
        self.assertFalse(result.to_dict()["automatic_retry"])

    def test_payload_dependent_probe_and_0024_changes_are_allowed(self):
        temporary, root, now, zero_state, candidate, authorization = self._case()
        self.addCleanup(temporary.cleanup)
        post = self._post(root, "payload-dependent", candidate.candidate_blob, now, zero_state)
        manifest_path = post / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest["objects"]:
            if entry["filename"] in {"object-01.bin", "object-07.bin"}:
                path = post / entry["filename"]
                data = bytes((value + 1) % 256 for value in path.read_bytes())
                path.write_bytes(data)
                entry["sha256"] = hashlib.sha256(data).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        result = verify_prepared_package_readback(
            authorization,
            candidate,
            post,
            completion=0,
            now=now,
            max_age_seconds=None,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.unchanged_object_count, 5)

    def test_nonzero_missing_or_malformed_completion_is_terminal_without_retry(self):
        temporary, root, now, zero_state, candidate, authorization = self._case()
        self.addCleanup(temporary.cleanup)
        post = self._post(root, "after", candidate.candidate_blob, now, zero_state)
        for completion in (1, None, "0"):
            with self.subTest(completion=completion):
                with self.assertRaisesRegex(PreparedPackageVerificationError, "automatic retry is prohibited") as raised:
                    verify_prepared_package_readback(
                        authorization,
                        candidate,
                        post,
                        completion=completion,
                        now=now,
                        max_age_seconds=None,
                    )
                self.assertFalse(raised.exception.automatic_retry_allowed)
                self.assertEqual(raised.exception.outcome, "failed")

    def test_missing_or_malformed_post_backup_is_indeterminate(self):
        temporary, root, now, _zero_state, candidate, authorization = self._case()
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(PreparedPackageVerificationError, "post-operation backup") as raised:
            verify_prepared_package_readback(
                authorization,
                candidate,
                root / "missing",
                completion=0,
                now=now,
                max_age_seconds=None,
            )
        self.assertEqual(raised.exception.outcome, "indeterminate")
        self.assertIn("read-only", raised.exception.recovery_guidance)

    def test_candidate_mismatch_and_fixed_state_difference_are_terminal(self):
        temporary, root, now, zero_state, candidate, authorization = self._case()
        self.addCleanup(temporary.cleanup)
        baseline = candidate.baseline.data
        mismatch = self._post(root, "mismatch", baseline, now, zero_state)
        with self.assertRaisesRegex(PreparedPackageVerificationError, "dynamic blob"):
            verify_prepared_package_readback(
                authorization,
                candidate,
                mismatch,
                completion=0,
                now=now,
                max_age_seconds=None,
            )
        changed_state = dict(zero_state)
        block = bytearray(changed_state[0x001B])
        block[4] = 1
        changed_state[0x001B] = bytes(block)
        fixed_mismatch = self._post(root, "fixed-mismatch", candidate.candidate_blob, now, changed_state)
        with self.assertRaisesRegex(PreparedPackageVerificationError, "fixed-state"):
            verify_prepared_package_readback(
                authorization,
                candidate,
                fixed_mismatch,
                completion=0,
                now=now,
                max_age_seconds=None,
            )

    def test_unexpected_backup_object_set_change_is_rejected(self):
        temporary, root, now, zero_state, candidate, authorization = self._case()
        self.addCleanup(temporary.cleanup)
        post = self._post(root, "unrelated", candidate.candidate_blob, now, zero_state)
        object_path = post / "object-09.bin"
        object_path.write_bytes(b"unexpected")
        manifest_path = post / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["objects"].append(
            {
                "sequence": 9,
                "command": "0x0099",
                "kind": "unexpected",
                "filename": object_path.name,
                "requested_length": len(object_path.read_bytes()),
                "received_length": len(object_path.read_bytes()),
                "sha256": hashlib.sha256(object_path.read_bytes()).hexdigest(),
            }
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(PreparedPackageVerificationError, "object set"):
            verify_prepared_package_readback(
                authorization,
                candidate,
                post,
                completion=0,
                now=now,
                max_age_seconds=None,
            )


if __name__ == "__main__":
    unittest.main()
