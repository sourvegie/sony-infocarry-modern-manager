# P18-016 — Guarded Product Exposure

Date: 2026-09-10  
Repository: `sourvegie/sony-infocarry-modern-manager`  
Canonical base: `77cad55ebecdfd039704e21617454c308036761f`  
Branch: `task/P18-016-guarded-product-exposure`  
Risk: **R2 host/product exposure**  
Initial disposition: **AUTHORIZED — HOST-ONLY IMPLEMENTATION**

## Goal

Turn the already proven VNW-V15 flat TXT → BMP → TXT Library transfer shape into a clear, normal ttk product workflow **without making a device-changing action reachable in this task**.

P18-015 established one clean one-shot physical proof with terminal read-back. P18-016 must use that evidence to improve product usability while preserving the architectural boundary between:

1. **reusable product/profile eligibility** — whether one prepared Library package has the narrowly proven shape and is suitable for a future guarded attempt; and
2. **one-off operation identity/authorization** — fresh device state, destination binding, candidate, transaction, approval, confirmation, claim, sender marker, execution, and read-back for one separately authorized hardware operation.

The current Experimental review is still hard-bound to the consumed P18-015 destination/phrases. That historical binding must not become a reusable GUI Send path.

## Owner/PM scope

The owner approved moving on to this host-only product-exposure task. This does **not** authorize a new physical transaction, standing Send capability, arbitrary live transfer, overwrite, delete, restore, V10 write behavior, or reuse of the consumed P18-015 operation.

No hardware execution is part of P18-016.

## Canonical evidence boundary

P18-015 proved, on VNW-V15 `0x054c:0x001e`:

- one root-level absent folder;
- exactly three ordered children;
- child-kind order **TXT → BMP → TXT**;
- no overwrite/merge/delete/nesting/batch;
- one logical transaction;
- no automatic retry;
- explicit integer `0x0000` completion;
- complete post-write backup and independent read-back;
- the reviewed display-history/bookmark preservation policy.

P18-016 may generalize **host-side presentation/eligibility** from the historical P18-015 operation identity, but must not claim that arbitrary names, payloads, destinations, or packages are live-enabled merely because they satisfy host validation.

## Product behavior

### Normal ttk Library workflow

Extend the existing `desktop_ttk.py` Library flow rather than creating another application or live pipeline.

The user-facing progression should remain coherent with:

`Select → Arrange → Prepare → Preview → Review transfer`

For one explicit prepared package, provide a normal product-visible **Experimental transfer readiness** review. It should explain, in ordinary product language:

- supported device boundary: VNW-V15 only;
- selected root destination;
- exactly three authoritative ordered children;
- TXT → BMP → TXT profile result;
- prepared sizes and hashes where appropriate;
- conflict/absence status when an offline verified backup is available;
- capacity status when it is legitimately available from existing host evidence;
- a fresh device backup and fresh live capacity are still required before any real attempt;
- one-shot/no-retry semantics;
- post-write read-back verification requirement;
- why the item is host-eligible or blocked.

Do not expose internal milestone names, old owner approval phrases, old runtime confirmation phrases, claim IDs, or stale P18-015 target bindings as reusable product controls.

### Final action state

A visible final transfer affordance may be shown for workflow clarity, but in P18-016 it must be **non-actionable** and unambiguously labeled as unavailable until separately enabled/reviewed.

There must be no code path from the normal ttk UI to:

- operation authorization;
- final live candidate/transaction construction;
- execution-claim consumption;
- sender-marker creation;
- `0x101b` transmission;
- live completion/result decisions.

`desktop_ttk.py` must not import `experimental_library_transfer`, `prepared_library_package_live_adapter`, sender/claim execution helpers, or another live execution shim as part of P18-016.

## Architecture

### Separate reusable profile from historical operation identity

Refactor only as needed so host/product eligibility is not defined by these consumed P18-015 constants:

- `IC_P18_LIBRARY_20260907_01`;
- `APPROVE P18-015 V15 PHYSICAL VALIDATION 01`;
- `ADD IC_P18_LIBRARY_20260907_01 ONCE`.

Preserve the existing strict operation-specific review/runner behavior needed by historical and guarded live code. Do not silently relax its exact bindings.

Prefer a small UI-independent product/profile model or presenter that can:

- inspect exactly one explicit prepared Library package;
- validate one root-level folder with exactly three direct children;
- require child kinds TXT, BMP, TXT in authoritative order;
- require existing filename/path/CP932/payload limits from canonical preparation contracts;
- reject nesting, extra/missing children, multi-selection merging, automatic grouping, unsupported media, malformed manifests, or conflicting destinations;
- distinguish `host_profile_eligible`, `needs_fresh_live_evidence`, and `blocked` without implying authorization;
- emit a deterministic review object for the ttk UI;
- remain free of USB, sender, claim-store, lock mutation, and live-adapter imports.

Do not create a phase/milestone-named production module.

### Historical P18-015 replay protection

The product surface must not present the consumed P18-015 operation as reusable authorization.

If a verified baseline already contains the selected target, show a conflict/block. Never auto-generate a replacement name in a way that could be mistaken for approved live behavior.

Any future operation identity must be created under a separate R3 task from fresh live evidence and a separately approved product-execution boundary.

## Device/model boundary

- VNW-V15 may be described as the only currently verified device for this Experimental profile.
- VNW-V10 remains `UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED`.
- Do not infer V15 write support for V10.
- Bus/address are session observations, not physical identity.

## Required negative coverage

At minimum, prove fail-closed behavior for:

1. zero or multiple selected Library items;
2. non-package selection;
3. wrong child count;
4. wrong child order;
5. wrong child kind;
6. nested child/package structure;
7. extra or missing child;
8. malformed or unsupported prepared manifest;
9. invalid component/path encoding or existing preparation-limit violation;
10. automatic grouping/overlap;
11. destination collision in a verified baseline;
12. stale P18-015 owner approval/confirmation/operation identity being treated as reusable product authorization;
13. V10/model substitution;
14. report mutation/tamper where deterministic bindings are used;
15. GUI final transfer affordance being actionable;
16. any accidental UI import/reachability of the live sender path.

Retain existing P18-006 adversarial and P18-014/P18-015 regression coverage where relevant.

## UI expectations

Keep the current ttk/Tk 9 design direction and ordinary-window usability. Reuse the existing Library panes and Experimental review area rather than creating a modal maze or a second manager.

Recommended product wording:

- primary action: `Review transfer…` or equivalent;
- status when shape qualifies: `Experimental profile eligible — live transfer not enabled in this build`;
- blocked status should name the concrete reason;
- final disabled affordance: `Transfer once` with adjacent explanation that a separately reviewed live boundary is required.

Avoid developer-only prose in the main surface; detailed hashes/safety bindings may remain in a technical-details section/report.

The UI must never offer `Retry` after a hypothetical started write; P18-016 itself cannot start one.

## No-hardware boundary

For P18-016:

```text
device-changing operations: 0
sender invocations:          0
0x101b transmissions:        0
execution claims consumed:   0
sender markers created:      0
lock mutations:              0
```

Do not require a connected device. Do not perform a physical validation. Read-only USB is unnecessary for acceptance.

## Documentation

Update only subjects that actually change:

- `CURRENT_STATUS.md` — current P18-016 host product-exposure status;
- `CAPABILITY_MATRIX.md` — distinguish normal-UI host readiness exposure from live execution; do not mark generalized transfer as enabled;
- `PRODUCT_VISION.md` only if wording must reflect that the normal ttk workflow now exposes the Experimental readiness stage;
- this analysis record with implementation evidence and final review.

Do not rewrite P18-015 history.

## Validation

Required before integration:

1. focused product/profile eligibility tests;
2. ttk/controller tests proving the final action is non-actionable;
3. existing Experimental review/coordinator regressions;
4. relevant P18-006 adversarial and P18-014/P18-015 regression tests;
5. full portable Python 3.12 suite;
6. Python compilation;
7. `git diff --check`;
8. macOS Python 3.12 CI;
9. Windows Python 3.12 CI;
10. fresh independent R2 review of the exact final commit.

Use at most two material correction rounds. Final review requirement:

`P0=0, P1=0, P2=0 — PASS`

## Acceptance

P18-016 is `COMPLETE` only if:

- the normal ttk Library workflow exposes a clear Experimental transfer-readiness stage;
- host profile eligibility is no longer synonymous with the consumed P18-015 operation identity;
- exact TXT → BMP → TXT shape and existing preparation constraints fail closed;
- stale P18-015 approval/confirmation cannot become reusable authorization;
- destination collisions and unsupported shapes are clearly blocked;
- the live sender path remains unreachable from the normal UI;
- no claim/marker/lock/device state is mutated;
- device writes and `0x101b` remain zero;
- tests, CI, and independent R2 review pass.

Stop after host/product readiness. Do not begin P18-017 or any new physical operation without a separate task and explicit owner decision.

## Final report

Report:

- base/branch/head/PR;
- files/modules changed;
- exact product-visible workflow;
- eligibility/profile rules;
- proof of separation from P18-015 operation identity;
- proof live execution remains unreachable;
- negative tests;
- focused/full test results;
- CI;
- independent R2 disposition;
- explicit `device-changing operations = 0`, `sender calls = 0`, `0x101b = 0`, `claims consumed = 0`;
- final outcome.