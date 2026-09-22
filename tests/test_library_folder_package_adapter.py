"""Host-only regressions for the exact-folder package adapter."""

import hashlib
from pathlib import Path
import tempfile
import unittest

from infocarry.capability_profile import VNW_V15_FOUR_LEAF_PROFILE_ID
from infocarry.device_library_semantics import (
    DEVICE_ROOT_PATH,
    DeviceLibraryNode,
    DeviceLibrarySnapshot,
)
from infocarry.execution_profile import FOUR_LEAF_CHILD_NAMES, FRESH_CHILD_NAMES
from infocarry.library import LibraryCatalog
from infocarry.library_device_transfer import (
    LibraryDeviceTransferPlanError,
    build_library_device_transfer_plan,
)
from infocarry.library_folder_package_adapter import prepare_exact_folder_package
from infocarry.transfer_shape import EXACT_VERIFIED_LIVE_PROFILE, assess_transfer_shape


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


def empty_device() -> DeviceLibrarySnapshot:
    return DeviceLibrarySnapshot(
        (DeviceLibraryNode(DEVICE_ROOT_PATH, "directory", 0, system=True),)
    )


class LibraryFolderPackageAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.catalog_path = self.root / "manager" / "library.json"
        self.catalog = LibraryCatalog(self.catalog_path)
        self.staging = self.root / "manager" / "prepared-content"

    def tearDown(self):
        self.temporary.cleanup()

    def _import_folder(
        self, kinds, *, name="Fresh Folder", nested=False, extra=False, first_text=None
    ):
        folder = self.root / name
        folder.mkdir(parents=True)
        names = (
            FOUR_LEAF_CHILD_NAMES
            if tuple(kinds) == ("txt", "bmp", "txt", "txt")
            else FRESH_CHILD_NAMES
            if tuple(kinds) == ("txt", "bmp", "txt")
            else tuple(f"{index + 1:02}-page.{kind}" for index, kind in enumerate(kinds))
        )
        for index, kind in enumerate(kinds):
            source = folder / names[index]
            if kind == "txt":
                content = (
                    first_text
                    if index == 0 and first_text is not None
                    else f"Page {index + 1}\n日本語\n"
                )
                source.write_text(content, encoding="utf-8")
            else:
                source.write_bytes(make_profile_bmp())
        if extra:
            (folder / "05-extra.txt").write_text("Extra\n", encoding="utf-8")
        if nested:
            child = folder / "nested"
            child.mkdir()
            (child / "nested.txt").write_text("Nested\n", encoding="utf-8")
        item = self.catalog.import_folder(folder)
        return item

    def _plan(self, item, *, snapshot=None):
        return build_library_device_transfer_plan(
            self.catalog,
            [item.item_id],
            ("root",),
            snapshot or empty_device(),
        )

    def test_exact_three_leaf_folder_stages_existing_contract_without_catalog_write(self):
        folder = self._import_folder(("txt", "bmp", "txt"))
        plan = self._plan(
            folder,
            snapshot=DeviceLibrarySnapshot(
                (
                    DeviceLibraryNode(DEVICE_ROOT_PATH, "directory", 0, system=True),
                    DeviceLibraryNode(("root", "Shared"), "directory", 0),
                )
            ),
        )
        self.assertEqual(plan.nodes[0].sibling_order, 1)
        before_catalog = self.catalog_path.read_bytes()
        sources = {
            child.source_path: (
                Path(child.source_path).read_bytes(),
                hashlib.sha256(Path(child.source_path).read_bytes()).hexdigest(),
            )
            for child in self.catalog.children(folder.item_id)
        }

        stage = prepare_exact_folder_package(
            self.catalog, folder, plan, staging_parent=self.staging
        )
        self.assertIsNotNone(stage)
        self.addCleanup(stage.cleanup)
        self.assertEqual(stage.artifact.root_name, "Fresh Folder")
        self.assertEqual(
            tuple((child.kind, child.name) for child in stage.artifact.children),
            tuple(zip(("txt", "bmp", "txt"), FRESH_CHILD_NAMES)),
        )
        self.assertEqual(
            tuple(child.source_sha256 for child in stage.artifact.children),
            tuple(node.source_payload_sha256 for node in plan.nodes[1:]),
        )
        self.assertEqual(
            assess_transfer_shape(stage.artifact).classification,
            EXACT_VERIFIED_LIVE_PROFILE,
        )
        self.assertEqual(self.catalog_path.read_bytes(), before_catalog)
        self.assertEqual(self.catalog.get(folder.item_id).node_kind, "folder")
        for source_path, (payload, digest) in sources.items():
            path = Path(source_path)
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_bytes(), payload)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_exact_four_leaf_folder_preserves_sibling_order_and_target_name(self):
        folder = self._import_folder(
            ("txt", "bmp", "txt", "txt"), name="Four Leaf Book"
        )
        plan = self._plan(folder)
        stage = prepare_exact_folder_package(
            self.catalog, folder, plan, staging_parent=self.staging
        )
        self.assertIsNotNone(stage)
        self.addCleanup(stage.cleanup)
        self.assertEqual(stage.artifact.root_name, "Four Leaf Book")
        self.assertEqual(
            tuple(child.name for child in stage.artifact.children),
            FOUR_LEAF_CHILD_NAMES,
        )
        self.assertEqual(
            tuple(child.order for child in stage.artifact.children),
            tuple(range(len(FOUR_LEAF_CHILD_NAMES))),
        )
        self.assertEqual(
            tuple(child.source_sha256 for child in stage.artifact.children),
            tuple(node.source_payload_sha256 for node in plan.nodes[1:]),
        )

    def test_unsupported_direct_shapes_and_nested_selection_remain_host_only(self):
        cases = (
            (("txt",), False, False),
            (("bmp",), False, False),
            (("txt", "bmp"), False, False),
            (("txt", "bmp", "txt", "txt", "txt"), False, False),
            (("txt", "bmp", "txt"), True, False),
            (("bmp", "txt", "txt"), False, False),
        )
        for index, (kinds, nested, extra) in enumerate(cases, start=1):
            with self.subTest(kinds=kinds, nested=nested):
                folder = self._import_folder(
                    kinds,
                    name=f"Unsupported {index}",
                    nested=nested,
                    extra=extra,
                )
                plan = self._plan(folder)
                self.assertIsNone(
                    prepare_exact_folder_package(
                        self.catalog, folder, plan, staging_parent=self.staging
                    )
                )

    def test_reordered_four_leaf_remains_blocked_even_when_kinds_match(self):
        folder = self._import_folder(("txt", "bmp", "txt", "txt"))
        children = self.catalog.children(folder.item_id)
        fourth = next(child for child in children if child.source_filename == FOUR_LEAF_CHILD_NAMES[3])
        self.catalog.move_up(fourth.item_id)
        reloaded = LibraryCatalog(self.catalog_path)
        folder = reloaded.get(folder.item_id)
        plan = build_library_device_transfer_plan(
            reloaded, [folder.item_id], ("root",), empty_device()
        )
        self.assertEqual(
            tuple(node.file_type for node in plan.nodes if node.kind == "file"),
            ("txt", "bmp", "txt", "txt"),
        )
        self.assertIsNone(
            prepare_exact_folder_package(
                reloaded, folder, plan, staging_parent=self.staging
            )
        )

    def test_existing_device_target_conflict_fails_before_staging(self):
        folder = self._import_folder(("txt", "bmp", "txt"))
        target_present = DeviceLibrarySnapshot(
            (
                DeviceLibraryNode(DEVICE_ROOT_PATH, "directory", 0, system=True),
                DeviceLibraryNode(("root", folder.source_filename), "directory", 0),
            )
        )
        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "conflict"):
            self._plan(folder, snapshot=target_present)
        self.assertFalse(self.staging.exists())

    def test_non_root_destination_remains_host_only(self):
        folder = self._import_folder(("txt", "bmp", "txt"))
        snapshot = DeviceLibrarySnapshot(
            (
                DeviceLibraryNode(DEVICE_ROOT_PATH, "directory", 0, system=True),
                DeviceLibraryNode(("root", "Books"), "directory", 0),
            )
        )
        plan = build_library_device_transfer_plan(
            self.catalog,
            [folder.item_id],
            ("root", "Books"),
            snapshot,
        )
        self.assertIsNone(
            prepare_exact_folder_package(
                self.catalog, folder, plan, staging_parent=self.staging
            )
        )

    def test_source_change_after_host_plan_discards_staging(self):
        folder = self._import_folder(("txt", "bmp", "txt"))
        plan = self._plan(folder)
        first = self.catalog.children(folder.item_id)[0]
        Path(first.source_path).write_bytes(b"changed after planning")
        with self.assertRaisesRegex(ValueError, "changed after planning"):
            prepare_exact_folder_package(
                self.catalog, folder, plan, staging_parent=self.staging
            )
        self.assertFalse(self.staging.exists())

    def test_source_change_after_staging_is_rejected_before_live_preflight(self):
        folder = self._import_folder(("txt", "bmp", "txt"))
        plan = self._plan(folder)
        stage = prepare_exact_folder_package(
            self.catalog, folder, plan, staging_parent=self.staging
        )
        self.assertIsNotNone(stage)
        self.addCleanup(stage.cleanup)
        Path(self.catalog.children(folder.item_id)[0].source_path).write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "changed after planning"):
            stage.verify_source_bindings()

    def test_cp932_substitution_is_not_silently_prepared_for_transfer(self):
        folder = self._import_folder(
            ("txt", "bmp", "txt"),
            first_text="A copied em dash — needs review\n",
        )
        plan = self._plan(folder)

        with self.assertRaisesRegex(ValueError, "will not silently alter"):
            prepare_exact_folder_package(
                self.catalog, folder, plan, staging_parent=self.staging
            )
        self.assertFalse(self.staging.exists())


if __name__ == "__main__":
    unittest.main()
