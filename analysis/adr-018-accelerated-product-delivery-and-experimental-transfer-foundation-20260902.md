# ADR-018 — Accelerated product delivery and Experimental transfer foundation

Date: 2026-09-02
Status: Accepted for P18-002 host/offline implementation
Risk: R2 overall; any sender, final-candidate, authorization, or live-success
reachability remains R3 and is out of scope here.

## Decision

Adopt the owner-approved accelerated delivery policy. Product work may proceed
in controlled increments instead of requiring a separate shape-named milestone
for every host feature, while the capability policy remains conservative and
machine-enforced. PM may approve reviewed R0/R1/R2 work. Project Owner approval
remains required for physical device-changing experiments, capability-envelope
expansion, fundamental write/authorization/recovery changes, exact restore,
interrupted-write experiments, firmware/service/alternate modes, and
destructive operations outside an enabled profile. A reviewed writer inside an
already owner-enabled Experimental profile uses transaction-specific in-app
confirmation rather than a relayed task phrase.

Risk is classified by reachability: offline selection, preparation, Library
review, and planning are not R3 merely because their subject is transfer. R3
starts where code can authorize, construct the final transaction, reach a
sender, or decide live-write success. Use at most two material
review-correction rounds and maintain at most two active streams: Product
Delivery and Legacy Oracle. Do not add phase/milestone/smoke-named production
modules or parallel live pipelines.

## Initial capability envelope

`src/infocarry/capability_profile.py` defines the reviewed, versioned profile
`experimental-flat-root-folder-txt-bmp-v1` with SHA-256
`ec69e0076e57f2eeca1634966777413f205880303dd8be7528218c77b3a7abc4`. It
allows the host product to validate and review one explicitly grouped new
root folder containing 1–8 ordered flat children. Children are strict
supported TXT or validated 237×320, 1-bit monochrome BMP. The profile also
enforces CP932-safe names, duplicate/path rejection, per-child and aggregate
limits, one package, one logical transaction, new-absent conflict policy,
complete fresh backup/capacity requirements, complete post-backup and
independent semantic verification, explicit `0x0000`, and no automatic retry.

This is a capability definition, not a claim of compatibility for every shape.
Its status is `defined_not_live_enabled`; unsupported, stale, nested,
multi-package, differently shaped, or unproven items remain preview-only with
a machine-readable reason. `CAPABILITY_MATRIX.md` is the authoritative
operation-status register and traces this profile explicitly.

## Application foundation

The host-only façade in `src/infocarry/transfer_foundation.py` records:

`PreparedItem[] → TransferPlan → CandidateLibrary → Authorization → ExecuteOnce → ReadBackVerification`

It accepts one fully revalidated explicit package, binds deterministic profile,
manifest, destination, candidate, and transaction hashes, keeps candidate
bytes out of the report, requires in-app confirmation metadata, and leaves
execution disabled. It deliberately reuses no parallel writer and imports no
USB/live adapter. Existing reviewed P17 candidate, authorization, one-shot,
output-lifecycle, and wrapper-reconciliation components remain the only later
R3 integration path.

## Indeterminate-write contract

`src/infocarry/indeterminate_write_lock.py` defines a persistent per-device
lock for a future live boundary. An ambiguous post-transmission result locks
the device across process restart and reconnect. No automatic clear is
possible. Clearing requires a complete read-only diagnostic backup, a
documented recovery decision, and a separately hash-bound decision record;
backup is not undo. The store is not connected to GUI/CLI or hardware in
P18-002, so the live path remains fail-closed until a later R3 task integrates
it.

## Legacy Oracle workstream

The Legacy Oracle stream remains offline by default. It will:

1. map the Manager/VICCTR/VicOne/VicTwo/driver send and delete path;
2. identify the final pre-USB candidate and transaction buffers without
   transmitting them;
3. build a sanitized, versioned corpus of exact inputs and outputs; and
4. compare legacy and modern reconstruction field-by-field, retaining every
   unexplained byte difference.

The Oracle is an analysis/differential aid, not a second live pipeline. Native
captures and original/private material remain outside Git.

## Ordered delivery

The approved sequence is: complete P18-001A visual acceptance; resolve
font/project licensing, hermetic tests, and Windows CI; define the capability
profile; establish the façade; integrate selection/order/prepare/preview;
review guarded execution and verification; exercise offline matrix/tamper
tests; run Legacy Oracle comparison; complete R3 review; perform one combined
GUI hardware smoke; then make a standing Experimental enablement decision.
Deletion remains a later separate delete/re-add lifecycle.

## Safety and evidence

Every future enabled operation must preserve strict validation and deterministic
identity, show an exact preview, obtain a fresh verified backup and capacity
result, immediately revalidate, use an in-app transaction confirmation, send
one logical transaction at most, accept only explicit integer `0x0000`, capture
a complete post-backup, independently verify semantics, and never retry.
Allowed differences must be explicit; an indeterminate outcome requires
read-only diagnosis and a persistent lock. P18-002 performs no hardware access,
requests no approval phrase, constructs no sender, and transmits no `0x101b`.

## P18-001A human checkpoint

The owner reports that the responsive Library surface works at approximately
980×680 and 1120×760 or larger. This is human-observed evidence for the
bounded GUI checks and closes P18-001A’s human gate in the current task’s
records. It does not infer hardware behavior, transfer execution, or other
display environments.

## P18-002 verification checkpoint

The host/offline implementation is **COMPLETE** for this policy-foundation
scope, pending the normal PR/CI merge boundary. Focused profile, façade, lock,
and Experimental-contract tests pass. The complete portable suite passes 665
tests with 3 intentional evidence-dependent skips; Python compilation,
`git diff --check`, and the excluded-evidence/history audit pass. The final
independent R2 verification is **PASS**. Its bounded correction required
`DiagnosticBackupEvidence.complete`, `.read_only`, and `.integrity_verified`
to be the built-in bool type and exactly `True`; false and truthy non-boolean
values are rejected, without coercion. Earlier review findings on stale
authorization, mandatory backup/capacity gates, unknown child fields,
explicit grouping/destination binding, strict profile typing, immutable
candidate paths, and runtime diagnostic-evidence typing remain closed.

No hardware, external evidence, approval phrase, sender, or `0x101b` was
accessed or constructed. Live execution remains disabled by the profile and
normal GUI/CLI isolation remains intact.

## Historical record routing

The pre-P18-002 long-form governance documents are preserved in the archive
files linked from `CURRENT_STATUS.md`. Phase-specific evidence and prior
review records remain in `analysis/` unchanged.
