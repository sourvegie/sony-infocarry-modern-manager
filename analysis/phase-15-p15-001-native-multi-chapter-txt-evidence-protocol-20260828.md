# P15-001 — native multi-chapter TXT evidence protocol

Date: 2026-08-28; procedure revision and approval reconfirmed 2026-08-29
Status: **BLOCKED_BY_EXTERNAL_EVIDENCE — Capture 01 ingested; native gate open.**

This is the operation-specific procedure for one disposable, flat, text-only
legacy Manager capture. It is the next evidence gate after the Phase 14
offline package work. Preparing this record, the package, or a future
preflight does not authorize a device change. The owner must give a new,
operation-specific approval immediately before the legacy Manager sends the
package.

## Exact package

Use the committed sanitized package at
`samples/generated/P15-001-native-multi-chapter-txt/`. The exact source tree
is:

```text
IC_P15_MULTI_20260828_01/
  chapter-01.txt
  chapter-02.txt
  chapter-03.txt
  chapter-04.txt
```

The folder is one new root-level folder. The four children are explicitly
ordered by their target names and by in-file `Order marker: NN of 04.` lines.
Every file is 120 bytes, ASCII-only (and therefore strict-CP932 compatible),
uses CRLF line endings, and has a unique `P15-001-NN-END` marker. The exact
source SHA-256 values are in `manifest.json`, `MANIFEST.md`, and
`SHA256SUMS.txt`. Copy the complete source tree and those three manifest files
to the external session without changing bytes. Do not substitute Japanese,
BMP, EPUB, MOBI, nested, renamed, reordered, or additional content.

The package is intentionally not a candidate or transaction artifact. The
existing offline multi-child candidate is a comparison model only; it is not
used to authorize this legacy operation.

## Minimum complete external evidence set

Create one new, non-overwriting session root outside Git, for example:

```text
${EVIDENCE_ROOT}/phase-15-p15-001-native-multi-txt-<UTC-TIMESTAMP>/
  00-package/
  01-pre-operation/
  02-manager-before/
  03-snoopypro-transaction/
  04-manager-result/
  05-post-operation/
  06-timestamps/
  07-analysis/
  preservation-manifest.json
```

The session is complete only when it preserves, at minimum:

1. the fresh complete pre-operation device backup, including every object,
   object hash, backup manifest, device identity, and dynamic-model hash;
2. the exact four source files, the exact package folder tree, and the
   human-readable and machine-readable manifests;
3. the legacy Manager BEFORE snapshot, preserving actual relative paths for
   `Backup/VICDATA.bin`, `Memo/VICMEM.bin`, `Memo/VICLV.bin`, the applicable
   nested `ICM/<transfer-folder>/order.vnw`, and any additional related sidecar;
4. the exact native USB transaction capture, in native form and any derived
   form separately, with the correct `USB\\Vid_054c&Pid_001e` target and a
   hash of the unchanged native file;
5. the legacy Manager result/AFTER snapshot, including the exact displayed
   result and a screenshot when available, with the same sidecar paths as the
   BEFORE snapshot;
6. the fresh complete post-operation device backup with every object,
   object hash, backup manifest, device identity, and dynamic-model hash;
7. relevant timestamp observations and a separate mapping of each timestamp
   to its event; and
8. a preservation manifest containing relative path, byte size, SHA-256,
   source/type, and capture timestamp for every session file, plus the
   session manifest hash.

Also preserve a read-only native capacity observation before the operation
when available: the raw hardware/capacity response and its hash, or a clearly
identified Manager capacity display with a screenshot. A missing or malformed
capacity observation is not silently replaced by an estimate.

## Preconditions and owner checkpoint

1. Keep the VNW-V15 unchanged. No modern client write/delete, restore,
   refresh, reorder, or other mutation is part of this procedure.
2. With macOS owning the device exclusively, confirm Sony `VID 0x054c`,
   `PID 0x001e`, create a new complete read-only backup under
   `01-pre-operation/`, and verify its complete manifest before proceeding.
3. Verify that the pre-operation dynamic model contains neither
   `root\\IC_P15_MULTI_20260828_01` nor any of its four children. If the
   folder or any child exists, stop and choose no replacement name in this
   task.
4. Verify the package copy against `00-package/SHA256SUMS.txt`. Confirm four
   files, four distinct hashes, four distinct target names, 480 total source
   bytes, strict CP932 decoding, and CRLF line endings. Preserve the exact
   copy used by Manager.
5. Preserve the read-only capacity observation and its hash, if obtained.
   Record tool/version, UTC/local clocks, device identity, backup path, and
   any clock skew or unavailable observation.
6. Before any ownership change, show the owner the package manifest, the
   verified pre-operation backup summary, the target absence, the capture
   destination, and this exact expected effect: one new root folder, four
   ordered TXT children, no removals, no unrelated changes, one selected-send
   operation, and no retry.
7. Request the separate approval phrase exactly:

   ```text
   APPROVE P15-001 LEGACY MULTI-TXT CAPTURE 01
   ```

   The owner supplied this exact approval in the Dispatcher conversation on
   2026-08-28 and reconfirmed it on 2026-08-29 under the revised
   three-required-timestamp procedure. It authorizes only the one legacy
   Manager operation described here. The human operator must still follow the
   procedure and preserve the complete external evidence set. It does not
   authorize a modern `0x101b` transaction.

## Timestamp observations

Use the established Windows 2000 timestamp tool when available. Preserve its
raw numbered output unchanged and use a separate mapping file; do not rename,
normalize, or overwrite raw timestamp files. Capture and label these three
required observations:

1. immediately before the isolated SnoopyPro capture/Manager operation is
   armed, after startup and browsing traffic is idle;
2. immediately before the single Send Selected action;
3. immediately after Manager reports its result and the correct SnoopyPro
   row has been idle for approximately 2–3 seconds.

An additional observation immediately before returning USB ownership is
optional. It may document the administrative cleanup boundary, but it is not
required for timestamp analysis: the required third observation, stopped
native log, result screenshot, and post-operation backup already bind the
completed transfer. Do not delay stopping the isolated native log merely to
capture this optional observation.

If the tool is unavailable, clocks are inconsistent, or an event cannot be
   distinguished, preserve the partial observation and stop the experiment;
   do not infer a timestamp rule from wall-clock filenames.

## Isolated legacy Manager operation

1. Release USB ownership cleanly to Windows 2000. Do not let macOS and
   Windows own the device at the same time.
2. Start a new native SnoopyPro log and attach it to the actual InfoCarry row
   `USB\\Vid_054c&Pid_001e`, never a root hub. Record SnoopyPro and Manager
   versions, native-log path, and the row/device identity. Do not begin the
   operation until unrelated startup and browsing traffic is idle. Capture
   timestamp 1 at that idle boundary.
3. Copy the exact package folder into the Manager transfer-source location,
   preserving the four target names and their order. Confirm that Manager
   displays exactly the new folder and four children in order.
4. Copy the complete Manager BEFORE snapshot into `02-manager-before/` using
   actual relative paths. Hash every file. If Manager locks a file, close it
   normally without refresh/receive, copy it, and reopen only before the
   isolated operation. If the complete snapshot cannot be preserved, abort.
5. Capture timestamp 2. Select only the root folder
   `IC_P15_MULTI_20260828_01`; do not select a child or another item.
6. Invoke only the ordinary legacy Manager **Send Selected** action once.
   Confirm the dialog identifies exactly the package folder. Do not use Send
   All, Receive, Receive All, refresh, browse, rename, reorder, delete, or
   another transfer.
7. Wait for Manager to finish. Record the displayed result verbatim and take
   the result screenshot. Capture timestamp 3. Stop the native log before any
   refresh or read operation.
8. Copy the complete Manager result/AFTER snapshot into
   `04-manager-result/`, with the same actual relative paths and a new hash
   list. Preserve any missing-file observation explicitly; do not replace it
   with the BEFORE copy.
9. Preserve the native log unchanged in `03-snoopypro-transaction/`, hash it
   before any XML/export conversion, and preserve derived forms separately.

Abort immediately, preserve all partial material, and perform no retry if the
wrong device row is selected, the package is absent/duplicated/reordered, any
target already exists, Manager reports failure/timeout/disconnect/ambiguity,
the native log is missing, traffic is not isolated, the snapshot is
incomplete, an unexpected dialog/action appears, or any unrelated content or
state changes. A failed or indeterminate attempt is evidence, not permission
for a second attempt.

## Return and post-operation preservation

1. Close Manager normally without refresh, receive, browsing, or another
   mutation. Preserve the result screenshot and displayed text. An optional
   fourth timestamp may be captured immediately before returning ownership,
   but its absence does not make an otherwise complete session invalid.
2. Return USB ownership cleanly to macOS. Do not force-quit, force-eject, or
   change ownership while Manager or SnoopyPro is active.
3. Create one new complete read-only post-operation backup under
   `05-post-operation/`. Verify all objects and hashes before comparison. Do
   this regardless of Manager wording or apparent success.
4. Complete `preservation-manifest.json` only after copying all session files.
   Confirm that the manifest has no missing, extra, or hash-mismatched entry.
   Keep raw backups, native captures, screenshots, and private source copies
   at the external evidence root; never add them to Git.

## Offline intake and analysis gate

When the owner supplies an approved session, preserve the supplied raw root
unchanged and validate `preservation-manifest.json` and every listed hash
before interpreting any result. The Dispatcher must record only supplied
observations and host-verifiable comparisons.

The analysis must include:

- complete pre/post backup validity, device identity, object hashes, dynamic
  model lengths and hashes, and the exact path delta;
- parsed pre/post record inventories for the new folder, leading parent
  marker, each ordered child, direct-parent relationships, sibling order,
  metadata offsets, content offsets, four-byte alignment, payload lengths and
  hashes, native prefixes/wrappers, timestamps, fixed-state references, and
  capacity/model-length values;
- native capture transaction count, command declaration, all range lengths
  and hashes, `N/M` staging fields, completion/result evidence, and any
  mismatch between Manager wording and native result;
- Manager BEFORE/AFTER file hashes and changes, kept separate from
  device-resident `VICDATA.bin`/`0x8004` conclusions;
- unchanged unrelated records, payloads, sidecars, fixed-state objects, and
  other device objects, without normalizing unexplained differences away; and
- a byte-level comparison of the native post-state against the existing
  offline multi-TXT candidate using the exact observed package, paths/order,
  observed timestamp, validated TXT prefix, fixed state, capacity, and
  transaction lengths. Any mismatch must be reported before deciding whether
  the candidate model can be reconciled.

Use the existing read-only parsers and inventory helpers where applicable:
`infocarry.prepared_evidence.inventory_records`,
`infocarry.usblog.find_101b_headers` / `extract_101b`, and the independent
multi-package read-back verifier. Do not copy raw bytes into a tracked report.

Every conclusion receives one label:

- **verified** — directly established by validated bytes, hashes, parser
  invariants, or an exact independent comparison;
- **observed** — directly reported by the operator or visible in a Manager,
  SnoopyPro, screenshot, or timestamp artifact but not independently proved
  as device semantics;
- **inferred** — a model explanation that fits the verified observations;
- **unresolved** — missing, ambiguous, contradictory, or insufficient
  evidence.

The native gate closes only if the evidence supports all of the following:

1. exactly one new root folder and exactly four reachable TXT child records;
2. the four child records preserve the specified order and expected parent,
   leading-marker, sibling, and folder relationships;
3. record fields, payload offsets, 32-byte TXT wrappers, payload lengths,
   four-byte alignment, and content padding reconcile without unexplained
   differences;
4. native declared/range lengths and the post-backup dynamic model align;
5. timestamps and fixed-state changes are recorded and bounded, not guessed;
6. capacity/model-length behavior is supported by the fresh observation and
   pre/post measurements;
7. all unrelated records, payloads, objects, and Manager sidecars are
   unchanged or separately explained; and
8. Manager result, native completion, and post-backup persistence agree, or
   any disagreement is explicitly classified unresolved.

If any item fails, classify the result as `BLOCKED_BY_EXTERNAL_EVIDENCE` or
`ESCALATION_REQUIRED` as appropriate, document the discrepancy, and do not
reconcile it away or produce a modern smoke dossier.

## Capture 01 intake result

The owner-supplied Capture 01 was preserved outside Git at
`/Users/stardust/Projects/InfoCarry-Evidence/phase-15-p15-001-native-multi-txt-20260828-01/`.
The preservation manifest covers 82 files and records the unresolved missing
event mapping, explicit Manager result/completion evidence, and timestamp-model
decision. The raw source remains unchanged under
`08-supplied-capture11-raw/`; role-staged copies are byte-identical.

The sanitized synthesis is
`analysis/phase-15-p15-001-native-multi-chapter-txt-capture-01-results-20260829.md`.
Host verification establishes the exact four-child payload/order and
folder/parent-marker structure, a 992-byte model growth from 2,051,280 to
2,052,272 bytes, native capacity of 3,145,728 bytes, and byte equality between
native transaction ranges 05+08 and the complete post-operation dynamic blob.
The five fixed-state response objects are unchanged and all shared file
payloads are unchanged.

The gate remains open. The pre/post comparison observes timestamp changes in
all 313 shared reachable records, and the new fourth child has timestamp
`0x6a91a908` while the folder, leading marker, and first three children use
`0x6a91a907`. This contradicts the current offline policy of preserving shared
timestamps and applying one frozen value to all new records. The three raw
timestamp logs are valid and chronological, but no event mapping was supplied;
the offline native parser also does not decode request-4 completion, and no
explicit Manager result/screenshot was supplied. These differences are not
normalized away. No modern candidate or smoke dossier is authorized by this
intake.

## Modern-smoke boundary

No modern multi-TXT smoke dossier is produced by this record because Capture 01
did not close the native gate. A later dossier may be prepared
only after the gate above closes and a second strong independent review
confirms the exact constrained shape. It must bind a new fresh complete
backup, device identity, exact four sources and target paths/order, capacity
evidence, fixed state, reconciled candidate, prospective transaction, result
handling, and no-retry policy. It must stop at
`READY_FOR_HARDWARE_TEST` and request a separate approval before any modern
`0x101b`; this legacy capture approval can never be reused for that purpose.
