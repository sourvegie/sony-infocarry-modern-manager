# Legacy operation parity matrix

Date: 2026-08-22

This matrix separates legacy evidence, offline implementation, controlled live
proof, and product exposure. Exploratory code or an observed legacy operation
does not by itself authorize a modern device mutation.

Status terms:

- **Verified:** supported by preserved evidence or a successful controlled
  modern operation and independent read-back.
- **Offline:** modeled and tested without accessing a device.
- **Exploratory:** useful code or observations exist, but the operation's
  evidence/safety gate is not closed.
- **Blocked:** intentionally unavailable pending the stated gate.
- **Excluded:** outside the normal Manager replacement scope.

| Operation | Legacy/evidence state | Offline and failure model | Modern live proof | Product exposure | Next gate |
| --- | --- | --- | --- | --- | --- |
| Detect VNW-V15 | Verified USB identity and descriptors | Verified | Verified read-only | Enabled | Preserve regression coverage |
| Device information | Verified commands and raw responses | Verified conservative decoder | Verified read-only | Enabled | Preserve unknown fields |
| Complete backup | Repeatable eight-object captures verified | Integrity and manifest verification proven | Verified read-only | Enabled | Keep backups immutable |
| Browse and export text/BMP | Known records decoded; unknown bytes preserved | Deterministic export and preview proven | Uses verified backups | Enabled | Extend formats only with evidence |
| Replace existing TXT payload | Native transaction reconstructed | Exact target binding, strict CP932/CRLF, fake failures, and full read-back proven | Guarded live ttk smoke verified | Enabled as constrained v0.2 operation | Keep frozen and regression-tested |
| Add one root-level TXT | Clean capture 04 verifies one added record, exact transaction/post blob, and unchanged Manager-local sidecars | Milestone F complete offline; Milestone G binds one UTF-8 source, strict CP932/CRLF output, fresh backup, exact authorization, one-shot sender, and independent read-back | One explicitly approved 2026-08-22 smoke on `0x054c:0x001e` added exactly `root\\IC_G_LIVE_20260822_01.txt`, returned `0x0000`, matched the candidate blob exactly, and preserved every unrelated backup object | Disabled | Preserve the narrow evidence, keep the normal action disabled, and do not generalize beyond the closed root-level TXT scope |
| Delete one selected item | Attempt 01 remains failure evidence. Attempt 02 closes the persisted legacy deletion-effect evidence gate for legacy-created `root\\IC_E_ADD_20260822_04.txt`: one isolated native transaction, exact candidate/post dynamic-blob equality, 368-to-367 records, exactly one removed path, no added path, no shared payload changes, unchanged observed Manager sidecars, and `_04` absent from the device preview | Commits `b5bae4b` and `c8162c0` complete the narrow offline candidate, exact delete binding, independent post-delete verifier, and fake-transport failure model. The attempt-02 timestamp map is required and opaque; native `0x001d` is preserved as `count=0`, `value_04=1`, empty offsets, with only the observed stable `value_04=0` normalization allowed at read-back. Fake transport cannot prove physical atomicity or recovery. | None | Disabled | Offline gate complete for the narrow scope; require separate approval before any modern live-delete smoke, and keep product exposure absent |
| Rename an item | Partial historical observations only | Exploratory structural mutation code only | None | Disabled | Obtain one-property legacy fixture and exact offline equivalence |
| Reorder an item | Device ordering is decoded for browsing | No proven mutation serializer/workflow | None | Disabled | Capture one isolated reorder and account for every changed byte |
| Move between folders | Not isolated in a controlled fixture | No proven complete model | None | Disabled | Capture isolated move after folder semantics are established |
| Create/delete folders | Not fully proven | Exploratory only | None | Disabled | Separate create and empty-delete evidence gates |
| Prepared multi-record text content | Source-side conversion concepts exist | Minimum folder/ordering package not yet proven | None | Preview only | Milestone I after create/delete primitives |
| Import image content | Existing BMP content can be decoded/exported | Renderer structure exists but device compatibility remains unproven | None | Import disabled | Capture native add-image behavior and validate exact format/order |
| Import memo/other content | Existing content is partially understood | No proven creator | None | Import disabled | Separate evidence gate for each native type |
| Batch selected transfer | Legacy broad transfer behavior is understood as risky | Queue planning is allowed; execution model blocked | None | Execution disabled | Prove every queued primitive; one backup and plan-bound authorization |
| Transfer all ready items | No destructive legacy send-all parity intended | Additive queue semantics defined | None | Preview only | Close R14; never treat as sync or replacement |
| Restore full backup | Legacy capability exists but recovery behavior is unresolved | No safe modern restore | None | Disabled | Separate restore protocol, recovery evidence, and explicit approval |
| Interrupted-write recovery | Device commit point and atomicity are unknown | Failure/no-retry behavior can be simulated but physical recovery cannot | None | Writes labeled experimental | Requires second/sacrificial VNW-V15 and approved interruption protocol |
| Firmware, unlock, demo/service, alternate modes | Some commands/paths observed | Not part of normal transfer core | None | Excluded | Separate future research decision only |

## Current critical path

1. Preserve Milestone G's narrow live-smoke evidence while keeping the normal
   new-file action disabled.
2. Preserve the closed narrow offline Milestone H delete gate; require separate
   approval before any modern live-delete smoke.
3. Prove one minimum multi-record text package in Milestone I; do not begin it
   in this handoff.
4. Integrate Library/Prepare/queue workflows only from proven primitives.
5. Expand live new-file scope only after a separate safety review and approval.

## Recovery boundary

The current writer can prevent stale or unauthorized candidates, bind a
transaction, classify fake-transport interruption outcomes, avoid automatic
retry, and verify a completed result. It cannot prove that the device rolls
back an interrupted `0x101b` transaction. Routine cancellation is therefore
allowed before the device-changing request begins. After it begins, an
interruption is an indeterminate outcome requiring read-only detection and
backup assessment. Deliberate interruption testing is deferred until a second
or sacrificial unit is available.
