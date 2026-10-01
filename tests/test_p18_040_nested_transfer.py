"""Host-only nested source, candidate, and independent readback fixtures."""

from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import hashlib
import json

from infocarry.backup_format import parse_backup_blob
from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.device_info import RawInfoResponse
from infocarry.desktop import DesktopWorkflowModel
from infocarry.desktop_ttk import refresh_device_library_from_verified_transfer
from infocarry.device_library_semantics import DeviceLibraryNode, DeviceLibrarySnapshot
from infocarry.library import LibraryCatalog
from infocarry.library_device_transfer import LibraryDeviceTransferPlanError, build_library_device_transfer_plan
from infocarry.library_folder_package_adapter import LibraryFolderPackageAdapterError, prepare_nested_folder_package
from infocarry.library_prepare import prepare_library_hierarchy
from infocarry.capability_profile import NESTED_HOST_PROFILE_ID
from infocarry.library_transfer_plan import build_library_transfer_queue_plan, SELECTION_SELECTED
from infocarry.library_transfer_readiness import build_library_transfer_readiness
from infocarry.prepared_library_package_bridge import build_prepared_library_package_candidate
import infocarry.prepared_library_package_bridge as bridge_module
import infocarry.prepared_package_multi_candidate as candidate_module
from infocarry.prepared_hierarchy_source import load_prepared_hierarchy_source
from infocarry.prepared_package_multi_candidate import build_prepared_multi_package_candidate
from infocarry.prepared_multi_package_gate import authorize_prepared_multi_package
from infocarry.prepared_multi_package_gate import PreparedMultiPackageGateError
from infocarry.prepared_package_multi_candidate import PreparedMultiCandidateError
from infocarry.write_protocol import REQUEST_BEGIN_TRANSMIT
from infocarry.prepared_package_multi_verify import verify_prepared_multi_package_readback
from infocarry.write_gate import verify_fresh_backup

try:
    from test_library_device_transfer import empty_device, make_profile_bmp
    from test_new_txt import _write_archive
    from test_prepared_package_multi_candidate import _blob, _template_blobs
    from test_prepared_library_package_bridge import _response, _native_named_template_blob
    from test_backup_format import make_record
except ModuleNotFoundError:
    from tests.test_library_device_transfer import empty_device, make_profile_bmp
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_package_multi_candidate import _blob, _template_blobs
    from tests.test_prepared_library_package_bridge import _response, _native_named_template_blob
    from tests.test_backup_format import make_record


def small_nested_fixture(parent: Path) -> Path:
    root = parent / "IC_P18_040_NESTED_TEST"
    (root / "Section-A").mkdir(parents=True)
    (root / "Section-B" / "Detail").mkdir(parents=True)
    for name in (
        "01-intro.txt", "Section-A/03-notes.txt", "Section-B/Detail/05-ending.txt"
    ):
        (root / name).write_text(f"{name}\n", encoding="utf-8")
    for name in ("Section-A/02-page.bmp", "Section-B/Detail/04-page.bmp"):
        (root / name).write_bytes(make_profile_bmp())
    return root


class NestedTransferHostTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = small_nested_fixture(self.root)
        self.catalog = LibraryCatalog(self.root / "catalog.json")
        self.item = self.catalog.import_folder(self.source)
        self.plan = build_library_device_transfer_plan(
            self.catalog, [self.item.item_id], ("root",), empty_device()
        )
        self.stage = prepare_nested_folder_package(self.catalog, self.item, self.plan)
        assert self.stage is not None

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _candidate(self, *, capacity=None):
        self.stage.materialize_operation_artifact(self.root / "operation")
        package = load_prepared_hierarchy_source(self.stage.operation_owned_root)
        baseline_blob, template_blob = _template_blobs()
        fixed = {command: b"\x00" * 64 for command in range(0x001B, 0x0020)}
        before = _write_archive(
            self.root / "before", baseline_blob, datetime.now(timezone.utc), fixed_state=fixed
        )
        backup = verify_fresh_backup(before, max_age_seconds=None)
        candidate = build_prepared_multi_package_candidate(
            package, backup, parse_backup_blob(template_blob),
            new_record_timestamp_be32=0x6A942500,
            native_capacity_response=capacity or _response(),
            template_folder_path=("root", "Template"),
            template_item_paths={
                "txt": ("root", "Template", "chapter"),
                "bmp": ("root", "Template", "page"),
            },
        )
        return candidate, fixed

    def _fresh_artifact(self):
        catalog = LibraryCatalog(self.root / f"catalog-{len(list(self.root.glob('catalog-*')))}.json")
        item = catalog.import_folder(self.source)
        return prepare_library_hierarchy(catalog, item.item_id, profile_id=NESTED_HOST_PROFILE_ID).artifact

    def _sealed_fake_preflight(self, *, backend=None):
        try:
            from test_library_transfer_execution import LibraryTransferExecutionFacadeTests
        except ModuleNotFoundError:
            from tests.test_library_transfer_execution import LibraryTransferExecutionFacadeTests
        setup = LibraryTransferExecutionFacadeTests()._setup(
            include_operation_binding=False, backend=backend
        )
        self.addCleanup(setup["temporary"].cleanup)
        offline = build_library_transfer_queue_plan(
            self.stage.catalog, selection_mode=SELECTION_SELECTED,
            selected_item_ids=[self.item.item_id], backup=setup["baseline"],
            available_capacity_bytes=10_000_000,
        ).to_dict()
        digest = hashlib.sha256(setup["template"].data).hexdigest()
        for module, name in (
            (bridge_module, "P17_003_REVIEWED_TEMPLATE_BLOB_SHA256"),
            (candidate_module, "REVIEWED_TEMPLATE_SUBSET_POLICY_SHA256"),
        ):
            template_patch = patch.object(module, name, digest)
            template_patch.start()
            self.addCleanup(template_patch.stop)
        prepared = setup["facade"].refresh_live_preflight(
            offline, catalog=self.stage.catalog,
            preflight_report_path=setup["root"] / "nested-operation" / "sealed-preflight.json",
            bundle_path=setup["root"] / "nested-operation" / "operation-bundle.json",
            operation_stage=self.stage,
        )
        setup["candidate_holder"]["candidate"] = prepared.preflight.candidate
        return setup, prepared

    def _assert_no_sender_or_claim(self, setup):
        self.assertEqual(setup["backend"].calls, [])
        self.assertIsNone(setup["claim_store"].read_sender_in_flight())
        self.assertIsNone(setup["lock"].read())
        connection = sqlite3.connect(setup["claim_store"].path)
        try:
            self.assertEqual(connection.execute("SELECT count(*) FROM execution_claims").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT count(*) FROM sender_in_flight").fetchone()[0], 0)
        finally:
            connection.close()

    def test_nested_root_appends_after_22_existing_siblings_without_rebasing_children(self):
        baseline = DeviceLibrarySnapshot((
            *empty_device().nodes,
            *(DeviceLibraryNode(("root", f"Existing-{index:02}"), "directory", index)
              for index in range(22)),
        ))
        plan = build_library_device_transfer_plan(
            self.catalog, [self.item.item_id], ("root",), baseline
        )
        self.assertEqual(plan.nodes[0].sibling_order, 22)
        stage = prepare_nested_folder_package(self.catalog, self.item, plan)
        self.assertIsNotNone(stage)
        hierarchy = prepare_library_hierarchy(
            self.catalog, self.item.item_id, profile_id=NESTED_HOST_PROFILE_ID
        )
        self.assertEqual(hierarchy.nodes[0]["order"], 0)
        self.assertEqual(
            tuple((node.path, node.sibling_order) for node in plan.expected_delta.additions),
            tuple((node.destination_path, node.sibling_order) for node in plan.nodes),
        )
        self.assertEqual(
            tuple(node.sibling_order for node in plan.nodes[1:]),
            tuple(node["order"] for node in hierarchy.nodes[1:]),
        )
        self.assertEqual(
            tuple(node.path[-1] for node in plan.expected_delta.expected_snapshot().children(("root",))),
            (*tuple(f"Existing-{index:02}" for index in range(22)), self.item.source_filename),
        )

    def test_nested_plan_rejects_stale_root_and_internal_order(self):
        baseline = DeviceLibrarySnapshot((
            *empty_device().nodes,
            DeviceLibraryNode(("root", "Existing"), "directory", 0),
        ))
        plan = build_library_device_transfer_plan(
            self.catalog, [self.item.item_id], ("root",), baseline
        )
        for index, wrong_order in ((0, 0), (1, 1)):
            changed = list(plan.nodes)
            changed[index] = replace(changed[index], sibling_order=wrong_order)
            with self.subTest(index=index), self.assertRaises(LibraryFolderPackageAdapterError):
                prepare_nested_folder_package(
                    self.catalog, self.item, replace(plan, nodes=tuple(changed))
                )
        changed = list(plan.nodes)
        changed[1] = replace(changed[1], sibling_order=1)
        with self.assertRaises(ValueError):
            replace(plan.expected_delta, additions=tuple(
                replace(node, sibling_order=1) if index == 1 else node
                for index, node in enumerate(plan.expected_delta.additions)
            ))

    def test_existing_target_rejects_before_nested_preparation(self):
        baseline = DeviceLibrarySnapshot((
            *empty_device().nodes,
            DeviceLibraryNode(("root", self.item.source_filename), "directory", 0),
        ))
        with self.assertRaisesRegex(LibraryDeviceTransferPlanError, "destination conflict"):
            build_library_device_transfer_plan(
                self.catalog, [self.item.item_id], ("root",), baseline
            )

    def test_exact_small_candidate_and_independent_readback(self):
        candidate, fixed = self._candidate()
        self.assertEqual(len(candidate.audit["package"]["paths"]), 9)
        self.assertEqual(candidate.audit["allocation"]["source_bytes"], sum(
            len(item.source_bytes) for item in candidate.package.items
        ))
        self.assertEqual(candidate.audit["allocation"]["candidate_model_bytes"], len(candidate.candidate_blob))
        authorization = authorize_prepared_multi_package(
            candidate, confirmation="ADD ONE INFOCARRY MULTI-CHILD PACKAGE"
        )
        authorization.revalidate(candidate, max_age_seconds=None)
        after = _write_archive(
            self.root / "after", candidate.candidate_blob,
            datetime.now(timezone.utc), fixed_state=fixed,
        )
        result = verify_prepared_multi_package_readback(
            candidate, after, completion=0, max_age_seconds=None
        )
        self.assertEqual(len(result.details["added_paths"]), 9)
        self.assertEqual(result.details["removed_paths"], [])

    def test_existing_nested_library_and_payload_survive_new_nested_root(self):
        self.stage.materialize_operation_artifact(self.root / "operation")
        package = load_prepared_hierarchy_source(self.stage.operation_owned_root)
        _unused, template_blob = _template_blobs()
        template = parse_backup_blob(template_blob)
        template_content = template.data[
            template.header.content_start:template.header.content_start + template.header.content_length
        ]
        old = template.record_at(0xC0)
        chapter = template.record_at(0x180)
        page = template.record_at(0x1C0)
        existing_payload = b"existing nested\r\n"
        existing_segment = b"\xff" * 32 + existing_payload
        existing_segment += b"\xff" * (-len(existing_segment) % 4)
        records = b"".join((
            make_record(0xD0, "", 0x40, 0x100, "root"),
            make_record(0xD0, "", 0x00, 0x100, ".."),
            bytes.fromhex(old.raw_hex),
            make_record(0xD0, "", 0x180, 0xC0, "Template"),
            make_record(0xD0, "", 0x280, 0x80, "Existing"),
            make_record(0xD0, "", 0x40, 0x100, ".."),
            make_record(0xD0, "", 0x40, 0x100, ".."),
            bytes.fromhex(chapter.raw_hex),
            bytes.fromhex(page.raw_hex),
            make_record(0xD0, "", 0x100, 0xC0, ".."),
            make_record(0xD0, "", 0x40, 0x140, ".."),
            make_record(0xE0, "txt", len(template_content), len(existing_payload), "source", 0x200),
            make_record(0xD0, "", 0x140, 0x80, ".."),
        ))
        baseline_blob = _blob(records, template_content + existing_segment)
        baseline = parse_backup_blob(baseline_blob)
        self.assertIn(("root", "Existing", "source"), baseline.paths.values())
        fixed = {command: b"\x00" * 64 for command in range(0x001B, 0x0020)}
        before = _write_archive(
            self.root / "nested-before", baseline_blob, datetime.now(timezone.utc), fixed_state=fixed
        )
        digest = hashlib.sha256(template_blob).hexdigest()
        with patch.object(candidate_module, "REVIEWED_TEMPLATE_SUBSET_POLICY_SHA256", digest):
            candidate = build_prepared_multi_package_candidate(
                package, verify_fresh_backup(before, max_age_seconds=None), template,
                new_record_timestamp_be32=0x6A942500,
                native_capacity_response=_response(),
                template_folder_path=("root", "Template"),
                template_item_paths={
                    "txt": ("root", "Template", "chapter"),
                    "bmp": ("root", "Template", "page"),
                },
                template_subset_policy_sha256=digest,
            )
        after = _write_archive(
            self.root / "nested-after", candidate.candidate_blob,
            datetime.now(timezone.utc), fixed_state=fixed,
        )
        result = verify_prepared_multi_package_readback(
            candidate, after, completion=0, max_age_seconds=None
        )
        self.assertEqual(result.details["removed_paths"], [])
        self.assertEqual(len(result.details["added_paths"]), 9)
        self.assertIn(("root", "Existing", "source"), candidate.candidate.paths.values())

    def test_operation_owned_copy_survives_original_source_removal(self):
        candidate, _fixed = self._candidate()
        shutil.rmtree(self.source)
        loaded = load_prepared_hierarchy_source(self.stage.operation_owned_root)
        self.assertEqual(loaded.artifact.artifact_identity, candidate.package.artifact.artifact_identity)
        authorization = authorize_prepared_multi_package(
            candidate, confirmation="ADD ONE INFOCARRY MULTI-CHILD PACKAGE"
        )
        authorization.revalidate(candidate, max_age_seconds=None)

    def test_source_drift_and_missing_source_stop_before_staging(self):
        source_leaf = self.source / "Section-A" / "03-notes.txt"
        source_leaf.write_text("changed after plan\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.stage.verify_source_bindings()
        source_leaf.unlink()
        with self.assertRaisesRegex(ValueError, "changed"):
            self.stage.materialize_operation_artifact(self.root / "missing-source")

    def test_missing_operation_owned_payload_invalidates_authorization(self):
        candidate, _fixed = self._candidate()
        authorization = authorize_prepared_multi_package(
            candidate, confirmation="ADD ONE INFOCARRY MULTI-CHILD PACKAGE"
        )
        (self.stage.operation_owned_root / "prepared" / "Section-A" / "03-notes.txt").unlink()
        with self.assertRaises(PreparedMultiPackageGateError):
            authorization.revalidate(candidate, max_age_seconds=None)

    def test_tree_identity_changes_for_bytes_order_name_move_type_and_removal(self):
        original = self.stage.artifact.artifact_identity
        source_leaf = self.source / "Section-A" / "03-notes.txt"
        source_leaf.write_text("changed bytes\n", encoding="utf-8")
        self.assertNotEqual(original, self._fresh_artifact().artifact_identity)
        source_leaf.write_text("Section-A/03-notes.txt\n", encoding="utf-8")
        reimport = LibraryCatalog(self.root / "reorder-catalog.json")
        reordered_root = reimport.import_folder(self.source)
        first = reimport.children(reordered_root.item_id)[0]
        reimport.move_to(first.item_id, 2)
        self.assertNotEqual(original, prepare_library_hierarchy(
            reimport, reordered_root.item_id, profile_id=NESTED_HOST_PROFILE_ID
        ).artifact.artifact_identity)
        source_leaf.rename(self.source / "Section-A" / "03-renamed.txt")
        self.assertNotEqual(original, self._fresh_artifact().artifact_identity)
        (self.source / "Section-A" / "03-renamed.txt").rename(source_leaf)
        moved = self.source / "Section-B" / "Detail" / "03-notes.txt"
        shutil.move(source_leaf, moved)
        self.assertNotEqual(original, self._fresh_artifact().artifact_identity)
        shutil.move(moved, source_leaf)
        source_leaf.unlink()
        self.assertNotEqual(original, self._fresh_artifact().artifact_identity)

    def test_invalid_name_and_component_limit_fail_closed(self):
        (self.source / "Section-A" / "bad-😊.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError):
            self._fresh_artifact()
        (self.source / "Section-A" / "bad-😊.txt").unlink()
        (self.source / "Section-A" / ("x" * 40 + ".txt")).write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError):
            self._fresh_artifact()

    def test_duplicate_sibling_and_unsupported_deep_path_fail_closed(self):
        catalog = LibraryCatalog(self.root / "duplicate-catalog.json")
        root = catalog.import_folder(self.source)
        section = next(item for item in catalog.children(root.item_id) if item.source_filename == "Section-A")
        siblings = catalog.children(section.item_id)
        catalog._items[siblings[1].item_id] = replace(
            siblings[1], source_filename=siblings[0].source_filename
        )
        with self.assertRaises(ValueError):
            prepare_library_hierarchy(catalog, root.item_id, profile_id=NESTED_HOST_PROFILE_ID)
        deep = self.source / "Section-B" / "Detail" / "Deep-1" / "Deep-2"
        deep.mkdir(parents=True)
        (deep / "06-deep.txt").write_text("too deep\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self._fresh_artifact()

    def test_native_extension_projection_collision_fails_closed(self):
        (self.source / "Section-A" / "03-notes.bmp").write_bytes(make_profile_bmp())
        with self.assertRaisesRegex(ValueError, "native extension projection"):
            self._fresh_artifact()

    def test_added_child_and_txt_bmp_type_change_change_identity(self):
        original = self.stage.artifact.artifact_identity
        added = self.source / "Section-A" / "06-added.txt"
        added.write_text("added\n", encoding="utf-8")
        self.assertNotEqual(original, self._fresh_artifact().artifact_identity)
        added.unlink()
        original_text = self.source / "Section-A" / "03-notes.txt"
        original_text.unlink()
        (self.source / "Section-A" / "03-notes.bmp").write_bytes(make_profile_bmp())
        self.assertNotEqual(original, self._fresh_artifact().artifact_identity)

    def test_insufficient_native_capacity_rejects_candidate(self):
        raw = bytearray(_response().raw_response)
        raw[8:12] = (1).to_bytes(4, "big")
        capacity = NativeCapacityResponse.from_hardware_response(
            RawInfoResponse(0x0019, "nested-capacity-test", bytes(raw)),
            device_identity=(0x054C, 0x001E),
        )
        with self.assertRaises(PreparedMultiCandidateError):
            self._candidate(capacity=capacity)

    def test_existing_target_root_rejects_add_without_merge(self):
        target = self.root / "Template"
        shutil.copytree(self.source, target)
        catalog = LibraryCatalog(self.root / "conflict-catalog.json")
        item = catalog.import_folder(target)
        plan = build_library_device_transfer_plan(
            catalog, [item.item_id], ("root",), empty_device()
        )
        stage = prepare_nested_folder_package(catalog, item, plan)
        self.assertIsNotNone(stage)
        stage.materialize_operation_artifact(self.root / "conflict-operation")
        package = load_prepared_hierarchy_source(stage.operation_owned_root)
        _baseline_blob, template_blob = _template_blobs()
        fixed = {command: b"\x00" * 64 for command in range(0x001B, 0x0020)}
        before = _write_archive(
            self.root / "conflict-before", template_blob,
            datetime.now(timezone.utc), fixed_state=fixed,
        )
        backup = verify_fresh_backup(before, max_age_seconds=None)
        with self.assertRaises(PreparedMultiCandidateError):
            build_prepared_multi_package_candidate(
                package, backup, parse_backup_blob(template_blob),
                new_record_timestamp_be32=0x6A942500,
                native_capacity_response=_response(),
                template_folder_path=("root", "Template"),
                template_item_paths={
                    "txt": ("root", "Template", "chapter"),
                    "bmp": ("root", "Template", "page"),
                },
            )

    def test_candidate_and_transaction_tampering_are_rejected(self):
        candidate, _fixed = self._candidate()
        authorization = authorize_prepared_multi_package(
            candidate, confirmation="ADD ONE INFOCARRY MULTI-CHILD PACKAGE"
        )
        with self.assertRaises(PreparedMultiPackageGateError):
            authorization.require_same_candidate(replace(candidate, candidate_blob=b"tampered"))
        original_ranges = candidate.transaction.ranges
        tampered_transaction = replace(
            candidate.transaction,
            ranges=(bytes([original_ranges[0][0] ^ 1]) + original_ranges[0][1:], *original_ranges[1:]),
        )
        with self.assertRaises(PreparedMultiPackageGateError):
            authorization.require_same_candidate(replace(candidate, transaction=tampered_transaction))

    def test_existing_queue_readiness_and_bridge_accept_nested_stage(self):
        offline_plan = build_library_transfer_queue_plan(
            self.stage.catalog, selection_mode=SELECTION_SELECTED,
            selected_item_ids=[self.item.item_id],
        )
        self.assertTrue(build_library_transfer_readiness(offline_plan.to_dict()).host_profile_eligible)
        stable = self.stage.materialize_operation_artifact(self.root / "operation")
        plan = build_library_transfer_queue_plan(
            stable, selection_mode=SELECTION_SELECTED,
            selected_item_ids=[self.item.item_id],
        )
        readiness = build_library_transfer_readiness(plan.to_dict())
        self.assertTrue(readiness.report["eligibility"]["host_profile_eligible"], readiness.report["eligibility"])
        baseline_blob, _ = _template_blobs()
        fixed = {command: b"\x00" * 64 for command in range(0x001B, 0x0020)}
        before = _write_archive(self.root / "before", baseline_blob, datetime.now(timezone.utc), fixed_state=fixed)
        backup = verify_fresh_backup(before, max_age_seconds=None)
        template = parse_backup_blob(_native_named_template_blob())
        digest = hashlib.sha256(template.data).hexdigest()
        with patch.object(bridge_module, "P17_003_REVIEWED_TEMPLATE_BLOB_SHA256", digest), patch.object(
            candidate_module, "REVIEWED_TEMPLATE_SUBSET_POLICY_SHA256", digest
        ):
            candidate = build_prepared_library_package_candidate(
                stable, self.item.item_id, backup, template,
                new_record_timestamp_be32=0x6A942500,
                native_capacity_response=_response(),
                profile_id="host-reviewed-nested-root-folder-txt-bmp-v1",
            )
        self.assertEqual(len(candidate.core.audit["package"]["paths"]), 9)

    def test_nested_stage_reaches_existing_sealed_preflight(self):
        setup, prepared = self._sealed_fake_preflight()
        self.assertTrue(prepared.ready)
        self.assertEqual(prepared.operation_intent.profile_id, NESTED_HOST_PROFILE_ID)
        identity = setup["facade"].owner_authorization_identity
        self.assertIsNotNone(identity)
        self._assert_no_sender_or_claim(setup)
        setup["facade"].authorize_prepared_operation(identity.approval_phrase)
        result = setup["facade"].execute_once(
            prepared.plan_report,
            confirmation_interaction=lambda _review: prepared.operation_intent.confirmation_phrase,
        )
        self.assertEqual(result.state, "readback_verified")
        model = DesktopWorkflowModel()
        model.load_backup(setup["baseline"].directory)
        self.assertFalse(any(self.item.source_filename in row.path for row in model.rows()))
        refresh_device_library_from_verified_transfer(model, result)
        paths = [row.path for row in model.rows()]
        self.assertTrue(any("Section-B\\Detail\\05-ending" in path for path in paths))

    def test_ordinary_confirmation_and_wrong_owner_approval_cannot_send(self):
        setup, prepared = self._sealed_fake_preflight()
        with self.assertRaises(Exception):
            setup["facade"].authorize_prepared_operation("APPROVE ANOTHER OPERATION")
        with self.assertRaises(Exception):
            setup["facade"].execute_once(
                prepared.plan_report,
                confirmation_interaction=lambda _review: prepared.operation_intent.confirmation_phrase,
            )
        self._assert_no_sender_or_claim(setup)

    def test_missing_sealed_prepared_payload_stops_before_sender(self):
        setup, prepared = self._sealed_fake_preflight()
        identity = setup["facade"].owner_authorization_identity
        setup["facade"].authorize_prepared_operation(identity.approval_phrase)
        (self.stage.operation_owned_root / "prepared" / "Section-B" / "Detail" / "05-ending.txt").unlink()
        with self.assertRaises(Exception):
            setup["facade"].execute_once(
                prepared.plan_report,
                confirmation_interaction=lambda _review: prepared.operation_intent.confirmation_phrase,
            )
        self._assert_no_sender_or_claim(setup)

    def test_tampered_sealed_order_stops_before_claim_marker_lock_and_backend(self):
        setup, prepared = self._sealed_fake_preflight()
        identity = setup["facade"].owner_authorization_identity
        setup["facade"].authorize_prepared_operation(identity.approval_phrase)
        manifest_path = self.stage.operation_owned_root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["nodes"][0]["order"] = 1
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(Exception):
            setup["facade"].execute_once(
                prepared.plan_report,
                confirmation_interaction=lambda _review: prepared.operation_intent.confirmation_phrase,
            )
        self._assert_no_sender_or_claim(setup)

    def test_nested_preflight_and_bundle_require_operation_owned_staging(self):
        setup, prepared = self._sealed_fake_preflight()
        with self.assertRaisesRegex(Exception, "operation-owned"):
            setup["facade"].refresh_live_preflight(
                prepared.plan_report,
                catalog=self.stage.catalog,
                preflight_report_path=setup["root"] / "unstaged" / "sealed-preflight.json",
                bundle_path=setup["root"] / "unstaged" / "operation-bundle.json",
                operation_stage=None,
            )
        with self.assertRaisesRegex(Exception, "operation-owned"):
            replace(prepared.operation_bundle, operation_owned_staging=None).verify_artifacts()
        self._assert_no_sender_or_claim(setup)

    def test_sealed_fake_operation_survives_original_import_removal(self):
        setup, prepared = self._sealed_fake_preflight()
        shutil.rmtree(self.source)
        identity = setup["facade"].owner_authorization_identity
        setup["facade"].authorize_prepared_operation(identity.approval_phrase)
        result = setup["facade"].execute_once(
            prepared.plan_report,
            confirmation_interaction=lambda _review: prepared.operation_intent.confirmation_phrase,
        )
        self.assertEqual(result.state, "readback_verified")

    def test_approved_operation_cannot_be_refreshed_before_confirm_transfer(self):
        setup, first = self._sealed_fake_preflight()
        prior = setup["facade"].owner_authorization_identity
        setup["facade"].authorize_prepared_operation(prior.approval_phrase)
        second_stage = prepare_nested_folder_package(self.catalog, self.item, self.plan)
        self.assertIsNotNone(second_stage)
        second_plan = build_library_transfer_queue_plan(
            second_stage.catalog, selection_mode=SELECTION_SELECTED,
            selected_item_ids=[self.item.item_id], backup=setup["baseline"],
            available_capacity_bytes=10_000_000,
        ).to_dict()
        with self.assertRaisesRegex(Exception, "owner-approved operation cannot be rebuilt"):
            setup["facade"].refresh_live_preflight(
                second_plan, catalog=second_stage.catalog,
                preflight_report_path=setup["root"] / "second-operation" / "sealed-preflight.json",
                bundle_path=setup["root"] / "second-operation" / "operation-bundle.json",
                operation_stage=second_stage,
            )
        self.assertFalse(setup["facade"].owner_approval_accepted)
        with self.assertRaises(Exception):
            setup["facade"].execute_once(
                first.plan_report,
                confirmation_interaction=lambda _review: first.operation_intent.confirmation_phrase,
            )
        self._assert_no_sender_or_claim(setup)

    def test_late_worker_preflight_cannot_replace_approved_operation(self):
        setup, first = self._sealed_fake_preflight()
        second_stage = prepare_nested_folder_package(self.catalog, self.item, self.plan)
        self.assertIsNotNone(second_stage)
        second_plan = build_library_transfer_queue_plan(
            second_stage.catalog, selection_mode=SELECTION_SELECTED,
            selected_item_ids=[self.item.item_id], backup=setup["baseline"],
            available_capacity_bytes=10_000_000,
        ).to_dict()
        second = setup["facade"].refresh_live_preflight(
            second_plan, catalog=second_stage.catalog,
            preflight_report_path=setup["root"] / "late-operation" / "sealed-preflight.json",
            bundle_path=setup["root"] / "late-operation" / "operation-bundle.json",
            operation_stage=second_stage, store=False,
        )
        prior = setup["facade"].owner_authorization_identity
        self.assertNotEqual(prior.identity_sha256,
                            type(prior).from_bundle(second.operation_bundle).identity_sha256)
        setup["facade"].authorize_prepared_operation(prior.approval_phrase)
        with self.assertRaisesRegex(Exception, "owner-approved operation cannot be replaced"):
            setup["facade"].adopt_prepared_operation(second)
        self.assertFalse(setup["facade"].owner_approval_accepted)
        for operation in (first, second):
            with self.assertRaises(Exception):
                setup["facade"].execute_once(
                    operation.plan_report,
                    confirmation_interaction=lambda _review: operation.operation_intent.confirmation_phrase,
                )
        self._assert_no_sender_or_claim(setup)

    def test_ui_rebuild_stop_requires_new_owner_approval_for_operation_b(self):
        setup, first = self._sealed_fake_preflight()
        owner_a = setup["facade"].owner_authorization_identity
        setup["facade"].authorize_prepared_operation(owner_a.approval_phrase)
        self.assertTrue(setup["facade"].stop_approved_rebuild())
        self.assertFalse(setup["facade"].owner_approval_accepted)

        second_stage = prepare_nested_folder_package(self.catalog, self.item, self.plan)
        second_plan = build_library_transfer_queue_plan(
            second_stage.catalog, selection_mode=SELECTION_SELECTED,
            selected_item_ids=[self.item.item_id], backup=setup["baseline"],
            available_capacity_bytes=10_000_000,
        ).to_dict()
        second = setup["facade"].refresh_live_preflight(
            second_plan, catalog=second_stage.catalog,
            preflight_report_path=setup["root"] / "new-review" / "sealed-preflight.json",
            bundle_path=setup["root"] / "new-review" / "operation-bundle.json",
            operation_stage=second_stage,
        )
        self.assertNotEqual(
            owner_a.identity_sha256,
            setup["facade"].owner_authorization_identity.identity_sha256,
        )
        with self.assertRaisesRegex(Exception, "lacks separate owner identity approval"):
            setup["facade"].execute_once(
                second.plan_report,
                confirmation_interaction=lambda _review: second.operation_intent.confirmation_phrase,
            )
        self._assert_no_sender_or_claim(setup)

    def test_nonzero_fake_completion_has_no_automatic_retry(self):
        try:
            from test_prepared_package_workflow import PackageWorkflowBackend
        except ModuleNotFoundError:
            from tests.test_prepared_package_workflow import PackageWorkflowBackend
        setup, prepared = self._sealed_fake_preflight(
            backend=PackageWorkflowBackend(completions=(1, 0))
        )
        identity = setup["facade"].owner_authorization_identity
        setup["facade"].authorize_prepared_operation(identity.approval_phrase)
        with self.assertRaises(Exception) as raised:
            setup["facade"].execute_once(
                prepared.plan_report,
                confirmation_interaction=lambda _review: prepared.operation_intent.confirmation_phrase,
            )
        self.assertIn("no automatic retry", str(raised.exception))
        self.assertEqual(
            sum(call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT for call in setup["backend"].calls),
            1,
        )

    def test_ambiguous_fake_sender_result_locks_and_never_retries(self):
        try:
            from test_prepared_package_workflow import PackageWorkflowBackend
        except ModuleNotFoundError:
            from tests.test_prepared_package_workflow import PackageWorkflowBackend
        setup, prepared = self._sealed_fake_preflight(
            backend=PackageWorkflowBackend(bulk_error=OSError("ambiguous fake write"))
        )
        identity = setup["facade"].owner_authorization_identity
        setup["facade"].authorize_prepared_operation(identity.approval_phrase)
        with self.assertRaises(Exception) as raised:
            setup["facade"].execute_once(
                prepared.plan_report,
                confirmation_interaction=lambda _review: prepared.operation_intent.confirmation_phrase,
            )
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertEqual(
            sum(call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT for call in setup["backend"].calls),
            1,
        )
        self.assertIsNotNone(setup["lock"].read())

    def test_scale_fixture_planning_and_serialization_only(self):
        scale = self.root / "IC_P18_040_SCALE"
        bmp = make_profile_bmp()
        for group_index in range(20):
            group = scale / f"Group-{group_index:02}"
            detail = group / "Detail"
            detail.mkdir(parents=True)
            for leaf_index in range(3):
                (group / f"{leaf_index:02}-note.txt").write_text(
                    f"group {group_index} leaf {leaf_index}\n", encoding="utf-8"
                )
                (detail / f"{leaf_index:02}-page.bmp").write_bytes(bmp)
        catalog = LibraryCatalog(self.root / "scale-catalog.json")
        item = catalog.import_folder(scale)
        plan = build_library_device_transfer_plan(
            catalog, [item.item_id], ("root",), empty_device()
        )
        serialized = json.loads(json.dumps(plan.to_dict()))
        self.assertEqual(len(plan.nodes), 161)
        self.assertEqual(sum(node.kind == "directory" for node in plan.nodes), 41)
        self.assertEqual(sum(node.kind == "file" for node in plan.nodes), 120)
        self.assertEqual(len(serialized["nodes"]), 161)
        self.assertFalse(plan.expected_delta.removed_paths)


if __name__ == "__main__":
    unittest.main()
