import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from infocarry.experimental_library_transfer_review import (
    EXPERIMENTAL_CONFIRMATION,
    EXPERIMENTAL_CONFIRMATION_POLICY,
    EXPERIMENTAL_OWNER_APPROVAL,
    EXPERIMENTAL_TARGET_FOLDER,
    ExperimentalLibraryTransferReviewError,
    build_experimental_library_transfer_review,
)
from infocarry.experimental_transfer_contract import (
    APPLICATION_TRANSFER_STAGES,
    EXPERIMENTAL_FAILURE_BOUNDARIES,
    experimental_safety_contract,
)
import infocarry.experimental_library_transfer as integration
from infocarry.indeterminate_write_lock import PersistentIndeterminateWriteLock
from infocarry.execution_claim_store import PersistentExecutionClaimStore


def _paths():
    return [
        f"root\\{EXPERIMENTAL_TARGET_FOLDER}",
        f"root\\{EXPERIMENTAL_TARGET_FOLDER}\\01-introduction.txt",
        f"root\\{EXPERIMENTAL_TARGET_FOLDER}\\02-page-01.bmp",
        f"root\\{EXPERIMENTAL_TARGET_FOLDER}\\03-ending.txt",
    ]


def _plan(*, selected_ids=None, children=None, paths=None):
    children = children or [
        {"order": 0, "kind": "txt", "name": "01-introduction.txt", "path": _paths()[1], "source_sha256": "1" * 64, "source_bytes": 12, "prepared_payload_sha256": "2" * 64, "prepared_payload_bytes": 12},
        {"order": 1, "kind": "bmp", "name": "02-page-01.bmp", "path": _paths()[2], "source_sha256": "3" * 64, "source_bytes": 9662, "prepared_payload_sha256": "4" * 64, "prepared_payload_bytes": 9662},
        {"order": 2, "kind": "txt", "name": "03-ending.txt", "path": _paths()[3], "source_sha256": "5" * 64, "source_bytes": 8, "prepared_payload_sha256": "6" * 64, "prepared_payload_bytes": 8},
    ]
    return {
        "format": "infocarry-library-transfer-plan-v1",
        "state": "previewed_offline",
        "usb_accessed": False,
        "device_change": "none",
        "selection": {"mode": "selected", "selected_item_ids": ["item-1"] if selected_ids is None else selected_ids},
        "grouping": {"automatic_grouping": False, "overlap_status": "none"},
        "eligibility": {
            "offline_review_ready": True,
            "queue_ready": True,
            "device_candidate_eligible": False,
            "transfer_enabled": False,
        },
        "safety": {
            "source_mutated": False,
            "catalog_mutated": False,
            "candidate_constructed": False,
            "authorization_created": False,
            "transaction_constructed": False,
            "sender_called": False,
            "automatic_retry": False,
        },
        "items": [{
            "item_id": "item-1",
            "operation_type": "prepared_flat_typed_package",
            "execution_eligible": False,
            "prepared_artifact": {
                "contract": "infocarry-prepared-typed-media-package-v1",
                "manifest_sha256": "f" * 64,
                "source_bytes": 123,
                "prepared_payload_bytes": 9682,
                "ordered_children": children,
            },
            "destination": {"paths": _paths() if paths is None else paths},
            "conflicts": [],
            "queue_ready": True,
        }],
    }


def _bundle():
    digest = "a" * 64
    return {
        "format": "infocarry-p17-017-library-package-operation-bundle-v1",
        "bundle_sha256": "b" * 64,
        "device_identity": ["0x054c", "0x001e"],
        "expected_folder_name": EXPERIMENTAL_TARGET_FOLDER,
        "owner_approval_phrase": EXPERIMENTAL_OWNER_APPROVAL,
        "confirmation_phrase": EXPERIMENTAL_CONFIRMATION,
        "confirmation_policy": EXPERIMENTAL_CONFIRMATION_POLICY,
        "safety": {
            "automatic_retry_allowed": False,
            "max_sender_calls": 1,
            "transaction_request": "0x101b",
            "accepted_completion": "0x0000",
        },
        "package_children": [
            {"order": 0, "kind": "txt", "name": "01-introduction.txt", "source_sha256": "1" * 64, "source_bytes": 12, "prepared_payload_sha256": "2" * 64, "prepared_payload_bytes": 12},
            {"order": 1, "kind": "bmp", "name": "02-page-01.bmp", "source_sha256": "3" * 64, "source_bytes": 9662, "prepared_payload_sha256": "4" * 64, "prepared_payload_bytes": 9662},
            {"order": 2, "kind": "txt", "name": "03-ending.txt", "source_sha256": "5" * 64, "source_bytes": 8, "prepared_payload_sha256": "6" * 64, "prepared_payload_bytes": 8},
        ],
        "expected_post_operation": {"added_paths": _paths()},
        "candidate_blob_sha256": digest,
        "transaction_sha256": "c" * 64,
        "preflight_seal_sha256": "d" * 64,
        "core_preflight_seal_sha256": "e" * 64,
        "baseline_state_identity_sha256": "1" * 64,
        "capacity_response_sha256": "2" * 64,
        "candidate_audit_sha256": "3" * 64,
        "authorization_sha256": "4" * 64,
        "expected_post_operation_sha256": "5" * 64,
        "library_binding_sha256": "6" * 64,
        "fixed_state_policy": "capture7_exact_all_zero_fixed_state",
        "fixed_state_before_sha256": ["7" * 64] * 5,
        "fixed_state_candidate_sha256": ["7" * 64] * 5,
        "bookmark_binding_sha256": "8" * 64,
    }


def _preflight():
    bundle = _bundle()
    return {
        "state": "ready_for_hardware_test_host_only",
        "profile": "one_selected_library_item_root_txt_bmp_txt",
        "device_identity": ["0x054c", "0x001e"],
        "expected_folder_name": EXPERIMENTAL_TARGET_FOLDER,
        "owner_approval_phrase": EXPERIMENTAL_OWNER_APPROVAL,
        "confirmation_phrase": EXPERIMENTAL_CONFIRMATION,
        "confirmation_policy": EXPERIMENTAL_CONFIRMATION_POLICY,
        "read_only_preflight": True,
        "device_changing_operation_performed": False,
        "usb_transmission_performed": False,
        "target_absent_from_fresh_backup": True,
        "approval_consumed": False,
        "write_started": False,
        "sender_calls": 0,
        "backend_write_calls": 0,
        "send_count": 0,
        "completion": None,
        "automatic_retry_allowed": False,
        "normal_gui_cli_transfer_exposed": False,
        "preflight_seal_sha256": bundle["preflight_seal_sha256"],
        "core_preflight_seal_sha256": bundle["core_preflight_seal_sha256"],
        "candidate": {
            "candidate": {"blob_sha256": bundle["candidate_blob_sha256"], "blob_length": 100},
            "package": {
                "paths": _paths(),
                "prepared_manifest_sha256": "f" * 64,
                "ordered_items": [
                    {"order": 0, "kind": "txt", "path": _paths()[1], "source_sha256": "1" * 64, "source_bytes": 12, "prepared_payload_sha256": "2" * 64},
                    {"order": 1, "kind": "bmp", "path": _paths()[2], "source_sha256": "3" * 64, "source_bytes": 9662, "prepared_payload_sha256": "4" * 64},
                    {"order": 2, "kind": "txt", "path": _paths()[3], "source_sha256": "5" * 64, "source_bytes": 8, "prepared_payload_sha256": "6" * 64},
                ],
            },
            "allocation": {
                "candidate_growth_bytes": 16036,
                "capacity_limit_bytes": 3145728,
                "remaining_growth_bytes": 1070472,
                "baseline_model_bytes": 2075256,
                "candidate_model_bytes": 2091292,
            },
            "policy": {"fixed_state": bundle["fixed_state_policy"]},
        },
        "authorization": {
            "candidate_transaction_sha256": bundle["transaction_sha256"],
            "fixed_state_policy": bundle["fixed_state_policy"],
            "fixed_state_before_sha256": bundle["fixed_state_before_sha256"],
            "fixed_state_candidate_sha256": bundle["fixed_state_candidate_sha256"],
            "bookmark_binding_sha256": bundle["bookmark_binding_sha256"],
        },
    }


class ExperimentalLibraryTransferReviewTests(unittest.TestCase):
    def test_exact_package_without_sealed_preflight_is_preview_only(self):
        review = build_experimental_library_transfer_review(_plan()).to_dict()

        self.assertEqual(review["eligibility"]["state"], "preview_only")
        self.assertFalse(review["candidate"]["available"])
        self.assertIn("fresh complete verified backup", " ".join(review["eligibility"]["reasons"]))
        self.assertFalse(review["safety"]["usb_accessed"])

    def test_exact_sealed_package_reports_hash_only_hardware_readiness(self):
        review = build_experimental_library_transfer_review(
            _plan(), preflight_report=_preflight(), bundle_report=_bundle(), audit_location="/external/audit"
        ).to_dict()

        self.assertEqual(review["eligibility"]["state"], "ready_for_hardware_test")
        self.assertTrue(review["candidate"]["available"])
        self.assertEqual(review["candidate"]["candidate_blob_sha256"], "a" * 64)
        self.assertEqual(review["operation_identity"]["transaction_sha256"], "c" * 64)
        self.assertEqual(review["verification"]["audit_location"], "/external/audit")
        self.assertFalse(review["eligibility"]["execution_action_exposed"])
        self.assertFalse(review["safety"]["candidate_bytes_included"])
        self.assertEqual(
            review["safety"]["contract"]["terminal_failure_boundaries"],
            list(EXPERIMENTAL_FAILURE_BOUNDARIES),
        )

    def test_stale_or_mutated_approval_never_reports_hardware_readiness(self):
        cases = (
            ("owner_approval_phrase", "APPROVE P17-003 MODERN LIBRARY PACKAGE SMOKE 01"),
            ("confirmation_phrase", "CONFIRM P17-003 ONE INFOCARRY MULTI-CHILD PACKAGE"),
            ("confirmation_policy", "fixed_confirmation_phrase_v1"),
        )
        for location in ("preflight", "bundle"):
            for field, stale_value in cases:
                with self.subTest(location=location, field=field):
                    preflight = _preflight()
                    bundle = _bundle()
                    (preflight if location == "preflight" else bundle)[field] = stale_value
                    review = build_experimental_library_transfer_review(
                        _plan(), preflight_report=preflight, bundle_report=bundle
                    )
                    self.assertFalse(review.ready_for_hardware_test)

    def test_multiple_selection_is_never_a_package(self):
        review = build_experimental_library_transfer_review(
            _plan(selected_ids=["item-1", "item-2"])
        ).to_dict()

        self.assertEqual(review["eligibility"]["state"], "preview_only")
        self.assertIn("multiple rows are never merged", " ".join(review["eligibility"]["reasons"]))

    def test_wrong_order_is_preview_only(self):
        children = list(_plan()["items"][0]["prepared_artifact"]["ordered_children"])
        children[1], children[2] = children[2], children[1]
        review = build_experimental_library_transfer_review(
            _plan(children=children)
        ).to_dict()

        self.assertEqual(review["eligibility"]["state"], "preview_only")
        self.assertIn("proven TXT/BMP/TXT", " ".join(review["eligibility"]["reasons"]))

    def test_sealed_candidate_mismatch_fails_closed_to_preview(self):
        preflight = _preflight()
        preflight["candidate"]["candidate"]["blob_sha256"] = "9" * 64
        review = build_experimental_library_transfer_review(
            _plan(), preflight_report=preflight, bundle_report=_bundle()
        ).to_dict()

        self.assertEqual(review["eligibility"]["state"], "preview_only")
        self.assertIn("candidate hash differs", " ".join(review["eligibility"]["reasons"]))

    def test_unrevalidated_queue_item_is_preview_only(self):
        plan = _plan()
        plan["items"][0]["queue_ready"] = False
        review = build_experimental_library_transfer_review(plan).to_dict()

        self.assertEqual(review["eligibility"]["state"], "preview_only")
        self.assertIn("not fully revalidated", " ".join(review["eligibility"]["reasons"]))

    def test_host_only_plan_flags_cannot_be_promoted_to_execution(self):
        plan = _plan()
        plan["eligibility"]["transfer_enabled"] = True
        review = build_experimental_library_transfer_review(
            plan, preflight_report=_preflight(), bundle_report=_bundle()
        ).to_dict()

        self.assertEqual(review["eligibility"]["state"], "preview_only")
        self.assertIn("transfer_enabled", " ".join(review["eligibility"]["reasons"]))

    def test_safety_contract_covers_every_terminal_boundary_without_retry(self):
        contract = experimental_safety_contract()

        self.assertEqual(contract["application_stages"], list(APPLICATION_TRANSFER_STAGES))
        self.assertTrue(contract["one_package_one_logical_transaction"])
        self.assertEqual(
            contract["terminal_failure_boundaries"],
            list(EXPERIMENTAL_FAILURE_BOUNDARIES),
        )
        self.assertEqual(contract["maximum_logical_sender_calls"], 1)
        self.assertFalse(contract["automatic_retry_allowed"])
        self.assertEqual(
            contract["indeterminate_write_lock"]["scope"], "installation-wide"
        )
        self.assertFalse(contract["indeterminate_write_lock"]["physical_unit_identity_proven"])
        self.assertTrue(contract["indeterminate_write_lock"]["deliberate_same_model_overblocking"])
        self.assertFalse(contract["indeterminate_write_lock"]["automatic_clear"])

    def test_non_mapping_plan_is_rejected(self):
        with self.assertRaises(ExperimentalLibraryTransferReviewError):
            build_experimental_library_transfer_review(None)

    def test_normal_gui_and_cli_do_not_import_execution_shim(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        for relative in ("src/infocarry/cli.py", "src/infocarry/desktop_ttk.py"):
            source = (root / relative).read_text(encoding="utf-8")
            self.assertNotIn("from .experimental_library_transfer import", source)
            self.assertNotIn("import infocarry.experimental_library_transfer", source)

    def test_integration_delegates_one_bundle_to_canonical_runner_and_reconciler(self):
        bundle = object()
        result = object()
        with TemporaryDirectory() as temporary:
            lock = PersistentIndeterminateWriteLock(Path(temporary) / "lock.json")
            store = PersistentExecutionClaimStore(Path(temporary) / "claims.sqlite3")
            with patch.object(
                integration.GuardedLibraryExecutionCoordinator,
                "execute",
                return_value=result,
            ) as execute:
                returned = integration.run_experimental_library_transfer(
                    bundle,
                    indeterminate_write_lock=lock,
                    execution_claim_store=store,
                    plan_report={},
                    confirmation_interaction=lambda _review: "confirmed",
                    low_level_bulk_write_calls=20,
                    detect_device=object(),
                    query_capacity=object(),
                    capture=object(),
                    evidence_namespace="external",
                )

        self.assertIs(returned, result)
        execute.assert_called_once()
        self.assertIs(execute.call_args.args[0], bundle)
        self.assertEqual(execute.call_args.kwargs["plan_report"], {})
        self.assertNotIn("candidate", execute.call_args.kwargs)
        self.assertNotIn("transaction", execute.call_args.kwargs)
        self.assertNotIn("before_backup", execute.call_args.kwargs)
        self.assertNotIn("capacity_response", execute.call_args.kwargs)

    def test_integration_preflight_only_does_not_reconcile_or_add_a_sender(self):
        runner_result = object()
        with TemporaryDirectory() as temporary:
            lock = PersistentIndeterminateWriteLock(Path(temporary) / "lock.json")
            store = PersistentExecutionClaimStore(Path(temporary) / "claims.sqlite3")
            with patch.object(
                integration.GuardedLibraryExecutionCoordinator,
                "execute",
                return_value=runner_result,
            ) as execute:
                result = integration.run_experimental_library_transfer(
                    object(),
                    indeterminate_write_lock=lock,
                    execution_claim_store=store,
                    plan_report=None,
                    confirmation_interaction=None,
                    preflight_only=True,
                    detect_device=object(),
                    query_capacity=object(),
                    capture=object(),
                    evidence_namespace="external",
                )

        self.assertIs(result, runner_result)
        execute.assert_called_once()
        self.assertTrue(execute.call_args.kwargs["preflight_only"])


if __name__ == "__main__":
    unittest.main()
