# P17-017 — Separate immutable operation identity from attempt evidence

Date: 2026-09-01
Risk: R3 — immutable authorization and one-shot live entrypoint
Status: **READY_FOR_HARDWARE_TEST — host-only; no hardware authorized**

## Trigger and preserved failure

P17-016 correctly preserved one sealed, hash-bound operation input, but its
bundle also included the concrete `fresh_backup_destination`,
`post_operation_destination`, and `evidence_manifest_destination`. The
authorized preflight-only production run created the bound fresh-backup
directory. The later live attempt therefore rejected the same approved bundle
before device access because one immutable output path was already occupied.
This was an orchestration defect, not device-state evidence.

The P17-016 failed-attempt evidence remains unchanged outside Git at
`/Users/stardust/Projects/InfoCarry-Evidence/phase-17-p17-016-library-package-live-attempt-20260901-01/`.
The preserved audit records `device_accessed=false`,
`write_started=false`, `sender_calls=0`, `backend_write_calls=0`,
`approval_consumed=false`, no completion, no `0x101b`, no mutation, and no
retry. P17-017 does not modify that evidence or request/reuse its phrases.

## Corrected invariant

The new `infocarry-p17-017-library-package-operation-bundle-v1` self-hash
covers the immutable safety identity: sealed-report and baseline artifacts,
catalog/package/template/capacity bindings, ordered child sources, selected
item and destination, raw-state identity, candidate/transaction hashes,
authorization and timestamp policy, fixed state, and the explicit one-shot
`0x101b`/integer `0x0000`/no-retry policy. It contains only a fixed evidence
output policy, not an acquisition path.

At execution, the isolated runner receives one external evidence namespace and
optionally an injected allocator for host tests. It atomically reserves one
new direct child with exclusive directory creation, rejects an occupied root,
path escape, symlink-resolved escape, or child collision, and derives exactly
these names beneath the reserved root:

- `backup-before-0001`;
- `backup-after-0001`; and
- `result-manifest-0001.json`.

The namespace and generated paths are attempt provenance. The namespace must
be an existing absolute non-symlink directory outside the source repository;
the allocated root is its exclusive direct child. They are recorded
in result audits and the external evidence manifest, but are not authorization
identity and cannot substitute a baseline, candidate, transaction, package,
device, or approval-bound artifact. Bundle resolution and all safety checks
still complete before runtime callbacks; output reservation is the only new
pre-callback boundary.

Preflight-only mode reserves its own root, runs the same read-only gates, and
stops at the sender boundary without consuming the one-shot claim. A later
live mode can use the same immutable safety bundle and reserve a distinct
root. After the exact approvals are accepted, the live claim is consumed
before any device callback; a failure after that point expires the approval
and cannot be retried. A successful fake run still permits exactly one send,
explicit `0x0000`, fresh post-backup, and independent read-back. Output
collision/namespace failures and safe cancellation before callbacks do not
consume approval or construct a sender.

## Mandatory regression proof

The focused adapter suite now runs 34 tests. It includes two independent
nominal fake runs and the same-bundle P17-016 sequence: preflight-only first,
then one live fake send with explicit `0x0000`, complete post-backup, and
independent read-back. It also proves:

- output roots are absent from the bundle self-hash and two bundles made from
  the same sealed safety inputs have the same identity;
- output-root collision, out-of-namespace allocation, source-repository
  namespaces, and symlinked namespaces fail before detection, backup capture,
  sender construction, approval consumption, or transmission;
- after exact approval, the live claim is consumed before any device-state
  callback, so detection, capacity, backup, candidate, and pre-send gate
  failures expire the approval and cannot be retried; safe cancellation before
  callbacks and preflight-only mode remain non-consuming;
- the fixed output policy cannot be mutated in a loaded bundle;
- candidate, transaction, baseline, source, device, capacity, fixed-state,
  completion, cancellation, timeout, disconnect, post-backup/read-back, and
  replay controls remain fail-closed through the existing P17-005/P17-013
  regression matrix; and
- generated paths appear in the success audit/manifest while candidate and
  transaction bytes remain excluded.

The complete portable suite passes with 623 tests and 3 intentional
evidence-dependent skips. No hardware, real sender, approval phrase, or
`0x101b` was used.

## Evidence classifications and disposition

- **Verified:** the P17-016 output collision; the new bundle schema excludes
  concrete attempt paths; exclusive direct-child reservation under an external
  non-symlink namespace; fixed output names; same-bundle preflight-only then
  live fake execution; pre-callback claim expiry after approval; one-shot/no-
  retry and existing safety gates; and hash-only result-path reporting.
- **Observed:** injected fakes record one sender call on nominal live runs and
  zero sender calls in preflight-only/collision cases.
- **Inferred:** one later real attempt can use one newly constructed P17-017
  bundle and the same sealed safety identity across a preflight-only run and a
  live run, provided a fresh operation-specific preflight and approval are
  obtained by a later task.
- **Unresolved:** physical device compatibility, native completion semantics,
  interrupted-write recovery, and all broader package/transfer behavior.

Final status is `READY_FOR_HARDWARE_TEST` after strong independent R3 review,
full validation, diff/exclusion audits, and the local pre-push checks recorded
below. CI remains a repository gate to confirm on the review PR. This
correction itself authorizes no hardware access and requests no owner phrases.
