import unittest

from infocarry.desktop_ttk import _device_library_snapshot_from_inventory
from infocarry.device_library_semantics import DeviceLibrarySemanticError


class DeviceLibraryInventoryAdapterTests(unittest.TestCase):
    def test_preserves_record_order_and_adds_file_extensions_for_logical_paths(self):
        digest = "a" * 64
        inventory = {
            "records": [
                {"path": "root", "kind": "directory"},
                {"path": "root\\Books", "kind": "directory"},
                {
                    "path": "root\\Books\\chapter01",
                    "kind": "file",
                    "extension": "txt",
                    "payload_bytes": 9,
                    "payload_sha256": digest,
                },
                {"path": "root\\Books\\Section", "kind": "directory"},
                {
                    "path": "root\\Books\\Section\\image01",
                    "kind": "file",
                    "extension": "bmp",
                    "payload_bytes": 4,
                    "payload_sha256": digest,
                },
            ]
        }

        snapshot = _device_library_snapshot_from_inventory(inventory)

        self.assertEqual(
            [node.path for node in snapshot.traversal()],
            [
                ("root",),
                ("root", "Books"),
                ("root", "Books", "chapter01.txt"),
                ("root", "Books", "Section"),
                ("root", "Books", "Section", "image01.bmp"),
            ],
        )
        self.assertEqual(
            [node.sibling_order for node in snapshot.children(("root", "Books"))],
            [0, 1],
        )
        self.assertFalse(snapshot.auxiliary_state.resolved)

    def test_unresolved_inventory_nodes_fail_closed(self):
        with self.assertRaisesRegex(DeviceLibrarySemanticError, "unresolved"):
            _device_library_snapshot_from_inventory(
                {
                    "records": [
                        {"path": "root", "kind": "directory"},
                        {"path": "root\\unknown", "kind": "unknown"},
                    ]
                }
            )


if __name__ == "__main__":
    unittest.main()
