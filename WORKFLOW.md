# Sony InfoCarry Development Workflow

## Purpose

This document defines how human decisions, AI-assisted engineering, review, repository state, and physical-device verification move through the project. Keep the process as small as possible while preserving correctness, independent verification where it matters, and explicit hardware boundaries.

## Roles and decision authority

### Project Owner

The human project owner decides product intent, priorities, acceptable risk, destructive-operation approval, and final acceptance of physical-device behavior. Only the owner may authorize a new live write, delete, restore, firmware/unlock, alternate-mode, or other device-changing experiment.

### Project Lead / PM

Use a project-lead conversation for ambiguous requirements, architecture choices, consequential product decisions, evidence strategy, and prioritization. It should produce concise approved engineering tasks rather than implementation transcripts.

Do not escalate ordinary implementation details such as naming, formatting, local refactors, test organization, or small internal design choices consistent with established architecture.

### Fresh Codex Task Executor

Use one fresh Codex task per meaningful engineering task. The Task Executor works directly inside the already authorized task boundary and should:

1. read `AGENTS.md` and `CURRENT_STATUS.md`;
2. inspect the relevant repository state;
3. implement directly by default, using a temporary specialist only when technically justified;
4. run or confirm host-side validation;
5. invoke independent review according to the task risk;
6. route bounded findings back to implementation;
7. stop and request human verification when external or hardware evidence is required;
8. update only durable project documentation genuinely affected by the change;
9. create a coherent commit/checkpoint when appropriate; and
10. escalate only material requirement, architecture, persistence-format, security/data-loss, or hardware-safety issues.

Dispatch and coordination are responsibilities of the Task Executor, not a permanent intermediary role. The Task Executor is not a second product owner and must not invent requirements or treat direct execution as new authority.

### Temporary specialists

There are no permanent Junior Engineer or Secretary roles. The Task Executor owns implementation, validation, and affected documentation. It may invoke a temporary specialist for bounded coding, debugging, research, or review when technically justified. If correct behavior is known but implementation is difficult, keep the issue with the Task Executor or a specialist rather than escalating to the Project Lead.

### Reviewer

Independent review is selective. For required R2/R3 review, give the reviewer a bounded review packet, but require independent inspection of the exact commit or diff, relevant source, relevant tests and results, cited evidence where applicable, and applicable safety and acceptance requirements. The executor's summary is navigational context, not evidence of correctness. Use a finite repair loop: implementation -> review -> correction -> re-review, with at most two material correction rounds before disagreement becomes `ESCALATION_REQUIRED`.

### Human tester/operator

Humans perform physical-device operations, visual inspection that cannot be automated, real-world measurements, and other external checks. AI agents must prepare procedures and record supplied observations faithfully, but must never invent observations or claim physical verification they did not perform.

## Source of truth

The sanitized `sony-infocarry-modern-manager` repository is the canonical development source of truth.

The sibling evidence-bearing reverse-engineering checkout is a read-only research archive. The separate `InfoCarry-Toolkit` checkout is also read-only reference material for this project unless the owner explicitly approves a deliberate reviewed port of functionality.

Keep raw captures, complete device backups, original Sony software, private device data, credentials, and other excluded evidence outside Git under the established preservation rules. Commit sanitized analyses, manifests, and durable conclusions when appropriate.

Conversation history is transient. Approved decisions, implementation state, test evidence, blockers, and current project status belong in the repository.

## Canonical documents

- `CURRENT_STATUS.md`: concise current project snapshot; update after meaningful verified checkpoints.
- `CAPABILITY_MATRIX.md`: authoritative exact-shape operation support/exposure register; use it for capability questions instead of copying milestone narratives.
- `PRODUCT_VISION.md`: stable product scope and approved product behavior.
- `RISK_REGISTER.md`: material risks, controls, and unresolved safety boundaries.
- `ROADMAP.md`: longer-term milestones and historical progress.
- `README.md`: development setup, supported commands, and user/developer entry points.
- `analysis/`: investigation records, evidence synthesis, protocols, and technical history.
- `AGENTS.md`: compact operational instructions for coding agents.

Do not duplicate chronological milestone history or capability tables into every governance file. Prefer the capability matrix for exact operation status and `analysis/` for evidence/history; keep `CURRENT_STATUS.md` focused on the current sprint.

## Context-loading policy

For ordinary work, the default startup context is:

- `AGENTS.md`;
- `CURRENT_STATUS.md`;
- the approved task brief; and
- relevant source files and tests.

Load additional governance or history only when the task triggers it:

- `WORKFLOW.md` for risk classification, review, escalation, hardware, or process questions;
- `CAPABILITY_MATRIX.md` for operation support or exposure;
- `RISK_REGISTER.md` for safety, persistence, recovery, or data-loss implications;
- `PRODUCT_VISION.md` for product-scope or behavior decisions;
- `ROADMAP.md` for sequencing or prioritization; and
- specifically relevant `analysis/` records for historical or evidence questions.

Do not broadly scan `analysis/` during ordinary product work. Legacy Oracle, protocol reconstruction, candidate/state construction, recovery work, and R3 review must still inspect the specifically relevant evidence.

The accelerated delivery policy classifies work by reachability. Offline
selection, preparation, Library review, and host-only planning are not R3
solely because their subject is transfer. R3 begins at authorization, final
candidate construction, sender reachability, or live-success determination.
PM may approve reviewed R0/R1/R2 work; the Project Owner retains approval for
physical device changes, capability-envelope expansion, fundamental
write/authorization/recovery changes, exact restore, interruption testing,
firmware/service/alternate modes, and destructive operations outside an
enabled profile. An enabled Experimental operation uses an in-app,
transaction-specific confirmation. Keep at most two active streams—Product
Delivery and Legacy Oracle—and at most two material correction rounds. Do not
add phase/milestone/smoke-named production modules or parallel live pipelines.

Model support is explicit, not inferred from the product name. VNW-V15 is the
only verified model profile; VNW-V10 remains
`UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED` and cannot inherit V15
protocol, format, capacity, candidate, authorization, or write behavior. USB
VID/PID and bus/address are session observations, not proven unit identity.
Until a unit identifier is independently established, an ambiguous write
sets one installation-wide persistent fail-safe lock that deliberately
over-blocks every model/session and clears only through the documented
incident-bound diagnostic/recovery process.

## Task lifecycle

For each meaningful engineering task, use a concise task brief containing:

- task ID and title;
- goal;
- acceptance criteria;
- out-of-scope items;
- risk level;
- relevant canonical files/modules;
- required validation; and
- escalation conditions.

Use one Fresh Codex Task Executor per meaningful task when practical. The executor should read repository state instead of depending on copied conversation history. Direct execution is permitted only inside the approved scope: R0/R1 may proceed when consistent with established behavior; R2 remains within the task boundary and requires independent review; authorized R3 host/offline work stops at `READY_FOR_HARDWARE_TEST` before physical hardware use. Capability-envelope expansion remains an owner decision.

Task outcomes are:

- `COMPLETE`: all required verification is host-verifiable and passed, or required human/external evidence has been supplied and incorporated.
- `READY_FOR_HUMAN_TEST`: implementation is complete but human interaction/visual verification is still required.
- `READY_FOR_HARDWARE_TEST`: offline/host work is complete but correctness depends on an explicitly approved physical-device test.
- `BLOCKED_BY_EXTERNAL_EVIDENCE`: implementation cannot safely proceed without new external/native evidence; additional model reasoning alone cannot resolve it.
- `ESCALATION_REQUIRED`: a material requirement, architecture, persistence-format, security/data-loss, or hardware-safety decision is unresolved.

Do not equate "coding finished" with `COMPLETE`.

## Risk levels and review

### R0 — trivial

Examples: typo, formatting, harmless diagnostics, obvious mechanical documentation correction.

Flow: implement -> targeted validation -> commit. Independent review is normally unnecessary.

### R1 — ordinary engineering

Examples: ordinary GUI behavior, non-persistent presentation logic, utilities, local refactors, routine tests.

Flow: implement -> tests -> commit. Review is optional when regression risk is low.

### R2 — regression-sensitive

Examples: Library persistence, CP932/Unicode semantics, backup parsing, metadata structures, serialization, public/cross-module interfaces, complex state handling, rendering/performance-sensitive paths.

Flow: implement -> tests -> independent review -> correction if needed -> re-review for material findings -> commit.

### R3 — device/safety critical

Examples: `write_*`, `delete_*`, USB transport, authorization gates, live candidate generation, device-state construction, verification used to authorize a live operation, and live runners.

Flow: implement -> complete host validation -> strong independent review -> correction/re-review -> `READY_FOR_HARDWARE_TEST` -> STOP. A live operation requires a separate, operation-specific owner approval and an approved procedure. After the human operation, ingest the supplied evidence and independently verify what can be verified before marking the task `COMPLETE`.

Never retry an indeterminate device-changing operation automatically.

## Escalation rule

Use this distinction:

- If correct behavior is known but implementation is difficult, keep the issue with implementation or a specialist.
- If correct behavior cannot be determined without changing requirements, architecture, persistent formats, public interfaces, risk posture, or evidence assumptions, escalate to the Project Lead/owner.

Material escalation examples include requirement ambiguity, architecture conflict, persistent schema/file-format change, public API change, security/data-loss risk, hardware behavior blocking implementation, repeated implementation/review failure, or a consequential product decision.

## Branches, commits, and review records

`main` represents verified canonical state.

For substantive work, prefer a short-lived task branch such as `task/<id>-<description>`. R0 changes may be committed directly when appropriate. R2/R3 work benefits from a branch and, when useful, a pull request because the review boundary has durable value.

Do not require an issue or pull request for every trivial change. Process exists to improve quality and auditability, not to create ceremony.

Before integrating substantive work:

1. run the relevant targeted tests;
2. run the full portable offline suite unless the task explicitly cannot affect code;
3. run `git diff --check` locally;
4. complete required independent review; and
5. confirm there is no unresolved escalation or unclaimed external verification.

Keep commits coherent. Do not force-push or rewrite published canonical history.

## Validation boundaries

Host-verifiable evidence includes automated tests, static/offline parsing, fixture comparisons, fake transports, hashes, deterministic candidate reconstruction, and CI results.

Externally verifiable evidence includes observations from Windows 2000, the legacy Manager, external captures, or other systems that an agent cannot directly access.

Human-observed evidence includes GUI usability/visual behavior and physical VNW-V15 behavior supplied by the operator.

Always label evidence according to its source. Fake transport success is not physical-device proof. CI success is not hardware verification.

## Final task report

A Task Executor final report should state:

- outcome;
- implementation summary;
- files changed;
- validation performed and results;
- independent review status;
- remaining human/external/hardware validation;
- architectural or safety concerns;
- commit/branch/push state.

Keep the report concise and link to durable repository evidence rather than reproducing long histories.

## Reassessment

Reassess this workflow when repository size/interdependence rises materially, review begins catching significant issues, implementation/review failures become recurrent, hardware integration becomes more complex, model/tool economics change, or the process itself becomes a coordination burden.

Add or remove roles only when demonstrated need justifies them. Do not create permanent agents merely because the tooling supports them.

Use this simplified execution model for the next 3–5 meaningful engineering tasks. During that evaluation, do not add permanent roles or restructure the workflow again unless an observed failure or bottleneck justifies it. Assess time to useful implementation, unnecessary handoffs, repeated context loading, documentation and review quality, escalation correctness, and missed safety/evidence requirements. Afterward, report only material findings and recommend changes only for demonstrated need.
