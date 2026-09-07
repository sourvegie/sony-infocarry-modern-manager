# P18-013 — Incident-Bound Recovery State Closure

Date: 2026-09-07  
Repository: `sourvegie/sony-infocarry-modern-manager`  
Canonical base: `6bc0c046312400ed28fc4bef543522d250eb469c`  
Branch: `task/P18-013-recovery-state-closure`  
Risk: R3 host safety-state recovery  
Outcome: **COMPLETE**

## Scope and historical disposition

P18-013 closed only the durable host recovery state for the exact P18-011
incident. P18-011 remains historically **ESCALATION_REQUIRED**: this task did
not create a missing terminal-success record or retroactively convert that
physical operation into a success. P18-012 supplied sufficient independent
read-only recovery evidence, and the Project Owner supplied the explicit
decision used here.

No USB/device write was authorized or performed. P18-013 did not send
`0x101b`, construct a transfer transaction, consume a claim, create a sender
marker, retry P18-011, or alter device content. It did not expand the
capability matrix. Device-changing operations: **0**.

## Exact incident binding

- incident: `guarded-library-6aa14fe3d1c64f9497ff89a795bcf88c`;
- attempt: `6aa14fe3d1c64f9497ff89a795bcf88c`;
- permanently consumed claim: `827bfde0b93d4b2da57ee646ff6aaa1d`;
- preflight seal: `32740319540d5c33f53bc602e77146dff653c980b67fe84841e75f1b3c276931`;
- core preflight seal: `8fd1d4b044614bfbb9e20055a43781d00eb7848f2815968f8517430011e3a819`;
- candidate: `6fd27699ca6c13a46f8d75467ba72860af8b865b7cf19046b7a91f63bf471e01`;
- transaction: `9373330cd78f58faaa0cfe61590e4cd0ce489ea5c8069c3112144e69aafe10f4`;
- authorization: `d89c50dcfda1de87cc943ca5d1a76e3de4190e360630dd20340767da224f2878`;
- baseline state identity: `a6ea8922c0a1fa3231b04cbcf5de9791acf7536329b4eaf8d65a64352cacf9b9`;
- execution-time capacity response:
  `edea080952fe3541552cbb18c25498c233ced034fac87ec29cc895a55d1eeea1`.

Before recovery, the installation-wide lock was typed `locked`, the exact
sender marker was `lock_recorded`, and the claim store contained exactly one
relevant committed `consumed` tombstone. The marker and claim agreed on every
listed hash. SQLite integrity was `ok`.

## Durable diagnostic evidence

The original P18-012 evidence under
`/private/tmp/p18-012-readonly-diagnostic.JcWSYs` was copied without changing
its source, filenames, or bytes to:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-18-p18-012-readonly-diagnostic-20260907-01`

All 15 original files matched byte-for-byte after copying. The canonical
sorted original-file inventory SHA-256 is
`fec7ad5ac4ebbb3e1aae38d28c68c7bd07b831ff011ff6a550eed3141b256e43`.
The raw evidence remains outside Git.

- `0x0019` response:
  `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a`;
- diagnostic manifest:
  `bc20a3bcf2383880710700b6682c937239054d7d8ac5ade21e0d19d98bfa8c60`;
- dynamic blob:
  `6fd27699ca6c13a46f8d75467ba72860af8b865b7cf19046b7a91f63bf471e01`;
- canonical state identity:
  `e603fecc087bd615bada4dd37f6636eba7af257a75d0f1baa0b913764e7797b4`.

Independent revalidation verified all eight backup objects, 335 baseline
paths with no loss, the exact fixed target and ordered TXT → BMP → TXT
children, unchanged shared payloads and record bytes except established
metadata-pointer relocation, seven valid display-history references, one
valid bookmark group with four nonzero values, exact opaque bookmark values
and unused tail, and zero-count `0x001c`–`0x001e`. The current dynamic blob is
identical to both the sealed candidate and preserved immediate post-write
blob. The conclusion remained **NO CORRECTIVE DEVICE WRITE REQUIRED**.

## Recovery decision and supported transition

The deterministic decision record was created at
`2026-09-07T04:54:28+00:00` as
`recovery-decision-p18-013.json` in the durable archive. It binds the complete
diagnostic, original lock, exact marker, consumed claim, all operation hashes,
owner rationale, permitted host transition, and explicit zero-write boundary.
Its SHA-256 is:

`03414e625af346d48ba98e04a2ee2353adb561880e616fb4b8539603498ce3f9`

Only the existing supported contracts were used. A
`DiagnosticBackupEvidence` bound the original V15 model key, incident,
attempt, complete eight-object diagnostic manifest, read-only acquisition,
and verified integrity. `PersistentIndeterminateWriteLock.clear_after_diagnostic()`
then produced a typed `cleared` record retaining the exact incident and
attempt and recording the diagnostic, decision, decision-record hash, and
durable evidence root. After that typed record was reread, only the matching
marker was passed to `resolve_sender_after_diagnostic()`.

Final durable host state:

| State | Before | After |
| --- | --- | --- |
| Installation-wide lock | `locked` | `cleared` |
| Matching sender marker | `lock_recorded` | none |
| P18-011 execution claim | `consumed` | `consumed` |
| Relevant claim count | 1 | 1 |
| Claim-store integrity | `ok` | `ok` |

The cleared lock records the diagnostic manifest and decision-record hashes.
The sender-marker table contains zero rows. The consumed claim row is exactly
unchanged and cannot authorize replay.

## Tests and R3 review

Recovery coverage includes wrong incident, wrong attempt, wrong diagnostic
binding, incomplete diagnostic, wrong model key, malformed decision hash,
empty decision, lock-clear-before-diagnostic, marker resolution with a locked
record, wrong marker/lock incident binding, marker/claim corruption, and
permanent claim consumption after recovery.

- focused recovery and P18-006 adversarial suite: **33 passed**;
- full portable suite: **754 passed, 3 intentional skips**;
- `git diff --check`: passed.

Independent strong R3 pre-mutation review round 1 found `P0=0, P1=1, P2=1`:
the validator needed to exclude and separately hash the new decision record,
and isolated negative API tests were missing. Both findings were corrected.
Round 2 verified the correction, exact live bindings, and transition plan with
`P0=0, P1=0, P2=0 — PASS`. Final post-recovery review verified the durable
cleared state, absent marker, retained consumed claim, zero writes, and no
capability expansion with `P0=0, P1=0, P2=0 — PASS`.

## Future operations

Clearing the safety lock does not itself authorize a write. Every future
physical operation requires a new owner-approved task, fresh evidence, a new
operation authorization, and a new one-shot claim. The P18-011 claim remains
permanently consumed.
