# Current Project Status

Date: 2026-09-01
Canonical checkpoint: P17-010 freshness-clock correction is host-validated and READY_FOR_HARDWARE_TEST for a future fresh attempt; the authorized attempt-01 stopped fail-closed before sender construction because its harness used a pre-capture fixed timestamp; no sender call, backend write, or 0x101b transaction occurred

## Portable offline validation

- 602 passing tests
- 3 intentional evidence-dependent skips

These are host/offline results only. They do not claim physical-device verification.

## Proven or delivered scopes

- Canonical sanitized repository established as the development source of truth.
- Read-first modern manager, backup, browsing, export, and preview workflows delivered for the supported VNW-V15 scope.
- Constrained existing-text replacement has passed its approved guarded live scope with read-back evidence.
- One narrowly scoped root-level TXT creation path has passed an approved live smoke with read-back evidence.
- One constrained one-folder/one-TXT package path has passed an approved live smoke with read-back evidence.
- Selective-delete modeling/hardening has completed its supported offline structural scope, and one constrained modern root-level TXT delete smoke has passed with independent read-back.
- Local Library foundation and offline Prepare workflow exist; normal generalized transfer remains disconnected from the product workflow.
- Ordered multi-child TXT and mixed TXT/BMP logical preparation, candidate construction, authorization binding, fake-only workflow, readiness preview, and independent offline read-back exist for their defined offline scopes.
- P17-001 adds a framework-independent, offline-only Library queue plan for
  explicit selected items and “all ready” review. Each prepared item remains
  its own root-level TXT package; duplicate or overlapping destinations fail
  closed rather than being auto-grouped. The plan revalidates source and
  prepared-manifest hashes, compares destinations against a supplied verified
  offline backup when present, reports lower-bound size/capacity, and never
  constructs a candidate, authorization, transaction, or sender action.
- P17-002 adds the versioned, deterministic
  `infocarry-prepared-typed-media-package-v1` import/revalidation boundary for
  one flat ordered TXT/BMP package. Supported TXT and/or BMP children are
  allowed; the historical mixed builder remains unchanged by default and an
  explicit content-builder mode handles single-kind packages. The manifest,
  source archive, prepared children, hashes, sizes, names, kinds, and package
  containment are checked before persistence. The catalog stores one non-owning grouped package item
  using an additive optional record, so existing Library source items retain
  their meaning and legacy catalog records remain loadable without an
  automatic rewrite. Re-import is idempotent; changed or invalid packages
  fail closed rather than being silently replaced, and Library removal leaves
  original files untouched.
- The P17-001 queue now keeps an explicitly imported package as one logical
  item and reports its ordered child kinds/names, destinations, hashes,
  payload sizes, conflicts, lower-bound growth, and blocked execution state.
  Several unrelated Library rows are still never merged. The ttk Library has
  a directory-based `Import prepared package…` action; preparation and queue
  review remain offline-only and no transfer control is enabled.
- P17-003 adds a narrowly isolated R3 bridge from exactly one fully
  revalidated P17-002 Library package into the existing ordered TXT/BMP/TXT
  candidate, authorization, hash-only preview, independent read-back, and
  fake-host workflow. It binds the catalog record and full package manifest
  identity in addition to the existing device, backup, template, capacity,
  fixed-state, candidate, transaction, timestamp, and additive post-state
  bindings. The exact profile is one root folder with
  `01-introduction.txt`, `02-page-01.bmp`, and `03-ending.txt` in that order;
  stale/tampered packages, profile/order/template-byte/destination conflicts,
  unsupported state, catalog source/manifest drift, immutable sealed-report
  tampering, and Library binding drift fail closed. The bridge requires the
  exact reviewed P16-001 native template blob hash
  `6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b`. The isolated
  bridge is not imported by normal GUI/CLI code, uses only injected fake
  hardware boundaries, and has no live sender or owner-approval path. P17-003
  is **READY_FOR_HARDWARE_TEST** for this host-only preparation; a later task
  must obtain a new fresh backup/capacity boundary and separate approval.
- P17-004 prepared one explicitly imported Library package and completed a
  fresh, in-order read-only preflight for the new absent destination
  `IC_P17_LIBRARY_20260831_03`. Sony `054c:001e` detection (durably preserved
  with bus 2/address 3), the fresh native `0x0019` capacity response, a
  complete eight-object backup, destination absence, package/catalog/source
  hashes, reviewed template, display-history state, candidate, transaction,
  and sealed preview were independently replayed. The 3,145,728-byte parsed
  capacity leaves 1,054,436 bytes after the 2,091,292-byte candidate model.
  The authoritative external preservation manifest covers 72 entries with
  zero mismatches; the refresh is ordered detection → capacity →
  complete backup. The corrected report distinguishes
  `read_only_hardware_accessed=true` from
  `hardware_write_performed=false` and `usb_transmission_performed=false`.
  A narrow opt-in template-subset check accommodates later verified records
  already present in the fresh baseline; all extra baseline paths remain
  protected by the existing preservation verifier. P17-004 is
  **READY_FOR_HARDWARE_TEST** at the owner-approval boundary only. No write
  phrase was requested or consumed, no sender was invoked, and no `0x101b`
  transaction occurred. Physical compatibility for this new source content
  remains unresolved.
- P17-005 adds the isolated, unregistered one-shot adapter for the exact
  P17-004 Library package profile. It reuses the P17-003 bridge, candidate,
  authorization, and independent read-back verifier; fixes the future
  preflight order to expected-device detection, parsed native `0x0019`
  capacity, complete verified backup, exact Library/package reconstruction,
  hash-only preview, and seal. Its later execution boundary captures and
  verifies a new complete pre-write backup before reconstructing and sending;
  a successful result requires a complete post-backup and non-overwriting
  before/after evidence manifest. The existing sender is constructed only
  inside the execution function after all gates; its execution-local
  authorization and one-shot call are not exposed as an adapter object. The
  success manifest accepts only the exact canonical operation sequence and
  hash-only result schema. It binds the exact package, state, capacity,
  candidate, transaction, approval phrases, no-retry policy, and expected
  post-state. Host tests cover stale/tampered bindings, identity/capacity/
  fixed-state drift, target conflict, insufficient capacity, cancellation,
  all material post-start failures, post-operation verification, and
  at-most-one sender-call enforcement. The adapter is not imported by normal
  GUI/CLI code.
  No hardware or external evidence was accessed. Independent R3 review passes
  and is recorded in
  `analysis/phase-13-p17-005-r3-review-20260901.md`. P17-005 is
  **READY_FOR_HARDWARE_TEST** only; a later task must perform a new fresh
  preflight and obtain separate operation-specific approval.
- P17-006 completed a fresh, in-order read-only preflight for the exact
  explicitly imported P17-004 Library package at
  `root\\IC_P17_LIBRARY_20260831_03`. Detection reported Sony `054c:001e`
  on bus 2/address 3; a fresh parsed `0x0019` response reported a
  3,145,728-byte capacity limit; and a complete eight-object backup was
  captured and verified with the target absent. The exact reconstructed
  candidate is 2,091,292 bytes from a 2,075,256-byte baseline, for 16,036
  bytes of growth and 1,054,436 bytes of parsed-capacity margin. Candidate,
  transaction, Library, fixed/display-state, timestamp, expected-post-state,
  no-retry, and seal bindings are preserved in the external P17-006 session.
  P17-006 is **READY_FOR_HARDWARE_TEST** only at the owner-approval boundary:
  no sender was constructed, no approval phrase was requested or consumed,
  and no `0x101b` request was issued. Physical compatibility, native numeric
  completion decoding, and operation-specific capacity semantics remain
  unresolved. The authoritative sanitized record is
  `analysis/phase-13-p17-006-exact-library-package-live-smoke-preflight-20260901.md`;
  independent R3 review passes are recorded in
  `analysis/phase-13-p17-006-r3-review-20260901.md`.
- P17-007 performed the separately approved fresh read-only revalidation for
  the exact P17-004 Library package at
  `root\\IC_P17_LIBRARY_20260831_03`. Sony `054c:001e` was detected on bus
  2/address 3; the fresh native `0x0019` response reported 3,145,728 bytes;
  and complete eight-object backups were captured with the target absent. The
  corrected sealed preflight rebuilt the exact approved candidate and
  transaction: 2,091,292-byte candidate, 16,036-byte growth, 1,054,436-byte
  capacity margin, candidate SHA-256
  `0e3af665c6046c91d1096e8570f8b63b1fc82d35788027becf65ff942ca8883f`, and
  transaction SHA-256
  `1abab51a9ddb069154fba4d411ffbe31359125270b1438d78acd47b745a54439`.
  With both exact operation phrases supplied, the merged P17-005 adapter
  captured a new complete pre-write backup but rejected its full archive
  identity because capture-generated archive/object timestamps changed its
  manifest SHA-256, even though all raw object hashes and the dynamic blob
  matched. The sender was never constructed or opened, sender calls were 0,
  and no `0x101b` request occurred. P17-007 is
  **ESCALATION_REQUIRED** pending a Project Lead decision on the safe backup
  identity boundary; no retry or normalization is permitted. The external
  evidence root and 73-entry v2 preservation manifest remain outside Git; see
  `analysis/phase-13-p17-007-exact-library-package-live-smoke-20260901.md`.
- P17-008 replaces the P17-005 full archive-manifest equality gate with the
  reviewed immutable `BackupStateIdentity`. It is derived only after the
  existing complete/integrity verifier succeeds and binds the exact Sony
  identity, protocol, canonical eight-object order and roles, filename
  semantics, lengths, raw hashes, dynamic blob, and fixed-state hashes.
  Capture archive paths, manifest hash, and acquisition timestamps remain
  preserved in the full backup/audit records and are reported separately as
  provenance differences. The isolated P17-005 adapter now accepts an
  independently captured backup only when this raw identity matches, while
  still requiring exact candidate bytes, exact transaction bytes, and exact
  non-provenance bindings before sender construction. Focused fake-host tests
  cover provenance-only equality and material identity changes; no USB or
  external evidence was accessed or modified. Independent R3 review passes
  are recorded in
  `analysis/phase-13-p17-008-r3-review-20260901.md`. P17-008 is
  **READY_FOR_HARDWARE_TEST** only; a later task must perform a new fresh
  preflight and obtain new operation-specific approval.
- P17-009 completed a new in-order read-only preflight for the preserved
  P17-004 Library item targeting
  `root\\IC_P17_LIBRARY_20260831_03`. Sony `054c:001e` was detected at bus
  2/address 3; the fresh native `0x0019` response is 64 bytes with SHA-256
  `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662` and
  reports a 3,145,728-byte capacity limit. The fresh complete eight-object
  backup has manifest SHA-256
  `b143485b76935c69a427c13f17f01fc2ebf2c1e0a7fbe596bd3b678eff88d403`,
  dynamic model 2,075,256 bytes, and raw-state identity SHA-256
  `6b330ac1b77960327f3532a0c5723d6b514ec06111344267fd2a2df888160510`;
  `_03` was absent. A comparison against the preserved P17-004 refresh is
  raw-state equal and explicitly reports only acquisition-provenance
  differences. The exact 2,091,292-byte candidate grows 16,036 bytes and
  leaves 1,054,436 bytes of parsed-capacity margin; candidate, transaction,
  and preflight seal hashes are recorded in the P17-009 dossier. The six
  active `0x001b` references are semantically rebased by the exact `0x140`
  metadata delta to the same paths/records, while `0x001c`–`0x001f` remain
  supported all-zero state. The original external 67-entry v1 manifest is
  preserved unchanged and replays with zero mismatches. The corrected
  non-overwriting v2 manifest covers 68 entries and also replays with zero
  mismatches. P17-009 is
  **READY_FOR_HARDWARE_TEST** only; sender calls,
  backend write calls, USB transmissions, and device-changing operations are
  zero. The adapter now consumes a thread-safe process-local single-use claim
  keyed by the sealed preflight before sender construction; a same-seal second
  execution fails closed. The two new phrases are bound but were not requested or consumed;
  old P17-007 phrases are not reusable. Physical compatibility and native
  numeric completion decoding remain unresolved. See
  `analysis/phase-13-p17-009-corrected-raw-state-library-package-fresh-preflight-20260901.md` and
  `analysis/phase-13-p17-009-r3-review-20260901.md`.
- P17-010 completed the separately authorized read-only revalidation for the
  same exact Library item and destination. In-order detection observed one
  Sony `054c:001e` at bus 2/address 3; the fresh native `0x0019` response is
  64 bytes with SHA-256
  `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662` and
  reports a 3,145,728-byte capacity limit. The fresh complete eight-object
  backup has manifest SHA-256
  `2a581a9282e56cac31c1e7baa42593a5b15ed94c3e0f301f6f5c9321603f9ebf`,
  dynamic model 2,075,256 bytes, and raw-state identity SHA-256
  `6b330ac1b77960327f3532a0c5723d6b514ec06111344267fd2a2df888160510`;
  `_03` was absent. Its raw state equals the P17-009 baseline while archive
  path, manifest hash, and acquisition timestamps remain preserved as
  provenance differences. The exact rebuilt candidate and transaction remain
  the P17-009-approved hashes
  `a5e9ca7f429a6f75583c1c5701bb669ed2b7f79e068dda69c63bb06300174761` and
  `1d1adc02cee8b856e2e8281ff623e84e681ec893793bebacb247a82c788749d5`.
  The candidate grows by 16,036 bytes; baseline available growth is 1,070,472
  bytes and post-candidate capacity margin is 1,054,436 bytes. The new
  P17-010 core seal is
  `fa9f8fbed201648bc351dd65b3e206460fdf11576385806739d065b77866fbc4` and
  the outer preflight seal is
  `d25ca9d32b9417f7784cbecbce8bc25b8324aa55ee1cc88519249aa04f2f3a91`.
  Sender calls, backend writes, USB transmissions, and device changes are
  zero. P17-010 is **READY_FOR_HARDWARE_TEST** only at the final owner
  approval boundary; its two exact phrases are bound but not consumed. The
  external v1 preservation manifest (67 entries), non-overwriting v2 (69
  entries), and v3 (72 entries) remain outside Git. The corrected sealed
  projection makes baseline allowance and post-candidate headroom explicit;
  see
  `analysis/phase-13-p17-010-exact-library-package-live-execution-preflight-20260901.md`.
- P17-010 attempt 01 is preserved as a safe, fail-closed pre-send result under
  the external, non-overwriting root
  `/Users/stardust/Projects/InfoCarry-Evidence/phase-17-p17-010-library-package-live-execution-20260901-02`.
  Exact Sony `054c:001e` detection, the native `0x0019` capacity response, and
  the complete eight-object backup succeeded; the target was absent. The
  harness then rejected the backup because it compared the finalized backup
  manifest with a wall-clock reference captured before acquisition. This was a
  host timing defect, not device-state evidence. The preserved failure audit
  records `write_started=false`, `sender_calls=0`, no completion,
  `approval_consumed=false`, no mutation, and no retry; its verified 13-entry
  manifest remains unchanged with zero mismatches.
  The shared freshness helper now samples its authoritative reference only
  after the complete backup callback returns, with an injectable clock only for
  deterministic tests. P17-010 uses the corrected post-finalization clock at
  the live boundary, and the established package, mixed-package, existing-text,
  new-TXT, and delete execution chains now use the same safe boundary for their
  downstream freshness checks. The replay audit ignores only verifier-generated
  `verified_at_utc` differences while retaining all raw-state and other
  provenance checks. Focused and full host validation pass at 602 tests plus
  3 intentional evidence-dependent skips. P17-010 is **READY_FOR_HARDWARE_TEST**
  only for a future new fresh attempt; no hardware was accessed in this
  correction and the prior phrases are not reusable.
- P16-001 Capture 01 is preserved outside Git and its native transaction is
  parseable. A new complete read-only post-operation backup is preserved
  outside Git and exactly matches the native transaction model. The
  transaction-model and post-state five-record addition, exact TXT/BMP
  payloads, folder/marker/child order, 16-byte BMP prefix, unchanged shared
  file payloads, and unchanged 0x001b–0x001f fixed-state objects are verified.
  The owner confirms the three timestamp meanings, normal Manager completion
  without an error, and device accessibility of the transferred package.
  P16-001 is **COMPLETE** for this exact native evidence scope. Native numeric
  completion decoding and operation-specific capacity response semantics
  remain explicit non-blocking observations. No modern mixed-package hardware
  transaction was performed.

- P16-002 is **READY_FOR_HARDWARE_TEST** for one exact host-prepared modern
  flat TXT/BMP/TXT package at the distinct destination
  `IC_P16_MIXED_20260830_02`. Its candidate, source paths and hashes, native
  TXT/BMP templates, record offsets, fixed-state hashes, offline capacity
  reference, approved modern timestamp policy, prospective `0x101b`
  transaction, and expected post-operation delta are bound and independently
  reviewed. The isolated one-shot runner is host-tested only through injected
  fake hardware boundaries; it is not exposed through the normal GUI or CLI.
  A future live task must capture a fresh complete backup and fresh native
  `0x0019` capacity response, then obtain separate operation-specific approval.
  No device was detected, queried, backed up, or written during P16-002.

- P16-003A adds the narrow, opt-in support needed to assess the owner-confirmed
  display-history-only fresh state. The fresh P16-003 backup is authoritative
  offline evidence, not an executable live baseline. Its three valid `0x001b`
  references are parsed, resolved, and semantically rebased only at or after
  the exact insertion point by the exact metadata delta; count, header words,
  unused tail, entry order, unshifted references, preserved records, and
  `0x001c`–`0x001f` all-zero state remain protected. The exact candidate,
  authorization, transaction, and independent read-back now bind the before
  and candidate fixed-state hashes plus old/new reference pairs. P16-003A is
  **READY_FOR_HARDWARE_TEST** for this offline correction only. No rebasing of
  raw evidence, normalization, hardware access, or modern transaction was
  performed.

- P16-003B performed exactly one separately approved modern `0x101b` transaction
  for the fresh-state-preserving mixed package at
  `IC_P16_MIXED_20260830_02`. The device identity was Sony `054c:001e`; a fresh
  `0x0019` response reported 3,145,728 bytes; the target was absent from the
  fresh complete backup; and the exact candidate, transaction, and preflight
  seal were revalidated before transmission. The device returned explicit
  integer `0x0000`. A complete post-operation backup and independent read-back
  verified the folder, ordered TXT/BMP/TXT children, exact payloads/prefixes,
  preserved `_01` read flags and existing content, semantic `0x001b` rebase,
  zero `0x001c`–`0x001f`, and unchanged unrelated objects. P16-003B is
  **COMPLETE** only for this exact flat package. Raw and derived evidence is
  preserved outside Git under the versioned P16-003B evidence root; no retry,
  corrective write, or broader operation occurred.
  After that operation, the owner opened `IC_P16_MIXED_20260830_02` on the
  physical InfoCarry and opened `01-introduction`, `02-page-01`, and
  `03-ending` in order; both TXT files and the BMP displayed normally without
  errors. This is human-observed physical acceptance evidence only. Opening
  the files can change read/display-history state, so any later hardware task
  must use a new fresh preflight rather than this post-operation state.

## P15 status boundary

Capture 01 remains preserved outside Git as historical native evidence. The
earlier P15-001 modern dossier was prematurely classified and is now retained
as **IMPLEMENTATION_READY** historical material; it must not be used as an
executable operation. Its native legacy operation-wide timestamp rewrite and
child-4 one-second serialization remain observed behavior, not normalized into
the modern candidate policy. The native numeric request-4 word remains
unresolved, while the owner-supplied normal Manager return and complete
post-backup persistence remain explicitly recorded as non-contradictory
observed/verified evidence.

P15-002 prepared a distinct `_02` root destination with rebuilt
source/path/order, capacity, candidate, authorization, transaction, and
verification bindings from the latest preserved Capture 01 post-state. Its
isolated live runner was host-tested through injected fake hardware boundaries,
was not exposed by the normal CLI or GUI, and passed R3 review at
**READY_FOR_HARDWARE_TEST**. The exact operation was then executed separately
under P15-003 and is recorded as complete only for that constrained shape.

P15-003 performed exactly one approved modern `0x101b` transaction for the
four-TXT `_02` package. The device returned explicit `0x0000`; a fresh complete
post-operation backup and independent read-back verified the folder, four
ordered children, exact payloads and wrappers, preserved timestamps/fixed state,
and unchanged unrelated content. The result is recorded in
`analysis/phase-15-p15-003-exact-modern-four-txt-hardware-smoke-20260830.md`.
No broader hardware behavior is proven, and this status document does not
authorize another device-changing operation.

## P15-001 native evidence checkpoint

The sanitized four-child package and operation-specific legacy Manager
procedure are recorded at
`samples/generated/P15-001-native-multi-chapter-txt/` and
`analysis/phase-15-p15-001-native-multi-chapter-txt-evidence-protocol-20260828.md`.
The package is one new root folder with four 120-byte, ASCII/CP932-compatible
CRLF TXT children in explicit order. Exact source hashes and a preservation
manifest template are included. No backup, capture, candidate, transaction,
or private device data is in the repository.

Capture 01 was supplied from the approved owner path and preserved at
`/Users/stardust/Projects/InfoCarry-Evidence/phase-15-p15-001-native-multi-txt-20260828-01/`.
The four child payloads, folder/parent-marker relationships, capacity fit,
fixed-state objects, and native range-to-post-blob equality are verified in
`analysis/phase-15-p15-001-native-multi-chapter-txt-capture-01-results.md`.
The owner event mapping and Project Lead timestamp decision are recorded, and
the constrained candidate/authorization/verifier dossier is reviewed
offline. Raw evidence remains outside Git and no modern hardware transaction
was performed.

## P16-001 native mixed-package evidence boundary

The new sanitized fixture and operation-specific legacy Manager procedure are
recorded at
`samples/generated/P16-001-native-mixed-txt-bmp/` and
`analysis/phase-16-p16-001-native-mixed-txt-bmp-evidence-protocol-20260830.md`.
The fixture is one new root folder containing exactly an introduction TXT, one
generated 237x320 one-bit BMP page, and an ending TXT in explicit order. Its
source hashes, CRLF/CP932 policy, BMP profile, visual sentinels, and manifest
are tested offline. The procedure requires a fresh complete pre-operation
backup, exact Manager/SnoopyPro before/after evidence, native USB capture,
complete post-operation backup, three mapped timestamps, and a preservation
manifest under the non-overwriting external root
`/Users/stardust/Projects/InfoCarry-Evidence/phase-16-p16-001-native-mixed-txt-bmp-20260830-01/`.

The owner supplied `capture12`, which is preserved byte-for-byte under
`08-supplied-capture12-raw/`. The parsed native `0x101b` contains the exact
three-child TXT/BMP/TXT transaction model and exposes a 16-byte BMP wrapper.
A new complete post-operation backup is preserved under
`05-post-operation/backup-20260830-02/`; it matches the transaction model
byte-for-byte and verifies persistence, exact source payloads, unchanged
shared file payloads, and unchanged fixed-state objects. The post-backup
verification, owner confirmation, and version-03 preservation manifest remain
outside Git. The owner confirms stamp-0001 idle initialization, stamp-0002
immediately before Send Selected, stamp-0003 completed/packet-idle, normal
Manager completion without an error, and device accessibility. The five new
records carry 0x6a942449 (2026-08-30T12:38:33Z), within the confirmed send
interval; the legacy global timestamp rewrite remains observed and is not a
modern rule. P16-001 is **COMPLETE** only for this exact native evidence
scope. Numeric completion decoding and operation-specific capacity response
remain unresolved/non-blocking, and no modern transaction is authorized by
this task. See
`analysis/phase-16-p16-001-native-mixed-txt-bmp-capture-01-results.md`.

## Current product safety boundary

Normal product-facing controls remain disabled for:

- generalized/new arbitrary package transfer;
- generalized deletion;
- bulk/destructive synchronization;
- restore;
- firmware/unlock and alternate modes.

Do not intentionally test interrupted-write recovery on the only valuable unit. Physical write atomicity and recovery remain unproven.

## External/hardware boundaries still unresolved

- physical modern multi-child compatibility beyond the exact verified four-TXT `_02` smoke;
- physical modern mixed-package compatibility beyond the exact verified
  TXT/BMP/TXT `_02` smoke and its tested fresh-state display-history policy;
- generalized deletion beyond the exact supported smoke scope;
- physical interrupted-write atomicity, rollback, and recovery;
- broader arbitrary/nested package behavior.
- Library batch execution, automatic grouping, and normal GUI/CLI transfer
  exposure remain disabled; P17-001/P17-002 are offline planning and review
  only, and P17-003 adds no product-facing transfer action. Explicit package
  grouping is supported at import, not inferred from multi-selection.

## Development priority

Preserve functional parity and proven transfer-safety boundaries before investing in aesthetic polish or broad transfer exposure. Continue offline engineering only where requirements/evidence support deterministic fail-closed behavior. Do not use additional model reasoning as a substitute for missing native evidence.

## Next approved engineering task

No further device-changing task is approved by this checkpoint. P16-003B remains
complete only for the exact fresh-state-preserving flat TXT/BMP/TXT package,
P17-001/P17-002 are complete only as offline Library planning/review, and
P17-003/P17-004/P17-005/P17-008/P17-009 are host-ready only for their exact
constrained package bridges and fresh-preflight/one-shot boundary. Any later
hardware operation must be
separately briefed, use a new fresh read-only preflight and evidence root,
obtain new operation-specific owner approval, and remain outside normal
GUI/CLI transfer. Native global timestamp rewriting, numeric completion
decoding, operation-specific capacity semantics, interrupted-write recovery,
arbitrary package hardware compatibility, and batch execution remain
unresolved or disabled. P17-009 is also an approval-boundary record only: its
new phrases are documented but not requested or consumed, and it does not
authorize a live operation or reuse the P17-007 approval phrases. A later
operation must use a new fresh preflight and new exact operation-specific
approval.

## Canonical reading order

1. `AGENTS.md` — compact operational rules for coding agents.
2. `CURRENT_STATUS.md` — this current snapshot.
3. `WORKFLOW.md` — human/AI task lifecycle, risk, review, and verification rules.
4. `PRODUCT_VISION.md` — stable product scope.
5. `RISK_REGISTER.md` — material safety and release risks.
6. `ROADMAP.md` — longer-term milestone/history record.
7. Relevant `analysis/` files only when the task needs their evidence.
8. `README.md` for setup, commands, and current supported developer/user entry points.

Update this file after meaningful verified checkpoints. Keep historical detail in `ROADMAP.md` and `analysis/` rather than growing this document into another project diary.
