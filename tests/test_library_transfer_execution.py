"""Host-only integration tests for the normal Library execution facade."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from infocarry.backup_format import parse_backup_blob
from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.capability_profile import (
    INITIAL_EXPERIMENTAL_PROFILE_ID,
    VNW_V15_FOUR_LEAF_PROFILE_ID,
)
from infocarry.device_info import RawInfoResponse
from infocarry.device_library_semantics import (
    DEVICE_ROOT_PATH,
    DeviceLibraryNode,
    DeviceLibrarySnapshot,
)
from infocarry.desktop_ttk import _exact_live_package_artifact
from infocarry.execution_profile import FOUR_LEAF_CHILD_NAMES, FRESH_CHILD_NAMES
from infocarry.library import LibraryCatalog
from infocarry.library_device_transfer import build_library_device_transfer_plan
from infocarry.library_folder_package_adapter import prepare_exact_folder_package
from infocarry.library_transfer_execution import (
    FRESH_AUXILIARY_STATE_POLICY,
    LibraryTransferExecutionError,
    LibraryTransferExecutionFacade,
    LibraryTransferExecutionRuntime,
    LibraryTransferOperationBinding,
)
from infocarry.library_transfer_plan import (
    SELECTION_SELECTED,
    build_library_transfer_queue_plan,
)
from infocarry.library_transfer_readiness import (
    ReadinessReasonCode,
    readiness_state_from_error,
)
from infocarry.prepared_media_package import (
    build_prepared_media_package,
    export_prepared_media_package,
)
from infocarry.prepared_library_package_operation_bundle import load_operation_bundle
from infocarry.execution_claim_store import PersistentExecutionClaimStore
from infocarry.indeterminate_write_lock import PersistentIndeterminateWriteLock
from infocarry.write_protocol import REQUEST_BEGIN_TRANSMIT
from infocarry.write_safety_boundary import PersistentWriteSafetyOwner
import infocarry.experimental_library_transfer as experimental_transfer_module
from infocarry.prepared_library_package_live_adapter import (
    PreparedLibraryPackageLiveResultReconciliationError,
)
import infocarry.prepared_library_package_bridge as bridge_module
import infocarry.prepared_package_multi_candidate as candidate_module

try:
    from test_new_txt import _write_archive
    from test_prepared_library_package_live_adapter import _named_template_blob, _response
    from test_prepared_package_multi_candidate import _template_blobs, make_profile_bmp
    from test_prepared_package_workflow import PackageWorkflowBackend
except ModuleNotFoundError:
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_library_package_live_adapter import _named_template_blob, _response
    from tests.test_prepared_package_multi_candidate import _template_blobs, make_profile_bmp
    from tests.test_prepared_package_workflow import PackageWorkflowBackend


NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)
FRESH_TEST_TARGET = "IC_P18_LIBRARY_20260913_03"
HISTORICAL_P18_021_TARGET = "IC_P18_LIBRARY_20260913_01"
HISTORICAL_P18_023_TARGET = "IC_P18_LIBRARY_20260913_02"
FRESH_CONFIRMATION = f"ADD {FRESH_TEST_TARGET} ONCE"
FRESH_OWNER_APPROVAL = "APPROVE P18-025 V15 UI PHYSICAL VALIDATION 01"


def _capacity_response_with_limit(limit: int) -> NativeCapacityResponse:
    raw = bytearray(_response().raw_response)
    raw[0x08:0x0C] = limit.to_bytes(4, "big")
    return NativeCapacityResponse.from_hardware_response(
        RawInfoResponse(0x0019, "capacity-propagation-test", bytes(raw)),
        device_identity=(0x054C, 0x001E),
    )


class LibraryTransferExecutionFacadeTests(unittest.TestCase):
    def _setup(
        self,
        *,
        backend=None,
        detected=(0x054C, 0x001E),
        auxiliary_state=True,
        after_mode=None,
        target=FRESH_TEST_TARGET,
        child_kinds=("txt", "bmp", "txt"),
        profile_id=None,
        include_operation_binding=True,
        runtime_provider_mode=False,
    ):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        baseline_blob, template_blob = _template_blobs()
        fixed_state = {command: b"\x00" * 64 for command in range(0x001B, 0x0020)}
        if auxiliary_state:
            display = bytearray(64)
            display[0:4] = (1).to_bytes(4, "big")
            display[8:12] = (0x80).to_bytes(4, "big")
            display[60:] = b"HIST"
            bookmark = bytearray(64)
            bookmark[:20] = b"".join(
                value.to_bytes(4, "big")
                for value in (0x80, 0xC00, 0, 0x14, 0xFFF101C5)
            )
            bookmark[40:] = b"B" * 24
            fixed_state[0x001B] = bytes(display)
            fixed_state[0x001F] = bytes(bookmark)
        baseline_path = _write_archive(
            root / "baseline",
            baseline_blob,
            NOW,
            fixed_state=fixed_state,
        )
        baseline = __import__("infocarry.write_gate", fromlist=["verify_fresh_backup"]).verify_fresh_backup(
            baseline_path,
            now=NOW,
            max_age_seconds=None,
        )

        child_names = (
            FRESH_CHILD_NAMES
            if tuple(child_kinds) == ("txt", "bmp", "txt")
            else FOUR_LEAF_CHILD_NAMES
            if tuple(child_kinds) == ("txt", "bmp", "txt", "txt")
            else tuple(f"{index:02}-page.{kind}" for index, kind in enumerate(child_kinds, 1))
        )
        sources = []
        for index, (kind, name) in enumerate(zip(child_kinds, child_names), start=1):
            source = root / f"source-{index}.{kind}"
            if kind == "txt":
                source.write_text(f"Page {index}\n日本語\n", encoding="utf-8")
            else:
                source.write_bytes(make_profile_bmp())
            sources.append((source, name))
        package = build_prepared_media_package(
            sources,
            target,
        )
        # Exercise the corrected P18-024 representation seam: the physical
        # archive envelope is intentionally named 00-package, while the
        # manifest target remains the owner-visible Library identity.
        package_root = export_prepared_media_package(package, root / "00-package")
        catalog = LibraryCatalog(root / "catalog" / "library.json")
        item = catalog.import_prepared_package(package_root)
        plan = build_library_transfer_queue_plan(
            catalog,
            selected_item_ids=[item.item_id],
            selection_mode=SELECTION_SELECTED,
            backup=baseline,
            available_capacity_bytes=10_000_000,
        ).to_dict()
        template = parse_backup_blob(_named_template_blob())
        template_path = root / "reviewed-template.bin"
        template_path.write_bytes(template.data)
        evidence_namespace = root / "evidence"
        evidence_namespace.mkdir()
        candidate_holder = {"candidate": None}
        captures = []

        def capture(destination, **_kwargs):
            destination = Path(destination)
            captures.append(destination)
            if destination.name.startswith("backup-after"):
                if after_mode == "no_backup":
                    raise OSError("simulated missing post-operation backup")
                candidate = candidate_holder["candidate"]
                if candidate is None:
                    raise AssertionError("post-operation backup requested before candidate")
                blob = candidate.candidate_blob
                if after_mode == "stale_readback":
                    blob = baseline_blob
                blocks = candidate.core.fixed_state.candidate_raw_blocks
                after_state = dict(zip(range(0x001B, 0x0020), blocks))
            else:
                blob = baseline_blob
                after_state = fixed_state
            _write_archive(destination, blob, NOW, fixed_state=after_state)

        binding = (
            LibraryTransferOperationBinding(
                target_folder_name=target,
                owner_approval_phrase=FRESH_OWNER_APPROVAL,
                profile_id=(
                    profile_id
                    or (
                        VNW_V15_FOUR_LEAF_PROFILE_ID
                        if tuple(child_kinds) == ("txt", "bmp", "txt", "txt")
                        else INITIAL_EXPERIMENTAL_PROFILE_ID
                    )
                ),
            )
            if include_operation_binding
            else None
        )
        claim_store = PersistentExecutionClaimStore(
            root / "installation-state" / "execution-claims.sqlite3"
        )
        lock = PersistentIndeterminateWriteLock(root / "installation-state" / "lock.json")
        runtime = LibraryTransferExecutionRuntime(
            template=template,
            template_path=template_path,
            evidence_namespace=evidence_namespace,
            detect_device=lambda: detected,
            query_capacity=_response,
            capture=capture,
            backend=backend or PackageWorkflowBackend(),
            execution_claim_store=claim_store,
            indeterminate_write_lock=lock,
            new_record_timestamp_be32=0x6A958595,
            max_age_seconds=None,
        )
        runtime_provider = None
        if runtime_provider_mode:
            class FakeRuntimeProvider:
                evidence_namespace = runtime.evidence_namespace

                def __init__(self):
                    self.create_calls = 0

                def create_runtime(self, *, write_safety_owner):
                    self.create_calls += 1
                    if (
                        write_safety_owner.execution_claim_store is not claim_store
                        or write_safety_owner.indeterminate_write_lock is not lock
                    ):
                        raise AssertionError("provider did not receive the shared safety owner")
                    return runtime

            runtime_provider = FakeRuntimeProvider()
            facade = LibraryTransferExecutionFacade(
                operation_binding=binding,
                runtime_provider=runtime_provider,
            )
            facade.attach_write_safety_owner(
                PersistentWriteSafetyOwner(
                    execution_claim_store=claim_store,
                    indeterminate_write_lock=lock,
                )
            )
        else:
            facade = LibraryTransferExecutionFacade(
                operation_binding=binding,
                runtime=runtime,
            )
        return {
            "temporary": temporary,
            "root": root,
            "baseline": baseline,
            "baseline_blob": baseline_blob,
            "fixed_state": fixed_state,
            "catalog": catalog,
            "item": item,
            "plan": plan,
            "template": template,
            "candidate_holder": candidate_holder,
            "captures": captures,
            "facade": facade,
            "runtime": runtime,
            "runtime_provider": runtime_provider,
            "backend": runtime.backend,
            "claim_store": claim_store,
            "lock": lock,
            "binding": binding,
        }

    def _prepare(self, setup, *, operation_name="operation"):
        self._patch_template_hashes(setup)
        offline_plan = setup["plan"]
        operation_root = setup["root"] / operation_name
        prepared = setup["facade"].refresh_live_preflight(
            offline_plan,
            catalog=setup["catalog"],
            preflight_report_path=operation_root / "sealed-preflight.json",
            bundle_path=operation_root / "operation-bundle.json",
        )
        setup["candidate_holder"]["candidate"] = prepared.preflight.candidate
        setup["offline_plan"] = offline_plan
        setup["plan"] = dict(prepared.plan_report)
        return prepared

    @staticmethod
    def _claim_count(setup):
        connection = sqlite3.connect(setup["claim_store"].path)
        try:
            return connection.execute("SELECT count(*) FROM execution_claims").fetchone()[0]
        finally:
            connection.close()

    def test_visible_folder_transfer_mapping_enters_only_existing_readiness_boundary(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        source_root = setup["root"] / "visible-local-library"
        folder_path = source_root / FRESH_TEST_TARGET
        folder_path.mkdir(parents=True)
        source_payloads = {}
        for index, (kind, name) in enumerate(
            zip(("txt", "bmp", "txt"), FRESH_CHILD_NAMES),
            start=1,
        ):
            path = folder_path / name
            if kind == "txt":
                path.write_text(f"Ordinary folder page {index}\n", encoding="utf-8")
            else:
                path.write_bytes(make_profile_bmp())
            source_payloads[path] = path.read_bytes()

        folder_catalog = LibraryCatalog(source_root / "library.json")
        folder = folder_catalog.import_folder(folder_path)
        logical_plan = build_library_device_transfer_plan(
            folder_catalog,
            [folder.item_id],
            ("root",),
            DeviceLibrarySnapshot(
                (DeviceLibraryNode(DEVICE_ROOT_PATH, "directory", 0, system=True),)
            ),
        )
        catalog_before_stage = folder_catalog.path.read_bytes()
        stage = prepare_exact_folder_package(
            folder_catalog,
            folder,
            logical_plan,
            staging_parent=setup["root"] / "manager-prepared-content",
        )
        self.assertIsNotNone(stage)
        self.addCleanup(stage.cleanup)

        # Equivalent to the visible Transfer action's existing single-item
        # readiness step. It deliberately stops before live preflight.
        queue = build_library_transfer_queue_plan(
            stage.catalog,
            selected_item_ids=[folder.item_id],
            selection_mode=SELECTION_SELECTED,
            backup=setup["baseline"],
            available_capacity_bytes=10_000_000,
        )
        readiness = setup["facade"].review_readiness(queue.to_dict())

        self.assertTrue(readiness.host_profile_eligible)
        self.assertEqual(
            readiness.report["profile"]["id"],
            INITIAL_EXPERIMENTAL_PROFILE_ID,
        )
        self.assertEqual(
            readiness.report["package"]["folder_path"],
            f"root\\{FRESH_TEST_TARGET}",
        )
        self.assertFalse(queue.to_dict()["safety"]["candidate_constructed"])
        self.assertIsNone(setup["candidate_holder"]["candidate"])
        self.assertEqual(setup["backend"].calls, [])
        self.assertEqual(self._claim_count(setup), 0)
        self.assertEqual(folder_catalog.path.read_bytes(), catalog_before_stage)
        for path, payload in source_payloads.items():
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_bytes(), payload)

        # Simulate only the exact admitted live-service boundary with the
        # injected host runtime. This may build a candidate, but does not
        # execute, consume a claim, or call the sender.
        self._patch_template_hashes(setup)
        operation_root = setup["root"] / "folder-operation"
        prepared = setup["facade"].refresh_live_preflight(
            queue.to_dict(),
            catalog=stage.catalog,
            preflight_report_path=operation_root / "sealed-preflight.json",
            bundle_path=operation_root / "operation-bundle.json",
            store=False,
            operation_stage=stage,
        )
        self.assertTrue(prepared.ready)
        self.assertEqual(
            tuple(item.kind for item in prepared.preflight.candidate.package.items),
            ("txt", "bmp", "txt"),
        )
        bound_bundle = load_operation_bundle(prepared.bundle_path)
        self.assertIsNotNone(bound_bundle.operation_owned_staging)
        self.assertEqual(
            Path(bound_bundle.package_manifest.path).parts[-2:],
            ("prepared-package", "manifest.json"),
        )
        stage.cleanup()
        reloaded_bundle = load_operation_bundle(prepared.bundle_path)
        self.assertIsNotNone(reloaded_bundle.operation_owned_staging)
        reloaded_bundle.verify_artifacts()
        setup["candidate_holder"]["candidate"] = prepared.preflight.candidate
        setup["facade"].adopt_prepared_operation(prepared)
        setup["plan"] = dict(prepared.plan_report)
        result = setup["facade"].execute_once(
            setup["plan"],
            confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
        )
        self.assertEqual(result.state, "readback_verified")
        self.assertEqual(
            sum(
                call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
                for call in setup["backend"].calls
            ),
            1,
        )
        self.assertEqual(self._claim_count(setup), 1)
        self.assertIsNone(setup["claim_store"].read_sender_in_flight())
        self.assertIsNone(setup["lock"].read())

    def _patch_template_hashes(self, setup):
        template_hash = hashlib.sha256(setup["template"].data).hexdigest()
        patchers = [
            patch.object(bridge_module, "P17_003_REVIEWED_TEMPLATE_BLOB_SHA256", template_hash),
            patch.object(candidate_module, "REVIEWED_TEMPLATE_SUBSET_POLICY_SHA256", template_hash),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_exact_package_reaches_host_ready_review_without_hardware_write(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        self._patch_template_hashes(setup)
        facade = setup["facade"]
        readiness = facade.review_readiness(setup["plan"])
        self.assertTrue(readiness.host_profile_eligible)
        self.assertFalse(facade.transfer_actionable)
        self.assertEqual(setup["backend"].calls, [])

        prepared = facade.refresh_live_preflight(
            setup["plan"],
            catalog=setup["catalog"],
            preflight_report_path=setup["root"] / "operation" / "sealed-preflight.json",
            bundle_path=setup["root"] / "operation" / "operation-bundle.json",
        )
        setup["candidate_holder"]["candidate"] = prepared.preflight.candidate
        setup["plan"] = dict(prepared.plan_report)
        self.assertTrue(prepared.ready)
        self.assertTrue(facade.transfer_actionable)
        self.assertEqual(
            load_operation_bundle(prepared.bundle_path).operation_id,
            setup["binding"].operation_id,
        )
        self.assertIsNone(setup["claim_store"].read_sender_in_flight())
        self.assertEqual(
            len([call for call in setup["backend"].calls if call[0] == "control_out"]),
            0,
        )

        result = facade.execute_once(
            setup["plan"],
            confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
        )
        self.assertEqual(result.state, "readback_verified")
        self.assertEqual(result.completion, 0)
        self.assertEqual(
            len(
                [
                    call
                    for call in setup["backend"].calls
                    if call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
                ]
            ),
            1,
        )
        self.assertEqual(self._claim_count(setup), 1)
        self.assertIsNone(setup["claim_store"].read_sender_in_flight())
        self.assertIsNone(setup["lock"].read())

    def test_missing_operation_owned_package_is_diagnostic_before_claim(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        self._patch_template_hashes(setup)
        source_root = setup["root"] / "ordinary-source"
        folder_path = source_root / FRESH_TEST_TARGET
        folder_path.mkdir(parents=True)
        for index, (kind, name) in enumerate(
            zip(("txt", "bmp", "txt"), FRESH_CHILD_NAMES),
            start=1,
        ):
            path = folder_path / name
            if kind == "txt":
                path.write_text(f"Ordinary folder page {index}\n", encoding="utf-8")
            else:
                path.write_bytes(make_profile_bmp())
        catalog = LibraryCatalog(source_root / "library.json")
        folder = catalog.import_folder(folder_path)
        logical_plan = build_library_device_transfer_plan(
            catalog,
            [folder.item_id],
            DEVICE_ROOT_PATH,
            DeviceLibrarySnapshot(
                (DeviceLibraryNode(DEVICE_ROOT_PATH, "directory", 0, system=True),)
            ),
        )
        stage = prepare_exact_folder_package(
            catalog,
            folder,
            logical_plan,
            staging_parent=setup["root"] / "manager-prepared-content",
        )
        self.assertIsNotNone(stage)
        self.addCleanup(stage.cleanup)
        prepared = setup["facade"].refresh_live_preflight(
            build_library_transfer_queue_plan(
                stage.catalog,
                selected_item_ids=[folder.item_id],
                selection_mode=SELECTION_SELECTED,
                backup=setup["baseline"],
                available_capacity_bytes=10_000_000,
            ).to_dict(),
            catalog=stage.catalog,
            preflight_report_path=setup["root"] / "missing-stage" / "sealed-preflight.json",
            bundle_path=setup["root"] / "missing-stage" / "operation-bundle.json",
            operation_stage=stage,
        )
        setup["facade"].adopt_prepared_operation(prepared)
        setup["plan"] = dict(prepared.plan_report)
        stage.cleanup()
        Path(prepared.operation_bundle.package_manifest.path).unlink()

        with self.assertRaises(LibraryTransferExecutionError) as raised:
            setup["facade"].execute_once(
                setup["plan"],
                confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
            )
        error = raised.exception
        diagnostic_path = Path(error.audit["diagnostic_path"])
        diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
        self.assertEqual(diagnostic["reason_code"], "staged_artifact_missing")
        self.assertFalse(diagnostic["sender_started"])
        self.assertTrue(diagnostic["authorization_occurred"])
        self.assertFalse(diagnostic["execution_claim_created"])
        self.assertFalse(diagnostic["sender_marker_present"])
        self.assertEqual(setup["backend"].calls, [])
        self.assertEqual(self._claim_count(setup), 0)
        self.assertIsNone(setup["claim_store"].read_sender_in_flight())
        self.assertIsNone(setup["lock"].read())
        self.assertEqual(
            readiness_state_from_error(error).reason_codes,
            (ReadinessReasonCode.TRANSFER_PREPARATION_UNVERIFIED,),
        )

    def test_nested_folder_selection_is_rejected_before_operation_staging(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        source_root = setup["root"] / "ordinary-source"
        outer = source_root / "Outer"
        nested = outer / "Nested"
        nested.mkdir(parents=True)
        (nested / "01-introduction.txt").write_text("intro\n", encoding="utf-8")
        (nested / "02-page-01.bmp").write_bytes(make_profile_bmp())
        (nested / "03-ending.txt").write_text("end\n", encoding="utf-8")
        folder_catalog = LibraryCatalog(source_root / "library.json")
        folder_catalog.import_folder(outer)
        nested_item = next(
            item
            for item in folder_catalog._items.values()
            if item.source_filename == "Nested"
        )
        logical_plan = build_library_device_transfer_plan(
            folder_catalog,
            [nested_item.item_id],
            DEVICE_ROOT_PATH,
            DeviceLibrarySnapshot(
                (DeviceLibraryNode(DEVICE_ROOT_PATH, "directory", 0, system=True),)
            ),
        )
        self.assertIsNone(
            prepare_exact_folder_package(
                folder_catalog,
                nested_item,
                logical_plan,
                staging_parent=setup["root"] / "manager-prepared-content",
            )
        )

    def test_diagnostic_store_read_failure_is_explicitly_unknown(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        prepared = self._prepare(setup)
        error = LibraryTransferExecutionError(
            "operation-owned package is unavailable",
            stage="operation_staging",
        )
        with patch.object(
            type(setup["claim_store"]),
            "read_claim",
            side_effect=RuntimeError("claim database unavailable"),
        ), patch.object(
            type(setup["claim_store"]),
            "read_sender_in_flight",
            side_effect=RuntimeError("marker database unavailable"),
        ):
            diagnostic_path = setup["facade"]._persist_operation_diagnostic(
                prepared,
                error,
                binding=None,
            )
        self.assertIsNotNone(diagnostic_path)
        diagnostic = json.loads(Path(diagnostic_path).read_text(encoding="utf-8"))
        self.assertIsNone(diagnostic["sender_started"])
        self.assertIsNone(diagnostic["execution_claim_created"])
        self.assertIsNone(diagnostic["sender_marker_present"])
        self.assertEqual(diagnostic["execution_claim_state"], "unavailable")
        self.assertEqual(diagnostic["sender_marker_state"], "unavailable")
        self.assertEqual(len(diagnostic["diagnostic_state_read_errors"]), 2)

    def test_diagnostic_write_failure_is_exposed_on_original_error(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        prepared = self._prepare(setup)
        error = LibraryTransferExecutionError("pre-send failure")
        with patch(
            "infocarry.library_transfer_execution._write_new_json",
            side_effect=OSError("evidence volume unavailable"),
        ):
            diagnostic_path = setup["facade"]._persist_operation_diagnostic(
                prepared,
                error,
                binding=None,
            )
        self.assertIsNone(diagnostic_path)
        self.assertTrue(
            error.audit["diagnostic_path"].endswith("pre-send-diagnostic.json")
        )
        self.assertIn(
            "evidence volume unavailable",
            error.audit["diagnostic_persistence_error"],
        )

    def test_diagnostic_missing_store_is_explicitly_unavailable(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        prepared = self._prepare(setup)
        setup["facade"].runtime = replace(
            setup["facade"].runtime,
            execution_claim_store=None,
        )
        error = LibraryTransferExecutionError("pre-send failure")
        diagnostic_path = setup["facade"]._persist_operation_diagnostic(
            prepared,
            error,
            binding=None,
        )
        diagnostic = json.loads(Path(diagnostic_path).read_text(encoding="utf-8"))
        self.assertIsNone(diagnostic["sender_started"])
        self.assertIsNone(diagnostic["execution_claim_created"])
        self.assertIsNone(diagnostic["sender_marker_present"])
        self.assertEqual(diagnostic["execution_claim_state"], "unavailable")
        self.assertEqual(diagnostic["sender_marker_state"], "unavailable")

    def _generic_exact_plan(self, setup):
        snapshot = DeviceLibrarySnapshot(
            (DeviceLibraryNode(DEVICE_ROOT_PATH, "directory", 0, system=True),)
        )
        plan = build_library_device_transfer_plan(
            setup["catalog"],
            [setup["item"].item_id],
            DEVICE_ROOT_PATH,
            snapshot,
        )
        return plan

    def _assert_exact_route_reaches_guarded_preflight(self, setup):
        self.addCleanup(setup["temporary"].cleanup)
        self._patch_template_hashes(setup)
        logical_plan = self._generic_exact_plan(setup)
        artifact = _exact_live_package_artifact(setup["item"], logical_plan)
        self.assertIsNotNone(artifact)
        self.assertFalse(logical_plan.to_dict()["safety"]["candidate_constructed"])

        facade = setup["facade"]
        review = facade.review_readiness(setup["plan"])
        self.assertTrue(review.host_profile_eligible)
        self.assertEqual(setup["backend"].calls, [])
        self.assertEqual(self._claim_count(setup), 0)
        self.assertIsNone(setup["lock"].read())

        prepared = facade.refresh_live_preflight(
            setup["plan"],
            catalog=setup["catalog"],
            preflight_report_path=setup["root"] / "operation" / "sealed-preflight.json",
            bundle_path=setup["root"] / "operation" / "operation-bundle.json",
        )

        self.assertTrue(prepared.ready)
        self.assertTrue(facade.transfer_actionable)
        self.assertIs(facade.runtime.execution_claim_store, setup["claim_store"])
        self.assertIs(facade.runtime.indeterminate_write_lock, setup["lock"])
        self.assertEqual(setup["backend"].calls, [])
        self.assertEqual(self._claim_count(setup), 0)
        self.assertIsNone(setup["claim_store"].read_sender_in_flight())
        self.assertIsNone(setup["lock"].read())

    def test_exact_three_leaf_ui_mapping_reaches_existing_guarded_preflight_only(self):
        setup = self._setup()
        self._assert_exact_route_reaches_guarded_preflight(setup)

    def test_exact_four_leaf_ui_mapping_reaches_existing_guarded_preflight_only(self):
        setup = self._setup(
            child_kinds=("txt", "bmp", "txt", "txt"),
            profile_id=VNW_V15_FOUR_LEAF_PROFILE_ID,
        )
        self._assert_exact_route_reaches_guarded_preflight(setup)

    def test_production_style_late_binding_requires_final_confirmation_for_both_profiles(self):
        for label, kinds, profile_id in (
            (
                "three-leaf",
                ("txt", "bmp", "txt"),
                INITIAL_EXPERIMENTAL_PROFILE_ID,
            ),
            (
                "four-leaf",
                ("txt", "bmp", "txt", "txt"),
                VNW_V15_FOUR_LEAF_PROFILE_ID,
            ),
        ):
            with self.subTest(profile=label):
                setup = self._setup(
                    child_kinds=kinds,
                    profile_id=profile_id,
                    include_operation_binding=False,
                    runtime_provider_mode=True,
                )
                self.addCleanup(setup["temporary"].cleanup)
                facade = setup["facade"]
                provider = setup["runtime_provider"]
                self.assertIsNone(facade.operation_binding)
                self.assertIsNone(facade.runtime)
                self.assertEqual(provider.create_calls, 0)
                prepared = self._prepare(setup)
                self.assertIs(facade.runtime, setup["runtime"])
                self.assertEqual(provider.create_calls, 1)
                intent = prepared.operation_intent
                self.assertIsNotNone(intent)
                self.assertIsNone(facade.operation_binding)
                self.assertEqual(
                    prepared.operation_bundle.operation_id,
                    intent.operation_id,
                )
                self.assertEqual(setup["backend"].calls, [])
                self.assertEqual(self._claim_count(setup), 0)
                self.assertIsNone(setup["claim_store"].read_sender_in_flight())
                self.assertIsNone(setup["lock"].read())

                with self.assertRaises(LibraryTransferExecutionError):
                    facade.execute_once(
                        setup["plan"],
                        confirmation_interaction=lambda _review: "not the target phrase",
                    )
                self.assertIsNone(facade.operation_binding)
                self.assertEqual(setup["backend"].calls, [])
                self.assertEqual(self._claim_count(setup), 0)
                self.assertIsNone(setup["claim_store"].read_sender_in_flight())
                self.assertIsNone(setup["lock"].read())

                prepared = self._prepare(setup, operation_name="confirmed-operation")
                self.assertIsNone(facade.operation_binding)
                result = facade.execute_once(
                    setup["plan"],
                    confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
                )
                self.assertEqual(result.state, "readback_verified")
                self.assertEqual(result.completion, 0)
                self.assertEqual(
                    sum(
                        call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
                        for call in setup["backend"].calls
                    ),
                    1,
                )
                self.assertIsNone(facade.operation_binding)
                self.assertEqual(self._claim_count(setup), 1)
                self.assertIsNone(setup["claim_store"].read_sender_in_flight())
                self.assertIsNone(setup["lock"].read())

    def test_production_style_unsupported_shape_is_rejected_before_live_preflight(self):
        for kinds in (
            ("txt", "txt", "bmp", "txt"),
            ("txt", "bmp", "txt", "txt", "txt"),
        ):
            with self.subTest(child_kinds=kinds):
                setup = self._setup(
                    child_kinds=kinds,
                    include_operation_binding=False,
                )
                self.addCleanup(setup["temporary"].cleanup)
                with self.assertRaises(LibraryTransferExecutionError):
                    setup["facade"].refresh_live_preflight(
                        setup["plan"],
                        catalog=setup["catalog"],
                        preflight_report_path=setup["root"] / "blocked" / "sealed.json",
                        bundle_path=setup["root"] / "blocked" / "bundle.json",
                    )
                self.assertIsNone(setup["facade"].operation_binding)
                self.assertEqual(setup["captures"], [])
                self.assertEqual(setup["backend"].calls, [])
                self.assertEqual(self._claim_count(setup), 0)
                self.assertIsNone(setup["claim_store"].read_sender_in_flight())
                self.assertIsNone(setup["lock"].read())

    def test_unsupported_package_shapes_remain_host_only(self):
        for label, kinds in (
            ("two-leaf", ("txt", "bmp")),
            ("reordered-four-leaf", ("txt", "txt", "bmp", "txt")),
            ("five-leaf", ("txt", "bmp", "txt", "txt", "txt")),
        ):
            with self.subTest(shape=label):
                setup = self._setup(child_kinds=kinds)
                self.addCleanup(setup["temporary"].cleanup)
                logical_plan = self._generic_exact_plan(setup)
                self.assertIsNone(
                    _exact_live_package_artifact(setup["item"], logical_plan)
                )
                self.assertFalse(
                    logical_plan.to_dict()["safety"]["candidate_constructed"]
                )

    def test_batch_nested_and_non_root_selections_cannot_map_to_live_package(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        snapshot = DeviceLibrarySnapshot(
            (DeviceLibraryNode(DEVICE_ROOT_PATH, "directory", 0, system=True),)
        )
        second_source = setup["root"] / "unrelated.txt"
        second_source.write_text("unrelated\n", encoding="utf-8")
        second_item = setup["catalog"].import_file(second_source)
        batch_plan = build_library_device_transfer_plan(
            setup["catalog"],
            [setup["item"].item_id, second_item.item_id],
            DEVICE_ROOT_PATH,
            snapshot,
        )
        self.assertIsNone(_exact_live_package_artifact(setup["item"], batch_plan))

        for kind in ("txt", "bmp"):
            with self.subTest(single_leaf=kind):
                source = setup["root"] / f"unprepared.{kind}"
                if kind == "txt":
                    source.write_text("unprepared\n", encoding="utf-8")
                else:
                    source.write_bytes(make_profile_bmp())
                leaf = setup["catalog"].import_file(source)
                single_plan = build_library_device_transfer_plan(
                    setup["catalog"],
                    [leaf.item_id],
                    DEVICE_ROOT_PATH,
                    snapshot,
                )
                self.assertIsNone(_exact_live_package_artifact(leaf, single_plan))

        books = DeviceLibrarySnapshot(
            (
                DeviceLibraryNode(DEVICE_ROOT_PATH, "directory", 0, system=True),
                DeviceLibraryNode(("root", "Books"), "directory", 0),
            )
        )
        nested_destination_plan = build_library_device_transfer_plan(
            setup["catalog"],
            [setup["item"].item_id],
            ("root", "Books"),
            books,
        )
        self.assertIsNone(
            _exact_live_package_artifact(setup["item"], nested_destination_plan)
        )

        nested_source = setup["root"] / "nested-source"
        nested_child = nested_source / "Part"
        nested_child.mkdir(parents=True)
        (nested_source / "01-introduction.txt").write_text("intro\n", encoding="utf-8")
        (nested_child / "02-page-01.bmp").write_bytes(make_profile_bmp())
        (nested_child / "03-ending.txt").write_text("end\n", encoding="utf-8")
        folder_item = setup["catalog"].import_folder(nested_source)
        nested_plan = build_library_device_transfer_plan(
            setup["catalog"],
            [folder_item.item_id],
            DEVICE_ROOT_PATH,
            snapshot,
        )
        self.assertIsNone(_exact_live_package_artifact(folder_item, nested_plan))

    def test_p18_025_fresh_target_reaches_host_ready_through_normal_facade(self):
        setup = self._setup(target=FRESH_TEST_TARGET)
        self.addCleanup(setup["temporary"].cleanup)
        self._patch_template_hashes(setup)

        prepared = self._prepare(setup)

        self.assertTrue(prepared.ready)
        review = prepared.review.to_dict()
        self.assertEqual(
            review["package"]["folder_path"],
            f"root\\{FRESH_TEST_TARGET}",
        )
        self.assertEqual(
            review["operation_identity"]["operation_id"],
            setup["binding"].operation_id,
        )
        self.assertEqual(
            review["operation_identity"]["candidate_blob_length"],
            prepared.preflight.candidate.audit_dict()["candidate"]["blob_length"],
        )
        self.assertEqual(
            review["operation_identity"]["transaction_payload_length"],
            prepared.preflight.candidate.audit_dict()["transaction"]["payload_length"],
        )
        self.assertNotIn("20260910", setup["binding"].operation_id)
        self.assertEqual(setup["backend"].calls, [])
        self.assertEqual(self._claim_count(setup), 0)

    def test_p18_025_host_readiness_never_enters_write_boundary(self):
        setup = self._setup(target=FRESH_TEST_TARGET)
        self.addCleanup(setup["temporary"].cleanup)

        prepared = self._prepare(setup)

        self.assertTrue(prepared.ready)
        self.assertEqual(setup["backend"].calls, [])
        self.assertEqual(self._claim_count(setup), 0)
        self.assertIsNone(setup["claim_store"].read_sender_in_flight())
        self.assertIsNone(setup["lock"].read())
        review = prepared.review.to_dict()
        self.assertFalse(review["eligibility"]["execution_action_exposed"])
        self.assertEqual(review["safety"]["device_change"], "none")

    def test_p18_025_prior_target_is_not_privileged(self):
        current = LibraryTransferOperationBinding(
            target_folder_name=FRESH_TEST_TARGET,
            owner_approval_phrase=FRESH_OWNER_APPROVAL,
        )
        prior = LibraryTransferOperationBinding(
            target_folder_name=HISTORICAL_P18_021_TARGET,
            owner_approval_phrase=FRESH_OWNER_APPROVAL,
        )

        self.assertNotEqual(current.operation_id, prior.operation_id)
        self.assertNotEqual(current.target_folder_name, HISTORICAL_P18_021_TARGET)
        self.assertNotIn(HISTORICAL_P18_021_TARGET, current.to_dict()["target_folder_name"])
        self.assertNotEqual(current.target_folder_name, HISTORICAL_P18_023_TARGET)
        self.assertNotIn(HISTORICAL_P18_023_TARGET, current.to_dict()["target_folder_name"])
        with self.assertRaises(ValueError):
            LibraryTransferOperationBinding(
                target_folder_name=FRESH_TEST_TARGET,
                owner_approval_phrase="APPROVE P18-022 FRESH OPERATION IDENTITY",
            )

    def test_replacing_binding_after_preflight_invalidates_actionability(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        prepared = self._prepare(setup)
        setup["facade"].operation_binding = LibraryTransferOperationBinding(
            target_folder_name="Another Fresh Target",
            owner_approval_phrase="APPROVE ANOTHER FRESH VNW-V15 VALIDATION 01",
        )

        self.assertFalse(setup["facade"].transfer_actionable)
        with self.assertRaises(LibraryTransferExecutionError):
            setup["facade"].execute_once(
                prepared.plan_report,
                confirmation_interaction=lambda _review: "ADD Another Fresh Target ONCE",
            )
        self.assertEqual(setup["backend"].calls, [])
        self.assertEqual(self._claim_count(setup), 0)

    def test_normal_facade_and_adapter_have_no_historical_20260910_dependency(self):
        root = Path(__file__).parents[1]
        for relative in (
            "src/infocarry/library_transfer_execution.py",
            "src/infocarry/prepared_library_package_live_adapter.py",
            "src/infocarry/desktop_ttk.py",
        ):
            source = (root / relative).read_text(encoding="utf-8")
            self.assertNotIn("IC_P18_LIBRARY_20260910_01", source)
            self.assertNotIn("vnw-v15-library-ui-validation-20260910-01", source)

    def test_p18_021_strings_and_scalar_capacity_cannot_unlock_execution(self):
        for marker in ("P18-015", "P18-018", "P18-021", "P18-022", "P18-023"):
            with self.subTest(marker=marker):
                with self.assertRaises(ValueError):
                    LibraryTransferOperationBinding(
                        target_folder_name=FRESH_TEST_TARGET,
                        owner_approval_phrase=f"APPROVE {marker} V15 UI PHYSICAL VALIDATION 01",
                    )
                with self.assertRaises(ValueError):
                    LibraryTransferOperationBinding(
                        target_folder_name=FRESH_TEST_TARGET,
                        confirmation_phrase=f"historical {marker} confirmation",
                    )
        with self.assertRaises(ValueError):
            LibraryTransferOperationBinding(
                target_folder_name=FRESH_TEST_TARGET,
                confirmation_phrase=f"ADD {HISTORICAL_P18_023_TARGET} ONCE",
            )

        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        self._patch_template_hashes(setup)
        offline = dict(setup["plan"])
        offline["capacity"] = {
            "status": "sufficient",
            "available_bytes": 10_000_000,
            "lower_bound_bytes": 1,
        }
        self.assertFalse(setup["facade"].transfer_actionable)
        with self.assertRaises(LibraryTransferExecutionError):
            setup["facade"].execute_once(
                offline,
                confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
            )
        self.assertEqual(setup["backend"].calls, [])
        self.assertEqual(self._claim_count(setup), 0)

    def test_fresh_capacity_replaces_offline_plan_in_the_normal_readiness_state(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        self._patch_template_hashes(setup)
        offline_plan = build_library_transfer_queue_plan(
            setup["catalog"],
            selected_item_ids=[setup["item"].item_id],
            selection_mode=SELECTION_SELECTED,
            backup=setup["baseline"],
        ).to_dict()
        self.assertFalse(offline_plan["eligibility"]["queue_ready"])
        self.assertEqual(offline_plan["capacity"]["available_bytes"], None)
        self.assertIn("capacity was not supplied", " ".join(offline_plan["eligibility"]["reasons"]))

        prepared = setup["facade"].refresh_live_preflight(
            offline_plan,
            catalog=setup["catalog"],
            preflight_report_path=setup["root"] / "fresh" / "sealed-preflight.json",
            bundle_path=setup["root"] / "fresh" / "operation-bundle.json",
        )
        fresh_plan = prepared.plan_report

        self.assertTrue(fresh_plan["eligibility"]["queue_ready"])
        self.assertEqual(fresh_plan["capacity"]["status"], "sufficient_for_lower_bound_only")
        self.assertEqual(fresh_plan["capacity"]["source"], "fresh_native_0x0019")
        self.assertEqual(
            fresh_plan["capacity"]["native_response_sha256"],
            prepared.preflight.capacity_response.raw_response_sha256,
        )
        self.assertEqual(
            fresh_plan["capacity"]["available_bytes"],
            prepared.preflight.capacity_response.capacity_limit_bytes,
        )
        self.assertNotIn("capacity was not supplied", " ".join(fresh_plan["eligibility"]["reasons"]))
        self.assertTrue(prepared.readiness.host_profile_eligible)
        self.assertTrue(prepared.ready)
        self.assertTrue(setup["facade"].transfer_actionable)
        self.assertIsNone(setup["claim_store"].read_sender_in_flight())
        self.assertIsNone(setup["lock"].read())
        self.assertEqual(setup["backend"].calls, [])

    def test_fresh_capacity_failures_remain_blocked_before_claim_or_sender(self):
        for label, query_capacity in (
            ("missing", lambda: None),
            ("malformed", lambda: RawInfoResponse(0x0019, "malformed", b"bad")),
            ("insufficient", lambda: _capacity_response_with_limit(1)),
        ):
            with self.subTest(label=label):
                setup = self._setup()
                self.addCleanup(setup["temporary"].cleanup)
                self._patch_template_hashes(setup)
                setup["facade"].runtime = replace(
                    setup["facade"].runtime,
                    query_capacity=query_capacity,
                )
                with self.assertRaises(LibraryTransferExecutionError):
                    setup["facade"].refresh_live_preflight(
                        setup["plan"],
                        catalog=setup["catalog"],
                        preflight_report_path=setup["root"] / label / "sealed.json",
                        bundle_path=setup["root"] / label / "bundle.json",
                    )
                self.assertFalse(setup["facade"].transfer_actionable)
                self.assertIsNone(setup["claim_store"].read_sender_in_flight())
                self.assertIsNone(setup["lock"].read())
                self.assertEqual(setup["backend"].calls, [])

    def test_stale_or_historical_capacity_cannot_unlock_a_changed_operation(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        prepared = self._prepare(setup)
        stale_plan = deepcopy(prepared.plan_report)
        stale_plan["capacity"]["available_bytes"] = 10_000_000
        with self.assertRaisesRegex(LibraryTransferExecutionError, "plan changed"):
            setup["facade"].execute_once(
                stale_plan,
                confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
            )
        self.assertIsNone(setup["claim_store"].read_sender_in_flight())
        self.assertEqual(setup["backend"].calls, [])

        self.assertFalse(
            LibraryTransferExecutionFacade(
                operation_binding=setup["binding"],
            ).transfer_actionable
        )

    def test_shape_collision_capacity_and_v10_substitution_are_blocked(self):
        for label, mutation in (
            (
                "multiple selection",
                lambda value: value["selection"].update(
                    selected_item_ids=["one", "two"]
                ),
            ),
            (
                "wrong child count",
                lambda value: value["items"][0]["prepared_artifact"].update(
                    ordered_children=value["items"][0]["prepared_artifact"]["ordered_children"][:2]
                ),
            ),
            (
                "wrong child order",
                lambda value: value["items"][0]["prepared_artifact"].update(
                    ordered_children=list(reversed(value["items"][0]["prepared_artifact"]["ordered_children"]))
                ),
            ),
            (
                "nesting",
                lambda value: value["items"][0]["prepared_artifact"]["ordered_children"][0].update(
                    path=f"root\\{setup['binding'].target_folder_name}\\nested\\01-introduction.txt"
                ),
            ),
            (
                "destination collision",
                lambda value: value["items"][0].update(
                    conflicts=[{"path": "root\\IC_P18_LIBRARY_20260910_01"}]
                ),
            ),
            (
                "insufficient capacity",
                lambda value: value["items"][0].update(
                    capacity={
                        "status": "insufficient_for_lower_bound",
                        "lower_bound_bytes": 10_000_000,
                        "available_bytes": 1,
                    },
                    reasons=["available capacity is below the package lower bound"],
                ),
            ),
            (
                "V10 substitution",
                lambda value: value.update(device_model_profile_id="sony-vnw-v10-uncharacterized"),
            ),
        ):
            with self.subTest(label=label):
                setup = self._setup()
                self.addCleanup(setup["temporary"].cleanup)
                changed = deepcopy(setup["plan"])
                mutation(changed)
                readiness = setup["facade"].review_readiness(changed)
                self.assertFalse(readiness.host_profile_eligible)
                self.assertFalse(readiness.transfer_enabled)

    def test_missing_auxiliary_policy_and_stale_backup_are_blocked_before_send(self):
        setup = self._setup(auxiliary_state=False)
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaises(LibraryTransferExecutionError):
            self._prepare(setup)
        self.assertEqual(setup["backend"].calls, [])

        stale = self._setup()
        self.addCleanup(stale["temporary"].cleanup)
        self._patch_template_hashes(stale)
        stale["facade"].runtime = LibraryTransferExecutionRuntime(
            **{
                **stale["facade"].runtime.__dict__,
                "max_age_seconds": 0,
            }
        )
        with self.assertRaises(LibraryTransferExecutionError):
            stale["facade"].refresh_live_preflight(
                stale["plan"],
                catalog=stale["catalog"],
                preflight_report_path=stale["root"] / "stale" / "sealed.json",
                bundle_path=stale["root"] / "stale" / "bundle.json",
            )

    def test_changed_plan_wrong_confirmation_and_cancel_consume_nothing(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        self._prepare(setup)
        changed = deepcopy(setup["plan"])
        changed["items"][0]["prepared_artifact"]["ordered_children"][0]["source_bytes"] += 1
        with self.assertRaises(LibraryTransferExecutionError):
            setup["facade"].execute_once(
                changed,
                confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
            )
        self.assertFalse(setup["facade"].transfer_actionable)
        with self.assertRaises(Exception):
            setup["facade"].execute_once(
                setup["plan"],
                confirmation_interaction=lambda _review: "WRONG CONFIRMATION",
            )
        with self.assertRaises(Exception):
            setup["facade"].execute_once(
                setup["plan"],
                confirmation_interaction=lambda _review: "",
            )
        self.assertIsNone(setup["claim_store"].read_sender_in_flight())
        self.assertEqual(setup["backend"].calls, [])

    def test_indeterminate_post_start_is_locked_and_never_retried(self):
        setup = self._setup(backend=PackageWorkflowBackend(bulk_error=OSError("disconnect")))
        self.addCleanup(setup["temporary"].cleanup)
        self._prepare(setup)
        with self.assertRaises(Exception) as raised:
            setup["facade"].execute_once(
                setup["plan"],
                confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
            )
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertIsNotNone(setup["lock"].read())
        self.assertEqual(
            len(
                [
                    call
                    for call in setup["backend"].calls
                    if call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
                ]
            ),
            1,
        )
        self.assertEqual(self._claim_count(setup), 1)
        with self.assertRaises(Exception):
            setup["facade"].execute_once(
                setup["plan"],
                confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
            )
        self.assertEqual(
            sum(
                call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
                for call in setup["backend"].calls
            ),
            1,
        )

    def test_sender_session_close_failure_after_completion_is_locked_as_indeterminate(self):
        backend = PackageWorkflowBackend()

        def fail_close():
            raise OSError("simulated USB session close failure")

        backend.close = fail_close
        setup = self._setup(backend=backend)
        self.addCleanup(setup["temporary"].cleanup)
        self._prepare(setup)

        with self.assertRaises(LibraryTransferExecutionError) as raised:
            setup["facade"].execute_once(
                setup["plan"],
                confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
            )

        self.assertEqual(
            raised.exception.state,
            "indeterminate_after_transaction_start",
        )
        self.assertEqual(
            raised.exception.audit["native_completion_observed"],
            "0x0000",
        )
        self.assertIsNotNone(setup["lock"].read())
        self.assertIsNotNone(setup["claim_store"].read_sender_in_flight())
        self.assertEqual(
            sum(
                call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
                for call in backend.calls
            ),
            1,
        )
        self.assertEqual(self._claim_count(setup), 1)
        with self.assertRaises(Exception):
            setup["facade"].execute_once(
                setup["plan"],
                confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
            )
        self.assertEqual(
            len(
                [
                    call
                    for call in setup["backend"].calls
                    if call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
                ]
            ),
            1,
        )

    def test_nonzero_completion_consumes_once_but_does_not_retry_or_lock(self):
        setup = self._setup(backend=PackageWorkflowBackend(completions=(1,)))
        self.addCleanup(setup["temporary"].cleanup)
        self._prepare(setup)
        with self.assertRaises(Exception) as raised:
            setup["facade"].execute_once(
                setup["plan"],
                confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
            )
        self.assertEqual(raised.exception.state, "failed")
        self.assertIsNone(setup["lock"].read())
        self.assertIsNone(setup["claim_store"].read_sender_in_flight())
        self.assertEqual(
            len(
                [
                    call
                    for call in setup["backend"].calls
                    if call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
                ]
            ),
            1,
        )
        connection = sqlite3.connect(setup["claim_store"].path)
        try:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM execution_claims").fetchone()[0],
                1,
            )
        finally:
            connection.close()

    def test_post_backup_and_terminal_readback_failures_are_indeterminate(self):
        for mode in ("no_backup", "stale_readback"):
            with self.subTest(mode=mode):
                setup = self._setup(after_mode=mode)
                self.addCleanup(setup["temporary"].cleanup)
                self._prepare(setup)
                with self.assertRaises(Exception) as raised:
                    setup["facade"].execute_once(
                        setup["plan"],
                        confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
                    )
                self.assertEqual(
                    raised.exception.state,
                    "indeterminate_after_transaction_start",
                )
                self.assertIsNotNone(setup["lock"].read())
                self.assertEqual(
                    len(
                        [
                            call
                            for call in setup["backend"].calls
                            if call[0] == "control_out"
                            and call[1] == REQUEST_BEGIN_TRANSMIT
                        ]
                    ),
                    1,
                )

    def test_reconciliation_failure_preserves_indeterminate_state_at_facade(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        self._prepare(setup)
        reconciliation_error = PreparedLibraryPackageLiveResultReconciliationError(
            "independent terminal read-back could not be completed",
            stage="independent_readback",
        )
        with patch.object(
            experimental_transfer_module,
            "reconcile_prepared_library_package_live_result",
            side_effect=reconciliation_error,
        ):
            with self.assertRaises(LibraryTransferExecutionError) as raised:
                setup["facade"].execute_once(
                    setup["plan"],
                    confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
                )
        self.assertEqual(
            raised.exception.state,
            "indeterminate_after_transaction_start",
        )
        self.assertIn("indeterminate_write_lock", raised.exception.audit)
        self.assertIsNotNone(setup["lock"].read())
        self.assertEqual(self._claim_count(setup), 1)
        self.assertEqual(
            len(
                [
                    call
                    for call in setup["backend"].calls
                    if call[0] == "control_out"
                    and call[1] == REQUEST_BEGIN_TRANSMIT
                ]
            ),
            1,
        )

    def test_operation_bundle_tampering_is_rejected_before_claim(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        prepared = self._prepare(setup)
        tampered_bundle = replace(
            prepared.operation_bundle,
            operation_id="vnw-v15-library-ui-validation-tampered",
        )
        setup["facade"]._prepared_operation = replace(
            prepared,
            operation_bundle=tampered_bundle,
        )
        with self.assertRaises(LibraryTransferExecutionError):
            setup["facade"].execute_once(
                setup["plan"],
                confirmation_interaction=lambda _review: FRESH_CONFIRMATION,
            )
        self.assertEqual(setup["backend"].calls, [])
        self.assertEqual(self._claim_count(setup), 0)

    def test_normal_facade_without_authorized_runtime_cannot_execute(self):
        facade = LibraryTransferExecutionFacade()
        self.assertFalse(facade.can_prepare_live)
        self.assertFalse(facade.transfer_actionable)
        with self.assertRaises(LibraryTransferExecutionError):
            facade.execute_once({}, confirmation_interaction=lambda _review: FRESH_CONFIRMATION)

    def test_historical_identity_cannot_become_fresh_binding(self):
        with self.assertRaises(ValueError):
            LibraryTransferOperationBinding(
                target_folder_name=FRESH_TEST_TARGET,
                operation_id="vnw-v15-library-ui-validation-20260910-01",
            )
        with self.assertRaises(ValueError):
            LibraryTransferOperationBinding(
                target_folder_name=FRESH_TEST_TARGET,
                owner_approval_phrase="historical P18-015 approval",
            )
        with self.assertRaises(ValueError):
            LibraryTransferOperationBinding(
                target_folder_name=FRESH_TEST_TARGET,
                confirmation_phrase="ADD IC_P18_LIBRARY_20260910_01 ONCE",
            )
        with self.assertRaises(ValueError):
            LibraryTransferOperationBinding(
                target_folder_name=FRESH_TEST_TARGET,
                confirmation_phrase="ADD IC_P18_LIBRARY_20260913_01 ONCE",
            )
        with self.assertRaises(ValueError):
            LibraryTransferOperationBinding(
                target_folder_name=FRESH_TEST_TARGET,
                confirmation_phrase=f"ADD {HISTORICAL_P18_023_TARGET} ONCE",
            )

    def test_wrong_model_is_rejected_before_read_only_preflight(self):
        setup = self._setup(detected=(0x054C, 0x001F))
        self.addCleanup(setup["temporary"].cleanup)
        self._patch_template_hashes(setup)
        with self.assertRaises(LibraryTransferExecutionError):
            setup["facade"].refresh_live_preflight(
                setup["plan"],
                catalog=setup["catalog"],
                preflight_report_path=setup["root"] / "bad" / "sealed.json",
                bundle_path=setup["root"] / "bad" / "bundle.json",
            )
        self.assertEqual(setup["backend"].calls, [])


if __name__ == "__main__":
    unittest.main()
