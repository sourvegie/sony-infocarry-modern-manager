# P18-021 — VNW-V15 UI-Driven Physical Validation

Date: 2026-09-13
Repository: `sourvegie/sony-infocarry-modern-manager`
Canonical base: `e98d310878ea92d541217b29155bee2b69007af8`
Branch: `task/P18-021-v15-ui-physical-validation`
Risk: **R3 physical validation**
Status: **HOST-ONLY PREPARATION — READY_FOR_HARDWARE_TEST after validation**

## Purpose and host-only boundary

P18-021 prepares one fresh owner-authorized VNW-V15 UI-driven physical
validation through the normal manager flow after P18-019 and P18-020. This
setup task performs no physical operation. It must not use USB, touch or
detect hardware, invoke the sender, consume claims, create or resolve sender
markers, or mutate the installation-wide indeterminate-write lock.

The physical attempt is a separate operation. The agent must complete the
host validation and independent review below, report
`READY_FOR_HARDWARE_TEST`, and stop. No approval in this document, a prior
conversation, or a prior phase substitutes for the new operation-specific
owner approval in chat.

## Owner authorization and runtime confirmation

The Project Owner must explicitly authorize exactly this operation in chat
with:

```text
APPROVE P18-021 V15 UI PHYSICAL VALIDATION 01
```

The normal manager must display the following exact transaction-specific
confirmation immediately before sender entry:

```text
ADD IC_P18_LIBRARY_20260913_01 ONCE
```

The presence of either string in documentation, source, logs, tests, or
conversation history is not authorization and must not enable execution.
The confirmation is valid only for the freshly rebuilt P18-021 operation
identity and exact target below.

## Exact physical operation boundary

Device/model boundary:

- Sony VNW-V15 only;
- exact USB VID/PID `0x054c:0x001e`;
- fresh device detection is required for this operation;
- VNW-V10 remains `UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED` and is
  blocked from every V15 path.

Exact proposed destination root:

```text
root/IC_P18_LIBRARY_20260913_01
```

The target must be absent in the fresh live preflight immediately before any
write. Do not auto-select another target if it is present or its absence is
ambiguous.

The prepared root has exactly these three direct children, in this exact
order:

1. `01-introduction.txt`
2. `02-page-01.bmp`
3. `03-ending.txt`

The resulting native order is **TXT → BMP → TXT**. The capability envelope is
exactly one prepared root, one absent destination root, and one one-shot
transaction. The following are out of scope and must remain unreachable:

- overwrite, replacement, deletion, restore, or corrective write;
- nesting, merge, grouping, batching, or any second package/root;
- VNW-V10, another model, another target, or a broader package shape;
- automatic retry, replay, or a second sender/transaction path.

Maximum device-changing activity:

```text
logical transactions = 1
sender invocations   <= 1
0x101b transmissions  <= 1
retries              = 0
```

## Fresh pre-physical and pre-write gates

The physical procedure must use freshly acquired evidence from the proven
host-visible USB environment. Offline fixtures and P18-011/P18-015/P18-018
evidence are regression references only. Before the runtime confirmation,
claim consumption, sender-marker creation, or any device-changing request,
the normal UI/coordinator must establish all of the following:

1. The canonical filtered detector returns exactly one supported VNW-V15 with
   VID/PID `0x054c:0x001e`. Bus/address may be recorded as session
   observations but are not device identity.
2. A fresh complete eight-object backup is captured, verified, and bound to a
   fresh state identity for the detected VNW-V15.
3. A fresh native `0x0019` capacity response is captured and validated. Its
   capacity, source, response hash, and device identity are propagated into
   the canonical queue plan/readiness and remain part of the fresh sealed
   evidence; offline or stale capacity cannot clear readiness.
4. The exact target root is absent in that fresh backup/preflight. Presence,
   ambiguity, stale state, or a target mismatch stops the attempt before the
   write boundary without choosing a substitute target.
5. The exact prepared package is selected through the normal manager flow and
   rebuilt as one root with the three direct children and TXT → BMP → TXT
   order above. No unsupported shape or second package is accepted.
6. The candidate and transaction are rebuilt from the fresh state and exact
   prepared package, then sealed together with a fresh operation identity,
   authorization binding, queue plan/readiness identity, and preflight seal.
   Historical candidates, transactions, seals, approvals, confirmations, and
   result manifests must not validate this attempt.
7. The reviewed auxiliary-state policy is supported and preserved:

   ```text
   verified_display_history_0x001b_and_bookmark_0x001f_semantic_rebase_plus_zero_count_0x001c_to_0x001e
   ```

   All established `0x001b` logical paths, the established `0x001f` bookmark
   logical path, four opaque bookmark dwords, and unused bookmark tail must
   be preserved according to policy. `0x001c`–`0x001e` must remain
   zero-count. Malformed, dangling, unaligned, inconsistent, or unsupported
   auxiliary state fails closed.
8. The installation-wide persistent indeterminate-write lock is `cleared`,
   no sender marker is active, and the durable claim store passes integrity
   validation. The historical P18-011 and P18-015 claims remain consumed and
   are not reused; no P18-018 authorization or operation identity is reused.
9. The normal UI review displays this exact operation and the fresh
   capacity-cleared readiness. Final pre-send revalidation repeats the
   operation, target, package, capacity, auxiliary-state, lock, marker, and
   claim checks immediately before the confirmation/claim boundary.

If any gate is missing, stale, conflicting, or ambiguous, stop before the
device-changing boundary. Do not bypass the UI, relax the envelope, consume a
claim, create a marker, or mutate the lock to make the plan appear ready.

## Device-changing boundary

Only after every fresh gate passes and the Project Owner has supplied the
exact P18-021 approval in chat may the normal manager present the exact
runtime confirmation. After explicit acceptance, the existing canonical
application-wide safety lifecycle must:

1. consume exactly one fresh P18-021 durable execution claim;
2. establish the sender-start marker before entering the sender;
3. enter the existing sender once and transmit at most one `0x101b`;
4. perform no automatic retry, replay, corrective write, or second
   transaction.

Claim consumption, marker creation, sender start, native completion, terminal
verification, and final closure must remain distinct durable states. The
runtime must not infer a device change from claim consumption alone.

## Terminal success requirements

Success is reportable only when the native sender returns the explicit native
integer success `0x0000` and all of the following independently pass:

1. A complete post-write backup is captured and verified.
2. The post-write dynamic state/readback matches the freshly sealed candidate
   under the reviewed comparison rules.
3. The exact target is present with exactly the prepared root and the ordered
   children `01-introduction.txt`, `02-page-01.bmp`, `03-ending.txt`.
4. Target identity, child order, and every payload are independently verified.
5. Shared baseline paths, payloads, and timestamps are preserved.
6. The reviewed auxiliary-state policy and unrelated/opaque state are
   preserved, except only for the documented exact relocation effects.
7. A durable result manifest is written by the canonical path and is bound to
   this operation and its terminal evidence.
8. Claim closure is correct, the sender marker is closed, the global
   indeterminate-write lock is clear, and all counters remain within the
   one-shot limits.

Do not report `COMPLETE` or `Transfer verified` for a missing, malformed,
partial, or synthetic post-write backup, readback, result manifest, or
verification result.

## Indeterminate handling

If sender start may have occurred and completion or terminal success cannot be
proven—whether because of timeout, disconnect, exception, malformed/nonzero
completion, missing post-write backup, failed reconciliation/readback,
missing durable result, or any other ambiguity:

- never retry or send a second transaction;
- persist or retain the installation-wide indeterminate-write lock;
- persist or retain the sender-start marker according to the canonical
  lifecycle;
- preserve the original operation/attempt binding and evidence;
- end with `ESCALATION_REQUIRED` and stop for read-only diagnosis.

An indeterminate outcome must never be presented as a generic retryable error.

## Preserved history and identity separation

Retain these historical dispositions as evidence and regression context:

- P18-011: historical VNW-V15 physical-validation escalation;
- P18-015: successful VNW-V15 physical validation with terminal read-back;
- P18-018: historical UI-driven pre-write escalation before sender entry.

P18-021 is a new operation. It must not reuse any P18-011, P18-015, or
P18-018 owner approval, target, claim, candidate, transaction, seal, marker,
lock incident, or result identity.

## Required host validation and independent review

Before any physical action, complete and record:

- relevant focused safety/UI/facade/coordinator/adapter/claim/marker/lock/
  verifier and P18-019 fresh-capacity propagation tests;
- the full portable Python 3.12 offline suite:
  `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v`;
- Python compilation for `src/` and `git diff --check`;
- a static/offline reachability check confirming this setup performs no USB,
  sender, claim, marker, or installation-lock mutation;
- a fresh independent strong R3 review of the exact reviewed branch head and
  diff, with the reviewer independently inspecting the applicable source,
  tests, evidence references, and every acceptance/safety condition.

The host validation must be labeled host/offline evidence. It is not a claim
of device presence, physical success, native capacity, or UI behavior on real
hardware. After all host gates and the exact-head R3 review pass, the task
reports `READY_FOR_HARDWARE_TEST` and stops for the Project Owner's explicit
P18-021 approval in chat.

## Exit states

- `READY_FOR_HARDWARE_TEST`: host preparation, validation, and independent
  review pass; no physical action has occurred; stop for owner approval.
- `COMPLETE`: only after the separately approved physical run satisfies every
  terminal-success requirement above and independent verification passes.
- `ESCALATION_REQUIRED`: any material review/safety ambiguity, any possible
  started-but-indeterminate operation, or any unresolved identity/state issue.
- `BLOCKED_BY_EXTERNAL_EVIDENCE`: a required native or external observation
  is unavailable before a safe physical conclusion can be made.

Do not merge automatically. Keep raw/private device evidence and complete
backups outside Git; commit only sanitized durable conclusions.
