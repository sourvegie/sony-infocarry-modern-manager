# P18-030 — VNW-V15 four-leaf direct-content capability preparation

Date: 2026-09-19  
Risk: R3 host-side preparation  
Canonical base: `4d8f432040f715380e03796a855f9dd26ede82f3`  
Branch: `task/P18-030-v15-four-leaf-capability-preparation`  
Outcome while preparing: host-only; physical stage not performed

## Scope and safety disposition

This record prepares exactly one future VNW-V15 validation shape:

`one absent root → TXT → BMP → TXT → TXT`

The operation is validation-only and is not a normal UI or live-send
capability. No device was connected or probed. No USB/device-changing
operation, real `0x101b`, sender call, claim consumption, sender-marker
mutation, or installation-wide lock mutation occurred. No retry or recovery
behavior was changed. `CAPABILITY_MATRIX.md` is unchanged.

The existing `TXT → BMP → TXT` product/readiness boundary remains unchanged.
`TransferShapeAssessment` continues to classify the four-leaf direct shape as
`plausible_future_vnw_v15_direct_leaf`, requiring separate validation rather
than treating it as verified/live-enabled.

## Exact validation profile

Profile ID: `experimental-vnw-v15-four-leaf-direct-validation-v1`  
Profile status: `validation_only_not_live_enabled`  
Profile SHA-256: `ac7b37934e9800d906f80c663561097eb6a0b59aff4c6502e09fb4c4da4f1475`

The descriptor binds the reviewed `sony-vnw-v15-reviewed-v1` model, one
root-level absent target, four flat direct children, the existing CP932/path/
size/BMP rules, fresh complete backup and native `0x0019` capacity evidence,
exact candidate and transaction hashes, and an exact authorization identity.
It records candidate construction and authorization as host-validation stages
but keeps execution and device change disabled. The normal `PreparedItem`,
`TransferPlan`, and `TransferFoundation` seams can represent the profile, and
the foundation's `execute_once` descriptor remains disabled.

## Deterministic disposable artifact

Target root: `IC_P18_4LEAF_20260918_01`  
Artifact identity: `4b1aecada00bed36f1c053385453f75028bfebda6488b2fcbf471409f431c7f8`  
Aggregate prepared payload: `10,380` bytes

| Order | Kind | Name | Prepared bytes | SHA-256 |
|---:|---|---|---:|---|
| 0 | TXT | `01-introduction.txt` | 28 | `d1da9961f4668d7ea958616b5dbcdacb2d3a238b0fa98e23c870ff9f023ee865` |
| 1 | BMP | `02-page-01.bmp` | 10,302 | `d3f03cf2b000e38d06825353033fe1f2a64a3e50b58c1b407d4433fffd7a3ccb` |
| 2 | TXT | `03-ending.txt` | 22 | `d05cfdda174d647638ee7e6cca3417c277eba467c824245c50a73c111b0519a2` |
| 3 | TXT | `04-extra.txt` | 28 | `509bac0ce28701cf352d971b15119ee8d8e11bb892affb99aacad238ee1123f3` |

The text sources are short ASCII/CP932-safe disposable sentences identifying
the introduction, ending, and fourth leaf. The BMP is the existing exact
237×320, one-bit, uncompressed Windows BMP fixture. The artifact identity
changes when the fourth payload, child order, or root name changes.

## Reused architecture

The new exact profile binding is layered over the existing path:

`PreparedContentArtifact`
→ `TransferShapeAssessment`
→ normal readiness (four leaves remain blocked)
→ `TransferFoundation` host-only plan
→ existing ordered multi-package candidate builder
→ existing exact multi-package authorization gate
→ disabled canonical execute-once descriptor
→ existing independent multi-package read-back verifier

The new `four_leaf_validation.py` module has no USB, transport, sender,
claim-store, marker, or lock import. It adds no second candidate builder or
sender. Its authorization identity includes the validation profile, artifact,
device/baseline, capacity evidence, candidate blob, transaction, fixed-state,
and explicit confirmation bindings. The shared verifier now formats one
malformed-payload failure path correctly; the success and three-leaf logic is
unchanged.

## Host validation evidence

Focused P18-030 tests cover deterministic artifact/order/identity, exact
profile acceptance and rejection of three/five/reordered/nested/unsupported
shapes, future-shape assessment, normal four-leaf readiness blocking and
three-leaf eligibility, host-only foundation state, deterministic candidate
and transaction identity, backup/capacity/candidate authorization invalidation,
no second sender/hardware path, exact synthetic four-leaf read-back, and
missing-fourth/altered-fourth/reordered/unexpected-sibling failures.

The focused test result at this checkpoint is 11 passed. The full portable
suite is 870 passed with 3 existing intentional skips. `compileall`,
`git diff --check`, and the unchanged `CAPABILITY_MATRIX.md` check are clean;
the static boundary scan finds no transport, claim, marker, lock, or sender
path in the new validation module. The independent local review of the
corrected working tree is `P0=0, P1=0, P2=0 — PASS`; final-head macOS/Windows
CI, fresh post-publication R3 review, and publication identifiers remain
pending and must be recorded before the task can stop at
`READY_FOR_HARDWARE_TEST`.

## Publication and physical gate

The exact branch may be published only after local validation is complete and
must be reviewed at its exact published head against canonical `main`. Do not
merge. A future physical operation requires a separate operation-specific
owner authorization naming `IC_P18_4LEAF_20260918_01`; this host-preparation
task is not that authorization.
