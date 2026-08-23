from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import parse_backup_blob
from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.device_info import RawInfoResponse
from infocarry.prepared_package import build_prepared_text_package
from infocarry.prepared_package_candidate import (
    PreparedPackageCandidateError,
    build_prepared_package_candidate,
)
from infocarry.prepared_package_gate import (
    PREPARED_PACKAGE_CONFIRMATION_PHRASE,
    PreparedPackageGateError,
    authorize_prepared_package,
)
from infocarry.write_gate import verify_fresh_backup

try:
    from test_new_txt import _write_archive
    from test_prepared_folder import make_folder_fixtures
except ModuleNotFoundError:
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_folder import make_folder_fixtures


class PreparedPackageNativeCapacityTests(unittest.TestCase):
    def _case(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        baseline_blob, template_blob = make_folder_fixtures()
        state = {command: b"\x00" * 64 for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
        now = datetime(2026, 8, 23, tzinfo=timezone.utc)
        backup_path = _write_archive(root / "backup", baseline_blob, now, fixed_state=state)
        source = root / "source.txt"
        source.write_text("A\nB", encoding="utf-8")
        package = build_prepared_text_package(source, "Package", "chapter.txt")
        backup = verify_fresh_backup(backup_path, now=now, max_age_seconds=None)
        fixture = json.loads(
            (Path(__file__).parent / "fixtures" / "infocarry_info_responses.json").read_text(
                encoding="utf-8"
            )
        )
        raw = bytes.fromhex(fixture["hardware"]["response_hex"])
        response = NativeCapacityResponse.from_hardware_response(
            RawInfoResponse(0x0019, "hardware", raw),
            device_identity=(0x054C, 0x001E),
        )
        candidate = build_prepared_package_candidate(
            package,
            backup,
            parse_backup_blob(template_blob),
            new_record_timestamp_be32=0x6A8ABA6F,
            native_capacity_response=response,
        )
        return temporary, package, backup, candidate, response, now

    def test_native_evidence_is_required_for_live_eligible_authorization(self):
        temporary, _package, _backup, candidate, response, now = self._case()
        self.addCleanup(temporary.cleanup)
        evidence = candidate.native_capacity_evidence
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence.raw_response_sha256, response.raw_response_sha256)
        self.assertEqual(candidate.audit["capacity_evidence"]["response_command"], "0x0019")
        authorization = authorize_prepared_package(
            candidate,
            confirmation=PREPARED_PACKAGE_CONFIRMATION_PHRASE,
            require_native_capacity_evidence=True,
        )
        self.assertTrue(authorization.live_eligible)
        self.assertEqual(authorization.capacity_response_sha256, response.raw_response_sha256)
        authorization.revalidate(candidate, now=now, max_age_seconds=None)

    def test_compatibility_budget_cannot_be_promoted_to_live(self):
        temporary, package, backup, candidate, _response, _now = self._case()
        self.addCleanup(temporary.cleanup)
        compatibility = build_prepared_package_candidate(
            package,
            backup,
            parse_backup_blob(make_folder_fixtures()[1]),
            new_record_timestamp_be32=0x6A8ABA6F,
            available_capacity_bytes=10_000,
        )
        with self.assertRaisesRegex(PreparedPackageGateError, "parsed 0x0019"):
            authorize_prepared_package(
                compatibility,
                confirmation=PREPARED_PACKAGE_CONFIRMATION_PHRASE,
                require_native_capacity_evidence=True,
            )

    def test_capacity_response_audit_mutation_invalidates_authorization(self):
        temporary, _package, _backup, candidate, _response, _now = self._case()
        self.addCleanup(temporary.cleanup)
        authorization = authorize_prepared_package(
            candidate,
            confirmation=PREPARED_PACKAGE_CONFIRMATION_PHRASE,
            require_native_capacity_evidence=True,
        )
        audit = {key: dict(value) if isinstance(value, dict) else value for key, value in candidate.audit.items()}
        audit["capacity_evidence"]["raw_response_sha256"] = "0" * 64
        mutated = replace(candidate, audit=audit)
        with self.assertRaises(PreparedPackageGateError):
            authorization.require_same_candidate(mutated)

    def test_candidate_length_change_invalidates_native_evidence(self):
        temporary, _package, _backup, candidate, _response, _now = self._case()
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(PreparedPackageGateError, "capacity evidence"):
            audit = {key: dict(value) if isinstance(value, dict) else value for key, value in candidate.audit.items()}
            audit["capacity_evidence"]["candidate_model_bytes"] += 1
            authorize_prepared_package(
                replace(candidate, audit=audit),
                confirmation=PREPARED_PACKAGE_CONFIRMATION_PHRASE,
                require_native_capacity_evidence=True,
            )

    def test_wrong_native_capacity_limit_fails_candidate_reconstruction(self):
        temporary, package, backup, candidate, response, _now = self._case()
        self.addCleanup(temporary.cleanup)
        wrong_raw = bytearray(response.raw_response)
        wrong_raw[0x08:0x0C] = (candidate.candidate_model_bytes - 1).to_bytes(4, "big")
        import hashlib
        wrong = NativeCapacityResponse(
            device_identity=response.device_identity,
            raw_response=bytes(wrong_raw),
            raw_response_sha256=hashlib.sha256(bytes(wrong_raw)).hexdigest(),
            response_command=response.response_command,
            field_offset=response.field_offset,
            capacity_limit_bytes=candidate.candidate_model_bytes - 1,
        )
        with self.assertRaisesRegex(PreparedPackageCandidateError, "exceeds"):
            build_prepared_package_candidate(
                package,
                backup,
                parse_backup_blob(make_folder_fixtures()[1]),
                new_record_timestamp_be32=0x6A8ABA6F,
                native_capacity_response=wrong,
            )


if __name__ == "__main__":
    unittest.main()
