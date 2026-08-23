# Milestone I.0 — prepared text-package evidence audit

Date: 2026-08-23
Status: **Offline audit complete; capture-7 folder/multi-record evidence gate
satisfied for the exact fixture; live package compatibility remains blocked.**

This audit reads preserved backups, Manager snapshots, sidecar reports, native
transaction analyses, and the canonical offline conversion implementation. It
does not access USB, modify evidence, modify `InfoCarry-Toolkit`, or construct a
device transaction.

The machine-readable inventory is
`analysis/phase-12-milestone-i-prepared-text-package-inventory-2026-08-23.json`.
The reusable deterministic record inventory is implemented by
`src/infocarry/prepared_evidence.py` and tested without a personal absolute
evidence path in `tests/test_prepared_evidence.py`.

## Preserved device-resident structures

The base Manager fixture contains 2,035 metadata records, 1,856 reachable
records, 179 directories, 1,677 files, 1,662 text records with 32-byte native
prefixes, and 14 BMP records. The complete `root\\簡易マニュアル` subtree has
60 records, 12 directory records, 46 TXT files, and 2 BMP files. Its records
retain metadata offsets, stored child order, parent-marker records, timestamps,
content offsets, 4-byte alignment, payload gaps, and payload hashes.

The complete device backups used by the live evidence show the following
book-like roots:

| Backup | `日本語書籍` | `中文書籍` | `Books` | `簡易マニュアル` |
| --- | ---: | ---: | ---: | ---: |
| clean legacy add-04 pre | 3 records / 2 TXT | 130 / 1 TXT + 114 BMP | 112 / 49 TXT + 34 BMP | 62 / 48 TXT + 2 BMP |
| modern add-G pre | 2 records / 1 TXT | 130 / 1 TXT + 114 BMP | 112 / 49 TXT + 34 BMP | 60 / 46 TXT + 2 BMP |

These are existing device structures, not proof that the modern client or
legacy Manager can create an equivalent new package. The live add operations
added exactly one root-level TXT record and did not add a directory record.

Representative verified records include:

- `root\\日本語書籍\\kagakushato_atama`, a TXT record with `field_14=0x200`,
  a 32-byte native prefix, and an 8,850-byte payload.
- `root\\中文書籍\\在群中_Im Schwarm_InfoCarry\\page_0001.bmp`, an observed
  1-bit BMP page in a nested tree. BMP dimensions vary across preserved
  records; the common 240×320 shape is observed but not a creation rule.
- `root\\簡易マニュアル\\各部の名前とはたらき`, a 3,135-byte TXT record
  with a 32-byte prefix and payload hash
  `5a036415ae4c95d225135ea875126ece5e4a6c6900a3ff0dad43f3d7c0ad0dcc`.

The inventory utility records each selected record's offset, path, kind,
extension, all five metadata dwords, timestamp, parent, child and sibling
relationships, parent marker, read/unread state, prefix size/hash, payload
offset/size/hash, alignment padding, and content gap. It is deterministic and
JSON-safe. The compact tests use a derived nested blob, not a personal path or
raw evidence file.

## Device state versus Manager bookkeeping

The decoded `VICDATA.bin`/`0x8004` blob and fixed response objects are
device-resident protocol state. The clean add-04 Manager snapshots show
`VICDATA.bin`, `VICMEM.bin`, `VICLV.bin`, and the nested
`ICM/転送元フォルダ/order.vnw` byte-identical before and after Send Selected:

| Manager file | SHA-256 |
| --- | --- |
| `Backup/VICDATA.bin` | `72142be59413acdbd4c065fad9d16c2e50bc05d77e316844528de802b689b728` |
| `Memo/VICMEM.bin` | `f93fe3039983c83826c0c22c7da0f64b723acef5d61dde54761660892762986d` |
| `Memo/VICLV.bin` | `86f79cd4d3edf092149203fb9d35dbe212d5651e24c3123f70d931a74d869eb2` |
| `ICM/転送元フォルダ/order.vnw` | `824ec471ffee0154f982a94a7ec4dd0aef7b1f1d6208f0febd94e2f66fc46894` |

The fixture sidecars contain Manager-local membership: `order.vnw` lists
`日本語書籍`, `中文書籍`, `Books`, `簡易マニュアル`, and `簡易メモ`; `VICLV`
contains category-2 entries for the empty path and `日本語書籍`; `VICMEM`
contains category sections and paths for manual, book, and BMP material. Only
two manual paths resolve directly against the decoded fixture in the existing
correlation report. These files are source/bookkeeping evidence, not a proven
recipe for a new device package.

The canonical converter is separately bounded: `offline_conversion.py` accepts
one strict UTF-8 source, normalizes CRLF, encodes strict CP932, creates a
deterministic logical page plan, and can export a new non-overwriting offline
conversion directory. It does not emit device transaction bytes, folder model
records, sidecars, or BMP creation claims.

## Native transfer evidence and gate decision

Preserved native evidence contains:

1. A clean legacy add-04 transaction that adds one root-level TXT record.
2. One approved modern add-G transaction that adds one root-level TXT record.
3. A copy-delta transaction that duplicates two existing TXT records into an
   existing manual directory. It does not create a new directory model node.
4. Existing static worker analysis showing recursive folder serialization, but
   unresolved source-node construction and variable path/text grammar.

No preserved isolated before/transaction/after sequence proves creation of a
new directory record plus a new TXT child. The following remain unresolved:

- directory record construction and parent/child/sibling pointer grammar;
- encoded child order for a newly created folder;
- timestamp generation for folder/package records;
- fixed-state preservation or rebasing for a new multi-record package;
- one transaction versus multiple transactions;
- whether `VICMEM.bin`, `VICLV.bin`, or `order.vnw` participates in sending; and
- exact device capacity growth.

Therefore the smallest logical package is selected as one root-level folder
with one TXT child, but its device candidate is blocked. No guessed builder,
USB action, normal GUI/CLI package action, or new capture is authorized by this
audit.

At the time of this audit, the next evidence gate was exactly one disposable
root folder with one short TXT child through one isolated legacy Manager
Send-Selected operation, with complete pre/transaction/post evidence, source
bytes, Manager before/after files, native log, and explicit Manager result.
That gate was subsequently executed and is recorded in the capture-7 evidence
record below.

## Capture-7 update

The previously missing isolated sequence was completed once in capture 7. The
owner-supplied evidence is synthesized in
`analysis/phase-12-milestone-i-folder-package-capture7-20260823.md` and
`analysis/phase-12-milestone-i-folder-package-capture7-20260823.json`.

That sequence proves one new root directory, one reachable TXT child, the
three-record metadata insertion, the observed alignment and pointer changes,
one native `0x101b` transaction, exact range-5/range-8 to post-blob equality,
unchanged shared payloads, and byte-identical observed Manager sidecars. It
does not establish a general timestamp rule, general fixed-state derivation,
capacity semantics, request-4 completion decoding, or live modern package
eligibility. The new evidence permits an offline golden builder only.
