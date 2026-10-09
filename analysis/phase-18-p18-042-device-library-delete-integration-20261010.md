# P18-042 Device Library Delete integration — 2026-10-10

Approved owner task: Device Library integration, evidence closeout, tests,
independent R3 review and related host-only follow-on work. Risk: **R3**.
Starting commit `5966933388137138230140deca7b244d5bb74a8b`; branch
`task/P18-042-device-library-delete`; isolated development checkout
`/external/local-path`. The older reference
checkouts and original P18-041 checkout remain untouched. No push or merge.

## Delivered behavior and boundary

**IMPLEMENTED / TESTED OFFLINE:** Device Library toolbar and Device menu
Delete callbacks, one readable Delete/Cancel dialog, responsive shared
background controller, progress and error messages, safe preparation
cancellation, post-confirmation close/cancel protection, and automatic refresh
from the independently verified complete post-delete archive. Cancel is the
default keyboard/window-close decision. Normal review exposes filename,
model, operation, storage-change warning and backup/no-retry guidance; no
fingerprint or protocol details. Detailed result/error evidence stays under
More → Technical Details. A widget refresh failure is reported separately
from evidence verification failure; neither is hidden as successful refresh.

`device_library_delete_execution.py` binds the exact row/offset/path/payload
and displayed blob to its immutable complete archive, re-admits it before
opening the lazy runtime, and requires fresh complete raw-state equivalence
before review. One explicit Delete choice pins the complete frozen owner
identity and uses the existing canonical confirmation internally. Candidate,
audit, source, capacity, transaction and baseline are sealed by P18-041;
approval cannot authorize a second bundle. The service discards authorization
and closes its runtime at every terminal boundary. Teardown cancels only
read-only preparation and releases undelivered prepared reviews.

It reuses `ExperimentalRootTxtDeleteFacade` / `RootTxtDeleteBundle`, pinned
runtime, production runtime provider, shared persistent safety owner,
coordinator, guarded sender, independent Delete verifier and complete-backup
implementation. Existing root ADD gains only an explicit progress callback
argument; its default behavior is unchanged. Delete preparation gains
cooperative cancellation/progress callbacks. The USB sender, transport,
transaction format, claim schema, marker and global lock implementation are
unchanged. New UI uses the existing shared `OperationController`; no second
live pipeline. Old transfer review is cleared before Delete; tree clicks and
stale transfer-review callbacks cannot invalidate an active Delete result.

**Exact admitted execution scope:** only Sony VNW-V15,
`root\IC_P18_041G_CLOCK_01.txt`, exact 29-byte fixture payload SHA-256
`9541c1b9d09ee7d4ab91c704755c4bea8b2022c3bb8f50aa15c1a990bf80c35d`,
unreferenced target, supported protected-state geometry. It remains
Experimental and needs a fresh matching displayed complete backup, a new
complete preflight backup, final execution-equivalent complete backup/capacity,
one owner confirmation and the canonical single-use lifecycle. A successful
send alone is insufficient: native integer zero, complete independent
post-backup, exact sole removal, survivor/prefix/timestamp/checksum and
protected-state checks, terminal evidence and marker resolution precede UI
completion. Any uncertain started result retains the existing fail-safe lock
and no retry. Unsupported selections have no enabled Delete affordance.

**PHYSICALLY DEMONSTRATED:** only P18-041's single exact observed operation;
[canonical closeout and hash inventory](phase-18-p18-041-physical-delete-closeout-20261010.md)
verify all 43 original artifact hashes without alteration. No independent
USB bus trace exists. P18-042 GUI execution was not physically tested.

**NOT SUPPORTED:** arbitrary root TXT, BMP, nested files, directories,
subtrees, root/system entries, ambiguous/multiple selections, VNW-V10,
Restore, recovery or interrupted-write testing. General TXT admission is not
silently promoted from one successful fixture. Existing host candidate rules
cover more geometry, but no reviewed physical class-level envelope exists;
root-parent marker/auxiliary/content behavior outside the demonstrated case
needs scoped validation. The actual preserved post-delete library no longer
contains the admitted fixture, so Delete is disabled for its surviving files.
No replacement of that fixture or repeat write is authorized by this task.

## Validation and review packet

Supported Python 3.12.14 via existing reference runtime, with `PYTHONPATH=src`
inside this isolated checkout (no combined infocarry import path). Tests use
only injected fake USB backends and temporary safety stores.

- New service tests: exact selection, unsupported/ambiguous/multiple paths,
  forged/missing/changed targets, raw auxiliary drift, cancel/teardown,
  candidate/owner rebinding, stale/reconnect-equivalent state, one sender,
  consumed claim/resolved marker/clear lock, no reuse, nonzero completion,
  disconnection, missing/bad complete post-backup, corrupted result, no guessed
  refresh, global lock refusal and useful failure categories.
- Actual ttk callback tests execute extracted production callback bodies with
  lightweight widgets and the real threaded controller/main-thread callback
  queue: one dialog, cancel, stale selection before/during dialog, duplicate
  clicks, cancel before execution, refresh/error separation, disconnect,
  nonzero completion, post-result evidence corruption, close protection and
  teardown suppression. No GUI visual observation is claimed.
- Focused Delete/integration/planning: **40 tests passed**; existing desktop
  regressions: **43 passed**. Existing exact experimental sender/lifecycle,
  transfer, backup, reconnect and guarded-write tests remain in the portable
  suite.
- Initial full portable run: **1,128 run, OK, 3 established intentional skips**.
  Corrected final portable run: **1,133 run / 1,130 passed / 3 established
  skips**, 124.777s, exit 0. Log: `/external/local-path`.
- `compileall src tests` and `git diff --check` pass.
- Strong independent exact-code-head R3 **PASS, P0/P1/P2=0/0/0** after one
  material correction round at `300bd0cdd5b5faf15fac96e403de32225d0948be`.
  [Canonical independent report](phase-18-p18-042-independent-r3-review-20261010.md)
  records independent diff/source/test/evidence inspection, 40 corrected
  integration tests, 121 dependency regressions and full-log verification.
  No production readiness or physical GUI validation is implied.

## Follow-on work / remaining validation

[Follow-on structural analysis](phase-18-p18-042-follow-on-delete-analysis-20261010.md):
root BMP has two synthetic repacker/survivor checks; all 132 actual nested TXT
files pass pure structural checks, 127 pass protected-state derivation and five
referenced targets correctly refuse. An actual nested BMP host probe passes.
Empty folders retain serialized parent markers; the existing file repacker
rejects directory deletion and serialized subtree ownership remains unresolved.
No optional class was enabled or physically demonstrated. Raw data remains
outside Git. Further generalized root TXT/BMP admission should reuse these
same seams and obtain separate scoped review/physical evidence.

Task physical counters: USB requests **0**, physical writes **0**, real
`0x101b` **0**, production claim consumption **0**, production sender-marker
mutations **0**, production global-lock mutations **0**. Fake counters exist
only in temporary tests. GUI visual/packaged cross-platform smoke and any
physical validation require further evidence; no CI is claimed. Physical
atomicity and interrupted-write recovery remain unresolved.

## Independent review correction round 1

Independent R3 inspected exact integration head
`0f4dded047112c3aee45415a7c1df830e2f099b3`, independently verified the 43
artifacts and eight report hashes, reran actual before/post verification, and
ran 39 integration tests plus 121 dependency/desktop regressions. Initial
findings: **P0=0 / P1=0 / P2=1**. The only P2 was an actual UI interaction:
`show_selection()` overwrote the main footer's terminal Delete warning with a
read-only text-preview message. The dedicated Delete status retained the
warning, but the main footer could obscure the indeterminate/locked outcome.

Correction restores both status variables after selection/control refresh.
The callback harness now executes the real `show_selection()` and real stale
transfer-review invalidator, preserving terminal messages in both places and
proving that a stale transfer review cannot discard the shared controller's
active Delete result. Focused integration/planning now **40 passed**.
Pre-correction final code-head suite: **1,132 run / 1,129 passed / 3 established
skips**, 116.749s. Corrected full run passed 1,133 tests with the same three
established skips; exact-code-head re-review passed P0/P1/P2=0/0/0.
External independent report: `/external/local-path`.

Additional host check: all four actual surviving root TXT files in the
preserved post-delete backup pass the existing pure structural model and
protected-state candidate derivation. This corroborates host modeling, but
does not establish a physical class-level envelope; independent review agrees
the exact fixture execution gate must remain. Result record is outside Git:
`/external/local-path`.

## Final disposition

**READY_FOR_HARDWARE_TEST** for the implemented, host-tested, independently
reviewed exact Device Library UI path. Authorized offline work packages A–F
are complete; G improved callback coverage and completed the bounded follow-on
investigation. Only the original P18-041 exact observed operation is physically
demonstrated. Arbitrary root TXT/BMP/nested/directory/subtree execution remains
unavailable. No production readiness, GUI visual observation, packaged
cross-platform validation, independent USB trace or new physical behavior is
claimed. Further hardware use needs separate operation-specific owner approval;
this task performed none. Do not repeat the original experiment by inference.

Local checkpoints: `4d79453` evidence closeout, `0f4dded` integration,
`300bd0c` reviewed correction. A documentation-only closure follows; final
exact-head acknowledgment is in `/external/local-path`.
No source/test changes follow the reviewed correction. Branch is
`task/P18-042-device-library-delete`; no push/merge. Recommendation: establish
an ordinary root-TXT class envelope using the existing host model and scoped
physical evidence, then reuse the same seams for one root BMP. Directory and
subtree work stays behind unresolved serialized-marker ownership.

Validation log `p18-042-r3-correction-full-tests.log` SHA-256: `e83d7cea6251650d5958c2ce98ed9cf828b7e3005ac3f8fbf5339ffc2c68c186`.

Validation log `p18-042-r3-correction-focused.log` SHA-256: `4a4bd368c13b311b00af197ace4e07820ca2a3f3052c091581050ba826b221ba`.

Validation log `p18-042-desktop-tests.log` SHA-256: `5f9020d751c8e646bb196c5a6579bc07fbeb3817cb5de4c7aa6b84c953d0e549`.
