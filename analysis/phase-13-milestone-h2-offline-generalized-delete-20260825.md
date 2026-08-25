# Milestone H.2 — offline generalized deletion boundary

Date: 2026-08-25

This report records the offline safety boundary after the successful
stateful legacy deletion observation. It contains no raw capture, complete
backup, Manager file, USB range, timestamp log, or device payload.

## Evidence boundary

The preserved `I7-LEGACY-DELETE-01` result verifies one persisted legacy
effect for `root\\IC_I7_CLOCK_01.txt`: exactly one path was removed, no path was
added, surviving file payloads were byte-identical, Display History/Mark 1/
Bookmark 1 target references were cleared, and the native candidate matched
the complete post-delete dynamic blob. It does not establish the legacy
timestamp-generation rule, trustworthy request-4 completion semantics, or
physical atomicity/recovery.

## Provisional modern policy

The offline modern model intentionally does not reproduce the legacy
operation-wide timestamp rewrite. It preserves every surviving record
timestamp exactly and removes only the deleted record's metadata. This is an
explicit safety policy, not a discovered legacy rule, and it remains subject
to a future separately approved live decision.

Fixed-state derivation is independent of dynamic-model deletion. The supported
inputs are:

- exact all-zero `0x001b`–`0x001f`, preserved byte-for-byte; or
- an exact single target-reference form in an offset-list object, or the
  experimentally justified Bookmark 1 tuple
  `(target_ref, 0, 0x80000000, 0, 0)`, cleared to the exact zero object.

Unfamiliar nonzero headers, tails, multiple references, unsupported bookmark
groups, malformed objects, and unresolved references fail closed. No generic
rebasing rule is synthesized.

## Implemented offline slices

| Commit | Scope | Result |
| --- | --- | --- |
| `2145360` | `delete_model.py` and focused tests | One existing reachable ordinary TXT leaf; structural metadata/content rebasing; surviving timestamp/unknown-field/payload preservation; deterministic audit. |
| `83a5b41` | `delete_state.py` and focused tests | Fresh fixed-state parsing and exact supported reference clearing; authoritative Bookmark 1 byte order; malformed/unfamiliar-state rejection. |
| `b746347` | `delete_generalized.py` and focused tests | Fresh-backup candidate construction, exact device/backup/target/payload/candidate/transaction/fixed-state binding, strict post-readback verifier. |
| `7f9d417` | `delete_workflow.py` and focused tests | Fake-only guarded sequence, one send maximum, bounded progress callback, safe pre-start cancellation, indeterminate post-start interruption, strict completion, no retry. |

The complete suite at this boundary is **455 passing tests with three
intentional evidence-dependent skips**.

## Supported offline scope

- one existing reachable ordinary TXT record;
- exact target path and record offset from a complete fresh backup;
- root record, directories, markers, malformed records, unsupported record
  types, ambiguous paths, and unresolved state rejected;
- all surviving payloads and timestamps preserved by the provisional policy;
- exact `0x0000` completion only;
- complete independent post-operation backup and candidate/read-back equality;
- fake transport callbacks only, with no normal CLI/GUI exposure.

## Fail-closed and unresolved cases

The model is not a live modern deletion implementation. It rejects unfamiliar
nonzero fixed state, unsupported bookmark structures, malformed or incomplete
backups, duplicate/ambiguous paths, target mismatch, candidate mismatch,
nonzero/missing/malformed completion, post-write read-back mismatch,
disconnect/timeout/cancellation after transaction entry, and any condition
that would require an automatic retry. The legacy causal timestamp rule,
request-4 result interpretation, physical interrupted-write atomicity/recovery,
and broader record/state types remain unresolved.

Accordingly, a separately approved disposable live modern deletion smoke is
**not technically ready** at this checkpoint. The offline candidate and
fake-only workflow are useful safety boundaries, but no live sender or live
protocol is connected, and the remaining evidence/safety gates are not closed.
