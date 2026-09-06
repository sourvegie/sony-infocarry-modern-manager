# P18-012 — Read-Only Incident Diagnosis and Verifier Closure

Date: 2026-09-07  
Repository: `sourvegie/sony-infocarry-modern-manager`  
Canonical base: `a0ac0765d3a358898f665c8e3dca3a0027db83d7`  
Branch: `task/P18-012-readback-recovery-closure`  
Risk: R3 host/read-only  
Outcome: **COMPLETE** for host/read-only closure; P18-011 remains
**ESCALATION_REQUIRED**

## Safety boundary

This task performed no device-changing operation. It did not send `0x101b`,
construct or execute a write transaction, consume a claim, create a sender
marker, clear the installation-wide lock, resolve the existing marker, or
modify device content. `CAPABILITY_MATRIX.md` is unchanged.

The existing P18-011 incident binding remained active throughout:

- incident: `guarded-library-6aa14fe3d1c64f9497ff89a795bcf88c`;
- attempt: `6aa14fe3d1c64f9497ff89a795bcf88c`;
- consumed claim: `827bfde0b93d4b2da57ee646ff6aaa1d`;
- sender marker: `lock_recorded`;
- installation-wide lock: `locked`.

## Verifier correction

`src/infocarry/prepared_package_multi_verify.py` now derives bookmark
permission only from the validated candidate's sealed fixed-state snapshot and
policy. It requires the candidate assessment, candidate snapshot, audit
snapshot, and audit policy to agree before enabling bookmark verification.

Only the exact reviewed policy
`verified_display_history_0x001b_and_bookmark_0x001f_semantic_rebase_plus_zero_count_0x001c_to_0x001e`
enables bookmark verification. Non-bookmark policies reject bookmark
snapshots; unsupported or inconsistent policy/snapshot bindings fail closed.
There is no new public caller-controlled `allow_verified_bookmarks` switch.

The verifier now consumes the existing `rebase_auxiliary_state` result,
including bookmark verification details, while retaining the existing
display-history, pointer-alignment, path-resolution, opaque-byte, unused-tail,
zero-count, and shared-state checks.

## Preserved P18-011 replay

The preserved P18-011 sealed preflight, pre-write backup, package, candidate,
and immediate post-write backup were replayed from disk only. The corrected
verifier passed with `completion=0`:

- pre-write manifest: `2a686bcc2907cd395712fc809f0c69793df356c753a0f42a683610bb0da33816`;
- immediate post-write manifest: `8bf3d26ddbd28e9c91c0861889943548dc5082d5c5f20bf14ac6496b1b953c6f`;
- sealed candidate and post-write dynamic blob:
  `6fd27699ca6c13a46f8d75467ba72860af8b865b7cf19046b7a91f63bf471e01`;
- transaction hash: `9373330cd78f58faaa0cfe61590e4cd0ce489ea5c8069c3112144e69aafe10f4`;
- shared baseline paths verified: `335`;
- added paths verified exactly: `root\\IC_P18_LIBRARY_20260906_01` and the
  ordered `01-introduction.txt`, `02-page-01.bmp`, `03-ending.txt` children;
- shared payloads, timestamps, unknown record bytes, and unrelated backup
  objects remained unchanged;
- all seven display-history references resolved to their bound logical paths;
- the established bookmark pointer resolved to its bound logical path;
- bookmark opaque dwords and unused tail remained exact;
- `0x001c`–`0x001e` remained zero-count.

This is read-back correctness evidence only. It does not recreate the missing
P18-011 durable terminal-success manifest and does not change P18-011's
`ESCALATION_REQUIRED` outcome.

## Fresh incident-bound diagnostic

The VNW-V15 was available for one new complete read-only diagnostic. The
adapter enumerated the exact profile `0x054c:0x001e`; the diagnostic used the
read-only session/backend, obtained a fresh native `0x0019` response, and
captured and verified all eight backup objects. Bus/address were not used as a
binding identity.

Diagnostic evidence was preserved outside Git under the new namespace
`/private/tmp/p18-012-readonly-diagnostic.JcWSYs` and bound to the exact
P18-011 incident, attempt, claim, marker, and active lock. The post-capture
marker and lock records were byte-for-byte unchanged.

- fresh `0x0019` response SHA-256:
  `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a`;
- fresh diagnostic backup manifest:
  `bc20a3bcf2383880710700b6682c937239054d7d8ac5ade21e0d19d98bfa8c60`;
- fresh diagnostic dynamic blob:
  `6fd27699ca6c13a46f8d75467ba72860af8b865b7cf19046b7a91f63bf471e01`;
- fresh diagnostic canonical state identity:
  `e603fecc087bd615bada4dd37f6636eba7af257a75d0f1baa0b913764e7797b4`;
- fixed-state inventory: seven `0x001b` display-history entries, one active
  `0x001f` bookmark group with four nonzero values, and zero-count
  `0x001c`–`0x001e`.

The corrected verifier passed against the fresh diagnostic. It confirmed the
exact target and three ordered children, all 335 baseline paths, shared
payload/timestamp preservation, seven display-history paths, the bookmark
path, opaque bookmark values, unused tail, and exact fixed-state semantics.
No unexpected unrelated state mutation was found.

## Recovery assessment

| Question | Assessment |
| --- | --- |
| Does the immediate post-write state match the sealed candidate? | Yes; the corrected independent replay passed and the dynamic blob matches. |
| Does the fresh current diagnostic remain structurally safe? | Yes; it matches the candidate and passes the complete structural and auxiliary-state verifier. |
| Is the original ambiguity sufficiently diagnosed to recommend clearing the lock? | Yes, subject to a later explicit recovery decision; the evidence is incident-bound and the lock remains active in this task. |
| What binds the recommendation? | The exact incident, attempt, consumed claim, `lock_recorded` marker, active installation-wide lock, preserved before/after backups, and fresh diagnostic all agree. |
| Is a corrective device write needed? | No. The evidence supports no corrective write. |

P18-012 does not clear the lock or resolve the sender marker. A later explicit
recovery decision may handle those durable state changes separately. No
terminal-success claim or physical capability claim is added.

## Negative coverage and validation

Focused coverage rejects bookmark permission under the wrong policy, altered
bookmark and display-history pointers, unaligned and dangling pointers,
same-offset/wrong-path substitutions, opaque bookmark dword mutation, unused
tail mutation, unexpected active bookmark groups, nonzero unsupported
`0x001c`–`0x001e`, and candidate/policy/snapshot binding tampering. Existing
P18-006 adversarial coverage remains passing.

- focused verifier/candidate tests: **18 passed**;
- P18-006 guarded-transfer matrix: **18 passed**;
- full portable suite: **754 passed, 3 intentional skips**;
- Python compilation with an isolated temporary bytecode prefix: passed;
- `git diff --check`: passed;
- device-changing operations: **0**.

Independent strong R3 review: **PASS**, with no remaining P0/P1/P2 findings.

## Disposition

P18-012 is complete for the host/read-only verifier and incident-diagnosis
boundary. P18-011 remains `ESCALATION_REQUIRED`; its missing durable terminal
success record was not synthesized. The installation-wide lock remains
`locked`, the sender marker remains `lock_recorded`, and no device write was
performed.
