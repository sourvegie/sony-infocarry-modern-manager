# P18-025 — VNW-V15 UI Physical Validation

Date: 2026-09-14
Repository: `sourvegie/sony-infocarry-modern-manager`
Canonical base: `3e8fde113acdbf0c8b00f49dcf7cfe0629111806`
Preparation branch: `task/P18-025-v15-ui-physical-validation`
Documentation branch: `docs/p18-025-v15-physical-validation-evidence`
Boundary: **COMPLETE / PHYSICALLY VERIFIED**

## Fresh operation identity

P18-025 was a new operation. It did not reuse any P18-023 authorization,
confirmation, target, claim, seal, candidate, transaction, or operation
identity. P18-023 remains historical **BLOCKED before sender entry** because
the former normal catalog path rejected the package envelope as the duplicate
owner-visible sibling `00-package`. P18-024 corrected that representation
seam and is inherited as complete at the canonical base.

The exact P18-025 target is:

```text
IC_P18_LIBRARY_20260913_03
```

The exact selected prepared package is one absent destination root with these
direct children, in this order:

1. `01-introduction.txt`
2. `02-page-01.bmp`
3. `03-ending.txt`

The owner supplied the exact phrase once for the bounded physical operation:

```text
APPROVE P18-025 V15 UI PHYSICAL VALIDATION 01
```

The exact runtime confirmation is:

```text
ADD IC_P18_LIBRARY_20260913_03 ONCE
```

These strings are recorded as evidence of that completed run; their presence
in this record, source, tests, logs, or chat is not reusable authorization for
another operation.

## Completed physical validation

The exact reviewed normal UI/adapter/canonical guarded lifecycle completed one
operation for `IC_P18_LIBRARY_20260913_03` on canonical `main` at
`3e8fde113acdbf0c8b00f49dcf7cfe0629111806`. The repository was clean and no
production-code modification was made for the physical run.

Fresh live evidence identified Sony VNW-V15 `VID:PID 0x054c:0x001e`,
`bcdDevice 0x0100`, with the supported interface/session identity. Native
`0x0019` capacity was `3,145,728` bytes. The target was absent in the fresh
pre-write backup. The fresh candidate and transaction were rebuilt and bound
to the operation identity, bundle, and seals; the P18-024 `00-package`
projection correction was active with no duplicate owner-visible collision.

The operation used one logical sender call, one real `0x101b`, zero retries,
and returned native `0x0000`. The durable claim was consumed once. The sender
marker transitioned `none → in-flight → resolved`, with the final marker store
empty; the installation-wide indeterminate lock remained cleared. A complete
post-write backup was obtained and the independent verifier returned
`readback_verified`.

The target was created exactly once with the direct-child order
`01-introduction.txt` → `02-page-01.bmp` → `03-ending.txt`. The verified
prepared payloads were 22 bytes, 10,302 bytes, and 9 bytes respectively, with
SHA-256 values `d61ca2d514d000e1e92429eb0ade4022dbfd2e12641cf2c278fca54cfe193b8d`,
`d3f03cf2b000e38d06825353033fe1f2a64a3e50b58c1b407d4433fffd7a3ccb`, and
`098e0ed5001f9e1f17defd5f6492756d3cfb17aa1dad0f3521860f3c21281318`.
The verifier confirmed shared/unrelated state preservation, the reviewed
display-history/bookmark policy, no removed paths, and 343 shared paths.
The durable terminal result records independently verified success.

Preserved external evidence:

- `/Users/stardust/Projects/InfoCarry-Evidence/phase-18-p18-025-v15-ui-physical-validation-20260914-02/terminal-summary.json`
- `/Users/stardust/Projects/InfoCarry-Evidence/phase-18-p18-025-v15-ui-physical-validation-20260914-02/attempts/p17-017-attempt-e3a8a272d06d461fa0ca0c1c2ad39964/result-manifest-0001.json`

The attempt directory retains the older `p17-017` label from the evidence
allocator. It is historical evidence and must not be renamed or rewritten.

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

The committed host-only preparation checkpoint was
`28f84f49aa3d020a37ffa17f69d37216baf59cab`; it passed the focused execution,
projection, readiness, and adapter validation, the full Python 3.12 portable
suite (**806 tests, 3 intentional skips**), compilation, and whitespace
checks. It was published with passing macOS and Windows CI and independent
R3 `P0=0, P1=0, P2=0 — PASS`, then merged to canonical `main` at
`3e8fde113acdbf0c8b00f49dcf7cfe0629111806`. The physical run above then
recorded the single live transaction; no stale P18 operation identity was
reused.

## Physical safety boundary and disposition

The physical proof is limited to the exact reviewed VNW-V15 package/profile
and guarded lifecycle above. It does not establish arbitrary 1–8 file live
transfer, overwrite, deletion, nesting, multiple packages, VNW-V10 support,
restore/sync, or generalized ebook transfer. Any future operation requires a
new exact package, fresh evidence, separate owner authorization, and all
canonical gates. An ambiguous future sender outcome remains
`ESCALATION_REQUIRED` with no retry and read-only diagnosis only.

## Validation and release gate

For this documentation/evidence codification branch, run and record:

- focused P18-025/P18-024 readiness and projection tests;
- the complete Python 3.12 portable offline suite;
- Python compilation checks;
- stale/historical identity scans;
- `git diff --check` and documentation/static checks.

The physical run required no R3 hardware review because this follow-up changes
only documentation and accurately records the already completed exact proof;
it does not alter code or broaden capability semantics. The documentation
branch must stop for PM acceptance before merge.
