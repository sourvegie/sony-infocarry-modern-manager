# P18-020 — Application-Wide Write Safety Closure

Date: 2026-09-12
Canonical base: `f1041551592a2aef930cbb7793d795652e807f77`
Branch: `task/P18-020-application-wide-write-safety`
Risk: **R3 host-side safety architecture**

## Goal

Make the persistent write-safety boundary genuinely application-wide before any further physical UI-driven validation.

The known defect is the legacy existing-text replacement route: it performs fresh backup, authorization, direct `AuthorizedWriteSender` execution and read-back, but it does not participate in the durable execution-claim, sender-marker, and installation-wide indeterminate-lock lifecycle used by the canonical Library route.

P18-020 must either place that route behind the same durable safety owner/lifecycle or disable the product write affordance until that integration is complete. Prefer integration if it can reuse the canonical safety services without creating a parallel live pipeline.

## Scope

- Existing-text replacement write path only, plus neutral shared safety abstractions strictly required to make all product write routes use one persistent safety boundary.
- Preserve its operation-specific candidate construction and terminal verifier.
- Preserve the canonical Library coordinator/adapter path unchanged except for neutral shared interfaces if technically necessary.
- No physical device-changing operation.
- No capability expansion.

## Required invariants

Every reachable product write route must:

1. check the installation-wide indeterminate lock before authorization/execution;
2. reject when an active sender marker exists;
3. validate durable claim-store integrity;
4. create/consume a unique operation-specific durable claim only at the reviewed execution boundary;
5. establish the sender-start marker before sender entry;
6. allow at most one sender invocation and zero automatic retries;
7. accept only the route's reviewed native-success condition;
8. require its existing post-write read-back/semantic verification for terminal success;
9. on any started-but-indeterminate outcome, retain/persist the sender marker and installation-wide lock and surface `ESCALATION_REQUIRED` / no-retry guidance;
10. on determinate pre-start failure, consume no claim and create no marker;
11. reject replay of a consumed operation.

Do not infer device modification from claim consumption alone: a claim may be consumed before the sender starts if final execution-time checks fail. Track claim state, sender-start state, and terminal result distinctly.

## Existing-text replacement boundary

Do not broaden replacement capability. Preserve the existing single selected TXT replacement semantics, fresh backup, exact authorization/confirmation behavior, candidate builder, and post-write verifier unless a change is necessary for safety integration.

Do not generalize this task into overwrite support for Library packages.

## Architecture

There must remain one application-wide persistent safety owner for claim / sender marker / global indeterminate lock behavior.

Do not create a second claim database, second lock file, second marker store, GUI-only safety flag, or route-specific approximation of the Library protections.

If practical, factor neutral write-execution safety primitives/services out of milestone/Library-specific ownership so both the Library route and replacement route use them. Do not perform a broad rewrite of candidate generation, transaction formats, or verification.

If a clean shared integration would require a large architectural redesign, it is acceptable to disable the replacement write action as a fail-closed interim resolution and report the architectural blocker for a later task. The product must not retain a reachable unprotected write route.

## UI behavior

- Existing-text replacement preview may remain available offline.
- The write button must be disabled/blocked whenever the global lock, active marker, corrupt claim store, stale operation identity, or other safety gate is unsafe.
- An indeterminate started replacement must not be shown as a generic retryable error and must not offer Retry.
- User-facing status should distinguish: pre-start failure, device-reported determinate failure, verified success, and indeterminate outcome.

## Required host tests

At minimum prove for the replacement route:

- active global lock blocks before claim/sender;
- active sender marker blocks before claim/sender;
- corrupt claim store blocks;
- confirmation cancel/wrong confirmation consumes no claim;
- final pre-send validation failure consumes no claim if before the claim boundary;
- exactly one claim for an executed operation;
- exactly one sender marker before sender entry;
- exactly one fake sender call;
- no automatic retry;
- native/route-specific failure handling remains determinate where evidence supports it;
- timeout/disconnect/exception after possible sender start produces/retains global lock and marker;
- missing or failed post-write read-back produces indeterminate lock/marker state;
- verified success closes marker and leaves lock clear;
- replay of consumed operation rejects;
- Library-route P18-008/P18-017/P18-019 safety regressions remain green;
- no second safety pipeline is introduced.

Use deterministic fake transports/state. Real device-changing operations = 0.

## Validation

Run focused replacement/safety/claim/marker/lock/Library regression suites, then the full Python 3.12 portable suite, compilation, and `git diff --check`.

Require final-head macOS and Windows CI PASS and a fresh independent strong R3 review with `P0=0, P1=0, P2=0 — PASS`.

## Documentation

Update `CURRENT_STATUS.md`, `RISK_REGISTER.md` if the application-wide safety risk is materially closed, and capability/product docs only if genuinely affected. Preserve P18-018/P18-019 history.

## Exit

`COMPLETE` only when no reachable product write path bypasses the application-wide persistent claim/marker/global-lock boundary, or when the unsafe route is explicitly disabled fail-closed and that closure is documented/reviewed.

Do not perform a physical transaction. Do not authorize the next physical validation. Stop for PM disposition after host review/CI.