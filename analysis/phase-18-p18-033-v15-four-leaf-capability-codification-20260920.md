# P18-033 — Verified VNW-V15 Four-Leaf Capability Codification

Date: 2026-09-20  
Risk: R2 host-only capability promotion  
Branch: `task/P18-033-v15-four-leaf-capability-codification`  
Canonical base: `a57a1ec2bbe3bfcfef5633d58136aeb48ff443a4`

## Scope and evidence

This task promotes exactly one already physically verified VNW-V15 shape into
the normal reviewed capability surface:

```text
TXT → BMP → TXT → TXT
```

The evidence namespace supplied for this task is preserved read-only at:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-18-p18-032-v15-four-leaf-physical-validation-20260920-75FHwI`

The codified profile is:

- profile ID: `verified-vnw-v15-four-leaf-direct-v1`;
- status: `physically_verified_live_supported`;
- profile SHA-256: `74159694d370665a0055030c6091f564293af1a7e97a4ac5af35280bc21e5a39`;
- exact child kinds: `TXT → BMP → TXT → TXT`;
- exact root-level, one-package, absent-target semantics;
- no arbitrary 1–8 generalization.

The physical proof supplied with the task covers one reviewed VNW-V15 unit and
one narrow operation: one logical sender, one real `0x101b`, zero retries,
explicit native `0x0000`, complete post-write backup, independent read-back,
and preservation of shared/unrelated auxiliary state. This task does not
repeat or claim a physical operation.

## Implementation decision

Normal readiness now classifies both the established
`TXT → BMP → TXT` shape and the promoted four-leaf shape as exact verified
profiles. It selects the four-leaf capability profile for the latter and
retains fresh-backup, capacity, conflict, stale-state, typed-binding, and
transaction-specific confirmation requirements.

The four-leaf normal route reuses the existing generic seams:

- canonical transfer-shape assessment;
- `build_prepared_multi_package_candidate`;
- `authorize_prepared_multi_package`;
- the existing guarded multi-package workflow and sender;
- `verify_prepared_multi_package_readback` and wrapper reconciliation.

The historical `four_leaf_validation` module remains available only as a
compatibility adapter for P18-030/P18-031 evidence and direct regression
coverage. It is no longer selected by normal readiness, the Library bridge,
or the live adapter. No second sender, USB path, claim path, marker path, or
lock path was added.

The profile records `live_supported`, exact candidate/authorization/write
policy, and normal shape exposure, while the host foundation continues to
keep `live_enabled` false and the default UI Transfer action disabled. A
future physical attempt still requires fresh operation-specific evidence,
owner approval, and all existing guarded lifecycle gates.

## Preserved boundaries

- VNW-V10 remains `UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED` and does
  not inherit VNW-V15 rules.
- Reordered four-leaf shapes, arbitrary four-leaf permutations, five leaves,
  nesting, overwrite/conflict targets, delete/merge/restore/synchronization,
  and broader counts remain blocked.
- The P18-032 semantic auxiliary-state policy remains canonical; no new
  capture-7 or fixed-state path was introduced.
- No automatic retry is allowed after transfer start when the result is
  indeterminate.
- P18-025, P18-030, P18-031, and P18-032 safety behavior remains covered by
  regression tests.

## Acceptance coverage

The focused acceptance/regression coverage verifies:

1. exact three-leaf and four-leaf normal readiness;
2. no validation-only product status/copy;
3. shared generic candidate, authorization, sender, and read-back seams;
4. rejection of reorder, five-leaf, nested, unsupported, overwrite, stale
   backup, and stale capacity cases;
5. unchanged auxiliary-state, VNW-V10, no-second-route, one-shot, completion,
   claim, marker, and lock safeguards;
6. no physical counters or evidence mutations.

## Validation and review

Required host validation is:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python -m compileall -q src
git diff --check
```

Validation completed on the current working tree: focused acceptance and
P18-025→P18-032 regression coverage passed; the full portable suite ran 883
tests with 880 passed and 3 documented skips; `compileall` passed; and
`git diff --check` passed. No merge is authorized by this record.

Fresh independent exact-head R2 review passed with `P0=0, P1=0, P2=0`.
There are no remaining review findings; PM acceptance is the remaining gate.

## Publication

- Commit: `a0ddf7f8670d5b0d73ac8c9573f507a5690da2d6`
- Pull request: #60, open and unmerged, targeting `main`.
- Available GitHub workflow: `Offline tests`, run ID `35456833157`, initially
  queued after publication.
- This repository has no macOS or Windows workflow definitions; local host
  validation above is the available cross-platform evidence for this task.

Physical boundary for P18-033 is strictly zero: USB/device operations 0,
sender calls 0, real `0x101b` 0, claims consumed 0, sender-marker mutations
0, and installation-wide-lock mutations 0.

Current disposition: `READY_FOR_PM_ACCEPTANCE`.
