# P15-001 — legacy multi-TXT Capture 01 results

Date: 2026-08-30
Status: **READY_FOR_HARDWARE_TEST**
Risk: **R3 — device/safety critical**

## Outcome

Capture 01 is preserved outside Git and supports the exact constrained native
shape: one new root folder containing four ordered TXT children. The timestamp
mapping and Project Lead policy now permit a bounded offline modern candidate.
The modern dossier is ready for a later hardware test, but no modern
`0x101b` transaction was performed or authorized by this record.

The external session is:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-15-p15-001-native-multi-txt-20260828-01/`

Its preservation manifest covers 119 files. The supplied raw tree remains
unchanged under `08-supplied-capture11-raw/`; raw evidence, private content,
backups, and captures remain outside Git.

## Evidence bindings

- Package: `IC_P15_MULTI_20260828_01`, four explicitly ordered TXT children,
  120 bytes each, 480 source bytes total. Source hashes are preserved in the
  committed package manifest and external session.
- Device identity: USB `054c:001e`.
- Pre dynamic model: 2,051,280 bytes,
  `d4e4fa74e4338c18aa366e016ba9cb756d0af4e84b3bd19045993553d3526f20`.
- Native post dynamic model: 2,052,272 bytes,
  `08d8eead50a177b2dc143e7f1d3274b45fe2a45f81d43c5d21cf98f33e25ac99`.
- Native USB log: one ordinary `0x101b` transaction, 2,117,808 declared
  bytes, `N=0`, `M=2,052,272`, range lengths
  `[256, 64, 65216, 0, 64, 0, 0, 2052208]`.
- Native transaction artifact: ranges 05+08 equal the complete post dynamic
  model byte-for-byte; artifact manifest SHA-256 is
  `17fc69f3aaa32a43b953e8c5d130fc9bc1a1e51c5ccf3588545e1058da1b44b9`.
- Capacity: read-only `0x0019`, field `+0x08`, limit 3,145,728 bytes,
  response SHA-256
  `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a`.
- Fixed response objects `0x001b`–`0x001f` are unchanged all-zero blocks;
  the post object set remains eight objects.
- Manager snapshots: `VICDATA.bin`, `VICLV`, and `VICMEM` are unchanged;
  `order.vnw` is a Manager-local sidecar change adding the package folder.

## Native structure — verified

The post inventory contains, in order:

1. `root\IC_P15_MULTI_20260828_01` at record offset `0x340`;
2. a leading `..` parent marker at `0x380`;
3. `chapter-01.txt`, `chapter-02.txt`, `chapter-03.txt`, and
   `chapter-04.txt` at `0x3c0`, `0x400`, `0x440`, and `0x480`.

All children are unread `0xe0` TXT records with 32-byte native prefixes and
120-byte payloads. Each payload hash equals its exact prepared source hash.
The folder table is five records wide, the children are contiguous and
ordered, and the parent-marker relationships, alignment, payload offsets, and
992-byte growth (384 metadata plus 608 aligned content bytes) reconcile.

## Timestamp and completion classifications

### Verified

- Every raw file and manifest hash was validated before analysis; raw timestamp
  files were not modified.
- The complete post backup proves the four-TXT package persisted.
- All shared file payloads, fixed-state objects, object count, and unrelated
  object payloads are unchanged.
- The constrained modern candidate preserves every existing record timestamp,
  assigns `0x6a91a907` to all six new records, fits capacity, binds the exact
  sources/order/backup/device/fixed state, and passes independent fake-only
  read-back verification.

### Observed

- The Project Owner maps `stamp-0001` to Manager/SnoopyPro initialized and
  idle, `stamp-0002` to immediately before Send Selected, and `stamp-0003` to
  transfer completed with packets idle.
- The Project Owner observed that Manager returned to its normal state without
  an observed error or ambiguity after transfer.
- The native legacy operation rewrote timestamps on all 313 shared reachable
  records. The folder, parent marker, and children 1–3 use `0x6a91a907`; child
  4 uses `0x6a91a908`.

### Inferred

- The shared timestamp rewrite is legacy operation behavior and is not a
  required modern structural invariant.
- The fourth child’s one-second difference is sequential legacy serialization,
  not a required modern invariant.
- The Manager `order.vnw` change is local bookkeeping, kept separate from
  device-resident state.

### Unresolved

- The native SnoopyPro representation does not expose a trustworthy numeric
  request-4 completion word. Offline investigation of the 2,688 bytes after
  the recognized transaction found a different sequence of USB frame headers,
  no additional `0x101b`, and no reliable two-byte request-4 result.
  The owner-normal-return observation and independently verified persistence
  are non-contradictory, but they are not a decoded numeric completion.
- The broader semantics of the native TXT prefix and changed content-dependent
  `0x0024` response remain bounded to this exact shape.

The unresolved native completion value is preserved explicitly; it is not
normalized into success. A future modern operation must obtain an explicit
numeric `0x0000`, and missing, ambiguous, malformed, or nonzero completion is
terminal with no retry.

## Offline modern reconciliation

The native post and modern candidate have the same length, reachable paths,
child order, payloads, prefixes, and non-timestamp metadata. They differ in
314 timestamp fields: 313 existing records and native child 4. This is the
approved policy difference, not an unexplained byte normalization. The modern
candidate SHA-256 is
`12cf167f1c6486ac166d2cc95d6285c7bfdbffe143875ed8c6ddc30f836ec6f9`; its
prospective transaction SHA-256 is
`63b2c991f87599a5d30b0649c06e9eb697abf2154bacab4d3d2f1bdf96f13286`.

The candidate was constructed offline from the current pre-backup plus the
observed native folder, leading-marker, and TXT-wrapper bytes. The derived
one-child template is an adapter for the existing builder’s template API; it
does not add a new device format or claim arbitrary package support.

## Gate and modern boundary

The native gate is closed only for the exact constrained shape: one root-level
folder with four ordered TXT children, the verified capacity/state envelope,
and the approved modern timestamp policy. The unresolved native request-4 word
is explicitly bounded and has no contradictory Manager or post-backup result.

The modern multi-TXT smoke dossier is **READY_FOR_HARDWARE_TEST**. It binds the
exact fresh Capture 01 pre-backup, device identity, source manifest and hashes,
paths/order, native capacity response, fixed state, candidate, transaction,
completion policy, and no-retry rule. The captured backup is an offline
evidence binding; a later live operation must recapture a fresh complete
backup immediately before any send.

A separate operation-specific owner approval is required before any modern
`0x101b`. The legacy Capture 01 approval cannot be reused, and this task did
not perform a modern transaction.

## Reproducibility

The external derived synthesis is
`07-analysis/capture11-native-evidence-synthesis-01.json`; the external
preservation manifest records the current 119-file session and its hashes.
The sanitized modern dossier is
`analysis/phase-15-p15-001-modern-multi-txt-smoke-dossier.md`.
