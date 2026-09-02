# Sony InfoCarry Toolkit — Agent Instructions

## Operational bootstrap

For ordinary engineering work, begin with:

1. this file;
2. `CURRENT_STATUS.md`;
3. the approved task brief; and
4. relevant source files and tests.

Load other material only when triggered: `WORKFLOW.md` for risk/review/escalation/hardware/process questions; `CAPABILITY_MATRIX.md` for support or exposure; `RISK_REGISTER.md` for safety, persistence, recovery, or data-loss; `PRODUCT_VISION.md` for product scope/behavior; `ROADMAP.md` for sequencing; and only specifically relevant `analysis/` records for evidence/history. Legacy Oracle, protocol reconstruction, candidate/state construction, recovery, and R3 review must inspect their relevant evidence. Do not broadly scan `analysis/` during ordinary product work. Use `README.md` for supported setup and commands.

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

Use one Fresh Codex Task Executor for each meaningful task when practical. It inspects relevant state, implements directly by default inside the already authorized scope, validates, updates only genuinely affected durable documentation, coordinates required review, applies findings within the two-round limit, and escalates material decisions. Dispatch is a responsibility, not a permanent intermediary role. There are no permanent Junior Engineer or Secretary roles; invoke temporary specialists only when technically justified.

Resolve ordinary implementation details locally. Do not escalate naming, formatting, straightforward refactors, ordinary test organization, or small internal choices consistent with established architecture.

If correct behavior is known but implementation is difficult, keep working or use a bounded specialist. If correct behavior cannot be determined without a material requirement, architecture, persistence-format, interface, security/data-loss, evidence, or hardware decision, follow `WORKFLOW.md` and return `ESCALATION_REQUIRED`.

## Risk and independent review

Classify substantive tasks according to `WORKFLOW.md`; direct execution grants no new authority. R0/R1 may proceed inside established behavior. R2 remains inside its approved task boundary and requires independent review. R3 requires complete host validation and strong independent review, then stops at `READY_FOR_HARDWARE_TEST` before physical use.

Use at most two correction rounds for material review findings. Persistent material disagreement becomes `ESCALATION_REQUIRED`; do not create endless agent loops.

For required R2/R3 review, provide a bounded review packet. The reviewer must independently inspect the exact commit/diff, relevant source, tests and results, cited evidence where applicable, and the applicable safety/acceptance requirements. The executor summary is navigation, not evidence.

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

Use the concise outcome and reporting format in `WORKFLOW.md`. Do not call a task complete merely because coding stopped.
