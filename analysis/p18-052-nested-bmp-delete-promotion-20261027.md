# P18-052 — Experimental nested-BMP Delete promotion

Date: 2026-10-27 JST. Risk: R3, because ordinary Device Library can authorize a
reviewed device-changing candidate. Scope: offline implementation, verification,
independent exact-head review and local integration preparation. No hardware
command, discovery, sender, push, merge or main integration is performed here.
P18-051's exhausted two-write authority is not reused.

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
  BI_RGB/uncompressed, two-entry palette (`colors_used` 0 or 2), pixel offset62,
  stride32, exact pixel bounds and canonical decoder acceptance. Payload is
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
bottom-up237×320, record `0x880`, parent `0x700`, marker `0x780`, surviving BMP
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

The restored 454-record archive contains163 nested BMPs:13 structural passes,
11 complete protected-state host candidates and2 protected-reference refusals.
Only ONE restored existing BMP matches this additional two-folder/nonempty-parent
class; ten other complete candidates fail the depth restriction. Other
refusals:119 dimensions,27 unsafe path syntax,4 nonexact CP932 identities.
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

## Validation and review checkpoint

Focused existing nested-BMP preparation/nested-TXT/root-BMP regressions:
22/22 passed in90.495s. New focused module has17 tests, covering positive
class variations, refusal profiles/graph/markers/allocations/checksum/state,
references, raw survivor/timestamp/payload preservation, identity tampering,
reconnect, one-shot/no-retry policy and actual ttk callback Cancel/success/
failure/refresh. Nine execution/UI tests passed in the initial diagnostic;
eight corrected refusal tests passed separately (6 in0.653s,2 in1.964s).
The initial diagnostic exposed test assumptions about exception inheritance and
an invented marker rule; those test assumptions were corrected, with no
production bypass or disabled assertion. Canonical full-suite result pending.

macOS arm64 package: supported CPython3.12.14/Tcl-Tk9.0, dependency check,
PyInstaller build, plist lint, ad-hoc deep strict signature verification PASS.
Frozen runtime PASS: bundled Tk9.0.4 and libusb backend, Local Library import,
host planning and unavailable-runtime/locked controls; zero real device
enumerations, senders, `0x101b`, claims or sender markers. No Developer ID,
notarization, Windows runtime or physical device-display inspection is claimed.

Native macOS Tk fake-workflow PASS: one real Delete/Cancel dialog, one fake
sender, independent readback and refreshed tree; zero real USB calls or writes.
Wheel build and isolated extracted-wheel import PASS (no source-tree import).
Compile and whitespace checks PASS. Raw logs/build products and fake-workflow
state stay in ignored output or private task evidence outside Git.

Independent exact-code-head R3 and final preservation/privacy/Git checks are
pending. This checkpoint is not yet a completed review or integration authority.
No local main integration, push or merge is requested or performed.
