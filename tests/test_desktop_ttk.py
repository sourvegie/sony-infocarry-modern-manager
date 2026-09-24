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
    _backup_review_filesystem_revision,
    _source_review_filesystem_revision,
    _application_safety_notice,
    _application_write_safety_status,
    _initial_device_home_status,
    _library_package_shape,
    _persistent_safety_unavailable_message,
    format_library_device_tree_preview,
    format_library_preparation_audit,
    format_library_transfer_plan,
    format_early_transfer_eligibility_summary,
    _try_create_application_write_safety_owner,
    format_experimental_library_transfer_review,
    format_library_host_only_terminal_state,
    format_library_operation_failure,
    format_library_preparation_summary,
    format_library_preview_summary,
    format_library_readiness_summary,
    format_library_transfer_review_summary,
    format_offline_conversion_report,
    format_offline_page_preview,
    format_post_write_verification,
    format_text_replacement_preview,
    friendly_error_message,
    launch_ttk_desktop,
)
from infocarry.guarded_workflow import GuardedWorkflowError
from infocarry.library_transfer_execution import LibraryTransferExecutionError
from infocarry.library_folder_package_adapter import LibraryFolderPackageAdapterError
from infocarry.library_transfer_readiness import ReadinessAction, ReadinessState
from infocarry.offline_conversion import PageLayout, load_utf8_text_document
from infocarry.execution_claim_store import ExecutionClaimStoreError
from infocarry.prepared_content import EMPTY_SHA256, PreparedContentArtifact, PreparedContentChild
from infocarry.write_safety_boundary import create_default_application_write_safety_owner


class DesktopTtkMessageTests(unittest.TestCase):
    def test_source_file_metadata_stales_an_open_transfer_review(self):
        with TemporaryDirectory(prefix="infocarry-review-source-") as temporary:
            source = Path(temporary) / "story.txt"
            source.write_text("before", encoding="utf-8")
            original = _source_review_filesystem_revision(source)
            source.write_text("after with new content", encoding="utf-8")
            changed = _source_review_filesystem_revision(source)

        self.assertNotEqual(original, changed)
        source = inspect.getsource(launch_ttk_desktop)
        self.assertIn("_source_review_filesystem_revision(value.source_path)", source)
        self.assertIn("root.after(1000, process_library_review_freshness)", source)
        self.assertIn("invalidate_library_transfer_review_if_stale()", source)

    def test_prepared_package_normalization_locations_are_owner_visible(self):
        artifact = PreparedContentArtifact(
            "Book",
            (
                PreparedContentChild(
                    order=0,
                    kind="txt",
                    name="chapter.txt",
                    path="root\\Book\\chapter.txt",
                    payload_sha256=hashlib.sha256(b"prepared").hexdigest(),
                    payload_bytes=8,
                    payload_path="prepared/chapter.txt",
                ),
            ),
        )
        workspace_preview = SimpleNamespace(
            source_kind=SimpleNamespace(value="prepared_package"),
            source_path=Path("package"),
            normalization_substitutions=(("“", '"'),),
            normalization_occurrences=(),
            normalization_details=(
                ("chapter.txt", "source.txt", 2, 4, "“", '"'),
            ),
            rendered_details=(),
            warnings=(),
        )
        prepared = SimpleNamespace(
            artifact=artifact,
            preview=workspace_preview,
            source_path=Path("package"),
            source_format="prepared_package",
        )
        summary = format_library_preparation_summary(
            SimpleNamespace(artifact=artifact, prepared=prepared)
        )
        self.assertIn("chapter.txt (source source.txt), line 2, column 4", summary)
        self.assertIn("'“' → '\"'", summary)

    def test_epub_normalization_locations_are_owner_visible(self):
        artifact = PreparedContentArtifact(
            "Book",
            (
                PreparedContentChild(
                    order=0,
                    kind="txt",
                    name="chapter-001.txt",
                    path="root\\Book\\chapter-001.txt",
                    payload_sha256=hashlib.sha256(b"prepared").hexdigest(),
                    payload_bytes=8,
                    payload_path="prepared/chapter-001.txt",
                ),
            ),
        )
        occurrence = {
            "source": "OEBPS/chapter.xhtml",
            "coordinate_basis": "extracted chapter text",
            "line": 2,
            "column": 7,
            "from": "“",
            "to": '"',
        }
        prepared = SimpleNamespace(
            artifact=artifact,
            source_path=Path("book.epub"),
            source_format="epub",
            normalization_events=1,
            unsupported_features=(),
            preview_children=lambda **_kwargs: (
                {
                    "name": "chapter-001.txt",
                    "kind": "txt",
                    "text": 'Hello "world"',
                    "truncated": False,
                    "normalization_occurrences": [occurrence],
                },
            ),
        )
        result = SimpleNamespace(artifact=artifact, prepared=prepared)
        preparation = format_library_preparation_summary(result)
        preview = format_library_preview_summary(result)
        self.assertIn("extracted chapter text", preparation)
        self.assertIn("chapter-001.txt (EPUB OEBPS/chapter.xhtml), line 2, column 7", preparation)
        self.assertIn("chapter-001.txt (EPUB OEBPS/chapter.xhtml), line 2, column 7", preview)

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
        self.assertEqual(_application_safety_notice(owner, explanation), explanation)
        source = inspect.getsource(launch_ttk_desktop)
        self.assertIn("_try_create_application_write_safety_owner", source)
        safety_message_source = inspect.getsource(_persistent_safety_unavailable_message)
        self.assertIn("Read-only Device Home remains available", safety_message_source)
        self.assertIn("Device-changing actions are disabled", safety_message_source)
        self.assertIn("textvariable=safety_state_var", source)
        self.assertIn("safety_state_label.grid(row=5, column=0", source)
        self.assertIn("safety_state_var.set(_persistent_safety_unavailable_message(detail))", source)
        self.assertIn("initial_safety_detail = _application_safety_notice(", source)

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
            startup_detail = _application_safety_notice(owner, None)
            self.assertEqual(startup_detail, detail)
            message = _persistent_safety_unavailable_message(startup_detail or "")
            self.assertIn("Read-only Device Home remains available", message)
            self.assertIn("globally locked", message)
            self.assertIn("Do not remove or recreate the safety files", message)

    def test_startup_safety_notice_is_read_only_for_an_abandoned_sender_marker(self):
        with TemporaryDirectory(prefix="infocarry-ui-marker-") as temporary:
            paths = application_paths(
                home=Path(temporary), platform="darwin", os_name="posix", environ={}
            )
            owner = create_default_application_write_safety_owner(paths=paths)
            claim = owner.consume_execution_claim(
                {
                    "preflight_seal_sha256": "a" * 64,
                    "core_preflight_seal_sha256": "b" * 64,
                    "candidate_blob_sha256": "c" * 64,
                    "transaction_sha256": "d" * 64,
                    "authorization_sha256": "e" * 64,
                    "baseline_state_identity_sha256": "f" * 64,
                    "capacity_response_sha256": "1" * 64,
                }
            )
            owner.mark_sender_start(
                claim,
                attempt_id="attempt-ui-startup",
                evidence_root="fixture-evidence",
                operation_label="fixture-operation",
            )
            restarted = create_default_application_write_safety_owner(paths=paths)

            detail = _application_safety_notice(restarted, None)

            self.assertIn("unresolved sender-start marker", detail or "")
            self.assertFalse(paths.indeterminate_write_lock.exists())
            marker = restarted.execution_claim_store.read_sender_in_flight()
            self.assertIsNotNone(marker)
            self.assertEqual(marker.state, "in_flight")
            source = inspect.getsource(launch_ttk_desktop)
            self.assertIn("initial_safety_detail = _application_safety_notice(", source)

    def test_device_home_startup_does_not_claim_disconnected_before_inspection(self):
        heading, message = _initial_device_home_status()

        self.assertEqual(heading, "Device status not checked")
        self.assertIn("Refresh Device Home to check", message)
        source = inspect.getsource(launch_ttk_desktop)
        self.assertIn("_initial_device_home_status()", source)

    def test_backup_file_change_changes_review_revision(self):
        with TemporaryDirectory() as temporary:
            backup = Path(temporary)
            blob = backup / "model.bin"
            blob.write_bytes(b"first backup")
            first = _backup_review_filesystem_revision(backup)
            blob.write_bytes(b"replacement backup with changed size")
            second = _backup_review_filesystem_revision(backup)

        self.assertNotEqual(first, second)

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
            self.assertIn(f"{display_shape} is transferable for the reviewed VNW-V15 shape", summary)
            self.assertIn("Fresh device checks", summary)
        self.assertIn(
            "not yet supported for transfer",
            format_early_transfer_eligibility_summary(artifact(("txt", "txt"))),
        )

    def test_local_and_device_libraries_share_the_primary_workspace(self):
        source = inspect.getsource(launch_ttk_desktop)
        self.assertIn('workspace = ttk.Panedwindow(root, orient="horizontal")', source)
        self.assertIn("workspace.add(library_tab, weight=1)", source)
        self.assertIn("workspace.add(device_tab, weight=1)", source)
        self.assertNotIn("notebook.add(", source)
        self.assertIn('text="LOCAL LIBRARY"', source)
        self.assertIn('text="DEVICE LIBRARY"', source)
        self.assertIn('text="Back Up"', source)
        self.assertIn('text="Technical Details…"', source)
        self.assertIn("device_home_service.inspect()", source)
        self.assertIn("remember_complete_backup(application_data_paths, destination)", source)
        self.assertIn("device_home_frame.bind(\"<Configure>\"", source)
        self.assertIn("Backup ≠ Restore: backups are read-only snapshots; Restore is unavailable.", source)
        self.assertIn('text="Delete", state="disabled"', source)

    def test_normal_library_formatters_hide_technical_identities(self):
        state = ReadinessState(
            state="needs_review",
            message="Content is prepared. Review current device readiness before sending.",
            action_allowed=False,
            next_action=ReadinessAction.REVIEW,
        )
        summary = format_library_readiness_summary(state)
        self.assertIn("NOT CURRENTLY READY FOR TRANSFER", summary)
        self.assertIn("Viewing this review does not authorize or start a transfer", summary)
        self.assertIn("Device-changing operations during this review: 0", summary)
        for secret in ("candidate_sha", "transaction_sha", "claim", "seal", "profile_id", "milestone"):
            self.assertNotIn(secret, summary.lower())

        blocked = ReadinessState(
            state="blocked",
            message="Connect the InfoCarry device to continue.",
            action_allowed=False,
            next_action=ReadinessAction.RECONNECT,
        )
        self.assertIn("NOT CURRENTLY READY FOR TRANSFER", format_library_readiness_summary(blocked))

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
        self.assertIn("PREPARED SUCCESSFULLY — ready to preview", prepare)
        self.assertIn("PREVIEW", preview)
        self.assertIn("root\\Book\\chapter.txt", preview)
        self.assertIn("same current prepared content", preview)
        self.assertNotIn("sha-256", prepare.lower())
        self.assertNotIn("sha-256", preview.lower())

    def test_owner_transfer_review_shows_order_checks_and_no_authorization(self):
        artifact = PreparedContentArtifact(
            "Book",
            (
                PreparedContentChild(
                    order=0,
                    kind="txt",
                    name="start.txt",
                    path="root\\Book\\start.txt",
                    payload_sha256="0" * 64,
                    payload_bytes=12,
                    payload_path="prepared/start.txt",
                ),
                PreparedContentChild(
                    order=1,
                    kind="bmp",
                    name="page.bmp",
                    path="root\\Book\\page.bmp",
                    payload_sha256="1" * 64,
                    payload_bytes=20,
                    payload_path="prepared/page.bmp",
                ),
                PreparedContentChild(
                    order=2,
                    kind="txt",
                    name="end.txt",
                    path="root\\Book\\end.txt",
                    payload_sha256="2" * 64,
                    payload_bytes=8,
                    payload_path="prepared/end.txt",
                ),
            ),
        )
        report = {
            "baseline": {"available": True},
            "items": [
                {
                    "item_id": "internal-item-id",
                    "source": {"filename": "book.txt"},
                    "prepared_artifact": {
                        "ordered_children": [
                            {"kind": child.kind, "name": child.name} for child in artifact.children
                        ],
                        "prepared_payload_bytes": artifact.aggregate_size,
                    },
                    "destination": {"paths": ["root\\Book"]},
                    "conflicts": [],
                    "reasons": [],
                }
            ],
            "totals": {"prepared_payload_bytes": artifact.aggregate_size},
            "capacity": {"status": "not_evaluated_without_verified_backup"},
            "eligibility": {"queue_ready": False},
        }
        summary = format_library_transfer_review_summary(
            report,
            artifacts={"internal-item-id": artifact},
            device_snapshot=SimpleNamespace(
                heading="Device is connected", state="connected", capacity_bytes=1_000
            ),
            backup_created_at="2026-09-20T01:00:00Z",
        )
        self.assertIn("TXT → BMP → TXT is transferable for the reviewed VNW-V15 shape", summary)
        self.assertIn("TXT start.txt, BMP page.bmp, TXT end.txt", summary)
        self.assertIn("integrity-checked for this review", summary)
        self.assertIn("Capacity comparison", summary)
        self.assertIn("does not authorize or start", summary)
        self.assertIn("no device change occurred", summary)
        self.assertNotIn("internal-item-id", summary)

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
            "library_review_context_revision",
            "library_transfer_review_revision(library_item_revision(item))",
            "_backup_review_filesystem_revision(model.state.backup_directory)",
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

    def test_live_transfer_uses_simple_confirmation_and_background_controller(self):
        source = inspect.getsource(launch_ttk_desktop)
        start = source.index("    def library_transfer_once_action()")
        end = source.index(
            '    library_tree.bind("<<TreeviewSelect>>"',
            start,
        )
        action = source[start:end]

        self.assertIn('messagebox.askokcancel(', action)
        self.assertIn('"Confirm Transfer"', action)
        self.assertIn("Keep the InfoCarry connected until verification finishes.", action)
        self.assertNotIn("simpledialog.askstring", action)
        self.assertNotIn("Type exactly:", action)

        self.assertIn("def work(", action)
        self.assertIn("library_execution_facade.execute_once(", action)
        self.assertIn("start_library_operation(", action)
        self.assertIn('"Transfer to InfoCarry"', action)
        self.assertIn("validate_revision=False", action)
        self.assertIn(
            '"Final safety checks — keep the InfoCarry connected"',
            action,
        )
        self.assertIn(
            '"Transferring to InfoCarry — do not disconnect"',
            action,
        )
        self.assertIn(
            '"Verifying transfer — do not disconnect"',
            action,
        )
        self.assertIn("cancelled=lambda: False", action)
        self.assertIn('library_cancel_button.configure(state="disabled")', action)
        self.assertIn("library_device_change_in_progress = True", action)
        self.assertIn("on_terminal=terminal", action)

        close_start = source.index("    def close_action()")
        close_end = source.index(
            '    tree.bind("<<TreeviewSelect>>"',
            close_start,
        )
        close_action = source[close_start:close_end]
        self.assertIn("if library_device_change_in_progress:", close_action)
        self.assertIn('"Transfer in progress"', close_action)
        self.assertIn("return", close_action)

        # Clicking OK authorizes the existing exact sealed operation; it does
        # not bypass or replace the canonical phrase-based safety contract.
        self.assertIn(
            "confirmation_interaction=lambda _review: confirmation_phrase",
            action,
        )
        self.assertIn("intent.confirmation_phrase", action)

    def test_live_transfer_cannot_be_invalidated_by_selection_or_drag(self):
        source = inspect.getsource(launch_ttk_desktop)

        selection_start = source.index("    def show_library_selection(")
        selection_end = source.index("\n    def library_import_can_start(", selection_start)
        selection = source[selection_start:selection_end]
        guard = selection.index("if library_device_change_in_progress:")
        invalidation = selection.index("library_operation_controller.invalidate()")
        self.assertLess(guard, invalidation)
        self.assertIn("library_cancel_button", selection[guard:invalidation])
        self.assertIn('button.configure(state="disabled")', selection[guard:invalidation])
        self.assertIn("return", selection[guard:invalidation])

        drag_press_start = source.index("    def library_drag_press(")
        drag_motion_start = source.index("    def library_drag_motion(", drag_press_start)
        drag_press = source[drag_press_start:drag_motion_start]
        self.assertIn("if library_operation_controller.busy:", drag_press)

        drag_release_start = source.index("    def library_drag_release(", drag_motion_start)
        drag_release_end = source.index("\n    def library_rename_destination_action(", drag_release_start)
        drag_release = source[drag_release_start:drag_release_end]
        self.assertIn("if library_operation_controller.busy:", drag_release)
        self.assertLess(
            drag_release.index("if library_operation_controller.busy:"),
            drag_release.index("clear_library_review_for_input_change()"),
        )

        transfer_start = source.index("    def library_transfer_once_action()")
        transfer_end = source.index(
            '    library_tree.bind("<<TreeviewSelect>>"',
            transfer_start,
        )
        transfer = source[transfer_start:transfer_end]
        self.assertIn("show_library_selection()", transfer)
        self.assertIn("library_device_change_in_progress = False", transfer)

    def test_transfer_success_copy_is_product_facing(self):
        source = inspect.getsource(launch_ttk_desktop)
        start = source.index("    def library_transfer_once_action()")
        end = source.index(
            '    library_tree.bind("<<TreeviewSelect>>"',
            start,
        )
        action = source[start:end]
        self.assertIn(
            '"Transfer complete — content verified on the InfoCarry"',
            action,
        )
        self.assertNotIn("readback_verified", action)

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
        self.assertEqual(LIBRARY_MINIMUM_GEOMETRY, (1080, 680))
        self.assertGreaterEqual(LIBRARY_DEFAULT_GEOMETRY[0], LIBRARY_MINIMUM_GEOMETRY[0])
        self.assertGreaterEqual(LIBRARY_DEFAULT_GEOMETRY[1], LIBRARY_MINIMUM_GEOMETRY[1])
        self.assertGreaterEqual(LIBRARY_LIST_MIN_WIDTH, 320)
        self.assertGreaterEqual(LIBRARY_DETAIL_MIN_WIDTH, 400)

    def test_library_layout_uses_scrollable_portable_ttk_controls(self):
        source = inspect.getsource(launch_ttk_desktop)
        self.assertNotIn("minsize=", source)
        for control in (
            "library_tree_horizontal_scroll",
            "tree_horizontal_scroll",
            "library_report_horizontal_scroll",
            "library_status_label",
            "keep_library_sash_in_bounds",
            "sashpos",
            "library_add_menu",
            "library_search_entry",
            "library_remove_selection_button",
            "library_reorder_up_button",
            "library_reorder_down_button",
            "library_transfer_button",
            "library_toolbar.pack_forget()",
        ):
            self.assertIn(control, source)

    def test_local_add_controls_are_decoupled_from_device_and_transfer_state(self):
        source = inspect.getsource(launch_ttk_desktop)

        def body(name: str, next_name: str) -> str:
            start = source.index(f"    def {name}(")
            end = source.index(f"\n    def {next_name}(", start + 1)
            return source[start:end]

        add_state = body(
            "set_library_add_controls_available", "restore_device_manager_controls"
        )
        for control in (
            "library_add_button",
            "library_add_menu.entryconfigure",
            "library_import_button",
            "library_folder_import_button",
        ):
            self.assertIn(control, add_state)
        for forbidden_state in (
            "library_execution_facade",
            "operation_binding",
            "capacity",
            "replacement_safety_owner",
            "indeterminate_write_lock",
            "sender",
            "usb",
        ):
            self.assertNotIn(forbidden_state, add_state.casefold())

        device_busy = body("set_busy", "selected_device_destination_path")
        for control in (
            "library_add_button",
            "library_import_button",
            "library_folder_import_button",
            "library_package_import_button",
        ):
            self.assertNotIn(control, device_busy)

        library_busy = body("set_library_operation_busy", "library_cancel_action")
        for control in (
            "library_add_button",
            "library_import_button",
            "library_folder_import_button",
            "library_package_import_button",
        ):
            self.assertNotIn(control, library_busy)

        selection_state = body("show_library_selection", "library_import_can_start")
        for control in (
            "library_add_button",
            "library_add_menu",
            "library_import_button",
            "library_folder_import_button",
            "library_package_import_button",
        ):
            self.assertNotIn(control, selection_state)

        import_action = body("library_import_can_start", "library_import_action")
        self.assertIn("library_operation_controller.busy", import_action)
        self.assertNotIn("library_execution_facade", import_action)

    def test_library_layout_wires_hierarchy_chooser_order_and_host_preview(self):
        source = inspect.getsource(launch_ttk_desktop)
        for contract in (
            "askopenfilenames",
            "askdirectory",
            "library_workflow.import_files",
            "library_workflow.import_folder",
            "library_catalog.children(parent_id)",
            "library_catalog.move_to",
            "library_catalog.remove_many",
            "library_workflow.prepare_preview",
            "format_library_device_tree_preview",
            'library_tree.bind("<B1-Motion>"',
        ):
            self.assertIn(contract, source)
        self.assertNotIn("prepared_library_package_live_adapter", source)

    def test_visible_add_folder_transfer_path_uses_transient_exact_adapter(self):
        source = inspect.getsource(launch_ttk_desktop)
        action_start = source.index("    def library_transfer_action()")
        action_end = source.index("    def library_transfer_once_action()", action_start)
        action = source[action_start:action_end]
        self.assertIn("library_folder_import_action", source)
        self.assertIn("library_folder_import_button.configure(command=library_folder_import_action)", source)
        self.assertIn('label="Add Folder…", command=lambda: library_folder_import_action()', source)
        self.assertIn("prepare_exact_folder_package(", action)
        self.assertIn("selected[0].node_kind == NODE_FOLDER", action)
        self.assertIn("catalog_override=catalog_override", action)
        self.assertIn("artifact_override=artifact_override", action)
        self.assertIn("transfer_stage=folder_stage", action)
        self.assertIn("library_single_transfer_review_action(", action)
        self.assertIn("library_toolbar.pack_forget()", source)
        self.assertNotIn("library_prepare_action()", action)
        self.assertNotIn("library_package_import_action()", action)
        self.assertNotIn("execute_once(", action)
        self.assertNotIn("refresh_live_preflight(", action)

    def test_primary_transfer_routes_only_exact_packages_through_existing_guards(self):
        source = inspect.getsource(launch_ttk_desktop)
        action_start = source.index("    def library_transfer_action()")
        action_end = source.index("    def library_transfer_once_action()", action_start)
        action = source[action_start:action_end]
        self.assertIn("build_library_device_transfer_plan(", action)
        self.assertIn("_exact_live_package_artifact(", action)
        self.assertIn("library_single_transfer_review_action(", action)
        self.assertIn("continue_to_preflight=True", action)
        self.assertIn("has not yet been enabled for device transfer", action)
        self.assertIn("this plan does not authorize a device operation", action)
        self.assertIn("library_toolbar.pack_forget()", source)
        self.assertNotIn("execute_once(", action)
        self.assertNotIn("refresh_live_preflight(", action)
        self.assertNotIn("build_candidate", action)
        self.assertNotIn("sender", action.lower())
        self.assertNotIn("experimental-flat-root-folder-txt-bmp-v1", action)
        self.assertNotIn("verified-vnw-v15-four-leaf-direct-v1", action)

    def test_opening_and_selecting_library_content_never_starts_live_services(self):
        source = inspect.getsource(launch_ttk_desktop)
        selection_start = source.index("    def show_library_selection(")
        selection_end = source.index("\n    def ", selection_start + 6)
        selection = source[selection_start:selection_end]
        for operation in (
            "review_readiness(",
            "refresh_live_preflight(",
            "execute_once(",
        ):
            self.assertNotIn(operation, selection)
        self.assertIn('library_tree.bind("<<TreeviewSelect>>", show_library_selection)', source)
        self.assertIn("library_transfer_button.configure(command=library_transfer_action)", source)

    def test_local_remove_only_updates_the_catalog(self):
        source = inspect.getsource(launch_ttk_desktop)
        action_start = source.index("    def library_remove_action()")
        action_end = source.index("    def library_move_action(", action_start)
        action = source[action_start:action_end]
        self.assertIn("library_catalog.remove_many(", action)
        self.assertIn("original source files will not be ", action)
        self.assertIn("moved or deleted.", action)
        self.assertNotIn(".unlink(", action)
        self.assertNotIn("shutil.rmtree(", action)

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

    def test_folder_transfer_cp932_rejection_is_visible_in_normal_error_report(self):
        message = format_library_operation_failure(
            LibraryFolderPackageAdapterError(
                "This folder contains text that needs CP932 character substitutions. "
                "The Manager will not silently alter it for transfer; use source text "
                "that needs no substitutions. No device checks or changes occurred."
            )
        )

        self.assertIn("TRANSFER PREPARATION STOPPED", message)
        self.assertIn("text needs review", message)
        self.assertIn("source was not changed", message)
        self.assertIn("needs no CP932 substitutions", message)
        self.assertIn("No device checks or changes occurred", message)
        self.assertNotIn("Review the details and prepare again", message)

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
