# P17-010A — Independent R3 review and re-review

Date: 2026-09-01
Risk: R3 — device/safety critical
Reviewer: independent read-only review pass
Disposition: PASS — narrow host correction is fail-closed

## Scope reviewed

The review covered the freshness-clock correction, the preserved failed
P17-010 attempt, the shared backup capture helper, every established isolated
package/delete/text execution chain that calls it, the P17-010 adapter, the
focused regression tests, and the sanitized status/risk/roadmap/report
updates. No hardware, sender, approval phrase, raw evidence, or external
candidate/transaction artifact was accessed or modified by the correction.

## Initial finding and correction

The initial independent review passed the P17-010 adapter but found one
repository-wide residual: downstream post-capture verifiers in the established
package, multi-package, mixed-package, existing-text, new-TXT, and delete
execution chains still received the operation's pre-capture `now`. That could
reproduce the same false future-dated result after a slow backup.

The correction round changed those backup freshness call chains to use the
current UTC reference after capture/finalization, including the direct
post-operation read-back checks and pre-send sender bindings. Offline model
timestamp inputs and deterministic fixture contracts remain explicit where
they are not backup freshness references.

## R3 gate review

- The shared capture helper samples freshness only after the capture callback
  returns; an injected clock is available only to deterministic tests.
- Stale and genuinely future-dated manifests remain rejected.
- Complete-backup and per-object integrity verification remain mandatory.
- P17-010 pre-send failure constructs no sender and consumes no one-shot
  approval claim; post-start failures remain terminal and are never retried.
- P17-010 retains raw-state, target-absence, capacity, package/source,
  fixed/display-state, candidate, transaction, seal, and post-read-back gates.
- Result-audit replay excludes only verifier-generated `verified_at_utc`
  observation churn. Raw state, acquisition provenance, object hashes,
  completeness, and all other bindings remain compared.
- The failed attempt's external 13-entry manifest remains unchanged and
  replays with zero mismatches.
- Normal GUI/CLI paths remain unconnected; the correction adds no sender and
  performs no device access.

## Validation

Focused freshness/write-gate and P17 live-adapter tests pass: 29/29. The
affected established execution workflow tests also pass. The complete
portable suite passes with 602 tests and 3 intentional evidence-dependent
skips. `git diff --check` passes. The external-evidence exclusion scan found
no evidence artifacts in the tracked tree or history; legitimate source
module names containing terms such as `backup` and `capture` are not evidence.
The preserved external 13-entry manifest has SHA-256
`73c1001235c2fa6b9c917035ac63641bfad724905630f1ec40e7e8699364ac65`, zero
missing files, and zero hash mismatches.

## Final disposition

The correction is **READY_FOR_HARDWARE_TEST** only for a future, newly
revalidated P17-010 attempt. The prior attempt remains a historical safe
pre-send failure and its approval phrases are expired for this correction.
Renewed operation-specific owner approval is required later. No hardware
access, sender construction, `0x101b`, mutation, or retry is authorized here.
