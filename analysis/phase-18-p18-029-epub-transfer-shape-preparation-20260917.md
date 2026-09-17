# P18-029 — EPUB Conversion + Transfer-Shape Preparation

Date: 2026-09-17
Branch: `task/P18-029-epub-transfer-shape-preparation`
Risk: R2/R3-boundary host-side parser, persistence, and transfer-review integration
Physical device activity: none

## Pre-publication anomaly resolution

The earlier report used the absolute path
`/Users/stardust/Projects/InfoCarry-Toolkit/analysis/phase-18-p18-029-epub-transfer-shape-preparation-20260917.md`.
This checkout is the canonical development checkout for the
`sony-infocarry-modern-manager` remote, and the expected record is present and
tracked at this repository-relative path:

`analysis/phase-18-p18-029-epub-transfer-shape-preparation-20260917.md`

The path discrepancy was therefore a reporting/repository-name typo only. No
cross-repository copy or historical/reference-file correction was needed.

The second anomaly was a real provenance error in the initial local branch.
The requested base `8aaddd2bd29bb10087083e9f1bf5ab863af4bce8` was fetched and
verified as the exact P18-028 commit. The initial P18-029 work at
`2edda50626bfffb615a2c5bbb306e89aa0140a46` had instead been based on an older
P18-026 continuation. That old branch is preserved as
`backup/P18-029-before-base-correction`; the final work is rebuilt directly on
the requested base. No merge was performed.

### Exact test-collection comparison

The canonical P18-028 base collected 843 tests with no collection errors. The
initial wrong-base P18-029 tree collected 830 tests with no collection errors.
The 13-test deficit was not caused by pyusb, dependency gating, a renamed test
module, or a deliberate P18-029 test restructuring. The old branch retained
the 16 new P18-029 tests but omitted 29 exact canonical tests inherited from
P18-028, producing the observed net change of `843 - 29 + 16 = 830`.

The omitted canonical tests were:

- `tests.test_content_workspace.ContentWorkspaceTests`:
  `test_bmp_is_deterministic_and_payload_mutation_changes_identity`,
  `test_cancellation_is_safe_before_preparation`,
  `test_epub_is_explicitly_deferred` (the final branch retains this test slot
  with its behavior updated to supported host-only EPUB),
  `test_folder_hierarchy_keeps_legacy_manifest_and_canonical_identity_distinct`,
  `test_library_prepare_preview_and_review_share_canonical_identity`,
  `test_library_source_change_discards_persisted_artifact`,
  `test_prepared_folder_uses_existing_hierarchy_adapter`,
  `test_prepared_package_uses_existing_canonical_adapter`,
  `test_review_rechecks_source_before_using_saved_artifact`,
  `test_settings_and_logical_root_participate_in_identity`,
  `test_strict_unsupported_character_is_typed`, and
  `test_txt_is_deterministic_and_surfaces_normalization`;
- `tests.test_desktop_ttk.DesktopTtkMessageTests`:
  `test_host_only_terminal_state_is_truthful`,
  `test_normal_library_formatters_hide_technical_identities`,
  `test_normal_ttk_library_path_uses_controller_and_technical_details_boundary`,
  and `test_prepare_and_preview_use_the_same_canonical_artifact`;
- `tests.test_library_transfer_readiness.LibraryTransferReadinessTests`:
  `test_destination_exists_and_unsupported_profile_have_typed_states`,
  `test_error_mapping_covers_safe_recovery_actions`,
  `test_missing_fresh_capacity_is_not_send_actionable`, and
  `test_typed_readiness_is_deterministic_and_separates_diagnostics`;
- `tests.test_operation_controller.OperationControllerTests`:
  `test_blocking_work_runs_off_ui_thread_and_completion_is_marshaled`,
  `test_close_discards_queued_callbacks_for_destroyed_ui`,
  `test_conflicting_second_operation_is_rejected`,
  `test_invalidated_late_result_is_discarded`,
  `test_newer_operation_wins_after_input_revision_change`,
  `test_progress_is_marshaled_and_current_only`,
  `test_safe_host_cancellation_returns_cancelled_outcome`,
  `test_thread_start_failure_is_typed_and_clears_busy`, and
  `test_worker_exception_is_typed_failed_outcome`.

The corrected branch retains all 843 canonical tests, updates the deferred EPUB
test's expectation to the approved bounded host-only behavior, and adds the 16
new EPUB/shape tests. Its full collection is therefore 859 tests.

## PyUSB disposition

The repository already declares `PyUSB==1.3.1` in `pyproject.toml`. The
supported Python 3.12 virtual environment initially lacked that declared
dependency, so the earlier ad-hoc no-device stub was not an acceptable basis
for the final validation. The temporary stub was removed and is absent from
the worktree, Git status, and tracked files. Real `PyUSB==1.3.1` was installed
in the supported virtual environment. No production source was changed to
accommodate a stub, and no stub exported a device or made a USB test exercise
hardware; the final suite ran with the real package and the repository's
existing no-device test isolation.

## Implementation and safety boundary

`ContentWorkspace` now accepts bounded EPUB 2/3 ZIP/OCF sources. It validates
archive paths, duplicate names, symlinks, encryption, compression and resource
limits; rejects unsafe XML declarations and DRM/encryption metadata; follows a
local OPF manifest and linear spine; extracts text without executing XHTML,
JavaScript, CSS, or remote resources; applies the existing strict CP932/CRLF
normalization; and emits a canonical `PreparedContentArtifact`. Only local BMP
bytes already accepted by the exact 237×320 1-bit validator become BMP children.
Optional materialization is new-only and contains prepared content metadata,
not device candidate bytes.

`TransferShapeAssessment` is a descriptive, host-only classification layer.
It recognizes the exact reviewed VNW-V15 TXT → BMP → TXT shape, labels bounded
flat direct-leaf TXT/BMP shapes as future-only, and marks nested or unsupported
shapes unmappable. It does not construct candidates, authorize operations,
open USB, call a sender, or alter the capability envelope. EPUB preparation
and review remain ineligible for live transfer. EPUB workflow previews expose a
`HostOnlyTransferPreview` record with the plan/report only; the generic
candidate and authorization attachment methods are not exposed on the EPUB
preview object.

The existing live boundary remains exactly VNW-V15 direct-leaf
`TXT → BMP → TXT`; no second sender or transfer pipeline was added. VNW-V10
remains `UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED`.

## Host validation

- Focused P18-029 tests (`tests.test_content_workspace`,
  `tests.test_transfer_shape`): 28 passed.
- P18-026 → P18-028 regression set: 188 passed.
- Full Python 3.12 portable suite with real PyUSB: 859 passed, 3 intentional
  skips.
- `PYTHONPATH=src .venv/bin/python -m compileall -q src tests`: passed.
- `git diff --check`: passed.
- `CAPABILITY_MATRIX.md`: unchanged from the requested base.

The first exact-head independent R3 review found P1/P2 findings: the EPUB
preview had exposed the generic candidate/authorization attachment methods,
and Markdown hard-break whitespace invalidated the claimed diff check. Both
were corrected in the next bounded round. The EPUB preview now uses the
method-free host-only record above, and the analysis record contains no
trailing whitespace. The corrected commit requires a fresh exact-head review.

No hardware-facing or device-changing operation was run. Physical counters
are all zero: USB/device operations 0, sender calls 0, real `0x101b` 0, claims
consumed 0, sender-marker mutations 0, and installation-wide-lock mutations 0.

## P18-030 recommendation

The best bounded next physical-validation shape is the direct-leaf four-child
sequence `TXT → BMP → TXT → TXT`. It adds one TXT leaf and therefore tests
ordered multi-leaf binding with minimal expansion from the already verified
three-child shape, while preserving the no-nesting, no-overwrite, no-delete,
and no-merge boundaries. It requires a separate approved host/evidence task,
fresh capability review, owner authorization, and an approved physical
procedure. It was not physically tested in P18-029.

## Publication and review checkpoint

This record is updated before final publication. The final commit, published
branch, focused PR, macOS/Windows CI identifiers, and independent exact-head
R3 result must be recorded here before PM acceptance. The required host-only
R3 disposition is `P0=0, P1=0, P2=0 — PASS`, followed by
`READY_FOR_HARDWARE_TEST`; no merge or physical action is authorized by this
task.
