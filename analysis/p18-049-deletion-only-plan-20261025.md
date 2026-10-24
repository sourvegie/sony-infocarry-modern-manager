# P18-049 final Delete — new single-write task

Date: 2026-10-25 JST. Status: prepared; no owner approval or physical deletion.

## Scope and immutable identity

New task envelope SHA-256:
`0fbc9a8216bd383b9b86e7f1632fdd8ebc0d3025a4620bdbdbece2fd76d556e1`.

Reviewed code: `51d6b75166a164c2fba707506fbeb3d2164f37d2`.
Later documentation checkpoints must contain no source/script/test differences.
Private envelope location:
`/private/tmp/p18-049-final-delete-readonly-20261025-01/frozen-task/task-envelope.json`.

Only Sony InfoCarry **VNW-V15** is admitted. The one existing target is
`root\IC_P18_040_NESTED_20260930_01\Section-A\IC_P18_049_DELETE_A.txt`.
Its record is `0x880`; existing Section-A parent is `0x700`. It is unique,
unreferenced, unread ordinary TXT, flag `0xe0`, opaque `0xffffffff`, selector
`0x200`, with the existing exact 32-byte prefix. No placement is proposed.

| Binding | Exact value |
| --- | --- |
| Target payload | 34 bytes, SHA-256 `aa1cecbacdeb3daa43c1b162aee68c7d3ad87f89f98874b61db0c02569984975` |
| Current target raw record | `3b48b8f20323c1a64f881a42446c47687a1f4d3125884c18a505119cf4c1e215` |
| Target native prefix | `d0bcc6bc85dc36cdc1ad3882952c5d3d4414869c0bdd75b3b58ba28a32deb92a` |
| Current dynamic object | `a0d28fbbd8ce6bd354df9f91ccf0088c045f84053178e9f4523c6de615933475` |
| Delete candidate/original dynamic object | `6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8` |
| Delete transaction | `e5831e0e363cab494c3f4aa859763808fa5a7676b01c6fd4ddb15edd4d58c452` |
| Fresh native manifest | `bfb1e7b9ba12f20fa3f85c2997e1b7b95b095aeda323664d9c62b440286ed522` |
| Original restoration manifest | `88b4567b32bd174311e9eb0cc089d1fff5a97bbbf73a521f0abac49b9e80c2e9` |
| Capacity | 3,145,728 bytes; exact response identity in envelope |

The envelope contains all eight current and restoration object hashes. The
fresh native eight-object backup equals the independently verified actual
placement, including its native `0x0024` response and probe. The original
restoration set equals the original approved pre-placement baseline.

## Entire remaining physical sequence — one operation

1. Acquire fresh native capacity and complete eight-object backup through the
   existing guarded Delete preparation. Require exact frozen current state,
   capacity, target record/payload/path, candidate, transaction and restoration
   bindings. Freeze the new operation identity against that verified state.
2. Under the **new** task-level owner approval, invoke the existing authorization
   and normal Delete confirmation gates for this one operation. Consume one
   durable claim, arm one sender marker and send one transaction at most.
3. Require integer native `0x0000`, complete independent post-readback and all
   eight original object hashes before canonical success. Verify exact single
   removed path, surviving parent/siblings/markers, every survivor timestamp,
   payload, prefix, ordering and protected references; then refresh from verified
   native evidence. Dynamic size returns 2,210,564 → 2,210,432 bytes and record
   count 455 → 454. All 300 preexisting payload/prefix pairs and 79 markers survive.

**Maximum physical sender invocations: one.** No placement, retry, restore,
automatic recovery, extra setup or cleanup write. Stop on any mismatch,
ambiguous/missing/nonzero completion, failed readback or safety inconsistency.
An attempted/stopped task directory cannot be reused. Fresh preflight is repeated
after reconnect; no ambiguous send is resumed. One approval covers this entire
listed operation and its existing internal confirmation gates.

The prepared opt-in executor is external/private and unexecuted:
`/private/tmp/p18-049-final-delete-executor.py`. It requires the full new envelope
hash, independent executor review, a separately preserved new owner approval,
unchanged reviewed source and explicit write-enabling option. No approval file
exists at preparation. The old stopped executor is not modified or resumed.

## Resolution and validation

The [separate provenance investigation](p18-049-provenance-resolution-20261025.md)
documents a real source-identity mismatch. It does not describe the two source
payloads as equivalent or amend old approval. Independent reconstruction proves
all copied bytes match and all differences are overwritten or never copied;
the original provenance failure and execution records remain unchanged.
Deletion derives from the existing target and names no insertion template.

The correction reuses the existing selector, adapter, confirmations, claims,
markers, lock, sender and verifier. Restoration hashes are sealed in the existing
bundle and checked against independently reverified after-backup bytes before
terminal success. Regression covers same-output/different-source rejection,
wrong task/state/capacity/target/source binding before claims, and auxiliary
native-object mismatch retaining existing indeterminate-write protections.

- Portable suite: **1,281 run / 1,276 passed / five established skips**, 275.138 s.
- Executor focused tests: 25 passed; independent focused tests: 106 passed.
- Compile and diff checks passed; macOS package/signature passed.
- Packaged Tk/GUI/runtime smoke passed with isolated home and zero USB enumeration,
  physical sender, claim and sender-marker counters.
- Fresh read-only staging passed with zero senders/writes, 25 unchanged claims,
  zero sender markers, unchanged clear lock and 103 unchanged original files.
- Primary P18-034 checkout: original head/status and all 1,107 dirty-path evidence
  entries preserved. Origin main independently remains `25bfddda7232617f7fc84ada4c44c9440306b584`.
- Local ancestry/privacy audit passed: sanitized base is an ancestor, excluded
  personal JSON blob is absent, no outgoing blob exceeds 1 MiB, and changed files
  contain no raw native captures, device archives or personal source paths.
- Exact-code-head and final scope/executor R3 outcome:
  [independent report](p18-049-resolution-r3-review-20261025.md).

No physical write occurred during this resolution. Delete remains unperformed,
the fixture remains in place, and baseline restoration is still a proposed
postcondition. General nested Delete remains disabled. No push or merge.

## Single owner approval request

Approve envelope
`0fbc9a8216bd383b9b86e7f1632fdd8ebc0d3025a4620bdbdbece2fd76d556e1`
for deleting only the existing named VNW-V15 fixture, with at most one sender,
fresh guarded preflight and complete independent restoration of all eight
original native objects, zero retries and no other device writes.

Stop here until that new owner approval is supplied.
