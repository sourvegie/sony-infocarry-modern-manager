# Current Project Status

Date: 2026-08-31
Canonical checkpoint: P17-001 offline device-aware Library transfer planning is COMPLETE; no USB access, candidate execution, or new device-changing operation occurred

## Portable offline validation

- 559 passing tests
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
- Library batch execution, package grouping, and normal GUI/CLI transfer
  exposure remain disabled; P17-001 is offline planning only.

## Development priority

Preserve functional parity and proven transfer-safety boundaries before investing in aesthetic polish or broad transfer exposure. Continue offline engineering only where requirements/evidence support deterministic fail-closed behavior. Do not use additional model reasoning as a substitute for missing native evidence.

## Next approved engineering task

No device-changing task is approved by this checkpoint. P16-003B remains
complete only for the exact fresh-state-preserving flat TXT/BMP/TXT package,
and P17-001 is complete only as offline Library planning. Any later hardware
operation must be separately briefed, use a new fresh read-only preflight and
evidence root, obtain new operation-specific owner approval, and remain
outside normal GUI/CLI transfer. Native global timestamp rewriting, numeric
completion decoding, operation-specific capacity semantics, interrupted-write
recovery, package grouping, and batch execution remain unresolved or disabled.

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
