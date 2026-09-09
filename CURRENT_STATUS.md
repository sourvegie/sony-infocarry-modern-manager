# Current Project Status

Date: 2026-09-09

## P18-015 VNW-V15 physical validation

P18-015 stopped **BLOCKED_BY_EXTERNAL_EVIDENCE** on
`task/P18-015-v15-physical-validation` at the initial physical-evidence gate.
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

The installation-wide lock remains `cleared`, no sender marker is active,
claim-store integrity is `ok`, and historical P18-011 claim
`827bfde0b93d4b2da57ee646ff6aaa1d` remains permanently `consumed`. No new
P18-015 claim was consumed. Runtime confirmation was neither presented nor
accepted; sender calls, `0x101b` transmissions, logical transactions, and
retries are all zero. No device-changing operation began. No post-write or
terminal physical result exists, and no capability boundary changed. See the
sanitized [P18-015 analysis record](analysis/phase-18-p18-015-v15-physical-validation-20260909.md).
The physical execution remains stopped pending PM review and separate
authorization to resume. The read-only diagnosis performed zero device writes,
sender calls, `0x101b` transmissions, and claim consumptions.

## Canonical checkpoint

Canonical `main` is `1c16d48856328de53171a13f8e5665da0a46e47a` after merged
P18-010. P18-004 through P18-010 are complete on the canonical history, and the
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
P18-015 is the separate owner-approved physical validation task. Final status
will be updated only after commit, CI, PR review, and final independent R3
sign-off. The initial CI run passed on the first implementation commit, but
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

The exact P17-018 TXT/BMP/TXT Library transfer remains the only integrated
Experimental physical proof. Physical opening of its folder and all three
children remains a separate human acceptance check where still noted by the
evidence records. The capability authority is
[`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md).

## Safety posture

- P18-011 reached sender entry once after complete fresh gates. Its post-write
  backup is preserved, but terminal closure is indeterminate; the
  installation-wide lock is intentionally active and must not be cleared by a
  reconnect or by assuming that the device matches the candidate.

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
