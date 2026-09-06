# Current Project Status

Date: 2026-09-06

## Canonical checkpoint

Canonical `main` is `c5877a53988f603f765f5c89acbacf624bcd5d67` after merged
P18-008 / PR #34. P18-004 through P18-008 are complete on `main`, and the
required P18-005/P18-006/P18-008 R3 reviews have passed. P18-009 has explicit
owner approval for one bounded VNW-V15 TXT → BMP → TXT physical validation;
the resumed attempt is recorded below as `ESCALATION_REQUIRED` because the
exact destination already exists and fresh auxiliary-state evidence includes
unresolved bookmark/display-history state. No device-changing operation was
performed.

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

The exact P17-018 TXT/BMP/TXT Library transfer remains the only integrated
Experimental physical proof. Physical opening of its folder and all three
children remains a separate human acceptance check where still noted by the
evidence records. The capability authority is
[`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md).

## Safety posture

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
