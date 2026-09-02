# ADR-019: Fresh Codex Task Executor workflow

Date: 2026-09-02  
Status: Accepted

## Decision

Use one **Fresh Codex Task Executor** for each meaningful engineering task. It
inspects relevant repository state, implements directly by default within the
approved task scope, validates the result, updates only affected durable
documentation, coordinates required independent review, corrects bounded
findings, and escalates material decisions. Dispatch is a responsibility, not
a permanent intermediary agent. There are no permanent Junior Engineer or
Secretary roles; temporary specialists remain available when justified.

Ordinary startup context is `AGENTS.md`, `CURRENT_STATUS.md`, the approved task
brief, and relevant source/tests. Additional governance and historical records
are loaded only when triggered by risk, capability, product, sequencing, or
evidence needs. Evidence-sensitive research and R3 work must still inspect the
specifically relevant records.

## Boundaries retained

Direct execution grants no new authority. R2 retains independent review. R3
host/offline work stops at `READY_FOR_HARDWARE_TEST`; physical device changes
and capability-envelope expansion retain their owner-approval boundaries. The
model-separation, persistent fail-safe lock, indeterminate-write, and
no-automatic-retry rules are unchanged.

Required R2/R3 reviewers receive a bounded review packet but independently
inspect the exact change, source, tests/results, applicable evidence, and
safety/acceptance requirements. The two-material-correction-round limit
remains.

## Evaluation

Use this model for the next 3–5 meaningful engineering tasks without adding
permanent roles or restructuring again absent an observed failure. Evaluate
time to useful implementation, handoffs, context loading, documentation,
review, escalation, and missed safety/evidence requirements. Report only
material findings and change the workflow only for demonstrated need.
