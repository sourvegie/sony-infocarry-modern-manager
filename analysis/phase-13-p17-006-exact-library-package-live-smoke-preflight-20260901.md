# P17-006 — exact Library-package live smoke fresh preflight

Date: 2026-09-01
Baseline: merged canonical `main` at `17f57d1` (PR #12)
Status: **READY_FOR_HARDWARE_TEST — fresh read-only preflight complete; stop at owner-approval boundary**
Risk: **R3 — device/safety critical**

## Scope and boundary

P17-006 performed the authorized read-only preflight for exactly one
explicitly imported P17-002 Library package. It did not request or consume
the later approval phrases, construct a sender, transmit `0x101b`, or perform
any device-changing operation. The operation remains experimental host
readiness for this exact Library package, not a physical compatibility claim.

The authoritative session root is:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-17-p17-006-library-package-live-smoke-20260901-03/`

The first reserved `...-01` root stopped during an offline report-field
mapping error before device access. The second `...-02` root completed a
read-only detection, capacity query, and complete backup, then the adapter
rejected the archive because the supplied host `now` value preceded the
backup manifest's later write timestamp. Those roots remain external and
non-overwritten; neither is used as the authoritative sealed preflight. The
corrected `...-03` session performed one fresh in-order read-only sequence and
is the authoritative evidence for this task.

## Exact Library package

The preserved P17-004 package and catalog were revalidated without changing
their files. The package remains one explicit Library item with this exact
flat order:

```text
root\IC_P17_LIBRARY_20260831_03
├── 01-introduction.txt
├── 02-page-01.bmp
└── 03-ending.txt
```

The contract is `infocarry-prepared-typed-media-package-v1`. The package
manifest binding is `caa60795f9f5bc136f0faf8965addf28c48401641cdb2ea73aa705e5e361ba75`;
the catalog item is
`f767f6ba-7ea2-5bd9-8e0d-9bf8443946ae`. The source and prepared payload
bindings are:

| Order | Child | Source SHA-256 | Prepared bytes | Prepared SHA-256 |
| ---: | --- | --- | ---: | --- |
| 0 | `01-introduction.txt` | `4fda9e7576748e5c58d68d4b0ccad84fcecffc7e29ff9c2bed6bc97a50c0af30` | 3,294 | `38391cc8f2ea488c09990562539c206df14cfef5bad6148ab7e73b2af49ad9ad` |
| 1 | `02-page-01.bmp` | `f795a8e1466c3988b804f344645a6208bdcfa27e9d51d8b314c99d9a5973aadd` | 10,302 | `f795a8e1466c3988b804f344645a6208bdcfa27e9d51d8b314c99d9a5973aadd` |
| 2 | `03-ending.txt` | `779a3850b1fb782ee7dc6cd943b34f43e4d762879d5301adc731a0c6b3ad95f8` | 2,036 | `1dcafec84c06a52c24d898f389bb94fefea1c0569457ae92476c86a906fb5151` |

The exact reviewed native template was loaded from the preserved P16-003B
post-operation evidence and matched SHA-256
`6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b`.

## Fresh read-only preflight

The P17-005 adapter's injected real read-only boundaries were invoked in this
order: expected-device detection, native `0x0019` capacity, complete backup,
Library/package reconstruction, hash-only preview, and seal. Detection
reported one Sony `054c:001e` on bus 2/address 3. The preserved 64-byte
`0x0019` response has SHA-256
`c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662`; parsed
field `+0x08` reports **3,145,728 bytes**.

The fresh backup is a complete eight-object archive. Its manifest SHA-256 is
`f11d7a1f6df9f0aad1310c3d73cf4d09c986504dd5fb0153cca3fdcbf24ad40b`, its
dynamic blob SHA-256 is
`e3ac59cb5586a5dc35ea04f6bf24f5cc6509931761ece01bc2605a717335e741`, and
the parsed baseline model is 2,075,256 bytes. Every listed object was
rehashed and length-checked; the archive and dynamic blob were parsed before
candidate use. The exact target folder was absent from this fresh backup.

## Candidate and sealed operation

The reviewed P17-003/P17-005 construction was rebuilt from the fresh backup
and the exact Library package. The candidate and prospective transaction are:

| Binding | Value |
| --- | --- |
| Candidate model | 2,091,292 bytes, 399 records |
| Candidate growth | 16,036 bytes |
| Parsed capacity margin | 1,054,436 bytes |
| Candidate blob SHA-256 | `0e3af665c6046c91d1096e8570f8b63b1fc82d35788027becf65ff942ca8883f` |
| Candidate timestamp | `0x6a95b144`, one explicit value for new records |
| Prospective `0x101b` transaction SHA-256 | `1abab51a9ddb069154fba4d411ffbe31359125270b1438d78acd47b745a54439` |
| Preflight seal SHA-256 | `03146e3766609fcaa1f1d4858aec7d27c7d46ce0dbfa90dd191775aca1a7f770` |
| Send count | 0 |

The candidate's expected additive paths are exactly the four folder/child
paths above, with ordered kinds `directory`, `txt`, `bmp`, `txt`. Existing
timestamps, flags, payloads, prefixes, names, unknown fields, and supported
fixed/display-history state are preserved according to the established
P17-003 policy. The active `0x001b` block contains six validated references
and is semantically rebased by the exact established `0x140` metadata delta;
the references remain bound to the same preserved paths. `0x001c` through
`0x001f` remain the supported zero state. No generalized state rule is
claimed.

The sealed report is
`02-sealed-preflight/sealed-preflight.json` (file SHA-256
`d393743639c09da4882bbd4ae2fab521f8b8c1d772010760fb415b238d315996`). Raw
candidate and eight transaction ranges are preserved only in the external
session root. The external `preservation-manifest-v1.json` covers 27
produced evidence files and was replayed with zero hash or size mismatches;
its SHA-256 is
`d3b0c1efe4d5b0b6796e79ca098d283234d7ca1975f601e5975ae8c29862eb03`.

No sender was constructed, no approval phrase was requested or consumed, and
no `0x101b` request was issued.

## Evidence classification

### Verified

- exact P17-004 Library catalog/package identity, manifest, flat order,
  profiles, paths, and source/prepared hashes;
- reviewed native template identity;
- Sony `054c:001e` identity during the read-only detection;
- fresh native `0x0019` response bytes, hash, and parsed capacity field;
- complete fresh eight-object backup identity, lengths, hashes, and dynamic
  model parse;
- absence of `IC_P17_LIBRARY_20260831_03` in that fresh pre-state;
- candidate, transaction, fixed/display-state, timestamp, preservation,
  expected-post-state, Library, and no-retry bindings;
- sealed hash-only report and external preservation manifest; and
- zero write/transmission and zero sender calls for this task.

### Observed

- the device was detected on bus 2/address 3;
- the read-only capacity query and complete backup completed normally; and
- the host adapter completed its corrected preflight and seal.

### Inferred

- the exact candidate model fits the parsed total-capacity limit; and
- the reviewed P17-005 adapter can present this exact package to a later
  separately approved execution boundary.

### Unresolved

- physical compatibility or persistence of this new package;
- native numeric completion decoding;
- operation-specific capacity semantics beyond parsed `0x0019` field `+0x08`;
- interrupted-write atomicity/recovery; and
- arbitrary packages, broader state, nesting, batching, synchronization, and
  normal GUI/CLI transfer.

## Validation checkpoint

- Focused P17-005 adapter, P17-003 Library bridge, and independent read-back
  verifier tests: **27 passed**.
- Complete portable offline suite: **591 passed, 3 intentional skips**.
- `git diff --check` and the documentation trailing-whitespace audit passed.
- External P17-006 preservation manifest replay: **27 entries, zero hash or
  size mismatches**.
- Excluded-content/history audit passed: no tracked or reachable-history raw
  evidence/proprietary binary files, evidence directories, or credential
  patterns were found.
- Independent R3 review: **PASS**, recorded in
  `analysis/phase-13-p17-006-r3-review-20260901.md`.

## Final boundary

P17-006 is **READY_FOR_HARDWARE_TEST** at the fresh read-only preflight and
owner-approval boundary. Stop here. A later task must perform immediate fresh
revalidation and obtain both exact operation-specific phrases before any
device-changing action:

```text
APPROVE P17-003 MODERN LIBRARY PACKAGE SMOKE 01
ADD ONE INFOCARRY MULTI-CHILD PACKAGE
```

These phrases are recorded as future requirements only. They were not
requested or consumed in P17-006.
