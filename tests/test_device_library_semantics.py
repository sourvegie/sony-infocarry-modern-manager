import hashlib
import unittest

from infocarry.device_library_semantics import (
    DEVICE_ROOT_PATH,
    AuxiliaryStateSnapshot,
    AuxiliaryStateValue,
    DeviceLibraryNode,
    DeviceLibrarySnapshot,
    DeviceSemanticVerificationError,
    ExpectedDeviceDelta,
    verify_device_library_delta,
)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def baseline() -> DeviceLibrarySnapshot:
    return DeviceLibrarySnapshot(
        (
            DeviceLibraryNode(DEVICE_ROOT_PATH, "directory", 0, system=True),
            DeviceLibraryNode(("root", "Books"), "directory", 0),
            DeviceLibraryNode(("root", "Books", "keep.txt"), "file", 0, "txt", digest(b"keep"), 4),
            DeviceLibraryNode(("root", "Books", "image.bmp"), "file", 1, "bmp", digest(b"bmp"), 3),
            DeviceLibraryNode(("root", "Other"), "directory", 1),
        ),
        AuxiliaryStateSnapshot(
            True,
            (AuxiliaryStateValue("opaque-history", digest(b"history"), (("root", "Other"),)),),
        ),
    )


def expected_delta() -> ExpectedDeviceDelta:
    return ExpectedDeviceDelta(
        baseline(),
        (
            DeviceLibraryNode(("root", "Books", "New Book"), "directory", 2),
            DeviceLibraryNode(
                ("root", "Books", "New Book", "chapter.txt"),
                "file",
                0,
                "txt",
                digest(b"chapter"),
                7,
            ),
        ),
    )


class DeviceLibrarySemanticsTests(unittest.TestCase):
    def test_expected_delta_verifies_hierarchy_order_payload_and_auxiliary_preservation(self):
        expected = expected_delta()
        actual = expected.expected_snapshot()
        report = verify_device_library_delta(expected, actual)
        self.assertEqual(report.expected_added_paths, (
            ("root", "Books", "New Book"),
            ("root", "Books", "New Book", "chapter.txt"),
        ))
        self.assertEqual(report.expected_removed_paths, ())
        self.assertEqual(report.verified_path_count, len(actual.nodes))
        self.assertEqual(report.expected_snapshot_sha256, report.actual_snapshot_sha256)

    def test_missing_and_unexpected_path_deltas_are_rejected(self):
        expected = expected_delta()
        wanted = expected.expected_snapshot()
        missing = DeviceLibrarySnapshot(
            tuple(node for node in wanted.nodes if node.path != ("root", "Books", "New Book", "chapter.txt")),
            wanted.auxiliary_state,
        )
        with self.assertRaisesRegex(DeviceSemanticVerificationError, "missing expected paths"):
            verify_device_library_delta(expected, missing)

        unexpected = DeviceLibrarySnapshot(
            wanted.nodes
            + (DeviceLibraryNode(("root", "Other", "unexpected.txt"), "file", 0, "txt", digest(b"x"), 1),),
            wanted.auxiliary_state,
        )
        with self.assertRaisesRegex(DeviceSemanticVerificationError, "unexpected paths"):
            verify_device_library_delta(expected, unexpected)

    def test_wrong_hierarchy_sibling_order_and_payload_are_rejected(self):
        expected = expected_delta()
        wanted = expected.expected_snapshot()
        nodes = list(wanted.nodes)
        target = ("root", "Books", "New Book", "chapter.txt")

        wrong_parent = tuple(
            DeviceLibraryNode(
                ("root", "Other", "chapter.txt") if node.path == target else node.path,
                node.kind,
                0 if node.path == target else node.sibling_order,
                node.file_type,
                node.payload_sha256,
                node.payload_size_bytes,
                node.system,
            )
            for node in nodes
        )
        with self.assertRaises(DeviceSemanticVerificationError):
            verify_device_library_delta(expected, DeviceLibrarySnapshot(wrong_parent, wanted.auxiliary_state))

        order_changed = tuple(
            DeviceLibraryNode(
                node.path,
                node.kind,
                (
                    1
                    if node.path == ("root", "Books", "New Book")
                    else 2
                    if node.path == ("root", "Books", "image.bmp")
                    else node.sibling_order
                ),
                node.file_type,
                node.payload_sha256,
                node.payload_size_bytes,
                node.system,
            )
            for node in nodes
        )
        with self.assertRaisesRegex(DeviceSemanticVerificationError, "order"):
            verify_device_library_delta(expected, DeviceLibrarySnapshot(order_changed, wanted.auxiliary_state))

        payload_changed = tuple(
            DeviceLibraryNode(
                node.path,
                node.kind,
                node.sibling_order,
                node.file_type,
                digest(b"different") if node.path == target else node.payload_sha256,
                9 if node.path == target else node.payload_size_bytes,
                node.system,
            )
            for node in nodes
        )
        with self.assertRaisesRegex(DeviceSemanticVerificationError, "payload"):
            verify_device_library_delta(expected, DeviceLibrarySnapshot(payload_changed, wanted.auxiliary_state))

    def test_modification_to_unaffected_path_is_detected(self):
        expected = expected_delta()
        wanted = expected.expected_snapshot()
        mutated = tuple(
            DeviceLibraryNode(
                node.path,
                node.kind,
                node.sibling_order,
                node.file_type,
                digest(b"changed keep") if node.path == ("root", "Books", "keep.txt") else node.payload_sha256,
                12 if node.path == ("root", "Books", "keep.txt") else node.payload_size_bytes,
                node.system,
            )
            for node in wanted.nodes
        )
        with self.assertRaisesRegex(DeviceSemanticVerificationError, "unaffected path modified"):
            verify_device_library_delta(expected, DeviceLibrarySnapshot(mutated, wanted.auxiliary_state))

    def test_auxiliary_state_difference_and_unresolved_state_are_rejected(self):
        expected = expected_delta()
        wanted = expected.expected_snapshot()
        changed_aux = AuxiliaryStateSnapshot(
            True,
            (AuxiliaryStateValue("opaque-history", digest(b"new history"), (("root", "Other"),)),),
        )
        with self.assertRaisesRegex(DeviceSemanticVerificationError, "auxiliary-state"):
            verify_device_library_delta(
                expected,
                DeviceLibrarySnapshot(wanted.nodes, changed_aux),
            )

        unresolved_baseline = DeviceLibrarySnapshot(
            expected.baseline.nodes,
            AuxiliaryStateSnapshot(False, expected.baseline.auxiliary_state.values),
        )
        unresolved_expected = ExpectedDeviceDelta(unresolved_baseline, expected.additions)
        with self.assertRaisesRegex(DeviceSemanticVerificationError, "unresolved"):
            verify_device_library_delta(unresolved_expected, unresolved_expected.expected_snapshot())

    def test_unexpected_removal_of_unaffected_path_is_detected(self):
        expected = expected_delta()
        wanted = expected.expected_snapshot()
        removed_nodes = []
        for node in wanted.nodes:
            if node.path == ("root", "Books", "keep.txt"):
                continue
            order = node.sibling_order
            if node.path == ("root", "Books", "image.bmp"):
                order = 0
            elif node.path == ("root", "Books", "New Book"):
                order = 1
            removed_nodes.append(
                DeviceLibraryNode(
                    node.path,
                    node.kind,
                    order,
                    node.file_type,
                    node.payload_sha256,
                    node.payload_size_bytes,
                    node.system,
                )
            )
        removed = DeviceLibrarySnapshot(tuple(removed_nodes), wanted.auxiliary_state)
        with self.assertRaisesRegex(DeviceSemanticVerificationError, "missing expected paths"):
            verify_device_library_delta(expected, removed)

    def test_expected_removal_delta_is_verified_and_extra_removals_fail(self):
        base = baseline()
        image_path = ("root", "Books", "image.bmp")
        expected = ExpectedDeviceDelta(base, removals=(image_path,))
        actual = expected.expected_snapshot()
        report = verify_device_library_delta(expected, actual)
        self.assertEqual(report.expected_removed_paths, (image_path,))

        extra_removed = DeviceLibrarySnapshot(
            tuple(node for node in actual.nodes if node.path != ("root", "Books", "keep.txt")),
            actual.auxiliary_state,
        )
        with self.assertRaisesRegex(DeviceSemanticVerificationError, "missing expected paths"):
            verify_device_library_delta(expected, extra_removed)


if __name__ == "__main__":
    unittest.main()
