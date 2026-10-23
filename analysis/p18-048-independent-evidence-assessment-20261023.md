# P18-048 — independent root-BMP evidence assessment

Starting checkpoint: `ad6aea0ac244497b884e1512160af33fa7679233`, with unchanged reviewed/live implementation from `ed76e7990faf77b181726ff56f0debfccc0f3389`.

## Disposition

**The accumulated evidence supports the proposed conservative ordinary unread root-BMP envelope as an Experimental VNW-V15 capability, subject to implementation validation and independent exact-head R3 review. There is no unresolved evidence blocker requiring another physical experiment for this bounded envelope.**

This is an evidence assessment, not approval of a future unreviewed implementation or authorization to perform another device write. No implementation was changed here. The current owner's explicit P18-048 scope permits a justified capability promotion; each future operation must still receive the existing transaction-specific confirmation.

## Physical evidence independently rechecked

I inspected saved operation audits and terminal-resolution evidence, rehashed complete before/post backups, rebuilt both exact BMP candidates and transactions, and reran the existing independent complete Delete readback verifier against actual saved post-states. Neither this assessment nor those checks accessed USB or constructed/mutated a production safety store.

| Specimen | Native record/payload | Verified geometry and result |
| --- | --- | --- |
| P18-046 A | Root BMP, unread `0xe0`, opaque `0xffffffff`, selector `0x100`, 16 all-FF prefix bytes; 10,302-byte bottom-up 237×320 monochrome BMP | Target `0x680`, 25 surviving serialized records before and 429 after. Actual post archive exactly original pre-placement state. |
| P18-047 B | Same native record profile; distinct 10,302-byte top-down/inverted 237×320 monochrome BMP | Target `0x6c0`, 26 surviving serialized records before and 429 after. Exact A32 anchor at `0x680` survives unchanged. Every actual post object equals verified actual A32 state. |

Each exact BMP Delete has native `0x0000`, one audited sender/single `0x101b`, zero automatic retries, complete eight-object readback, valid checksum/structure, preserved survivor timestamps/prefixes/payloads and eight protected history/bookmark associations. Terminal resolution is `verified_terminal_success`; counts derive from saved execution audits, not an independent USB bus trace.

The P18-047 A32 placement, B placement, B Delete and final A32 cleanup each have separate owner approval and independent post-operation PASS. All eight final cleanup objects directly match original baseline bytes, lengths and hashes; both disposable fixtures are absent. Complete backup objects include `0x0024`, five protected responses and blob probe/blob; native `0x0019` capacity is separate evidence.

Rechecked anchors:

- P18-046 payload SHA-256: `2701eb9214e2f0afec20b36c93ef739ef3bce35e931fd8c5721e15915447b26d`.
- P18-046 actual result manifest: `30e9c7c4f9d3cf787a8b0a0f81af9ebbc9f9ae0646b398c0e880d3a268afb80f`.
- P18-046 complete post-backup manifest: `fd1eb69cb729b993648ab093dc9bb8036d580a5164d891431b39c95ab681e806`.
- P18-047 B payload SHA-256: `c172a44bb01de67abb3146b2bad89abe524963cf9ca56fc911bb4430dac70e82`.
- P18-047 B Delete actual result manifest: `8e0901e07e52f7a62934d996730f45859536945da1e9bbb71c077156fd2afb1a`.
- P18-047 B Delete complete post-backup manifest: `204bbb10ce606325e44d6ccd3a5f06e6da7d87a56f42d96ba9595c097f1ba9d9`.
- Independent actual B Delete report: `5d8a152989381d0b68a74a580abcdf73376117d1996a4c6ad0e3182eec446de0`.
- Independent final A32 cleanup report: `153cd1a759a31b570b830cff2a4f7cbf5854c19383d2fca8d0eda4c4c3247eda`.

## Why a bounded class inference is justified

The operation removes one fixed-size native metadata record and its opaque aligned content segment. It never interprets pixel content to select a different write algorithm, regenerates survivor names, changes bitmap orientation, or infers arbitrary opaque fields. Both physical payload orientations/content patterns and a second native serialized position have now succeeded with exact predicted complete states.

I independently reran the preserved archive census: 163 archived BMP records, 33 validator-supported 237×320 records containing 22 unique payloads, 130 other-dimension records refused. All 33 supported archived payloads passed conservative admission in first/middle/last **synthetic root positions**: 99 candidates. These are archived payloads placed in synthetic root geometries, not 99 physical root deletions. Existing synthetic tests also cover sole-root-file removal, native names, state/prefix/opaque-field refusals, ambiguous identities, allocation overlap, protected references, candidate tampering and one-shot failure handling.

The shared deletion mathematics has separately tested first/middle/last records and records on both sides of the target. The legacy parent-marker relation rule is supported by two preserved native deletion cases; its implementation validates exact related pointers and preserves unrelated marker fields. Modern BMP physical results validate that same deletion arithmetic without permitting arbitrary marker semantics. Current structural/protected-state validation remains mandatory for every selected file.

A different safe filename changes only bytes in the record being removed. Native identity is fixed-size, NUL-terminated, CP932-roundtripping and checked for unique paths/stems; deletion neither truncates nor rewrites survivor names. Therefore another physical test for every name, pixel pattern or aligned record slot would be redundant. Metadata/content offsets remain variables derived from each complete source archive and checked before authorization and again before sending.

## Recommended exact execution envelope

- **Model:** VNW-V15 only, with existing model gates. VID/PID and bus/address are not asserted to identify a physical unit. Keep installation-wide fail-safe locking.
- **Selection:** Exactly one reachable ordinary direct child of device `root`; native extension exactly lowercase `bmp`. No directories, markers, nested files, subtree closure or multiple selection.
- **Identity:** Existing safe native stem rule: 1–39 CP932 bytes, exact Unicode/CP932 roundtrip, exact NUL-terminated field, no root/system/path/control syntax or surrounding whitespace. Reject duplicate/case-folded path identities and TXT/BMP native-stem collisions. Bind exact path, metadata offset and payload from the selected verified archive.
- **Native state:** Exactly unread `0xe0`, field `0x10 = 0xffffffff`, selector `0x100`, exactly 16 all-FF prefix bytes. Reject read `0x20`, selector `0x200`, different prefix contents/lengths and unfamiliar opaque state.
- **BMP payload:** Existing canonical validator, unchanged: BM signature, exact declared size, 40-byte BITMAPINFOHEADER, width 237, signed height +320 or -320, one plane, 1-bit uncompressed, two-entry palette semantics already accepted by the validator, pixel offset 62, row stride 32, 10,240 pixel bytes and exact total length 10,302. Reject alternative dimensions, compression, bit depths, headers, truncation or trailers. Do not infer additional image-format support.
- **Record positions:** Permit any exact reachable, metadata-aligned root-file slot that passes the existing unique-parent/child-table/pointer/path/survivor invariants; do not impose fixture offsets or require a disposable anchor for ordinary admission. Physical offsets are only `0x680` and `0x6c0`; extension to other valid slots is a structural engineering inference supported by independent raw-record validation and first/middle/last host tests, not a claim of physical testing at every slot.
- **Content geometry:** Existing 4-byte-aligned bounded target allocation, including its established alignment gap, with no overlap and all surviving prefixes/payloads/gaps preserved. Canonical target prefix+payload is 10,318 bytes and aligned allocation 10,320 bytes, so the 10,384-byte whole-archive reduction is invariant for this envelope. Other payload lengths or unaligned/overlapping geometry are excluded.
- **Protected state:** Target unreferenced by supported history/bookmark state; active Marks and unfamiliar state remain refused. Preserve/rebase only established survivor associations and verify all opaque bytes. Do not clear references to admit a target.
- **Execution:** Fresh verified complete eight-object backup and native capacity, frozen candidate/transaction/source identity, reconnect-safe source equality, normal one-operation confirmation, durable single-use claim, marker lifecycle, installation-wide lock, one sender/no retry and explicit native zero followed by independent complete readback and UI refresh. Sender return alone is never success.

## Implementation acceptance and remaining limits

The smallest promotion should connect the existing conservative host admission to the existing Device Library/facade path. General execution must rebuild that admission from verified source bytes at sealing and revalidation, never accept an audit label, caller boolean or extension alone as authority. Retain explicit exact B validation behavior without allowing it to weaken ordinary admission, and preserve TXT candidate/authorization behavior. No transport, claim schema, lock or parallel writer is needed.

Focused/full regressions, GUI admission/confirmation/refresh checks, historical exact-A/B reconstruction, packaging checks where affected and independent exact-head R3 must pass before declaring promoted implementation complete. This assessment does not substitute for that code review.

Residual physical atomicity/interrupted-write recovery remains unresolved and is contained by existing no-retry/indeterminate handling. Read-state/32-prefix BMPs, nested deletion, directories/subtrees, VNW-V10 and recovery are outside the proposed envelope. There is no evidence-based requirement for an additional physical write merely to promote the specified unread root-BMP envelope. A concrete new format/state defect discovered during implementation would require reassessment.

No code edits, USB access, new physical operation, GUI input, safety-store mutation, push or merge occurred during this assessment. Raw hardware evidence remains external and unmodified.
