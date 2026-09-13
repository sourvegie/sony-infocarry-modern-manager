# P18-023 — VNW-V15 UI-Driven Physical Validation Preparation

Date: 2026-09-13
Repository: `sourvegie/sony-infocarry-modern-manager`
Canonical base/main: `011dd531f7257b919e262ed4349abc153642e668`
Branch: `task/P18-023-v15-ui-physical-validation`
Risk: **R3 physical-validation preparation**
Preparation boundary: **HOST-ONLY**

## Final disposition

P18-023 is concluded as **BLOCKED before sender entry**. The normal
facade/catalog path failed closed with:

```text
duplicate sibling name in Library: 00-package
```

This is not success and not an ambiguous post-send escalation. Sender calls,
real `0x101b`, retries, claim creation/consumption, sender-marker mutation,
installation-wide lock mutation, and device mutation were all zero. Fresh live
V15/session evidence was not reached; capacity, live target absence, backup,
candidate, transaction, verifier, and post-backup were not reached. The
sender marker remained `none`, the installation-wide lock remained `cleared`,
and P18-023 authorization and confirmation are concluded and must not be
reused.

The preparation intent below is preserved as historical context only and is
superseded by this blocked disposition. P18-024 records and corrects the
catalog representation seam without performing physical validation.

## Original preparation intent (superseded)

P18-021 remains a historical `ESCALATION_REQUIRED` stop. P18-022 is
`COMPLETE` on canonical `main` after PR #48. P18-023 is a new host-only
preparation task for a fresh physical operation. Its intended host exit is
`READY_FOR_HARDWARE_TEST`; that state is not physical success and is not owner
authorization.

This task does not access USB or hardware, invoke a sender, consume a real
claim, create or mutate a real sender marker, mutate the installation-wide
indeterminate-write lock, or transmit a real `0x101b`. Deterministic fakes are
used only in isolated tests. No physical transaction is performed here.

## Fresh operation binding

The proposed physical target is:

```text
IC_P18_LIBRARY_20260913_02
```

The prior `IC_P18_LIBRARY_20260913_01` target belongs to concluded P18-021
documentation and is not reused. `IC_P18_LIBRARY_20260910_01` remains
historical and is not privileged by the normal path.

The exact proposed package is one prepared root with these direct children in
this order:

1. `01-introduction.txt`
2. `02-page-01.bmp`
3. `03-ending.txt`

The later physical stage would require this new owner approval phrase:

```text
APPROVE P18-023 V15 UI PHYSICAL VALIDATION 01
```

The current runtime confirmation is derived from the current target and must
be exactly:

```text
ADD IC_P18_LIBRARY_20260913_02 ONCE
```

The presence of either string in this document, tests, source, logs, or chat
does not authorize execution. No physical authorization exists until the
Project Owner explicitly sends the owner approval phrase.

## Capability and safety boundary

The supported envelope is unchanged:

- exact Sony VNW-V15 identity `0x054c:0x001e` only;
- one explicitly selected prepared root package;
- exactly three direct children in TXT → BMP → TXT order;
- one destination root that must be absent in fresh state;
- no overwrite, delete, nesting, merge, grouping, second package, VNW-V10,
  broader package shape, automatic retry, restore, synchronization, or
  recovery expansion;
- one logical transaction, at most one sender call, at most one `0x101b`, and
  zero retries.

The normal lifecycle under test is:

```text
selection → arrange → prepare → preview → review transfer
→ fresh live preflight abstraction → immutable operation identity/bundle/seals
→ exact transaction-specific confirmation → guarded coordinator readiness
```

Fresh host evidence must bind the exact device/session, complete verified
backup and baseline state identity, typed native `0x0019` capacity provenance,
immediate target absence, rebuilt candidate and transaction, reviewed
auxiliary-state policy, clear global lock, inactive sender marker, valid claim
store, and a fresh unconsumed operation identity. Any change to the target,
prepared package, selection, device/session, backup, capacity, candidate,
transaction, auxiliary policy, confirmation, or seal invalidates the prior
readiness/binding.

The canonical `PersistentWriteSafetyOwner` claim/marker/lock boundary remains
the only execution safety boundary. Host readiness occurs before that write
boundary and must leave all real state untouched. If a later physical sender
may have started and the outcome is ambiguous, the only valid disposition is
`ESCALATION_REQUIRED` with zero retry, preserved sender marker, retained global
indeterminate lock, and read-only diagnosis.

## Implemented preparation

P18-022 already generalized the normal Library facade and adapter from a
milestone-bound target to a typed, dynamically supplied operation binding.
P18-023 carries that path forward with the fresh target and exact owner phrase
only in deterministic host fixtures; it does not add a production target
allowlist or a second transfer pipeline. The binding now also rejects
historical P18-022 approval markers, alongside P18-015, P18-018, and P18-021.

The preparation tests exercise the normal facade/adapter/coordinator path and
prove that the target and current package identity reach host readiness without
USB, sender, claim consumption, marker mutation, lock mutation, or real
`0x101b`. The existing P18-017 through P18-022 suites remain in scope for
regression validation.

## Required host-only acceptance coverage

The focused coverage proves:

1. `IC_P18_LIBRARY_20260913_02` reaches host readiness through the normal
   facade with deterministic fakes and no write-boundary activity.
2. `IC_P18_LIBRARY_20260913_01` and the historical `20260910` target are not
   privileged; current operation identity and confirmation are target-bound.
3. Changing the target or prepared package invalidates readiness,
   authorization, or sealed actionability.
4. Historical P18-015/P18-018/P18-021/P18-022 identities and phrases fail
   closed.
5. Fresh typed native `0x0019` capacity provenance remains required; scalar or
   historical capacity cannot unlock readiness.
6. Changed device/session, backup/state, capacity, candidate, transaction, or
   auxiliary-state bindings cannot validate an earlier operation.
7. P18-020 global claim/marker/lock protections, no-retry semantics, and
   indeterminate handling remain intact.
8. Confirmation text is derived from the current target and cannot be
   replaced by an older phrase.
9. No GUI/direct-facade bypass or second sender/candidate/transaction pipeline
   is introduced.
10. The complete P18-017 through P18-022 regression set remains green.

## Validation record

Local validation completed on the working tree:

- focused facade/adapter/review/readiness/UI/claim-marker-lock suites: **112
  passing**;
- full portable Python 3.12 suite: **799 passing, 3 intentional skips**;
- Python compilation: **pass**;
- `git diff --check`: **pass**;
- production stale-target scan: **clean**;
- `CAPABILITY_MATRIX.md`: **unchanged**;
- physical boundary: **zero real device-changing operations, sender calls,
  claims, markers, locks, and `0x101b` transmissions**.

Final-head macOS CI, final-head Windows CI, and a fresh independent strong R3
review must report:

```text
P0=0, P1=0, P2=0 — PASS
```

Those external checks are pending publication of this local branch. Only after
they pass may this preparation be reported as `READY_FOR_HARDWARE_TEST`. A
CI/review-pending state is not ready and does not authorize hardware.

## Exit

Stop at `READY_FOR_HARDWARE_TEST` after host validation. Do not perform the
physical transaction. Report the branch, exact head, PR/push status, tests,
CI/R3 result, and repeat the exact owner approval phrase required for the
later physical stage. The next physical action requires a separate explicit
owner message:

```text
APPROVE P18-023 V15 UI PHYSICAL VALIDATION 01
```
