# P18-041G — Surviving timestamp rule characterization

Date: 2026-10-04 (Asia/Tokyo)

Disposition: **TIMESTAMP RULE UNRECOVERABLE FROM ARCHIVES — BOUNDED PHYSICAL EXPERIMENT JUSTIFIED**

Branch at analysis start: `task/P18-041F-guarded-root-leaf-delete`
(`bc6daa9`), based on canonical `origin/main`
`5bca280ffbd673fa56a2646a65b0329a4dc496f2`.

## Scope and safety boundary

This was an offline-only evidence analysis. No production deletion path, UI
control, sender, claim, marker, lock, USB session, or hardware write was
added or reached. No file under `sources/` or any external evidence checkout
was modified. The complete per-record machine-readable comparison is in
[private machine-readable timestamp comparison omitted].

The probe compares parsed record metadata only; it does not use the historical
timestamp map as a candidate-builder input. The field is interpreted as a
big-endian 32-bit Unix-style seconds value and rendered in UTC using the
established parser conversion. The preserved Windows timestamp tool records
local time, UTC time, epoch milliseconds, and a +09:00 offset, but its sequence
numbers are not event identities without a separate mapping.

## P18-041F exact comparison

Inputs:

| Artifact | SHA-256 | Bytes |
| --- | --- | ---: |
| Exact baseline | `aec90438c1323400b2f4d4210541c599600f4e9493596edc710bd676dee8adf6` | 2,051,000 |
| Historical native/post-delete output | `88b95f8bc158ab89253faea8c9085799cebba76abf0a3f416afa62df8b55f287` | 2,050,848 |
| Existing modern structural candidate | `dc099dca21169054c4643ed346fc617f3e991e9ae9f93e7c3b07fedb57895df9` | 2,050,848 |

The target was exactly `root\IC_E_ADD_20260822_04.txt` at metadata offset
`0x2c0`. The native output has 368 → 367 records and removes exactly that
path. The comparison table contains all 367 surviving records, including
unreachable `..` marker records by serialized identity.

The exact field statistics are:

| Statistic | Result |
| --- | ---: |
| Surviving timestamp fields compared | 367 |
| Fields whose integer value changed | 367 |
| Timestamp bytes differing | 734 |
| Equal timestamp bytes | 734 |
| Bytes differing at record `+0x0c` / `+0x0d` | 0 / 0 |
| Bytes differing at record `+0x0e` / `+0x0f` | 367 / 367 |
| Four-byte fields with all four bytes changed | 0 |
| Fields with exactly two bytes changed | 367 |
| Modern-candidate vs native-output header checksum | yes; 3 bytes in the derived field differ |
| Non-timestamp record-structure differences after established rebasing | 0 beyond the expected structural transformation |
| Surviving file payload mismatches | 0; 253 payloads remained byte-identical |

The 734-byte residual is therefore not 367 independent four-byte rewrites
with coincidental equality. It is a narrower two-low-byte rewrite in every
surviving field. Among the 367 surviving records, baseline timestamp values were
`0x6a8a2458` (76), `0x6a8a2459` (175), `0x6a8a245a` (115), and
`0x6a8a24b4` (1). Native post values were `0x6a8a82c0` (184),
`0x6a8a82c1` (136), and `0x6a8a82c2` (47). The old-to-new mapping crosses
baseline timestamp classes; it is not a value-preserving or one-to-one
conversion.

The post value follows serialized ordering in broad runs (41 runs; largest
run 169), but record type is not sufficient: directories use `0x6a8a82c0`
and `0x6a8a82c1`, while files use all three values. No surviving record's
post value equals either same-record baseline neighbor timestamp in this
case.

## Independent native corroboration

The same read-only probe compared preserved native output for five additional
cases. Modern-generated candidates were not used as native
corroboration.

| Case | Native before → after | Shared records | Shared timestamp changes | Post shared values |
| --- | --- | ---: | ---: | --- |
| P12 clean legacy root-TXT add | `51fb612e…` → `c86f5523…` | 308 | 308 | `0x6a891db6..b8` |
| P13 legacy root-TXT add | `fbebd820…` → `7d64a9dc…` | 314 | 314 | `0x6a8c4ba3..a5` |
| P13 legacy root-TXT delete | `5b081faf…` → `fbfe0dc9…` | 373 | 373 | `0x6a8d8c6b..6d` |
| P15 native four-TXT add | `d4e4fa74…` → `08d8eead…` | 313 | 313 | `0x6a91a7fa..fd` |
| P16 native TXT/BMP/TXT add | `70ea314d…` → `6c654fe4…` | 323 | 323 | `0x6a942348..4a` |

Across every independent native case, all shared timestamps changed and the
post values occupy a short consecutive-second window. The exact window and
the assignment of values to records vary by operation. P15 has an owner-
supplied event mapping, but the post metadata values precede its first
captured initialization-idle timestamp by seconds; P13's post window lies
between the preserved before/after event observations. P16 v2 maps all three
preserved timestamps: shared values are `12:34:16–18Z`, before the
`12:34:40Z` initialization point, while the new-record value `12:38:33Z`
falls within the send interval. These mappings constrain timing hypotheses but
still do not prove a particular clock source.

The native cases reject these candidate families:

- one common operation timestamp: falsified by 3–4 post values in every case;
- copied root/header timestamp: falsified by multiple post values per case;
- copied direct pre-operation predecessor/successor timestamp: P18-041F
  produced no same-record baseline-neighbor matches and all cases cross
  baseline timestamp classes. This does not exclude a broader post-operation
  serialization dependency;
- preserved filesystem/creation timestamp: falsified as a general rule by
  operation-wide rewrites of all shared records;
- simple path/type rule: files and directories share post values and the same
  old timestamp can map to multiple post values;
- simple endianness/epoch conversion: all values are valid big-endian
  Unix-style seconds, but no conversion of preserved baseline values explains
  the new operation-specific windows;
- a deterministic rule from the currently available baseline alone: not
  established, because independently native operations with different
  contexts produce different windows and no complete causal input is
  preserved.

The evidence is consistent with a native reconstruction/serialization pass
that obtains one or more environment or filesystem times and assigns them
while emitting records. That is a hypothesis, not an implementation rule.
Static inspection already found Windows file-time conversion helpers in
`VicTwo.dll`, but no proven write-side path from those helpers to record
`+0x0c`.

## Calibration result

Because no non-circular timestamp rule was established, the required
timestamp-rule re-run was not attempted. The existing structural delete was
re-run without a timestamp map and reproduced the prior candidate hash
`dc099dca21169054c4643ed346fc617f3e991e9ae9f93e7c3b07fedb57895df9`, not the
required native hash `88b95f8b…`. No checksum bytes were patched directly.

## Bounded physical experiment assessment

The archives are insufficient for a fresh deterministic rule, but one
bounded disposable experiment is justified because the remaining question is
narrow and the independent add/delete cases already show the exact observable
signature to isolate. This is a design only; it was not performed.

Fixture and operation:

- one ordinary root-level TXT named `IC_P18_041G_CLOCK_01.txt`;
- exact CP932/ASCII bytes: `P18-041G timestamp probe 01\r\n` (29 bytes,
  SHA-256 `9541c1b9d09ee7d4ab91c704755c4bea8b2022c3bb8f50aa15c1a990bf80c35d`);
- pre-stage the fixture before the sealed experiment begins, and take the
  fresh pre-delete backup only after that fixture is present; the experiment
  itself must not perform a native add;
- perform exactly one legacy root-level delete of that pre-staged item;
- if the fixture cannot be pre-staged without an additional hardware write,
  stop rather than broaden this experiment;
- no nested item, directory selection, subtree, second target, modern sender,
  retry, or unrelated Manager operation.

Required capture and gate:

1. Obtain operation-specific owner authorization and confirm the fixture is
   disposable.
2. Preserve and hash a fresh complete pre-delete eight-object device backup,
   the exact Manager-before files, and the exact fixture/source metadata.
3. Capture the native delete transaction once, with the one `0x101b` request
   and all ranges preserved. Record the declared length and candidate hash.
4. Capture Windows local time, UTC, epoch milliseconds, timezone, device clock
   if visible, and file creation/last-write times at four explicitly mapped
   points: before Manager initialization, after initialization idle,
   immediately before Delete, and immediately after the normal return. Keep
   event mapping separate from raw timestamp files.
5. Preserve Manager-before/after sidecars and one result observation, then
   take a complete post-delete backup and independently compare the exact
   logical one-path removal, all 367-style surviving timestamp fields, payloads,
   fixed-state objects, and checksum.
6. Stop on any malformed/ambiguous result or missing post-backup. Do not retry
   the delete. Keep the pre-backup and native ranges immutable.

Recovery must be decided and authorized before the delete: retain the
complete pre-backup and use only a separately approved, known recovery method
after the evidence is sealed. This experiment must not assume that the
unproven modern Delete/Restore path can recover the device. If no acceptable
recovery plan exists, the physical experiment is not authorized despite this
assessment.

## Validation and independent review

The read-only characterization script was syntax-checked, run against all six
native pairs above, and passed `git diff --check`. The existing structural
delete tests and the full portable suite remain the P18-041F baseline; no
production source was changed by this characterization.

An independent read-only R2 review inspected the exact analysis-tool diff,
generated JSON including all 367 P18-041F rows, cited native evidence, and the
non-circularity/safety gates. Findings were P0=0, P1=2, P2=3. The two P1
findings were corrected here: P16 v2's event mapping is now reported
accurately, and the physical design now requires a pre-staged fixture so the
experiment contains only one delete operation. The three P2 clarifications
were also applied: five additional cases (not four), checksum wording is
explicitly candidate-versus-native, and predecessor/successor falsification is
scoped to direct pre-operation neighbors. The reviewer confirmed that the
final disposition is supported. No physical experiment is part of this
checkpoint.

Safety counters for this task:

```text
hardware/USB sessions              0
hardware writes                    0
real 0x101b                        0
production sender calls            0
claims consumed                    0
sender-marker mutations            0
installation-wide lock mutations  0
```
