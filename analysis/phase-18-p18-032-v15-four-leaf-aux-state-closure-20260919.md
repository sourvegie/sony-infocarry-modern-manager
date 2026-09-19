# P18-032 — VNW-V15 Four-Leaf Auxiliary-State Policy Closure

Date: 2026-09-19
Risk: R3 host-side
Scope: narrow auxiliary-state policy binding correction; no physical operation.

## Binding

- Canonical base: `737746319162b7ffc65fded19fa47db19d2a69fc`
- Branch: `task/P18-032-v15-four-leaf-aux-state-closure`
- Device profile: reviewed Sony VNW-V15 (`0x054c:0x001e`)
- Validation profile: `experimental-vnw-v15-four-leaf-direct-validation-v1`
- Exact shape: `TXT → BMP → TXT → TXT`
- Historical evidence consulted read-only:
  `/Users/stardust/Projects/InfoCarry-Evidence/phase-18-p18-031-v15-four-leaf-physical-validation-20260919-t3D9X8`

## Root cause

P18-031 introduced `FOUR_LEAF_FIXED_STATE_POLICY` in
`src/infocarry/library_transfer_execution.py` and selected
`capture7_exact_all_zero_fixed_state` whenever the operation-specific
four-leaf profile was bound. The canonical candidate builder did not use that
policy: it reused the reviewed `assess_prepared_fixed_state` and
`rebase_auxiliary_state` path, including semantic display-history and bookmark
pointer preservation. On the reviewed synthetic/live-shaped evidence, the
sealed candidate therefore carried
`verified_display_history_0x001b_and_bookmark_0x001f_semantic_rebase_plus_zero_count_0x001c_to_0x001e`,
and the guard correctly stopped before sender because the binding and
candidate identities differed.

This was an adapter/binding ownership error, not a device or candidate
construction failure. The candidate, authorization, operation bundle, and
read-back layers already validate the semantic preservation policy and reject
unexpected auxiliary mutations.

## Correction

The operation binding now reuses the existing
`FRESH_AUXILIARY_STATE_POLICY` for both the established three-leaf profile and
the exact operation-specific four-leaf profile. The capture-7 label is no
longer introduced or required by the four-leaf binding. The actual candidate
policy remains included in the candidate audit, authorization, sealed bundle,
and operation identity; changing it makes the binding stale and stops the
guard before any callback.

No sender, USB, claim, marker, installation-lock, retry, device-profile,
VNW-V10, arbitrary-shape, overwrite, delete, merge, nesting, or capability-
matrix behavior changed. The exact four-leaf shape remains operation-specific
and authorization-gated; it is not hardware-proven by this task.

## Validation and publication

To be completed on the final published head:

- focused P18-032 policy and synthetic pre-write regression tests;
- P18-025 auxiliary-state, P18-030 profile, P18-031 execution, and relevant
  P18-026→P18-031 regressions;
- full Python 3.12 suite, `compileall`, and `git diff --check`;
- independent exact-head R3 review with `P0=0, P1=0, P2=0 — PASS`;
- final-head macOS and Windows CI;
- focused PR against canonical base, unmerged.

Physical boundary for this task is strictly zero: no USB/device-changing
operation, sender call, real `0x101b`, claim consumption, sender-marker
mutation, or installation-lock mutation.

Final host disposition: `READY_FOR_HARDWARE_TEST` after the publication and
review gates pass. This record does not claim physical verification.
