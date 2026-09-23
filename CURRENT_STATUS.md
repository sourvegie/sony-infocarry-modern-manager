# Current Project Status

Date: 2026-09-24

## P18-037 post-merge closure

PR #65 was merged into `main` with the standard merge-commit method after
verification of the exact approved PR head
`87bc260e3a669bb61e8a31967068ec58dc36bee1`. The merge commit is
`9449b19600476f86f67ff2cb33179aaacab30a65`; `main` now includes that merge
and this documentation-only closure. The final offline macOS and
Windows checks and macOS/Windows package checks were green; the repository
has no configured required-review gate and no submitted review records for
this PR. This closure is documentation-only: no physical device operation
was performed, and historical validation evidence and prior dated status
snapshots remain unchanged. References below to PR #65 being open or
unmerged describe the state at the dates of those snapshots.

## P18-037 — Local Library ↔ Device Library Manager foundation

P18-037 implements the side-by-side Local Library and Device Library workspace
on `task/P18-037-library-device-manager`, from canonical base
`dfeeb4604b25b77a61c99ff9e0677ed69aa7c8ca`. The Local Library remains a
persistent catalog of references to user files; nested import, search,
multi-selection, persisted sibling ordering, remove-without-deleting-sources,
and compact Details are part of the redesigned window. The generic ordered
TXT/BMP tree and destination planner preserve selected subtrees, validate
source freshness and encoded components, and fail closed on conflicts. Its
offline scale fixture contains 61 directories and 150 mixed leaves. A separate
host-only delete-closure/expected-delta model rejects unsafe or unresolved
selections.

The primary Transfer action first builds the generic offline plan. A single
ordinary root-level Local Library folder can now be adapted transiently into
the existing prepared-package contract only when its revalidated direct-file
children, persisted order, canonical names, and unchanged content match one of
the exact VNW-V15 three- or four-leaf profiles. The transient package is staged
under Manager-owned application state and overlaid in memory; it is not added
to or persisted in the user catalog. It continues through the existing
readiness, fresh-preflight, typed one-shot-confirmation, and execution facade.
The adapter cannot authorize execution, build a device candidate, or transmit.
Both packaged entry points now wire the same lazy production runtime provider;
launch creates no live runtime or operation binding and performs no device
checks, claim, marker, lock mutation, or write. After exact-profile admission
and fresh read-only evidence, the final typed confirmation creates a one-shot
binding tied to that preflight. Runtime configuration fails closed while safe
read-only Manager functions remain available. Generic plans and every
unsupported shape remain host-only; there is no capability-envelope
expansion, alternate sender, or parallel safety path. Generalized/nested live
transfer, arbitrary deletion, and Restore remain unavailable. The accepted P2
finding and R3-bounded corrections are recorded in the [P18-037 analysis
record](analysis/phase-18-p18-037-library-device-manager-foundation-20260921.md).

The 2026-09-23 continuation preserved the owner-stopped `-07` physical
validation as a failed pre-write attempt. Host reproduction showed that the
ordinary-folder adapter's transient prepared package was cleaned before the
sealed operation was reloaded, causing the canonical bundle resolver to fail
closed with `bound artifact is unavailable`; no claim, sender, USB request, or
device change occurred. The host-only correction now materializes a complete
operation-owned prepared package and reloadable catalog snapshot under the
operation evidence directory before sealing, binds their identities and
hashes into the existing operation bundle, and retains them through the full
guarded lifecycle. The user catalog and original source files remain
unchanged. Durable pre-send diagnostics record stable reason codes and claim,
marker, authorization, and sender-start state, while unavailable safety state
and diagnostic-write failures are explicit and the normal UI remains concise
and fail-closed. The focused ordinary-folder regression covers three-/four-leaf
cleanup survival, reload, source/catalog immutability, root-level-only
admission, fake canonical execution, and missing-artifact/diagnostic failure
cases with zero claim/sender activity. The full Python 3.12 portable suite
passes 1,004 tests with 3 documented skips; compile and `git diff --check`
pass. This remains host-only until fresh independent exact-head review, final
macOS/Windows CI, and packaging checks pass; no physical operation is
authorized or claimed.

See the [operation-owned staging analysis record](analysis/phase-18-p18-037-operation-owned-staging-20260923.md).

The previous validated implementation checkpoint `7bda0b18533c7f85aea3d0947ea0802162eeb469`
passed the portable Python 3.12 suite (984 tests, 3 documented skips), the 85
focused adapter/readiness/UI/device-plan tests, `compileall`, and
`git diff --check`. The local arm64/Tk 9 macOS app build and strict ad-hoc
signature verification pass. Local LaunchServices could not scan/open the app
from this `/private/tmp` worktree (`kLSNoExecutableErr`; Spotlight registration
returned `-10822`), but final-head hosted packaging passed its actual smokes:
[Offline tests run 206](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35687898124)
passed on macOS and Windows;
[macOS package run 23](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35687898122)
passed the Apple Silicon build and Japanese-working-directory LaunchServices
smoke; and
[Windows package run 27](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35687898153)
passed the x64 build and frozen-runtime smoke. Independent exact-head review,
including its CP932 display finding and correction, passed `P0=0, P1=0, P2=0`.
The pre-task exact head `f1128d56005ad91e312494a77876829ab18fb670` was used to
prepare physical-validation attempt `-05`. That attempt stopped before device
access when the packaged Manager was found to lack production runtime and
operation-binding wiring; no physical operation occurred. Attempts `-01`
through `-04` also remain stopped and are not relabeled. The owner-authorized
R3 follow-up's reviewed runtime-code commit is
`c3da4c16b8e210132f764d18f45e6ec7aaf22d2b`. Host validation passed: the
Python 3.12 suite ran 995 tests with 3 documented skips; the focused
application-safety, production-provider, guarded-execution, and desktop UI
group passed 83 tests; `compileall` and `git diff --check` passed. Because
local PyUSB is unavailable, these host runs used an external test-only PyUSB
import stub that raises on any USB discovery/session call. Exact-head hosted
[Offline tests run 209](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35725974618)
passed on macOS and Windows;
[macOS package run 26](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35725974796)
passed the Apple Silicon build and LaunchServices smoke; and
[Windows package run 30](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35725974643)
passed the x64 build and frozen-runtime smoke. Independent strong exact-head
review of the corrected implementation passed `P0=0, P1=0, P2=0`. Its first
review had found P2 startup safety-state mutation; startup now inspects state
read-only and the canonical guarded execution boundary retains durable
reconciliation before claim consumption. The local macOS package attempt
stopped before bundle creation because `pip check` found `packaging` missing;
hosted package builds passed. Host disposition is
`READY_FOR_HARDWARE_TEST`. This status update is documentation-only after the
reviewed runtime-code commit. PR #65 remains open and unmerged; no separate PR
was created. No physical operation occurred or is authorized by this task; any
future hardware validation requires new operation-specific owner authorization
and an approved procedure.

The 2026-09-22 continuation followed a stopped `-06` host/device attempt in
which the packaged `+ Add` control was reported disabled; the preserved stop
record contains no live widget/health snapshot, so its exact runtime branch
cannot be distinguished. Source tracing identified incorrect coupling in
Library busy/selection state, while catalog/workflow health remains the
independent valid fail-closed condition. Commit
`d3cafa73c5c254578f95891285f61ca2f9183102` decouples Add and import controls
from device and transfer state, preserves a guard against a conflicting
concurrent Library import, and extends both packaged production-bootstrap
smokes to exercise Add Files/Add Folder with disposable host fixtures and
device/sender calls forbidden. The smoke confirms nested ordinary-folder
import, unchanged source files, Add available with an indeterminate lock and
unavailable live runtime/no operation binding, unchanged lock bytes, and zero
claims/markers. Transfer admission, authorization, claim/marker lifecycle,
sender, and independent verification code were not changed. Focused local
validation passed 43 tests; the full Python 3.12 suite passed 997 tests with 3
documented skips; `compileall` and `git diff --check` passed. Exact-commit
[Offline tests run 211](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35735357171)
passed on macOS and Windows;
[macOS package run 28](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35735357217)
passed the Apple Silicon build and LaunchServices/package smoke; and
[Windows package run 32](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/35735357125)
passed the x64 build and packaged smoke. Fresh independent exact-commit R3
review passed `P0=0, P1=0, P2=0`. A local screenshot of the CI-built Manager
showed `+ Add` enabled; the native chooser windows were not separately
visually inspected. No physical-device validation or device-changing action
occurred. The code commit is pushed to existing PR #65; it remains open and
unmerged. Host disposition remains `READY_FOR_HARDWARE_TEST`, with a new
operation-specific owner authorization and approved procedure required for
any later physical validation.

## Product direction after P18-036

The current product direction and near-term sequence are recorded in
[PRODUCT_VISION.md](PRODUCT_VISION.md) and [ROADMAP.md](ROADMAP.md). The
decision rationale is in the [dated analysis record](analysis/phase-18-post-p18-036-product-direction-20260921.md). This documentation update does not change a capability or authorize a device operation.

## P18-036 — Everyday content preparation and transfer review UX

P18-036 is the R2 host-only Content journey update on
`task/P18-036-everyday-content-transfer-review`, based exactly on
`a13bdecc8381b7d8414b0361203445f96536df11`. Add, prepare/preview, arrange,
and transfer review now have a clear owner-facing sequence. Only the exact
reviewed VNW-V15 TXT → BMP → TXT and TXT → BMP → TXT → TXT shapes are
identified as transferable; preparation and preview remain available for
other valid arrangements, with no capability or guarded-transfer behavior
change.

The portable Python 3.12 suite passes (933 tests, 3 intentional skips);
`compileall`, `git diff --check`, and the local arm64 app build/signature check
pass. Fresh CI passed the macOS and Windows offline suites and both package
workflows, including hosted macOS LaunchServices and Windows packaged smokes.
The content journey now shows source-specific normalization locations for EPUB
and prepared-package imports, and clears transfer review when a source changes.
PR #63 is open against `main`; its analysis record binds package evidence to
the runtime/code head before the following documentation-only evidence update.
The earlier local LaunchServices attempt could not open the app from
`/private/tmp`, and a direct smoke launch stopped during local Tk/AppKit
registration before writing a report. Owner Finder/visual validation remains
pending. No physical-device access or device-changing operation occurred. PM
acceptance remains pending; see the
[P18-036 analysis record](analysis/phase-18-p18-036-everyday-content-transfer-review-20260920.md).

## P18-035 — macOS first-class owner app and read-only Device Home

P18-035 is in progress on `task/P18-035-macos-owner-app-device-home`, based
exactly on `3b6697eac01b6c35d588d163325bedb99ddf76ff`. The task adds an
Apple Silicon onedir `.app`, bundled CPython/Tcl-Tk/PyUSB/libusb, a first-tab
read-only Device Home, complete-backup history/actions, explicit capacity and
transfer-shape wording, and a centralized path abstraction. The historical
macOS application-support directory remains authoritative for claims,
sender-start state, and the installation-wide lock; no state migration or
device capability expansion occurred.

Local arm64 packaging and strict ad-hoc signature verification pass. The
focused safety, desktop, and packaging suite is 40/40; the full portable suite
is 926 passed with 3 intentional skips; `compileall` and `git diff --check`
pass. The local arm64 package build and strict ad-hoc signature verification
pass. The accepted runtime/code/package head passed offline CI on macOS and
Windows, the macOS package and LaunchServices smoke, and the Windows package
smoke. The macOS smoke passed from a Japanese working directory. The local
isolated `/private/tmp` LaunchServices indexing limitation remains; owner
Finder and visual checks are pending. The final PR follow-up is documentation
only and retains artifact evidence for the accepted runtime head. PM
acceptance remains pending. No physical device access or device-changing
operation occurred. See the
[P18-035 analysis record](analysis/phase-18-p18-035-macos-owner-app-device-home-20260920.md).

## P18-034 — Windows packaging & deployment baseline (host-only)

P18-034 establishes a reproducible Windows x64 one-folder build of the
existing ttk Manager with CPython 3.15.0rc2 and bundled Tcl/Tk 9.0.4. The
exact-shape capability behavior and disabled Send path are unchanged. The
packaged CI smoke passed without Python on `PATH`; the full Python 3.12 suite
passed on both macOS and Windows (891 tests per platform). Fresh review
corrections are recorded in the
[P18-034 analysis record](analysis/phase-18-p18-034-windows-packaging-baseline-20260920.md).

PR #61 is open and unmerged. Its Windows package artifact is
`InfoCarry-Manager-windows-x64-py3.15.0rc2-tk9`; the current analysis record
contains its digest and CI IDs. Native ARM64 remains
`BLOCKED_BY_RUNTIME_OR_DEPENDENCY` because the pinned `libusb-package` release
has no ARM64 wheel/source distribution. No device enumeration or physical
operation occurred. PM acceptance remains outstanding, along with a Python
3.15 final-runtime rebuild and clean-machine Windows visual checks.

## P18-033 — Verified VNW-V15 four-leaf capability codification (host-only)

P18-033 is the R2 host-only capability promotion on
`task/P18-033-v15-four-leaf-capability-codification`, based exactly on
`a57a1ec2bbe3bfcfef5633d58136aeb48ff443a4`. It codifies the exact physically
verified VNW-V15 direct-leaf shape `TXT → BMP → TXT → TXT` from the preserved
P18-032 evidence namespace
`/Users/stardust/Projects/InfoCarry-Evidence/phase-18-p18-032-v15-four-leaf-physical-validation-20260920-75FHwI`.
The built-in profile is now
`verified-vnw-v15-four-leaf-direct-v1` with profile SHA-256
`74159694d370665a0055030c6091f564293af1a7e97a4ac5af35280bc21e5a39` and
status `physically_verified_live_supported`.

Normal readiness accepts both exact reviewed direct-leaf orders
`TXT → BMP → TXT` and `TXT → BMP → TXT → TXT`; reordered four-leaf shapes,
five leaves, arbitrary permutations, nesting, overwrite/conflict targets, and
VNW-V10 remain blocked. The four-leaf path uses the existing generic candidate,
authorization, guarded workflow, sender, and independent read-back seams; the
historical validation helper remains only as a compatibility adapter. The
profile records support, but the host foundation still keeps `live_enabled`
false and the normal Transfer action disabled until fresh operation-specific
evidence and owner approval are supplied.

This task has performed no USB or device-changing operation. Physical
counters are strictly zero: USB/device operations 0, sender calls 0, real
`0x101b` 0, claims consumed 0, sender-marker mutations 0, and
installation-wide-lock mutations 0. Focused P18-033 and P18-025→P18-032
regressions are green; the full portable suite is 883 tests with 880 passed
and 3 documented skips. Exact-head independent R2 review passed with
`P0=0, P1=0, P2=0`; PR #60 is open and unmerged against `main`; GitHub
`Offline tests` run `35456901297` passed on both macOS and Windows. PM
acceptance is the remaining gate.
The durable record is the
[P18-033 analysis record](analysis/phase-18-p18-033-v15-four-leaf-capability-codification-20260920.md).

## P18-032 — VNW-V15 four-leaf auxiliary-state policy closure (host-only)

P18-032 is the narrow R3 host-side correction on
`task/P18-032-v15-four-leaf-aux-state-closure`, based exactly on canonical
`737746319162b7ffc65fded19fa47db19d2a69fc`. The exact VNW-V15 four-leaf
operation binding now reuses the existing reviewed semantic auxiliary-state
preservation policy rather than requiring the capture-7 all-zero label. The
candidate, authorization, sealed bundle, and canonical guarded execution
layers remain unchanged; stale policy identities fail closed before any
callback. The exact enabled shape remains only `TXT → BMP → TXT → TXT`,
arbitrary 1–8 execution and VNW-V10 remain disabled, and
`CAPABILITY_MATRIX.md` is unchanged.

Local validation is green: the focused P18-025→P18-031 regression set is
137 passed, the full portable Python 3.12 suite is 880 passed with 3
pre-existing skips, and compile/whitespace checks are clean. This task has
performed no USB/device-changing operation; sender calls, real `0x101b`,
claims, sender-marker mutations, and installation-lock mutations are all
zero. Publication, final-head macOS/Windows CI, independent exact-head R3,
and PM acceptance remain pending. The durable record is the
[P18-032 analysis record](analysis/phase-18-p18-032-v15-four-leaf-aux-state-closure-20260919.md).

## P18-030 — VNW-V15 four-leaf direct-content capability preparation (host-only)

P18-030 is the current R3 host-preparation task on
`task/P18-030-v15-four-leaf-capability-preparation`, based exactly on
`4d8f432040f715380e03796a855f9dd26ede82f3`. It adds an explicit,
validation-only VNW-V15 profile for one absent root with exactly
`TXT → BMP → TXT → TXT`; it does not widen the normal product profile or
enable execution. The reusable candidate builder, authorization gate,
transfer foundation, and independent read-back verifier remain the only
corresponding seams.

The deterministic disposable target is `IC_P18_4LEAF_20260918_01` with
`01-introduction.txt` (28 bytes), `02-page-01.bmp` (10,302 bytes),
`03-ending.txt` (22 bytes), and `04-extra.txt` (28 bytes), for 10,380
prepared payload bytes. Its profile-bound artifact identity is
`4b1aecada00bed36f1c053385453f75028bfebda6488b2fcbf471409f431c7f8`. The
normal readiness/UI path still requires exactly `TXT → BMP → TXT`; four-leaf
content remains a future direct-leaf candidate and is blocked from normal
live eligibility. No physical or read-only hardware operation has occurred;
all device-changing, sender, real `0x101b`, claim, marker, and lock counters
remain zero. Focused P18-030 validation is green; the full portable suite is
870 passed with 3 existing intentional skips, and compile/whitespace/matrix
checks are clean. PR 57 is open and unmerged. Its first final-head gate found
host-only newline portability and whitespace P2 findings; the scoped
correction changes only exact synthetic fixture bytes and record formatting.
Both CI platforms and a fresh independent exact-head R3 review must pass on
the corrected commit before PM acceptance. The durable record is the
[P18-030 analysis record](analysis/phase-18-p18-030-v15-four-leaf-capability-preparation-20260918.md).

## P18-029 — EPUB conversion and transfer-shape preparation (preceding host-only task)

P18-029 was the preceding host-only task on
`task/P18-029-epub-transfer-shape-preparation`, rebuilt from the exact
canonical P18-028 base `8aaddd2bd29bb10087083e9f1bf5ab863af4bce8`. The initial
local attempt was based on the wrong P18-026 continuation; that branch remains
preserved as a backup, and the corrected test collection and provenance are
recorded in the [P18-029 analysis record](analysis/phase-18-p18-029-epub-transfer-shape-preparation-20260917.md).

The bounded `ContentWorkspace` accepts EPUB 2/3 ZIP/OCF packages and routes
safe container/OPF/spine/XHTML extraction through strict CP932/CRLF authoring.
Text-centric chapters become deterministic TXT children; only exact local
237×320 1-bit BMP images become BMP children. Metadata, normalization notices,
unsupported-feature classifications, source/payload hashes, and a canonical
`PreparedContentArtifact` are retained. ZIP slip, normalized duplicates,
excessive entries/size/ratio, malformed XML, external entities,
remote resources, DRM/encryption, and missing package links fail closed or
remain explicitly classified. No network, script execution, candidate,
authorization, sender, USB, device, claim, marker, or lock path is reachable
from the workspace.

`TransferShapeAssessment` is descriptive and host-only. It identifies the
current exact VNW-V15 TXT → BMP → TXT shape, labels other flat TXT/BMP leaves
as future direct-leaf shapes requiring separate capability validation, and
marks hierarchy/unsupported shapes unmappable. Existing live readiness still
accepts only its established exact shape and remains disabled/authorization-
gated; no capability envelope was expanded. Host validation is complete, but
publication, final-head CI, independent exact-head R3 review, and PM acceptance
remain pending. Physical device operations for this task are zero.

## P18-028 — Add Content & Conversion Workspace

P18-028 remains the preceding host-only integration task on
`task/P18-028-add-content-conversion-workspace`. The normal Library workflow
accepts TXT, exact prepared BMP, existing prepared folders, and existing
prepared typed-media packages through one `ContentWorkspace` seam. Its full
suite result was 843 passed with 3 intentional skips. The 240×320 rendering
canvas and 237×320 transferable BMP viewport remain distinct, and preparation
validity remains separate from live eligibility.

## P18-027 — Normal Manager Workflow Productization

P18-027 is the current host-only delivery branch from canonical base
`e052ae94919856fc413547fc2e2ce110ce27f39e`. It productizes the normal ttk
Library path as Add content → Preview → Prepare → Review transfer → Send to
InfoCarry → Verified, while keeping the Send action behind the existing
guarded VNW-V15 facade and performing no physical operation.

The normal path now consumes the P18-026 `PreparedContentArtifact` directly,
uses typed readiness reasons/actions for owner-facing status, and routes
preparation, preview, transfer review, typed readiness review, and read-only
device readiness through one background operation controller. Tk updates are
marshalled to the main thread; source/target/selection revisions discard late
results, and window teardown prevents late callbacks. Candidate/transaction
hashes, claims, seals, profile IDs, milestone IDs, and raw transport details
remain behind the explicit Technical Details action.

Local validation is green: 42 focused P18-027 tests, 242 focused
P18-017→P18-026 regressions, and the full portable suite (830 passed, 3
documented skips). `CAPABILITY_MATRIX.md` is unchanged. Physical counters for
this task are all zero: USB/device operations 0, sender calls 0, real
`0x101b` 0, claims consumed 0, sender-marker mutations 0, and
installation-wide-lock mutations 0. Final-head macOS/Windows CI and fresh
independent strong R3 review remain required before PM acceptance. See the
[P18-027 analysis record](analysis/phase-18-p18-027-normal-manager-productization-20260914.md).

## P18-026 — Unified Prepared Content Workflow

P18-026 is the current host-only integration branch from canonical base
`317e123531c302da0e415bb322e0fe47fd306030`. It introduces one canonical
`PreparedContentArtifact` contract for logical Library root name, ordered typed
children, prepared payload identity/path, sizes, provenance, profile identity,
and deterministic artifact identity. Existing hierarchy, TXT-package,
typed-media-package, and persisted catalog records remain supported as narrow
compatibility views/adapters; no storage migration was added.

The normal Prepare → Preview → Review transfer path now carries the same
canonical artifact identity into the host preview, queue plan, readiness gate,
and transfer-plan adapter. Preparation validity is explicit and remains
separate from the exact reviewed VNW-V15 live-eligibility gate. Valid
hierarchical or broader prepared content is still ineligible for live transfer;
the exact TXT → BMP → TXT shape remains host-profile eligible with live
execution disabled.

This task does not change `CAPABILITY_MATRIX.md`, ebook conversion, the
240×320 rendering canvas, or the 237×320 transferable BMP validator. It has
performed no physical validation and requires final-head macOS/Windows CI and
fresh independent R3 review before PM acceptance. Physical counters for this
task are all zero: USB/device operations 0, sender calls 0, real `0x101b` 0,
claims consumed 0, sender-marker mutations 0, and installation-wide-lock
mutations 0. See the [P18-026 analysis record](analysis/phase-18-p18-026-unified-prepared-content-20260914.md).

## Current direction after completed P18-025 physical validation

P18-024 is the inherited complete host-only correction at canonical base
`dcef4e6594b9ba3b95a885efe9dab3deb4d3a760`. It corrected the Library catalog
projection seam that treated an offline package envelope basename as an
owner-visible sibling name. The P18 fixture envelope `00-package` remains
physical archive detail; the manifest's validated logical target folder is
the deterministic Library node name. Genuine owner-visible duplicates still
fail closed.

P18-025 is **COMPLETE — PHYSICALLY VERIFIED** on canonical `main` at
`3e8fde113acdbf0c8b00f49dcf7cfe0629111806`. The normal reviewed VNW-V15
Select → Arrange → Prepare → Preview → Review transfer → catalog/package
projection → fresh preflight → operation identity/bundle/seals → exact
confirmation → guarded sender lifecycle completed once for
`IC_P18_LIBRARY_20260913_03` with the direct-child order TXT → BMP → TXT.
P18-023 remains historical `BLOCKED` before sender entry; none of its
authorization, confirmation, target, claim, seal, candidate, transaction, or
operation identity was reused.

The physical proof is narrowly scoped to this exact reviewed VNW-V15 package
and lifecycle. It does not enable arbitrary file counts or shapes, overwrite,
deletion, nesting, multiple packages, VNW-V10, restore/sync, or generalized
ebook transfer. A future operation still requires fresh evidence, separate
owner authorization, and the full guarded lifecycle.

Verified P18-025 facts are: exact Sony VNW-V15 `0x054c:0x001e`,
`bcdDevice 0x0100`; fresh native `0x0019` capacity `3,145,728` bytes; target
absent before write; one logical sender and one real `0x101b`; retries `0`;
native completion `0x0000`; one durable consumed claim; sender marker
`none → in-flight → resolved` with the final marker store empty; and the
installation-wide indeterminate lock remained cleared. A complete post-write
backup and independent `readback_verified` result confirmed the exact target,
TXT → BMP → TXT order/content, preserved shared and unrelated state, the
reviewed display-history/bookmark policy, no removed paths, and 343 shared
paths. The durable terminal result records independently verified success.

The preserved external evidence is at:

- `/Users/stardust/Projects/InfoCarry-Evidence/phase-18-p18-025-v15-ui-physical-validation-20260914-02/terminal-summary.json`
- `/Users/stardust/Projects/InfoCarry-Evidence/phase-18-p18-025-v15-ui-physical-validation-20260914-02/attempts/p17-017-attempt-e3a8a272d06d461fa0ca0c1c2ad39964/result-manifest-0001.json`

The attempt directory retains the older `p17-017` label from the canonical
evidence allocator; it is preserved and is not renamed or rewritten.

### P18-023 — BLOCKED before sender entry

P18-023 is concluded as **BLOCKED before sender entry**, not success and not
an ambiguous post-send escalation. The normal facade/catalog path stopped on
`duplicate sibling name in Library: 00-package`. Preserved facts are:

- sender calls = 0; real `0x101b` = 0; retries = 0;
- claim created/consumed = 0; sender marker remained `none`;
- installation-wide lock remained `cleared`; device mutation = 0;
- fresh live V15/session evidence was not reached;
- capacity, live target-absence, backup, candidate, transaction, verifier,
  and post-backup were not reached;
- P18-023 authorization and confirmation are concluded and must not be reused.

P18-024 does not perform physical validation and does not activate a new
physical authorization. Its supported boundary remains VNW-V15 only, one
absent destination root, exactly three direct children in TXT → BMP → TXT,
with no overwrite, deletion, nesting, merge, second package, VNW-V10,
broader shape, grouping, retry, restore, synchronization, or recovery
expansion. A possible future physical task may reserve a new target such as
`IC_P18_LIBRARY_20260913_03`; that value is not special in production code.

Local focused validation is green. Final-head macOS CI, Windows CI, and a
fresh independent strong R3 review remain required before P18-024 can be
reported **COMPLETE**; the required R3 disposition is
`P0=0, P1=0, P2=0 — PASS`.

## Historical P18-023 preparation record

P18-023 was the host-only preparation branch from canonical `main` at
`011dd531f7257b919e262ed4349abc153642e668`. It prepares the fresh dynamic
target `IC_P18_LIBRARY_20260913_02` through the normal Library
Select → Arrange → Prepare → Preview → Review transfer → fresh preflight →
sealed coordinator lifecycle. The deterministic preparation boundary performs
no USB access, sender call, real claim consumption, sender-marker mutation,
installation-wide lock mutation, or real `0x101b` transmission. The later
physical stage would require the new owner phrase
`APPROVE P18-023 V15 UI PHYSICAL VALIDATION 01`; its derived runtime
confirmation is `ADD IC_P18_LIBRARY_20260913_02 ONCE`. Neither string in this
status file or any source/test artifact authorizes execution.

P18-023 must not reuse `IC_P18_LIBRARY_20260913_01` from concluded P18-021 or
the historical `IC_P18_LIBRARY_20260910_01`. The exact capability boundary is
unchanged: VNW-V15 `0x054c:0x001e`, one absent root, exactly TXT → BMP → TXT,
one transaction, no overwrite/delete/nesting/merge/VNW-V10/retry/restore/sync.
The host exit is `READY_FOR_HARDWARE_TEST` only after focused and full local
validation, final-head macOS and Windows CI, and an independent strong R3
exact-head review with `P0=0, P1=0, P2=0 — PASS`. No physical transaction is
part of P18-023 preparation.

## Current direction after P18-020

The Astra architecture/product review has been dispositioned as advisory
project guidance. P18-020 is complete on canonical `main` at
`a158eaf30b234b37b86442c9b3a21860c9532e62` after PR #46 and resolves the
known application-wide existing-text write-safety bypass. All reachable
product write routes now use the shared persistent claim, sender-marker, and
installation-wide indeterminate-lock boundary.

P18-021 is now preserved as a historical host-only
`ESCALATION_REQUIRED` stop: its normal UI/adapter still used a milestone-bound
operation identity and it never reached hardware readiness. P18-022 is the
completed correction on canonical `main` at
`011dd531f7257b919e262ed4349abc153642e668`; it generalizes the typed
operation binding without adding a transfer pipeline or expanding the
capability envelope. None of these decisions expands `CAPABILITY_MATRIX.md`;
VNW-V10, broader shapes, restore, synchronization, and recovery remain
unavailable.

P18-023's documentation and deterministic host preparation remain historical
reference only. P18-024 is complete in the canonical base used by P18-025;
P18-025 is now complete as the narrowly scoped physical proof recorded above.
`CAPABILITY_MATRIX.md` records that exact VNW-V15 evidence and does not broaden
the supported profile.

## P18-021 historical blocker and P18-022 fresh operation identity

P18-021 remains a concluded safe pre-write stop. Its documentation-only
history is carried forward on the P18-022 branch, and its historical approval
and confirmation material is inert. No USB, sender, claim, marker, or
installation-wide lock operation occurred for that task.

P18-022 removes the normal facade/adapter dependency on the former dated
target and operation identity. A caller must supply an ordinary valid target
component; the typed binding derives the transaction confirmation and a
deterministic binding identifier from the current reviewed VNW-V15 policy.
The sealed review identity then combines that binding with the selected
prepared package and child order, fresh verified baseline/state identity,
fresh typed native `0x0019` capacity provenance, candidate and transaction
hashes, authorization, preflight/core seals, and the reviewed auxiliary-state
policy. Changing any reviewed selection or evidence invalidates actionability
and requires a new preflight/review.

The exact supported boundary is unchanged: one prepared root with three direct
children in TXT → BMP → TXT order, one absent destination root, no overwrite,
delete, nesting, merge, second package, VNW-V10, retry, restore, or sync
expansion. Host deterministic-fake coverage proves an arbitrary valid fresh
target can reach `READY_FOR_HARDWARE_TEST` through the normal facade while
preflight consumes no claim, creates no marker, mutates no lock, calls no
sender, and transmits no `0x101b`. Physical validation is not authorized.

The P18-022 final source state passed the focused identity/readiness/UI and
claim-marker-lock suites, the full Python 3.12 portable suite (797 tests, 3
intentional skips), compilation, whitespace checks, final-head macOS and
Windows CI, and an independent strong R3 exact-head review with
`P0=0, P1=0, P2=0 — PASS`. P18-022 is therefore `COMPLETE` on canonical
`main`; this does not authorize physical validation.

## P18-015 VNW-V15 physical validation

P18-015 is **PHYSICALLY COMPLETE — TERMINAL READ-BACK VERIFIED** on
`task/P18-015-v15-physical-validation`. It initially stopped at the physical-
evidence gate because sandboxed PyUSB returned no devices; read-only diagnosis
proved classification A and the owner separately authorized resumption.
The initial filtered PyUSB enumeration inside the managed command sandbox
returned zero matching devices; it did not establish that no physical device
was attached. Therefore no fresh native `0x0019`, complete pre-write backup,
candidate, transaction, or seals were produced for a physical attempt.

The subsequent strictly read-only diagnosis is complete with classification
**A**. macOS IORegistry reported the exact Sony `0x054c:0x001e`,
`bcdDevice=0x0100` node at bus 1/address 1. Unfiltered PyUSB inside the command
sandbox saw zero devices total, while the same Python 3.12.14 / PyUSB 1.3.1 /
arm64 Homebrew libusb 1.0.30 environment outside that sandbox saw seven total
devices and the exact bus-1/address-1 Sony node. The existing filtered detector
then returned exactly one matching device. Five bounded enumeration-only
repetitions were stable. This was an execution-context visibility difference,
not evidence of physical absence and not a detector-semantics defect.

Fresh live preflight identified `0x054c:0x001e` at bus 1/address 1, obtained
native capacity 3,145,728 bytes, captured and verified a complete backup, and
rebuilt the exact reviewed candidate and transaction. The exact runtime phrase
was accepted. Claim `e921b09cb11d475c96730566a0e65108` was consumed and one
sender call transmitted one `0x101b`; native completion was `0x0000`, with no
retry. The complete post-write backup equals the sealed candidate. Corrected
terminal verification independently passed the exact target, TXT -> BMP -> TXT
order and payloads, 339 shared paths/payloads/timestamps, unrelated state,
seven display-history paths, bookmark path and opaque state/tail, and zero-count
`0x001c`-`0x001e`.

The final lock is `cleared`, no sender marker is active, claim-store integrity
is `ok`, and both the historical P18-011 claim and new P18-015 claim remain
permanently consumed. A temporary reporting helper failed after durable
terminal success because it expected only the historical claim; this caused no
additional USB operation and does not make the completed result ambiguous.
Raw evidence remains outside Git. No broader live capability is claimed. See
the sanitized [P18-015 analysis record](analysis/phase-18-p18-015-v15-physical-validation-20260909.md).

## P18-016 guarded product exposure

P18-016 adds the normal ttk Library `Review transfer…` stage for the reusable
host-only VNW-V15 Experimental profile. Exactly one explicitly selected
prepared root package with exactly three direct children in TXT → BMP → TXT
order is reviewed for canonical preparation constraints, destination, sizes,
verified-baseline conflicts, and available lower-bound capacity information.
Missing fresh live evidence is shown explicitly; conflicts and unsupported
shapes are blocked. The visible `Transfer once` affordance is permanently
disabled in this build and has no normal-UI callback. The reusable readiness
model does not import or expose the historical operation-specific sender,
claim, lock, candidate, transaction, or approval identity.

## P18-017 guarded UI-driven transfer integration

P18-017 connects the normal ttk Library progression
`Select → Arrange → Prepare → Preview → Review transfer` to a
product-facing execution facade. The facade can obtain fresh read-only
preflight evidence and present the exact proposed operation, then delegates a
future confirmed attempt to the existing canonical guarded coordinator,
Library live adapter, sender, post-write backup, and independent verifier. It
does not create a second sender, candidate, transaction, claim, or lock path.

The code-reachable live boundary remains exact VNW-V15 only: one explicitly
selected prepared root package at fresh target
`IC_P18_LIBRARY_20260910_01`, exactly `01-introduction.txt`,
`02-page-01.bmp`, `03-ending.txt` in TXT → BMP → TXT order, target absent,
no overwrite/delete/merge/nesting/batch/grouping, one transaction, and no
automatic retry. The typed fresh operation ID is hash-bound in the immutable
operation bundle. The consumed P18-015 target and approval/confirmation cannot
be replayed as product authorization.

P18-017 performed no physical transaction and has not physically validated the
ttk-driven path. VNW-V10 remains **UNCHARACTERIZED / READ-ONLY DISCOVERY
REQUIRED**; broader package shapes remain unavailable. The intended exit state
is **READY_FOR_HARDWARE_TEST**, pending final-head macOS/Windows CI and fresh
independent R3 review. A separate PM/owner decision is required before any
bounded physical UI-driven VNW-V15 validation.

## P18-018 VNW-V15 UI-driven physical validation

P18-018 was attempted in the proven host-visible USB environment, but stopped
safely before the device-changing boundary. The canonical filtered detector
returned exactly one Sony VNW-V15 at `0x054c:0x001e` (observed bus 1/address 1).
The host was Python 3.12.14 on arm64 with PyUSB 1.3.1, the libusb1 backend,
and `/opt/homebrew/lib/libusb-1.0.dylib`.

Two normal ttk review/preflight cycles obtained fresh read-only evidence. The
latest cycle captured a complete eight-object backup, fresh native `0x0019`
capacity of 3,145,728 bytes, target absence, and the exact candidate for
`IC_P18_LIBRARY_20260910_01` with TXT → BMP → TXT children. The UI then refused
to expose the exact runtime confirmation because the offline plan had
`queue_ready=false`: the ttk plan builder does not supply a capacity value, so
the plan remains capacity-uncleared even after the fresh preflight has supplied
and sealed capacity. The facade correctly stopped with no claim, marker, or
write. This is an unresolved product integration blocker, not evidence of
device absence.

No runtime confirmation was presented or accepted. No P18-018 claim exists or
was consumed; the historical P18-011 and P18-015 claims remain permanently
consumed. No sender call, `0x101b`, post-write backup, result manifest, or
device-changing operation occurred. The final disposition is
**ESCALATION_REQUIRED** because the reviewed ttk path cannot yet reach its
confirmation gate with the fresh evidence available. VNW-V10 remains
**UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED**, broader package shapes
remain unavailable, and no new physical capability is claimed. A separately
scoped product correction and fresh validation decision are required; this
task did not authorize a bypass or a physical retry.

## P18-019 fresh capacity propagation closure

P18-019 closes the P18-018 host-side gating defect. The existing typed native
`0x0019` capacity response from a fresh read-only preflight is now propagated
into a rebuilt canonical Library queue plan, together with the fresh verified
backup. Queue readiness and Experimental readiness are recomputed from that
plan; the UI adopts its plan/readiness identity, and records the native source
and response hash so fresh capacity remains distinct from offline assumptions.

The exact supported VNW-V15 package boundary is unchanged. Missing,
insufficient, malformed, stale, or mismatched capacity evidence remains
blocked before any claim, marker, sender, or device-changing path. P18-019
performed no physical operation and did not reuse P18-015/P18-018 identity or
approval. VNW-V10 remains **UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED**;
broader package shapes remain unavailable. A later physical validation still
requires a separate operation-specific PM/owner decision.

## P18-020 application-wide write safety closure

P18-020 is **COMPLETE** on canonical `main` at
`a158eaf30b234b37b86442c9b3a21860c9532e62` after PR #46. It closes the
reachable existing-text replacement write-path gap on the host. The
replacement route now uses the same persistent application-wide claim-store,
sender-start marker, and indeterminate-write lock boundary as the Library
coordinator through one neutral `PersistentWriteSafetyOwner`. Its
operation-specific candidate builder, authorization gate, one-call sender, and
terminal semantic read-back verifier remain unchanged in scope. The route
consumes one durable claim, commits one marker before sender entry, never
automatically retries, and preserves the global lock and marker when a started
operation or terminal read-back cannot be proven. Replayed or stale operations,
active lock/marker state, and corrupt claim state fail closed before sender
entry. Offline replacement preview remains available; the write affordance
also remains disabled if the shared safety owner cannot be configured.

The reviewed closure had successful final-head macOS and Windows CI in run
`34676222163` (jobs `103506450905` and `103506450975`) and independent R3
review `P0=0, P1=0, P2=0 — PASS`. This documentation task remains host-only:
no device-changing operation, real sender call, native `0x101b`, real claim
consumption, marker mutation, or lock mutation is performed.

## Astra architecture/product review disposition

The durable disposition is recorded in
[`analysis/phase-18-astra-architecture-product-review-disposition-20260912.md`](analysis/phase-18-astra-architecture-product-review-disposition-20260912.md).
Adopted direction is limited to product architecture and governance: one
prepared-content concept, Library-integrated conversion, simpler normal UX,
typed readiness/outcome reasons, one background operation controller, and
gradual removal of milestone-specific production identities. The permanent
safety invariants remain unchanged: no automatic retry after ambiguity,
model-specific capability boundaries, persistent indeterminate-write
protection, and independent verification. SQLite/JSON storage consolidation
is deferred, and plugins, a broad GUI rewrite, and automatic synchronization
are rejected for now.

## Historical canonical checkpoint before P18-015

Canonical `main` is `5d23e8b219507535b2db4b57028602073aa23c61` after merged
P18-014. P18-004 through P18-014 are complete on the canonical history, and the
required P18-005/P18-006/P18-008 R3 reviews have passed. P18-009 has explicit
owner approval for one bounded VNW-V15 TXT → BMP → TXT physical validation;
that attempt is recorded below as `ESCALATION_REQUIRED` because the exact
destination already exists and fresh auxiliary-state evidence includes
unresolved bookmark/display-history state. No device-changing operation was
performed in P18-009.

## P18-011 owner-approved VNW-V15 physical validation

P18-011 resumed on the existing branch
`task/P18-011-v15-physical-validation` and PR #37. Host-level USB detection
confirmed the connected Sony InfoCarry VNW-V15 (`0x054c:0x001e`), and the
complete authoritative fresh preflight passed from a new session. It rebuilt
capacity, descriptors, the eight-object baseline backup, destination absence,
auxiliary-state eligibility, candidate, seal, transaction, and execution-time
capacity evidence without reusing stale evidence.

The exact owner confirmation `ADD IC_P18_LIBRARY_20260906_01 ONCE` was accepted
once. One durable claim was consumed and the sender entered one authorized
`0x101b` transaction; no retry or second transaction occurred. The native
sender result passed the exact integer `0x0000` gate, and a complete post-write
backup was captured whose dynamic blob matches the sealed candidate. Durable
terminal verification is unresolved because the bookmark-policy verifier did
not derive/pass the sealed P18-010 bookmark-preservation allowance and no
durable result manifest exists. The physical result is therefore
**ESCALATION_REQUIRED**, not complete and not a capability proof.

The sender marker is durably `lock_recorded` and the installation-wide
indeterminate-write lock is active. No further USB write, automatic retry,
overwrite, deletion, corrective write, or capability expansion is authorized.
Recovery requires a later read-only diagnostic and an explicit documented
recovery decision. No production code changed. See the sanitized
[P18-011 analysis record](analysis/phase-18-p18-011-v15-physical-validation-20260906.md).

This is distinct from the earlier P18-009 event: P18-009 stopped before
sender entry because its old target already existed and its auxiliary state
required closure; no write occurred there. P18-011 is the later
owner-approved operation against the fresh target and already-closed P18-010
auxiliary-state policy, and it reached one physical transaction.

The independent R3 review found `P0: none`, `P1: none`, and
`P2: corrections required`. The production-code P2 is deferred to the
separate host/read-only P18-012 closure task; it is not changed in PR #37.

## P18-012 read-only incident diagnosis and verifier closure

P18-012 is **COMPLETE** for the host/read-only closure boundary on
`task/P18-012-readback-recovery-closure`, based on canonical
`a0ac0765d3a358898f665c8e3dca3a0027db83d7`. It narrowly corrected
`prepared_package_multi_verify.py` so bookmark verification is enabled only by
the exact validated sealed P18-010 bookmark-preservation policy and matching
fixed-state snapshot. The public verifier has no caller-controlled bookmark
permission switch. Wrong-policy, malformed, pointer/path, opaque-byte,
unused-tail, unsupported-state, and policy/snapshot tampering remain fail-closed.

The corrected verifier independently passed the preserved P18-011 immediate
post-write backup and the fresh incident-bound VNW-V15 diagnostic. Both match
the sealed candidate blob
`6fd27699ca6c13a46f8d75467ba72860af8b865b7cf19046b7a91f63bf471e01`; the fresh
diagnostic is complete, exact-profile `0x054c:0x001e`, and bound to the
original incident, attempt, consumed claim, sender marker, and active global
lock. It verifies the exact target and ordered TXT → BMP → TXT children, all
335 baseline paths, shared-state preservation, seven display-history
references, one bookmark group, exact opaque bookmark values and unused tail,
and zero-count `0x001c`–`0x001e`.

The documented recovery recommendation is **no corrective device write** and
a later explicit decision may clear the installation-wide lock. P18-012 did
not clear the lock or resolve the marker. P18-011 remains
`ESCALATION_REQUIRED`; no durable terminal-success manifest or physical write
capability claim was manufactured. Independent strong R3 review completed its
correction loop with final disposition `P0: none`, `P1: none`, `P2: none`.
See the sanitized
[P18-012 analysis record](analysis/phase-18-p18-012-readback-recovery-closure-20260907.md).

## P18-013 incident-bound recovery-state closure

P18-013 is **COMPLETE** for the exact P18-011 host recovery state on
`task/P18-013-recovery-state-closure`, based on canonical
`6bc0c046312400ed28fc4bef543522d250eb469c`. The original P18-012 diagnostic
was copied byte-for-byte from temporary storage into durable external evidence
at
`/Users/stardust/Projects/InfoCarry-Evidence/phase-18-p18-012-readonly-diagnostic-20260907-01`.
The complete diagnostic was independently revalidated against the preserved
immediate post-write backup, sealed candidate, exact target contents,
baseline-path preservation, display history, bookmarks, opaque bookmark
state, and zero-count unsupported auxiliary commands. The conclusion remained
**NO CORRECTIVE DEVICE WRITE REQUIRED**.

The Project Owner's exact recovery decision was preserved in a deterministic
record with SHA-256
`03414e625af346d48ba98e04a2ee2353adb561880e616fb4b8539603498ce3f9`.
Using only the existing typed recovery APIs, P18-013 cleared the
installation-wide lock bound to incident
`guarded-library-6aa14fe3d1c64f9497ff89a795bcf88c` and attempt
`6aa14fe3d1c64f9497ff89a795bcf88c`, then resolved only its matching
`lock_recorded` sender marker. The final lock is `cleared`, the active marker
is absent, and claim `827bfde0b93d4b2da57ee646ff6aaa1d` remains the sole
permanently `consumed` tombstone. Claim-store integrity is `ok`.

P18-011 remains historically **ESCALATION_REQUIRED**. P18-013 does not create
retroactive terminal success, authorize a retry, or establish new transfer
capability. It performed zero USB/device writes and made no device-content or
capability-matrix change. Future writes require a separate owner-approved
operation. Independent strong R3 review completed its correction loop with
final `P0=0, P1=0, P2=0 — PASS`. See the sanitized
[P18-013 analysis record](analysis/phase-18-p18-013-recovery-state-closure-20260907.md).

## P18-014 fresh post-recovery operation identity closure

P18-014 host validation is complete, with final release gates pending, for the
host-only operation identity boundary on `task/P18-014-fresh-operation-identity`, based on
canonical `5dc54cb04fcef9025b8e3f347e69b335af887135`. It uses the durable
P18-012 read-only diagnostic and proves that the new fixed destination
`IC_P18_LIBRARY_20260907_01` is absent from the preserved baseline. The exact
TXT → BMP → TXT package is bound to the new P18-015 owner-approval and
confirmation phrases, while the stale P18-010 phrases and destination remain
rejected.

The rebuilt candidate is 2,123,364 bytes with SHA-256
`2d21044987668c55d06aaa202fa678d760f9dbca99a96679eb4dff26e5e818ac`; its
transaction SHA-256 is
`82be7e81b213fbb07eba86894ee525970b8a48a1101da5b4324857b1003d2fc8`. The
operation preserves all seven `0x001b` display-history paths by the exact
`0x140` metadata delta, rebases only the independently established
`0x001f` bookmark pointer, preserves all four opaque bookmark values and the
unused tail exactly, and keeps `0x001c`–`0x001e` at zero active entries.
Unrelated baseline paths, payloads, timestamps, and unknown bytes remain
unchanged. Capacity projection leaves 1,038,400 bytes of growth margin.

P18-014 performed zero USB/device writes, sent no `0x101b`, consumed no claim,
created no sender marker, and did not expand the capability matrix. The
P18-013 lock remains `cleared`, its sender marker remains absent, and the
P18-011 claim remains permanently `consumed`. This is host readiness only;
P18-015 was the separate owner-approved physical validation task and is now
recorded above as terminally read-back verified. The initial P18-014 CI run
passed on the first implementation commit, but
the reviewed documentation commit's macOS and Windows jobs were rejected
before any steps by GitHub's account billing/spending-limit condition; the
rerun failed identically. Final readiness therefore remains escalated pending
successful CI on the reviewed commit. See the
[P18-014 analysis record](analysis/phase-18-p18-014-fresh-operation-identity-20260907.md).

## Current product checkpoint

P18-003 adds the host workflow Select files/folder → Arrange → Prepare →
Preview through the P18-002 façade. Normal multi-file and recursive-folder
choosers are available; the approved Tk runtime has no external file-drop API,
so drag-and-drop remains unavailable without an optional TkDND dependency.

The separate `host-offline-hierarchical-library-txt-bmp-v1` profile is
`host_offline_draft_not_live_enabled`: exactly one prepared root, 1–8 TXT/BMP
leaves, at most two directory levels below the conceptual device root, no
empty directories, at most 9 directories and 17 logical nodes, 39 CP932 bytes
per component, and 259 CP932 bytes per relative path. It retains the existing
1 MiB per-leaf, 4 MiB source-total, and 1 MiB prepared-total limits.

The exact V15 `experimental-flat-root-folder-txt-bmp-v1` profile remains
unchanged and `defined_not_live_enabled`.

The flat profile is explicitly associated with reviewed model profile
`sony-vnw-v15-reviewed-v1`; it is not generic InfoCarry capability. VNW-V15
is the only verified model, with observed session identity `0x054c:0x001e`.
VNW-V10 is an explicit target with status
`UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED`: no V10 protocol, capacity,
format, candidate, authorization, or write behavior is enabled or implied.
V15 sessions must freshly obtain `0x0019` capacity evidence (64-byte response,
big-endian `+0x08`) and bind total, baseline, candidate growth, remaining-growth
capacity (total minus baseline), and remaining-after-transfer margin (total minus
candidate); V10 capacity semantics remain unknown.

The host façade records `PreparedItem[] → TransferPlan → CandidateLibrary →
Authorization → ExecuteOnce → ReadBackVerification` without USB access,
candidate bytes, sender construction, or a GUI/CLI write action. The
persistent indeterminate-write lock is installation-wide, not per-device:
an ambiguous outcome blocks every model/session across restart and reconnect.
It deliberately over-blocks because no stable physical-unit identifier is
proven. It never auto-clears from VID/PID; clearing binds the original
incident/attempt, complete read-only diagnostic evidence, and a documented
recovery decision.

## P18-005/P18-006 guarded-boundary checkpoint

P18-005 is merged on canonical `main`. Its guarded coordinator reaches only
the exact reviewed logical shape: one new absent root folder with ordered
TXT → BMP → TXT children. It requires the exact reviewed VNW-V15 profile, the
Experimental capability identifier, one sealed operation bundle, current
hash-only confirmation, fresh backup/capacity revalidation, one sender claim,
complete post-backup, and independent semantic read-back. The broader flat
profile remains non-live; the hierarchical profile remains preview-only; VNW-
V10 remains uncharacterized and non-write-capable.

P18-006 adds the offline/fake A–O adversarial matrix and positive control. It
covers shape/profile/content/binding/backup/capacity/drift/confirmation/lock/
transport/one-shot/post-backup/read-back/auxiliary-state/GUI-CLI boundaries,
including concurrent sender attempts. The matrix passes with no hardware or
USB access. It found and corrected two R3 safety issues: exact reviewed
profile-value substitution was not rejected, and malformed or boolean
post-start completion values were not classified as indeterminate. The latter
now activates the existing installation-wide persistent lock; nonzero integer
completion remains determinate failure. No automatic retry is allowed.
Independent R3 review passed with no correction round required. P18-008 closes
the prior process-local one-shot claim carry-forward on canonical `main`:
SQLite is now the cross-process/restart authority, with real subprocess
crash/race coverage and a durable sender-start marker. This is a host-side
safety closure; it does not enable a physical write or claim physical
transaction atomicity.

## P18-007 Legacy Oracle checkpoint

P18-007 is `COMPLETE` for the offline Legacy Oracle boundary and representative
differential corpus. Corpus A covers one TXT, B covers four ordered TXT
children, and C covers the exact TXT → BMP → TXT product shape. A retains an
unexplained four-byte allocation/offset discrepancy; B normalizes only the
independently established timestamp/checksum differences; C is
`NOT_COMPARABLE` as a whole blob because the preserved native and modern
baseline/target identities differ, while its typed package projection matches.
Hierarchical Corpus D was not available and remains exploratory external
evidence only.

The final preserved host-side boundary is the `0x101b` command header and
payload immediately before driver/USB submission. No transmission, hardware,
or live Oracle operation occurred. The reusable comparator preserves raw
differences alongside any normalized view, and no production transfer code or
capability row was broadened. Independent R2 review/re-review passed with no
remaining material findings. The focused PR is [PR #33](https://github.com/sourvegie/sony-infocarry-modern-manager/pull/33), with both [macOS](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/33962042514/job/101295488675)
and [Windows](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/33962042514/job/101295488741)
Python 3.12 CI passing. A same-baseline P16 whole-blob observation or
hierarchical fixture is not required for the completed A–C host-side result.
The former P18-006 process-local one-shot claim carry-forward is resolved by
P18-008 on canonical `main`; the P18-007 Oracle boundary and its limitations
are unchanged.

## P18-008 durable one-shot claim checkpoint

P18-008 adds an installation-owned, injected SQLite claim store. A direct
committed insert keyed by the exact preflight seal is authoritative, survives
restart, and has no reset, TTL, process-local fallback, candidate/transaction
byte storage, or claim-before-callback exception. The live adapter and guarded
coordinator require the same durable store; `preflight_only=True` remains
claim-free.

The store also commits one hash-bound sender-in-flight marker immediately
before sender entry. After a crash or abrupt exit, the next guarded attempt
promotes the marker into the existing installation-wide indeterminate-write
lock. Normal terminal cleanup requires a store-issued live-process handle;
diagnostic cleanup requires a typed cleared lock record matching both the
original incident and attempt. Binding corruption fails closed.

The host evidence uses actual independent subprocesses for restart persistence,
`os._exit` crash persistence, and a same-seal two-process race with exactly one
winner. The focused claim/adapter/coordinator tests pass 90 tests; the full
portable suite passes 746 tests with 3 intentional evidence-dependent skips.
The merged P18-008 change has passing macOS and Windows Python 3.12 offline
checks in [workflow run 33976813020](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/33976813020).
Independent R3 re-review of `c5877a5` is PASS with no remaining
P0/P1/P2 findings. No USB, hardware, `0x101b`, or live transfer was used.

## P18-009 owner-approved VNW-V15 physical validation

P18-009 received explicit owner approval for exactly one physical validation of
the reviewed `sony-vnw-v15-reviewed-v1` operation: one new absent root with
ordered TXT → BMP → TXT children, against the expected session identity
`0x054c:0x001e`. The fresh branch is
`task/P18-009-v15-hardware-validation`, based directly on canonical
`c5877a53988f603f765f5c89acbacf624bcd5d67`; no production code changed.

The resumed result is `ESCALATION_REQUIRED`. Fresh read-only enumeration and
descriptor validation matched Sony InfoCarry VNW-V15, reviewed profile
`sony-vnw-v15-reviewed-v1`, and session identity `0x054c:0x001e`. Fresh native
`0x0019` evidence was 64 bytes with big-endian `+0x08` capacity
`3,145,728` bytes. A complete integrity-verified fresh backup was captured.

The exact required destination `root/IC_P17_LIBRARY_20260831_03` was already
present in that backup with existing children `01-introduction`, `02-page-01`,
and `03-ending`. The reviewed candidate builder stopped before candidate or
transaction construction. Independent read-only fixed-state assessment found
7 display-history references in `0x001b` and 4 nonzero bookmark values in
`0x001f`; no auxiliary state was changed. No alternate destination, overwrite,
delete, merge, or retry is authorized.

Sender calls: 0; runtime confirmation: not accepted; durable claim: not
consumed; sender marker: none; `0x101b`: not transmitted; post-backup,
semantic read-back, and human acceptance: not applicable. The real
installation-stable claim store remains schema-valid with zero claims and no
sender marker; the installation-wide indeterminate-write lock remains
inactive. No capability row gains physical evidence. Broader flat shapes remain
non-live, hierarchy remains preview-only, VNW-V10 remains non-write-capable,
and standing Experimental physical-write exposure remains disabled. See the
sanitized [P18-009 analysis record](analysis/phase-18-p18-009-v15-hardware-validation-20260906.md).

## P18-010 fresh target and auxiliary-state preservation

P18-010 is an R3 host-only closure on
`task/P18-010-aux-state-preservation`, based directly on canonical
`a67d448a803838c6f16b4c21961496ce3e8d9fc9`. It fixes the next validation
destination to `IC_P18_LIBRARY_20260906_01`, which is absent from the preserved
P18-009 baseline, and reuses the existing exact TXT → BMP → TXT pipeline.

The real P18-009 state has seven `0x001b` display-history references, zero
counts in `0x001c`–`0x001e`, and one active `0x001f` bookmark group with four
nonzero values. The host candidate rebases only the seven established history
pointers and the independently resolved bookmark record pointer by the exact
`0x140` metadata delta. The bookmark group's other four dwords, its unused
tail, all zero-count mark blocks, every referenced existing payload, and all
unrelated baseline state remain exact.

The resulting 2,107,328-byte candidate has SHA-256
`6fd27699ca6c13a46f8d75467ba72860af8b865b7cf19046b7a91f63bf471e01`;
the 2,172,864-byte transaction has SHA-256
`9373330cd78f58faaa0cfe61590e4cd0ce489ea5c8069c3112144e69aafe10f4`.
Against native capacity 3,145,728 bytes, projected post-candidate margin is
1,038,400 bytes. The fixed-state policy and before/candidate hashes, semantic
bookmark binding, destination, candidate, and transaction are carried through
authorization, sealed preflight, immutable operation bundle, and product
review.

Focused tests pass 109 tests; the full portable suite passes 751 tests with 3
intentional evidence-dependent skips. Independent strong R3 review passed after
two bounded correction rounds with no remaining P0–P2 findings. Python 3.12 CI
passes on macOS and Windows in
[PR #36](https://github.com/sourvegie/sony-infocarry-modern-manager/pull/36).
The host-side result is `READY_FOR_HARDWARE_TEST`. No USB,
hardware, `0x101b`, claim consumption, or device-changing operation was used.
See the sanitized [P18-010 analysis record](analysis/phase-18-p18-010-fresh-target-aux-state-preservation-20260906.md).

## Verified recent result

P18-004's foundation-quality closure is implemented on the fresh
`task/P18-004-foundation-quality` branch from canonical `main`: the portable
Python 3.12 workflow targets both macOS and Windows, the README records the
offline-suite boundary, and the project declares the owner-authorized MIT
License in [`LICENSE`](LICENSE) and package metadata. The focused suite passes
38 tests with the same 3 intentional evidence skips; the full suite passes
688 tests with 3 intentional skips both normally and under a sanitized
environment. No test writes preserved evidence or uses hardware, network, the
separate toolkit, or user application data. Post-change macOS and Windows
GitHub CI both pass in [PR #30 workflow run 33886273729](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/33886273729)
on `macos-latest` and `windows-latest` with Python 3.12. The generated
evidence-package trees are explicitly preserved as byte-exact non-text files
so their manifests and source hashes remain portable across checkout
platforms.

The MIT License applies only to this project's own source code. It does not
grant rights to Sony proprietary software, firmware, documentation,
trademarks, captures, backups, private evidence, or the separate
`InfoCarry-Toolkit` and reference archives. The guarded execution and
independent read-back boundary is now host-reviewed under P18-005/P18-006;
no live behavior is enabled for normal application surfaces and no physical
compatibility is claimed.

P18-001A’s bounded responsive Library correction is **COMPLETE** based on the
owner’s human-observed retest at approximately 980×680 and 1120×760 or
larger. This observation covers the tested GUI sizes only; it does not infer
hardware behavior, transfer execution, or other display environments.

The exact P17-018 and P18-015 TXT/BMP/TXT Library transfers are the integrated
Experimental physical proofs for that exact shape. P18-015 adds terminal
read-back verification under the established display-history and bookmark
preservation policy; it does not generalize other shapes or normal product
reachability. Physical opening remains a separate human acceptance check where
still noted by the evidence records. The capability authority is
[`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md).

## Safety posture

- P18-011 historically reached sender entry once and required indeterminate
  closure. P18-012 verified its preserved state and P18-013 cleared that exact
  incident through the reviewed recovery API. P18-015 later completed a
  separate one-shot operation with terminal read-back verification. The
  installation-wide lock is now `cleared`; neither event authorizes a retry.

- P18-009 reached fresh read-only VNW-V15 evidence but stopped before sender
  entry because the exact destination existed and auxiliary state was not
  within the established safe proof. No approval phrase was accepted, no
  sender was constructed, no `0x101b` was sent, and no live enablement occurred.
- Nested content is host preparation/preview only within its exact draft
  profile. Unsupported shapes, excessive limits, automatic grouping, batch
  operations, overwrite/merge/delete, restore, synchronization, and recovery
  remain unavailable with a precise reason.
- Without fresh verified evidence, total model limit, fresh baseline model
  length, candidate growth, and remaining after transfer are **Not evaluated**.
- The supplied V10 manual statement says a new Manager transfer clears
  Bookmarks, and the owner reports corresponding V15 documentation. Do not
  infer that Marks or display history are cleared; no clear or write action is
  enabled here.
- A later enabled Experimental operation must use fresh verified backup and
  capacity evidence, exact in-app confirmation, one logical transaction,
  explicit integer `0x0000`, complete post-write backup, independent semantic
  read-back, and no automatic retry. Backup is not undo.
- Any ambiguous live outcome requires persistent installation-wide read-only
  diagnosis before a documented recovery decision can clear the lock.

## Delivery and review

The two active streams are Product Delivery and Legacy Oracle. P18-004 through
P18-008 are complete on canonical `main`; P18-009 received its separate owner
approval, obtained fresh read-only VNW-V15 evidence, and escalated before any
device-changing operation because the exact destination existed and auxiliary
state was unresolved. Any future physical write would require a fresh R3 review
and owner decision for changed scope; this task remains limited to the exact
TXT → BMP → TXT boundary.

P18-008 implementation, local validation, remote macOS/Windows CI, and R3
review are complete on merged PR #34. P18-009 performed no device-changing
operation and does not change the standing Experimental exposure decision.

Portable baseline figures through P18-006 remain recorded below for history.
P18-006 focused validation is 17 passing; the guarded/P17 focused validation
is 155 passing; the full portable suite is 714 passing with 3 intentional
skips. Compilation and `git diff --check` pass.
Independent R2 re-review is PASS with no remaining material findings. PR #28
was merged after its GitHub Python 3.12 offline-suite check passed; no hardware
or live validation is claimed.

Task outcome: `COMPLETE` for the bounded host GUI/workflow gate. The owner
reported “Everything works as expected” and supplied the offline Prepare and
device-tree Preview artifacts for the expected ordered TXT/BMP/TXT package.
This is bounded human GUI/workflow evidence only; it does not claim hardware,
USB, candidate, authorization, or live-write behavior.

P18-006 outcome: `COMPLETE` for host-verifiable offline guarded-transfer and
tamper coverage. Its P2 cross-process claim carry-forward is resolved by
merged P18-008 on canonical `main`; this still does not authorize a device write. The exact
TXT/BMP/TXT shape remains the only guarded-execution shape; broader flat,
hierarchical, and V10 paths remain unavailable or preview-only.
The required GitHub Python 3.12 offline workflow passed on both
`macos-latest` and `windows-latest` in [PR #32 workflow run 33950704593](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/33950704593).

## Execution workflow

The canonical working model is one **Fresh Codex Task Executor** per meaningful
task. It implements directly inside an approved scope, validates, updates only
affected durable documentation, coordinates required independent review, and
escalates material decisions. Dispatch is a responsibility rather than a
permanent intermediary; there are no permanent Junior Engineer or Secretary
roles. Hardware, capability-expansion, fail-safe lock, indeterminate-write,
and no-automatic-retry boundaries are unchanged.

Use the model for the next 3–5 meaningful engineering tasks before considering
further workflow restructuring. Record only material findings from that
evaluation.

## Historical records

The pre-P18-002 long-form status, risk register, and roadmap are preserved in
[`analysis/archive-current-status-through-p18-001a-20260902.md`](analysis/archive-current-status-through-p18-001a-20260902.md),
[`analysis/archive-risk-register-through-p18-001a-20260902.md`](analysis/archive-risk-register-through-p18-001a-20260902.md),
and [`analysis/archive-roadmap-through-p18-001a-20260902.md`](analysis/archive-roadmap-through-p18-001a-20260902.md).
