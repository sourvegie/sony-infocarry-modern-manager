# P17-010A — Fresh-backup freshness-clock correction

Date: 2026-09-01
Risk: R3 — device/safety critical
Disposition: READY_FOR_HARDWARE_TEST for a future fresh attempt only

## Boundary

This correction is host-only. It does not access the InfoCarry, construct a
sender, transmit `0x101b`, consume approval, or reuse the prior operation
phrases. The prior P17-010 attempt remains the only live attempt and its raw
evidence is preserved outside Git at:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-17-p17-010-library-package-live-execution-20260901-02`

That root and its verified 13-entry preservation manifest were not modified.

## Failed attempt and evidence classification

The owner-authorized read-only sequence successfully detected one Sony
`054c:001e`, captured the native `0x0019` response (64 bytes,
SHA-256 `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662`,
parsed capacity 3,145,728 bytes), and captured and verified a complete
eight-object backup. The target remained absent.

The harness stopped before candidate construction because it supplied a fixed
wall-clock value captured before backup acquisition to freshness verification.
The backup manifest finalized after that reference, so the valid backup was
falsely classified as future-dated. This is a safe host timing defect, not
device-state evidence. The preserved failure audit records:

- `write_started=false`;
- `sender_calls=0`;
- completion: none;
- `approval_consumed=false`;
- no device mutation;
- no retry.

The external 13-entry manifest has SHA-256
`73c1001235c2fa6b9c917035ac63641bfad724905630f1ec40e7e8699364ac65` and
replayed with zero mismatches. The complete backup and capacity observations
remain preserved as evidence of the read-only portion;
the failed preflight is not an executable approval or baseline for a later
attempt.

## Correction

`capture_and_verify_fresh_backup` now samples its authoritative freshness
reference only after the complete backup callback has returned and its
manifest has been finalized. An optional `reference_clock` exists solely for
deterministic host tests; the live boundary uses the current UTC clock after
capture. The legacy `now` parameter remains accepted for source compatibility
but is no longer authoritative for this capture helper.

The P17-010 adapter now uses post-finalization wall-clock evaluation for its
baseline, pre-send, and post-operation freshness checks. During audit replay,
only verifier-generated `verified_at_utc` values are excluded from the
comparison because replay necessarily resamples that observation. Raw-state
identity, complete object integrity, acquisition provenance, package and
operation bindings, and every other freshness/state gate remain enforced.

The independent review also found the same downstream fixed-clock pattern in
the established package, multi-package, mixed-package, existing-text,
new-TXT, and delete execution chains: after a backup callback, they passed the
operation's pre-capture `now` into a direct freshness verifier or sender
binding. Those chains now use the verifier's current post-capture UTC clock for
backup freshness. Explicit `now` values remain only where they are part of an
offline model or deterministic fixture contract; no production or GUI/CLI
transfer path was enabled.

## Validation and disposition

Focused write-gate and P17 live-adapter tests pass, including acceptance when
the reference is sampled after finalization, rejection of genuinely future and
stale manifests, pre-send failure without sender construction or approval
consumption, and no retry. The complete portable suite passes with 602 tests
and 3 intentional evidence-dependent skips. `git diff --check`, external
evidence exclusion, and preservation-manifest replay pass.

The correction preserves backup completeness, integrity, maximum-age,
future-skew, raw-state, target-absence, capacity, package, authorization,
transaction, seal, one-shot, no-retry, and post-read-back requirements. It is
**READY_FOR_HARDWARE_TEST** only for a later fresh attempt with renewed exact
owner approval. No hardware access or sender construction is authorized by
P17-010A.
