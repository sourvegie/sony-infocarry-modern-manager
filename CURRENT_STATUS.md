# Current Project Status

Date: 2026-09-02

## Canonical checkpoint

Canonical `main` is `5ad2dbc` (merged P18-001A). The P18-002 host/offline
implementation is complete on `codex/p18-002-experimental-transfer-foundation`
and is awaiting its review PR/CI boundary; no live device work is authorized
by this task.

## Current sprint

P18-002 defines the accelerated product-delivery policy and a host-only,
framework-independent transfer foundation. The initial machine-enforced
profile is `experimental-flat-root-folder-txt-bmp-v1` at
`src/infocarry/capability_profile.py` (profile SHA-256
`ec69e0076e57f2eeca1634966777413f205880303dd8be7528218c77b3a7abc4`). It
allows review of one explicitly grouped flat root folder with 1–8 ordered
strict TXT or validated 1-bit BMP children, but remains
`defined_not_live_enabled`.

The host façade records `PreparedItem[] → TransferPlan → CandidateLibrary →
Authorization → ExecuteOnce → ReadBackVerification` without USB access,
candidate bytes, sender construction, or a GUI/CLI write action. The
persistent indeterminate-write lock contract is defined separately and does
not auto-clear after restart or reconnect.

## Verified recent result

P18-001A’s bounded responsive Library correction is **COMPLETE** based on the
owner’s human-observed retest at approximately 980×680 and 1120×760 or
larger. This observation covers the tested GUI sizes only; it does not infer
hardware behavior, transfer execution, or other display environments.

The exact P17-018 TXT/BMP/TXT Library transfer remains the only integrated
Experimental physical proof. Physical opening of its folder and all three
children remains a separate human acceptance check where still noted by the
evidence records. The capability authority is
[`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md).

## Safety posture

- This task is R2 host/offline work. No hardware access, approval phrase,
  sender construction, `0x101b`, or live enablement is authorized.
- Unsupported shapes, nesting, automatic grouping, batch operations,
  overwrite/merge/delete, restore, synchronization, and recovery remain
  unavailable or preview-only with a reason.
- A later enabled Experimental operation must use fresh verified backup and
  capacity evidence, exact in-app confirmation, one logical transaction,
  explicit integer `0x0000`, complete post-write backup, independent semantic
  read-back, and no automatic retry. Backup is not undo.
- Any ambiguous live outcome requires persistent per-device read-only
  diagnosis before a documented recovery decision can clear the lock.

## Delivery and review

The two active streams are Product Delivery and Legacy Oracle. The required
sequence is recorded in the P18-002 ADR: close visual usability, resolve
licensing/hermetic/Windows CI concerns, define the capability profile and
façade, add selection/order/prepare/preview, then separately review guarded
execution, offline tamper coverage, Oracle comparison, and one combined GUI
hardware smoke before standing Experimental enablement.

Portable baseline before P18-002 changes: 644 passing, 3 intentional skips.
Current P18-002 validation: 665 passing, 3 intentional skips; focused profile,
foundation, lock, and Experimental checks pass; compilation, diff hygiene, and
excluded-evidence audit pass. Independent R2 verification is PASS, including
the exact-`True` lock-evidence correction.

## Historical records

The pre-P18-002 long-form status, risk register, and roadmap are preserved in
[`analysis/archive-current-status-through-p18-001a-20260902.md`](analysis/archive-current-status-through-p18-001a-20260902.md),
[`analysis/archive-risk-register-through-p18-001a-20260902.md`](analysis/archive-risk-register-through-p18-001a-20260902.md),
and [`analysis/archive-roadmap-through-p18-001a-20260902.md`](analysis/archive-roadmap-through-p18-001a-20260902.md).
