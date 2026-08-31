# P17-004 — fresh read-only Library-package live preflight

Date: 2026-08-31
Status: **READY_FOR_HARDWARE_TEST — fresh read-only preflight complete; stop at owner-approval boundary**
Risk: **R3 — device/safety critical**

## Scope and boundary

P17-004 prepared one explicitly grouped P17-002 Library package, performed the
authorized read-only device preflight, and sealed one future operation. It did
not request or consume live write approval, invoke a sender, or transmit
`0x101b`. No previous P16 evidence was modified. The package is experimental
host readiness for this exact new source content, not a physical compatibility
claim.

The external session root is:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-17-p17-004-fresh-library-package-20260831-02/`

The first reserved `...-01` session root was left non-overwritten after its
initial one-line source selection failed the short-excerpt validation. It was
not used for package, device, or candidate evidence. The first `...-02`
preflight was superseded because its durable detection transcript was added
after the original capacity/backup capture. The authoritative refresh is
`03-preflight-refresh-0001`, whose in-order detection, capacity query, and
complete backup are separately preserved. Its corrected versioned preservation
manifest covers 72 files with zero hash or size mismatches; superseded
pre-correction reports remain preserved beside the corrected reports.

## Exact prepared package

The package was created through the canonical P17-002 preparation/export path,
then imported into an isolated disposable `infocarry-library-v1` catalog as
one item. The destination is distinct from the prior P16 `_01` and `_02`
folders and was absent in the fresh backup:

```text
root\IC_P17_LIBRARY_20260831_03
├── 01-introduction.txt
├── 02-page-01.bmp
└── 03-ending.txt
```

The package contract is
`infocarry-prepared-typed-media-package-v1`. Its signed manifest file is
5,265 bytes with file SHA-256
`ab344dc414d2e84c6e4ff52544bffe859d519a53987bce7083b87c9d1b512cfc`; its
canonical manifest binding is
`caa60795f9f5bc136f0faf8965addf28c48401641cdb2ea73aa705e5e361ba75`.
The isolated Library item ID is
`f767f6ba-7ea2-5bd9-8e0d-9bf8443946ae`; the catalog file SHA-256 is
`1c56c1ab76656d0f65bb1c5e8270303edcc2297df47d312a7b165d0aa03e7742`, and its
canonical catalog binding is
`58cad0352fceff98433f5d688525454fa719b89c23c5fc517e869210f2d0bea1`.

| Order | Child | Source SHA-256 | Prepared payload bytes | Prepared payload SHA-256 |
| ---: | --- | --- | ---: | --- |
| 0 | `01-introduction.txt` | `4fda9e7576748e5c58d68d4b0ccad84fcecffc7e29ff9c2bed6bc97a50c0af30` | 3,294 | `38391cc8f2ea488c09990562539c206df14cfef5bad6148ab7e73b2af49ad9ad` |
| 1 | `02-page-01.bmp` | `f795a8e1466c3988b804f344645a6208bdcfa27e9d51d8b314c99d9a5973aadd` | 10,302 | `f795a8e1466c3988b804f344645a6208bdcfa27e9d51d8b314c99d9a5973aadd` |
| 2 | `03-ending.txt` | `779a3850b1fb782ee7dc6cd943b34f43e4d762879d5301adc731a0c6b3ad95f8` | 2,036 | `1dcafec84c06a52c24d898f389bb94fefea1c0569457ae92476c86a906fb5151` |

The TXT sources were short UTF-8 excerpts copied read-only from the owner-
designated `/Users/stardust/Documents/InfoCarry` source pool and prepared as
strict CP932/CRLF payloads without replacements. The BMP is the repository-
generated validated 237 x 320, 1-bit, uncompressed profile. The original
source-pool file hash and extraction rule are preserved in the external
source-provenance record; no source-pool file was modified.

## Authorized read-only preflight

The authoritative refresh recorded the durable detection transcript
(`821e00f11c11e73eb191fc0fd009c3dfa74e37cde0023e96459e9c7c3232b901`) first;
its manifest records Sony `054c:001e` on bus 2/address 3. The subsequent fresh
native `0x0019` hardware response was 64 bytes with SHA-256
`c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662`; parsed
field `+0x08` reports a capacity limit of **3,145,728 bytes**.

The refreshed backup was captured after the ordered detection/capacity events
into a new non-overwriting subdirectory and independently verified as a
complete eight-object archive:

| Binding | Value |
| --- | --- |
| Backup updated | `2026-08-31T14:20:19.526848+00:00` |
| Backup manifest SHA-256 | `4ff385e4a7b97699c3556ce4318b2b029b74fef4f3f008a5ef5487a6ec4cdc69` |
| Dynamic blob SHA-256 | `e3ac59cb5586a5dc35ea04f6bf24f5cc6509931761ece01bc2605a717335e741` |
| Dynamic blob/model bytes | 2,075,256 |
| Objects | 8 |
| Fixed state | `0x001b` parsed active display history; `0x001c`–`0x001f` supported all-zero state |
| Target conflict | none; `_03` absent |

All object lengths and hashes are retained in the external backup manifest and
the P17 preservation manifest. The fresh backup, not the older P16 post-state,
was the candidate baseline.

## Candidate and seal

The exact reviewed P16-001 native template was reloaded from the preserved
post-operation evidence and matched SHA-256
`6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b`.
Because the fresh baseline already contains later verified records from prior
additive operations, the bridge uses an explicit opt-in template-subset
validation. It verifies the reviewed template paths and stable record/type/
name/prefix/payload facts against the fresh baseline, permits only the known
direct-child `0xe0` to `0x20` read-state difference plus expected geometry and
timestamp rebasing, and leaves every extra fresh-baseline path to the existing
candidate preservation verifier. Ordinary generic candidate callers retain
the strict full-shape comparison.

The reconstructed candidate and future transaction are:

| Binding | Value |
| --- | --- |
| Baseline model | 2,075,256 bytes; 394 records |
| Candidate model | 2,091,292 bytes; 399 records |
| Candidate growth | 16,036 bytes |
| Capacity margin | 1,054,436 bytes |
| Candidate blob SHA-256 | `a5e9ca7f429a6f75583c1c5701bb669ed2b7f79e068dda69c63bb06300174761` |
| `0x101b` transaction SHA-256 | `1d1adc02cee8b856e2e8281ff623e84e681ec893793bebacb247a82c788749d5` |
| New-record timestamp | `0x6a958595` (one explicit frozen value) |
| Preflight seal SHA-256 | `4c41ef4431e0b141950d059a04c3ba5ea3c4a71956505af58bdaa48a37148728` |
| Send count | 0 |

The candidate preserves existing timestamps, flags, payloads, prefixes, names,
unknown record bytes, and fixed-state semantics. Its exact expected additive
delta is the four paths shown above, with ordered kinds `directory`, `txt`,
`bmp`, `txt`. The active fresh display-history block contains six valid
references to existing files from the prior `_01` and `_02` packages. The
existing evidence-backed semantic rebase shifts only references at or after
the exact insertion point by metadata delta `0x140`; count, headers, unused
tail, order, same-path resolution, and unshifted-byte preservation remain
bound. `0x001c`–`0x001f` remain exact supported zero state.

The sealed report is hash-only with respect to the candidate/payload model;
raw candidate and transaction artifacts are retained only outside Git in the
session root. The corrected report explicitly records
`read_only_hardware_accessed=true`, `hardware_write_performed=false`, and
`usb_transmission_performed=false`; it also binds
`device_changing_operation_performed=false` and `send_count=0`. It does not
conflate a read-only device observation with a write. Its corrected preflight
seal is the digest above. The refreshed sealed-report file SHA-256 is
`5012f98f29bd03ff47e808a7b65388bbe3607cbfcd06b4c5bd5124ffaec56321`.
The external preservation manifest is the corrected authoritative
`preservation-manifest-v4.json` (72 entries, SHA-256
`2c4cb8f0347ec8975a7a4af6ca21301c20c2755d812ba9a3305c9cd5cc2da8d2`);
`preservation-manifest-v1.json`, `preservation-manifest-v2.json`, and
`preservation-manifest-v3.json` are
retained as superseded snapshots.

## Evidence classification

### Verified

- expected Sony identity during read-only detection;
- fresh native `0x0019` response bytes, hash, and parsed capacity field;
- complete eight-object backup identity, lengths, hashes, and dynamic-model
  parse;
- absence of the new `_03` destination in that fresh backup;
- canonical package import, explicit grouping, order, path containment,
  profile, source/prepared sizes, and all child hashes;
- reviewed native template identity;
- candidate, transaction, Library binding, timestamp policy, display-history
  transformation, expected post-state, and sealed-report replay; and
- corrected external preservation manifest with 72 entries and zero
  mismatches.

### Observed

- the refreshed CLI detection reported Sony `054c:001e` on bus 2/address 3,
  preserved by the detection transcript and manifest; and
- the authorized read-only capacity query and complete backup capture finished
  normally.

These observations do not establish physical acceptance of the new package.

### Inferred

- the exact reconstructed candidate fits the parsed native capacity for this
  offline model; and
- the reviewed bridge can present this exact package for a later live task,
  subject to a new fresh preflight and approval boundary.

### Unresolved

- physical compatibility or persistence of this new source content;
- native numeric completion decoding;
- operation-specific capacity-response semantics beyond the parsed field;
- interrupted-write atomicity/recovery; and
- arbitrary package shapes, display-history states, nesting, batching, or
  normal GUI/CLI transfer.

## Final boundary

P17-004 is **READY_FOR_HARDWARE_TEST** at the fresh read-only preflight and
owner-approval boundary. No write approval was requested or consumed. Any
later device-changing task must re-detect the device, capture a new fresh
capacity response and complete backup, revalidate target absence and every
binding, and separately request these exact operation-specific phrases:

```text
APPROVE P17-003 MODERN LIBRARY PACKAGE SMOKE 01
ADD ONE INFOCARRY MULTI-CHILD PACKAGE
```

Those phrases are recorded as future requirements only. They are not an
authorization or approval in P17-004.
