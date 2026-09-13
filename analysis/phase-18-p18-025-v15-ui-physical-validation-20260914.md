# P18-025 — VNW-V15 UI Physical-Validation Preparation

Date: 2026-09-14  
Repository: `sourvegie/sony-infocarry-modern-manager`  
Canonical base: `dcef4e6594b9ba3b95a885efe9dab3deb4d3a760`  
Branch: `task/P18-025-v15-ui-physical-validation`  
Boundary: **HOST-ONLY**

## Fresh operation identity

P18-025 is a new operation. It does not reuse any P18-023 authorization,
confirmation, target, claim, seal, candidate, transaction, or operation
identity. P18-023 remains historical **BLOCKED before sender entry** because
the former normal catalog path rejected the package envelope as the duplicate
owner-visible sibling `00-package`. P18-024 corrected that representation
seam and is inherited as complete at this canonical base.

The exact P18-025 target is:

```text
IC_P18_LIBRARY_20260913_03
```

The exact selected prepared package is one absent destination root with these
direct children, in this order:

1. `01-introduction.txt`
2. `02-page-01.bmp`
3. `03-ending.txt`

The later physical stage would require the exact owner phrase:

```text
APPROVE P18-025 V15 UI PHYSICAL VALIDATION 01
```

The exact runtime confirmation is:

```text
ADD IC_P18_LIBRARY_20260913_03 ONCE
```

Neither string authorizes execution merely by appearing in this record,
source, tests, logs, or chat. No physical authorization exists in this task.

## Capability and safety boundary

The reviewed boundary remains unchanged:

- Sony VNW-V15 only, exact `0x054c:0x001e`;
- one explicitly selected absent destination root;
- exactly three direct children in TXT → BMP → TXT order;
- no overwrite, deletion, nesting, merge, second package, grouping, VNW-V10,
  broader package shapes, retry, restore, synchronization, or recovery
  expansion;
- one logical transaction, at most one sender call, at most one real
  `0x101b`, and zero retries.

The normal host path under test is:

```text
Select → Arrange → Prepare → Preview → Review transfer
→ catalog/package projection → fresh preflight abstraction
→ operation identity/bundle/seals → confirmation → guarded readiness
```

The existing typed fresh native `0x0019` capacity provenance, dynamically
bound operation identity, persistent installation-wide indeterminate lock,
persistent sender-start marker, durable one-shot claim, stale-operation
rejection, no automatic retry after possible sender start, and independent
terminal semantic readback remain the only reviewed safety boundary.

Any change to target, prepared package, selection, device/session, baseline or
backup, capacity, candidate, transaction, auxiliary-state policy, confirmation,
or seal invalidates the prior readiness and requires a fresh operation.

## P18-024 regression proof

The focused catalog/package tests preserve and extend the P18-024 proof:

1. `IC_P18_LIBRARY_20260913_03` passes the normal catalog/package projection
   and queue gate without the former `duplicate sibling name in Library:
   00-package` failure.
2. The manifest logical target folder is the owner-visible Library package
   identity and the destination is `root\\IC_P18_LIBRARY_20260913_03`.
3. The physical package-envelope basename remains `00-package` storage
   detail only; it is not the Library sibling identity.
4. Genuine duplicate owner-visible package roots still fail closed.
5. Internal/generated package nodes cannot collide with each other or with an
   owner-visible payload/folder name under the supported profile.
6. Duplicate payload child names remain rejected by package composition.

The P18-025 facade fixture also exports the package beneath a `00-package`
envelope, then carries the manifest identity through the normal catalog,
queue, fresh preflight, candidate, transaction, bundle, and review objects.

## Identity and safety regression proof

The focused execution suite proves that:

- the fresh `_03` target reaches host readiness through the normal facade;
- changing the target or prepared package makes the reviewed operation stale;
- stale P18-015, P18-018, P18-021, P18-022, and P18-023 approval/confirmation
  material fails closed;
- stale scalar or historical capacity cannot substitute for fresh typed
  native `0x0019` evidence;
- changed device/session, backup, capacity, candidate, transaction, or
  auxiliary-state evidence cannot unlock an earlier operation;
- host readiness consumes no real claim and mutates no real sender marker or
  installation-wide lock;
- sender calls and real `0x101b` remain zero during host preparation;
- started-operation ambiguity retains the marker/lock, escalates, and never
  retries;
- the normal UI remains wired to the one facade and does not add a direct
  GUI bypass or second sender/candidate/transaction pipeline.

The prior P18-017 through P18-024 suites remain regression coverage. The
P18-024 catalog tests specifically retain the old `00-package` reproduction,
corrected projection, true duplicate sibling, and internal/generated-node
collision cases.

At committed host-only head `e9e7833a2e1d4dc6fad26f81c9801d39e5509552`,
focused execution/projection/readiness/adapter validation passed, the full
Python 3.12 portable suite passed with **806 tests and 3 intentional skips**,
and the focused host path recorded zero sender calls, zero real `0x101b`, zero
real claims, zero sender-marker mutations, and zero installation-wide lock
mutations.

## Physical boundary

This task performs strictly zero:

```text
USB/device-changing operations = 0
sender calls                   = 0
real 0x101b transmissions      = 0
real claims consumed           = 0
sender-marker mutations        = 0
installation-wide lock changes = 0
```

The later physical gates are documented only, not executed: exact device and
session identity, fresh complete pre-backup/baseline, fresh native `0x0019`,
live target absence, fresh candidate and transaction, auxiliary-state review,
clear lock, inactive marker, valid claim store, immediate exact confirmation,
final pre-send revalidation, sender ≤ 1, real `0x101b` ≤ 1, and retries = 0.

If a future sender may have started and the result is ambiguous, the only
valid disposition is `ESCALATION_REQUIRED`: no retry, marker retained or
updated, installation-wide lock retained or set, and read-only diagnosis only.

## Validation and release gate

At the host-only checkpoint, run and record:

- focused P18-025/P18-024 readiness and projection tests;
- the complete Python 3.12 portable offline suite;
- Python compilation checks;
- `git diff --check`;
- stale/historical identity scans;
- final-head macOS CI and Windows CI;
- a fresh independent strong R3 review of the exact published head.

Local compilation and `git diff --check` pass. `CAPABILITY_MATRIX.md` is
byte-for-byte unchanged from the canonical base. Final-head CI, publication,
and independent R3 remain external release gates; they are not inferred from
the local suite.

The required independent review result is:

```text
P0=0, P1=0, P2=0 — PASS
```

`CAPABILITY_MATRIX.md` is not modified by P18-025. No merge and no physical
transaction are permitted. The final disposition becomes
`READY_FOR_HARDWARE_TEST` only after local validation, publication, both
final-head CI results, and the independent R3 result are all green. Then stop
for explicit owner authorization.
