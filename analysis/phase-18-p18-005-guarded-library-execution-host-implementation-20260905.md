# P18-005 — Guarded Library execution host implementation

Date: 2026-09-05  
Base: canonical `main` at P18-004 commit `fbae39d`  
Host disposition: **HOST_R3_REVIEW_PASS**

## Scope

The isolated `experimental_library_transfer` entrypoint now exposes a reusable
`GuardedLibraryExecutionCoordinator`. It connects the existing Library
Select → Arrange → Prepare → Preview artifacts to the reviewed P17 execution
boundary without creating a second candidate builder, authorizer, sender,
classifier, or lock implementation.

The coordinator requires:

- the exact VNW-V15 transfer-capable device profile and the exact Experimental
  flat package capability profile;
- one immutable P17 operation bundle and a current hash-only queue plan whose
  sealed preflight/bundle bindings describe exactly one absent root folder with
  ordered TXT/BMP/TXT children;
- a transaction-specific confirmation callback receiving the hash-only review;
- a persistent installation-wide indeterminate-write lock; and
- the existing injected detection, capacity, backup, fake/approved backend,
  evidence, one-shot, completion, post-backup, and semantic read-back callbacks.

The adapter adds one optional pre-send revalidation hook. The coordinator uses
it to recheck the persistent lock, plan digest, and sealed review bindings
immediately before the canonical sender. Plan, source, manifest, destination,
capacity, candidate, conflict, device, and model revalidation remains in the
existing P17 bridge/adapter. Any indeterminate adapter outcome or terminal
post-run reconciliation failure records the installation-wide lock with the
attempt evidence root; deterministic nonzero completion does not.

No normal GUI/CLI import or send action was added. No hardware, USB, approval,
`0x101b`, raw candidate bytes, or physical evidence was used in this task.

## Host verification

The exact fake-host lifecycle was exercised with one logical package and one
sender call: `0x0000` completion, complete post-operation backup, independent
semantic read-back, and no active lock on success. Focused negative cases cover
non-exact package shape, V10 rejection, wrong confirmation, plan mutation after
confirmation, persistent lock after disconnect, active-lock blocking, and
deterministic nonzero completion without a lock. Existing P17 adapter, bridge,
operation-bundle, review, lock, and normal GUI/CLI isolation tests remain green.

The full portable suite passes with 697 tests and 3 intentional
evidence-dependent skips. This is host/fake validation only. It does not
change the capability profile from `defined_not_live_enabled` and does not
authorize physical execution.

## Final checkpoint

P18-005 merged to canonical `main` as `63b7e7a` in PR #31 after the bounded
R3 review passed. The required Python 3.12 offline CI passed on both
`macos-latest` and `windows-latest` in [workflow run 33944258579](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/33944258579).
The implementation remains host/fake only: it does not claim physical
compatibility, alter normal GUI/CLI exposure, or authorize a device operation.

P18-006 is the separate offline guarded-transfer matrix and tamper-coverage
gate. Its bounded R3 corrections and independent review are recorded in
`analysis/phase-18-p18-006-offline-guarded-transfer-matrix-and-tamper-coverage-20260905.md`.
