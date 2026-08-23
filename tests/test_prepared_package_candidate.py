from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import parse_backup_blob
from infocarry.prepared_folder import build_modern_root_folder_text_candidate
from infocarry.prepared_package import build_prepared_text_package
from infocarry.prepared_package_candidate import (
    PreparedPackageCandidateError,
    build_prepared_package_candidate,
)
from infocarry.write_gate import verify_fresh_backup

try:
    from test_new_txt import _write_archive
    from test_prepared_folder import make_folder_fixtures
except ModuleNotFoundError:
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_folder import make_folder_fixtures


class PreparedPackageCandidateTests(unittest.TestCase):
    def _case(self, *, source_text="A\nB", folder="Package", child="chapter.txt"):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        baseline_blob, template_blob = make_folder_fixtures()
        zero_state = {command: b"\x00" * 64 for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
        now = datetime(2026, 8, 23, tzinfo=timezone.utc)
        backup_path = _write_archive(root / "backup", baseline_blob, now, fixed_state=zero_state)
        source = root / "source.txt"
        source.write_text(source_text, encoding="utf-8")
        package = build_prepared_text_package(source, folder, child)
        backup = verify_fresh_backup(backup_path, now=now, max_age_seconds=None)
        return temporary, package, backup, parse_backup_blob(template_blob), now

    def test_builds_deterministic_candidate_and_exact_capacity_audit(self):
        temporary, package, backup, template, _now = self._case()
        self.addCleanup(temporary.cleanup)
        first = build_prepared_package_candidate(
            package,
            backup,
            template,
            new_record_timestamp_be32=0x6A8ABA6F,
            available_capacity_bytes=10_000,
        )
        second = build_prepared_package_candidate(
            package,
            backup,
            template,
            new_record_timestamp_be32=0x6A8ABA6F,
            available_capacity_bytes=10_000,
        )
        self.assertEqual(first.candidate_blob, second.candidate_blob)
        self.assertEqual(first.transaction.concatenated_sha256, second.transaction.concatenated_sha256)
        self.assertEqual(first.audit_dict(), second.audit_dict())
        allocation = first.audit["allocation"]
        self.assertEqual(
            allocation["complete_candidate_growth_bytes"],
            allocation["metadata_growth_bytes"] + allocation["aligned_content_growth_bytes"],
        )
        self.assertEqual(allocation["capacity_result"], "sufficient")
        self.assertEqual(
            first.audit["candidate"]["added_paths"],
            ["root\\Package", "root\\Package\\chapter.txt"],
        )
        self.assertEqual(first.audit["candidate"]["new_record_timestamp_be32"], "0x6a8aba6f")
        self.assertFalse(first.audit["usb_transmission_performed"])

    def test_rejects_unknown_insufficient_negative_and_inconsistent_capacity(self):
        temporary, package, backup, template, _now = self._case()
        self.addCleanup(temporary.cleanup)
        for capacity, message in ((None, "cannot be established"), (-1, "non-negative"), (0, "exceeds the total capacity")):
            with self.subTest(capacity=capacity):
                with self.assertRaisesRegex(PreparedPackageCandidateError, message):
                    build_prepared_package_candidate(
                        package,
                        backup,
                        template,
                        new_record_timestamp_be32=1,
                        available_capacity_bytes=capacity,
                    )

    def test_total_capacity_exact_boundary_and_one_byte_over(self):
        temporary, package, backup, template, _now = self._case()
        self.addCleanup(temporary.cleanup)
        provisional = build_prepared_package_candidate(
            package,
            backup,
            template,
            new_record_timestamp_be32=1,
            available_capacity_bytes=10_000,
        )
        exact = build_prepared_package_candidate(
            package,
            backup,
            template,
            new_record_timestamp_be32=1,
            capacity_limit_bytes=provisional.candidate_model_bytes,
            baseline_model_bytes=provisional.baseline_model_bytes,
            candidate_model_bytes=provisional.candidate_model_bytes,
            capacity_source="fixture_total_limit",
        )
        self.assertEqual(exact.candidate_model_bytes, exact.capacity_limit_bytes)
        self.assertEqual(
            exact.remaining_growth_bytes,
            exact.candidate_model_bytes - exact.baseline_model_bytes,
        )
        with self.assertRaisesRegex(PreparedPackageCandidateError, "exceeds the total capacity"):
            build_prepared_package_candidate(
                package,
                backup,
                template,
                new_record_timestamp_be32=1,
                capacity_limit_bytes=provisional.candidate_model_bytes - 1,
                baseline_model_bytes=provisional.baseline_model_bytes,
                candidate_model_bytes=provisional.candidate_model_bytes,
                capacity_source="fixture_total_limit",
            )

    def test_total_capacity_rejects_inconsistent_model_lengths_and_missing_evidence(self):
        temporary, package, backup, template, _now = self._case()
        self.addCleanup(temporary.cleanup)
        baseline_length = len(backup.directory.joinpath(backup.object_filename("0x8004:backup-blob")).read_bytes())
        with self.assertRaisesRegex(PreparedPackageCandidateError, "baseline model length"):
            build_prepared_package_candidate(
                package,
                backup,
                template,
                new_record_timestamp_be32=1,
                capacity_limit_bytes=baseline_length + 1_000,
                baseline_model_bytes=baseline_length + 1,
                capacity_source="fixture_total_limit",
            )
        with self.assertRaisesRegex(PreparedPackageCandidateError, "candidate model length"):
            build_prepared_package_candidate(
                package,
                backup,
                template,
                new_record_timestamp_be32=1,
                capacity_limit_bytes=baseline_length + 1_000,
                candidate_model_bytes=baseline_length,
                capacity_source="fixture_total_limit",
            )
        with self.assertRaisesRegex(PreparedPackageCandidateError, "capacity"):
            build_prepared_package_candidate(
                package,
                backup,
                template,
                new_record_timestamp_be32=1,
                capacity_limit_bytes=None,
                baseline_model_bytes=baseline_length,
                capacity_source="fixture_total_limit",
            )

    def test_rejects_folder_or_child_conflict_case_insensitively(self):
        temporary, package, backup, template, _now = self._case(folder="OLD", child="chapter.txt")
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(PreparedPackageCandidateError, "conflicts"):
            build_prepared_package_candidate(
                package,
                backup,
                template,
                new_record_timestamp_be32=1,
                available_capacity_bytes=10_000,
            )

    def test_rejects_changed_source_after_preview(self):
        temporary, package, backup, template, _now = self._case()
        self.addCleanup(temporary.cleanup)
        package.source_path.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(PreparedPackageCandidateError, "source changed"):
            build_prepared_package_candidate(
                package,
                backup,
                template,
                new_record_timestamp_be32=1,
                available_capacity_bytes=10_000,
            )

    def test_rejects_non_capture7_fixed_state_before_candidate_authorization(self):
        temporary, package, backup, template, now = self._case()
        self.addCleanup(temporary.cleanup)
        state = bytearray((backup.directory / backup.object_filename("0x001b:response-001b")).read_bytes())
        state[4] = 1
        path = backup.directory / backup.object_filename("0x001b:response-001b")
        path.write_bytes(state)
        # Recreate a valid manifest hash for the changed object, then verify it
        # as a fresh independent archive. The preflight must still reject it.
        import hashlib
        import json

        manifest_path = backup.directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest["objects"]:
            if entry["kind"] == "response-001b":
                entry["sha256"] = hashlib.sha256(bytes(state)).hexdigest()
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        changed_backup = verify_fresh_backup(backup.directory, now=now, max_age_seconds=None)
        with self.assertRaisesRegex(PreparedPackageCandidateError, "fixed-state"):
            build_prepared_package_candidate(
                package,
                changed_backup,
                template,
                new_record_timestamp_be32=1,
                available_capacity_bytes=10_000,
            )


if __name__ == "__main__":
    unittest.main()
