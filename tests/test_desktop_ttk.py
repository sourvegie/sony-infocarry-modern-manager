import errno
import hashlib
import inspect
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from infocarry.backup_format import BackupFormatError
from infocarry.app_paths import application_paths
from infocarry.desktop_ttk import (
    LIBRARY_DEFAULT_GEOMETRY,
    LIBRARY_DETAIL_MIN_WIDTH,
    LIBRARY_LIST_MIN_WIDTH,
    LIBRARY_MINIMUM_GEOMETRY,
    _application_write_safety_status,
    _library_package_shape,
    _persistent_safety_unavailable_message,
    format_library_device_tree_preview,
    format_library_preparation_audit,
    format_library_transfer_plan,
    format_early_transfer_eligibility_summary,
    _try_create_application_write_safety_owner,
    format_experimental_library_transfer_review,
    format_library_host_only_terminal_state,
    format_library_preparation_summary,
    format_library_preview_summary,
    format_library_readiness_summary,
    format_offline_conversion_report,
    format_offline_page_preview,
    format_post_write_verification,
    format_text_replacement_preview,
    friendly_error_message,
    launch_ttk_desktop,
)
from infocarry.guarded_workflow import GuardedWorkflowError
from infocarry.library_transfer_execution import LibraryTransferExecutionError
from infocarry.library_transfer_readiness import ReadinessAction, ReadinessState
from infocarry.offline_conversion import PageLayout, load_utf8_text_document
from infocarry.execution_claim_store import ExecutionClaimStoreError
from infocarry.prepared_content import EMPTY_SHA256, PreparedContentArtifact, PreparedContentChild
from infocarry.write_safety_boundary import create_default_application_write_safety_owner


class DesktopTtkMessageTests(unittest.TestCase):
    def test_invalid_persistent_claim_store_keeps_ui_safety_owner_closed(self):
        paths = application_paths(
            home=Path("/test-home"), platform="darwin", os_name="posix", environ={}
        )
        with patch(
            "infocarry.desktop_ttk.create_default_application_write_safety_owner",
            side_effect=ExecutionClaimStoreError("existing execution claim store is corrupt"),
        ):
            owner, explanation = _try_create_application_write_safety_owner(paths)

        self.assertIsNone(owner)
        self.assertEqual(explanation, "existing execution claim store is corrupt")
        source = inspect.getsource(launch_ttk_desktop)
        self.assertIn("_try_create_application_write_safety_owner", source)
        safety_message_source = inspect.getsource(_persistent_safety_unavailable_message)
        self.assertIn("Read-only Device Home remains available", safety_message_source)
        self.assertIn("Device-changing actions are disabled", safety_message_source)
        self.assertIn("textvariable=safety_state_var", source)
        self.assertIn("safety_state_label.grid(row=5, column=0", source)
        self.assertIn("safety_state_var.set(_persistent_safety_unavailable_message(detail))", source)

    def test_active_global_lock_has_visible_actionable_read_only_message(self):
        with TemporaryDirectory(prefix="infocarry-ui-lock-") as temporary:
            paths = application_paths(
                home=Path(temporary), platform="darwin", os_name="posix", environ={}
            )
            owner = create_default_application_write_safety_owner(paths=paths)
            owner.indeterminate_write_lock.record_indeterminate(
                reason="fixture unresolved outcome",
                evidence_root="fixture-evidence",
                model_key=owner.device_model_profile.lock_key,
                incident_id="incident-active",
                attempt_id="attempt-active",
            )

            available, detail = _application_write_safety_status(owner)

        self.assertFalse(available)
        self.assertIsNotNone(detail)
        message = _persistent_safety_unavailable_message(detail or "")
        self.assertIn("Read-only Device Home remains available", message)
        self.assertIn("globally locked", message)
        self.assertIn("Do not remove or recreate the safety files", message)

    def test_early_transfer_eligibility_names_exact_supported_shapes(self):
        self.assertIn("TXT → BMP → TXT", format_early_transfer_eligibility_summary())
        self.assertIn("TXT → BMP → TXT → TXT", format_early_transfer_eligibility_summary())

        def artifact(kinds):
            children = tuple(
                PreparedContentChild(
                    order=index,
                    kind=kind,
                    name=f"child-{index}.{kind}",
                    path=f"root\\Book\\child-{index}.{kind}",
                    payload_sha256=EMPTY_SHA256 if kind == "folder" else "0" * 64,
                    payload_bytes=0,
                    payload_path=None if kind == "folder" else f"prepared/{index}",
                )
                for index, kind in enumerate(kinds)
            )
            return PreparedContentArtifact("Book", children)

        for kinds, display_shape in (
            (("txt", "bmp", "txt"), "TXT → BMP → TXT"),
            (("txt", "bmp", "txt", "txt"), "TXT → BMP → TXT → TXT"),
        ):
            summary = format_early_transfer_eligibility_summary(artifact(kinds))
            self.assertIn(f"{display_shape} matches an exact verified VNW-V15 shape", summary)
            self.assertIn("Fresh device evidence", summary)
        self.assertIn(
            "currently unsupported for transfer",
            format_early_transfer_eligibility_summary(artifact(("txt", "txt"))),
        )

    def test_device_home_is_first_tab_and_uses_shared_read_only_inspection(self):
        source = inspect.getsource(launch_ttk_desktop)
        self.assertLess(source.index('notebook.add(device_tab, text="Device")'), source.index('notebook.add(library_tab, text="Library")'))
        self.assertIn('text="Back Up Now"', source)
        self.assertIn('text="Technical Details…"', source)
        self.assertIn("device_home_service.inspect()", source)
        self.assertIn("remember_complete_backup(application_data_paths, destination)", source)
        self.assertIn("device_home_frame.bind(\"<Configure>\"", source)
        self.assertIn("Backup ≠ Restore: backups are read-only snapshots; Restore is unavailable.", source)

    def test_normal_library_formatters_hide_technical_identities(self):
        state = ReadinessState(
            state="needs_review",
            message="Content is prepared. Review current device readiness before sending.",
            action_allowed=False,
            next_action=ReadinessAction.REVIEW,
        )
        summary = format_library_readiness_summary(state)
        self.assertIn("READY TO TRANSFER", summary)
        self.assertIn("Send to InfoCarry: disabled", summary)
        for secret in ("candidate_sha", "transaction_sha", "claim", "seal", "profile_id", "milestone"):
            self.assertNotIn(secret, summary.lower())

        blocked = ReadinessState(
            state="blocked",
            message="Connect the InfoCarry device to continue.",
            action_allowed=False,
            next_action=ReadinessAction.RECONNECT,
        )
        self.assertIn("NOT READY TO TRANSFER", format_library_readiness_summary(blocked))

    def test_prepare_and_preview_use_the_same_canonical_artifact(self):
        child = PreparedContentChild(
            order=0,
            kind="txt",
            name="chapter.txt",
            path="root\\Book\\chapter.txt",
            payload_sha256=hashlib.sha256(b"prepared txt").hexdigest(),
            payload_bytes=12,
            payload_path="prepared/Book/chapter.txt",
        )
        artifact = PreparedContentArtifact("Book", (child,))
        result = SimpleNamespace(artifact=artifact)
        prepare = format_library_preparation_summary(result)
        preview = format_library_preview_summary(result)
        self.assertIn("PREPARE COMPLETE", prepare)
        self.assertIn("PREVIEW", preview)
        self.assertIn("root\\Book\\chapter.txt", preview)
        self.assertIn("same current prepared content", preview)
        self.assertNotIn("sha-256", prepare.lower())
        self.assertNotIn("sha-256", preview.lower())

    def test_host_only_terminal_state_is_truthful(self):
        summary = format_library_host_only_terminal_state()
        self.assertIn("TRANSFERRED AND VERIFIED", summary)
        self.assertIn("host-only simulation", summary)
        self.assertIn("No device operation was performed", summary)

    def test_normal_ttk_library_path_uses_controller_and_technical_details_boundary(self):
        source = inspect.getsource(launch_ttk_desktop)
        for contract in (
            "OperationController",
            "library_operation_controller.start",
            "Check device readiness",
            "validate_revision=False",
            "library_callbacks",
            "Technical Details",
            "Send to InfoCarry",
            "library_selection_matches",
            "all_library_revision",
            "store=False",
            "adopt_prepared_operation",
            "library_operation_controller.busy",
            "restore_device_manager_controls",
            "Another manager operation started while the chooser was open",
            "Another manager operation started while confirmation was open",
            "root.after(50, process_library_callbacks)",
        ):
            self.assertIn(contract, source)

    def test_library_package_shape_accepts_persisted_child_mappings(self):
        package = SimpleNamespace(
            children=(
                {"kind": "txt"},
                {"kind": "bmp"},
                {"kind": "txt"},
            )
        )
        self.assertEqual(_library_package_shape(package), "TXT/BMP/TXT")

    def test_library_review_geometry_is_explicit_and_usable(self):
        self.assertEqual(LIBRARY_MINIMUM_GEOMETRY, (980, 680))
        self.assertGreaterEqual(LIBRARY_DEFAULT_GEOMETRY[0], LIBRARY_MINIMUM_GEOMETRY[0])
        self.assertGreaterEqual(LIBRARY_DEFAULT_GEOMETRY[1], LIBRARY_MINIMUM_GEOMETRY[1])
        self.assertGreaterEqual(LIBRARY_LIST_MIN_WIDTH, 320)
        self.assertGreaterEqual(LIBRARY_DETAIL_MIN_WIDTH, 400)

    def test_library_layout_uses_scrollable_portable_ttk_controls(self):
        source = inspect.getsource(launch_ttk_desktop)
        self.assertNotIn("minsize=", source)
        for control in (
            "library_tree_horizontal_scroll",
            "library_report_horizontal_scroll",
            "library_safety_notice",
            "library_status_label",
            "library_experimental_group",
            "keep_library_sash_in_bounds",
            "sashpos",
            "library_folder_import_button",
            "library_move_up_button",
            "library_move_down_button",
            "library_preview_button",
        ):
            self.assertIn(control, source)

    def test_library_layout_wires_hierarchy_chooser_order_and_host_preview(self):
        source = inspect.getsource(launch_ttk_desktop)
        for contract in (
            "askopenfilenames",
            "askdirectory",
            "library_workflow.import_files",
            "library_workflow.import_folder",
            "library_catalog.children(parent_id)",
            "library_workflow.move_up",
            "library_workflow.move_down",
            "library_workflow.remove",
            "library_workflow.prepare_preview",
            "format_library_device_tree_preview",
            "unavailable without TkDND",
        ):
            self.assertIn(contract, source)
        self.assertNotIn("prepared_library_package_live_adapter", source)

    def test_existing_replacement_confirmation_keeps_simpledialog_imported(self):
        source = inspect.getsource(launch_ttk_desktop)
        self.assertIn("from tkinter import filedialog, messagebox, simpledialog, ttk", source)
        self.assertIn("simpledialog.askstring", inspect.getsource(launch_ttk_desktop))

    def test_existing_replacement_write_uses_application_wide_safety_owner(self):
        source = inspect.getsource(launch_ttk_desktop)
        self.assertIn("replacement_write_safety_available", source)
        self.assertIn("safety_owner=replacement_safety_owner", source)
        self.assertIn("Existing-text replacement is disabled fail-closed", source)

    def test_hierarchical_device_tree_preview_is_exact_and_capacity_is_explicit(self):
        summary = format_library_device_tree_preview(
            {
                "profile_id": "host-offline-hierarchical-library-v1",
                "profile_status": "host_offline_only_not_live_enabled",
                "plan_sha256": "a" * 64,
                "ordered_nodes": [
                    {
                        "node_id": "book",
                        "parent_id": None,
                        "order": 0,
                        "kind": "folder",
                        "name": "Book",
                        "path": "root\\Book",
                        "prepared_payload_bytes": 0,
                        "validation": "passed",
                        "conflict": "not_evaluated",
                    },
                    {
                        "node_id": "chapter",
                        "parent_id": "book",
                        "order": 0,
                        "kind": "txt",
                        "name": "chapter.txt",
                        "path": "root\\Book\\chapter.txt",
                        "prepared_payload_bytes": 12,
                        "validation": "passed",
                        "conflict": "not_evaluated",
                    },
                ],
                "validation": {
                    "prepared_manifest": "passed",
                    "internal_paths_and_order": "passed",
                    "existing_device_paths": "not_evaluated_without_fresh_verified_baseline",
                    "conflicts": [],
                    "capability_match": "host_offline_only_not_live_capable",
                },
                "capacity": {
                    "total_model_limit_bytes": "not_evaluated",
                    "fresh_baseline_model_length_bytes": "not_evaluated",
                    "candidate_growth_bytes": "not_evaluated",
                    "remaining_after_transfer_bytes": "not_evaluated",
                },
                "execution": {
                    "enabled": False,
                    "candidate_constructed": False,
                    "usb_accessed": False,
                    "device_change": "none",
                },
            }
        )
        self.assertIn("host/offline only", summary)
        self.assertIn("order=0 type=FOLDER name=Book", summary)
        self.assertIn("  order=0 type=TXT name=chapter.txt", summary)
        self.assertIn("Destination: root\\Book\\chapter.txt", summary)
        self.assertIn("Prepared size: 12 bytes", summary)
        self.assertIn("Validation: passed", summary)
        self.assertIn("Conflict: not_evaluated", summary)
        for label in (
            "Total model limit",
            "Fresh baseline length",
            "Candidate growth",
            "Remaining after transfer",
        ):
            self.assertIn(f"{label}: Not evaluated", summary)
        self.assertIn("Execution enabled: no", summary)
        self.assertIn("USB accessed: no", summary)

    def test_device_tree_formatter_fails_closed_on_out_of_order_parent(self):
        with self.assertRaisesRegex(ValueError, "parent"):
            format_library_device_tree_preview(
                {
                    "ordered_nodes": [
                        {
                            "node_id": "child",
                            "parent_id": "missing",
                        }
                    ],
                    "validation": {"conflicts": []},
                    "capacity": {},
                    "execution": {},
                }
            )

    def test_library_prepare_summary_is_explicitly_offline(self):
        summary = format_library_preparation_audit(
            {
                "device_operation": "none",
                "usb_accessed": False,
                "source": {"sha256": "a" * 64},
                "prepared": {"child_path": "root\\Book\\chapter.txt"},
            }
        )
        self.assertIn("OFFLINE LIBRARY PREPARE", summary)
        self.assertIn("no device change occurred", summary)
        self.assertIn("root\\\\Book\\\\chapter.txt", summary)
        self.assertIn('"usb_accessed": false', summary)

    def test_library_transfer_summary_is_explicitly_offline(self):
        summary = format_library_transfer_plan(
            {
                "selection": {
                    "mode": "selected",
                    "selected_item_ids": ["item-1"],
                    "excluded_items": [],
                },
                "baseline": {"available": False},
                "grouping": {"policy": "one package per item"},
                "items": [
                    {
                        "source": {"filename": "chapter.txt", "sha256": "a" * 64, "size_bytes": 9},
                        "prepared_artifact": {
                            "manifest_sha256": "b" * 64,
                            "child_order": ["chapter.txt"],
                            "prepared_payload_bytes": 10,
                        },
                        "destination": {"paths": ["root\\Book", "root\\Book\\chapter.txt"]},
                        "operation_type": "prepared_root_txt_package",
                        "compatibility_state": "constrained_shape_ready_for_offline_review",
                        "conflicts": [],
                        "queue_ready": False,
                        "reasons": ["verified device backup is required"],
                    }
                ],
                "totals": {
                    "selected_items": 1,
                    "source_bytes": 9,
                    "prepared_payload_bytes": 10,
                    "estimated_growth_lower_bound": 128,
                },
                "capacity": {
                    "status": "not_evaluated_without_verified_backup",
                    "available_bytes": None,
                    "lower_bound_bytes": 128,
                },
                "eligibility": {"queue_ready": False},
            }
        )
        self.assertIn("OFFLINE LIBRARY TRANSFER REVIEW", summary)
        self.assertIn("root\\Book\\chapter.txt", summary)
        self.assertIn("Device execution: disabled", summary)
        self.assertIn("Candidate/auth/transaction/sender: none", summary)
        self.assertIn("USB operation performed: no", summary)

    def test_experimental_library_review_shows_guarded_scope_without_send(self):
        summary = format_experimental_library_transfer_review(
            {
                "profile": "one_selected_library_item_root_txt_bmp_txt",
                "selection": {"logical_item_id": "item-1"},
                "package": {
                    "prepared_manifest_sha256": "a" * 64,
                    "ordered_children": [
                        {"order": 0, "kind": "txt", "name": "01-introduction.txt", "path": "root\\Book\\01-introduction.txt", "prepared_payload_bytes": 10},
                        {"order": 1, "kind": "bmp", "name": "02-page-01.bmp", "path": "root\\Book\\02-page-01.bmp", "prepared_payload_bytes": 20},
                        {"order": 2, "kind": "txt", "name": "03-ending.txt", "path": "root\\Book\\03-ending.txt", "prepared_payload_bytes": 8},
                    ],
                },
                "destination": {"paths": ["root\\Book"], "conflicts": []},
                "capacity": {"status": "unknown", "available_bytes": None},
                "fresh_backup": {"destination": "allocated per attempt"},
                "candidate": {"candidate_blob_sha256": "not sealed"},
                "operation_identity": {},
                "transfer_semantics": {},
                "verification": {},
                "eligibility": {
                    "experimental_status": "preview_only",
                    "execution_action_exposed": False,
                    "reasons": ["fresh complete verified backup is required"],
                },
            }
        )
        self.assertIn("EXPERIMENTAL LIBRARY TRANSFER REVIEW", summary)
        self.assertIn("02-page-01.bmp", summary)
        self.assertIn("Status", summary)
        self.assertIn("Package contents (authoritative order)", summary)
        self.assertIn("Destination and conflicts", summary)
        self.assertIn("Capacity and backup state", summary)
        self.assertIn("Safety rules", summary)
        self.assertIn("Technical details", summary)
        self.assertIn("no send action", summary)
        self.assertIn("automatic retry: no", summary)
        self.assertIn("Why not hardware-ready", summary)

    def test_recovery_messages_cover_common_read_only_failures(self):
        self.assertIn("not enough free disk space", friendly_error_message(OSError(errno.ENOSPC, "full")))
        self.assertIn("not writable", friendly_error_message(PermissionError("denied")))
        malformed = friendly_error_message(BackupFormatError("bad checksum"))
        self.assertIn("incomplete or malformed", malformed)
        self.assertIn("fresh read-only backup", malformed)
        disconnected = friendly_error_message(RuntimeError("USB timeout while reading"))
        self.assertIn("Reconnect the device", disconnected)

    def test_replacement_preview_summary_is_explicitly_offline(self):
        report = {
            "authoring": {
                "input_characters": 5,
                "input_utf8_bytes": 7,
                "normalized_characters": 6,
                "encoded_payload_bytes": 6,
            },
            "target": {
                "path": "root\\memo",
                "record_offset_hex": "0x000000c0",
                "native_prefix": {"length_bytes": 32, "preserved_exactly": True},
            },
            "workflow": {
                "target_path": "root\\memo.txt",
                "target_record_offset": "0x000000c0",
                "input_path": "/tmp/replacement.txt",
            },
            "capacity": {
                "limit_applied": False,
                "limit_bytes": None,
                "encoded_payload_within_limit": True,
            },
        }
        summary = format_text_replacement_preview(report)
        self.assertIn("OFFLINE REPLACEMENT PREVIEW", summary)
        self.assertIn("no device change occurred", summary)
        self.assertIn("root\\memo.txt", summary)
        self.assertIn("0x000000c0", summary)
        self.assertIn("Source UTF-8 bytes: 7", summary)
        self.assertIn("Encoded payload (strict CP932): 6 bytes", summary)
        self.assertIn("Candidate bytes included: no", summary)
        self.assertIn("USB operation performed: no", summary)

    def test_post_write_summary_shows_all_independent_checks_and_no_retry(self):
        summary = format_post_write_verification(
            {
                "before_backup": {"directory": "/tmp/before"},
                "after_backup": {"directory": "/tmp/after"},
                "fixed_state_matches": True,
                "dynamic_blob_matches": True,
                "unrelated_objects_unchanged": True,
            }
        )
        self.assertIn("POST-WRITE READ-BACK VERIFICATION — VERIFIED", summary)
        self.assertIn("Fixed state matches candidate: yes", summary)
        self.assertIn("Dynamic content matches candidate: yes", summary)
        self.assertIn("Unrelated backup objects unchanged: yes", summary)
        self.assertIn("Automatic retry: no", summary)

    def test_guarded_write_error_explains_terminal_recovery(self):
        message = friendly_error_message(
            GuardedWorkflowError(
                "read-back did not match", stage="post_write_readback", write_started=True
            )
        )
        self.assertIn("Do not retry automatically", message)
        self.assertIn("post_write_readback", message)

    def test_library_indeterminate_error_explains_no_retry_diagnosis(self):
        message = friendly_error_message(
            LibraryTransferExecutionError(
                "independent terminal read-back could not be completed",
                stage="independent_readback",
                state="indeterminate_after_transaction_start",
            )
        )
        self.assertIn("ESCALATION_REQUIRED", message)
        self.assertIn("do not retry", message)
        self.assertIn("read-only diagnosis", message)
        self.assertIn("independent_readback", message)

    def test_conversion_and_renderer_summaries_are_explicitly_offline(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "notes.txt"
            source.write_text("hello\nworld", encoding="utf-8")
            document = load_utf8_text_document(
                source, layout=PageLayout(columns=5, lines_per_page=1)
            )
            report = format_offline_conversion_report(document)
            self.assertIn("OFFLINE TEXT CONVERSION", report)
            self.assertIn("Device accessed: no", report)
            self.assertIn("Candidate device bytes included: no", report)
            page = format_offline_page_preview(document, 1)
            self.assertIn("Page 1 / 2", page)
            self.assertIn("hello", page)


if __name__ == "__main__":
    unittest.main()
