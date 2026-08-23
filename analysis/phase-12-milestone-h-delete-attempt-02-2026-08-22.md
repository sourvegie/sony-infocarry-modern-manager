# Milestone H — legacy delete attempt 02 synthesis

Date: 2026-08-22
Status: **Persisted legacy deletion-effect evidence gate and narrow offline
delete safety gate complete; modern delete remains prohibited.**

This record synthesizes the owner-approved isolated legacy Manager deletion of
exactly `root\\IC_E_ADD_20260822_04.txt`. It does not authorize or implement a
modern delete. The original Desktop capture and the read-only synchronized
`InfoCarry-Toolkit` project remain untouched.

## Evidence preservation

All copies below are under a new non-overwriting attempt-02 evidence root.
The initially supplied layout, which contained `ICM.zip` and top-level
`order.vnw` copies, is preserved separately as historical intake. The owner
then supplied a corrected copy with the actual Japanese relative path; that
corrected copy is authoritative for Manager-side path comparisons.

| Evidence | Stable path | Verification |
| --- | --- | --- |
| Complete pre-delete backup | [`00-pre-delete-backup`](../../evidence/phase-12-milestone-h-delete-attempt-20260822-02/00-pre-delete-backup) | `manifest.json` SHA-256 `a0124716d81bfcadc76433b9bef06f4a452babca22700da1b91981e4e52591ea` |
| Corrected owner capture | [`01-owner-capture-corrected/owner-original`](../../evidence/phase-12-milestone-h-delete-attempt-20260822-02/01-owner-capture-corrected/owner-original) | `SHA256SUMS.txt` SHA-256 `72a4468f21135a92bf87d70c0b0b1cd4b88d7c58948e28f2749dc18623481b63`; all listed hashes verified |
| Native derived artifact | [`derived-analysis/native-delete-artifact`](../../evidence/phase-12-milestone-h-delete-attempt-20260822-02/01-owner-capture-corrected/derived-analysis/native-delete-artifact) | `manifest.json` SHA-256 `b908e9e0695b9f5b8d4775437ab72a0c4aa8fc512b5c096890419447c479af13`; offline-only, never transmitted |
| Owner-supplied result image | `01-owner-capture-corrected/owner-supplied/manager-result.png` | SHA-256 `f79c2c5dd00563311eb070e1554f1ec9be246adfd062b26f61e81a9f59740285` |
| Complete post-delete backup | [`02-post-delete-backup`](../../evidence/phase-12-milestone-h-delete-attempt-20260822-02/02-post-delete-backup) | `manifest.json` SHA-256 `dde2a9c0230c7cf02bf30dae5efe12164e81c2ed775dbeef5756c6b9f3286b50` |

The corrected native log is
`01-owner-capture-corrected/owner-original/usblog/01-delete.usblog`,
2,288,872 bytes, SHA-256
`676f68d8b5da4565ad295778c5d23a9772a568d727ecced8ac662e38c5001a3e`.

## Gate assessment

| Requirement | Result | Classification |
| --- | --- | --- |
| Exact target selected | `root\\IC_E_ADD_20260822_04.txt` was present exactly once in the fresh pre-delete backup at metadata offset `0x2c0`; the modern-created `_01` item remained present and was not selected | **Verified** |
| One isolated native transaction | Exactly one ordinary `0x101b` transaction; ranges `[256, 64, 65216, 0, 64, 0, 0, 2050784]`, with `N=0`, `M=2050848` | **Verified** |
| Candidate/post dynamic blob | Native range 5 plus range 8 is 2,050,848 bytes and SHA-256 `88b95f8bc158ab89253faea8c9085799cebba76abf0a3f416afa62df8b55f287`; it exactly matches the complete post-delete device blob | **Verified** |
| Target removal | Pre-delete record count 368; native candidate and post-delete blob contain 367 records. Exactly `_04` is removed; no path is added | **Verified** |
| Shared payload preservation | No shared file payload changed across the 253 shared file paths | **Verified** |
| Manager-local sidecars | `VICDATA.bin`, `VICMEM.bin`, `VICLV.bin`, and the nested `ICM/転送元フォルダ/order.vnw` are byte-identical before/after. The `order.vnw` hash is `824ec471ffee0154f982a94a7ec4dd0aef7b1f1d6208f0febd94e2f66fc46894` and still contains `_04` in both snapshots | **Verified negative result** |
| Manager result | The supplied image shows `_04` absent from the device preview. It does not preserve an explicit success dialog, exact Japanese result text, or numeric status; the owner reported that the delete completed. The persisted device effect is independently verified and no further capture is required | **Deletion effect verified; wording unavailable** |
| Request-4 completion | The native log reaches the request-4 boundary, but the native SnoopyPro representation does not expose a trustworthy decoded result word. Existing successful modern-write evidence establishes `0x0000` as the only accepted completion for a future modern delete; missing, ambiguous, malformed, or nonzero completion must be terminal with no retry | **Unavailable legacy value; safely constrained future behavior** |
| Fixed state | Native `0x001b`, `0x001c`, `0x001e`, and `0x001f` blocks match the post-backup responses. The delete-specific `0x001d` form is narrowly observed as native `count=0`, `value_04=1`, empty offsets; stable post-backup state is `count=0`, `value_04=0`, empty offsets | **Verified narrow normalization; semantic name unresolved** |

The exact native `0x001d` observations are:

```text
pre backup:   count=1, value_04=0x0001, record_offsets=(0x0300,)
native write: count=0, value_04=0x0001, record_offsets=()
post backup:  count=0, value_04=0x0000, record_offsets=()
```

This is not silently treated as stale data or assigned a semantic name. It is
classified only as an observed delete-specific transient-to-stable
normalization. No other fixed-state difference receives a normalization
allowance, and the later stable form is not substituted into the transmitted
candidate.

## Timestamp behavior and exact offline reproduction

The native candidate rewrites the timestamp field of every one of the 367
surviving metadata records. The observed values cannot be derived from the
pre-delete timestamps by a verified semantic rule. For the preserved attempt-02
comparison, the complete opaque map is paired in surviving metadata order and
contains 367 entries. Its canonical SHA-256 is
`67cdfaa4365832baf2be60babd97920f21f85dcfabe55ee16d1df1628ef39183`.

The offline delete builder therefore requires that complete caller-supplied
map and records it in the audit; it never silently synthesizes timestamps. The
native structural boundary is also narrow: the observed `..` marker field at
the exact next metadata boundary (`target offset + 0x40`) is rebased, while
other marker values are preserved. With the observed map and this exact
boundary rule, offline construction reproduces the native range-5 plus range-8
candidate byte-for-byte:

- candidate/post dynamic blob SHA-256:
  `88b95f8bc158ab89253faea8c9085799cebba76abf0a3f416afa62df8b55f287`;
- complete eight-range transaction SHA-256:
  `001b32e3901fde1563ae1a098c46ecc6dad2ec8c16cd5511f961bf53f9e4d888`.

This is verified offline equivalence to the preserved legacy transaction, not
proof that a modern delete is safe to transmit. Timestamp semantics remain
unresolved, and no general timestamp rule is inferred.

## Device state versus Manager bookkeeping

The dynamic `VICDATA`/`0x8004` blob and the fixed response objects are the
device-resident protocol state observed by the macOS backup. The copied
`VICMEM.bin`, `VICLV.bin`, and `order.vnw` files are Manager-local bookkeeping
snapshots. Their unchanged bytes do not contradict the device deletion and do
not establish that a sidecar update is required for every delete. In
particular, the unchanged `order.vnw` retaining `_04` after the operation is a
verified observation, not a model instruction to remove or invent a sidecar
entry.

The native candidate establishes the following offline structural behavior:

- the target metadata node and its aligned content are removed;
- exact-boundary metadata pointers are rebased;
- unrelated records and shared payloads are preserved;
- established fixed-state references are rebased where observed;
- fresh category, mark, bookmark, selection, or other state must be preserved
  or safely rebased, never invented from a single deletion capture.

The candidate is a comparison artifact only. It is not an authorized sender
input and has never been transmitted by the modern client.

## Decision and remaining gates

Attempt 02 proves the persisted legacy deletion-effect evidence gate:

- one exact disposable target is removed;
- the native candidate exactly matches the post-delete dynamic blob;
- record count changes from 368 to 367;
- no path is added and no shared payload changes;
- complete pre/post backups and the device preview are preserved; and
- the observed Manager sidecars are unchanged and remain outside the device
  transaction model.

Missing explicit Manager success wording and the unavailable trustworthy
legacy request-4 result remain documented limitations. They do not invalidate
the independently verified persisted result and do not justify another legacy
capture. The `0x001d` difference is constrained to the single observed
transient-to-stable normalization above; no semantic field name is invented.

Milestone H is complete for its narrow offline scope. Commit `b5bae4b` adds
the exact candidate/binding/verifier slice, and commit `c8162c0` adds the
delete-specific fake-transport failure model. The complete suite passes **279
tests**. No delete model is promoted to a live product operation, no normal
GUI/CLI delete control is enabled, and no retry is justified. R15 remains
open: fake transport cannot establish physical atomicity, rollback, or
recovery. A separate explicit approval is required before any modern
live-delete smoke.
