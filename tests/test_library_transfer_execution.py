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
from infocarry.library import LibraryCatalog
from infocarry.library_transfer_execution import (
    FRESH_AUXILIARY_STATE_POLICY,
    FRESH_CONFIRMATION,
    FRESH_VALIDATION_TARGET,
    HISTORICAL_P18_015_OWNER_APPROVAL,
    HISTORICAL_P18_015_TARGET,
    LibraryTransferExecutionError,
    LibraryTransferExecutionFacade,
    LibraryTransferExecutionRuntime,
    LibraryTransferOperationBinding,
)
from infocarry.library_transfer_plan import (
    SELECTION_SELECTED,
    build_library_transfer_queue_plan,
)
from infocarry.prepared_media_package import (
    build_prepared_media_package,
    export_prepared_media_package,
)
from infocarry.prepared_library_package_operation_bundle import load_operation_bundle
from infocarry.execution_claim_store import PersistentExecutionClaimStore
from infocarry.indeterminate_write_lock import PersistentIndeterminateWriteLock
from infocarry.write_protocol import REQUEST_BEGIN_TRANSMIT
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


class LibraryTransferExecutionFacadeTests(unittest.TestCase):
    def _setup(
        self,
        *,
        backend=None,
        detected=(0x054C, 0x001E),
        auxiliary_state=True,
        after_mode=None,
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

        intro = root / "intro.txt"
        image = root / "page.bmp"
        ending = root / "ending.txt"
        intro.write_text("Introduction\n日本語\n", encoding="utf-8")
        image.write_bytes(make_profile_bmp())
        ending.write_text("The End\n", encoding="utf-8")
        package = build_prepared_media_package(
            (
                (intro, "01-introduction.txt"),
                (image, "02-page-01.bmp"),
                (ending, "03-ending.txt"),
            ),
            FRESH_VALIDATION_TARGET,
        )
        package_root = export_prepared_media_package(package, root / "package")
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

        binding = LibraryTransferOperationBinding(
            owner_approval_phrase="APPROVE FRESH VNW-V15 UI VALIDATION 01",
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
            "backend": runtime.backend,
            "claim_store": claim_store,
            "lock": lock,
            "binding": binding,
        }

    def _prepare(self, setup):
        self._patch_template_hashes(setup)
        prepared = setup["facade"].refresh_live_preflight(
            setup["plan"],
            catalog=setup["catalog"],
            preflight_report_path=setup["root"] / "operation" / "sealed-preflight.json",
            bundle_path=setup["root"] / "operation" / "operation-bundle.json",
        )
        setup["candidate_holder"]["candidate"] = prepared.preflight.candidate
        return prepared

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
        with sqlite3.connect(setup["claim_store"].path) as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM execution_claims").fetchone()[0],
                1,
            )
        self.assertIsNone(setup["claim_store"].read_sender_in_flight())
        self.assertIsNone(setup["lock"].read())

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
                    path="root\\IC_P18_LIBRARY_20260910_01\\nested\\01-introduction.txt"
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
        with sqlite3.connect(setup["claim_store"].path) as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM execution_claims").fetchone()[0],
                1,
            )
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
        with sqlite3.connect(setup["claim_store"].path) as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM execution_claims").fetchone()[0],
                1,
            )

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
        with sqlite3.connect(setup["claim_store"].path) as connection:
            self.assertEqual(
                connection.execute("SELECT count(*) FROM execution_claims").fetchone()[0],
                0,
            )

    def test_normal_facade_without_authorized_runtime_cannot_execute(self):
        facade = LibraryTransferExecutionFacade()
        self.assertFalse(facade.can_prepare_live)
        self.assertFalse(facade.transfer_actionable)
        with self.assertRaises(LibraryTransferExecutionError):
            facade.execute_once({}, confirmation_interaction=lambda _review: FRESH_CONFIRMATION)

    def test_historical_identity_cannot_become_fresh_binding(self):
        with self.assertRaises(ValueError):
            LibraryTransferOperationBinding(target_folder_name=HISTORICAL_P18_015_TARGET)
        with self.assertRaises(ValueError):
            LibraryTransferOperationBinding(
                owner_approval_phrase=HISTORICAL_P18_015_OWNER_APPROVAL
            )
        with self.assertRaises(ValueError):
            LibraryTransferOperationBinding(
                confirmation_phrase=f"ADD {HISTORICAL_P18_015_TARGET} ONCE"
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
