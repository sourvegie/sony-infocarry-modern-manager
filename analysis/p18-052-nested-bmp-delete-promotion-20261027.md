# P18-052 — Experimental nested-BMP Delete promotion

Date: 2026-10-27 JST. Risk: R3, because ordinary Device Library can authorize a
reviewed device-changing candidate. Scope: offline implementation, verification,
independent exact-head review and local integration preparation. No hardware
command, discovery, sender, push, merge or main integration is performed here.
P18-051's exhausted two-write authority is not reused.

**P18-052 REVIEWED — READY FOR LOCAL INTEGRATION.** Exact reviewed executable
source/tests: `75f45db953133b9cbcca6e0a2a555036496464ba`. Independent R3
**P0/P1/P2=0/0/0**, no material correction round. The delivery checkpoint adds
only final sanitized documentation; executable source/tests remain identical.

## Source and admission

Isolated branch: `task/p18-052-nested-bmp-promotion`, cloned without hardlinks
from sanitized P18-051 final `219ebfb4182e8cafbb294e69e1fd8b79a9636579`.
Published sanitized main `c87a208cbf28e23daa1aa5bfa7ffdfdfed4fb771` is an
ancestor. The original P18-034 and P18-051 checkouts are read-only references.
The new profile is `vnw-v15-unread-nested-bmp-delete-v1`.

All of the following are required, rather than treating arbitrary nested BMP
records as supported:

- Reviewed VNW-V15 model, observed session identity `054c:001e`, complete verified
  eight-object archive, supported native capacity, and exact fresh displayed-state
  equivalence. VID/PID is a model/session observation, not a physical-unit ID.
- One reachable file with `.bmp` native extension, unique case-insensitive native
  path identity excluding extension; unread `0xe0`, opaque `0xffffffff`, selector
  `0x100`, and exactly 16 all-FF prefix bytes. Exact selected record offset,
  original payload, native record and source archive are bound and re-derived.
- Exactly two existing ordinary folders below root: `root\folder\folder\file.bmp`.
  Deletion must leave another reachable child in the immediate parent. Parent
  ownership, nonoverlapping child tables, leading-marker ownership, terminal
  marker references and raw native ordering must pass the existing model.
  Existing relation-only terminal-marker rules are retained, not replaced by
  an invented self-reference requirement. Orphans/unknown reachable kinds refuse.
- Target stem and ancestor names must be nonempty, 1–39 CP932 bytes, exactly
  representable and round-tripping, raw NUL-terminated and identical to decoded
  identity. Reserved `root`, `.`/`..`, control/DEL, leading/trailing whitespace
  and `\\/.:<>"|?*` syntax refuse. Ambiguous native paths anywhere refuse.
- Existing canonical BMP validator: `BM`, exact declared length, 40-byte
  BITMAPINFOHEADER, width 237, signed height ±320, one plane, one bit per pixel,
  BI_RGB/uncompressed, two-entry palette (`colors_used` 0 or 2), pixel offset 62,
  stride 32, exact pixel bounds and canonical decoder acceptance. Payload is
  exactly 10,302 bytes; no trailing payload. Top-down nested content is inferred.
- Checksums and native geometry must be valid. Every file allocation must be
  bounded, aligned and nonoverlapping before and after, including prefix,
  payload and padding. Candidate reconstruction and independent verification
  preserve all surviving raw fields, timestamps, opaque bytes, payload/prefix
  pairs, parent/sibling order and markers, with only required pointer/table/
  allocation/checksum rebases.
- Target must be absent from supported protected associations. Active Marks,
  dangling/unknown protected state or unsupported protected relationships refuse.
  Supported survivor associations and opaque tails must preserve semantics.

Read or alternate native profiles, other BMP formats, alternate folder depths,
emptying the parent, unsupported/system/ambiguous paths, multiple selections,
directory/subtree deletion, VNW-V10, interrupted-write recovery and unrestricted
nested-BMP deletion remain unavailable.

## Physical proof versus host inference

The exact physically demonstrated fixture is
`root\IC_P18_040_NESTED_20260930_01\Section-A\IC_P18_051_DELETE_A.bmp`:
10,302 bytes, SHA-256
`2701eb9214e2f0afec20b36c93ef739ef3bce35e931fd8c5721e15915447b26d`,
bottom-up 237×320, record `0x880`, parent `0x700`, marker `0x780`, surviving BMP
`0x800` and TXT `0x840`. P18-051 actually placed and deleted precisely that
fixture, each native integer zero/one sender/no retry, with all eight original
objects restored byte-for-byte. This task does not repeat that experiment.

Independent read-only revalidation checks original authority, all actual
operation identities/candidates/transaction ranges, full template provenance,
fresh backups, all-eight restoration and 20 indexed physical anchors. The
source-template payload and new fixture are distinct, and the actual prepared
candidate provenance matches the frozen envelope. See the
[independent evidence assessment](p18-052-independent-evidence-assessment-20261027.md)
and preserved [physical closeout](p18-051-independent-physical-validation-20261026.md).

The restored 454-record archive contains 163 nested BMPs: 13 structural passes,
11 complete protected-state host candidates and 2 protected-reference refusals.
Only ONE restored existing BMP matches this additional two-folder/nonempty-parent
class; ten other complete candidates fail the depth restriction. Other
refusals: 119 dimensions, 27 unsafe path syntax, 4 nonexact CP932 identities.
The one matching archive case is bottom-up. Other safe names, pixel patterns,
valid serialized slots and top-down nested content are reviewed engineering
inference, not additional nested physical specimens or exhaustive class proof.
Synthetic host tests exercise those variations explicitly. Root-BMP orientation
proof does not become nested physical proof.

## Implementation and unchanged lifecycle

Production changes are restricted to the existing generalized authorization
reconstruction, guarded Delete workflow, Device Library adapter and two help/
selection strings. The host nested candidate/repacker/independent verifier,
transport, coordinator, persistent formats, locks and claims are unchanged.
The generic generalized sender remains closed to all nested and all BMP
candidates. Only the established guarded façade can execute this profile.
Retained exact validation sessions remain fixture-only; changing labels cannot
turn them into ordinary class authority.

The user flow remains Select → Delete → Confirm → Verify → Refresh, with one
normal Delete/Cancel dialog displaying the full nested path. The operation
re-admits the immutable selected archive before opening a runtime, obtains a
fresh complete eight-object backup and capacity, compares fresh source state,
freezes source/path/record/payload/candidate/transaction/owner identity, then
rechecks immediately before one-shot execution. Reconnect-equivalent state is
accepted; changed/unsupported state refuses. Durable claim, sender marker and
installation-wide global lock are reused. After transfer starts, native
integer `0x0000` plus independent complete readback is required. Ambiguous,
nonzero, disconnected or failed-readback results stop after one sender and keep
the established fail-safe policy. No retry/recovery/cleanup is added.

Root-TXT, root-BMP and nested-TXT admission are unchanged. Inspection, local
Library, transfers and exact validation workflows are covered by existing
regressions. Ordinary deletion verifies exact survivor/protected-state semantics
against its own fresh baseline; P18-051's experiment-specific pre-placement
all-eight restoration set is not applied to unrelated ordinary deletions.

## Completed validation and independent review

Canonical portable command:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

**1,331 run / 1,326 passed / five established evidence-dependent skips in
739.822 seconds; exit zero.** No new skip/failure/error. Skips remain the two
absent stable-capture04 cases, two external P18-012/P17 evidence cases and one
local raw native-range comparison. Existing root-TXT/root-BMP/nested-TXT,
inspection, transfer, exact validation and guarded-lifecycle regressions pass.

Existing focused nested-BMP preparation/nested-TXT/root-BMP regressions:
**22/22 passed in 90.495 seconds**. The reviewer independently ran the new
exact-head module: **17/17 passed in 168.845 seconds**, covering CP932 names,
different pixels, both canonical orientations, first/last native positions,
native/format/depth/name/parent/marker/allocation/checksum/state refusals,
protected references, raw survivor/timestamp/payload preservation, frozen
identity, reconnect, one-shot/no-retry policy and actual ttk callback Cancel,
success, failure and verified refresh. All 17 also pass in the complete suite.

macOS arm64 package: supported CPython 3.12.14/Tcl-Tk 9.0, dependency check,
PyInstaller build, plist lint, ad-hoc deep strict signature verification PASS.
Frozen runtime PASS: bundled Tk 9.0.4 and libusb backend, Local Library import,
host planning and unavailable-runtime/locked controls; zero real device
enumerations, senders, `0x101b`, claims or sender markers. No Developer ID,
notarization, Windows runtime or physical device-display inspection is claimed.

Native macOS Tk fake-workflow PASS: one actual Delete/Cancel dialog, one fake
sender, independent readback and refreshed tree; zero real USB calls or writes.
Wheel build and isolated extracted-wheel import PASS. The reviewer additionally
compares all four changed production modules inside the wheel with reviewed
source: byte-identical. Compile and whitespace checks PASS. Raw logs/build
products and fake state stay in ignored output or private evidence outside Git.

The [independent exact-code-head R3 report](p18-052-independent-r3-review-20261027.md)
records **PASS, P0/P1/P2=0/0/0**, with no material correction round. It independently
inspects exact source, all results, actual native evidence and authority, and
reruns the new executable builder across all 163 archived nested BMPs: exactly
one admission at `0x800`, identical host candidate and independent no-repacker
verification; generic sender still refuses. The actual P18-051 placed fixture
reconstructs through retained exact and ordinary profiles with identical inverse
candidate/transaction and distinct authority profiles.

Private result navigation and hashes are retained at
`/private/tmp/p18-052-evidence/verification-index.json`, alongside completed
logs, independent census and preservation reports. This is an evidence index,
not a live operation envelope or hardware authorization.

## Preservation, privacy and local integration

Independent after-suite verification: **2,028 private file/symlink anchors
unchanged**, including all prior 1,550; original P18-034 HEAD/refs/exact status
and all **1,107 dirty paths unchanged**; P18-051 clean at its final commit.
Mode=ro production SQLite checks find the same **28 claim rows**, zero sender
markers and valid integrity; historical clear global-lock bytes are unchanged.
No canonical production safety owner is constructed.

Git integrity and sanitized ancestry PASS: published main `c87a208c…`, then
P18-051 `219ebfb4…`, then reviewed source `75f45db9…`; origin/main and the
original main ref are unchanged. `git fsck --full` exits zero with inherited
informational dangling commits only. New reachable blobs contain only source
and sanitized Markdown; all new versions are privacy-scanned. No raw native
backup, private source title/path, credentials, transaction binary or original
Sony artifact was added. The known excluded private blob is unreachable from
outgoing history. Final delivery checks repeat this scan for documentation.

The isolated branch is locally committed and ready for later integration from
the verified sanitized baseline. The documentation-only delivery commit retains
byte-identical reviewed source/tests and receives final independent attestation.
No local main integration, physical experiment, push or merge is performed.

Remaining limitations are the explicit admission exclusions above, inferred
class behavior beyond one physical bottom-up specimen, no stable physical-unit
identity, and unresolved physical atomicity/interrupted-write recovery. This
promotion grants no standing physical authority and no broader nested-BMP or
directory/subtree deletion capability.
