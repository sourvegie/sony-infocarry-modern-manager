# Milestone H — selective deletion evidence audit

Date: 2026-08-22
Status: **Preparation active; evidence gate open; no live deletion performed.**

Milestone H is approved for offline preparation. The existing evidence does
not authorize a modern delete or prove the legacy delete protocol. Creation
success, synthetic structural deletion, and intentional removals in an add
capture are not deletion proof.

## Evidence inventory

| Area | Current evidence | Status and boundary |
| --- | --- | --- |
| Target scope | The device contains the disposable live-smoke item `root\IC_G_LIVE_20260822_01.txt`; owner capture 01 targeted it exactly once and preserved complete pre/post-attempt backups | Manager failed and the target remains; no successful deletion has been captured |
| Device record/blob | The native candidate removes exactly the target, preserves 310 shared payloads, removes an 88-byte aligned content segment, and rebases metadata pointers at the deleted-record boundary; the existing helpers produce a structurally valid but different 4-byte-longer result | Native deletion-shaped comparison is available offline; successful device equivalence is not proven |
| Fixed state | Native `0x001b`, `0x001c`, `0x001d`, and `0x001f` exactly match a metadata-reference-rebased pre-state; `0x001e` has one unresolved two-byte field | Actual post-attempt fixed objects changed in an unattributed/unresolved pattern; membership and field semantics remain unsafe to generalize |
| `VICMEM.bin` | `remove_vicmem_exact_path()` and `delete_file_bundle()` can remove exact selected-file paths while preserving opaque fields | Helper behavior is offline only; no legacy delete snapshot proves that Manager changes this file or which records it removes |
| `VICLV.bin` | `remove_viclv_exact_path()` can remove exact path entries while preserving header/category bytes | No native deletion snapshot or category-lifecycle evidence |
| `order.vnw` | The offline bundle preserves it byte-for-byte; generated-name parsing exists | Delete lifecycle and counter behavior are unresolved; no deletion mutation is inferred |
| USB transaction | Owner capture 01 preserves one parseable ordinary native `0x101b` transaction with ranges and declared `N=0`, `M=2,050,848` | It is a failed Manager attempt; no successful delete transaction is available for replay or authorization |
| Completion | The supplied attempt reports Manager “data transmission failed”; no delete success completion is established | Delete completion semantics remain unknown |
| Before/after device state | Complete pre/post-attempt backups are preserved; the target and dynamic blob are byte-identical, while four fixed response objects changed | The target was not removed; failure-state fixed-object changes remain unresolved |
| Manager sidecars | The four supplied before/after Manager files are byte-identical in attempt 01 | This is negative evidence for the failed attempt, not proof of successful-delete sidecar policy |
| Modern live proof | None | Product exposure remains disabled |

## Existing offline code and tests

The offline code is deliberately bounded and must not be promoted silently:

- `src/infocarry/backup_repack.py` has a pure leaf-file structural delete;
- `src/infocarry/vicdata.py` applies that transform through the observed XOR
  layer only;
- `src/infocarry/manager_bundle.py` optionally removes exact `VICMEM.bin` and
  `VICLV.bin` paths while preserving `order.vnw`;
- current tests cover synthetic metadata/content remapping, checksum validity,
  rejection of directories/unreachable targets, and exact sidecar-path
  filtering;
- there is no delete-specific candidate transaction builder, target-bound
  authorization, fake sender workflow, post-delete verifier, or live control.

These helpers establish useful offline invariants but do not establish the
native delete operation. In particular, a future delete candidate must not
reuse the add model's assumptions about fixed-state membership, completion,
range population, capacity, or Manager sidecars without independent evidence.

## Gate decision

The Milestone H evidence gate remains open. No modern delete candidate is
authorized, no delete control is exposed through the normal CLI/GUI, and no
modern device mutation has been performed. The safe next work is comparison-
only refinement of the native candidate and a delete-specific failure model.
The supplied attempt is not a successful deletion capture; a successful
isolated legacy delete remains required before any modern live-delete approval.
Restore, folder deletion, bulk delete, synchronization, and combined add/delete
experiments remain excluded.

## Attempt 01 update

Owner capture 01 is documented in
`analysis/phase-12-milestone-h-delete-attempt-01-2026-08-22.md`, with the
detailed comparison in
`analysis/phase-12-milestone-h-offline-analysis-2026-08-22.md`. It returned a
Manager failure, left the target present in the complete post-attempt backup,
and supplied a deletion-shaped native candidate. The native result removes an
88-byte aligned content segment rather than the helper's 85-byte occupied
segment, rebases metadata pointers at the deleted-record boundary, and
mostly follows the fresh fixed-state rebase except for one unresolved two-byte
field. It is useful failure evidence, not a successful delete capture. No
retry is authorized automatically.
