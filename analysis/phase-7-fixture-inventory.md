# Phase 7 — Manager-produced sidecar fixture inventory

Date: 2026-08-21

This is an offline analysis of the user-provided fixture. It did not open the
device, send a protocol command, or modify any legacy source file. The
original files remain under the user's project tree and are treated as
read-only evidence.

## Preserved files

The fixture root is:

`${RESEARCH_ROOT}/fixtures/`

The meaningful files are:

| Relative path | Bytes | SHA-256 |
| --- | ---: | --- |
| `Backup/VICDATA.bin` | 2,648,900 | `72142be59413acdbd4c065fad9d16c2e50bc05d77e316844528de802b689b728` |
| `Memo/VICMEM.bin` | 3,436 | `c7ab518475322928a1d6fc5817bb2d79f1ed77a285d24343f0c284612ea1dd83` |
| `Memo/VICLV.bin` | 538 | `86f79cd4d3edf092149203fb9d35dbe212d5651e24c3123f70d931a74d869eb2` |
| `ICM/転送元フォルダ/order.vnw` | 62 | `5f41477311ce449952d8d0bee1039c4150fddd696b038497d0129d149a533230` |

The `.DS_Store` files in the copied directories are incidental macOS
metadata and are not part of the manager format.

## `VICDATA.bin` encoding and layout

The saved file does not begin with the normal `infoCarry 2.00` magic. A
single-byte XOR transform with key `0xaa`, applied in memory only, produces a
valid backup image:

- decoded SHA-256: `6785f57fbd8e1cd7618c39eedef3ff3228f3384e4f7e1812e899d04f8ca5f8f2`;
- magic: `infoCarry 2.00\x01\x00`;
- length: `2,648,900` bytes;
- metadata: start `0x40`, length `0x1fcc0` (2,035 64-byte records);
- content: start `0x1fd00`, length `0x266e40`;
- stored checksum: `0x0e826a40`, exactly reproduced by the toolkit checksum;
- record tree: 1,856 reachable records and 179 parent (`..`) records, with no
  orphan or cyclic links.

The XOR layer is **observed** in this one fixture; its producer is not yet
attributed to a specific manager routine. The encoded original must remain the
authoritative file until a second sample or a static write-path trace proves
the transform.

Record counts in the decoded image are:

| Field | Values observed |
| --- | --- |
| flags | `0xd0` directory: 358; `0xe0` unread file: 1,629; `0x20` read file: 48 |
| extensions | `txt`: 1,661; `bmp`: 14; `dem`: 1; `TXT`: 1; directories have an empty extension |
| field `0x14` | `0x00010200`: 1,117 text records; `0x00000200`: 545 text records; `0x00000100`: 15 BMP/demo records; zero: directories |

The `0x00010200` records are a legitimate manager variant. Their low 16 bits
select the same 32-byte text prefix as `0x00000200`; the high bit is preserved
as an opaque state bit. All 1,677 file payload intervals derived from these
prefix lengths are in bounds and non-overlapping. The toolkit parser now
accepts this form without discarding the raw field.

## Sidecar contents

`order.vnw` is a CRLF text file with the `;v1.0` comment preamble and five
recognized CP932 entries, in order:

1. `日本語書籍`
2. `中文書籍`
3. `Books`
4. `簡易マニュアル`
5. `簡易メモ`

`VICLV.bin` is a version-1 image with two entries, both category `2`:

- an empty relative path;
- `日本語書籍`.

`VICMEM.bin` has section mask `0x19` (category 0, category 3, and the tail):

- category 0 count 10, auxiliary bytes `00000000`; it lists two Japanese
  manual text paths, four Chinese-book BMP pages, and four Books pages;
- category 3 count 1, auxiliary bytes `0000696e`; it lists
  `簡易マニュアル\\各部の名前とはたらき.txt`;
- tail count 2, both bookmark dwords zero; it lists the two Japanese manual
  text paths.

The static category map identifies category 0 as display history and category
3 as mark 3. The auxiliary values and zero tail dwords remain opaque; this
fixture records them but does not assign a meaning.

## Cross-file correlation

The two Japanese manual files in `VICMEM.bin` resolve into the decoded backup:

| Sidecar path | Backup record | Flag / extension | Field `0x14` |
| --- | ---: | --- | ---: |
| `簡易マニュアル\\各部の名前とはたらき.txt` | `0x0e40` | `0x20` / `txt` | `0x00000200` |
| `簡易マニュアル\\画面の名前とはたらき.txt` | `0x0e80` | `0x20` / `txt` | `0x00000200` |

The Chinese-book, Books, `日本語書籍`, and `簡易メモ` names in the sidecars
do not occur in this decoded backup tree. Therefore the fixture proves a
partial correlation only; it does not prove that every sidecar entry belongs
to the same backup snapshot or that `order.vnw` is a complete device tree.

## Consequences

1. Keep the XOR-decoded view ephemeral or in a generated analysis directory;
   never overwrite the encoded fixture.
2. Use the observed Japanese-manual matches to test path-to-record mapping.
3. Preserve auxiliary words and bookmark dword `0x104` without assigning a
   meaning. Manager metadata ordering and collision behavior are now resolved
   separately by static loop tracing in `analysis/phase-7-order-control.md`.
4. The offline fixture report/exporter is now implemented at
   `analysis/phase-7-fixture-report.md`; it accepts the encoded file, verifies
   the XOR-derived checksum, and emits a manifest without any device I/O.
   A future fixture is useful only if it contains genuinely different
   `VICDATA.bin` bytes or controlled auxiliary/tail state.
