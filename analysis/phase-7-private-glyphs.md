# Phase 7 — InfoCarry Private Text Sequences

Date: 2026-08-21

The stable backup contains 194 occurrences of 41 two-byte sequences that use a
CP932 lead-range byte with a non-CP932 trail byte. The embedded Japanese manual
states semantic roles for 38 types. Native bytes remain unchanged; these labels
are metadata for readable export and do not substitute Unicode characters for
unknown glyph artwork.

## Manual-mapped sequences

| Raw bytes | Manual-stated semantic role |
| --- | --- |
| `81 23` | unread file icon |
| `81 24` | read file icon |
| `81 25` / `81 26` | mark 1 on unread/read file |
| `81 27` / `81 28` | mark 2 on unread/read file |
| `81 29` / `81 2a` | mark 3 on unread/read file |
| `81 2b` / `81 2c` | PC-acquired folder, closed/open |
| `81 2d` / `81 2e` | device-created folder, closed/open |
| `81 33 81 34 81 35` | three-component external-power indicator |
| `81 36 81 37` | battery level 4 indicator |
| `81 38 81 39` | battery level 3 indicator |
| `81 3a 81 3b` | battery level 2 indicator |
| `81 3c 81 3d` | low-battery indicator |
| `82 2c` | vertical line scrolling |
| `82 2f` | horizontal line scrolling |
| `82 32` | vertical page scrolling |
| `82 35` | horizontal page scrolling |
| `82 36` / `82 37` | locked/temporarily-unlocked file icon |
| `82 38` | cancel or return control |
| `82 3d` | delete previous character control |
| `82 3f` | character-unit cursor movement mode |
| `87 26 87 27` | two-component input-mode selector |
| `87 28 87 29` | two-component candidate paging control A |
| `88 28 88 29` | two-component candidate paging control B |

The paired and triple rows are composite icons. The exporter records a role for
each component while retaining its exact byte offset.

## Unresolved graphic components

Only `83 20`, `83 21`, and `84 20` remain without sufficiently precise
individual labels. They occur only in the manual's top-level folder-icon
illustration, adjacent to the already mapped device-created folder glyphs. They
are preserved and catalogued but intentionally remain unnamed until the glyph
artwork or a device-screen correlation is available.

## Verification

The deterministic post-read-state exports agree byte-for-byte and report 38
mapped and three unresolved types:

- `tests/output/phase-7-private-glyph-export-3`
- `tests/output/phase-7-private-glyph-export-4`

Their tree aggregate is
`3e28d64568714fe0e3f91385c5e225df997dea276b519e61466aa0d90fc520bc`.
Fifty-five offline tests pass, including the later `VICLV.bin` format tests.
