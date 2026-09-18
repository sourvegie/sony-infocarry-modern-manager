from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import copy
import inspect
import tempfile
import unittest
from unittest.mock import patch

from infocarry.backup_format import parse_backup_blob, calculate_backup_checksum
from infocarry.capability_profile import (
    FOUR_LEAF_VALIDATION_PROFILE_ID,
    four_leaf_validation_profile,
)
from infocarry.four_leaf_validation import (
    FOUR_LEAF_CHILD_KINDS,
    FOUR_LEAF_CHILD_NAMES,
    FOUR_LEAF_VALIDATION_TARGET,
    FourLeafValidationError,
    authorize_four_leaf_candidate,
    bind_four_leaf_validation_profile,
    build_four_leaf_validation_artifact,
    build_four_leaf_validation_candidate,
    build_four_leaf_validation_foundation,
    build_four_leaf_validation_package,
    derive_four_leaf_operation_id,
    validate_four_leaf_artifact,
    verify_four_leaf_readback,
)
from infocarry.prepared_content import PreparedContentArtifact
from infocarry.library_transfer_readiness import build_library_transfer_readiness
from infocarry.transfer_shape import (
    PLAUSIBLE_FUTURE_DIRECT_LEAF_V15,
    assess_transfer_shape,
)

try:
    from test_new_txt import _write_archive
    from test_prepared_content import _readiness_plan
    import test_prepared_package_multi_candidate as _multi_fixture
    from infocarry.prepared_folder import _replace_name
except ModuleNotFoundError:
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_content import _readiness_plan
    import tests.test_prepared_package_multi_candidate as _multi_fixture
    from infocarry.prepared_folder import _replace_name


class FourLeafValidationTests(unittest.TestCase):
    def _case(self):
        fixture = _multi_fixture.PreparedMultiCandidateTests()
        temporary, _old_package, backup, _old_candidate, template = fixture._case(mixed=True)
        root = Path(temporary.name)
        (root / "one.txt").write_bytes(b"P18-030 introduction leaf.\n")
        (root / "two.txt").write_bytes(b"P18-030 ending leaf.\n")
        (root / "fourth.txt").write_bytes(b"P18-030 extra fourth leaf.\n")
        sources = (
            (root / "one.txt", FOUR_LEAF_CHILD_NAMES[0]),
            (root / "page.bmp", FOUR_LEAF_CHILD_NAMES[1]),
            (root / "two.txt", FOUR_LEAF_CHILD_NAMES[2]),
            (root / "fourth.txt", FOUR_LEAF_CHILD_NAMES[3]),
        )
        package = build_four_leaf_validation_package(sources)
        artifact = build_four_leaf_validation_artifact(sources)
        candidate = build_four_leaf_validation_candidate(
            package,
            backup,
            template,
            new_record_timestamp_be32=0x6A8ABA6F,
            native_capacity_response=fixture._response(),
            template_folder_path=("root", "Template"),
            template_item_paths={
                "txt": ("root", "Template", "chapter"),
                "bmp": ("root", "Template", "page"),
            },
        )
        return fixture, temporary, root, package, artifact, backup, template, candidate

    @staticmethod
    def _post_archive(root, candidate, name="post"):
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        fixed_state = dict(
            zip(
                (0x001B, 0x001C, 0x001D, 0x001E, 0x001F),
                candidate.fixed_state.candidate_raw_blocks,
            )
        )
        return _write_archive(
            root / name,
            candidate.candidate_blob,
            now,
            fixed_state=fixed_state,
        )

    @staticmethod
    def _candidate_with_blob(candidate, blob):
        return replace(
            candidate,
            candidate_blob=blob,
            candidate=parse_backup_blob(blob),
        )

    @staticmethod
    def _rechecksum(blob):
        value = bytearray(blob)
        value[0x1C:0x20] = b"\x00" * 4
        value[0x1C:0x20] = calculate_backup_checksum(bytes(value)).to_bytes(4, "big")
        return bytes(value)

    def test_deterministic_artifact_order_sizes_and_digests(self):
        _fixture, temporary, _root, _package, artifact, *_ = self._case()
        self.addCleanup(temporary.cleanup)
        self.assertEqual(artifact.profile_id, FOUR_LEAF_VALIDATION_PROFILE_ID)
        self.assertEqual(
            [child.kind for child in artifact.children], list(FOUR_LEAF_CHILD_KINDS)
        )
        self.assertEqual(
            [child.name for child in artifact.children], list(FOUR_LEAF_CHILD_NAMES)
        )
        self.assertEqual([child.payload_bytes for child in artifact.children], [28, 10302, 22, 28])
        self.assertEqual(artifact.aggregate_size, 10380)
        self.assertEqual(
            [child.payload_sha256 for child in artifact.children],
            [
                "d1da9961f4668d7ea958616b5dbcdacb2d3a238b0fa98e23c870ff9f023ee865",
                "d3f03cf2b000e38d06825353033fe1f2a64a3e50b58c1b407d4433fffd7a3ccb",
                "d05cfdda174d647638ee7e6cca3417c277eba467c824245c50a73c111b0519a2",
                "509bac0ce28701cf352d971b15119ee8d8e11bb892affb99aacad238ee1123f3",
            ],
        )
        self.assertEqual(
            artifact.artifact_identity,
            "4b1aecada00bed36f1c053385453f75028bfebda6488b2fcbf471409f431c7f8",
        )

    def test_artifact_identity_changes_for_fourth_payload_reorder_and_root(self):
        _fixture, temporary, _root, _package, artifact, *_ = self._case()
        self.addCleanup(temporary.cleanup)
        changed_children = list(artifact.children)
        changed_children[3] = replace(changed_children[3], payload_sha256="f" * 64)
        changed_payload = PreparedContentArtifact(
            artifact.root_name, tuple(changed_children), profile_id="typed-media"
        )
        self.assertNotEqual(artifact.artifact_identity, changed_payload.artifact_identity)

        reordered = tuple(
            replace(child, order=index)
            for index, child in enumerate(reversed(artifact.children))
        )
        reordered_artifact = PreparedContentArtifact(
            artifact.root_name, reordered, profile_id="typed-media"
        )
        self.assertNotEqual(artifact.artifact_identity, reordered_artifact.artifact_identity)

        root_name = "IC_P18_4LEAF_20260918_02"
        root_changed = PreparedContentArtifact(
            root_name,
            tuple(
                replace(
                    child,
                    path=child.path.replace(artifact.root_path, f"root\\{root_name}"),
                )
                for child in artifact.children
            ),
            profile_id="typed-media",
        )
        self.assertNotEqual(artifact.artifact_identity, root_changed.artifact_identity)

    def test_transfer_shape_marks_four_leaf_as_future_only(self):
        _fixture, temporary, _root, _package, artifact, *_ = self._case()
        self.addCleanup(temporary.cleanup)
        assessment = assess_transfer_shape(artifact)
        self.assertEqual(assessment.classification, PLAUSIBLE_FUTURE_DIRECT_LEAF_V15)
        self.assertTrue(assessment.requires_capability_validation)
        self.assertFalse(assessment.to_dict()["candidate_constructed"])
        self.assertFalse(assessment.to_dict()["authorization_created"])

    def test_normal_readiness_blocks_four_leaf_but_three_leaf_remains_eligible(self):
        _fixture, temporary, _root, package, artifact, *_ = self._case()
        self.addCleanup(temporary.cleanup)
        four = build_library_transfer_readiness(_readiness_plan(artifact))
        self.assertTrue(four.blocked)
        self.assertFalse(four.host_profile_eligible)
        self.assertIn("exactly three direct children", " ".join(four.to_dict()["eligibility"]["reasons"]))

        three_artifact = PreparedContentArtifact.from_media_package(
            type("PackageView", (), {"items": package.items[:3], "folder_name": package.folder_name})()
        )
        three = build_library_transfer_readiness(_readiness_plan(three_artifact))
        self.assertFalse(three.blocked)
        self.assertTrue(three.host_profile_eligible)

    def test_exact_profile_accepts_only_four_leaf_order(self):
        profile = four_leaf_validation_profile()
        _fixture, temporary, _root, _package, artifact, *_ = self._case()
        self.addCleanup(temporary.cleanup)
        normalized = profile.validate_package(
            folder_name=artifact.root_name,
            children=artifact.to_legacy_children(),
        )
        self.assertEqual([child["kind"] for child in normalized], list(FOUR_LEAF_CHILD_KINDS))

        cases = {}
        children = artifact.to_legacy_children()
        cases["three"] = children[:3]
        five = copy.deepcopy(children)
        extra = dict(five[-1])
        extra.update({"order": 4, "name": "05-fifth.txt", "path": f"{artifact.root_path}\\05-fifth.txt"})
        five.append(extra)
        cases["five"] = five
        cases["reordered"] = [children[0], children[2], children[1], children[3]]
        nested = copy.deepcopy(children)
        nested[3]["path"] = f"{artifact.root_path}\\nested\\04-extra.txt"
        cases["nested"] = nested
        unsupported = copy.deepcopy(children)
        unsupported[3]["kind"] = "epub"
        cases["unsupported"] = unsupported
        for label, value in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(Exception):
                    profile.validate_package(folder_name=artifact.root_name, children=value)

    def test_profile_bound_foundation_is_host_only_and_preserves_order(self):
        _fixture, temporary, _root, _package, artifact, *_ = self._case()
        self.addCleanup(temporary.cleanup)
        foundation = build_four_leaf_validation_foundation(artifact)
        self.assertEqual(foundation.profile_id, FOUR_LEAF_VALIDATION_PROFILE_ID)
        self.assertFalse(foundation.execute_once.enabled)
        self.assertEqual(
            [node["kind"] for node in foundation.plan.preview()["ordered_nodes"]],
            ["folder", *FOUR_LEAF_CHILD_KINDS],
        )
        self.assertEqual(foundation.to_dict()["device_change"], "none")

    def test_candidate_and_transaction_are_deterministic(self):
        fixture, temporary, _root, package, _artifact, backup, template, candidate = self._case()
        self.addCleanup(temporary.cleanup)
        repeat = build_four_leaf_validation_candidate(
            package,
            backup,
            template,
            new_record_timestamp_be32=0x6A8ABA6F,
            native_capacity_response=fixture._response(),
            template_folder_path=("root", "Template"),
            template_item_paths={
                "txt": ("root", "Template", "chapter"),
                "bmp": ("root", "Template", "page"),
            },
        )
        self.assertEqual(candidate.candidate_blob_sha256, repeat.candidate_blob_sha256)
        self.assertEqual(candidate.transaction_sha256, repeat.transaction_sha256)
        self.assertEqual(derive_four_leaf_operation_id(candidate), derive_four_leaf_operation_id(repeat))

    def test_authorization_binds_exact_profile_operation_and_fresh_evidence(self):
        _fixture, temporary, _root, _package, artifact, _backup, _template, candidate = self._case()
        self.addCleanup(temporary.cleanup)
        authorization = authorize_four_leaf_candidate(candidate)
        self.assertFalse(authorization.execute_once_enabled)
        self.assertEqual(authorization.artifact_identity, artifact.artifact_identity)
        self.assertEqual(authorization.to_dict()["execution_enabled"], False)
        authorization.require_same_candidate(candidate)
        self.assertIsNotNone(
            authorization.revalidate(
                candidate,
                native_capacity_response=_fixture._response(),
                now=datetime(2026, 8, 27, tzinfo=timezone.utc),
                max_age_seconds=None,
            )
        )

        stale_backup_audit = copy.deepcopy(candidate.audit)
        stale_backup_audit["baseline"]["blob_sha256"] = "0" * 64
        stale_backup = replace(candidate, audit=stale_backup_audit)
        with self.assertRaises(FourLeafValidationError):
            authorization.require_same_candidate(stale_backup)

        stale_capacity_audit = copy.deepcopy(candidate.audit)
        stale_capacity_audit["allocation"]["capacity_limit_bytes"] -= 1
        stale_capacity = replace(candidate, audit=stale_capacity_audit)
        with self.assertRaises(FourLeafValidationError):
            authorization.require_same_candidate(stale_capacity)

        stale_candidate = replace(candidate, candidate_blob=candidate.candidate_blob + b"x")
        with self.assertRaises(FourLeafValidationError):
            authorization.require_same_candidate(stale_candidate)

        with patch(
            "infocarry.prepared_multi_package_gate.verify_fresh_backup",
            return_value=replace(candidate.backup, manifest_sha256="f" * 64),
        ):
            with self.assertRaises(FourLeafValidationError):
                authorization.revalidate(
                    candidate,
                    native_capacity_response=_fixture._response(),
                    now=datetime(2026, 8, 27, tzinfo=timezone.utc),
                    max_age_seconds=None,
                )

    def test_independent_verifier_accepts_exact_four_leaf_post_state(self):
        _fixture, temporary, root, _package, artifact, _backup, _template, candidate = self._case()
        self.addCleanup(temporary.cleanup)
        post = self._post_archive(root, candidate)
        result = verify_four_leaf_readback(
            candidate,
            post,
            completion=0,
            now=datetime(2026, 8, 27, tzinfo=timezone.utc),
            max_age_seconds=None,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.artifact_identity, artifact.artifact_identity)
        self.assertEqual(result.to_dict()["details"]["ordered_children_verified"], True)

    def test_independent_verifier_rejects_missing_altered_reordered_and_unexpected(self):
        _fixture, temporary, root, _package, _artifact, _backup, _template, candidate = self._case()
        self.addCleanup(temporary.cleanup)
        original = candidate.candidate_blob
        fourth_offset = next(
            offset
            for offset, path in candidate.candidate.paths.items()
            if path == ("root", FOUR_LEAF_VALIDATION_TARGET, "04-extra")
        )

        renamed = bytearray(original)
        raw = bytearray(candidate.candidate.record_at(fourth_offset).raw_hex.encode())
        raw = bytearray.fromhex(candidate.candidate.record_at(fourth_offset).raw_hex)
        _replace_name(raw, b"missing")
        renamed[fourth_offset : fourth_offset + 0x40] = raw
        missing_candidate = self._candidate_with_blob(candidate, self._rechecksum(bytes(renamed)))

        altered = bytearray(original)
        record = candidate.candidate.record_at(fourth_offset)
        _prefix, payload = candidate.candidate.payload_parts(record)
        payload_offset = candidate.candidate.header.content_start + record.field_04_be32 + len(_prefix)
        altered[payload_offset] ^= 1
        altered_candidate = self._candidate_with_blob(candidate, self._rechecksum(bytes(altered)))

        reordered = bytearray(original)
        page_offset = next(
            offset
            for offset, path in candidate.candidate.paths.items()
            if path == ("root", FOUR_LEAF_VALIDATION_TARGET, "02-page-01")
        )
        ending_offset = next(
            offset
            for offset, path in candidate.candidate.paths.items()
            if path == ("root", FOUR_LEAF_VALIDATION_TARGET, "03-ending")
        )
        page_raw = bytes(reordered[page_offset : page_offset + 0x40])
        ending_raw = bytes(reordered[ending_offset : ending_offset + 0x40])
        reordered[page_offset : page_offset + 0x40] = ending_raw
        reordered[ending_offset : ending_offset + 0x40] = page_raw
        reordered_candidate = self._candidate_with_blob(candidate, self._rechecksum(bytes(reordered)))

        unexpected = bytearray(original)
        raw = bytearray.fromhex(candidate.candidate.record_at(fourth_offset).raw_hex)
        _replace_name(raw, b"05-unexpected")
        unexpected[fourth_offset : fourth_offset + 0x40] = raw
        unexpected_candidate = self._candidate_with_blob(candidate, self._rechecksum(bytes(unexpected)))

        cases = {
            "missing fourth": missing_candidate,
            "altered fourth": altered_candidate,
            "reordered": reordered_candidate,
            "unexpected sibling": unexpected_candidate,
        }
        for label, value in cases.items():
            with self.subTest(label=label):
                post = self._post_archive(root, value, name=f"post-{label.replace(' ', '-')}")
                with self.assertRaises(FourLeafValidationError):
                    verify_four_leaf_readback(
                        value,
                        post,
                        completion=0,
                        now=datetime(2026, 8, 27, tzinfo=timezone.utc),
                        max_age_seconds=None,
                    )

    def test_static_boundary_has_no_second_sender_or_hardware_path(self):
        import infocarry.four_leaf_validation as module

        source = inspect.getsource(module)
        self.assertNotIn("library_transfer_execution", source)
        self.assertNotIn("execution_claim_store", source)
        self.assertNotIn("indeterminate_write_lock", source)
        self.assertNotIn("open_device", source)
        self.assertNotIn("bulk_write", source)


if __name__ == "__main__":
    unittest.main()
