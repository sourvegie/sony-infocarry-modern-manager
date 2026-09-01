import copy
import unittest
from pathlib import Path

from infocarry.capability_profile import (
    CAPABILITY_PROFILE_FORMAT,
    CAPABILITY_PROFILE_STATUS,
    CapabilityProfileError,
    INITIAL_EXPERIMENTAL_PROFILE_ID,
    initial_capability_profile,
    validate_capability_profile,
)


def _child(order, kind, name, *, source_bytes=10, prepared_bytes=12):
    return {
        "order": order,
        "kind": kind,
        "name": name,
        "path": f"root\\Book\\{name}",
        "source_sha256": f"{order + 1:x}" * 64,
        "prepared_payload_sha256": f"{order + 4:x}" * 64,
        "source_bytes": source_bytes,
        "prepared_payload_bytes": prepared_bytes,
    }


class CapabilityProfileTests(unittest.TestCase):
    def test_initial_profile_is_machine_validated_and_not_live_enabled(self):
        profile = initial_capability_profile()
        document = profile.to_dict()

        self.assertEqual(document["format"], CAPABILITY_PROFILE_FORMAT)
        self.assertEqual(profile.profile_id, INITIAL_EXPERIMENTAL_PROFILE_ID)
        self.assertFalse(profile.live_enabled)
        self.assertEqual(document["children"]["minimum"], 1)
        self.assertEqual(document["children"]["maximum"], 8)
        self.assertEqual(validate_capability_profile(document), document)
        self.assertEqual(len(profile.sha256), 64)

    def test_capability_matrix_traces_the_machine_profile(self):
        profile = initial_capability_profile()
        matrix = (
            Path(__file__).resolve().parents[1] / "CAPABILITY_MATRIX.md"
        ).read_text(encoding="utf-8")

        self.assertIn(profile.profile_id, matrix)
        self.assertIn(profile.sha256, matrix)
        self.assertIn(CAPABILITY_PROFILE_STATUS, matrix)

    def test_profile_mutation_is_rejected(self):
        document = initial_capability_profile().to_dict()
        document["operation"]["delete_allowed"] = True

        with self.assertRaises(CapabilityProfileError):
            validate_capability_profile(document)

    def test_exact_flat_txt_bmp_txt_package_is_accepted(self):
        profile = initial_capability_profile()
        children = (
            _child(0, "txt", "01-introduction.txt"),
            _child(1, "bmp", "02-page-01.bmp", source_bytes=10302, prepared_bytes=10302),
            _child(2, "txt", "03-ending.txt"),
        )

        normalized = profile.validate_package(folder_name="Book", children=children)

        self.assertEqual([child["order"] for child in normalized], [0, 1, 2])
        self.assertFalse(profile.live_enabled)

    def test_package_scope_rejects_count_type_nesting_duplicate_and_conflict(self):
        profile = initial_capability_profile()
        base = list(_child(0, "txt", "chapter.txt") for _ in range(9))
        for index, child in enumerate(base):
            child["order"] = index
            child["name"] = f"chapter-{index}.txt"
            child["path"] = f"root\\Book\\chapter-{index}.txt"
        with self.assertRaises(CapabilityProfileError):
            profile.validate_package(folder_name="Book", children=tuple(base))

        nested = _child(0, "txt", "chapter.txt")
        nested["path"] = "root\\Book\\nested\\chapter.txt"
        with self.assertRaises(CapabilityProfileError):
            profile.validate_package(folder_name="Book", children=(nested,))

        duplicate = _child(0, "txt", "chapter.txt")
        duplicate_two = _child(1, "txt", "CHAPTER.txt")
        duplicate_two["path"] = "root\\Book\\CHAPTER.txt"
        with self.assertRaises(CapabilityProfileError):
            profile.validate_package(folder_name="Book", children=(duplicate, duplicate_two))

        unsupported = _child(0, "epub", "chapter.epub")
        with self.assertRaises(CapabilityProfileError):
            profile.validate_package(folder_name="Book", children=(unsupported,))

        with self.assertRaises(CapabilityProfileError):
            profile.validate_package(
                folder_name="Book",
                children=(_child(0, "txt", "chapter.txt"),),
                existing_paths=("root\\Book",),
            )

    def test_package_scope_rejects_size_and_name_policy_overflow(self):
        profile = initial_capability_profile()
        oversized = _child(
            0,
            "txt",
            "chapter.txt",
            source_bytes=1048577,
        )
        with self.assertRaises(CapabilityProfileError):
            profile.validate_package(folder_name="Book", children=(oversized,))

        bad_name = _child(0, "txt", "chapter.one.txt")
        with self.assertRaises(CapabilityProfileError):
            profile.validate_package(folder_name="Book", children=(bad_name,))

        long_folder = "x" * 40
        with self.assertRaises(CapabilityProfileError):
            profile.validate_package(
                folder_name=long_folder,
                children=(_child(0, "txt", "chapter.txt"),),
            )

    def test_package_scope_rejects_boolean_order(self):
        profile = initial_capability_profile()
        child = _child(0, "txt", "chapter.txt")
        child["order"] = True

        with self.assertRaises(CapabilityProfileError):
            profile.validate_package(folder_name="Book", children=(child,))


if __name__ == "__main__":
    unittest.main()
