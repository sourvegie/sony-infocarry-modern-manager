# Sony InfoCarry Toolkit

## Development source and local research archive

This sanitized checkout is the future development source of truth and its
verified `main` commits are pushed normally to the approved private remote:
`https://github.com/sourvegie/sony-infocarry-modern-manager.git`.

The sibling evidence-bearing `modern-client` checkout is a read-only local
research archive. Do not commit product development there, rewrite or clean
its history, or push it. Older commit SHAs mentioned in these documents refer
to that preserved local research history unless explicitly identified as a
commit in this sanitized repository. Raw captures, complete backups, live
operation evidence, original Sony software, and transaction-range binaries
are intentionally absent from this source tree.

## Current Agent Handoff — Read This First

The authoritative project documents, in order, are:

1. `PRODUCT_VISION.md` — the user-approved product scope.
2. `RISK_REGISTER.md` — release blockers and mandatory safety controls.
3. `ROADMAP.md` — verified progress and the ordered next milestones.
4. `README.md` — current commands and development setup.

The project is no longer in open-ended protocol-discovery mode. Detection,
complete read-only backup, deterministic export, a narrowly guarded
existing-text replacement, and one narrowly scoped guarded new-root-TXT smoke
have been demonstrated. Do not restart completed reverse-engineering phases
or continue arbitrary-content research merely because unchecked research items
remain.

### Immediate Objective

Milestones A through F are complete for their defined scopes: the canonical
project is controlled, v0.1 read-only recovery is delivered, v0.2
existing-text replacement has passed its approved guarded live smoke, the clean
legacy new-TXT evidence gate is closed, and the offline new-record model has
passed its fake-transport boundary. Milestone G's guarded workflow has now
completed one separately approved live smoke with full read-back verification.
Milestone H's complete offline selective-delete gate is now closed by commits
`b5bae4b` and `c8162c0`; keep the normal new-file and delete GUI/CLI actions
disabled and preserve the narrow scope of all live evidence. Milestone H.1 —
live-delete generalization and readiness — is blocked and parked pending new
independent evidence because the captured fixture builder still requires
opaque attempt-02 timestamps and capture-specific fixed-state blocks. Do not
continue speculative deletion work, prepare a live-delete protocol, or request
another capture automatically. Milestone I.6 has completed one narrowly
constrained live one-folder/one-TXT package smoke with `0x0000` completion and
exact independent read-back. Milestone I.7 has now completed its offline
timestamp/fixed-state characterization and one separately approved controlled
legacy root-TXT add (`I7-LEGACY-ADD-01`); no deterministic fresh rule was
established. The add evidence shows one persisted new record, regeneration of
shared timestamps, and unchanged all-zero fixed state. The subsequent isolated
state experiment records bounded display-history, Mark-1, and Bookmark-1
transitions without establishing general timestamp or nonzero-state
construction. I.8 provides an ordered
source-bound multiple-TXT logical model with strict authoring and no device
candidate. I.9 now provides typed offline TXT/BMP validation with no device
candidate. I.10 now provides a flat manifest-driven representative ebook plan
that rejects nested sections. Protocol generalization remains the active
objective for offline evidence review and H.2; H.2
deletion generalization remains a separate fail-closed offline track. These
milestones may proceed independently of the parked H.1 blocker.
Milestone I.0 evidence audit, I.1 logical package model, and I.2 blocked
transfer preview are complete in commits `5a3c55b`, `0db6593`, and `05e29cb`;
the suite now passes **294 tests** at that checkpoint. The owner-approved
capture-7 folder/package sequence then satisfied the exact fixture evidence
gate in `139c658`; offline fixture-boundary hardening is complete in
`465120f`, with ten focused tests and a suite of **301 tests**. General
folder/package timestamp generation and fresh fixed-state derivation were
compared offline in `analysis/phase-13-milestone-i7-timestamp-fixed-state-characterization-20260823.md`;
no safe generalization was established. The portable I.7 matrix is
`analysis/phase-13-milestone-i7-timestamp-fixed-state-evidence-20260823.json`,
and `i7_readiness.py` fails closed unless both rules are independently verified
across multiple cases. Milestone I.4 is complete for its
offline/fake-only constrained modern policy: preserve existing timestamps, use
one explicit frozen timestamp for the three new records, and accept only the
exact capture-7 all-zero fixed state. This is not legacy timestamp
equivalence. Commits `9287c06`, `39c6f9f`, and `a3bff5a` add the separate
modern policy, exact fixed-state preflight, fail-closed candidate/capacity
gate, package-specific authorization, and independent read-back verification;
the suite now passes **329 tests**. The unexecuted owner protocol is recorded,
but general folder/package live eligibility remains blocked by physical
transport proof and a separate explicit live-smoke approval.
Milestone I.5 resolved the native total model limit offline: parsed `0x0019`
response `+0x08` is the 3,145,728-byte dispatcher limit. Milestone I.6
controlled package live-smoke readiness is complete for the narrow approved
policy: live authorization bound the complete parsed response, raw SHA-256,
device, baseline/candidate model lengths, and derived growth values. The fake
workflow and isolated runner were prepared in `09452be`; the owner-approved
attempt 01 stopped before `0x101b` because of a stale backup-verification
clock, with no retry. Attempt 02 then issued exactly one `0x101b`, received
`0x0000`, and produced complete pre/post evidence. The initial read-back audit
was preserved as terminal because the verifier had not yet allowed the known
payload-dependent `0x0024` and `0x8004` probe changes; offline correction
`cf7803b` and independent re-verification now confirm the constrained result.
The complete suite is **360 tests**. No normal package GUI/CLI action is
authorized, and no broader package compatibility or physical interrupted-write
recovery is claimed. See
`analysis/phase-12-milestone-i6-package-live-smoke-attempt-02-result-20260823.md`.
The sanitized source-of-truth promotion is complete in `07f0db9`, and the
non-destructive local Library foundation, offline Prepare workflow, and crude
ttk Library section are complete in `35f4406`, `7650aaa`, and `9dada7b` with a
portable suite of **408 tests** (three evidence-dependent skips). The current
I.7 preparation slice adds nine focused offline tests and the timestamp
validator slice adds twelve synthetic tests, bringing the suite to
**429 tests** with the same three intentional skips. The operator-ready
protocol is `analysis/phase-13-milestone-i7-legacy-add-clock-state-experiment-20260823.md`;
the read-only support module and separate support command only prepare and
ingest evidence. The approved add-01 evidence is synthesized in
`analysis/phase-13-milestone-i7-legacy-add-01-results-20260823.md` and its JSON
companion. The self-contained Windows 2000 timestamp tool is
`support/windows2000-timestamp/`; its logs are ignored and validated only by
`scripts/validate_timestamp_logs.py`. The harmless two-stamp dry run passed,
and the separately approved state experiment on `root\\IC_I7_CLOCK_01.txt`
completed with isolated display-history, Mark 1, and Bookmark 1 backups. Its
derived report is `analysis/phase-13-milestone-i7-state-experiment-20260824.md`;
the raw evidence remains outside Git. This state evidence does not resolve
general timestamp generation or fresh fixed-state derivation, and deletion
remains separately gated.
Keep package transfer disconnected from the Library and keep all normal
GUI/CLI write and delete actions absent.
Functional parity with the legacy Manager takes priority over Library polish,
visual refinement, advanced rendering, packaging, or other aesthetic work:

1. Preserve the canonical source tree and all original evidence. Copy; never
   move or delete. Keep generated output and environments out of release
   artifacts.
2. Keep the separate `InfoCarry-Toolkit` checkout read-only. Reimplement or
   deliberately copy reviewed conversion concepts into this canonical package;
   never combine the two `infocarry` packages on one import path.
3. Retain the clean capture-04 evidence and exact root-level TXT candidate
   reconstruction; do not request a redundant legacy add capture.
4. Preserve the completed Milestone F new-TXT-specific fake-transport
   integration boundary for partial transfer, disconnect, timeout,
   cancellation boundaries, ambiguous/nonzero completion, malformed read-back,
   and zero automatic retry.
5. Preserve Milestone G's narrow guarded workflow behind fresh-backup, exact
   authorization, one-shot transfer, and full read-back gates. Keep the normal
   GUI/CLI action disabled; the one approved live smoke is evidence for the
   exact tested scope only.
6. Treat cancellation before the device-changing request as ordinary and safe.
   Once `0x101b` begins, report disconnect, timeout, or cancellation as an
   indeterminate device outcome; never promise atomicity or retry automatically.
7. Preserve the completed selective-delete gate as an independent result; never
   infer delete safety merely from successful creation. Attempt 02 closes the
   persisted legacy deletion-effect evidence gate for one disposable leaf
   item, and commits `b5bae4b`/`c8162c0` close the narrow offline builder,
   authorization, verification, and fake-transport failure gates. Preserve
   both attempts as evidence, do not request another legacy capture, and keep
   modern delete and product exposure disabled.
8. Keep H.1 parked pending new independent evidence. Proceed with Milestone I's
   offline evidence, constrained package safety, native-capacity binding, and
   fake-only readiness only; do not generalize the capture-7 fixture into a
   live or normal GUI/CLI package action.
9. Only after create/delete/package primitives are proven, connect local
   Library, Prepare, selected transfer, and batch queue workflows. An early
   interface may remain crude and engineering-focused.

10. Treat this sanitized checkout as the only development source of truth.
    Push each verified commit normally to `origin/main`; keep the sibling
    evidence-bearing research archive read-only and outside product history.

The browser and Qt/PySide options remain explicitly deferred. See
`analysis/phase-9-gui-runtime-and-integration.md` and
`docs/USER_GUIDE.md`. The current priority rationale and agent handoff are in
`analysis/core-transfer-priority-reset-2026-08-22.md`.

### Hard Scope Boundary

- Preserve the completed v0.1 read-only behavior and the completed v0.2 safety
  sequence as regression-tested release boundaries.
- Do not perform another live device write, delete, restore, firmware/unlock
  command, alternate-mode experiment, or new Windows capture without a new,
  explicit approval.
- Do not intentionally test an interrupted write on the only valuable unit.
  Device commit atomicity is unknown; deliberate interruption/recovery testing
  requires a second or sacrificial VNW-V15 and its own approved protocol.
- Keep new-file creation and delete absent from the normal GUI/CLI. A separate
  explicit approval is required before any modern live-delete smoke; no live
  delete is authorized by this offline closure.
- Do not interpret **Transfer all ready items** as synchronize, delete, replace
  unmatched device content, or legacy send-all. It is an additive queue concept
  and remains preview-only until every queued operation has its own proven gate.
- Do not implement legacy send-all/receive-all semantics.
- Restore, firmware/unlock, alternate modes, and destructive synchronization
  remain excluded. Milestone H.1 is blocked and parked pending new independent
  evidence. I.7–I.10 have completed their defined offline slices; H.2 remains
  blocked and parked as an offline fail-closed research track. None can
  authorize a live transfer or product exposure. J.0–J.2 are complete;
  J.3 device-aware Library planning and aesthetic GUI work remain deferred.

### Definition of Completed Milestone H, Parked H.1, and Active Milestone I

Milestone H is complete when:

- the stable Milestone G live-smoke and Milestone H attempt-01 evidence copies
  remain hash-verified outside ignored `tmp` and Desktop-only locations;
- one isolated legacy Manager deletion has a standalone native USB log,
  complete before/after Manager snapshots, and complete macOS pre/post backups
  proving exactly one persisted removed disposable path with no unrelated
  payload change. Attempt 02 satisfies this deletion-effect evidence gate;
  explicit Manager success wording and a trustworthy native request-4 result
  are unavailable limitations, not reasons to request another capture;
- the deletion candidate, aligned content removal, metadata/pointer rebasing,
  fixed device state, timestamps, completion, capacity effect, and
  Manager-local sidecar behavior are classified as verified, observed,
  inferred, or unresolved without silently filling gaps. For a future modern
  delete, only completion `0x0000` is accepted; missing, ambiguous, malformed,
  or nonzero completion is terminal and never retried;
- a delete-specific builder reproduces the successful fixture exactly or with
  narrowly documented normalization while preserving all unrelated bytes;
- exact device, fresh backup, target, candidate, and transaction binding plus
  an operation-specific confirmation phrase are mandatory;
- fake-transport tests cover pre-start cancellation, post-start indeterminate
  interruption, nonzero/ambiguous completion, malformed read-back, mismatch,
  terminal failure, and zero automatic retry;
- no normal GUI/CLI delete control or modern live delete is enabled before a
  separate explicit approval; and
- the complete canonical offline suite passes; the captured-fixture H gate had
  279 tests and the H.1 readiness slice now passes **283 tests**.

Milestone G remains closed for its narrow root-level TXT scope. It does not
authorize general new files, expose a normal write control, or prove
interrupted-write recovery. Milestone H is closed only for its captured-fixture
offline scope. Milestone H.1 is blocked and parked pending new independent
evidence and must not be represented by a successful fake transfer using
invented timestamps or attempt-02 constants.

Milestone H.1 can close only when the following are either independently
verified from both delete attempts or fail-closed with an explicit blocker and
the smallest safe evidence needed to resolve it:

- the metadata `+0x0c` generation rule is deterministic and supported by
  independent evidence, or remains an explicit live-eligibility blocker;
- fixed-state `0x001b` through `0x001f` is derived from a fresh verified backup
  and exact target without global capture-specific blocks, preserving unknown
  bytes and rejecting unresolved references;
- a framework-independent eligibility result rejects every unresolved target
  rather than presenting fixture reproduction as live readiness; and
- only if those gates pass, a fake-only guarded workflow and an unexecuted
  owner protocol are prepared. No live transport, modern delete, or normal
  GUI/CLI action is enabled by H.1 documentation or tests.

Milestone I remains active for protocol generalization. I.6 has one separately
approved constrained live smoke with exact full read-back; this does not prove
arbitrary package behavior. Capture 7 proves the exact one-folder/one-TXT
legacy fixture and supports an offline golden builder. Milestone I.4 is
complete only for the separate constrained modern policy: one root folder, one
TXT child, preserved existing timestamps, one explicit frozen timestamp for
the three new records, exact capture-7 all-zero fixed state, no state
membership, and no sidecar assignment. I.6 now also has one separately
approved live smoke with exact full read-back for that shape. This is not
legacy timestamp equivalence; arbitrary folders, multiple children, bitmaps,
nested placement, and normal product exposure remain excluded. I.7 is complete
for offline characterization and one approved legacy add-01 evidence case, but
found no safe general rule; the add result is recorded in
`analysis/phase-13-milestone-i7-legacy-add-01-results-20260823.md`. The state
result is recorded in
`analysis/phase-13-milestone-i7-state-experiment-20260824.md`. No deletion
experiment has been performed. The next sequence is offline H.2/J.3 evidence
review. I.8's offline model, I.9's typed model,
and I.10's flat ebook plan are
recorded in `analysis/phase-13-milestone-i8-multiple-txt-offline-20260823.md`,
`analysis/phase-13-milestone-i9-mixed-txt-bmp-offline-20260823.md`, and
`analysis/phase-13-milestone-i10-ebook-plan-offline-20260823.md`; I.10 adds six
focused tests and the suite is **429 tests**.

The current I.4 candidate boundary is offline-only in
`prepared_package_candidate.py`. It revalidates the source bytes, rejects
case-insensitive folder/child conflicts, requires a verified native total-limit
capacity result sufficient for the complete candidate model, preserves the
verified fixed-state bytes, and reports baseline/candidate/transaction hashes.
The I.4 implementation checkpoint passed **329 tests**; the I.5 follow-up
passed **336 tests**, and the I.6 follow-up passes **360 tests**.
`prepared_package_gate.py` then binds that candidate to the exact operation
phrase, device, backup, package, paths, timestamp, fixed state, capacity, and
transaction. `prepared_package_verify.py` independently checks completion,
the candidate blob, path delta, shared bytes, fixed state, and unrelated
objects. `prepared_package_workflow.py` composes those pieces only behind an
explicit fake-transport assertion and never connects to normal CLI/ttk paths.
The isolated I.6 runner has now produced one narrowly verified live result;
these components do not establish arbitrary package live eligibility.

### Milestone I.5 — legacy capacity semantics (2026-08-23)

The native ordinary-worker capacity meaning is now resolved offline: preserved
`VicTwo.dll` data flow copies `0x0019` response `+0x08` into worker context
`+0x24`, and the dispatcher checks prospective `N+M` against that total model
limit. The Manager `+0x528`/`+0x52c` KB display is Manager-local accounting and
is not treated as device free capacity; command `0x0024` is observed to equal
the current dynamic-model length and excluded from capacity authorization;
broader semantics unresolved. Unknown `field_14_be32` remains unnamed.
See `analysis/phase-12-milestone-i5-capacity-semantics-20260823.md`.

The package candidate and authorization now bind total-limit, baseline-model,
candidate-model, growth, remaining-growth, and capacity-source values. The
offline suite was **336 tests** at the I.5 checkpoint after commit `9657e85`.
I.6 commit `09452be` adds parsed-response hashing, native-only live
eligibility, ordered fake workflow coverage, and the isolated runner; the
suite now passes **360 tests**. The approved attempt-02 result is recorded in
`analysis/phase-12-milestone-i6-package-live-smoke-attempt-02-result-20260823.md`.
Physical interrupted-write recovery, arbitrary package transport, automatic
retry, and package GUI/CLI exposure remain unresolved or prohibited.

### Milestone I.6 — controlled package live-smoke readiness (2026-08-23)

Milestone I.6 is complete for one approved constrained smoke. The native
evidence object was created from a parsed `0x0019` response and bound VID/PID,
the complete raw 64-byte response and SHA-256, command, field `+0x08`, the
3,145,728-byte limit, baseline/candidate model sizes, growth, remaining
growth, and evidence source version. Compatibility `available_capacity_bytes`,
Manager UI values, `0x0024`, and `field_14_be32` did not make the candidate
eligible. The runner performed detection, native capacity query, fresh backup,
candidate rebuild, exact authorization, one `0x101b`, `0x0000` completion,
post-backup, and independent read-back. The initial audit remains preserved;
the package verifier's expected payload-dependent boundary was corrected
offline in `cf7803b`, and the preserved result passed independent verification.
The suite is **360 tests**. See
`analysis/phase-12-milestone-i6-package-live-smoke-attempt-02-result-20260823.md`.
The normal CLI/ttk package action remains disabled, and no arbitrary package
or interrupted-write compatibility is claimed.

The v0.1 and v0.2 gates remain closed and regression-tested. Developer ID
signing/notarization remains deferred unless the audience broadens.

### Autonomy and Checkpoints

- Proceed autonomously with inspection, planning, documentation, copying into
  the approved canonical project location, small reversible implementation
  changes, and offline tests.
- Ask before adding a substantial production dependency, changing the
  application stack, performing a live hardware operation, or expanding the
  proven existing-text write scope.
- If filesystem permissions require approval to write the canonical Projects
  directory, request that permission for the narrowly scoped migration; do not
  substitute another hidden working directory.
- When blocked, leave the working tree safe and report the exact unmet gate.

### Verification Command

Use the project virtual environment, not the macOS system Python:

```sh
.venv/bin/python -m unittest discover -s tests -q
```

The macOS system interpreter lacks the pinned PyUSB dependency. A failure such
as `ModuleNotFoundError: usb` from `/usr/bin/python3` is an environment error,
not a project test failure.

### Private remote checkpoint policy

After every completed and verified local commit:

1. Confirm that the commit contains only intended project files.
2. Confirm that no original Sony software, ISO content, device backups,
   USB captures, credentials, private information, generated output, or
   temporary live-operation artifacts are tracked.
3. Run the required focused tests, complete suite, and `git diff --check`.
4. Push the current branch normally to the approved private GitHub remote.
5. Report the local commit SHA and whether the remote push succeeded.

Never force-push, rewrite published history, delete remote branches, change
repository visibility, or upload excluded evidence without explicit owner
approval. A failed push must not discard or amend the safe local commit;
preserve it and report the authentication or connectivity failure.

## Objective

Build and maintain a modern application for exchanging data with the Sony InfoCarry VNW-V15. The first hardware target is macOS, using user-space USB access rather than a custom macOS kernel driver. Keep the communication and conversion cores portable so Linux and Windows support can follow.

The application must:

- Detect only the supported Sony USB device (`VID 0x054C`, `PID 0x001E`).
- Read device information and make complete, reproducible backups before enabling writes.
- Import and export supported InfoCarry content safely; add restore only after
  its separate risk and recovery gates are satisfied.
- Convert Unicode text to conservative Shift-JIS/CP932 for the native text reader.
- Convert TXT and EPUB files into paginated 240 x 320, 1-bit monochrome BMP pages.
- Provide a simple GUI suitable for non-technical users.
- Keep the proven command-line core testable while the v0.1 GUI is built.

## Roadmap Discipline

- Treat `ROADMAP.md` as the implementation sequence and current status record.
- Complete each phase's exit gate before beginning device-changing work from a later phase.
- Update the roadmap when a milestone is verified, including the evidence or test that verified it.
- Label protocol facts as `verified`, `observed`, or `inferred`; never silently promote an inference to a fact.
- Record unresolved questions in the roadmap instead of embedding guesses in production code.

## Reference Material

- Treat `samples/reference/` as read-only.
- Never edit, rename, move, normalize, or overwrite reference files.
- Treat all legacy installers, ISO images, Windows executables, DLLs, drivers, and captured reference traffic as read-only evidence.
- Inspect reference files before making compatibility assumptions.
- Put generated files in `tests/output/`, `tmp/`, or `samples/generated/`.
- Store reverse-engineering notes and sanitized descriptor/traffic summaries under `analysis/`.
- Document verified USB, protocol, encoding, bitmap, pagination, and device-compatibility findings.

## Device Safety

- Default every hardware-facing command to read-only behavior.
- Never send an unknown command or undocumented control request merely to see what happens.
- Require an explicit write-enabling option and interactive confirmation before the first device-changing request.
- Before any write, create and verify a full backup unless the user explicitly stops the operation.
- Use bounded transfer sizes, finite timeouts, retry limits, and cancellation handling.
- Do not run the legacy Windows manager and the modern client against the device simultaneously.
- Keep raw received bytes before parsing them. Never discard the only copy of device data after a parse failure.
- Keep hardware tests opt-in and separate from ordinary automated tests.

## Architecture

- Start protocol discovery and the first client in Python using PyUSB/libusb.
- Separate USB discovery, transport framing, protocol commands, content formats, conversion, and UI code.
- Keep the low-level transport usable independently of the GUI.
- Prefer a small CLI that proves detection, information queries, and backup before adding write support or a desktop UI.
- Port the transport core only if packaging, reliability, or performance evidence justifies it.

## Implementation Priorities

- Prefer conservative device-compatible output over uncertain modern features.
- Keep decoding, character mapping, pagination, rendering, file writing, and device transport separate from the GUI.
- Preserve paragraph breaks and report replaced or unsupported characters clearly.
- Produce uncompressed Windows BMP files with exact 240 x 320 dimensions and 1-bit color depth.
- Make output deterministic: identical inputs and settings must produce identical files.
- Avoid unnecessary dependencies and platform-specific code in the conversion core.

## Quality Expectations

- Add focused tests for encoding detection, CP932 conversion, pagination, EPUB extraction, and BMP compliance.
- Add fixture-based tests for command framing, status handling, chunking, format parsing, and malformed responses.
- Use copies or temporary outputs in tests; never write into `samples/reference/`.
- Run relevant tests after changes and report any checks that could not be run.
- Update user and compatibility documentation when behavior changes.
- Do not claim hardware compatibility unless verified; clearly label inferred behavior.

## Working Style

- Implement working project files rather than stopping at plans or pseudocode.
- Make small, reviewable changes that address root causes.
- Preserve unrelated user changes and avoid destructive Git operations.
- Ask before adding a large production dependency or changing the application stack.
