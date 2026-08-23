# Milestone I.4 constrained modern package safety — offline result

Date: 2026-08-23

This note records the completed offline safety slices for one experimental
modern policy. It does not claim legacy-equivalent folder creation and does
not authorize a live device operation.

## Supported scope

Exactly one new root-level folder containing exactly one TXT child:

```text
root\<one CP932 folder name>\<one CP932 TXT name>.txt
```

The source is one local UTF-8 TXT. Preparation is strict CP932 with CRLF
normalization. The folder, its leading `..` marker, and the child receive one
explicit frozen `new_record_timestamp_be32`. Every existing record timestamp,
native prefix, payload, and unknown field is preserved except the proven
metadata/content offset and length rebasing required by the captured geometry.
No category, mark, bookmark, selection, history, or Manager-side sidecar
membership is assigned.

The candidate requires a complete fresh backup, a preserved capture-7-shaped
template, exact capture-7-compatible all-zero fixed state in `0x001b` through
`0x001f`, a verified native total model limit with
`candidate_model_bytes <= capacity_limit_bytes`, no case-insensitive path
conflict, and an unchanged source hash. The offline capacity semantics and
the distinction from the Manager UI display are recorded in the Milestone I.5
note.

## Evidence classification

| Item | Classification | Boundary |
| --- | --- | --- |
| Capture 7 has one folder, one leading marker, and one TXT child | verified observation | preserved in the Milestone I capture-7 evidence and golden tests |
| Capture 7 fixed-state objects are identical all-zero blocks before/after | verified observation | supports only the exact all-zero preflight |
| Existing shared timestamps can remain unchanged under the constrained policy | verified in modern root-TXT/replacement evidence; observed in capture 7 | does not solve legacy operation-wide timestamp generation |
| One frozen timestamp is used for the three new records | explicit modern policy | never generated implicitly and never presented as legacy equivalence |
| Fresh all-zero state bytes are transmitted unchanged | verified offline model behavior | any nonzero or unfamiliar byte is rejected |
| Native dispatcher capacity is a total model limit | verified static data flow in I.5 | live package transfer remains prohibited; Manager UI mapping remains separate |
| Completion `0x0000` is accepted | existing modern write protocol rule | folder-package completion remains a live/unresolved hardware assumption |
| Physical atomicity or recovery after interruption | unresolved | fake transports do not prove it; R15 remains open |

## Offline implementation slices

- `9287c06` — separate constrained modern folder policy; shared timestamps
  remain unchanged and the explicit timestamp is bound to the three new
  records.
- `39c6f9f` — exact all-zero fixed-state preflight preserving fresh raw bytes.
- `a3bff5a` — candidate construction, path conflict, source, alignment, and
  complete-growth capacity gate.
- `216f49e` — package-specific authorization binding for device, backup,
  source/package, paths, timestamp, fixed-state hashes, capacity, candidate,
  transaction, and phrase.
- `36f7024` — independent completion, candidate, path, shared-byte,
  fixed-state, and unrelated-object read-back verifier.
- `3da2180` — fake-only guarded workflow with one-shot and interruption
  handling.

The I.4 implementation checkpoint passed **329 tests** with:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -q
```

All candidate, authorization, verifier, and workflow tests are offline or
fake-transport tests. No package GUI/CLI action is enabled.

## Remaining boundary

The modern package policy is ready for a separately reviewed, unexecuted
smoke protocol only. It is not yet proof of live package compatibility. The
protocol must record the exact fresh-backup-derived folder offset, child
offset, source/payload hashes, frozen timestamp, candidate hash, transaction
hash, capacity calculation, and complete before/after evidence. Any
interruption after `0x101b` begins is indeterminate and must not be retried.

The owner-readable protocol is
`analysis/phase-12-milestone-i4-unexecuted-modern-package-smoke-protocol-20260823.md`.
Preparing it is not approval to execute it.

## I.5 follow-up

Milestone I.5 resolved the native ordinary-worker capacity semantics offline
in `analysis/phase-12-milestone-i5-capacity-semantics-20260823.md` and its
machine-readable companion. Commit `9657e85` adds explicit
`capacity_limit_bytes`, `baseline_model_bytes`, `candidate_model_bytes`,
`candidate_growth_bytes`, `remaining_growth_bytes`, and `capacity_source`
fields to the package candidate and authorization audit. I.6 then adds
hash-bound parsed `0x0019` evidence, native-capacity-only live eligibility,
the ordered fake workflow, and the isolated unexecuted runner in commit
`09452be`. The complete suite now passes **357 tests**. The Manager display
and command `0x0024` remain excluded from free-capacity calculations. No live
package write is authorized.
