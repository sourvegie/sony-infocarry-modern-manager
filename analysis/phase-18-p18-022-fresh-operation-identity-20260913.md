# P18-022 — Fresh Operation Identity Generalization

Date: 2026-09-13
Repository: `sourvegie/sony-infocarry-modern-manager`
Canonical base: `e98d310878ea92d541217b29155bee2b69007af8`
Branch: `task/P18-022-fresh-operation-identity`
Risk: **R3 host-side product/safety integration correction**

## Disposition

P18-022 is a host-only correction. It removes the normal product
facade/adapter dependency on the former dated validation target and operation
identifier. It does not authorize or perform hardware validation, and it does
not expand the supported capability envelope.

The preceding P18-021 record is intentionally preserved as a historical
documentation-only `ESCALATION_REQUIRED` stop. P18-021 stopped before
`READY_FOR_HARDWARE_TEST` because its normal UI/adapter path still carried a
stale milestone-specific target/operation binding. Its approval and
confirmation material is not imported as authorization by P18-022.

## Scope and invariants

The correction retains the canonical Library readiness, queue-plan,
candidate-builder, transaction-builder, verifier, execution coordinator,
claim-store, sender-marker, and installation-wide indeterminate-lock path.
There is no second sender, candidate, transaction, GUI bypass, retry route, or
alternate execution pipeline.

The supported boundary remains exactly:

- VNW-V15 only, with the reviewed Sony `0x054c:0x001e` model/session class;
- one explicitly selected prepared root package;
- exactly three direct children in TXT → BMP → TXT order;
- one absent destination root and no overwrite, delete, nesting, merge, or
  second package;
- one logical transaction, at most one sender call, explicit `0x0000`, and no
  automatic retry;
- no VNW-V10, restore, synchronization, broader shapes, or capability-matrix
  expansion.

## Implemented identity boundary

`LibraryTransferOperationBinding` now accepts an ordinary caller-supplied
target component subject to the reviewed CP932/native path-component limits.
It does not choose a target from a milestone allowlist. The confirmation is
derived from the current target (`ADD <current-target> ONCE`) and the logical
operation identifier is derived from the current reviewed profile, target,
device identity, child order, confirmation policy, fixed-state policy,
one-shot limits, and retry policy.

The binding rejects operation phrases carrying the historical P18-015, P18-018,
or P18-021 markers. A historical operation identifier or mismatched
confirmation cannot be supplied as a substitute for the derived current
binding. Merely documenting a historical phrase never creates authorization.

The reviewed operation identity is a second, composite hash over:

- the derived current binding and target;
- the prepared package manifest and exact ordered child bindings;
- the fresh complete verified backup/state identity;
- fresh typed native `0x0019` capacity provenance;
- candidate and transaction hashes and sizes;
- authorization and confirmation policy;
- core and outer preflight seals; and
- the reviewed auxiliary-state policy.

The immutable operation bundle contains the same current target, policy,
candidate, transaction, authorization, backup, capacity, and seal bindings.
The facade also checks that a prepared operation remains bound to the current
typed binding before it is actionable. Replacing the target, approval,
confirmation, policy, or derived identifier therefore invalidates the
prepared operation before claim consumption.

The adapter no longer imports the former dated target. Generic typed bundle
reloads reconstruct and validate the current binding; the adapter's historical
no-binding default remains only for existing low-level regression fixtures and
is not selected by the normal product facade.

## Staleness and historical rejection

The canonical lifecycle continues to rebuild and verify the exact candidate
and transaction from the current catalog selection, fresh backup, template,
and typed capacity evidence. Any changed target, package/child order,
selection, model/session identity, fresh backup/state identity, capacity
response, candidate, transaction, aux-state policy, or reviewed plan changes
the sealed bindings or makes the prepared facade operation non-actionable.

Historical P18-015/P18-018 operation identifiers and phrases cannot satisfy a
new derived binding. The old dated target is not privileged by the normal
facade/adapter, and the future physical target used in deterministic host
tests is treated as ordinary input rather than a production constant. Scalar
capacity values do not replace the typed fresh native capacity response.

## Host-only safety evidence

All P18-022 implementation and deterministic-fake validation is host/offline
evidence. The physical boundary is:

```text
device-changing operations = 0
real sender calls          = 0
real 0x101b transmissions  = 0
real claims consumed       = 0
real sender-marker writes  = 0
real installation-lock writes = 0
```

The preflight/review path remains before claim consumption, sender-marker
creation, sender entry, and lock mutation. The canonical claim/marker/lock
regressions remain covered by the existing adapter and coordinator suites.

## Required focused acceptance coverage

The P18-022 focused tests cover:

1. no former dated-target dependency in the normal facade, adapter, or ttk UI;
2. arbitrary valid fresh absent targets reaching host readiness through the
   normal facade with deterministic fakes;
3. target/binding replacement invalidating prepared actionability;
4. prepared-package/selection/plan changes invalidating fresh evidence;
5. historical P18-015/P18-018 identities and P18-021 documentation strings
   not authorizing a fresh operation;
6. scalar capacity not replacing typed fresh capacity provenance;
7. model/session/evidence mismatch and stale/replayed bundle rejection;
8. no claim consumption, marker mutation, sender call, or `0x101b` during
   host readiness validation; and
9. preservation of P18-017/P18-018/P18-019/P18-020 safety behavior, including
   one-shot, no-retry, post-write evidence, and installation-wide lock rules.

## Validation record

Targeted host suites completed during implementation:

- `test_library_transfer_execution.py`: 19 passing;
- `test_prepared_library_package_live_adapter.py`: 52 passing;
- `test_experimental_library_transfer.py`: 13 passing;
- `test_library_transfer_readiness.py`: 9 passing;
- `test_desktop_ttk.py`: 17 passing.

At the final local source state, the complete portable Python 3.12 suite
passed with 797 tests and 3 intentional skips. Compilation with a temporary
bytecode cache and `git diff --check` also passed. The normal facade/adapter/UI
historical-identity scan was clean, and the exact-head static/manual safety
review found no P0/P1/P2 issue in the local change set.

Final-head macOS CI, final-head Windows CI, and an independent exact-head
strong R3 review remain required. The branch has not been pushed, so those
external checks have not been run and this record remains
`ESCALATION_REQUIRED / PENDING_REMOTE_CI_AND_INDEPENDENT_R3`. No physical
validation is part of P18-022.

## Exit

P18-022 may be reported as `READY_FOR_HARDWARE_TEST` only after final-head
macOS/Windows CI and the independent strong R3 review are clean. That state
means host preparation is complete and no physical action has occurred; it is
not owner authorization and it is not hardware success. After that
disposition, stop for PM/owner direction. The later physical validation must
receive a new task number and a new owner approval phrase.
