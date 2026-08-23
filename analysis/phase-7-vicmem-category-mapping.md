# Phase 7 — `VICMEM.bin` category-to-state mapping

Date: 2026-08-21

This note records an offline correlation between the four fixed state
responses and the four category slots used by `VICMEM.bin`. The evidence is
from the preserved `VicTwo.dll` only; no device command or file write was
performed for this correlation.

## Static evidence

The helper at `0x10005760` parses four consecutive 64-byte response
structures. It starts at the command-word table `0x10015250` and advances by
two bytes, so the exact command order is:

| response slot | command | state verified elsewhere |
| ---: | ---: | --- |
| 0 | `0x001b` | display history |
| 1 | `0x001c` | mark 1 |
| 2 | `0x001d` | mark 2 |
| 3 | `0x001e` | mark 3 |

The category serializer/consumer at `0x10005940` (and its caller at
`0x10005ac0`) traverses four same-stride host lists and advances through the
mask table at `0x100151e8`. That table contains, in order, `1`, `2`, `4`, and
`8`. The writer at `0x10002180` uses the same four mask values when setting
the low four `VICMEM.bin` section bits, and the append helper at `0x10002360`
maps those logical values back to the same category slots.

The transfer receive/send paths call the response parser and the category
serializer with the same four-list stride. There is no alternate permutation
table or command-dependent remapping in the preserved code. Therefore the
modern index-level mapping is:

| `VICMEM` category index | section mask | fixed response | semantic state |
| ---: | ---: | ---: | --- |
| 0 | `0x01` | `0x001b` | display history |
| 1 | `0x02` | `0x001c` | mark 1 |
| 2 | `0x04` | `0x001d` | mark 2 |
| 3 | `0x08` | `0x001e` | mark 3 |

The state names in the last column are independently verified by the
controlled read-state and mark-state captures documented in
`phase-7-read-state-experiment.md` and `phase-7-mark-state-experiment.md`.
Those captures verify the command meanings and the metadata-relative record
offset convention; the table above correlates those commands to the static
category indices.

## What this does and does not establish

This mapping identifies which category list a modern implementation should
associate with each fixed state response. It does **not** assign meanings to:

- the four-byte auxiliary word emitted before each category's records;
- bytes after a record's first NUL in its 0x104-byte path storage;
- any category-record fields beyond the recovered path storage; or
- tail record dword `0x104`.

Those values remain opaque and must be retained byte-for-byte. A produced
legacy `VICMEM.bin` fixture is still needed before enabling full repacking.
