from copy import deepcopy
from dataclasses import replace
import unittest

try:
    import test_prepared_package_multi_candidate as _fixture
except ModuleNotFoundError:
    import tests.test_prepared_package_multi_candidate as _fixture

from infocarry.prepared_multi_package_gate import (
    PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE,
    PreparedMultiPackageAuthorization,
    PreparedMultiPackageGateError,
    authorize_prepared_multi_package,
)


class PreparedMultiPackageGateTests(unittest.TestCase):
    def _candidate(self):
        temporary, package, backup, candidate, template = _fixture.PreparedMultiCandidateTests()._case(mixed=True)
        self.addCleanup(temporary.cleanup)
        return package, backup, candidate, template

    def test_authorization_binds_every_package_identity_and_capacity_value(self):
        _package, _backup, candidate, _template = self._candidate()
        authorization = authorize_prepared_multi_package(
            candidate, confirmation=PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE
        )
        self.assertEqual(authorization.target_kinds, ("directory", "txt", "bmp", "txt"))
        self.assertEqual(len(authorization.target_paths), 4)
        self.assertEqual(len(authorization.target_record_offsets), 4)
        self.assertEqual(authorization.capacity_response_command, 0x0019)
        self.assertEqual(authorization.capacity_response_field_offset, 0x08)
        authorization.require_same_candidate(candidate)
        report = authorization.to_dict()
        self.assertEqual(report["usb_transmission_performed"], False)
        self.assertEqual(report["target_record_offsets"], [f"0x{value:08x}" for value in authorization.target_record_offsets])

    def test_exact_phrase_is_required(self):
        _package, _backup, candidate, _template = self._candidate()
        with self.assertRaisesRegex(PreparedMultiPackageGateError, "confirmation"):
            authorize_prepared_multi_package(candidate, confirmation="ADD ONE INFOCARRY PACKAGE")

    def test_mutating_each_audit_binding_invalidates_authorization(self):
        _package, _backup, candidate, _template = self._candidate()
        authorization = authorize_prepared_multi_package(
            candidate, confirmation=PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE
        )
        mutations = (
            ("baseline", "manifest_sha256", "0" * 64),
            ("baseline", "blob_sha256", "0" * 64),
            ("package", "prepared_manifest_sha256", "0" * 64),
            ("candidate", "blob_sha256", "0" * 64),
            ("candidate", "new_record_timestamp_be32", "0x00000001"),
            ("allocation", "capacity_limit_bytes", 1),
            ("allocation", "baseline_model_bytes", candidate.baseline_model_bytes + 1),
            ("allocation", "candidate_model_bytes", candidate.candidate_model_bytes + 1),
            ("allocation", "remaining_growth_bytes", 1),
            ("capacity_evidence", "raw_response_sha256", "0" * 64),
            ("transaction", "sha256", "0" * 64),
        )
        for section, key, value in mutations:
            with self.subTest(section=section, key=key):
                audit = deepcopy(candidate.audit_dict())
                audit[section][key] = value
                altered = replace(candidate, audit=audit)
                with self.assertRaises(PreparedMultiPackageGateError):
                    authorization.require_same_candidate(altered)

    def test_directly_constructed_authorization_uses_same_validation(self):
        _package, _backup, candidate, _template = self._candidate()
        values = authorize_prepared_multi_package(
            candidate, confirmation=PREPARED_MULTI_PACKAGE_CONFIRMATION_PHRASE
        )
        with self.assertRaisesRegex(PreparedMultiPackageGateError, "digest"):
            PreparedMultiPackageAuthorization(
                **{**values.__dict__, "candidate_blob_sha256": "not-a-digest"}
            )
        with self.assertRaisesRegex(PreparedMultiPackageGateError, "target record"):
            PreparedMultiPackageAuthorization(
                **{**values.__dict__, "target_record_offsets": (1, *values.target_record_offsets[1:])}
            )


if __name__ == "__main__":
    unittest.main()
