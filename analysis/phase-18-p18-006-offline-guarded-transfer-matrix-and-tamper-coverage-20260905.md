# P18-006 — Offline Guarded-Transfer Matrix and Tamper Coverage

Date: 2026-09-05
Base: canonical `main` at `63b7e7a` (merged P18-005 / PR #31)
Branch: `task/P18-006-offline-tamper-matrix`
Disposition: **HOST_R3_REVIEW_PASS_WITH_P2_CARRY_FORWARD**

## Scope and boundary

P18-006 is an offline/fake regression boundary for the merged P18-005
coordinator. It does not add capability or authorize a physical operation.
The only executable logical shape remains one new absent root folder with
exact ordered children:

```text
TXT → BMP → TXT
```

The tests inject detection, capacity, backup, and fake transport boundaries.
They do not open USB, transmit `0x101b`, run a real sender, or perform
hardware interruption/recovery experiments.

## Matrix disposition

The maintainable table-driven cases live in
`tests/test_p18_006_guarded_transfer_matrix.py`. Each negative case checks the
rejection seam, confirmation reachability, actual fake sender count, global
lock state, and automatic-retry prohibition. The matrix also includes one
exact positive control so it cannot pass by rejecting every operation.

| Category | Main adversarial coverage | Expected/observed safety disposition |
| --- | --- | --- |
| A Shape/profile | Non-exact counts, TXT/BMP order/type/name/path changes, nested and multiple roots, grouping/batch/overwrite/merge/delete, broader flat and hierarchical preview | `eligibility`; no confirmation or sender; no lock; preview only |
| B Model/profile | V10, unknown model/capability, substituted hierarchical profile, tampered V15 profile value | `model_profile`/`capability_profile`; no sender; V10 remains non-write-capable |
| C Content/manifest | TXT/BMP prepared/source drift, child and destination fields, logical manifest, strict sealed-report extra field | `preflight_load`/`operation_bundle`/`eligibility`; no sender; no lock |
| D Bindings | Independently valid plan/bundle/preflight objects crossed between transactions | `eligibility`; no confirmation or sender; no lock |
| E Backup evidence | Stale, incomplete, integrity-invalid, wrong-session, missing, substituted object, and non-boolean diagnostic evidence | Preflight/backup gate; no sender; no authorization; no auto-clear |
| F Capacity | Missing/malformed/altered response, exact boundary, beyond-boundary and arithmetic checks | Existing capacity semantics preserved; exact allowed boundary passes offline arithmetic; unsafe evidence stops before sender |
| G Drift/conflict | Plan change after confirmation, target/baseline/unrelated-content/device changes before send | `confirmation_revalidation` or `preflight_revalidation`; no sender; no lock |
| H Confirmation/replay | Decline, malformed callback return, callback-time plan change, premature approval/confirmation, repeated operation | Confirmation remains transaction-specific; no early sender; one successful operation cannot be replayed |
| I Global lock | Reopen, reconnect, V10/different model, missing/wrong diagnostic binding and attempted clear | Installation-wide lock persists; only complete bound read-only evidence plus decision can clear |
| J Transport/completion | `0x0000`, nonzero integer, `None`, bool, string, object, header/bulk errors, timeout, disconnect, cancellation, missing completion | `0x0000` succeeds; nonzero integer is determinate failure; malformed/ambiguous after-start results are indeterminate and lock |
| K Execute-once | Sender instrumentation, concurrent calls, second invocation, timeout/disconnect/missing completion/cancellation | At most one sender attempt; no implicit retry; consumed claim rejects a second call |
| L Post-backup | Missing, incomplete, integrity-invalid, wrong-session, parser-failed, and stale pre-operation post-backups | Sender count remains one; resulting state is indeterminate; global lock is recorded |
| M Independent read-back | Root/child/path/type/order/payload/metadata/unrelated-content tamper, altered expectation, claimed completion type | Independent verifier rejects; sender claims cannot establish success |
| N Auxiliary state | Fixed-state tamper and bounded manager-sidecar/display-history policy | Existing exact fixed-state policy is enforced; no new preservation/zeroing rule is inferred |
| O GUI/CLI isolation | Normal surfaces, review-only hierarchy, no standing send/debug bypass, import graph | Normal GUI/CLI remains review-only for this path; no USB access on import |

Duplicate completion callback is not applicable: the current injected sender
contract returns one completion value and exposes no completion callback. The
matrix covers malformed and missing completion at that seam instead.

## Findings and corrections

The first failing regressions identified two R3 safety defects already implied
by the merged boundary contract:

1. `GuardedLibraryExecutionCoordinator` checked a V15 profile ID and transfer
   capability but accepted a structurally altered profile value. The smallest
   correction requires the exact reviewed `VNW_V15_PROFILE` value.
2. The live adapter treated a boolean or non-integer completion returned after
   the sender claim as ordinary `failed`. Because the sender had already
   claimed the one-shot transaction, those values are not a known native
   status word. They now classify as
   `indeterminate_after_transaction_start`, recording the existing global
   persistent lock. A nonzero integer remains a determinate device-reported
   failure and does not create that lock.

No candidate, authorization, sender, lock architecture, retry policy, or
capability shape was broadened. Both corrections are covered by failing-then-
passing regression cases in the new matrix.

## Positive control

The exact fake TXT/BMP/TXT operation completes once with integer `0x0000`, a
complete post-operation backup, independent semantic read-back, one actual
fake sender invocation, three backup captures, and no remaining indeterminate
lock. A later invocation is refused by the consumed one-shot claim.

## Independent review

The independent R3 review passed with no correction round required. The
review confirmed the exact-profile gate, completion classification, fake
transport seams, persistent-lock behavior, retry resistance, concurrent-call
coverage, independent read-back, and positive control. It also confirmed that
no hardware or USB operation occurred.

The reviewer recorded one P2 carry-forward limitation: the one-shot claim is
process-local and the coordinator persists the indeterminate lock only after
receiving an exception. A process crash or separate process could therefore
reuse a bundle before the lock is persisted. P18-006 covers thread-level
concurrency and lock-store reopen, but not crash recovery or cross-process
claim persistence. This does not block the host-only P18-006 outcome because
normal GUI/CLI surfaces do not expose this coordinator. It must be resolved or
explicitly accepted before standing physical-write enablement.

## Review and remaining gates

Because production safety code changed in profile gating and completion
classification, this was an R3 delta. No hardware validation is part of
P18-006. After host review and CI, the next product gate is offline Legacy
Oracle differential/comparison, followed later by one combined owner-approved
hardware validation.
