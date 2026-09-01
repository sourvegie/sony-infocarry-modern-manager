# Sony InfoCarry Development Workflow

## Purpose

This document defines how human decisions, AI-assisted engineering, review, repository state, and physical-device verification move through the project. Keep the process as small as possible while preserving correctness, independent verification where it matters, and explicit hardware boundaries.

## Roles and decision authority

### Project Owner

The human project owner decides product intent, priorities, acceptable risk, destructive-operation approval, and final acceptance of physical-device behavior. Only the owner may authorize a new live write, delete, restore, firmware/unlock, alternate-mode, or other device-changing experiment.

### Project Lead / PM

Use a project-lead conversation for ambiguous requirements, architecture choices, consequential product decisions, evidence strategy, and prioritization. It should produce concise approved engineering tasks rather than implementation transcripts.

Do not escalate ordinary implementation details such as naming, formatting, local refactors, test organization, or small internal design choices consistent with established architecture.

### Codex Dispatcher

Use one main Codex conversation per meaningful engineering task. The main conversation acts as Dispatcher and should:

1. read `AGENTS.md` and `CURRENT_STATUS.md`;
2. inspect the relevant repository state;
3. implement directly or delegate bounded implementation/exploration when useful;
4. run or confirm host-side validation;
5. invoke independent review according to the task risk;
6. route bounded findings back to implementation;
7. stop and request human verification when external or hardware evidence is required;
8. update durable project documentation after meaningful verified changes;
9. create a coherent commit/checkpoint when appropriate; and
10. escalate only material requirement, architecture, persistence-format, security/data-loss, or hardware-safety issues.

The Dispatcher is not a second product owner and should not invent requirements.

### Implementation worker

Implementation workers handle bounded coding and debugging. Routine engineering decisions should remain close to implementation. If correct behavior is known but implementation is difficult, increase implementation reasoning or use a specialist rather than escalating to the Project Lead.

### Reviewer

Independent review is selective. A reviewer should examine the change and evidence, not merely repeat the implementation agent's reasoning. Use a finite repair loop: implementation -> review -> correction -> re-review, with at most two correction rounds before material disagreement becomes `ESCALATION_REQUIRED`.

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

Use one fresh Codex Dispatcher conversation per meaningful task when practical. The Dispatcher should read repository state instead of depending on copied conversation history.

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

A Dispatcher final report should state:

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
