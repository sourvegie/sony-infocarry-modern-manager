# Phase 7 — Fixture 1/2 comparison

The second extracted fixture is present at:

`${RESEARCH_ROOT}/fixtures-2`

Its latest offline report, including exact sidecar round-trip checks, is
preserved at:

`analysis/fixture-report-2-roundtrip/manifest.json`

The comparison was read-only; neither fixture was modified.

## File-level result

| File | Fixture 1 vs. fixture 2 |
| --- | --- |
| `Backup/VICDATA.bin` | byte-identical; SHA-256 `72142be59413acdbd4c065fad9d16c2e50bc05d77e316844528de802b689b728` |
| `Memo/VICLV.bin` | byte-identical; SHA-256 `86f79cd4d3edf092149203fb9d35dbe212d5651e24c3123f70d931a74d869eb2` |
| `ICM/.../order.vnw` | byte-identical; SHA-256 `5f41477311ce449952d8d0bee1039c4150fddd696b038497d0129d149a533230` |
| `Memo/VICMEM.bin` | different; fixture 1 `c7ab518475322928a1d6fc5817bb2d79f1ed77a285d24343f0c284612ea1dd83`, fixture 2 `ab40eeddf5fa8ba5cd4f9af533ccd35cf820447846a5f17b31c4ade30d955783` |

Both `VICDATA.bin` images decode with the observed `0xaa` XOR key to the same
decoded SHA-256, and both parse to the same 2,035-record tree, 1,856 reachable
records, 1,677 files, 179 directories, and non-overlapping payload intervals.
Because the backup bytes are identical, this second fixture does not yet test
the XOR layer on a different content state.

## `VICMEM.bin` difference

The two images are both 3,436 bytes and have the same version, reserved bytes,
section mask `0x19`, section counts, auxiliary values, decoded paths, and tail
fields. Exactly 722 bytes differ:

| Region | Changed bytes | Verified unchanged |
| --- | ---: | --- |
| category 0 records | 557 | path bytes and terminators; count; auxiliary `00000000` |
| category 3 record | 50 | path bytes and terminator; count; auxiliary `0000696e` |
| tail records | 115 | path bytes and terminators; `field_3`; rendered-line position |

Every changed byte is after its record's first NUL terminator. No header or
count/auxiliary bytes changed. The decoded category, tail, and all 20 sidecar
correlations are identical between reports.

This is strong evidence that the bytes after a VICMEM path terminator are
opaque or volatile record storage, not a stable path or category field. The
modern parser therefore continues to preserve those bytes losslessly while
using only the verified path and tail-field views. It must not normalize or
reconstruct the trailing bytes during any future round trip.

## Consequences

1. The observed XOR layer remains validated for this exact backup image, but a
   fixture with different `VICDATA.bin` bytes is still needed to test whether
   `0xaa` is stable across content states.
2. VICMEM auxiliary words and tail fields remain unresolved semantically; their
   equality here is useful negative evidence, not a new assigned meaning.
3. Repacking must preserve the complete raw VICMEM records, including bytes
   after the first NUL, and remains gated on unresolved ordering and write
   behavior.
