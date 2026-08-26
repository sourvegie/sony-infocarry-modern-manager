# H.2 modern live-delete smoke readiness dossier

Date: 2026-08-26
Status: OFFLINE READY FOR OWNER REVIEW — separate explicit live-smoke
approval required

This dossier is a readiness boundary, not an authorization and not a live
operation protocol. No live adapter, USB transaction, device detection, or
backup was executed while preparing it. Raw captures, complete backups,
Manager files, and transaction ranges remain outside this repository.

## Supported scope

The proposed future smoke would be limited to exactly one existing, reachable,
root-level ordinary TXT leaf selected from a fresh complete backup. The target
must be disposable and explicitly identified by its exact path, metadata record
offset, payload length, and payload SHA-256 immediately before authorization.
Folders, the root record, arbitrary record types, multiple targets, recursive
operations, synchronization, rename, restore, and bulk deletion are excluded.

The modern policy is deliberately not a claim of legacy timestamp equivalence:

- preserve every surviving record timestamp exactly;
- remove only the selected record's metadata, native prefix, and payload;
- clear only the exact supported target-reference forms in fixed objects
  0x001b through 0x001f;
- preserve the verified fresh fixed-state bytes for all other state;
- reject unfamiliar nonzero fields, unresolved references, malformed state, or
  any structure requiring guessed rebasing.

## Offline evidence gate

The corrected full I7 comparison was rebuilt from the complete 374-record
pre-delete model and compared with the complete 373-record legacy post-delete
model. It verified the following:

- exactly root\\IC_I7_CLOCK_01.txt was removed and no path was added;
- candidate and post-delete path sets and record counts agree;
- 255 surviving payloads are byte-identical;
- candidate and post-delete pointers parse independently;
- the candidate and post-delete model lengths are both 2,051,420 bytes;
- masking only surviving record timestamp bytes [0x0c:0x10] and the derived
  header checksum leaves zero non-timestamp byte differences;
- the relation-based parent-marker rule is supported by two independent
  deletion cases: shorten field_08_be32 only for the exact parent-directory
  relation, and preserve coincidental values in unrelated markers.

The derived comparison and two-case matrix are recorded in:

- analysis/phase-13-milestone-h2-offline-delete-hardening-20260826.json;
- analysis/phase-13-milestone-h2-parent-marker-two-case-matrix-20260826.md.

This closes the normalized offline structural gate for the supported model. It
does not establish the causal legacy timestamp rule, trustworthy legacy
request-4 interpretation, physical commit atomicity, rollback, or recovery.

## Required future binding

Before any separately approved smoke, the offline candidate and authorization
must bind all of the following to the same fresh operation:

1. exact supported USB device identity;
2. complete fresh pre-delete backup manifest and dynamic-blob hashes;
3. exact target path, record offset, record identity, payload length, and
   payload hash;
4. candidate dynamic-blob hash and complete prospective transaction hash;
5. exact fixed-state before/after hashes and the supported state policy;
6. exact capacity evidence and model lengths where the live adapter requires
   capacity validation;
7. the exact target shown in the preview and the exact confirmation phrase:
   DELETE ONE INFOCARRY ITEM.

Any changed device identity, backup, target, payload, fixed-state value,
candidate, transaction, or capacity value invalidates authorization. There is
no fallback to a capture-specific constant or to a compatibility budget.

## Required transaction and verification boundary

The future isolated adapter, if separately approved and implemented, must:

- send exactly one 0x101b transaction;
- accept completion 0x0000 only;
- treat missing, malformed, ambiguous, or nonzero completion as terminal;
- capture a complete independent post-operation backup;
- verify exactly one authorized path removal, no additions, unchanged
  unrelated payloads and prefixes, valid pointers, and the authorized
  fixed-state result;
- preserve before/after artifacts and a durable audit;
- never retry automatically.

Cancellation before transaction entry is an ordinary safe cancellation. After
transaction entry, cancellation, disconnect, timeout, or missing completion is
an indeterminate device outcome. The only permitted follow-up is read-only
detection, backup, and assessment; no rollback or unchanged-device claim may
be made.

## Architecture and test boundary

The offline workflow uses an explicit fake transport capability with no USB
imports, discovery path, normal sender integration, GUI import, or CLI action.
Its finite deadline is cooperative and is checked at defined boundaries; it
cannot forcibly terminate an arbitrary callback that hangs forever. Actual
bounded USB calls and low-level transport timeouts remain responsibilities of
a future isolated adapter. Fake tests therefore verify workflow classification
and no-retry behavior, not physical atomicity or recovery.

## Approval boundary

This dossier does not authorize execution. Before opening a write-capable
transport or changing a device, the owner must review a fresh target-specific
preflight and provide separate explicit approval for one disposable modern
delete smoke, in addition to the operation-specific phrase
DELETE ONE INFOCARRY ITEM. Normal GUI/CLI deletion remains disabled.

Outcome: OFFLINE READY FOR OWNER REVIEW — separate explicit live-smoke
approval required.

## Verification checkpoint

- Relation-corrected focused deletion suite: 40 passing tests.
- Complete suite: 472 passing tests; 3 intentional evidence-dependent skips.
- No live hardware operation performed.
- No raw evidence or complete backup added to Git.
