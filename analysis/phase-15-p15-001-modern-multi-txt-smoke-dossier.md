# P15-001 — modern multi-TXT smoke-test dossier

Date: 2026-08-30
Status: **IMPLEMENTATION_READY — superseded by P15-002**
Risk: **R3 — device/safety critical**

This is a historical offline dossier only. It is not executable because it
reuses the stale Capture 01 pre-backup and has no isolated live runner. No
modern `0x101b` transaction was performed. Use the corrected P15-002 dossier
for any future hardware consideration; its separate operation-specific owner
approval is still required and the legacy Capture 01 approval cannot be reused.

## Exact constrained operation

One additive root-level folder, `IC_P15_MULTI_20260828_01`, with exactly four
ordered TXT children:

```text
root\IC_P15_MULTI_20260828_01\chapter-01.txt
root\IC_P15_MULTI_20260828_01\chapter-02.txt
root\IC_P15_MULTI_20260828_01\chapter-03.txt
root\IC_P15_MULTI_20260828_01\chapter-04.txt
```

The committed package manifest SHA-256 is
`c03ccc0feb3bebb4314d6f748c227a19ba37bd4e56db08c04bec474e398dade1`.
The four source hashes, in order, are:

```text
8c262bd0f7b0ca44770de0c36f7a5a1a0f1c61d8d76f9903a99d3d285b276231
075363590fc049ed269a5033686ec727a63e7e1c440735858df8a6d7cba5b533
247ecfcdfbb9d778159897c9fc74a789b8533509f4450abaa2614f68df27e730
e92b86f6b261800d1ca3c9a4c3c9b3eec7dc20002e16667c2f15eff79f1e9812
```

No BMP, nesting, second folder, batch, delete, synchronization, or retry is
inside this dossier.

## Native evidence basis

Capture 01 independently verifies the exact four-child record/table/order,
32-byte TXT wrappers, 120-byte payloads, parent markers, 992-byte model
growth, capacity fit, fixed-state equality, unchanged unrelated payloads, and
native transaction ranges 05+08 equal to the complete post dynamic blob.

The owner-supplied event mapping is:

| Timestamp | Owner observation |
| --- | --- |
| `stamp-0001` | Manager/SnoopyPro initialized and idle |
| `stamp-0002` | Immediately before Send Selected |
| `stamp-0003` | Transfer completed and packets idle |

The owner also observed Manager returning to its normal state without an error
or ambiguity. The complete post backup independently proves persistence.

The native numeric request-4 word remains unresolved after an offline scan of
the existing USB log tail. This is explicitly retained as unresolved, not
converted into a native success value. It does not contradict the owner’s
normal-return observation or the post-backup persistence. The future modern
workflow nevertheless requires an explicit numeric `0x0000`.

## Approved modern policy

- Preserve every existing record timestamp exactly.
- Assign `0x6a91a907` as one explicit operation timestamp to all six new
  records (folder, parent marker, and four children).
- Do not reproduce the native legacy operation-wide timestamp rewrite.
- Treat native child 4’s one-second difference as observed sequential legacy
  serialization, not a modern invariant.

The modern candidate has SHA-256
`12cf167f1c6486ac166d2cc95d6285c7bfdbffe143875ed8c6ddc30f836ec6f9` and
model length 2,052,272 bytes. It has the same path set/order, payloads,
prefixes, and non-timestamp metadata as the native post. Its prospective
`0x101b` transaction SHA-256 is
`63b2c991f87599a5d30b0649c06e9eb697abf2154bacab4d3d2f1bdf96f13286` with
range lengths `[256, 64, 65216, 0, 64, 0, 0, 2052208]`.

The exact Capture 01 pre-backup is bound by manifest SHA-256
`1e9c3000d6c0a881667dacb3cf76b3d04a854f6f80f4526be09e2600b5cb7c9d`,
dynamic-model SHA-256
`d4e4fa74e4338c18aa366e016ba9cb756d0af4e84b3bd19045993553d3526f20`, and
device identity `054c:001e`. The native capacity response is bound by
`c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a` and
reports a 3,145,728-byte limit; candidate growth is 992 bytes.

## Fake-only verification

The candidate, exact authorization binding, fake-before/fake-after backups,
and workflow audit are preserved outside Git under:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-15-p15-001-native-multi-txt-20260828-01/07-analysis/`

The guarded workflow made one fake transport call, simulated completion
`0x0000`, and passed independent read-back verification for the exact four
children, shared timestamps, fixed state, and unrelated object set. Automatic
retry is disabled. This is host-only validation and is not physical proof.

## Hardware stop

`IMPLEMENTATION_READY` is the final state of this historical dossier. It must
not be used to authorize a device operation. P15-002 is the active corrected
boundary; before any later operation, the owner must issue a new, separate
operation-specific approval, the operator must obtain a new complete fresh
pre-operation backup and revalidate every binding, and the exact constrained
package must pass the isolated preflight. A missing, ambiguous, malformed, or
nonzero completion is terminal with no retry.
