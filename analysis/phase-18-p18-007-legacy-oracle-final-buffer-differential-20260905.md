# P18-007 — Legacy Oracle final-buffer differential

Date: 2026-09-05
Base: `origin/main` at `359c27adf473c86a8f2770de64712b81dc893e25`
Outcome: `COMPLETE` for the offline evidence and host-side differential boundary; no hardware or USB operation occurred.

## Legacy boundary

The latest safe boundary established from preserved evidence is the host-side
`0x101b` command header and payload immediately before the host submits the
bulk records to the legacy driver/USB path. The existing read-only
`infocarry.usblog` parser locates the native command record, validates its
declared length and completion records, and recovers the observed eight-range
layout: ranges 1, 2, 3, 5 and 8 carry data while ranges 4, 6 and 7 are empty.
Range 3 contains the verified `N/M` staging fields; in the preserved ordinary
path `N=0` and `M=len(range5)+len(range8)`. The candidate/library model is
therefore `range5 + range8`, while the wrapper remains the complete command
header plus all eight ranges.

This task used already-preserved captures only. It did not run Sony Manager,
VICCTR, VicOne, a legacy driver, or any Send operation. No final-buffer
interception with a connected InfoCarry was attempted. A future external
observation must use a structurally prevented transport: no device passthrough
or a stubbed final driver call, break before continuation at the final command
submission, dump the command header and eight ranges, and never continue into
the send. The returned artifact must be a sanitized manifest containing the
fixture identifier, command/header bytes or hash, range lengths and hashes,
candidate hash/length, transaction hash/length, and the prevention evidence.

## Reusable Oracle boundary

`src/infocarry/legacy_oracle.py` is an offline comparison layer only. It is
not imported by the sender, GUI, CLI, authorization gate, or coordinator. It
provides:

- deterministic SHA-256 and length identities;
- raw contiguous differing ranges, including length mismatches;
- independently supplied volatile/deterministic annotations that never erase
  raw differences;
- normalized views that retain the raw view and the rule/evidence;
- parsed backup record/header/path/payload comparisons;
- separate command-header and per-range transaction comparisons;
- sanitized corpus metadata validation, including representation hash checks.

Classification is strict: exact bytes are `EXACT_MATCH`; established rules
are `EXPLAINED_DETERMINISTIC_DIFFERENCE`; independently established changing
fields are `EXPLAINED_VOLATILE_FIELD`; all remaining changes are
`UNEXPLAINED`; semantically mismatched representations are `NOT_COMPARABLE`.

The sanitized corpus manifest is
[`corpus.json`](../samples/generated/P18-007-legacy-oracle-differential/corpus.json).
It contains no Sony executables, drivers, raw captures, private backups, or
user content.

## Representative corpus

| Fixture | Shape | Legacy candidate | Modern comparison input | Result |
| --- | --- | --- | --- | --- |
| A / P13 I7 | one root TXT | 2,053,380 bytes, `7d64a9dc…c1c805f` | low-level existing template reconstruction, 2,053,384 bytes, `fdb313d5…72a8790` | `UNEXPLAINED`; public builder rejects its five-byte padding result |
| B / P15 Capture 11 | four ordered TXT children | 2,052,272 bytes, `08d8eead…5ac99` | existing modern candidate, same length, `12cf167f…36ec6f9` | raw timestamp/checksum differences; normalized candidate `EXPLAINED_VOLATILE_FIELD`, zero residual ranges |
| C / P16 Capture 12 | root folder with TXT → BMP → TXT | 2,064,268 bytes, `6c654fe4…d796b` | existing modern P16-002 `_02` candidate, 2,075,256 bytes, `4bfe8a54…6f849` | whole blobs `NOT_COMPARABLE`; typed package projection `EXACT_MATCH` |
| D | nested/hierarchical probe | unavailable | unavailable | `NOT_COMPARABLE`; optional evidence not obtained |

Legacy transaction lengths/hashes and modern transaction lengths/hashes are
recorded separately in `corpus.json`; they are not conflated with candidate
hashes.

## Differential results

### A — single TXT

The preserved legacy transaction is 2,118,916 bytes (`cc23dc8f…c6dff1`);
the diagnostic modern wrapper is 2,118,920 bytes
(`1dae57af…15b17e`). The candidate raw comparison has 88,274 changed ranges
covering 1,394,198 bytes. After only timestamp/checksum annotations, 87,901
ranges covering 1,393,079 bytes remain. The first divergence is in the
backup header/checksum region, and the final four-byte length difference is
retained. Parsed structure has equal record/reachable counts (374/315), but
250 `field_04` offset differences remain in addition to 373 timestamp
changes. This is an unresolved allocation/alignment discrepancy, not an
equivalence claim.

The existing public `build_new_root_txt_add` independently rejects this result
because its observed-padding guard computes five bytes outside its allowed
zero-to-three range. The Oracle records the low-level result only to localize
the discrepancy; P18-007 does not modify that production path.

### B — four ordered TXT

Legacy and modern candidate lengths are equal. Raw comparison retains 374
ranges and 1,121 changed bytes: 373 timestamp ranges plus the derived
checksum. After the documented annotations, normalized comparison has zero
ranges. Parsed structure has equal 378 records and 313 reachable records;
all 373 semantic differences are `timestamp_be32`, with no non-timestamp
structural differences.

The wrapper comparison is also separate: ranges 1–4, 6 and 7 are exact;
range 5 differs only in the derived checksum and range 8 contains the same
373 volatile timestamp ranges. The normalized wrapper result has no residual
ranges. This supports a general ordered-child allocation/count rule for four
TXT children in this evidence, but does not prove arbitrary package sizes.

### C — TXT/BMP/TXT

The native and modern whole blobs are intentionally marked
`NOT_COMPARABLE`, not normalized to equal: native P16 `_01` was generated from
its pre-operation baseline, while the preserved modern P16-002 candidate adds
`_02` to the `_01` post-state. The raw byte comparison is retained in the
manifest (128,906 changed ranges and 1,735,793 changed bytes), as is the
wrapper mismatch.

The semantically bounded package projection is exact for four records in the
same relative order: directory, TXT, BMP, TXT. Both TXT records use the
32-byte prefix hash `d0bcc6bc…2deb92a`; the BMP record uses the distinct
16-byte prefix hash `5ac6a594…465461b`. All three payload hashes, lengths and
alignment padding match. This supports ordered-child construction with
type-specific record prefixes; it is not proof that the whole modern
transaction equals the native `_01` transaction.

## General algorithm versus branch assessment

| Dimension | Assessment | Evidence | Exceptions / uncertainty |
| --- | --- | --- | --- |
| record allocation | Unclear | P15 and the C projection preserve regular record sizing; A has a four-byte allocation/offset discrepancy | Do not repair or generalize from A inside this task |
| child count | Yes for observed flat shapes | one-child A, four-child B, and three-child C projections use explicit record counts | Not an envelope-wide proof for 1–8 or nested cases |
| child order | Yes for observed flat shapes | B preserves four TXT order; C preserves TXT/BMP/TXT order | No hidden sort-key proof beyond these fixtures |
| TXT creation | Unclear | B matches after timestamp/checksum annotation; A exposes an unresolved padding/offset issue | P13 production behavior is put in doubt and requires a separate R3 task |
| BMP creation | Unclear, type-specific path supported | C projection matches a distinct 16-byte BMP prefix and payload/alignment facts | Whole-blob equality is not comparable |
| timestamps | Explained volatile field only | P13/P15/P16 evidence shows operation-time rewrites | Do not generalize a timestamp value or source-time policy |
| fixed state | Partially supported | B fixed ranges 1–3 and empty ranges match; C native evidence records the reviewed all-zero fixed-state shape | Marks/bookmarks/display-history semantics are not fully resolved |
| auxiliary reading state | Unclear | Existing evidence covers selected bookmark/display-history constraints, not all sidecars | Do not infer that all auxiliary state is zeroed |
| transaction framing | General observed wrapper, not production proof | `0x101b`, eight ranges, `N/M` staging and separated candidate/body comparisons; B matches after annotations | A discrepancy remains; completion semantics are outside this offline task |
| nesting | Unclear / unavailable | No sanitized hierarchical final-buffer fixture was available | No hierarchical live claim or enablement |

## Auxiliary state and persistence

P18-007 does not decide an owner policy for Bookmarks, Marks, display history,
or Manager-side sidecars. It records only what the available comparisons show;
unresolved state remains unresolved. The P18-006 process-local one-shot claim
remains an explicit pre-hardware closure item. P18-007 found no evidence that
changes how that claim should bind transaction identity, so cross-process
persistence remains for the next separately reviewed Product Delivery safety
task.

## Safety and external evidence

- No device write or `0x101b` transmission occurred during P18-007.
- No legacy Send operation was run for this task.
- No candidate, authorization, sender, GUI, CLI, VNW-V10, hierarchy, deletion,
  restore, or synchronization capability was broadened.
- Raw unexplained ranges remain represented by counts, byte totals, first/last
  divergence bounds, and range-list digests; no unexplained bytes were
  normalized away.
- External Windows 2000/Manager evidence is not required for the A–C host-side
  corpus result. It remains required only for a future same-baseline final
  buffer observation if the C whole-blob question or hierarchical probe must
  be resolved. The safe procedure is the structurally prevented interception
  described above; a connected VNW-V15 must not be used merely to progress the
  Manager.

## Validation and review

Focused Oracle tests cover exact equality, single/multiple/separated ranges,
length mismatch, volatile annotations with raw retention, unexplained
differences, metadata/hash failures, deterministic reports, parsed structure,
transaction-wrapper annotation/classification, range-count mismatches, and
nested classification validation. The sanitized corpus is loaded and
validated by test code.

The verified host-side validation checkpoint is 19 focused Oracle tests
passing; 85 relevant reconstruction/parser/P17/P18 tests passing with two
pre-existing capture-dependent skips; and the full portable offline suite
passing 733 tests with three existing intentional skips. A read-only compile
sweep covered 194 Python files. Direct `compileall` was not usable because
the checkout contains protected pre-existing `__pycache__` entries; no source
compile errors were found by the read-only sweep. `git diff --check` passes.

Independent R2 review and re-review passed with no remaining material
findings. The review performed one primary correction round plus one bounded
nested-summary follow-up, within the two-round limit. It specifically verified
raw/normalized retention, strict classification and `NOT_COMPARABLE` metadata
rules, candidate/transaction separation, proprietary-evidence exclusion, and
absence of USB/live reachability. Any P13 R3 correction is explicitly out of
this review scope. Focused PR #33 CI also passed on [macOS Python
3.12](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/33961805274/job/101294857830)
and [Windows Python
3.12](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/33961805274/job/101294857765).
