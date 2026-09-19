# P18-031 — VNW-V15 Exact Four-Leaf Live Execution Closure

Date: 2026-09-19
Risk: R3
Scope: host-only implementation and review; no physical write performed.

## Binding

- Canonical base: `9e276931675bf10d50a961bf4533f8f42e856294`
- Branch: `task/P18-031-v15-four-leaf-live-execution`
- Device profile: reviewed Sony VNW-V15 (`0x054c:0x001e`)
- Validation profile: `experimental-vnw-v15-four-leaf-direct-validation-v1`
- Target: `IC_P18_4LEAF_20260918_01`
- Exact shape: `TXT → BMP → TXT → TXT`

The prior P18-030 physical authorization was not reused. P18-031 intentionally
does not open a live write boundary or claim physical validation.

## Implementation

The exact four-leaf profile is admitted by the existing guarded Library path
through profile-driven checks only. The implementation reuses the existing
candidate, transaction, authorization, durable execution claim, sender-start
marker, installation-wide indeterminate lock, one-shot sender, and independent
read-back machinery. The four-leaf profile binds its capability hash and
prepared artifact identity into the Library binding and authorization. The
normal product readiness/UI profile remains the existing three-leaf shape;
four-leaf readiness is operation-specific and explicit-owner gated.

The shared adapter routes the exact four-leaf result through the P18-030
semantic verifier and preserves the established no-retry and terminal
`readback_verified` rules. Unsupported counts, permutations, nesting,
overwrite/conflict, VNW-V10, and arbitrary future 1–8 shapes remain blocked.
The existing fake workflow now accepts the same profile-specific candidate,
authorization, and read-back callbacks, so host rehearsal preserves the exact
four-leaf binding instead of falling back to the generic three-leaf verifier.

## Physical boundary

No USB device-changing operation was attempted. No real sender call or real
`0x101b` was made, and no physical-device claim, sender marker, or installation
lock was created. Synthetic tests use the existing fake backend and temporary
host-side safety stores only.

## Validation record

- Focused P18-031 synthetic execution and guard coverage: 8 passed.
- Relevant bridge/adapter/review/execution regressions: 122 passed, then the
  bridge and P18-031 correction set: 20 passed.
- Full portable suite: 878 passed, 3 pre-existing skips.
- `compileall`: passed.
- `git diff --check`: passed.
- Static review: one canonical `AuthorizedWriteSender` path in the shared
  adapter; no new USB/claim/marker/lock path; no broad arbitrary 1–8 live
  enablement; no VNW-V10 execution path.

Independent R3 review was completed in two bounded rounds. The first round
identified typed-binding, test-coverage, and fake-workflow propagation gaps;
all were corrected and revalidated. The final round reported no material
findings.

This record does not claim physical proof; disposition is
`READY_FOR_HARDWARE_TEST` pending a separate operation-specific owner approval
and approved physical procedure.
