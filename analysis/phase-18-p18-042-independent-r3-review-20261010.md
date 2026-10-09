# P18-042 independent exact-head R3 final review

Date: 2026-10-10 Asia/Tokyo.
**PASS — P0=0 / P1=0 / P2=0 unresolved.**
Reviewed corrected code-bearing commit: `300bd0cdd5b5faf15fac96e403de32225d0948be`.
Base: `5966933388137138230140deca7b244d5bb74a8b`.
Checkout: `/external/local-path`.
Risk: **R3**. Disposition: **READY_FOR_HARDWARE_TEST for the integrated exact-fixture UI path**, subject to new operation-specific owner authorization and an approved procedure. No physical test was performed or authorized by this review.

## Scope independently reviewed

Read actual repository agent/workflow instructions, current status, capability/risk registers, product/roadmap requirements, the owner task and acceptance criteria, complete base-to-initial-head code/test changes and affected documentation, relevant dependencies, preserved physical reports, canonical evidence closeout/inventory and follow-on host analysis. Inspected candidate admission/construction, exact row/path/payload and displayed-state selection binding, frozen owner authorization, reconnect-safe raw-state equivalence, durable claim, sender marker, installation-wide lock, sender/no-retry behavior, complete independent post-backup/readback, result reconciliation, UI progress/error/cancellation/close/teardown and selection interactions, and existing ADD/transfer/backup regressions.

The integration delegates to the existing exact P18-041 facade and canonical coordinator/runner. The low-level sender, transaction format, persistent claim schema, sender-marker machinery and global lock architecture are unchanged. No parallel writer or safety store is introduced. The readable Delete/Cancel interaction binds the complete frozen internal identity; it cannot approve a different prepared object/candidate. Execution-equivalent state is checked before claim/sender; fresh complete backup and native integer `0x0000`, exact sole-path removal, preserved survivor data/timestamps/protected state and checksum, durable evidence and terminal resolution precede completion/refresh. Started operations have no automatic retry. Confirmed execution blocks close/cancel; preparation teardown releases undelivered review and runtime.

## One correction round, closed finding

Initial exact head `0f4dded047112c3aee45415a7c1df830e2f099b3`: P0=0 / P1=0 / P2=1. The real selection callback overwrote the main footer's terminal Delete warning with read-only text-preview status. Dedicated Delete status stayed correct; no sender/lock bypass occurred. The external initial report is `/external/local-path`.

Independently inspected exact correction diff at `300bd0cdd5b5faf15fac96e403de32225d0948be`. Terminal callback now restores both statuses after control/selection refresh. Tests execute the actual `show_selection()` and actual stale transfer-review invalidator; dual-status assertions and active Delete controller ownership are covered. Independently reran `/external/local-path` with simulated disconnect: both statuses retain `Delete outcome is uncertain. Writes are locked… do not retry.` The P2 is closed. No further P0/P1/P2 defect was found.

## Physical evidence and capability boundary

Independently read original `PHYSICAL_EXPERIMENT_REPORT.md` and `INDEPENDENT_POST_DELETE.md`, recomputed all 43 canonical referenced artifact hashes/lengths and eight report hashes, verified saved actual complete before/post archives, reconstructed the exact candidate, and reran independent Delete readback. All checks pass: exact target removal, 455→454 records, exact dynamic/fixed candidate state, unrelated payload/object preservation and expected candidate hash. The original independently verified physical record confirms 300 survivor payloads and 454 timestamps preserved, native zero, one audited sender/transaction, no retry, claim consumed, marker resolved and lock cleared. Those are supplied historical physical observations, not a new test by this reviewer. No independent USB bus trace exists.

Retained supported execution scope: **VNW-V15 exact `root\IC_P18_041G_CLOCK_01.txt`, exact 29-byte payload, unreferenced target and established protected-state geometry**. One physically demonstrated exact operation does not establish general root TXT capability. Four surviving root TXT host candidates/protected-state derivations corroborate modeling but provide no wider physical proof. BMP/nested files/directories/subtrees, root/system/multiple/ambiguous selection and VNW-V10 stay unavailable. The fixture is absent from the current preserved post-delete library. No repeat fixture placement/deletion is authorized. Generalization needs a scoped reviewed extension and separately authorized physical validation before promotion.

## Validation independently performed or inspected

- Independent initial integration/planning run: **39 passed**, no skips, 5.534s.
- Independent candidate/runtime/controller/desktop/regression run: **121 passed**, no skips, 2.966s, `/external/local-path`.
- Independent corrected integration/planning/callback run: **40 passed**, no skips, 5.928s, `/external/local-path`.
- Initial exact-head full portable log inspected: **1,132 run / 1,129 passed / 3 established skips**, 116.749s, `/external/local-path`.
- Corrected exact-head full portable log inspected: **1,133 run / 1,130 passed / 3 established skips**, 124.777s, `/external/local-path`, terminal `OK (skipped=3)`. The skips remain the two absent stable capture-04 cases and local-only native transaction ranges. No skipped/interrupted test is counted as passed.
- `git diff --check base..corrected-head` passed; corrected reviewed checkout clean.

No USB request, physical write, production claim consumption or marker/global-lock inspection/mutation was performed by this reviewer. Review used host fixtures, fakes and preserved immutable evidence only. GUI visual/packaged runtime validation and new UI physical behavior remain unverified; recovery/physical atomicity stay unresolved. This review grants no push/merge or physical operation approval.
