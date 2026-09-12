# Astra Architecture/Product Review — Project Disposition

Date: 2026-09-12
Canonical base: `a158eaf30b234b37b86442c9b3a21860c9532e62`
Task branch: `task/astra-governance-disposition`
Scope: host-only documentation and governance alignment

## Purpose and authority

Astra's architecture/product review is recorded here as advisory input, not
as an authority that can establish a capability, authorize a device operation,
or override the project's evidence gates. This record captures the project's
disposition of the recommendations that materially affect product direction,
safety governance, and delivery order. The full advisory report is not copied
into the canonical documents; relevant decisions are summarized here and
linked from the targeted governance files.

This task performs no USB or hardware operation, sends no device command,
creates no live authorization, and expands no capability boundary.

## Disposition summary

### Already completed

| Review recommendation | Project disposition and evidence |
| --- | --- |
| Make write safety application-wide rather than route-specific | **Completed by P18-020.** The known existing-text replacement bypass now uses the same `PersistentWriteSafetyOwner`, durable claim store, sender-start marker, and installation-wide indeterminate-write lock as the Library route. The closure was accepted on canonical `main` at `a158eaf…` after PR #46. |
| Preserve no-retry, lock, marker, claim, and independent-verification discipline | **Completed/retained as permanent safety policy.** P18-020 closes the known route inconsistency; it does not weaken the established controls or make an ambiguous result retryable. |

P18-020's published final-head validation was macOS/Windows CI run
`34676222163` (jobs `103506450905` and `103506450975`) with independent strong
R3 review `P0=0, P1=0, P2=0 — PASS`. These facts are recorded for governance
traceability; they do not authorize a physical retry.

### Adopted

| Recommendation | Adopted project decision |
| --- | --- |
| Use one prepared-content concept | Adopt for the next host-only product work. Manager-prepared content and imported sources should converge on one prepared-content contract; transfer eligibility is a capability of that artifact and exact target/profile, not a second content representation. |
| Make conversion part of Library preparation | Adopt. The intended boundary is `source → normalize/render → preview → prepared artifact → Library → transfer`. Conversion remains USB-agnostic and offline. |
| Simplify normal user-facing UX | Adopt. The primary flow should read as `Add to Library → Prepare → Preview → Ready to transfer → Transfer in progress → Transferred and verified`. Claims, hashes, seals, and evidence manifests remain available under Technical details rather than dominating normal status. |
| Use typed readiness and outcome reasons | Adopt. Product decisions must consume stable typed reason codes and outcome values; localized or explanatory prose is presentation, not a condition that code parses. |
| Use one background operation controller | Adopt. Preparation, backup, live preflight, and any future transfer work should not block the UI event thread and should report progress, cancellation, and terminal outcome through one operation model. This is a host architecture direction, not live enablement. |
| Remove milestone-specific production identities gradually | Adopt gradually. New production paths should use generic validated operation data. Historical P18 identifiers remain in evidence and regression fixtures where they preserve provenance or compatibility. |
| Treat Windows/Tk/libusb/ARM support as an investigation | Adopt as an evidence programme. Build and clean-install-test the actual packaged application on declared Windows x64 and ARM environments, including Tk and libusb deployment, before relaxing runtime requirements or advertising compatibility. |
| Change the two-round correction rule | Adopt as governance. Two material correction rounds now trigger mandatory PM reassessment rather than an unconditional stop. PM may authorize one further tightly bounded correction only when the finding is understood, scope has not expanded, and risk remains acceptable. |

The permanent safety invariants are not candidates for simplification:

- no automatic retry after an ambiguous, interrupted, timed-out, cancelled, or
  otherwise indeterminate started operation;
- model-specific capability boundaries, with VNW-V10 remaining uncharacterized
  and unable to inherit VNW-V15 behavior;
- persistent installation-wide indeterminate-write protection, including
  durable sender-marker and claim-state semantics; and
- independent post-operation verification before terminal success.

The product may hide these mechanisms from normal UX, but it must not remove
or replace them with presentation state.

### Deferred

| Recommendation or related change | Project disposition |
| --- | --- |
| Consolidate SQLite safety state and JSON artifact storage | **Deferred.** Keep one application-wide safety-state owner over the existing persistence boundary. Defer migration until crash consistency, upgrade behavior, and recovery semantics are demonstrated well enough to justify the risk. |
| Relax the selected Tk/runtime requirement immediately | **Deferred pending evidence.** Do not change the requirement based on assumptions about common Windows distributions; test the actual package first. |
| Generalize package shapes before the next proof | **Deferred behind sequencing.** Prepared-content unification and offline conversion can proceed, but variable flat packages, hierarchy, batch behavior, and other shapes require their own evidence and review gates. |

### Rejected or avoided for now

| Proposal | Project disposition |
| --- | --- |
| Plugin framework | **Avoid for now.** It does not address the current product bottleneck and would add an extension boundary before the core workflow is coherent. |
| Broad GUI-framework rewrite | **Avoid for now.** Improve the current supported workflow incrementally and keep the conversion/core boundaries portable; a rewrite is not justified by this review. |
| Automatic synchronization or general sync behavior | **Reject for the current scope.** Selection remains a logical operation, not a request to reconcile or delete unmatched device content. |
| Capability expansion based only on architecture advice | **Reject.** No recommendation can promote an unsupported or unproven operation in `CAPABILITY_MATRIX.md`. |

## Delivery order after this disposition

1. **P18-021 — Fresh UI-driven physical validation**, only after a new
   operation-specific PM/owner decision, using the exact host-ready VNW-V15
   TXT → BMP → TXT shape. Earlier approvals and claims do not carry forward.
2. **P18-022 — Prepared-content/product workflow consolidation**, including
   Library-integrated conversion and a simpler Select → Prepare → Preview path.
3. **P18-023 — Responsive operation controller and typed outcomes/reasons.**
4. **P18-024 — Useful bounded flat-package expansion**, only after the fresh
   physical UI validation and a separate evidence/review gate.
5. Continue offline ebook preparation and the Windows/Tk/libusb/x64/ARM
   packaging investigation in parallel with later host-only work.

This order separates product simplification from physical authorization. The
next physical task remains a new P18-021 operation; this documentation task is
not permission to perform it.

## Canonical-document impact

- `PRODUCT_VISION.md` records one prepared-content contract, Library-integrated
  conversion, simpler status language, typed reasons, background operations,
  generic operation data, and the packaging investigation.
- `ROADMAP.md` records the revised sequence and the SQLite/JSON deferral.
- `WORKFLOW.md` changes the two-round rule to mandatory PM reassessment.
- `RISK_REGISTER.md` records P18-020's closure of the known bypass and the
  remaining packaging and future-path risks.
- `CURRENT_STATUS.md` records P18-020 as complete and points to this
  disposition.
- `CAPABILITY_MATRIX.md` is intentionally unchanged because no evidence-backed
  capability fact changed.

## Safety boundary

This is a host-only governance record. Device-changing operations, USB
transfers, sender calls, `0x101b`, claim consumption, sender-marker mutation,
and lock mutation are all zero for this task. The capability boundary remains
the exact one recorded in `CAPABILITY_MATRIX.md`, and any future physical
operation requires fresh operation-specific owner authorization and review.
