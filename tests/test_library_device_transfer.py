import hashlib
from pathlib import Path
import tempfile
import unittest

from infocarry.device_library_semantics import DEVICE_ROOT_PATH, DeviceLibraryNode, DeviceLibrarySnapshot
from infocarry.library import LibraryCatalog
from infocarry.library_device_transfer import (
    CapacityEvidence,
    LibraryDeviceTransferPlanError,
    build_library_device_transfer_plan,
)
from infocarry.prepared_media_package import (
    build_prepared_media_package,
    export_prepared_media_package,
)


def make_profile_bmp() -> bytes:
    width, height = 237, 320
    row_stride = ((width + 31) // 32) * 4
    pixels = bytes(row_stride * height)
    payload = bytearray(62 + len(pixels))
    payload[:2] = b"BM"
    payload[2:6] = len(payload).to_bytes(4, "little")
    payload[10:14] = (62).to_bytes(4, "little")
    payload[14:18] = (40).to_bytes(4, "little")
    payload[18:22] = width.to_bytes(4, "little", signed=True)
    payload[22:26] = height.to_bytes(4, "little", signed=True)
    payload[26:28] = (1).to_bytes(2, "little")
    payload[28:30] = (1).to_bytes(2, "little")
    payload[34:38] = len(pixels).to_bytes(4, "little")
    payload[46:50] = (2).to_bytes(4, "little")
    payload[58:62] = b"\xff\xff\xff\x00"
    payload[62:] = pixels
    return bytes(payload)


def empty_device(*, books: bool = False) -> DeviceLibrarySnapshot:
    nodes = [
        DeviceLibraryNode(DEVICE_ROOT_PATH, "directory", 0, system=True),
    ]
    if books:
        nodes.append(DeviceLibraryNode(("root", "Books"), "directory", 0))
    return DeviceLibrarySnapshot(tuple(nodes))


class LibraryDeviceTransferTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.catalog = LibraryCatalog(self.root / "app" / "library.json")

    def tearDown(self):
        self.temporary.cleanup()

    def _import_package(self, kinds, *, folder_name="Package"):
        sources = []
        for index, kind in enumerate(kinds, start=1):
            source = self.root / "package-sources" / f"source-{index}.{kind}"
            source.parent.mkdir(parents=True, exist_ok=True)
            if kind == "txt":
                source.write_text(f"Page {index}\n", encoding="utf-8")
                name = f"{index:02}-page.txt"
            else:
                source.write_bytes(make_profile_bmp())
                name = f"{index:02}-page.bmp"
            sources.append((source, name))
        prepared = build_prepared_media_package(sources, folder_name)
        package_root = export_prepared_media_package(
            prepared, self.root / f"{folder_name}-archive"
        )
        return self.catalog.import_prepared_package(package_root)

    def test_explicit_prepared_package_is_expanded_only_as_a_host_logical_plan(self):
        item = self._import_package(("txt", "bmp", "txt"))

        plan = build_library_device_transfer_plan(
            self.catalog,
            [item.item_id],
            ("root",),
            empty_device(),
        )

        self.assertEqual(
            [(node.kind, node.file_type, node.destination_path) for node in plan.nodes],
            [
                ("directory", None, ("root", "Package")),
                ("file", "txt", ("root", "Package", "01-page.txt")),
                ("file", "bmp", ("root", "Package", "02-page.bmp")),
                ("file", "txt", ("root", "Package", "03-page.txt")),
            ],
        )
        self.assertEqual(plan.selected_item_ids, (item.item_id,))
        self.assertEqual(plan.expected_delta.removed_paths, ())
        self.assertEqual(
            plan.to_dict()["safety"],
            {
                "candidate_constructed": False,
                "transaction_constructed": False,
                "authorization_created": False,
                "sender_called": False,
                "live_capability_evaluated": False,
            },
        )

    def test_explicit_prepared_packages_of_other_shapes_remain_host_plannable(self):
        for index, kinds in enumerate(
            (("txt", "bmp"), ("txt", "bmp", "txt", "txt", "txt")),
            start=1,
        ):
            with self.subTest(kinds=kinds):
                item = self._import_package(kinds, folder_name=f"Package-{index}")
                plan = build_library_device_transfer_plan(
                    self.catalog,
                    [item.item_id],
                    ("root",),
                    empty_device(),
                )
                self.assertEqual(
                    tuple(node.file_type for node in plan.nodes if node.kind == "file"),
                    kinds,
                )
                self.assertFalse(plan.to_dict()["safety"]["candidate_constructed"])

    def test_prepared_package_manifest_drift_blocks_logical_planning(self):
        item = self._import_package(("txt", "bmp", "txt"))
        manifest_path = Path(item.package.manifest_path)
        manifest_path.write_bytes(manifest_path.read_bytes() + b" ")

        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "revalidated"):
            build_library_device_transfer_plan(
                self.catalog,
                [item.item_id],
                ("root",),
                empty_device(),
            )

    def test_prepared_package_destination_conflict_is_not_overwritten(self):
        item = self._import_package(("txt", "bmp", "txt"))
        snapshot = DeviceLibrarySnapshot(
            (
                DeviceLibraryNode(DEVICE_ROOT_PATH, "directory", 0, system=True),
                DeviceLibraryNode(("root", "Package"), "directory", 0),
            )
        )

        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "conflict"):
            build_library_device_transfer_plan(
                self.catalog,
                [item.item_id],
                ("root",),
                snapshot,
            )

    def test_selected_subtree_preserves_hierarchy_and_destination(self):
        source = self.root / "Novel"
        chapter = source / "Part 01"
        chapter.mkdir(parents=True)
        (chapter / "page.txt").write_bytes(b"first\n")
        (chapter / "image.bmp").write_bytes(make_profile_bmp())
        (source / "opening.txt").write_bytes(b"opening\n")
        root_item = self.catalog.import_folder(source)

        plan = build_library_device_transfer_plan(
            self.catalog,
            [root_item.item_id],
            ("root", "Books"),
            empty_device(books=True),
        )

        paths = [node.destination_path for node in plan.nodes]
        self.assertEqual(
            paths,
            [
                ("root", "Books", "Novel"),
                ("root", "Books", "Novel", "Part 01"),
                ("root", "Books", "Novel", "Part 01", "image.bmp"),
                ("root", "Books", "Novel", "Part 01", "page.txt"),
                ("root", "Books", "Novel", "opening.txt"),
            ],
        )
        self.assertEqual(plan.source_payload_bytes, len(make_profile_bmp()) + len(b"first\n") + len(b"opening\n"))
        self.assertIsNone(plan.candidate_growth_bytes)
        self.assertEqual(plan.capacity_status, "unknown")
        self.assertFalse(plan.to_dict()["safety"]["candidate_constructed"])
        self.assertEqual(plan.expected_delta.removed_paths, ())

    def test_individual_files_keep_explicit_selection_order(self):
        first = self.root / "first.txt"
        second = self.root / "second.txt"
        first.write_bytes(b"1")
        second.write_bytes(b"22")
        first_item = self.catalog.import_file(first)
        second_item = self.catalog.import_file(second)
        plan = build_library_device_transfer_plan(
            self.catalog,
            [second_item.item_id, first_item.item_id],
            ("root",),
            empty_device(),
        )
        self.assertEqual(
            [node.destination_path for node in plan.nodes],
            [("root", "second.txt"), ("root", "first.txt")],
        )
        self.assertEqual([node.sibling_order for node in plan.nodes], [0, 1])
        self.assertEqual(plan.source_payload_bytes, 3)

    def test_catalog_order_survives_reorder_and_reload(self):
        source = self.root / "ordered"
        source.mkdir()
        (source / "alpha.txt").write_text("a", encoding="utf-8")
        (source / "zulu.txt").write_text("z", encoding="utf-8")
        root_item = self.catalog.import_folder(source)
        children = self.catalog.children(root_item.item_id)
        zulu = next(item for item in children if item.source_filename == "zulu.txt")
        self.catalog.move_up(zulu.item_id)

        reloaded = LibraryCatalog(self.catalog.path)
        plan = build_library_device_transfer_plan(
            reloaded,
            [root_item.item_id],
            ("root",),
            empty_device(),
        )
        leaf_names = [node.destination_path[-1] for node in plan.nodes if node.kind == "file"]
        self.assertEqual(leaf_names, ["zulu.txt", "alpha.txt"])

    def test_device_collision_is_rejected_without_overwrite(self):
        source = self.root / "name.txt"
        source.write_bytes(b"body")
        item = self.catalog.import_file(source)
        device = DeviceLibrarySnapshot(
            (
                DeviceLibraryNode(("root",), "directory", 0, system=True),
                DeviceLibraryNode(("root", "name.txt"), "file", 0, "txt", hashlib.sha256(b"old").hexdigest(), 3),
            )
        )
        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "conflict"):
            build_library_device_transfer_plan(self.catalog, [item.item_id], ("root",), device)

    def test_selected_files_with_duplicate_basenames_conflict_deterministically(self):
        selected = []
        for folder_name in ("First", "Second"):
            folder = self.root / folder_name
            folder.mkdir()
            file_path = folder / "shared.txt"
            file_path.write_bytes(folder_name.encode("ascii"))
            folder_item = self.catalog.import_folder(folder)
            selected.append(self.catalog.children(folder_item.item_id)[0].item_id)
        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "conflict"):
            build_library_device_transfer_plan(
                self.catalog, selected, ("root",), empty_device()
            )

    def test_stale_missing_and_changed_folder_references_fail_closed(self):
        changed = self.root / "changed.txt"
        changed.write_bytes(b"before")
        changed_item = self.catalog.import_file(changed)
        changed.write_bytes(b"after!")
        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "changed since import"):
            build_library_device_transfer_plan(self.catalog, [changed_item.item_id], ("root",), empty_device())

        missing = self.root / "missing.txt"
        missing.write_bytes(b"x")
        missing_item = self.catalog.import_file(missing)
        missing.unlink()
        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "missing"):
            build_library_device_transfer_plan(self.catalog, [missing_item.item_id], ("root",), empty_device())

        folder = self.root / "folder"
        folder.mkdir()
        (folder / "inside.txt").write_bytes(b"x")
        folder_item = self.catalog.import_folder(folder)
        (folder / "new.txt").write_bytes(b"new")
        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "contents changed"):
            build_library_device_transfer_plan(self.catalog, [folder_item.item_id], ("root",), empty_device())

    def test_unsupported_type_and_invalid_utf8_are_rejected(self):
        unsupported = self.root / "notes.md"
        unsupported.write_bytes(b"markdown")
        unsupported_item = self.catalog.import_file(unsupported)
        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "unsupported"):
            build_library_device_transfer_plan(self.catalog, [unsupported_item.item_id], ("root",), empty_device())

        invalid = self.root / "invalid.txt"
        invalid.write_bytes(b"\xff\xfe")
        invalid_item = self.catalog.import_file(invalid)
        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "stale, blocked, or unsupported"):
            build_library_device_transfer_plan(self.catalog, [invalid_item.item_id], ("root",), empty_device())

    def test_cp932_component_validation_and_selection_overlap(self):
        non_cp932 = self.root / "🐈.txt"
        non_cp932.write_bytes(b"valid utf-8\n")
        item = self.catalog.import_file(non_cp932)
        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "CP932"):
            build_library_device_transfer_plan(self.catalog, [item.item_id], ("root",), empty_device())

        too_long = self.root / f"{'あ' * 20}.txt"
        too_long.write_bytes(b"valid\n")
        long_item = self.catalog.import_file(too_long)
        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "39-byte"):
            build_library_device_transfer_plan(
                self.catalog, [long_item.item_id], ("root",), empty_device()
            )

        folder = self.root / "tree"
        folder.mkdir()
        child = folder / "leaf.txt"
        child.write_bytes(b"leaf")
        folder_item = self.catalog.import_folder(folder)
        child_item = self.catalog.children(folder_item.item_id)[0]
        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "overlap"):
            build_library_device_transfer_plan(
                self.catalog,
                [folder_item.item_id, child_item.item_id],
                ("root",),
                empty_device(),
            )

    def test_unknown_and_insufficient_capacity_never_clear(self):
        source = self.root / "capacity.txt"
        source.write_bytes(b"1234")
        item = self.catalog.import_file(source)
        unknown = build_library_device_transfer_plan(
            self.catalog, [item.item_id], ("root",), empty_device()
        )
        self.assertEqual(unknown.capacity_status, "unknown")
        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "unknown"):
            unknown.require_capacity_clearance()

        insufficient = build_library_device_transfer_plan(
            self.catalog,
            [item.item_id],
            ("root",),
            empty_device(),
            capacity=CapacityEvidence(candidate_growth_bytes=10, remaining_growth_capacity_bytes=9),
        )
        self.assertEqual(insufficient.capacity_status, "insufficient")
        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "exceeds"):
            insufficient.require_capacity_clearance()

    def test_61_directory_150_mixed_leaf_fixture_persists_plans_and_does_not_mutate_sources(self):
        book = self.root / "Book"
        bmp = make_profile_bmp()
        for section_index in range(10):
            for volume_index in range(5):
                volume = book / f"Section {section_index:02d}" / f"Volume {volume_index:02d}"
                volume.mkdir(parents=True)
                for leaf_index in range(3):
                    if leaf_index % 2 == 0:
                        (volume / f"page-{leaf_index:02d}.txt").write_text(
                            f"section={section_index},volume={volume_index},leaf={leaf_index}\n",
                            encoding="utf-8",
                        )
                    else:
                        (volume / f"image-{leaf_index:02d}.bmp").write_bytes(bmp)

        source_state = {
            path: (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
            for path in book.rglob("*")
            if path.is_file()
        }
        root_item = self.catalog.import_folder(book)
        self.assertEqual(len(self.catalog.items), 61 + 150)
        reloaded = LibraryCatalog(self.catalog.path)
        self.assertEqual(len(reloaded.items), 211)
        catalog_before_plan = reloaded.to_dict()

        plan = build_library_device_transfer_plan(
            reloaded,
            [root_item.item_id],
            ("root", "Books"),
            empty_device(books=True),
        )
        directories = sum(node.kind == "directory" for node in plan.nodes)
        files = [node for node in plan.nodes if node.kind == "file"]
        self.assertEqual(directories, 61)
        self.assertEqual(len(files), 150)
        self.assertEqual(sum(node.file_type == "txt" for node in files), 100)
        self.assertEqual(sum(node.file_type == "bmp" for node in files), 50)
        self.assertEqual(
            plan.source_payload_bytes,
            sum(path.stat().st_size for path in source_state),
        )
        self.assertEqual(plan.capacity_status, "unknown")
        self.assertEqual(len(plan.expected_delta.added_paths), 211)
        self.assertEqual(reloaded.to_dict(), catalog_before_plan)
        self.assertEqual(
            source_state,
            {
                path: (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
                for path in book.rglob("*")
                if path.is_file()
            },
        )


if __name__ == "__main__":
    unittest.main()
