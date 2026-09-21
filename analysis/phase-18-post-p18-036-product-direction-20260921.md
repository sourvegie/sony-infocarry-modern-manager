# Post-P18-036 Product Direction

Date: 2026-09-21
Branch: `docs/post-p18-036-product-direction`
Canonical base: `760a021d9bdec3b988c8e0039c8e83d742245aa7`
Scope: product documentation and sequencing only
Risk: R0 documentation
State: decision recorded; no code or capability behavior changed

## Decision

After P18-036, Sony InfoCarry Modern Manager is directed toward a simple
file and library manager with two primary areas: Local Library and InfoCarry
Device Library. The ordinary workflow is:

`Add files or folders → Select content → Transfer → Verify completion → Refresh the device tree`

For device content, the corresponding workflow is:

`Select files or folders → Delete → Verify removal → Refresh the device tree`

Users should be able to browse realistic nested collections, select the content
they want to manage, and see clear results without learning protocol or
experimental transfer terminology. Backup remains available as a normal
safety and read-only function. Technical evidence remains available in an
optional details view.

Deletion is a core product requirement. It remains a guarded operation whose
implementation and availability depend on its own evidence, current
capability, and safety gates.

## Realistic structural model

The product and validation model should accommodate tens of folders—roughly
30–50—and many TXT and BMP items, including nested structures. These figures
set a realistic planning and test scale; they are not hard product limits.
Any hard limit must follow an evidenced device, format, protocol, or resource
constraint.

Future validation should prove bounded structural rules across representative
generated collections and their boundary and invalid cases. Relevant rules
include supported content types, names and paths, parent-child relationships,
uniqueness, nesting, folder and item counts, sizes, conflicts, capacity, and
any ordering requirements imposed by the device format.

## Why exact-shape conservatism is being relaxed

The exact-shape policy served an important purpose while evidence and verified
operations covered only narrow examples. It kept current writes tied to known
device behavior and prevented unsupported combinations from reaching the
device. That evidence remains valid for the cases it actually tested.

The product architecture should not treat a list of exact leaf permutations as
the definition of every valid library. That approach overfits the model to
fixtures, encourages toy collection limits, and can leave untested structural
relationships hidden behind a passing exact-order case. Future validation
should establish general bounded properties and test collections that vary in
size, depth, and supported item composition.

This relaxes the product-model and validation approach. It does not relax
operational eligibility. Exact captured examples remain regression evidence;
the current capability matrix remains authoritative; and no broader transfer
or delete operation becomes available until its separate evidence, review,
authorization, and verification gates are satisfied.

## Safety invariants preserved

This product-direction decision retains the existing device-safety controls:

- current capability status remains in `CAPABILITY_MATRIX.md`; documentation
  does not promote an operation;
- VNW-V15 remains the only verified model, and VNW-V10 remains uncharacterized
  without inherited V15 behavior;
- a device change requires a fresh target, readiness, conflict, and capacity
  review, plus source freshness where applicable;
- the existing policy requires a complete verified backup before a write;
- device changes require operation-specific authorization and explicit
  confirmation;
- bounded execution, single-use durable claims, proof-bound sender-marker
  resolution, and the installation-wide indeterminate-write lock remain in
  force;
- device-changing operations remain labeled Experimental while commit
  atomicity and interrupted-write recovery are unproven;
- no device-changing operation is automatically retried after its start when
  completion is ambiguous, interrupted, timed out, cancelled, malformed, or
  missing;
- verified success requires the exact native integer result `0x0000`, a
  complete post-write backup, independent read-back of expected and unaffected
  state, a durable terminal result, and sender-marker resolution; and
- a selected logical change may still cause the protocol to rewrite a complete
  candidate library image. The user must be shown the actual operation scope.

Deletion as a product requirement does not authorize deletion on any model or
scope whose current capability and evidence gates do not support it. Transfer
does not imply synchronization, merge, send-all, or removal of unmatched
device content.

## Toolkit integration

The InfoCarry Toolkit snapshot `97042a9` remains an important integration
input for conversion. Defer integration until the Manager's core library,
direct TXT/BMP transfer, verification, and content-management workflow is
useful. Until then, avoid heavy polish of the separate Text Converter and
Ebook Renderer experiences. Conversion should ultimately run through the
Manager's Local Library and normal review path. Toolkit integration does not
establish device capability.

## Near-term order

1. Focused UI/UX review of the Local Library and Device Library workflows.
2. General library model and direct TXT/BMP transfer, validated through
   bounded structural rules rather than exact leaf permutations.
3. Realistic nested hierarchy tested with roughly 30–50 folders and many
   TXT/BMP items.
4. Guarded selected deletion with independent verification and immediate
   Device Library refresh.
5. Toolkit snapshot `97042a9` integration after the core Manager workflow is
   useful.

## Canonical-document impact

- `PRODUCT_VISION.md` now describes the Local Library ↔ Device Library
  product contract, ordinary transfer and deletion workflows, realistic
  structural scale, and the safety boundary.
- `ROADMAP.md` records the agreed near-term sequence and Toolkit timing.
- `CURRENT_STATUS.md` carries a concise pointer to the decision and canonical
  guidance.
- `AGENTS.md` explicitly requires both product documents before UI or
  capability work.
- `CAPABILITY_MATRIX.md` and application code are unchanged because this
  decision provides no new operation evidence and changes no device behavior.

## Validation

- `git diff --check` — passed.
- Checked four local documentation link targets; all exist. No Markdown-specific lint or documentation-check command is configured in the repository.
- Reviewed the change scope; only the requested documentation files changed.
- No hardware operation was performed.
