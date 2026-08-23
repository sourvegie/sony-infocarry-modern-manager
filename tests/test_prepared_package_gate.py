from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import parse_backup_blob
from infocarry.prepared_package_candidate import build_prepared_package_candidate
from infocarry.prepared_package_gate import (
    PREPARED_PACKAGE_CONFIRMATION_PHRASE,
    PreparedPackageGateError,
    authorize_prepared_package,
    bind_prepared_package_sender,
)
from infocarry.prepared_package import build_prepared_text_package
from infocarry.write_gate import verify_fresh_backup

try:
    from test_new_txt import _write_archive
    from test_prepared_folder import make_folder_fixtures
except ModuleNotFoundError:
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_folder import make_folder_fixtures


class PreparedPackageGateTests(unittest.TestCase):
    def _case(self, *, source_text="A\nB", timestamp=0x6A8ABA6F):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        baseline_blob, template_blob = make_folder_fixtures()
        zero_state = {command: b"\x00" * 64 for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
        now = datetime(2026, 8, 23, tzinfo=timezone.utc)
        backup_path = _write_archive(root / "backup", baseline_blob, now, fixed_state=zero_state)
        source = root / "source.txt"
        source.write_text(source_text, encoding="utf-8")
        package = build_prepared_text_package(source, "Package", "chapter.txt")
        backup = verify_fresh_backup(backup_path, now=now, max_age_seconds=None)
        candidate = build_prepared_package_candidate(
            package,
            backup,
            parse_backup_blob(template_blob),
            new_record_timestamp_be32=timestamp,
            available_capacity_bytes=10_000,
        )
        return temporary, package, backup, candidate, now

    def test_authorization_binds_exact_phrase_and_all_candidate_identity(self):
        temporary, _package, _backup, candidate, now = self._case()
        self.addCleanup(temporary.cleanup)
        authorization = authorize_prepared_package(
            candidate,
            confirmation=PREPARED_PACKAGE_CONFIRMATION_PHRASE,
        )
        self.assertEqual(authorization.folder_path, "root\\Package")
        self.assertEqual(authorization.child_path, "root\\Package\\chapter.txt")
        self.assertEqual(authorization.new_record_timestamp_be32, 0x6A8ABA6F)
        self.assertEqual(authorization.fixed_state_sha256, ("f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b",) * 5)
        self.assertFalse(authorization.to_dict()["usb_transmission_performed"])
        authorization.require_same_candidate(candidate)
        self.assertIsNotNone(authorization.revalidate(candidate, now=now, max_age_seconds=None))

    def test_wrong_phrase_and_cross_timestamp_candidate_are_rejected(self):
        temporary, package, backup, candidate, _now = self._case()
        self.addCleanup(temporary.cleanup)
        with self.assertRaises(PreparedPackageGateError):
            authorize_prepared_package(candidate, confirmation="ADD INFOCARRY TXT")
        other = build_prepared_package_candidate(
            package,
            backup,
            parse_backup_blob(make_folder_fixtures()[1]),
            new_record_timestamp_be32=0x6A8ABA70,
            available_capacity_bytes=10_000,
        )
        authorization = authorize_prepared_package(
            candidate,
            confirmation=PREPARED_PACKAGE_CONFIRMATION_PHRASE,
        )
        with self.assertRaisesRegex(PreparedPackageGateError, "timestamp"):
            authorization.require_same_candidate(other)

    def test_each_audit_binding_mutation_is_rejected(self):
        temporary, _package, _backup, candidate, _now = self._case()
        self.addCleanup(temporary.cleanup)
        authorization = authorize_prepared_package(
            candidate,
            confirmation=PREPARED_PACKAGE_CONFIRMATION_PHRASE,
        )
        mutations = (
            ("baseline_manifest_sha256", "f" * 64),
            ("baseline_blob_sha256", "e" * 64),
            ("source_sha256", "d" * 64),
            ("prepared_manifest_sha256", "c" * 64),
            ("folder_path", "root\\Other"),
            ("child_path", "root\\Package\\other.txt"),
            ("new_record_timestamp_be32", "0x00000001"),
            ("candidate_blob_sha256", "b" * 64),
            ("candidate_transaction_sha256", "a" * 64),
            ("available_capacity_bytes", 1),
            ("complete_candidate_growth_bytes", 1),
            ("capacity_limit_bytes", 1),
            ("baseline_model_bytes", 1),
            ("candidate_model_bytes", 1),
            ("remaining_growth_bytes", 1),
            ("capacity_source", "different-capacity-source"),
        )
        for section, value in mutations:
            with self.subTest(section=section):
                audit = {key: dict(value) if isinstance(value, dict) else value for key, value in candidate.audit.items()}
                if section in {"baseline_manifest_sha256", "baseline_blob_sha256"}:
                    audit["baseline"][section.removeprefix("baseline_")] = value
                elif section == "source_sha256":
                    audit["source"]["sha256"] = value
                elif section == "prepared_manifest_sha256":
                    audit["package"][section] = value
                elif section in {"folder_path", "child_path"}:
                    audit["package"][section] = value
                elif section == "new_record_timestamp_be32":
                    audit["candidate"][section] = value
                elif section == "candidate_blob_sha256":
                    audit["candidate"]["blob_sha256"] = value
                elif section == "candidate_transaction_sha256":
                    audit["transaction"]["sha256"] = value
                else:
                    audit["allocation"][section] = value
                mutated = replace(candidate, audit=audit)
                with self.assertRaises(PreparedPackageGateError):
                    authorization.require_same_candidate(mutated)

    def test_sender_adapter_revalidates_transaction_and_remains_transport_free(self):
        temporary, _package, _backup, candidate, now = self._case()
        self.addCleanup(temporary.cleanup)
        authorization = authorize_prepared_package(
            candidate,
            confirmation=PREPARED_PACKAGE_CONFIRMATION_PHRASE,
        )
        adapter = bind_prepared_package_sender(
            authorization,
            candidate,
            now=now,
            max_age_seconds=None,
        )
        adapter.revalidate(candidate.transaction)
        self.assertFalse(adapter.to_dict()["usb_transmission_performed"])
        altered = replace(candidate.transaction, ranges=tuple(candidate.transaction.ranges[:-1]) + (candidate.transaction.ranges[-1][:-1] + b"\x00",))
        with self.assertRaises(PreparedPackageGateError):
            adapter.revalidate(altered)

    def test_source_mutation_invalidates_revalidation(self):
        temporary, package, _backup, candidate, now = self._case()
        self.addCleanup(temporary.cleanup)
        authorization = authorize_prepared_package(
            candidate,
            confirmation=PREPARED_PACKAGE_CONFIRMATION_PHRASE,
        )
        package.source_path.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(PreparedPackageGateError, "source bytes changed"):
            authorization.revalidate(candidate, now=now, max_age_seconds=None)


if __name__ == "__main__":
    unittest.main()
