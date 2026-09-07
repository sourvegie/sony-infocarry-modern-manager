# P18-014 — Fresh Post-Recovery Operation Identity Closure

Date: 2026-09-07
Repository: `sourvegie/sony-infocarry-modern-manager`
Canonical base: `5dc54cb04fcef9025b8e3f347e69b335af887135`
Branch: `task/P18-014-fresh-operation-identity`
Risk: R3 host-only safety preparation
Disposition: **ESCALATION_REQUIRED — EXTERNAL CI BILLING BLOCKER**

## Boundary

P18-014 prepares one fresh, hash-bound host operation for a later, separately
authorized P18-015 physical validation. It does not perform that validation.

The following remained zero throughout this task:

- USB/device-changing operations: **0**;
- `0x101b` transmissions: **0**;
- execution claims consumed: **0**;
- sender markers created: **0**;
- device-content changes: **0**;
- capability-matrix expansion: **0**.

No raw backup, candidate, transaction, or capture bytes were added to Git.
The durable raw evidence remains outside Git at the preserved P18-012 archive.

## Fresh target and operation phrases

The fixed destination is:

```text
root/IC_P18_LIBRARY_20260907_01
```

The exact ordered package is:

```text
root/IC_P18_LIBRARY_20260907_01/01-introduction.txt
root/IC_P18_LIBRARY_20260907_01/02-page-01.bmp
root/IC_P18_LIBRARY_20260907_01/03-ending.txt
```

The preserved P18-012 baseline has 404 records and 339 logical paths. The
new root is absent from that baseline; the former
`IC_P18_LIBRARY_20260906_01` root is present as historical content. The
candidate adds exactly the four paths above, with no removed paths.

The operation is bound to these exact phrases:

```text
owner approval: APPROVE P18-015 V15 PHYSICAL VALIDATION 01
confirmation:   ADD IC_P18_LIBRARY_20260907_01 ONCE
```

The stale P18-010 pair
`APPROVE P18-010 AUX STATE PRESERVATION TEST 01` /
`ADD IC_P18_LIBRARY_20260906_01 ONCE` is rejected. The normal GUI/CLI does not
expose this operation, and no standing Send path was added.

## Preserved P18-012 evidence

The read-only evidence root used by the host reconstruction is:

```text
/Users/stardust/Projects/InfoCarry-Evidence/phase-18-p18-012-readonly-diagnostic-20260907-01
```

The evidence identities are:

| Evidence | SHA-256 |
| --- | --- |
| complete diagnostic inventory | `fec7ad5ac4ebbb3e1aae38d28c68c7bd07b831ff011ff6a550eed3141b256e43` |
| diagnostic manifest | `bc20a3bcf2383880710700b6682c937239054d7d8ac5ade21e0d19d98bfa8c60` |
| baseline dynamic blob | `6fd27699ca6c13a46f8d75467ba72860af8b865b7cf19046b7a91f63bf471e01` |
| canonical baseline state identity | `e603fecc087bd615bada4dd37f6636eba7af257a75d0f1baa0b913764e7797b4` |
| native `0x0019` capacity response | `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a` |
| reviewed template subset | `6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b` |

The baseline model length is 2,107,328 bytes. Native capacity is 3,145,728
bytes, parsed from the exact Sony `0x054c:0x001e` `0x0019` response at big-endian
offset `0x08`.

## Exact TXT → BMP → TXT candidate

The offline package was rebuilt from the preserved P17 source inputs using the
reviewed native TXT/BMP templates and the fixed target above. The package
manifest identity is:

```text
d2f78866bc05a79d46bdb9fdf47beec8d5c38920f0bbbd53799bdc137dabd6d1
```

| Order | Kind | Path | Payload length | Payload SHA-256 |
| ---: | --- | --- | ---: | --- |
| 0 | TXT | `01-introduction.txt` | 3294 | `38391cc8f2ea488c09990562539c206df14cfef5bad6148ab7e73b2af49ad9ad` |
| 1 | BMP | `02-page-01.bmp` | 10302 | `f795a8e1466c3988b804f344645a6208bdcfa27e9d51d8b314c99d9a5973aadd` |
| 2 | TXT | `03-ending.txt` | 2036 | `1dcafec84c06a52c24d898f389bb94fefea1c0569457ae92476c86a906fb5151` |

The candidate has 409 records and is bound by:

```text
candidate length: 2,123,364
candidate SHA-256: 2d21044987668c55d06aaa202fa678d760f9dbca99a96679eb4dff26e5e818ac
transaction command: 0x101b (not transmitted)
transaction payload length: 2,188,900
transaction SHA-256: 82be7e81b213fbb07eba86894ee525970b8a48a1101da5b4324857b1003d2fc8
```

The operation identity is distinct from P18-011/P18-010:

```text
P18-011/P18-010 candidate:   6fd27699ca6c13a46f8d75467ba72860af8b865b7cf19046b7a91f63bf471e01
P18-011/P18-010 transaction: 9373330cd78f58faaa0cfe61590e4cd0ce489ea5c8069c3112144e69aafe10f4
P18-014 candidate:           2d21044987668c55d06aaa202fa678d760f9dbca99a96679eb4dff26e5e818ac
P18-014 transaction:         82be7e81b213fbb07eba86894ee525970b8a48a1101da5b4324857b1003d2fc8
```

## Metadata insertion and capacity

The new metadata is inserted at relative offset `0x00000480`, absolute
record-stream offset `0x000004c0`. Metadata growth is `0x00000140` (320)
bytes across five records. Aligned content growth is 15,716 bytes and total
candidate growth is 16,036 bytes.

| Projection | Bytes |
| --- | ---: |
| baseline model | 2,107,328 |
| candidate model | 2,123,364 |
| capacity limit | 3,145,728 |
| remaining growth after candidate | 1,038,400 |

Capacity is sufficient under the reviewed VNW-V15 host policy. No write was
started.

## `0x001b` display-history preservation

The baseline `0x001b` response contains 7 active references. The candidate
rebases each independently established metadata-record pointer by the exact
320-byte metadata delta. The logical path is unchanged in every row.

| Logical path | Before relative | After relative | Before absolute | After absolute |
| --- | ---: | ---: | ---: | ---: |
| `root\\簡易マニュアル\\infoCarry端末の便利な機能\\ファイルにしおりをはさむ／表示する` | `0x1380` | `0x14c0` | `0x13c0` | `0x1500` |
| `root\\IC_P16_MIXED_20260830_02\\03-ending` | `0x0740` | `0x0880` | `0x0780` | `0x08c0` |
| `root\\IC_P16_MIXED_20260830_02\\02-page-01` | `0x0700` | `0x0840` | `0x0740` | `0x0880` |
| `root\\IC_P16_MIXED_20260830_02\\01-introduction` | `0x06c0` | `0x0800` | `0x0700` | `0x0840` |
| `root\\IC_P16_MIXED_20260830_01\\01-introduction` | `0x07c0` | `0x0900` | `0x0800` | `0x0940` |
| `root\\IC_P16_MIXED_20260830_01\\02-page-01` | `0x0800` | `0x0940` | `0x0840` | `0x0980` |
| `root\\IC_P16_MIXED_20260830_01\\03-ending` | `0x0840` | `0x0980` | `0x0880` | `0x09c0` |

The `0x001b` baseline and candidate response hashes are respectively
`edcdda12e1ba34c12bb8f6ae359ec091827169cff4af6b543c93733b3253cca8` and
`4c02a0c342255fa884a8ffe125b9b50607ad7681dc2d82895dd15db6e0636618`.
The count header/tail remains unchanged, all seven semantic paths resolve,
and unrelated/unshifted bytes remain identical.

## `0x001f` bookmark preservation

The baseline contains one bookmark group with four nonzero opaque values. Its
record pointer is independently established and moves with the same exact
metadata delta:

| Group | Logical path | Before pointer | After pointer | Opaque values |
| ---: | --- | ---: | ---: | --- |
| 0 | `root\\簡易マニュアル\\infoCarry端末の便利な機能\\ファイルにしおりをはさむ／表示する` | `0x1380` | `0x14c0` | 4 nonzero values, unchanged byte-for-byte |

The opaque-value byte sequence has SHA-256
`7a432732d8b32e64bd0fdbad9da48cb531ac9c907419823de7e890458aad2943` in both
baseline and candidate. The unused bookmark tail is also byte-exact. The
baseline and candidate `0x001f` response hashes are respectively
`11554c96607bad8c7ca1e8615311414b2540cf7afddf6fcb913050d173d1cf21` and
`2f41631fa45ef41a985ddc2213725b213172f6c1bca6594d0a0a7b0c2d1934d4`.

Only the independently proven pointer field moved. Opaque/unresolved values
were not decoded, regenerated, normalized, or otherwise rewritten.

## Zero-state auxiliary commands and unrelated state

The baseline and candidate each have zero active entries for `0x001c`,
`0x001d`, and `0x001e`. Their 64-byte response hash is unchanged for each
command:

```text
f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b
```

The candidate preserved 339 existing logical paths, 274 shared file payloads,
all shared timestamps, unknown record bytes, and all unrelated state. No
baseline path was removed. The candidate’s `expected_post_operation` contains
only the four new paths and the three listed payload hashes.

## Sealed host identities

The full read-only preflight was executed against the preserved evidence and
the exact package, then passed through the supported sealed-report and
operation-bundle constructors. The resulting temporary artifact identities
were recorded without retaining raw bytes in Git:

```text
core preflight seal: 57a605445b8a5fb9c8e0ae51aac2180487081bfc3e1c28cea8cfdf18e569cdf2
preflight seal:      601a500cf73ea5df1e89558737c0ad8f7531e8dcbfc8a4258fea39a311281410
candidate audit:     ada9cb88328e63bfaced559d5e4fe6f44b24d848f90033d99b0d13ec1bd526db
authorization:       0b15f3bb6f51cef55b177f6701487e607281a0ab84e1fb512598b79a5452750f
operation bundle:    d34ed9b00f133eb3c4b24fb55eaea7c7868a7c45e0da5d68c4ec710f9e823539
capacity response:   c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a
baseline state:      e603fecc087bd615bada4dd37f6636eba7af257a75d0f1baa0b913764e7797b4
```

The operation bundle binds the target, ordered children, candidate and
transaction hashes, fixed-state before/candidate hashes, template subset,
capacity response, baseline identity, policy, authorization phrases, and
expected post-operation result. It does not consume or reference a new
execution claim.

## Durable safety state

P18-013 completed before this task. P18-014 reread and left the durable state
unchanged:

| State | P18-014 result |
| --- | --- |
| installation-wide lock | `cleared` |
| active sender marker | none |
| P18-011 claim `827bfde0b93d4b2da57ee646ff6aaa1d` | permanently `consumed` |
| SQLite integrity | `ok` |
| new claim or marker | none |

This task did not clear, create, resolve, or consume any durable safety-state
record.

## Verification and review

The focused live-adapter, experimental review, and P18-006 adversarial suites
passed with **83 tests**. The real-evidence P18-014 tests passed with **2
tests**. They cover target absence, exact new operation identity, candidate
and transaction non-reuse, display-history/bookmark semantics, opaque-value
preservation, zero-state auxiliary commands, recovered lock state, absent
marker, claim-store integrity, and permanent claim consumption.

The full portable suite passed with **757 tests and 3 intentional skips**;
Python 3.12 compilation and `git diff --check` passed. The focused PR is
[PR #40](https://github.com/sourvegie/sony-infocarry-modern-manager/pull/40)
at commit `9f08573`. Both required Python 3.12 CI legs passed:

- [macOS CI](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/34129931847/job/101767343505);
- [Windows CI](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/34129931847/job/101767343079).

Independent strong R3 review round 1 found `P0=0, P1=1, P2=0`: the record
claimed final readiness before commit, PR, CI, and final review existed. The
bounded correction changed this record and `CURRENT_STATUS.md` to provisional
host-validation-complete wording. No implementation or safety finding was
raised. Final independent strong R3 review round 2 found `P0=0, P1=1, P2=0`:
the passing CI run above covered commit `9f08573`, while the reviewed commit
`650536fb86ed1bfdaba1d6bf737249f8e8525044` was rejected before any workflow
step by GitHub's account billing/spending-limit condition. A rerun of
workflow `34130375371` failed identically on both macOS and Windows. Therefore
the final `P0=0, P1=0, P2=0 — PASS` gate cannot be issued. No implementation or
safety finding was raised; the exact blocker is external CI availability.
The task remains host-only and stops here; P18-015 is the separate
owner-approved physical validation task.
