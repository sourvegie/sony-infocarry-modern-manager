# P15-001 — legacy multi-TXT Capture 01 results

Date: 2026-08-29
Status: **BLOCKED_BY_EXTERNAL_EVIDENCE**
Risk: **R3 — device/safety critical**

## Outcome

Capture 01 is preserved outside Git and is sufficient to verify the observed
native four-child post-state, but it does not close the native gate. No modern
multi-TXT candidate, dossier, or modern `0x101b` transaction was produced.

The external session is:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-15-p15-001-native-multi-txt-20260828-01/`

Its preservation manifest covers 82 files. The raw supplied tree is retained
unchanged under `08-supplied-capture11-raw/`; raw evidence, private content,
backups, and captures are not in Git.

## Evidence bindings

- Package: `IC_P15_MULTI_20260828_01`, four ordered TXT children, 120 bytes
  each, 480 source bytes total. The four source hashes are preserved in the
  committed package manifest and the external session.
- Device identity: USB `054c:001e`.
- Pre dynamic model: 2,051,280 bytes,
  `d4e4fa74e4338c18aa366e016ba9cb756d0af4e84b3bd19045993553d3526f20`.
- Post dynamic model: 2,052,272 bytes,
  `08d8eead50a177b2dc143e7f1d3274b45fe2a45f81d43c5d21cf98f33e25ac99`.
- Native USB log: one ordinary `0x101b` transaction, 2,117,808 declared
  bytes, `N=0`, `M=2,052,272`, with range lengths
  `[256, 64, 65216, 0, 64, 0, 0, 2052208]`.
- Native transaction artifact: ranges 05+08 concatenate to the exact post
  dynamic model, byte-for-byte. The derived artifact manifest binds the
  transaction with SHA-256
  `17fc69f3aaa32a43b953e8c5d130fc9bc1a1e51c5ccf3588545e1058da1b44b9`.
- Capacity: read-only `0x0019`, field `+0x08`, limit 3,145,728 bytes,
  response SHA-256
  `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a`.
- Fixed response objects `0x001b`–`0x001f` are unchanged and remain the
  observed all-zero state. The post object set remains eight objects.
- Manager snapshots are separate from device state: `VICDATA.bin`, `VICLV`,
  and `VICMEM` hashes are unchanged; `order.vnw` changes from 227 to 253
  bytes and records the new folder in the Manager-local sidecar.

## Native structure

The post inventory verifies, in order:

1. `root\IC_P15_MULTI_20260828_01` at record offset `0x340`;
2. a leading `..` parent marker at `0x380`;
3. `chapter-01.txt`, `chapter-02.txt`, `chapter-03.txt`, and `chapter-04.txt`
   at `0x3c0`, `0x400`, `0x440`, and `0x480`.

All children are unread `0xe0` TXT records with 32-byte native prefixes and
120-byte payloads. Each payload hash equals its exact prepared source hash.
The folder table is five records wide (leading marker plus four children),
the child records are contiguous and ordered, and the root insertion boundary
and parent-marker relationships reconcile. Native growth is 384 metadata
bytes plus 608 aligned content bytes.

## Required conclusion labels

### Verified

- The prepared source package, source hashes, pre-backup, post-backup, native
  log, transaction artifact, and capacity response were hash-validated.
- The pre target path is absent; the post target is exactly one new root folder
  with four ordered TXT children.
- Child payloads, 32-byte prefixes, lengths, offsets, alignment, folder table
  width, parent-marker relationships, and native range-to-post-blob equality
  pass independent offline checks.
- All shared file payloads are unchanged; the five fixed-state response
  objects and object count are unchanged.

### Observed

- All 313 shared reachable records have different timestamp fields in the
  supplied pre/post dynamic blobs.
- The new folder, leading marker, and children 1–3 use `0x6a91a907`; child 4
  uses `0x6a91a908`.
- The three timestamp artifacts are valid and chronological with sequences
  1–3. Their event mapping is absent.
- The Manager-local `order.vnw` grows and adds the package folder name.
- The native capture contains one ordinary `0x101b` transaction with the
  recorded range geometry.

### Inferred

- The `order.vnw` change is Manager-local bookkeeping rather than proof of
  device-resident completion. This inference is kept separate from the
  verified `VICDATA` and post-backup result.
- The changed `0x0024` response and `0x8004` probe are content-dependent
  responses for this capture; their broader semantics remain unclaimed.

### Unresolved

- No owner-supplied event mapping identifies which timestamp is initialization,
  pre-send, or completed-packet idle.
- The offline parser does not decode request-4 completion, and the supplied
  tree contains no explicit Manager result text or screenshot.
- The all-shared-record timestamp rewrite is unexplained and conflicts with the
  current offline preservation policy. It must not be normalized away.
- The one-frozen-timestamp policy cannot represent the observed fourth-child
  timestamp without a reviewed model change.

## Native gate and modern boundary

The native gate is **not closed**. The result is
`BLOCKED_BY_EXTERNAL_EVIDENCE`, not a compatibility approval. The current
offline builder also rejects the exact four-child native post as a declared
template because it is intentionally limited to one template child per kind;
that failure is recorded rather than silently adapting the model.

Follow-up evidence/decisions required before any modern dossier:

- owner-supplied mapping for `stamp-0001` through `stamp-0003`;
- explicit Manager result/completion evidence or a reviewed protocol-specific
  completion decoder;
- PM/owner decision and independent R3 review of the shared timestamp rewrite
  and per-record timestamp behavior; and
- a fresh modern smoke approval, separate from the legacy Capture 01 approval,
  if and only if the reconciled candidate passes review.

The legacy approval cannot authorize a modern transaction. No device-changing
operation is authorized by this record.

## Reproducibility

The complete external derived synthesis is
`07-analysis/capture11-native-evidence-synthesis-01.json`, SHA-256
`9ff7e62c14d85d8906d24bf4d3e46766caed2cc5efb52e5941dda5deb68c6f11`.
The external preservation manifest has canonical-scope SHA-256
`12597ad2065e72680920e809c7db5ee3f49b3cf813baee9c1312bf6ed7eb679b` and file
SHA-256 `e95d99773ce28748d9093f99b280df867f6978fe88f9b52b43dbcd5d0609ed9b`.
