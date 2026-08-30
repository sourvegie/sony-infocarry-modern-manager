# Sony InfoCarry Modern Transfer Roadmap

This roadmap implements the [product vision](PRODUCT_VISION.md) and is governed
by the [risk register](RISK_REGISTER.md). Critical release risks are addressed
before expanding device-write capability.

## Source-of-truth boundary

This sanitized checkout is the future development source of truth. Verified
commits are pushed normally to the private remote
`https://github.com/sourvegie/sony-infocarry-modern-manager.git`.

The sibling evidence-bearing `modern-client` checkout remains a read-only
local research archive. Do not commit product work there, rewrite or clean its
history, or push it. Older commit SHAs in this roadmap refer to that preserved
local history unless explicitly identified as commits in this sanitized
repository. Raw captures, complete backups, live-operation evidence, original
Sony software, and transaction-range binaries are intentionally absent here.

## Goal

Deliver a modern application that can safely detect a Sony InfoCarry VNW-V15, inspect it, make a complete backup, export and import supported content, and transfer data in both directions without requiring Windows 2000.

The first supported computer platform is macOS. The protocol and conversion layers should remain portable to Linux and Windows.

## Definition of Done

The v1.0 project is complete when a non-technical user can:

1. Connect the InfoCarry and see a clear device status.
2. Create a verified backup without changing device contents.
3. Browse and export the backed-up information into ordinary files.
4. Import supported text, memo, image, and other understood content.
5. Transfer selected content to the device after an automatic backup.
6. Read the content back and verify that the round trip succeeded.
7. Recover safely from disconnects, timeouts, malformed data, and cancelled operations.

## Release Gates

- **v0.1 — read-only recovery manager:** detect the device, make and verify a
  complete backup, browse it, download/export selected content, and give useful
  failure guidance. The packaged UI contains no device-write control.
- **v0.2 — guarded selected upload:** add only the proven existing-record text
  replacement workflow, with preview, capacity/encoding checks, a fresh
  automatic backup, explicit authorization, progress, and full read-back
  verification.
- **v0.3 — guarded new TXT creation:** prove the legacy new-record metadata and
  sidecar behavior, then add one new TXT record with exact preview, fresh
  backup, authorization, bounded one-shot transfer, and full read-back.
- **v0.4 — selective removal and prepared content:** separately prove deletion
  of one disposable item, then prove any folder/multi-record creation required
  for one prepared book/content package.
- **v0.5 — local Library and safe staged transfer:** integrate non-destructive
  picker/drag-and-drop import, Prepare, selected transfer, and a capacity-aware
  queue using only operation types already proven. **Transfer all ready items**
  is additive, not sync/replace/send-all.
- **v1.0 — general content manager:** add supported new-file/folder creation,
  text/memo/image import, rename/delete, batches, and separately proven restore.

The old Manager's destructive send-all and receive-all behavior is not an
initial parity requirement. Firmware, unlock, demo/service, and alternate modes
are separate research topics and are excluded from the normal application.

## Parallel Delivery Tracks

The project uses two coordinated tracks so research completion is not confused
with product exposure:

- **Compatibility and safety research:** legacy evidence, lossless device-state
  modeling, offline equivalence, fake-transport failure behavior, controlled
  live validation, and separately approved recovery research.
- **Product delivery:** expose only operations whose research and safety gates
  are complete, then integrate them into the ttk workflow, Library, packaging,
  and user guidance.

The canonical operation-by-operation status is maintained in
`analysis/legacy-operation-parity-matrix-2026-08-22.md`. A research result may
be complete while its product control remains disabled. Conversely, a product
milestone is not complete merely because exploratory code exists.

## Status Summary

| Phase | Status | Exit gate |
| --- | --- | --- |
| 0. Preserve and inventory evidence | Complete | Key ISO files match the extracted package by SHA-256 |
| 1. Discover USB descriptors | Complete | Interface and bulk endpoint addresses are verified |
| 2. Map the Windows driver protocol | Complete | Each operation required by commands `0x18` and `0x19` is mapped to USB |
| 3. Capture reference behavior | Partially complete | Native selected-send captures are preserved and analyzed; additional captures are evidence-driven |
| 4. Build the read-only transport | Complete | Mac client detects, validates, claims, and releases the device safely |
| 5. Query device information | Complete | Commands `0x18` and `0x19` return repeatable, preserved, conservatively decoded data |
| 6. Make complete raw backups | Complete | Repeated backups are complete and hash-stable |
| 7. Decode and export content | Complete for v0.1 | Known content exports deterministically and unknown bytes remain preserved |
| 8. Add guarded writes | Proven for constrained existing-text replacement | Two guarded modern transactions completed; general creation/restore remains blocked |
| 9. Build the desktop workflow | Complete for constrained v0.2 | Read-only manager and guarded existing-text GUI workflow verified |
| 10. Package and release | v0.1 hobby package complete; later refresh pending | Canonical checkout, reproducible wheel, guide, tests, and smoke evidence |
| 11. Offline conversion foundation | First slice complete; deprioritized | Strict authoring, logical pages, and initial tabs exist; only core-transfer prerequisites proceed now |
| 12. Prove general new-file transfer and selective delete | Active — I.6 is complete for one constrained live package smoke; I.7 add-01, the isolated display-history/Mark-1/Bookmark-1 state experiment, and one stateful legacy deletion effect are independently verified; H.2's corrected offline gate and one constrained modern root-TXT delete smoke are complete for their supported scopes; I.8 logical multiple-TXT, I.9 typed TXT/BMP, and I.10 flat ebook planning are complete offline | The preserved I7 comparison now has zero unexplained non-timestamp differences after timestamp-only normalization; arbitrary package behavior, generalized deletion, request-4 completion, physical recovery, and normal product exposure remain unproven |
| 13. Integrate Library, Prepare, and staged transfer | J.0–J.2 local foundation complete; J.3 deferred | The crude Library import/Prepare UI is usable; device-aware planning waits for proven package operations |

Current Phase 12/I.7/H.2 status: native capacity semantics are resolved offline,
and commit `09452be` adds actual parsed `0x0019` response binding, native-only
capacity authorization, ordered fake workflow coverage, and an isolated
runner. Attempt 02 completed one approved constrained package smoke with
`0x0000`; the preserved post-operation backup passes independent read-back
after `cf7803b` corrected the expected payload-dependent object boundary. The
complete suite is **483 tests** with three intentional evidence-dependent
skips after the read-only I.7 experiment-support and bookmark-correction slices. The operator protocol
and offline helpers do not authorize or perform a device operation. The
separately approved I7 add-01 was completed and independently verified; the
evidence is synthesized in
`analysis/phase-13-milestone-i7-legacy-add-01-results-20260823.md` and its JSON
companion. The self-contained Windows 2000 timestamp tool is
`support/windows2000-timestamp/`; its logs are ignored and validated only by
`scripts/validate_timestamp_logs.py`. The harmless two-stamp dry run passed,
and the separately approved state experiment completed with isolated
display-history, Mark-1, and Bookmark-1 backups. The separately approved I7
legacy-delete observation is synthesized in
`analysis/phase-13-milestone-i7-legacy-delete-20260825.md`: exactly one
persisted path was removed, no path was added, all surviving payloads were
preserved, and the native candidate exactly matched the post-delete blob.
Request-4 completion and the general timestamp/fresh-state rules remain
unresolved. The offline H.2 generalized-delete model and fake-only workflow
are recorded in
`analysis/phase-13-milestone-h2-offline-generalized-delete-20260825.md`.
The 2026-08-26 hardening comparison is recorded in
`analysis/phase-13-milestone-h2-offline-delete-hardening-20260826.md`; it
normalizes only surviving record timestamp fields and the derived header
checksum, and the relation-corrected comparison has zero remaining
non-timestamp differences. H.2's offline structural gate is complete for its
supported scope, but these reports do not authorize arbitrary live operations.
Arbitrary package transfer, generalized delete, and normal GUI/CLI
package/delete actions remain prohibited. One separately approved modern
delete smoke is recorded below for its exact target and all-zero fixed-state
scope only.

## Verified Starting Facts

- USB identity: Sony `VID 0x054C`, `PID 0x001E`.
- The connected unit enumerates as USB 1.1 full-speed at 12 Mbps.
- It has one configuration and an 8-byte endpoint-zero packet size.
- It is a proprietary USB device, not USB mass storage.
- The legacy stack is `infoCarryManager.exe` -> `VICCTR.dll` -> `VicOne.dll`/`VicTwo.dll` -> `VICUSB.sys`.
- `VICCTR.dll` opens separate named read and write pipes.
- `VicTwo.dll` contains explicit VNW-V15 paths and transfer logic.
- Configuration and hardware-information command IDs are `0x18` and `0x19`.
- The legacy application uses bounded/chunked bulk transfers; a 128 KiB limit is present in `VicTwo.dll`.
- A selected operation is a logical change to one item, but the ordinary
  `0x101b` path carries the complete candidate dynamic model. The owner's
  legacy-Manager same-duration warning corroborates the capture evidence;
  progress and timing must not be described as a selected-payload-sized copy.

## Phase 0 — Preserve and Inventory Evidence

- [x] Preserve the original ISO separately from extracted files.
- [x] Calculate the ISO SHA-256 hash.
- [x] Inventory installers, executables, DLLs, drivers, configuration files, converters, and help files.
- [x] Verify important extracted files against the copies inside the ISO.
- [x] Identify the supported USB VID/PID from `VICUSB.inf`.
- [x] Identify the public `VICCTR.dll` API and model-specific DLLs.

Evidence already collected includes matching hashes for the driver, INF, MSI, manager executable, `VICCTR.dll`, `VicOne.dll`, and `VicTwo.dll`.

## Phase 1 — Discover USB Descriptors

Purpose: establish the exact interface layout without sending InfoCarry application commands.

- [x] Confirm that the connected Mac sees `054C:001E`.
- [x] Record speed, configuration count, and endpoint-zero packet size.
- [x] Make libusb available on the development Mac.
- [x] Read and save the raw device and configuration descriptors.
- [x] Record interface number, alternate setting, class/subclass/protocol, and configuration value.
- [x] Record every endpoint address, direction, transfer type, and maximum packet size.
- [x] Confirm the currently active/default transport pair: bulk OUT `0x01`, bulk IN `0x82`.
- [x] Add descriptor-only `detect` and `descriptors` CLI commands and fixture-based parser tests.
- [x] Determine in Phase 2 whether the legacy driver ever switches to alternate setting 1 (`0x81` IN and `0x02` OUT). The shipped manager does not call its alternate-interface wrapper and uses alternate setting 0.

Exit gate: satisfied on 2026-08-19. The active bulk-IN and bulk-OUT endpoint addresses were verified from the real device. No application-level command was sent.

User checkpoint: approve installation of the small libusb dependency and leave the powered device connected.

## Phase 2 — Map the Windows Driver Protocol

Purpose: replace the obsolete kernel driver with equivalent user-space USB requests.

- [x] Enumerate the private driver control-code range `0x220000` through `0x220024`.
- [x] Identify bulk read/write, pipe reset, configuration, interface-selection, and vendor/class request paths in the driver.
- [x] Identify the application-side six-byte command/length structure passed into the driver.
- [x] Assign a verified behavioral meaning to every control code used by `VicTwo.dll`.
- [x] Recover `bmRequestType`, `bRequest`, `wValue`, `wIndex`, direction, and expected data length for each required USB control transfer.
- [x] Map status values, busy polling, retry intervals, completion, cancellation, and error handling. Values `1` and `2` are verified failures but their device-specific names remain unknown.
- [x] Document the receive sequence used by commands `0x18` and `0x19`.
- [x] Document the send and receive data sequences without executing writes.
- [x] Publish the result as `analysis/protocol.md` with verified/inferred labels.

Exit gate: satisfied on 2026-08-20. The two read-only information commands are represented entirely as documented libusb operations in `analysis/protocol.md`. No device request was sent during this phase.

## Phase 3 — Capture Reference Behavior

Purpose: verify only details that cannot be established confidently through static analysis.

- [x] Decide whether static analysis left any material ambiguity. None blocks commands `0x18` or `0x19`; ambiguity remains for later backup, write, cancellation, and recovery behavior.
- [ ] If needed, prepare an isolated Windows 2000 environment or an original x86 Windows computer.
- [ ] Capture device discovery and hardware/configuration queries.
- [ ] Capture a full backup operation.
- [x] Capture deliberately small selected-send operations with SnoopyPro.
- [x] Sanitize, annotate, hash, and preserve the selected-send captures as
  read-only evidence.
- [x] Compare the selected-send traces with the documented driver behavior and
  reconstruct their eight ordinary write ranges.
- [ ] Capture cancellation only if it is needed to resolve a release-blocking
  ambiguity; offline failure injection currently covers the modern sender.

Exit gate: satisfied for the read-only client and constrained existing-text
write path. Every request needed for commands `0x18` and `0x19` is supported by
static evidence, and native selected-send captures are preserved and analyzed.
Discovery, full-backup, or cancellation capture remains conditional on a
specific unresolved release requirement.

User checkpoint: only required if a capture is necessary; the user may need to operate the original manager while capture is active.

## Phase 4 — Build the Read-Only Transport

Purpose: create the smallest safe modern client that opens the hardware correctly.

- [x] Create the Python package and test layout.
- [x] Implement strict VID/PID discovery and reject unrelated USB devices.
- [x] Implement configuration and interface selection.
- [x] Discover endpoints from descriptors instead of assuming pipe numbers.
- [x] Implement bounded control and bulk transfers with finite timeouts.
- [x] Implement status polling, retry limits, cancellation, and clear error messages.
- [x] Provide `infocarry detect` and `infocarry descriptors` commands.
- [x] Keep all write-capable entry points absent or hard-disabled. The production receiver defaults to an empty command allowlist, the PyUSB backend has no bulk-write method, and the CLI has no application-command entry point.
- [x] Add tests using captured descriptors and synthetic transport responses.

Exit gate: satisfied on 2026-08-20. Twenty offline tests passed, followed by three successful real-device open/claim/release cycles on interface 0 alternate 0. No vendor request, application command, or bulk transfer was sent. Evidence is recorded in `analysis/phase-4-read-only-transport.md`.

## Phase 5 — Query Device Information

- [x] Implement the read handshake used by `VicTwo.dll`.
- [x] Implement raw command `0x18` with strict expected-length checks.
- [x] Implement raw command `0x19` with strict expected-length checks.
- [x] Save raw responses before parsing, with exclusive creation, fsync, SHA-256, and a manifest.
- [x] Decode fields only when verified. Display dimensions are decoded as 240 x 320; configuration bytes and other hardware values retain neutral offset-based names.
- [x] Compare results across reconnects. Four observations per command are byte-identical; legacy-manager comparison remains optional because no material ambiguity blocks the read-only result.
- [x] Provide `infocarry info --save-raw <new-directory>`.

Exit gate: satisfied on 2026-08-21. Twenty-nine offline tests pass. Commands `0x18` and `0x19` each produced four byte-identical 64-byte responses across separate and combined sessions. Raw files and manifests were preserved before parsing, the device remained detectable, and no device-content request was sent. See `analysis/phase-5-device-info.md`.

## Phase 6 — Make Complete Raw Backups

- [x] Identify every command and object required by the exported legacy receive/backup workflow. The statically verified order is `0x24`, `0x1b`–`0x1f`, a 64-byte `0x8004` probe, then a dynamically sized `0x8004` blob.
- [x] Implement chunked bulk-IN transfer with exact-length and short-read handling.
- [x] Preserve raw objects with timestamps, hashes, protocol metadata, and a manifest.
- [x] Refuse to overwrite an existing backup directory.
- [x] Test cable disconnect, timeout, cancellation, low-space, and malformed-response handling with offline simulations.
- [x] Make at least three backups of an unchanged device and compare hashes. All eight objects are byte-identical across three complete archives.
- [x] Provide `infocarry backup <new-directory>`. The command passed offline tests and three complete live-device runs.

Offline milestone: satisfied on 2026-08-21. Forty tests pass. Static evidence, the dynamic-length formula, safety limits, unresolved meanings, and implementation behavior are recorded in `analysis/phase-6-backup-protocol.md`. No additional device command was sent during this work.

Exit gate: satisfied on 2026-08-21. The live probe selected a statically verified direct length of 2,050,100 bytes. After correcting the initial offline marker-offset assumption, three complete backups produced identical per-object hashes and the same aggregate SHA-256 (`74b0704621c78bf9908e12e7103d192984a120a7c3109eb599cac2e86e23dce6`). The device remained detectable after all read-only operations. See `analysis/phase-6-backup-protocol.md`.

User checkpoint: satisfied on 2026-08-21; device contents were kept stable during repeatability testing.

## Phase 7 — Decode and Export Content

The v0.1 release gate is satisfied: known content exports deterministically and
all unknown data is retained. The two remaining unchecked reconstruction items
are research backlog for broader v1.0 mutation support; they no longer block a
read-only recovery release.

- [ ] Reconstruct `VICDATA.bin`, `VICMEM.bin`, `VICLV.bin`, `order.vnw`, and related structures. `VICLV.bin` and the `VICMEM.bin` container layout are complete: their recovered headers, section/entry layouts, parser/builders, and synthetic round-trip tests are implemented. Every VICMEM record now has verified path storage at offset zero; the four category indices are statically correlated with `0x001b` display history and `0x001c`–`0x001e` mark lists 1–3. Tail dword 4 is the rendered-line position, while tail dword 3 and auxiliary fields remain unresolved. `order.vnw` now has verified writer/reader rules, metadata-record ordering, and first-failed-read-probe numeric collision handling, with lossless offline parsing and pure naming helpers. Existing-record `VICDATA` payload replacement, a bounded file rename, a template-backed file add, and a leaf-file delete now round-trip through the observed XOR layer; complete model regeneration and full sidecar synchronization remain unresolved. The 32-byte text-view wrapper's raw field offsets and checksum serializer are also recovered.
- [ ] Identify record headers, sizes, offsets, alignment, checksums, flags, timestamps, and character encoding. Header/layout/checksum, Unix timestamps, CP932 names, native payload boundaries, `0x20 = read`, `0xe0 = unread`, and 38 of 41 private glyph roles are verified. Three graphic components and individual mutable wrapper fields remain unresolved.
- [x] Correlate records with the first manager-produced sidecar fixture. The
  Japanese manual paths in `VICMEM.bin` resolve to backup records `0x0e40`
  and `0x0e80`; the remaining source-folder names are absent from this backup
  tree, so the correlation is explicitly partial. See
  `analysis/phase-7-fixture-inventory.md`.
- [x] Compare the second manager-produced fixture. `VICDATA.bin`,
  `VICLV.bin`, and `order.vnw` are byte-identical to fixture 1. The only
  change is 722 bytes of post-NUL opaque `VICMEM.bin` record storage; all
  verified paths, counts, auxiliary words, and tail fields remain unchanged.
  See `analysis/phase-7-fixture-2-comparison.md`.
- [x] Implement a pure generated-name helper for the statically verified
  one-based counter, raw-extension branch, and low-state-bit `ecd` override.
  Static tracing now also verifies metadata-record ordering and the first
  positive suffix whose read-open probe fails. The bounded compatibility
  helper performs no file or device I/O.
- [x] Add a reproducible offline fixture report. It verifies the observed
  XOR-`0xaa` layer and legacy backup checksum in memory, parses all three
  sidecars, records hashes and correlations, and writes only a JSON manifest.
  See `analysis/phase-7-fixture-report.md`.
- [x] Export known text and memo data without altering the raw backup. Exact native bytes and separate CP932-decoded views are produced; invalid device-specific bytes are escaped and reported.
- [x] Export images into standard formats while retaining original bytes. All 150 embedded payloads are already valid 1-bit Windows BMP files and are extracted exactly.
- [x] Preserve unknown records losslessly and report them clearly. Raw records, unresolved flags, prefixes, native payload hashes, and source provenance remain in the export manifest.
- [x] Add round-trip format tests using fixtures. The offline fixture report
  now asserts exact `VICLV.bin`, `VICMEM.bin`, and `order.vnw` parse/serialize
  round trips; text-view-wrapper fixture tests are also present. Constrained
  `VICDATA.bin` decode/replace/add/delete/rename/re-encode round trips pass for
  synthetic trees, while the preserved manager fixture anchors the payload
  path. Full arbitrary repacking remains gated on unresolved model and sidecar
  fields.

Category-mapping checkpoint: satisfied on 2026-08-21. Static receive and
serialization paths traverse the four fixed state lists in the same order as
commands `0x001b`–`0x001e`, with section masks `1`, `2`, `4`, and `8`. This
correlates categories 0–3 with display history and mark lists 1–3 without
assigning meanings to opaque auxiliary or record bytes. See
`analysis/phase-7-vicmem-category-mapping.md`.

Offline export milestone: satisfied on 2026-08-21. The stable blob contains 362 records forming 57 directories and 248 files with no cycles, orphans, or out-of-bounds payloads. The legacy checksum algorithm is implemented and agrees with all live blobs. Fifty-five tests pass, and exports from independent stable backups are byte-identical. Unix timestamps are rendered in UTC; all 194 occurrences of 41 private CP932-like sequences are inventoried, with 38 semantic roles mapped directly from the embedded manual; neutral parsers reproduce the fixed `0x001b`--`0x001f` response structures; and the recovered `VICLV.bin` layout has a lossless parser/builder with exact synthetic round trips. Format evidence and unresolved semantics are recorded in `analysis/phase-7-backup-format.md`. No device command was sent during offline decoding.

Read-state checkpoint: satisfied on 2026-08-21. After the user opened one known unread file and scrolled continuously into the adjacent file using the device UI, two complete read-only backups were byte-identical. Both displayed records changed from `0xe0` to `0x20`, their native payloads remained identical, and command `0x001b` prepended the corresponding directory/initial-file offsets. This verifies unread/read flags and identifies `0x001b` as display history. The second read-only backup caused no further change. See `analysis/phase-7-read-state-experiment.md`.

Mark-state checkpoint: satisfied on 2026-08-21. Stable read-only captures of isolated final states verify `0x001c` as mark list 1, `0x001d` as mark list 2, and `0x001e` as mark list 3. Each state contained the sole count-authorized metadata-relative `0x01c0` entry (absolute file record `0x0200`) in the corresponding response, while the other two commands declared count zero. Selecting a different mark replaced the previous mark on the tested file. The main content blob and display history remained unchanged throughout. Zero-count responses retained stale `0x01c0` bytes in unused slots, proving consumers must honor the count and ignore tail slots. Every state was confirmed by two byte-identical complete backups. See `analysis/phase-7-mark-state-experiment.md`.

Bookmark-state checkpoint: satisfied on 2026-08-21. Setting Bookmark 1 at the beginning of the same manual file changed only the first five-value group of command `0x001f` to `(0x01c0, 0x0140, 0, 0, 0)`. Setting Bookmark 2 one page lower changed only the second group to `(0x01c0, 0x0140, 0, 20, 0xfff101be)`, leaving Bookmark 1 intact; moving it to two pages produced `(0x01c0, 0x0140, 0, 40, 0xfff10448)`. Moving Bookmark 2 to the beginning of adjacent absolute file record `0x0240` changed its first dword to metadata-relative `0x0200` and reset the position fields to zero, verifying dword 1 as the selected-file record offset relative to metadata start `0x40`. Every state was confirmed by two byte-identical complete read-only backups; the main blob and unrelated responses remained unchanged. Dword 4 advances by 20 rendered lines per page, while dword 5's low 16 bits point to source-byte offsets 446 and 1096 at the corresponding valid CP932 wrapped-line boundaries. Its upper `0xfff1` tag and dwords 2/3 remain unresolved. See `analysis/phase-7-bookmark-state-experiment.md`.

Exit gate: all known content is exported deterministically and unexplained bytes remain preserved.

## Phase 8 — Add Guarded Writes and Authoring Research

The proven release scope is replacement of an existing text record. General
new-file creation, live delete, and restore remain unavailable until their
separate evidence and recovery gates are satisfied.

- [x] Document the write, completion, cancellation, and commit sequences. The
  ordinary path is one segmented `0x101b` transaction followed by request-4
  completion; it has no separate commit or abort request. Command `0x101d`
  belongs only to the distinct unlock workflow and is not a proven general
  commit. See `analysis/phase-8-write-transaction.md`.
- [x] Define a non-transmitting prospective transaction artifact. It validates
  all eight ranges, exact `N`/`M` length relationships, staging metadata, and
  hashes; preserves each range without overwrite; records explicitly that no
  USB transmission occurred; and has no CLI or USB backend integration.
- [x] Implement the two fixed state-range serializers independently of USB
  transmission. Static layouts at `VicTwo.dll` `0x10004660` and `0x10004760`
  are unit-tested; unused tails remain zero-filled. See
  `analysis/phase-8-write-transaction.md` and `src/infocarry/write_state.py`.
- [x] Implement the fixed range-3 staging builder independently of USB
  transmission. It emits only explicit big-endian `N`/`M` fields and the
  verified `0xff` fill; variable content remains caller-supplied.
- [x] Record and test the recovered model-builder size formulas independently
  of USB transmission. The formulas cover ordinary node allocation and the
  distinct range-8 padding rule; model bytes and range splitting remain
  unresolved. See `src/infocarry/model_layout.py`.
- [x] Implement the statically verified 64-byte metadata-node transformation
  independently of USB transmission, including five big-endian dwords and the
  legacy dangling Shift-JIS lead-byte boundary rule. See
  `src/infocarry/node_record.py`.
- [x] Compare the node transformation with all 362 metadata records in the
  preserved Phase 6 backup; every reconstructed record was byte-identical.
  The full eight-range payload still lacks a legacy write capture comparison.
- [x] Add an offline structural backup repacker for replacing payloads in the
  existing record set while preserving unknown fields and tree structure. It
  recomputes offsets/checksum and remains explicitly non-device-facing.
- [x] Connect the structural repacker to the observed manager `VICDATA.bin`
  XOR-`0xaa` layer. The guarded in-memory workflow validates decode and encode,
  returns byte-identical output for no changes, and rejects malformed input.
  A changed-length replacement against the preserved manager fixture retained
  all 1,856 reachable paths and passed parser/checksum validation. This does
  not prove that the XOR key is universal or that a device accepts the result.
- [x] Add a deterministic non-transmitting replacement audit. It reports
  source/candidate and payload hashes, target path and record offset, checksum
  changes, per-region length and difference counts, preserved invariants, and
  explicit no-USB/no-filesystem-output safety declarations. The report contains
  no candidate bytes and is not exposed through the CLI.
- [x] Add a conservative offline text-authoring preview for existing `txt`
  records. It normalizes Unicode line endings to observed CRLF, performs strict
  CP932 encoding, rejects unsupported characters and NULs, preserves the
  existing native prefix, applies only caller-supplied capacity limits, and
  feeds the bytes into the replacement audit without saving or transmitting
  them. See `src/infocarry/text_authoring.py`.
- [x] Build an evidence matrix for ranges 4–8 and unresolved model headers.
  It records verified sizes, source addresses, known byte rules, unresolved
  fields, and the smallest falsification test for each range. It does not
  promote model-size formulas into payload semantics. See
  `analysis/phase-8-range-evidence-matrix.md`.
- [x] Perform a targeted static inspection of range 5. The dispatch confirms
  its fixed `0x40`-byte length and position 5, and stack accounting proves that
  the range-5 pointer is exactly the destination produced by helper
  `0x10001550`. Its byte-level transformation is implemented and tested as an
  offline serializer in `src/infocarry/range5_model.py`; semantic field names
  and all other model ranges remain unresolved.
- [x] Recover range-5 source-object candidates from the preserved native
  transactions. The fixed helper map is exactly invertible for the ordinary
  64-byte length; both captures round-trip byte-for-byte through the offline
  serializer. The recovered source bytes are recorded without assigning field
  names in `analysis/phase-8-range5-source-recovery.md`.
- [x] Deepen the range-8 model-builder boundary. The fixed prefix helper
  `0x100042f0` is implemented as the offline `serialize_legacy_prefix()`
  primitive, and the recursive append grammar (prefix, variable node data,
  `0xff` alignment, child/sibling traversal) is documented. The variable
  record format and source-node construction remain unresolved.
- [x] Complete the ordinary-worker static call graph. The ten dispatcher
  arguments, range-6 literal-null path, range-7 zero-length descriptor,
  range-8 allocation/padding, fixed-record builder, duplicate 64-byte node
  serializer, and declared-length aggregation are recorded in
  `analysis/phase-8-static-worker-callgraph.md`. This strengthens the
  ordinary-path boundary but does not recover alternate model modes.
- [x] Add a guarded offline payload composer. It generates ranges 1–3 and 5
  from verified serializers, requires unresolved ranges 4/6/7/8 explicitly,
  and can re-compose all three preserved native transactions byte-for-byte
  without USB. See `src/infocarry/payload_builder.py` and
  `analysis/phase-8-offline-payload-generator.md`.
- [x] Add an explicit model-range composer for caller-supplied legacy nodes.
  It applies the recovered fixed-prefix, child/sibling, and `0xff` alignment
  grammar without inventing unresolved source fields. This is a structured
  offline candidate path; arbitrary `VICDATA`-to-node generation remains
  gated on an independent manager content tree. See
  `src/infocarry/model_range.py` and
  `analysis/phase-8-model-range-and-write-gate.md`.
- [x] Make the ordinary decoded-blob split explicit. Across all preserved
  captures, range 5 is exactly decoded `VICDATA[0:0x40]` and range 8 is exactly
  decoded `VICDATA[0x40:]`; `build_from_decoded_vicdata()` validates and
  composes that relationship offline from a separate state snapshot. This
  does not generate sidecars or open a USB path.
- [x] Add an offline toolkit-authored existing-record replacement boundary.
  `build_from_replacements()` repacks one or more existing file payloads,
  preserves native prefixes and unknown fields, recomputes offsets/checksum,
  and feeds the validated result into the ordinary range split. A template-
  backed add, leaf-file delete, and encoded bundle wrappers now cover bounded
  structural mutations; complete model and sidecar regeneration remains
  unresolved. See
  `analysis/phase-8-arbitrary-content.md`.
- [x] Add a bounded offline existing-file rename mutation. It updates the
  validated `VICDATA` metadata name and exact matching `VICMEM` selected-file
  paths while preserving `VICLV.bin` and `order.vnw` byte-for-byte. The
  companion structural helpers now support a template-backed add and leaf
  delete with exact `VICMEM` path removal; directory/recursive mutation and
  full sidecar synchronization remain unresolved. See
  `analysis/phase-8-bundle-rename.md`.
- [x] Add a bounded offline structural-mutation layer. It validates a
  template-backed arbitrary-payload add, a leaf-file delete with
  metadata/content offset remapping, and exact `VICMEM` path removal, without
  claiming model-node or `VICLV`/`order.vnw` regeneration. See
  `analysis/phase-8-structural-mutations.md`.
- [x] Add exact-path `VICLV.bin` rename/delete helpers and connect them to the
  bounded bundle wrappers. Category bytes, entry order, headers, and opaque
  post-NUL padding are retained; new-file category assignment remains
  unresolved. See `analysis/phase-8-sidecar-sync-boundary.md`.
- [x] Capture one native baseline and one cumulative selected-send SnoopyPro
  session. The traces contain the ordinary preflight sequence and a genuine
  second `0x101b` host-to-device transaction whose declared model region `M`
  grows by exactly 3,232 bytes. Native evidence and hashes are recorded in
  `analysis/phase-8-usblog-capture-analysis.md`. The native record parser now
  reconstructs all eight ranges, including exact lengths and per-range hashes;
  the first selected transaction is byte-identical to baseline and the second
  changes ranges 1, 3, 5, and 8 only. This remains read-only evidence.
- [x] Add a reproducible native-capture parser and JSON-safe range comparison
  report. It validates payload/completion records, reconstructs the observed
  eight-range path, reports exact hashes and localized differences, and keeps
  unresolved field semantics out of production code. See
  `src/infocarry/usblog.py`, `src/infocarry/usblog_report.py`, and
  `analysis/phase-8-usblog-capture-analysis.md`.
- [ ] Complete arbitrary-content payload generation independently of USB
  transmission. Existing-record replacement, template-backed add, leaf delete,
  bounded rename, and the decoded range split are reproducible offline. The
  ordinary path is now exposed as a named builder with ranges 4/6/7 empty, and
  the recovered source/node initializers are recorded as static helpers. The
  remaining work is alternate source-node/model-tree construction, new-file
  category/order sidecar policy, and any genuinely populated ranges 4/6/7; no
  live write is authorized by this checkpoint.
- [x] Validate the existing-record authoring path with parser round trips and
  one modern device write. The rebuilt blob retained 366 records and 309
  reachable paths, and candidate 4 was sent and read back successfully. Full
  arbitrary model-tree validation remains pending.
- [x] Require a fresh verified backup before enabling a write session. The
  offline gate verifies every object hash, the device identity, freshness, and
  dynamic-blob structure before authorizing a candidate.
- [x] Require both an explicit command-line flag and interactive confirmation.
  The gate accepts only the exact `WRITE INFOCARRY` phrase and binds the
  authorization to the candidate and backup hashes; the live sender remains
  outside the normal CLI.
- [x] Implement the ordinary segmented `0x101b` sender as a separately gated
  module. It revalidates the authorization before request 2, polls request 3
  before each bulk-OUT chunk, handles partial writes, and queries request 4
  for completion. It does not implement the unresolved unlock/`0x101d` path.
  See `src/infocarry/write_protocol.py` and `src/infocarry/transport.py`.
- [x] Add offline extraction and re-verification of a native SnoopyPro
  transaction into a prospective artifact. The `capture-artifact` command
  never modifies the native capture or accesses USB.
- [x] Cross-check a new selected-send capture against a fresh device backup.
  The selected item was `簡易マニュアル\\画面の名前とはたらき.txt`; the
  captured range-5 plus range-8 blob is byte-identical to the immediately
  following read-only backup, which now contains both the original and a
  `Copy of` record. This validates the capture pipeline but intentionally
  disqualifies the transaction from replay. See
  `analysis/phase-8-manager-test-3.md`.
- [x] Implement and test a constrained offline duplicate-existing-record
  repacker. With explicit source offsets, names, timestamps, and the observed
  metadata boundary, it reproduces the new manager blob byte-for-byte,
  including metadata/content shifts and checksum. It remains offline-only and
  does not solve arbitrary model-node or sidecar generation. See
  `src/infocarry/backup_duplicate.py` and
  `analysis/phase-8-copy-delta.md`.
- [x] Capture one genuinely disposable legacy selected-send candidate. The new
  capture contains exactly one added `IC_TEST_01.txt` record, while the
  read-only baseline contains no ordinary `0x101b` transaction. The candidate
  is preserved at `analysis/phase-8-candidate-2/`; a fresh post-send macOS
  backup is still required before any modern replay decision. See
  `analysis/phase-8-manager-test-4.md`.
- [x] Cross-check the disposable candidate with a fresh macOS read-only backup.
  The decoded range-5 plus range-8 blob is byte-identical to the device's new
  `0x8004` object; exactly one path (`IC_TEST_01.txt`) was added and no shared
  content or record shape changed. The modern sender remains gated on explicit
  final authorization.
- [x] Normalize the disposable candidate against the fresh device state.
  The captured send carried three stale bytes in one range-1 state block; a
  new offline artifact combines the fresh `0x001b`--`0x001f` state with the
  accepted blob at `analysis/phase-8-candidate-3/`. Its offline write-gate
  authorization passes; USB transmission remains disabled.
- [x] Upload one disposable minimal record through the explicitly authorized
  modern segmented `0x101b` sender. Completion returned `0x0000`; the sender
  did not invoke `0x101d`. See `analysis/phase-8-modern-write-1.md`.
- [x] Read the device back and verify the disposable record and surrounding
  state. The post-write complete backup is byte-identical to the pre-write
  backup, including all eight objects, and contains exactly the expected
  `IC_TEST_01.txt` record.
- [x] Send the first toolkit-authored existing-record content change through
  the explicitly authorized modern writer and verify it by read-back. Candidate
  4 changed `root\\IC_TEST_01.txt`, completed with `0x0000`, preserved 366
  records and 309 reachable paths, and passed the post-write verifier. The
  expected payload-dependent changes in response `0x0024` and the `0x8004`
  length probe are now covered. See `analysis/phase-8-modern-write-2.md`.
- [x] Test offline interruption handling before supporting bulk changes.
  Failure-injection tests cover a simulated mid-write disconnect and
  cancellation after a successful chunk; both query request 4 once, never
  retry, and preserve the primary error. They do not prove device atomicity or
  physical recovery. Fixed-state authorization binding and post-write
  read-back verification are documented in
  `analysis/phase-8-write-hardening.md`; physical recovery remains open under
  R15.
- [ ] Add restore support only after ordinary writes are reliable.

Constrained-write gate: satisfied on 2026-08-21. The normalized disposable
candidate was sent through the guarded modern `0x101b` path, completed with
`0x0000`, and the post-write complete backup was byte-identical to the
pre-write backup. A second toolkit-authored existing-text change was also sent
and verified by read-back. This does not satisfy the general new-file, delete,
or restore gates.

User checkpoint: satisfied on 2026-08-21 with the exact phrase
`WRITE INFOCARRY`; retain the same checkpoint for every future device-changing
operation.

## Phase 9 — Build the Desktop Workflow

- [x] Add an offline backup inventory with reachable paths, states, sizes, and
  hashes; reports refuse overwrite and contain no payload bytes.
- [x] Add an offline text-preview command with strict UTF-8 input, CRLF
  normalization, CP932 validation, optional capacity limits, and no-device
  safety declarations. See `analysis/phase-9-offline-workflow.md`.
- [x] Add a framework-independent desktop workflow model and optional Tk shell
  for loading backups, selecting records, previewing text, and saving reports;
  device-write controls are absent. See `src/infocarry/desktop.py`.
- [x] Prototype a simple connection and device-status view. The offline shell now
  includes a VID/PID-only **Check device** action; it never claims an interface
  or sends an application command. The system Tk 8.5 rendering path is not
  suitable for release.
- [x] Select and pin a supported macOS GUI/runtime stack, replacing the
  deprecated system Python 3.9/Tk 8.5 prototype path. The approved stack is
  Tkinter/ttk on Python 3.12.13 with Tcl/Tk 9.0; the runtime guard rejects the
  old system environment. See `analysis/phase-9-gui-runtime-and-integration.md`.
- [x] **v0.1 foundation:** Provide one-click backup with visible destination, progress,
  cancellation, and verification result.
- [x] **v0.1 foundation:** Provide a clear folder browser and selected-file/folder
  download/export.
- [x] **v0.1 foundation:** Provide useful recovery instructions for disconnects, timeouts,
  malformed backups, permission problems, and insufficient disk space.
- [x] **v0.1 safety boundary:** Keep all device-write controls absent. The
  non-technical usability test and limited-audience hobby release gate are
  complete.
- [x] **Offline authoring foundation:** integrate strict CP932/CRLF authoring,
  deterministic logical pagination, and a dependency-free 240 x 320 / 1-bit
  BMP serialization boundary without device access. Font-backed rasterization
  and EPUB/MOBI parsing remain explicitly pending.
- [x] **v0.2:** Preview the exact existing-text replacement, including target
  path, record offset, encoding conversion, source and encoded sizes, native
  prefix preservation, capacity checks, and unsupported-character warnings.
- [x] **v0.2:** Automatically make and verify a fresh backup before transfer.
- [x] **v0.2 offline gate:** Require an exact operation-specific confirmation
  phrase for the selected existing-text replacement.
- [x] **v0.2 offline gate:** Report bounded payload-byte progress from the
  isolated authorized sender, with finite limits and no retry behavior.
- [x] **v0.2 offline gate:** Run the existing complete post-write read-back
  verifier after one send and make verification failure terminal.
- [x] **v0.2 offline gate:** Preserve and render the complete read-back result
  with separate fixed-state, dynamic-content, and unrelated-object checks;
  incomplete results remain a no-retry failure.
- [x] **v0.2 guarded workflow:** Connect the existing-text sequence to an
  explicit GUI action with fresh before/after backups, exact phrase entry,
  bounded cancellation/progress, and terminal recovery messages. The callback
  is covered by fake-transport tests; no live GUI compatibility is claimed yet.
- [x] **v0.2 release gate:** Run one approved live GUI replacement of an
  existing TXT record and preserve the complete before/after evidence.

v0.1 exit gate: a non-technical user can detect, back up, browse, and download
content without the CLI and without any possibility of changing device data.

Milestone B offline evidence (2026-08-22): the canonical `.venv` uses Python
3.12.13 with Tcl/Tk 9.0 and pinned PyUSB 1.3.1; `python -m unittest discover
-s tests -q` passes all 199 tests (the original 188 plus focused runtime,
backup-progress, selected-export, recovery-message, ordering, and BMP-preview
tests). The test run does not access USB hardware. Together with the manual
smoke test and reproducible wheel, this satisfies the approved hobby v0.1
release profile.

Follow-up usability fixes (2026-08-22): the tree now preserves encoded
directory-child order, and the detail pane renders validated 1-bit BMP records
without adding a GUI/image dependency. The desktop now populates a Tk
`PhotoImage` through validated color rows instead of the platform-dependent
PPM data parser, which rejected both binary and ASCII image data on the
declared macOS runtime. Focused coverage now totals 199 tests, and the user
retest passed on the declared Python 3.12.13/Tk 9.0 runtime.

Source-checkout usability gate (2026-08-22): the project owner exercised
**Check device**, **New backup…**, **Open backup…**, and **Download selected…**
and reported all four working normally. Tree order and BMP preview were also
confirmed. This closes the non-technical v0.1 usability gate. The later hobby
distribution decision accepts the canonical checkout and reproducible wheel
without Developer ID signing; see
`analysis/phase-10-hobby-distribution-decision.md`.

Milestone C first offline slice (2026-08-22): `DesktopWorkflowModel` now
exposes `preview_selected_text_replacement()` for one selected existing TXT
record. It reads a local UTF-8 file, reuses strict CP932/CRLF authoring, and
reports the full target path, record offset, source character/UTF-8 byte
counts, encoded payload size, optional capacity result, and exact native-prefix
preservation. Unsupported CP932 characters, NUL, capacity overflow, malformed
targets, and unreachable/non-text records remain explicit errors. The ttk
manager adds **Preview replacement…**, which renders a clearly labeled
no-device-change summary; it does not expose the writer or save candidate
bytes. Focused model/summary tests and the complete offline suite pass: 202
tests (`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s
tests -q`). No hardware operation was performed and live compatibility is not
claimed. The next v0.2 slice is fresh-backup creation and verification before
any authorization.

Milestone C second offline slice (2026-08-22):
`capture_and_verify_fresh_backup()` now coordinates one injected read-only
capture into a new destination and immediately verifies the complete archive,
all object hashes, device identity, timestamps, and dynamic-blob structure.
Existing destinations are rejected, failed captures are preserved for review,
and no automatic retry or cleanup occurs. Fake-capture tests and the complete
offline suite pass: 204 tests. This coordinator has no USB dependency and has
not been connected to a live hardware callback.

Milestone C third offline slice (2026-08-22): `WriteTarget` and the extended
authorization record bind a future existing-text operation to the verified
device identity, manifest/blob hashes, exact record offset and path, source
payload hash, replacement payload hash, and full candidate transaction hash.
The binding is reconstructed from the no-device preview and rechecked against
both the source backup blob and candidate blob before authorization and during
revalidation. Focused authorization tests and the complete offline suite pass:
206 tests. No writer or GUI device action was enabled.

Milestone C fourth offline slice (2026-08-22): the constrained
`authorize_existing_text_replacement()` path requires the exact phrase
`REPLACE INFOCARRY TEXT`, rejects the generic confirmation phrase, and binds
the phrase to the same preview-derived target and candidate/backup hashes.
The resulting record remains authorization-only with
`usb_transmission_performed: false`. Focused gate tests and the complete
offline suite pass: 208 tests. No writer or GUI device action was enabled.

Milestone C fifth offline slice (2026-08-22): the isolated authorized sender
now accepts an optional bounded progress callback. It reports only backend-
confirmed payload bytes from 0 through the finite transaction total, and the
existing completion/cancellation/disconnect paths remain one-shot with no
automatic retry. Fake-transport tests cover monotonic progress and a finite
busy timeout with zero bulk writes. Focused protocol tests and the complete
offline suite pass: 210 tests. No live device operation or GUI write action
was enabled.

Milestone C sixth offline slice (2026-08-22): `send_and_verify()` now treats
the complete post-write backup comparison as a terminal step. A failed
read-back raises an explicit no-retry error after exactly one transport
transaction; the preserved post-write archive remains the caller's evidence
for review. Offline tests cover successful verifier integration and failed
verification without a second header or bulk transfer. The complete suite
passes: 211 tests. No live hardware operation or GUI write action was enabled.

Milestone C seventh offline slice (2026-08-22): the framework-independent
desktop model now records only a complete `PostWriteVerification` result, and
the ttk presentation helper renders the before/after backup locations plus
each independent verification check and the no-automatic-retry rule. Partial
results are rejected with recovery guidance. Focused desktop/model tests and
the complete offline suite pass: 214 tests. No upload control was added and no
live device operation was performed.

Milestone C eighth slice (2026-08-22): `ExistingTextReplacementWorkflow` now
coordinates the constrained sequence—fresh verified backup, target-bound
candidate construction, operation-specific confirmation, exactly one sender
call, fresh post-write backup, and full read-back verification—through injected
callbacks. The ttk manager exposes **Replace selected text…** only after an
offline preview and requires the exact phrase `REPLACE INFOCARRY TEXT`; errors
after a started write explicitly prohibit automatic retry. Fake workflow tests
cover successful completion, cancellation before send, phrase rejection, and
read-back failure. The complete suite passes: 219 tests. The GUI callback has
not yet been run against hardware in this checkpoint.

Milestone C live release-gate evidence (2026-08-22): the project owner ran
the guarded ttk action against the connected verified device for one existing
TXT record. The UI reported completion `0x0000`, separate before/after
backups, and passed fixed-state, dynamic-content, and unrelated-object
checks, with automatic retry disabled. The preserved archives are
`${EVIDENCE_ROOT}/live-smoke/2026-08-22/InfoCarry-write-before-20260822-110658` and
`${EVIDENCE_ROOT}/live-smoke/2026-08-22/InfoCarry-write-after-20260822-110658`. A local
read-only verification found both manifests complete, each with 8 objects and
device identity `0x054c:0x001e`. This is evidence for the constrained
existing-TXT path only; no compatibility claim is made for other models or
other write modes.

v0.2 exit gate: the same user can replace one supported existing text record
through the proven guarded path and see independent read-back verification.

## Phase 10 — Package and Release

- [x] Establish one version-controlled canonical application source tree under
  `${PROJECT_ROOT}`.
  Copy rather than move, verify hashes and tests, and preserve the current
  mirror and original evidence. See `analysis/canonical-source-migration.md`.
- [x] Separate immutable evidence, generated test output, and distributable
  application source; exclude evidence and generated output from packages.
- [x] Pin a supported Python/runtime and GUI dependency set. The canonical
  environment is Python 3.12.13/Tk 9.0 with pinned PyUSB; `pyproject.toml`
  requires Python 3.12+ and the desktop guard rejects older Tk.
- [x] Bundle or clearly install the required USB dependency. The canonical
  `.venv` installs pinned `PyUSB==1.3.1`, and the wheel declares the same
  exact dependency.
- [x] Produce an interim reproducible Python wheel and verify its installed
  CLI entry point without USB access. See `analysis/phase-10-package-check.md`.
- [x] Decide the signing/notarization policy. It is not required for the
  approved limited-audience hobby release and must be reopened before broader
  public distribution. See `analysis/phase-10-hobby-distribution-decision.md`.
- [x] Document the verified VNW-V15 model, current macOS/Tk test environment,
  backup workflow, recovery steps, known limitations, and troubleshooting.
  See `docs/USER_GUIDE.md`.
- [x] Run 199 automated offline tests plus the project owner's opt-in read-only
  GUI/device smoke test for the hobby release profile.
- [ ] Build and smoke-test a refreshed limited-audience hobby wheel after the
  core new-file/delete and later Library/Prepare workflows stabilize.
- [ ] Add Linux and Windows packaging only after the portable core is stable.

## Phase 11 — Offline Conversion Foundation

Priority note (2026-08-23): the existing conversion foundation is preserved.
Protocol and package generalization now take priority over renderer, EPUB/MOBI,
drag-and-drop, visual refinement, packaging, and signing. J.0–J.2 delivered
the local Library foundation, offline TXT Prepare, and crude ttk section in
Phase 13; device-aware planning remains deferred.

- [x] Freeze the constrained v0.2 scope after the approved live smoke and
  preserve the before/after evidence outside the source checkout.
- [x] Document a safe conversion integration boundary. The separate
  `InfoCarry-Toolkit` checkout remains read-only, and its duplicate
  `infocarry` package is not installed or imported.
- [x] Add strict UTF-8/CP932/CRLF authoring, deterministic logical page
  pagination, new-output-only conversion packages, and a validated
  dependency-free 1-bit BMP serializer in `offline_conversion.py`.
- [x] Add ttk **Text Converter**, **Ebook Renderer**, and **Settings & Help**
  tabs. They are offline-only; the Device Manager's write gates are unchanged.
- [x] **Library foundation:** delivered as Phase 13 J.0–J.2 in the sanitized
  source-of-truth commits `35f4406`, `7650aaa`, and `9dada7b`; it includes a
  versioned non-destructive catalog, picker TXT import, offline Prepare, and a
  crude ttk Library section. Drag-and-drop remains a later enhancement.
- [ ] Replace the normal-user converter-tab sequence with an outcome-oriented
  **Prepare for InfoCarry** workspace while retaining detailed controls in an
  advanced Conversion Lab; this is product polish, not the current protocol
  critical path.
- [ ] **Later renderer foundation:** select or approve a narrowly
  scoped font/image dependency, render deterministic 240 x 320 1-bit pages,
  validate BMP structure and representative glyph output, and connect preview
  and export to the canonical page model. Do not claim device compatibility
  from structural tests alone.
- [ ] **Later document import:** define one canonical offline document
  model, add EPUB import first, and evaluate MOBI separately. Preserve source
  metadata, surface unsupported content, and keep cancellation/progress free
  of USB activity.

Phase 11 first-slice evidence (2026-08-22): strict offline conversion,
deterministic page planning, the 1-bit BMP serializer, and the three ttk tabs
are covered by focused tests. The complete canonical suite passes **226
tests**. No device operation was performed and no conversion-project file was
modified. See `analysis/phase-11-offline-conversion.md`.

## Phase 12 — Prove General New-File Transfer and Selective Delete

- [x] **Milestone E — evidence gate:** complete on 2026-08-22. The evidence audit, stable preservation, and controlled owner capture are complete; the clean capture 04 synthesis closes the gate for the narrow offline model.
  - [x] Evidence audit — complete. The audit inspected the preserved
    selected-send captures, Phase 7/8 fixture reports, manager-produced files,
    complete backups, static notes, and preserved offline exports. It proves
    genuinely new TXT records, with clean capture 04 as the primary golden
    case. See `analysis/phase-12-milestone-e-evidence-matrix-2026-08-22.md`.
  - [x] Stable evidence preservation — complete. The five synchronized mirror
    roots were copied to the stable Phase 12 audit-source directory and every
    copied file was verified by size and SHA-256. See
    `analysis/phase-12-evidence-manifest-2026-08-22.json` and the stable
    manifest path recorded there.
  - [x] Controlled owner capture — complete. Capture 04 preserves an exact
    source, one native add log, independent before/after Manager snapshots,
    complete pre/post backups, exactly one new path, and no shared file-payload
    changes. The four observed Manager files are byte-identical before/after;
    this is verified negative evidence for Manager-local sidecar mutation, not
    a missing transfer artifact. See
    `analysis/phase-12-repeat-add-only-capture-evidence-04-2026-08-22.json`.
  - [x] Earlier owner captures — preserved as supporting/incomplete evidence.
    The first capture preserves an exact
    source, one native add log, before/after Manager snapshots, and complete
    pre/post backups, but its pre-add backup predates an insufficient-space
    attempt and deliberate deletions. The new record is proven, while the
    clean add-only delta and new-file sidecars remain unresolved. See
    `analysis/phase-12-owner-capture-evidence-2026-08-22.json`.
  - [x] Repeat pre/post backup preservation — complete. The owner-approved
    repeat has complete fresh pre/post backups and an offline delta proving one
    new `root\\IC_E_ADD_20260822_02.txt` path with no removed paths. The source
    and all eight-object backup manifests are hash-verified.
  - [x] Clean repeat add-only capture — complete. Capture 04 has a valid native
    log, independent before/after Manager snapshots, complete pre/post device
    backups, exactly one added path, exact range-5/range-8 to post-add blob
    equivalence, and no shared file-payload changes. Unchanged `VICMEM.bin`,
    `VICLV.bin`, and `order.vnw` are verified results; no new category or
    selection state is inferred.
  - [x] Complete Milestone E evidence gate — closed by capture 04 synthesis.
    Manager-level success is observed; `0x101b` completion `0x0000` is
    supported by existing modern replacement transactions, but its application
    to new-file addition remains a checked protocol assumption. Capacity
    interpretation and fail-closed enforcement move to Milestone F. Closure
    synthesis is committed in `e61794d`.
- [x] Owner-operated delete attempt 01 was captured separately with its own
  native USB log, before/after Manager snapshots, failure screenshot, and
  complete pre/post-attempt backups. Manager reported failure and the target
  remained present; the attempt is failure/alignment evidence only. See
  `analysis/phase-12-milestone-h-delete-attempt-01-2026-08-22.md` and the
  detailed offline comparison linked there.
- [x] **Milestone F — offline new-record model:** complete offline on 2026-08-22.
  Implemented and tested
  only one new root-level TXT candidate from a fresh validated backup, using
  the captured record template, strict CP932/CRLF authoring, safe metadata/state
  rebasing, duplicate/name validation, fail-closed capacity, deterministic
  audit hashes, and preserved unrelated records/payloads. Sidecar and
  completion behavior remains bounded by the explicit assumptions in the
  Milestone E matrix; no live or normal CLI/GUI write is enabled. First slice
  complete in `20fb6ee`; see
  `analysis/phase-12-milestone-f-offline-new-root-txt-2026-08-22.md`.
  Operation-specific identity/hash binding, exact confirmation phrase, and a
  fake-transport-only exercise are complete in `80f6e48`; the full suite is
  **242 tests**.
  Candidate-bound full read-back verification, including terminal mismatch/no
  retry behavior, is complete in `fef7339`; the full suite was **243 tests**.
  New-TXT-specific fake-transport integration and the explicit R15 outcome
  boundary are complete in `8a6166f`; the combined offline checkpoint passes
  **263 tests**. Duplicate targets, invalid names/CP932, embedded NULs,
  complete-size capacity refusal, malformed backups, state rebasing,
  unrelated-byte preservation, and deterministic hashes remain covered by the
  pure-builder tests rather than being misrepresented as transport failures.
- [x] **Milestone G — guarded new TXT creation:** complete for the narrow
  guarded scope on 2026-08-22. Commit `1aa4ccb` adds the framework-independent
  workflow and nine focused tests for UTF-8 source intake, hash-only preview,
  fresh injected-backup verification, immediate binding revalidation, exact
  phrase, bounded progress, one-shot fake send, terminal failures, and
  complete fake read-back. The workflow reports previewed/authorized/
  simulated/read-back/failed and post-start-indeterminate states.
- [x] One separately approved live modern new-TXT smoke completed on 2026-08-22
  using `root\\IC_G_LIVE_20260822_01.txt`. The fresh pre-add backup, exact
  candidate binding, one `0x101b` transaction, completion `0x0000`, complete
  post-add backup, exact candidate blob match, one-added/no-removed path delta,
  fixed-state match, and unrelated-object preservation are recorded in
  `analysis/phase-12-milestone-g-live-new-root-txt-smoke-2026-08-22.md`.
  The normal GUI/CLI action remains disabled; this is not broad compatibility
  or interrupted-write recovery proof.
- [x] **Milestone H — selective delete:** the narrow offline safety gate and
  legacy deletion-effect evidence gate are complete. Attempt 01 remains
  preserved failure evidence: Manager reported failure and its modern-created
  target remained. Attempt 02 against legacy-created
  `root\\IC_E_ADD_20260822_04.txt` has a complete pre/post backup pair, one
  isolated native `0x101b` transaction, exact native candidate/post
  dynamic-blob equality, record count 368 to 367, exactly one removed target,
  no added path, no shared payload changes, and byte-identical observed
  Manager sidecars. The supplied result image shows `_04` absent from the
  device preview. Missing Manager success wording and the unavailable native
  request-4 result are documented limitations; no further legacy capture is
  required. The transmitted `0x001d` form is preserved as the narrow observed
  delete-specific transient (`count=0`, `value_04=1`, empty offsets), while
  the stable post-backup form is (`count=0`, `value_04=0`, empty offsets).
  The attempt-02 synthesis and verified evidence hashes are recorded in
  `analysis/phase-12-milestone-h-delete-attempt-02-2026-08-22.md`; the stable
  evidence root is
  `${EVIDENCE_ROOT}/phase-12-milestone-h-delete-attempt-20260822-02/`.
  Commits `b5bae4b` and `c8162c0` add the narrow offline attempt-02 builder,
  exact binding, independent verifier, and delete-specific fake-transport
  failure coverage. The complete canonical suite is **283 tests** (279 at the
  H closure checkpoint). This closes
  Milestone H for its offline scope; physical atomicity/recovery remain
  unproven, and modern delete plus product exposure remain prohibited pending
  separate approval. Milestone H.1 is blocked and parked because the current
  builder still requires the opaque attempt-02 timestamp map and
  capture-specific fixed-state blocks. I.7–I.10 have completed their defined
  offline logical characterization slices and do not depend on deletion; H.2
  remains a separate fail-closed offline track.
- [ ] **Milestone H.1 — live-delete generalization and readiness:** blocked and
  parked pending new independent evidence. The metadata `+0x0c` generation rule
  and fresh fixed-state derivation remain unresolved; no speculative deletion
  work, live-delete protocol, modern delete, normal GUI/CLI delete, or other
  device-changing command is authorized. Do not request another capture
  automatically. The fail-closed readiness result is in
  `analysis/phase-12-milestone-h1-live-delete-readiness-2026-08-23.md` and the
  four focused readiness tests keep the suite at **283 tests**.
- [ ] **Milestone I — prepared content package:** I.0–I.10 are complete for
  their defined offline scopes, independent of H.1. I.0's evidence audit is complete in `5a3c55b` at **286
  tests**; I.1's logical package model is complete in `0db6593` at **291
  tests**; I.2's blocked transfer preview is complete in `05e29cb` at **294
  tests**. Owner-approved capture 7 now satisfies the exact one-folder/one-TXT
  legacy evidence gate. Commit `139c658` adds the machine-readable evidence
  synthesis and offline three-record golden builder; commit `465120f` adds
  template-integrity and boundary hardening with ten focused tests. The suite
  is **301 tests**. The builder reproduces capture 7 exactly only
  with an explicit captured timestamp map; arbitrary folder creation, fresh
  fixed-state derivation, request-4 completion decoding, live package
  eligibility, and normal GUI/CLI package action remain blocked. Native
  ordinary-worker total-limit capacity semantics were resolved separately in
  Milestone I.5; the Manager UI mapping and live package eligibility remain
  separate questions.
  The execution protocol and evidence are recorded in
  `analysis/phase-12-milestone-i-folder-package-capture7-20260823.md` and
  `analysis/phase-12-milestone-i-folder-package-capture7-20260823.json`.
  The read-only timestamp/fixed-state comparison is recorded in
  `analysis/phase-12-milestone-i-timestamp-fixed-state-comparison-20260823.md`;
  it establishes no general fresh-backup rule. I.7's portable evidence matrix,
  fail-closed readiness result, and unexecuted owner procedure are recorded in
  `analysis/phase-13-milestone-i7-timestamp-fixed-state-evidence-20260823.json`
  and `analysis/phase-13-milestone-i7-timestamp-fixed-state-characterization-20260823.md`;
  the I.7 slice adds five focused tests and reaches **384 tests**. I.8's
  ordered source-bound multiple-TXT logical model is complete offline in
  `src/infocarry/prepared_multi_text.py`, with nine focused synthetic tests;
  the suite reaches **393 tests**. Exact multi-record device construction,
  timestamp/fixed-state generalization, capacity authorization, and USB
  operation remain blocked. I.9 is now the next active offline slice.
- [x] **Milestone I.4 — constrained modern one-folder/one-TXT package safety
  gate:** complete for the constrained offline/fake-only scope. This is
  deliberately distinct from legacy
  timestamp reconstruction: preserve every existing timestamp, require one
  explicit frozen Unix timestamp for the new folder, leading `..` marker, and
  TXT child, accept only exact capture-7-compatible all-zero fixed state, and
  assign no category, mark, bookmark, selection, history, or Manager-side
  sidecar membership. The scope is exactly one root folder with one TXT child;
  live package transfer, normal GUI/CLI package action, arbitrary folders,
  multiple children, bitmap pages, nested folders, rename, delete, and
  synchronization remain prohibited until this gate and a separate approval
  pass. The candidate-policy slice is complete in `9287c06`, exact
  capture-7-compatible fixed-state preflight is complete in `39c6f9f`, and
  fail-closed complete-growth capacity/conflict checking is complete in
  `a3bff5a`; the suite is **313 tests**. The candidate revalidates source
  bytes, preserves verified state bytes, binds the explicit timestamp in its
  audit, and constructs no USB authorization or transport. Package-specific
  authorization binding is complete in `216f49e`; it binds the exact device,
  backup, source/package, paths, timestamp, fixed-state hashes, capacity,
  candidate, transaction, and phrase. The independent read-back verifier is
  complete in `36f7024`; it requires completion `0x0000`, exact candidate
  bytes, the two authorized added paths, preserved shared content/timestamps,
  exact fixed state, and unchanged unrelated backup objects, with terminal
  no-retry recovery guidance. The suite is **323 tests**. The fake-only
  guarded workflow and its failure coverage are complete in `3da2180`; it
  requires an explicit fake-transport assertion, rebuilds from a fresh backup,
  sends at most once, and classifies post-start interruption as indeterminate.
  The suite is **329 tests**. The unexecuted owner protocol is
  `analysis/phase-12-milestone-i4-unexecuted-modern-package-smoke-protocol-20260823.md`;
  preparing it is not approval. Physical transport proof and live eligibility
  remain open, and no package action is exposed in the normal GUI/CLI.
- [x] **Milestone I.5 — legacy capacity semantics (offline):** complete for
  the native ordinary-worker capacity meaning. Static data flow in the
  preserved `VicTwo.dll` proves that `0x0019` response `+0x08` populates
  worker context `+0x24`, and the dispatcher checks prospective `N+M` against
  that total model limit. The Manager `+0x528`/`+0x52c` display is recorded as
  separate Manager-local used/total KB accounting; command `0x0024` is observed
  to equal the current dynamic-model length and excluded from capacity
  authorization; broader semantics unresolved. Unknown `field_14_be32` is not
  treated as capacity. Commit `9657e85`
  adds explicit total-limit, baseline-model, candidate-model,
  growth/remaining-growth, and source fields to the package candidate and
  authorization. Boundary, malformed-evidence, inconsistent-length, and
  capacity-binding tests bring the complete suite to **336 tests**. See
  `analysis/phase-12-milestone-i5-capacity-semantics-20260823.md` and its JSON
  companion. This does not authorize a live package write or package GUI/CLI
  action; physical transport, package completion, and interrupted-write
  recovery remain unresolved.

- [x] **Milestone I.6 — controlled package live-smoke readiness:** complete
  for the constrained one-folder/one-TXT policy. Commit `09452be` added the
  native parsed `0x0019` capacity evidence, binding VID/PID, raw response and
  SHA-256, command, `+0x08`, the 3,145,728-byte total limit,
  baseline/candidate model bytes, growth, and remaining growth. Attempt 02
  used a new non-overwriting evidence root, one exact `0x101b` transaction,
  completion `0x0000`, and a complete post-operation backup. The preserved
  post-operation backup exactly matches the authorized candidate, adds only
  the authorized folder and TXT child, preserves all shared records/payloads/
  prefixes/timestamps and fixed-state objects, and changes only the expected
  payload-dependent `0x0024` and `0x8004` probe objects. The initial terminal
  audit remains preserved; commit `cf7803b` corrected the package verifier's
  boundary and independent offline re-verification passed. The complete suite
  is **360 tests**. See
  `analysis/phase-12-milestone-i6-package-live-smoke-attempt-02-result-20260823.md`.
  Arbitrary packages, interrupted-write recovery, and normal GUI/CLI package
  action remain prohibited.

### Protocol generalization sequence — I.7 through I.10 and H.2

- [x] **Milestone I.7 — timestamp and fixed-state characterization:** offline
  characterization complete as a fail-closed negative result. Inventory portable evidence for metadata timestamps, display
  history, mark lists, bookmarks, metadata-relative offsets, and fixed-state
  rebasing. Classify each result as byte-verified, independently observed,
  single-capture observed, inferred, or unresolved. Unsupported timestamp or
  state rules fail closed; no live operation is authorized by this milestone.
  The matrix, analysis, and unexecuted owner procedure are recorded in
  `analysis/phase-13-milestone-i7-timestamp-fixed-state-evidence-20260823.json`
  and `analysis/phase-13-milestone-i7-timestamp-fixed-state-characterization-20260823.md`.
  The later approved disposable-record state experiment separately verified
  bounded display-history, Mark-1, and Bookmark-1 transitions without closing
  the general timestamp or fresh-state rule; see
  `analysis/phase-13-milestone-i7-state-experiment-20260824.md`.
- [x] **Milestone I.7 controlled legacy add experiment — attempt 01:** the
  separately approved `I7-LEGACY-ADD-01` was completed once through the
  legacy Manager and independently verified from complete pre/post backups.
  The native capture contains one ordinary `0x101b`; the model changes from
  373 to 374 records and adds exactly `root\\IC_I7_CLOCK_01.txt` with the
  exact 1,863-byte source payload. All 314 shared timestamps changed, while
  all five fixed-state objects remained byte-identical all-zero state. The
  Manager preview shows the new item, but explicit success wording and a
  trustworthy request-4 completion decode were not preserved. The full
  synthesis is in
  `analysis/phase-13-milestone-i7-legacy-add-01-results-20260823.md` and its
  JSON companion. This closes the add evidence gate only; it does not resolve
  general timestamp/nonzero-state construction or authorize deletion. The
  suite remains **429 tests** with three intentional skips. The timestamp
  tool/validator slice is preparation-only. The harmless Windows dry run
  passed, followed by the separately approved display-history, Mark-1, and
  Bookmark-1 state experiment on the disposable record. Its raw evidence is
  local-only and its synthesis is recorded in
  `analysis/phase-13-milestone-i7-state-experiment-20260824.md`; deletion was
  separately gated and is now synthesized below.
- [x] **Milestone I.7 controlled legacy stateful deletion observation — attempt
  01:** the separately approved deletion of `root\\IC_I7_CLOCK_01.txt` is
  verified from complete pre/post backups, one isolated native `0x101b`, and
  complete Manager BEFORE/AFTER files. Exactly one path was removed, no path
  was added, all 255 surviving file payloads were byte-identical, the three
  active target references were cleared, and the native range-5 plus range-8
  candidate exactly matched the post-delete dynamic blob. All 314 shared
  timestamps were regenerated; the causal rule and request-4 completion remain
  unresolved. This closes only the one captured persisted-effect boundary and
  does not authorize generalized or modern deletion. The sanitized synthesis
  is `analysis/phase-13-milestone-i7-legacy-delete-20260825.md`; the suite is
  **435 tests** with three intentional skips.
- [x] **Milestone I.8 — multiple-TXT package:** the logical model now supports
  at least two explicitly ordered TXT children with strict authoring, conflict
  rejection, source/payload hashes, lower-bound growth accounting, and
  non-overwriting export. It remains offline and disconnected from normal
  CLI/ttk controls; exact multi-record construction, capacity authorization,
  independent device read-back, and fake transport are blocked pending the
  relevant native evidence. Nine focused synthetic tests bring the suite to
  **393 tests**. See
  `analysis/phase-13-milestone-i8-multiple-txt-offline-20260823.md`.
- [x] **Milestone I.9 — mixed TXT/BMP package:** add a typed ordered offline
  model for strict synthetic TXT and validated 237×320 one-bit Windows BMP
  items, preserving order, hashes, geometry, and source safety. Exact native
  wrappers, candidate/capacity/authorization/read-back construction, and
  fake-transport coverage remain blocked without the relevant evidence; live
  eligibility is not claimed. Nine focused tests bring the suite to **402
  tests**. See `analysis/phase-13-milestone-i9-mixed-txt-bmp-offline-20260823.md`.
- [x] **Milestone I.10 — representative small ebook package:** define the
  smallest flat manifest-driven plan supported by the typed offline builders,
  preserving order, paths, hashes, growth, capacity fields, timestamp and
  fixed-state policy, and expected read-back path delta. Nested folders are
  rejected rather than flattened because their native construction is not
  proven. Six focused tests bring the suite to **408 tests**. See
  `analysis/phase-13-milestone-i10-ebook-plan-offline-20260823.md`.
- [ ] **Milestone H.2 — deletion generalization:** the captured legacy effect
  is complete and the offline modern generalization/hardening gate is complete
  for its supported structural scope. One constrained modern live smoke has
  now passed; broader live eligibility remains unproven.
  Commits `2145360`, `83a5b41`, `b746347`, `7f9d417`, and `1ddaffc` add
  the one-existing-ordinary-TXT model, provisional surviving-timestamp
  preservation, fail-closed fresh-state derivation, exact binding, independent
  read-back, and fake-only failure workflow. The model accepts exact all-zero
  state or only proven target-reference clearing forms; it rejects unfamiliar
  nonzero state, unresolved references, malformed records, unsupported record
  types, nonzero/ambiguous completion, and any retry. Commits `6537649` and
  `f0ea7e7` correct the parent-marker relation and leave zero unexplained
  non-timestamp differences after masking only surviving timestamp fields and
  the derived header checksum. The suite is **483 tests** with three
  intentional skips. Timestamp generation, trustworthy legacy request-4
  completion, and physical interrupted-write recovery remain unresolved; a
  live modern adapter remains isolated and normal product deletion remains
  prohibited. See
  `analysis/phase-13-milestone-h2-offline-generalized-delete-20260825.md`,
  `analysis/phase-13-milestone-h2-offline-delete-hardening-20260826.md`, and
  the unexecuted owner-review boundary in
  `analysis/phase-13-milestone-h2-modern-live-smoke-readiness-dossier-20260826.md`,
  the earlier blocker
  `analysis/phase-13-milestone-h2-delete-generalization-blocker-20260823.md`.

The owner-provided external source library may be used only in ignored local
exploration. Tracked tests use synthetic data, generated fixtures, hashes, and
structural summaries; copyrighted text, images, manifests, and excerpts are
not copied into this repository.

Phase 12 is the active project priority. A crude engineering UI or CLI is
acceptable for proving each gated primitive. Do not spend the critical path on
artwork, visual polish, advanced profiles, broad packaging, or unneeded format
support.

Milestone E closure result (2026-08-22): the canonical `.venv` suite passes
exactly **226 tests** at the `b924605` evidence checkpoint. Clean capture 04
has one complete `0x101b` transaction whose range-5 plus range-8 bytes exactly
match a fresh complete post-add backup containing exactly one new TXT record.
Its four observed Manager files are independently hash-verified and
byte-identical before/after Send Selected; `order.vnw` already contained the
basename before the transfer. This is a verified negative result for
Manager-local sidecar mutation, not missing transfer data. Device-resident
fixed state is kept separate: established record offsets may be rebased, but
no new category, mark, bookmark, selection, or sidecar membership is invented.
Manager-level success is observed; `0x101b` completion `0x0000` is supported by
existing modern replacements, while its new-add application remains a checked
assumption. Capacity interpretation and fail-closed enforcement move to
Milestone F. No source code, normal CLI/GUI new-file control, USB transport, or
hardware state was changed.

Owner capture result (2026-08-22): the owner supplied one later successful
legacy send capture. The exact source, native log, four-file Manager snapshots,
and complete pre/post backups are preserved under the evidence root recorded in
`analysis/phase-12-owner-capture-evidence-2026-08-22.json`. Offline parsing
finds one ordinary `0x101b` transaction and the new
`root\\IC_E_ADD_20260822_01` path. The owner reports that an earlier transfer
failed for insufficient space, then three files were deliberately deleted
before the successful send was captured. The post-add backup consequently
contains those intentional removals and an unresolved change to
`root\\IC_TEST_01`; all four Manager sidecars are byte-identical before and
after and contain no new-file path. This capture is preserved as supporting
evidence; capture 04 is the clean closure case.

Repeat add-only attempt result (2026-08-22): the owner-approved repeat has
complete, hash-verified pre/post backups. Offline parsing finds exactly one
added `root\\IC_E_ADD_20260822_02.txt` path, no removed paths, a 53-byte payload
whose SHA-256 matches the preserved source, and no shared file-payload changes.
SnoopyPro did not capture packets, and no after-send Manager snapshot or
sidecars were supplied, so this is preserved as an incomplete attempt and does
not close Milestone E. Do not delete the disposable record; deletion remains a
separate later gate. See
`analysis/phase-12-repeat-add-only-attempt-2026-08-22.json`.

Repeat add-only attempt 03 result (2026-08-22): the owner preserved complete,
hash-verified pre/post backups, but SnoopyPro targeted the root hub rather than
`USB\\Vid_054c&Pid_001e`; no usable native log or Manager snapshots were
captured. Offline parsing nevertheless finds exactly one added
`root\\IC_E_ADD_20260822_03.txt` path, no removed paths, a 53-byte payload
matching the preserved source, and no shared file-payload changes. This attempt
is preserved as supporting evidence. The next source was prepared as
`IC_E_ADD_20260822_04.txt`; do not delete the existing disposable records. See
`analysis/phase-12-repeat-add-only-attempt-03-2026-08-22.json`.

Repeat add-only capture 04 result (2026-08-22): the owner supplied a valid
native log, independent before/after Manager snapshots, and complete device
pre/post backups. Offline parsing finds exactly one added
`root\\IC_E_ADD_20260822_04.txt` path, no removed paths, a 53-byte payload
matching the preserved source, and no shared file-payload changes. The native
range-5 plus range-8 bytes exactly match the post-add device blob. The
Manager-side `VICMEM.bin` and `VICLV.bin` are byte-identical and contain no new
path; `order.vnw` is also byte-identical and already lists the basename in both
snapshots. The unchanged sidecars are a verified result. This closes Milestone
E; the narrow offline generator, state rebasing, fail-closed capacity, and
checked completion handling are active in Milestone F. See
`analysis/phase-12-repeat-add-only-capture-evidence-04-2026-08-22.json`.

Milestone F first offline construction result (2026-08-22): commit `20fb6ee`
adds the narrow root-level TXT candidate builder and 12 focused new-TXT tests;
the complete canonical suite passes **238 tests**. The builder starts from a
fresh validated complete backup, reuses the captured record template, applies
strict CP932/CRLF authoring, calculates allocation and alignment before the
capacity check, fails closed on ambiguous capacity, rebases only established
fixed-state record references, preserves unrelated records and payloads, and
emits a deterministic offline audit. Capture 04 is reproduced exactly when
its observed timestamp map is supplied; otherwise only timestamp differences
and their checksum consequence are permitted by normalized comparison. No
source backup, evidence, device, normal CLI, or GUI was modified.

Milestone F closure result (2026-08-22): commit `8a6166f` adds 11 focused
new-TXT fake-transport integration tests and an explicit R15 failure
assessment. Cancellation before request `0x02` is ordinary safe cancellation;
after the request begins, disconnect, timeout, cancellation, or missing
completion is indeterminate, preserves the primary error, permits only later
read-only diagnosis/backup, and never retries. Nonzero completion is terminal
known failure with no retry. The combined complete offline suite passes **263
tests**. This is simulated transport evidence only and does not prove physical
atomicity or recovery. Milestone F is closed offline; Milestone G remains
offline/fake-only and the normal new-file controls remain disabled.

Milestone G initial offline workflow result (2026-08-22): commit `1aa4ccb`
adds the hash-only preview and injected fresh-backup → exact authorization →
fake send → complete read-back model. Nine focused tests pass and the complete
canonical suite remains at **263 tests**. It accepts one UTF-8 TXT source and
one root-level `.txt` destination, never serializes candidate bytes into the
preview, and preserves the explicit no-live-transport boundary. Milestone G
was initially offline/fake-only; the separate live-smoke result below closes
the narrow guarded workflow while keeping the normal GUI/CLI action disabled.

Milestone G controlled live smoke result (2026-08-22): the owner separately
approved one live modern new-TXT smoke. The exact bound source,
`root\\IC_G_LIVE_20260822_01.txt` target, fresh pre-add backup, candidate blob,
and transaction hashes are recorded in
`analysis/phase-12-milestone-g-live-new-root-txt-smoke-2026-08-22.md`. The
sender completed exactly one `0x101b` transaction with `0x0000`; a complete
post-add backup matched the candidate dynamic blob byte-for-byte, fixed state
matched, all unrelated backup objects were unchanged, and path parsing found
exactly one added path with no removals. The suite remains **263 passing
tests**. This is verified live evidence for one supported device and one
root-level TXT shape only; R15 remains open, delete is separate, and the
normal GUI/CLI new-file action remains disabled. The documentation update is
committed in `3dcf5e7` (`Record approved live new TXT smoke`).

Milestone H preparation result (2026-08-22): the deletion evidence audit found
no isolated legacy delete log, complete before/after delete backup pair,
Manager-side before/after snapshot pair, delete completion evidence, or
modern delete proof. Existing synthetic leaf-delete and exact `VICMEM`/
`VICLV` path helpers remain useful offline invariants but do not establish the
native operation. The audit and minimal owner-operated capture procedure are
recorded in
`analysis/phase-12-milestone-h-deletion-evidence-audit-2026-08-22.md` and
`analysis/phase-12-legacy-delete-capture-protocol-2026-08-22.md`. No device
mutation was performed; the normal CLI/GUI remains deletion-disabled and the
suite remains **263 passing tests**.

Milestone H owner capture 01 result (2026-08-22): the owner supplied one
standalone SnoopyPro log, before/after Manager snapshots, a failure screenshot,
and complete pre/post device backups. Manager displayed “data transmission
failed,” and the owner observed an empty Manager preview. The post-attempt
backup nevertheless retains `root\\IC_G_LIVE_20260822_01.txt`; the dynamic blob
is byte-identical before/after, and no device path or shared payload changed.
The native log contains a deletion-shaped candidate that removes the target.
The initial helper was 4 bytes longer because it used a different alignment
and padding rule. The refined offline helper in `d203ad0` now matches the
native candidate's length and structure; after copying the native timestamp
fields for comparison, its bytes are identical. Its fixed state mostly
matches an explicit metadata-reference rebase of the fresh pre-delete state,
with one unresolved two-byte field in `0x001e`; it is not classified as merely
stale. The four Manager sidecars are byte-identical before/after. This is
preserved as failure/alignment evidence, not successful delete proof. See
`analysis/phase-12-milestone-h-delete-attempt-01-2026-08-22.md`. No retry or
modern delete was performed; the detailed comparison is in
`analysis/phase-12-milestone-h-offline-analysis-2026-08-22.md`; the suite
now passes **264 tests** after the offline refinement.

Milestone H owner capture 02 result (2026-08-22): the owner supplied a
corrected capture layout with the actual nested `ICM/転送元フォルダ/order.vnw`
path, one native `0x101b` transaction, and a complete post-delete backup after
deleting the legacy-created `root\\IC_E_ADD_20260822_04.txt`. The native
range-5 plus range-8 candidate is byte-identical to the post-delete dynamic
blob. The pre/post record count is 368 to 367, exactly `_04` is removed, no
path is added, and all shared file payloads are unchanged. `VICDATA.bin`,
`VICMEM.bin`, `VICLV.bin`, and the correctly nested `order.vnw` are
byte-identical before/after; the unchanged `order.vnw` still contains `_04`
and is treated as Manager-local bookkeeping rather than a required device
state mutation. The native `0x001b`, `0x001c`, `0x001e`, and `0x001f` fixed
responses match the post-backup responses. Native `0x001d` has
`value_04=0x0001`, while the post-backup response has `value_04=0x0000`;
the field's meaning is unresolved. The supplied image shows the target absent
from the Manager device preview. Explicit Manager success wording and a
trustworthy legacy request-4 completion word remain unavailable limitations;
they do not invalidate the independently verified persisted result or justify
another capture. The native `0x001d` form is retained in the candidate as the
narrow observed transient (`count=0`, `value_04=1`, empty offsets), while the
stable post-backup form is (`count=0`, `value_04=0`, empty offsets). This
  closes the persisted legacy deletion-effect evidence gate. The offline
  delete builder, exact binding, failure model, and independent verifier are
  complete in `b5bae4b` and `c8162c0`; the complete Milestone H heading is
  checked for this narrow offline scope. The complete synthesis, stable paths,
  and hashes are recorded in
  `analysis/phase-12-milestone-h-delete-attempt-02-2026-08-22.md`; the full
  canonical suite passes **279 tests**. Physical atomicity/recovery remain
  unproven and modern delete remains prohibited pending separate approval.

## Phase 13 — Integrate Library, Prepare, and Staged Transfer

- [x] **Milestone J.0 — non-destructive local Library foundation:** add a
  versioned catalog for one original local UTF-8 TXT source, with stable
  identity/hash tracking, stale/missing detection, atomic recoverable writes,
  and catalog-only removal. Complete in `35f4406`; the suite passes **373
  tests** with three intentional evidence-dependent skips. The catalog is
  outside the checkout and reverse-engineering evidence.
- [x] **Milestone J.1 — offline Prepare workflow:** connect one supported TXT
  Library item to the proven `PreparedTextPackage` model without USB access,
  preserving strict encoding, naming, hashes, and no-device-change reporting.
  Complete in `7650aaa`; the suite passes **378 tests** at this slice.
- [x] **Milestone J.2 — crude local Library/Prepare ttk foundation:** the
  versioned non-destructive catalog, strict offline Prepare workflow, and
  file-picker-based Library section are complete in `35f4406`, `7650aaa`, and
  `9dada7b`; the suite passes **379 tests** with three intentional
  evidence-dependent skips. The catalog is per-user and outside the checkout;
  the UI has no package-transfer action.
- [ ] **Milestone J.3 — device-aware Library transfer planning:** after the
  relevant I.8–I.10/H.2 operation gates close, add a framework-independent
  preview/queue model that binds selected prepared items to proven operations,
  conflicts, capacity, and verification. Do not expose device transfer yet.
- [ ] Add a framework-independent offline transfer plan containing selected
  Library items, prepared artifacts, intended destinations, operation type,
  compatibility state, conflicts, per-item size, total size, and capacity
  result.
- [ ] Support **Transfer selected** and **Transfer all ready items** as queue
  construction and review actions. Keep every unsupported/new-record operation
  disabled and explain the missing evidence gate.
- [ ] Execute only mappings proven by Phase 12: existing-TXT replacement,
  guarded new TXT, selective delete, and later prepared-package operations as
  each gate closes. Batch execution remains blocked by R14 until every queued
  operation is individually proven.
- [ ] For any later enabled batch: create one fresh verified backup, bind exact
  authorization to the complete plan, stop on first failure, never retry
  automatically, and independently verify every committed item.
- [ ] After the crude functional path works, evolve the ttk shell toward the
  approved Concept A structure: local
  Library, content/selection workspace, persistent Device Bay, collapsible
  System Console, status bar, and optional Geek Mode. Preserve keyboard access
  and current safety controls; do not block functionality on final artwork.
- [ ] Use structured semantic events across preparation, device state,
  transfer, verification, and diagnostics. Critical warnings remain visible
  outside Geek Mode, and routine success does not require a modal dialog.
- [ ] **Milestone K — integrated hobby release:** test representative Library,
  Prepare, queue-preview, and proven-transfer workflows; refresh user guidance
  and compatibility claims; build and smoke-test a new wheel; retain the
  deferred signing policy.

The UI/UX handoff review and reconciled acceptance boundaries are recorded in
`analysis/ui-ux-handoff-review-2026-08-22.md`.

## Current Next Actions

1. Keep the constrained P15-001 modern dossier at
   `READY_FOR_HARDWARE_TEST`; obtain separate operation-specific owner approval
   before any modern hardware test, then recapture a fresh complete backup and
   revalidate every exact binding immediately before a possible send.
2. Preserve the validated I7 deletion intake, complete pre/post backups,
   transaction artifact, Manager snapshots, timestamp logs, and derived
   reports under the external evidence root; never add them to Git.
3. H.2's corrected normalized offline structural gate and one constrained
   modern root-level TXT deletion smoke are complete for their exact scopes:
   surviving timestamps are preserved by policy, the relation-based
   parent-marker rule leaves zero unexplained non-timestamp differences against
   the preserved I7 result, and the smoke completed with `0x0000` and full
   read-back. Keep generalized deletion, physical recovery, and broader state
   compatibility unresolved.
4. Keep I.8–I.10 multi-child device candidates, J.3 transfer planning, normal
   GUI/CLI package/delete controls, and all broad or interrupted-write
   operations blocked until their separate evidence gates close.
5. Push every verified sanitized commit normally to `origin/main` after the
   required focused tests, full suite, diff check, and excluded-content audit.

## Decisions

- Use user-space libusb instead of developing a macOS kernel driver.
- Use Python/PyUSB for protocol discovery and the first working client.
- Deliver a CLI before building a GUI.
- Treat read-only backup as the first useful release.
- Keep write support behind a separate safety gate and automatic backup.
- Treat live writes as experimental until `0x101b` commit atomicity and
  interrupted-write recovery are proven; do not deliberately interrupt the
  owner's only valuable unit.
- Preserve original files and raw device responses indefinitely.
- Build safe selected-file workflows rather than copying the legacy Manager's
  destructive send-all/receive-all behavior.
- Prioritize functional legacy-Manager parity—new content creation, selective
  transfer, and selective removal—before aesthetic refinement. Early UI may be
  crude if safety state and consequences remain clear.
- Use Tkinter/ttk on the approved Python 3.12.13/Tk 9.0 runtime. Do not build
  the local browser interface or migrate to Qt/PySide at this stage. Keep the
  conversion project read-only until its duplicate `infocarry` namespace is
  integrated deliberately. See
  `analysis/phase-9-gui-runtime-and-integration.md`.

## Next Milestone Summary (2026-08-22)

1. **Completed foundation:** USB protocol mapping, modern detection, repeatable
   complete backups, deterministic lossless export, native selected-send
   capture analysis, and a guarded existing-text write with read-back proof.
2. **Milestone A — project control:** completed. The canonical source tree is
   version-controlled, verified, and the original mirror/evidence are
   preserved. The supported GUI/runtime decision is now approved and recorded.
3. **Milestone B — v0.1 read-only product:** the ttk foundation now integrates
   connection status, one-click verified backup, hierarchical browse, selected
   download/export, progress/cancellation, and recovery guidance. Offline
   regression, source-checkout usability, and the approved limited-audience
   hobby delivery are complete.
4. **Milestone C — v0.2 selected upload:** complete. The proven existing-text
   path now has automatic backup, preview, authorization, progress, and
   independent live read-back evidence.
5. **Milestone D — offline conversion foundation:** first slice complete for
   strict TXT authoring, logical page planning, 1-bit BMP serialization, and
   ttk tabs.
6. **Milestone E — new-file evidence:** complete. The audit, stable evidence
   preservation, and clean capture 04 synthesis are recorded in the Phase 12
   matrix; unchanged Manager sidecars are a verified negative result.
7. **Milestone F — offline new-record model:** complete offline. Exact
   capture-04 reconstruction, state rebasing, fail-closed capacity, deterministic
   audit, operation binding, fake-transport failure integration, explicit R15
   classification, and independent read-back are complete at the 263-test
   checkpoint. No physical recovery claim is made.
8. **Milestone G — guarded new TXT:** complete for the initial offline/fake
   workflow and one separately approved live root-level TXT smoke with full
   read-back verification. The normal action remains disabled and physical
   interrupted-write recovery is unproven.
9. **Milestone H — selective delete:** **complete for its captured-fixture
   offline scope**. The persisted legacy deletion-effect gate and the offline
   builder, exact binding, independent verifier, and fake-transport failure
   model are complete in commits `b5bae4b` and `c8162c0`; the full canonical
   suite is **283 tests** after the H.1 readiness slice. Physical
   atomicity/recovery remain unproven.
10. **Milestone H.1 — live-delete generalization and readiness:** **blocked and
    parked pending new independent evidence**. The timestamp-generation rule
    and fresh fixed-state derivation are not independently justified; the
    fixture helper must not be presented as live eligibility. Modern delete,
    any live-delete protocol, normal GUI/CLI exposure, restore, and bulk
    deletion remain excluded.
11. **Milestone I — prepared content:** **active with a constrained live
    package result and continued offline scope**. I.0, I.1, and
    I.2 are complete in commits `5a3c55b`, `0db6593`, and `05e29cb`; capture 7
    and the exact offline golden builder are complete in `139c658`, with
    fixture-boundary hardening in `465120f`; the suite passes **301 tests**.
    The exact one-folder/one-TXT legacy fixture is proven
    and reproduced byte-for-byte offline. General timestamps, fresh state
    derivation, arbitrary package creation, and product exposure remain
    blocked. Native total-limit capacity semantics are resolved offline by
    I.5; I.6 additionally has one approved constrained live smoke with parsed
    `0x0019` evidence, `0x0000` completion, exact candidate read-back, and
    preserved shared state. Manager UI free-space mapping, arbitrary package
    behavior, and interrupted-write recovery are not proven.
    The independent timestamp/fixed-state comparison found no safe legacy
    fresh-backup rule. I.4 is complete only for the separate constrained
    modern offline/fake-only policy. The I.6 live result is recorded
    separately; normal package transfer remains disabled and requires its own
    future product gate.
12. **Milestone J — Library integration:** connect import/drag-and-drop,
    Prepare, selected transfer, removal, and queue review using only proven
    operations. A crude interface is acceptable before visual refinement.
13. **Milestone K — integrated hobby release:** test the end-to-end core flow,
    refresh guidance, and build a new wheel. Signing remains deferred.
14. **Later work:** advanced renderer/EPUB profiles, visual refinement,
    restore, bulk delete/synchronization, firmware, and alternate service modes
    remain outside the core critical path until their gates are deliberately
    opened.

## H.2 isolated modern-delete smoke runner checkpoint (2026-08-27)

The offline H.2 structural gate remains complete for its supported one-record
model. A separate unregistered support runner now provides an eligible-target
listing, target-specific candidate construction, non-overwriting external
session skeleton, and sealed preflight artifact. The artifact binds the
verified device identity, complete backup and dynamic-model hashes, exact
target/payload/prefix identity, candidate and transaction hashes and lengths,
fixed-state hashes, path delta, capacity effect, timestamp policy, completion
policy, and no-retry rule without carrying candidate bytes.

The execute phase is present only behind the sealed artifact, the exact
`DELETE ONE INFOCARRY ITEM` phrase, and the separate
`APPROVE H2 MODERN DELETE SMOKE 01` approval. It revalidates the backup and
device identity, sends at most once through an injected sender, accepts only
`0x0000`, and requires independent complete read-back. It was not called
against hardware; no device operation occurred. Normal GUI/CLI deletion,
hardware detection, generalized deletion, and broader hardware mutation remain
outside this checkpoint.

Verification at this checkpoint: **483 passing tests and three intentional
evidence-dependent skips**; focused isolated-runner coverage: **11 passing
tests**. The later owner-approved constrained root-level TXT smoke completed
with `0x0000` and exact independent read-back; it does not generalize to other
targets or states. R15 remains open.

## H.2 target-specific read-only preflight result (2026-08-27)

The owner-approved read-only preflight completed against one supported device
and a new external evidence session. The owner selected exactly
`root\\IC_TEST_01.txt`; no target was selected automatically. The complete
backup has manifest SHA-256
`39323d69d27c55d342dd1c3c4129268ddad1a43c614d01be513c7100d67775c8` and
dynamic-model SHA-256
`fbfe0dc9898a0cd6c406bd26542859282a1a410b059b16812c32522a9ce8e450`.

The sealed preflight binds record offset `0x000001c0`, metadata-relative offset
`0x00000180`, payload length 41, payload SHA-256
`85c8e82f3547ace5c72f3f2c1c3817788cd134e4e6bbf4dca9032d4ca11e4c08`, candidate
SHA-256
`d4e4fa74e4338c18aa366e016ba9cb756d0af4e84b3bd19045993553d3526f20`, and
transaction SHA-256
`78636328fc7f386fcaf5a565421cd7feae0525a675a740019e7e1813aa148298`.
The candidate is 2,051,280 bytes and 372 records versus 2,051,420 bytes and
373 records before deletion; the modeled reduction is 140 bytes. All five
fixed-state objects remain the exact supported all-zero bytes.

No `0x101b` request was issued and no device change occurred. The raw session
and sealed artifact remain outside Git; the external checksum manifest covers
10 files with zero verification mismatches. This preflight is not write
authorization. A new explicit approval is required before any modern delete,
followed by the exact `DELETE ONE INFOCARRY ITEM` phrase. Normal GUI/CLI
deletion remains absent and R15 remains open.

## H.2 constrained modern-delete smoke result (2026-08-27)

After the sealed preflight, the owner supplied the exact phrases
`DELETE ONE INFOCARRY ITEM` and `APPROVE H2 MODERN DELETE SMOKE 01`. The
isolated runner issued exactly one modern `0x101b` transaction for
`root\\IC_TEST_01.txt`, accepted completion `0x0000`, and issued no retry.
The complete post-delete backup and independent verifier passed: 373 → 372
records, exactly one removed path, no added path, candidate/post dynamic-blob
equality, byte-identical surviving payloads, unchanged supported all-zero
fixed state, and no unrelated object change outside the documented
payload-dependent objects.

The sanitized synthesis is
`analysis/phase-13-milestone-h2-modern-delete-smoke-20260827.md`. Raw before
and after backups remain outside Git at the external session root. Its final
21-file checksum manifest is
`checksums/SHA256SUMS-post-delete-01.txt`, SHA-256
`baa348b18ef0d2665baf861a7e980aad93021b187a5397479a231f5482036f87`, with
zero verification mismatches. This is one constrained live smoke, not
generalized deletion compatibility. R15 physical interrupted-write atomicity
and recovery remain unresolved; normal GUI/CLI deletion remains disabled.

## Phase 14 — offline ordered package candidates (2026-08-27)

The first general-content slice extends the existing capture-7-shaped folder
machinery to one new root folder with an explicitly ordered list of at least
two TXT or typed TXT/BMP children. The builder uses an explicit validated
native prefix template for every kind, one frozen timestamp for all new
records, exact source revalidation, parsed native `0x0019` total-capacity
evidence, capture-7-compatible all-zero fixed state, four-byte aligned content,
and the existing `0x101b` prospective range artifact. It preserves shared
record bytes outside the proven offset/length fields, timestamps, prefixes, and
payloads. This is an offline candidate only; it is not a live multi-child
compatibility claim. Its exact offline authorization binds ordered sources,
target record identities, native capacity evidence, fixed state, candidate,
and transaction hashes, but remains disconnected from all live actions. The
fake-only guarded workflow now covers fresh-backup rebuild, one-shot sending,
finite cooperative deadline checks, exact completion, and independent fake
read-back failure boundaries.

Commit `8e4641c` corrected the current constrained-delete documentation. The
candidate implementation and synthetic regression slice is recorded in
`phase-14-multiple-package-candidates-20260827.md`; it adds candidate and
independent read-back coverage and brings the portable suite to **507 passing
tests with three intentional evidence-dependent skips**. The flat I.10 ebook
plan is now connected to this offline candidate path while nested sections
remain rejected. Multi-child authorization is now covered offline and fake
only; the fake workflow and read-only package readiness preview are now
complete for the offline candidate boundary. Before P15-001, no native
multi-child before/transaction/post sequence existed; Capture 01 now supplies
that evidence for its exact four-TXT shape, while no modern hardware operation
has occurred.

## Phase 15 — P15-001 native multi-chapter TXT evidence readiness (2026-08-28)

P15-001 advances the evidence boundary from the proven one-folder/one-TXT
shape to one explicitly constrained flat text-only package. The sanitized
source fixture in
`samples/generated/P15-001-native-multi-chapter-txt/` contains one new root
folder, four 120-byte ASCII/strict-CP932-compatible CRLF TXT children, explicit
target order, unique in-file order/end markers, and exact source/manifest
hashes. The package contains no backup, capture, candidate, transaction, or
private device data.

The operation-specific legacy Manager procedure is recorded in
`analysis/phase-15-p15-001-native-multi-chapter-txt-evidence-protocol-20260828.md`.
It defines the fresh pre-operation and complete post-operation backups, exact
source and Manager snapshots, the isolated native USB capture, three required
timestamp observations (initialization idle, pre-send, and completed packet
idle), an optional ownership-return timestamp, checksums/preservation
manifest, abort conditions, and the
verified/observed/inferred/unresolved analysis labels. It stops at
`READY_FOR_HARDWARE_TEST`; the owner approved exactly one legacy capture on
2026-08-28 and reconfirmed that approval on 2026-08-29 under the revised
three-required-timestamp procedure. Capture 01 was then supplied and preserved
outside Git. The exact four-child native structure, payloads, relationships,
capacity fit, fixed state, and native range-to-post-blob equality are verified.
All 313 shared reachable record timestamps changed between the supplied
pre/post blobs, and child 4 has a distinct new timestamp; these native legacy
observations remain unnormalized. The owner-supplied event mapping and Project
Lead timestamp decision now bound the modern policy. The native numeric
request-4 word remains explicitly unresolved after offline log-tail
investigation, without contradicting the owner normal-return observation or
independently verified persistence. The constrained native gate is closed and
the modern dossier is `READY_FOR_HARDWARE_TEST` for this exact shape only.

The sanitized intake record is
`analysis/phase-15-p15-001-native-multi-chapter-txt-capture-01-results.md`.
The owner-supplied timestamp mapping and Project Lead decision reconcile the
modern policy: preserve all existing timestamps, assign one explicit timestamp
to all new records, and do not reproduce the legacy operation-wide rewrite or
child-4 sequential increment. The native numeric request-4 word remains
explicitly unresolved after offline log-tail investigation. The constrained
modern candidate, exact authorization, fake-only workflow, independent
read-back, and R3 review are complete; the dossier is
`READY_FOR_HARDWARE_TEST`. A separate owner approval remains required before
any later modern `0x101b` transaction.
