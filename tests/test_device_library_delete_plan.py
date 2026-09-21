import hashlib
import unittest

from infocarry.device_library_delete_plan import (
    DeviceLibraryDeletePlanError,
    build_device_library_delete_plan,
    select_device_path,
)
from infocarry.device_library_semantics import (
    DEVICE_ROOT_PATH,
    AuxiliaryStateSnapshot,
    AuxiliaryStateValue,
    DeviceLibraryNode,
    DeviceLibrarySnapshot,
)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def make_snapshot(*, resolved=True, system_file=False, auxiliary_refs=()) -> DeviceLibrarySnapshot:
    values = ()
    if auxiliary_refs:
        values = (AuxiliaryStateValue("opaque-index", digest(b"index"), tuple(auxiliary_refs)),)
    return DeviceLibrarySnapshot(
        (
            DeviceLibraryNode(DEVICE_ROOT_PATH, "directory", 0, system=True),
            DeviceLibraryNode(("root", "Books"), "directory", 0),
            DeviceLibraryNode(("root", "Books", "Shelf"), "directory", 0),
            DeviceLibraryNode(("root", "Books", "Shelf", "one.txt"), "file", 0, "txt", digest(b"one"), 3),
            DeviceLibraryNode(("root", "Books", "Shelf", "two.txt"), "file", 1, "txt", digest(b"two"), 3),
            DeviceLibraryNode(("root", "Books", "keep.txt"), "file", 1, "txt", digest(b"keep"), 4, system_file),
            DeviceLibraryNode(("root", "Other"), "directory", 1),
        ),
        AuxiliaryStateSnapshot(resolved, values),
    )


class DeviceLibraryDeletePlanTests(unittest.TestCase):
    def test_one_file_and_multiple_disjoint_files_plan_exact_removal(self):
        snapshot = make_snapshot()
        one = select_device_path(snapshot, ("root", "Books", "Shelf", "one.txt"))
        single = build_device_library_delete_plan(snapshot, [one])
        self.assertEqual(single.removed_paths, (("root", "Books", "Shelf", "one.txt"),))
        self.assertEqual(single.expected_delta.added_paths, ())
        self.assertFalse(single.to_dict()["safety"]["execution_available"])

        two = select_device_path(snapshot, ("root", "Books", "Shelf", "two.txt"))
        multiple = build_device_library_delete_plan(snapshot, [one, two])
        self.assertEqual(
            set(multiple.removed_paths),
            {
                ("root", "Books", "Shelf", "one.txt"),
                ("root", "Books", "Shelf", "two.txt"),
            },
        )

    def test_subtree_selection_closes_over_nested_descendants_and_preserves_siblings(self):
        snapshot = make_snapshot()
        shelf = select_device_path(snapshot, ("root", "Books", "Shelf"))
        plan = build_device_library_delete_plan(snapshot, [shelf])
        self.assertEqual(
            set(plan.removed_paths),
            {
                ("root", "Books", "Shelf"),
                ("root", "Books", "Shelf", "one.txt"),
                ("root", "Books", "Shelf", "two.txt"),
            },
        )
        after = plan.expected_delta.expected_snapshot()
        self.assertIn(("root", "Books", "keep.txt"), after.node_map)
        self.assertEqual(after.node_map[("root", "Books", "keep.txt")].sibling_order, 0)
        self.assertIn(("root", "Other"), after.node_map)

    def test_duplicate_overlapping_root_and_system_selections_are_rejected(self):
        snapshot = make_snapshot()
        shelf = select_device_path(snapshot, ("root", "Books", "Shelf"))
        leaf = select_device_path(snapshot, ("root", "Books", "Shelf", "one.txt"))
        with self.assertRaisesRegex(DeviceLibraryDeletePlanError, "overlapping"):
            build_device_library_delete_plan(snapshot, [shelf, leaf])
        with self.assertRaisesRegex(DeviceLibraryDeletePlanError, "duplicate"):
            build_device_library_delete_plan(snapshot, [leaf, leaf])

        root = select_device_path(snapshot, DEVICE_ROOT_PATH)
        with self.assertRaisesRegex(DeviceLibraryDeletePlanError, "root"):
            build_device_library_delete_plan(snapshot, [root])

        system_snapshot = make_snapshot(system_file=True)
        protected = select_device_path(system_snapshot, ("root", "Books", "keep.txt"))
        with self.assertRaisesRegex(DeviceLibraryDeletePlanError, "system"):
            build_device_library_delete_plan(system_snapshot, [protected])

    def test_stale_selection_identity_is_rejected(self):
        original = make_snapshot()
        selection = select_device_path(original, ("root", "Books", "Shelf"))
        changed = DeviceLibrarySnapshot(
            tuple(
                DeviceLibraryNode(
                    node.path,
                    node.kind,
                    node.sibling_order,
                    node.file_type,
                    digest(b"changed") if node.path == ("root", "Books", "Shelf", "one.txt") else node.payload_sha256,
                    7 if node.path == ("root", "Books", "Shelf", "one.txt") else node.payload_size_bytes,
                    node.system,
                )
                for node in original.nodes
            ),
            original.auxiliary_state,
        )
        with self.assertRaisesRegex(DeviceLibraryDeletePlanError, "stale"):
            build_device_library_delete_plan(changed, [selection])

    def test_unresolved_or_affected_auxiliary_state_fails_closed(self):
        unresolved = make_snapshot(resolved=False)
        selection = select_device_path(unresolved, ("root", "Books", "Shelf", "one.txt"))
        with self.assertRaisesRegex(DeviceLibraryDeletePlanError, "unresolved"):
            build_device_library_delete_plan(unresolved, [selection])

        referenced = ("root", "Books", "Shelf", "one.txt")
        stateful = make_snapshot(auxiliary_refs=(referenced,))
        selection = select_device_path(stateful, referenced)
        with self.assertRaisesRegex(DeviceLibraryDeletePlanError, "references"):
            build_device_library_delete_plan(stateful, [selection])


if __name__ == "__main__":
    unittest.main()
