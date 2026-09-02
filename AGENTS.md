# Sony InfoCarry Toolkit — Agent Instructions

## Read first

For every engineering task:

1. Read `CURRENT_STATUS.md` for the current verified checkpoint, blockers, and next approved work.
2. Read `WORKFLOW.md` for task lifecycle, risk levels, review requirements, escalation, and human/hardware boundaries.
3. Read `CAPABILITY_MATRIX.md` when an operation's support, exposure, or blocker is in question; it is the authoritative capability register.
4. Read `PRODUCT_VISION.md` when product scope or behavior matters.
5. Read `RISK_REGISTER.md` for any change with device, persistence, data-loss, or release risk.
6. Inspect only the relevant `ROADMAP.md` / `analysis/` records needed for the task. Do not reread the entire project history by default.
7. Use `README.md` for supported setup, commands, and developer/user entry points.

Repository state and canonical documents override remembered conversation history.

## Development source and external archives

This sanitized repository is the canonical development source of truth. Verified `main` commits are synchronized normally to the approved private remote.

The sibling evidence-bearing reverse-engineering checkout is read-only. Do not commit product development there, rewrite its history, or push it.

The separate `InfoCarry-Toolkit` checkout is read-only reference material for this project. Reimplement or deliberately port reviewed conversion concepts into this repository; never combine both `infocarry` packages on one import path.

Original Sony software, ISO contents, raw USB captures, complete device backups, private device data, credentials, transaction-range binaries, and excluded live-operation evidence remain outside Git under the existing preservation rules. Do not upload them merely because the remote is private.

## Current safety posture

The project is read-first and fail-closed. Preserve all proven narrow scopes without generalizing beyond their evidence.

Normal product-facing generalized write, package-transfer, delete, destructive synchronization, restore, firmware/unlock, and alternate-mode controls remain disabled unless `CURRENT_STATUS.md`, `CAPABILITY_MATRIX.md`, `RISK_REGISTER.md`, and an explicit approved task say otherwise. A proven narrow operation may be labeled Experimental only when its matrix row and exact safety gate support it. `CAPABILITY_MATRIX.md` is the authoritative operation-status register; use `CURRENT_STATUS.md` only for the present sprint and avoid duplicating milestone narratives in either file.

The accelerated delivery policy classifies risk by reachability: offline
preparation and review are not R3 merely because they describe transfers;
R3 begins when code can authorize, construct the final transaction, transmit,
or decide live-write success. PM may approve reviewed R0/R1/R2 work. Owner
approval remains reserved for physical device changes, capability-envelope
expansion, fundamental write/authorization/recovery changes, exact restore,
interrupted-write experiments, firmware/service/alternate modes, and
destructive operations outside an enabled profile. An already enabled,
reviewed Experimental operation uses transaction-specific in-app confirmation.
Keep at most two active streams (Product Delivery and Legacy Oracle), allow at
most two material review-correction rounds, and do not add phase/milestone/
smoke-named production modules or parallel live pipelines.

A successful fixture, fake transport, offline candidate comparison, or previous narrow live smoke does not authorize a broader live operation.

Device-model boundaries are explicit: VNW-V15 is the only verified model and
its reviewed capability profile is not generic InfoCarry behavior. VNW-V10 is
`UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED` and must not inherit V15
protocol, format, capacity, candidate, authorization, or write rules. VID/PID
and bus/address are session observations, not physical-unit identity. Use one
installation-wide persistent fail-safe write lock until a stable unit identity
is proven; deliberate over-blocking across models is safer than false
precision. Route capability questions to `CAPABILITY_MATRIX.md`.

Never intentionally test interrupted-write recovery on the only valuable VNW-V15. Physical commit atomicity and recovery are unresolved.

Never automatically retry a device-changing operation after transfer start if completion is missing, malformed, ambiguous, nonzero, interrupted, timed out, disconnected, or otherwise indeterminate.

## Preserved device and evidence safeguards

- Treat `samples/reference/`, legacy installers, ISO images, Windows executables/DLLs/drivers, and captured reference traffic as read-only evidence. Never edit, rename, move, normalize, or overwrite them; keep generated output and environments out of release artifacts.
- Default every hardware-facing command to read-only behavior. Never send an unknown command or undocumented control request merely to see what happens.
- Require an explicit write-enabling option and interactive confirmation before the first device-changing request. Before any write, create and verify a full backup unless the user explicitly stops the operation.
- Use bounded transfer sizes, finite timeouts, bounded retry limits, and cancellation handling. Preserve raw received bytes before parsing and never discard the only copy after a parse failure.
- Do not run the legacy Windows Manager and modern client against the device simultaneously. Keep hardware tests opt-in and separate from ordinary automated tests.
- Complete a phase's exit gate before starting device-changing work from a later phase. Label protocol facts as `verified`, `observed`, or `inferred`; never promote an inference silently or fill an unresolved question with a guess.

## Task execution

Use one main coding conversation as the Dispatcher for each meaningful task when practical. Start from the approved task brief and inspect repository state before editing.

Resolve ordinary implementation details locally. Do not escalate naming, formatting, straightforward refactors, ordinary test organization, or small internal choices consistent with established architecture.

Escalate only material issues such as:

- ambiguous requirements;
- architecture conflict;
- persistent schema/file-format change;
- public API change;
- security or data-loss risk;
- external/native/hardware behavior that blocks safe implementation;
- repeated implementation/review failure; or
- consequential product decisions.

If correct behavior is known but implementation is difficult, increase implementation reasoning or use a bounded specialist. If correct behavior itself cannot be determined without changing requirements, architecture, persistence, interfaces, or risk posture, return `ESCALATION_REQUIRED`.

## Risk and independent review

Classify substantive tasks according to `WORKFLOW.md`.

- **R0:** trivial documentation/formatting/mechanical correction — targeted validation; review normally unnecessary.
- **R1:** ordinary engineering — tests; independent review optional when regression risk is low.
- **R2:** regression-sensitive persistence, Unicode/CP932 semantics, parsing/serialization, metadata, cross-module state, public/internal interfaces, rendering/performance-sensitive paths — independent review required.
- **R3:** device/safety-critical `write_*`, `delete_*`, USB transport, live candidate/state construction, authorization gates, live verification or runners — complete host validation and strong independent review required before `READY_FOR_HARDWARE_TEST`.

Use at most two correction rounds for material review findings. Persistent material disagreement becomes `ESCALATION_REQUIRED`; do not create endless agent loops.

## Human and hardware boundary

Agents may verify host-side facts such as tests, fixture comparisons, hashes, fake transports, deterministic candidates, static/offline analysis, and CI results.

Agents must not claim physical-device behavior, visual inspection, Windows 2000 / legacy Manager observations, external capture results, or other real-world checks they did not actually perform.

For hardware-dependent work:

1. finish offline/host preparation;
2. complete required independent review;
3. report `READY_FOR_HARDWARE_TEST` and stop;
4. require a new operation-specific owner approval and approved procedure;
5. ingest only the observations/evidence actually supplied by the human operator; and
6. independently verify what can be verified before declaring `COMPLETE`.

Missing native evidence may legitimately produce `BLOCKED_BY_EXTERNAL_EVIDENCE`. Do not invent a rule merely to unblock implementation.

## Validation

Canonical portable offline test command:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Use the repository-supported Python 3.12 runtime. The macOS system Python 3.9 / Tk 8.5 path is unsupported for the desktop application.

Before integrating substantive code changes, normally:

1. run relevant targeted tests;
2. run the full portable offline suite;
3. run `git diff --check` locally;
4. complete independent review required by risk level; and
5. confirm any external/hardware requirement is explicitly reported rather than silently assumed.

Evidence-dependent skips are permitted only when they are already intentional and documented; do not hide new failures by converting them into skips.

## Git and checkpoints

`main` represents verified canonical state.

For substantive work, prefer a short-lived task branch such as `task/<id>-<description>`. A pull request is useful for R2/R3 work when the durable review boundary adds value, but do not require issue/PR ceremony for every trivial change.

Keep commits coherent and reviewable. Do not force-push, rewrite published canonical history, change repository visibility, or upload excluded external evidence without explicit owner approval.

After a meaningful verified checkpoint, update `CURRENT_STATUS.md`. Update `PRODUCT_VISION.md`, `RISK_REGISTER.md`, or `ROADMAP.md` only when their own canonical subject actually changes. Keep chronological evidence/history in `analysis/` rather than duplicating it into this file.

## Final task report

Finish substantive tasks with:

- **Outcome:** `COMPLETE`, `READY_FOR_HUMAN_TEST`, `READY_FOR_HARDWARE_TEST`, `BLOCKED_BY_EXTERNAL_EVIDENCE`, or `ESCALATION_REQUIRED`.
- **Implementation summary**
- **Files changed**
- **Validation performed and results**
- **Independent review status**
- **Remaining external/hardware validation**
- **Architectural/safety concerns**
- **Commit / branch / push state**

Do not call a task complete merely because coding stopped.
