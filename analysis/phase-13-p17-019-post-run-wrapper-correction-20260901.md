# P17-019 — Correct the P17-018 post-run wrapper false-negative

Date: 2026-09-01
Base: canonical `main` after P17-018 merge `99b5b8a`
Risk: R3 — post-operation verification and audit boundary
Disposition: **COMPLETE — offline correction only**

## Trigger and preserved evidence

P17-018 completed the exact authorized Library-package operation through the
production runner. The runner reported `readback_verified`, one logical
sender call, explicit integer `0x0000`, a complete post-operation backup, and
independent read-back. A surrounding audit wrapper then passed the enclosing
`PreparedLibraryPackageLivePreflight` object to a second disk-only call of
`verify_prepared_multi_package_readback()`. That verifier requires a
`PreparedMultiPackageCandidate`, so it raised `PreparedMultiVerificationError:
candidate is invalid` after the successful runner result.

The original external
`live-failure-audit.json` under the P17-018 attempt root remains unchanged.
It is historical wrapper diagnostic evidence, not the authoritative device
result. The P17-018 `offline-result-reconciliation.json` and 29-entry
preservation manifest remain outside Git and are not modified by this task.
No hardware, sender, approval phrase, or `0x101b` was used for P17-019.

## Corrected invariant

The new framework-independent
`reconcile_prepared_library_package_live_result()` boundary accepts only a
`PreparedLibraryPackageLiveResult` that already satisfies the production
runner's successful sealed result contract. It rechecks:

- the preflight seal and Library candidate/authorization binding;
- `state=readback_verified`, `approval_consumed=true`, and device-change
  success flags;
- exactly one logical sender call and `automatic_retry_allowed=false`;
- explicit integer completion `0x0000`;
- two verified, distinct backups, with the runner before-backup raw identity
  bound to both the sealed preflight and candidate baseline, plus the runner's
  successful read-back; and
- candidate and transaction hashes consistent with the sealed operation.

Only after these checks does the wrapper perform its second disk-only
verification with exactly `result.preflight.candidate.core`. The enclosing
preflight object is not accepted as a verifier candidate. A failure remains a
terminal `PreparedLibraryPackageLiveResultReconciliationError`; there is no
success conversion, audit overwrite, retry, sender, or device callback.

Wrapper accounting is explicit: `logical_sender_calls=1` describes the one
logical `0x101b` operation, while `low_level_bulk_write_calls=20` is an
independent optional observation. Low-level chunks cannot be counted as
sender calls. The successful wrapper audit does not emit a
`live-failure-audit` record.

## Offline regression proof

The focused adapter tests reproduce the exact bad call with the enclosing
preflight and observe `candidate is invalid`. They then pass the same
successful runner result through the corrected boundary, with the candidate
core, and obtain a terminal `readback_verified` result. The negative matrix
also rejects candidate substitution, raw before-backup substitution, shared
before/after evidence, post-backup substitution, nonzero or missing
completion, multiple logical sender calls, and an independent verifier
exception. Existing P17-005/P17-017/P17-018 fake-run, one-shot, no-retry,
post-backup, and GUI/CLI-isolation coverage remains in place.

Focused validation ran 40 adapter tests successfully. The complete portable
suite ran 629 tests with 3 intentional evidence-dependent skips. Python 3.12
compilation and `git diff --check` also passed.

The excluded-evidence/history audit found no raw backup, USB capture,
transaction, candidate, or P17-018 attempt artifact in tracked files or Git
history. The preserved P17-018 external manifest was replayed as 29/29
entries with zero hash/size mismatches and no unlisted evidence files; the
historical diagnostic SHA-256 remains
`add5eb7f75759f090bf50d779372a5e2ca52cb027bf31db20953350033dae809`.

## Evidence classification and boundary

- **Verified:** the P17-018 runner's successful read-back result and the
  wrapper's wrong-object cause as recorded in preserved/sanitized evidence;
  the corrected candidate-core call; separate logical/bulk accounting; and
  fail-closed negative tests.
- **Observed:** P17-018's external wrapper diagnostic and its recorded 20
  low-level bulk-write calls. The original diagnostic is not rewritten.
- **Inferred:** a future caller using the corrected wrapper will receive a
  successful terminal audit for an otherwise successful runner result rather
  than a false-negative wrapper error.
- **Unresolved:** physical opening of the P17-018 folder and all three
  children, interrupted-write recovery, native completion semantics beyond
  the explicit `0x0000` result, and broader package compatibility.

This correction does not reopen P17-018, authorize another live attempt, or
change the device protocol, candidate construction, authorization, one-shot,
post-backup, read-back, or normal GUI/CLI transfer boundary.
