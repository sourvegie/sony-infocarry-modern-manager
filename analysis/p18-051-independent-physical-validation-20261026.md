# P18-051 independent physical-validation review

Date: 2026-10-26 JST. **PASS; P0/P1/P2 = 0/0/0. The exact approved two-write experiment is COMPLETE.**

Placement and deletion each returned native integer `0x0000`, used one audited sender invocation and completed canonical plus independent readback. Actual final native readback restores **all eight objects byte-for-byte** to the original pre-placement baseline. No retry, recovery, extra placement or cleanup write occurred.

This review validates only the specified VNW-V15 experiment. Ordinary nested BMP Delete remains disabled; no class promotion, VNW-V10 behavior, directory/subtree deletion, interrupted-write recovery or physical atomicity is established.

## Reviewed authority and source

- Reviewed executable source: `8a443179298ac13d31b14c0f4d92f53035ba46ff`.
- Hardware execution delivery head: `06e8b050d4f87cba844e23b05f841ef5645f2c2a`; its changes after source review are Markdown only.
- Frozen task envelope: `315d64e4546c07b6449570585ef34295bd8ebeebb5f286b7d639bde04a18e7dd`.
- Reviewed private executor: `0ae2d8ba1fe476f9ad5f2570c96a95672e0b87346f1879cbb10cd07b6357f3ec`.
- Single owner approval: `cec2c34f94a309e4cac0452ca5ae1c1b9effefc83aa73ebb21569e92d4a10339`.

The approval covers exactly one placement followed by deletion of the same fixture, maximum two senders total, each with its own fresh backup/capacity, operation identity, one-shot claim, marker/global-lock checks and independent readback. Both actual frozen operation records bind this same approval and envelope. The executor completed once; the terminal experiment result is `COMPLETE` and no STOP record exists.

## Exact fixture and native identity

`root\IC_P18_040_NESTED_20260930_01\Section-A\IC_P18_051_DELETE_A.bmp`

The fixture is the deterministic 237×320 uncompressed monochrome BMP: **10,302 bytes**, SHA-256 `2701eb9214e2f0afec20b36c93ef739ef3bce35e931fd8c5721e15915447b26d`. It was absent before placement, appeared at record `0x880`, and is absent after deletion. Its existing parent is Section-A at `0x700`; siblings `02-page.bmp` at `0x800` and `03-notes.txt` at `0x840` survive, with the existing parent marker at `0x780`.

Actual placed record matches the frozen 64-byte native record: unread `e0`, extension `bmp`, content-relative pointer `0x2a18`, payload length `10302`, frozen timestamp `1792934825`, opaque `ffffffff`, selector `100`, NUL-terminated native stem, all-FF16 prefix and two allocation-padding bytes. Its raw-record SHA-256 is `842a51346650b173e95404ba674cfd3a633c571d237cab9867c535088fee85bd`.

The actual source template is the frozen reachable record `0x49c0`: raw-record SHA `51acce683e03f00581e236048a9de91e7617d4b4ab65f536bafa1bd6b747b472`, source-payload SHA `a30c4ac820cdd61d1a75825e10f7d7c802d6656b68de7e5617ca0f58bf6bc6ac` and prefix SHA `5ac6a5945f16500911219129984ba8b387a06f24fe383ce4e81a73294065461b`. Source payload and fixture payload are distinct. The complete source offset, native path, raw-record/payload/prefix/copied-field identity was independently reconstructed and compared against both the actual guarded candidate audit and frozen envelope. Full private source identity is retained only in the external JSON/evidence index. Candidate/transaction equality was not substituted for provenance equality.

## Actual operations and evidence

| Operation | Native result | Audited senders | Actual bundle SHA-256 |
| --- | --- | --- | --- |
| 1 — Placement | `0x0000` | 1 | `7e763e8bc2dc0c89041817e0f224f0bed9016933ed6183597dc58b8ce41b1844` |
| 2 — Delete | `0x0000` | 1 | `568d9b8b3fa38b0bc0bd16c73210cd33296039a163e90019d26c15b0f0eaa17e` |

| Operation | Actual before manifest SHA-256 | Actual after manifest SHA-256 |
| --- | --- | --- |
| 1 | `6c13d766a14fdb9bbc90397900440eecd0b69258a70712765d6870e585a206cd` | `af7e96a2a863c7c0c54430b5b8f3a51ab9211a872cdfba845b7df9f4c93d40d3` |
| 2 | `fa94abb06fa1f810f2e5594759d536f1cb0206162913a32aae3358c1a0eb4b0a` | `9db7ac47587e470aeb39c16aa0a7db36b74b31dbb7134d721336eb611f9499fc` |

Separate fresh native transaction-before captures were also reverified against each operation’s sealed baseline. All eight actual placement baseline objects directly match the original frozen baseline; all eight fresh Delete baseline objects directly match the actual verified placement. Actual operation capacities match the frozen 3,145,728-byte native capacity and exact raw response.

| Operation | Actual candidate SHA-256 | Actual transaction SHA-256 |
| --- | --- | --- |
| 1 | `341c98374fffaf6fb6db396dab1273583f611e2f293f849b9e803f8db890f92c` | `97995182012738fe9fd4352bebe935826e0d051f4d36abb8ed137d622e84d09a` |
| 2 | `6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8` | `e5831e0e363cab494c3f4aa859763808fa5a7676b01c6fd4ddb15edd4d58c452` |

Every preserved transaction range matches the corresponding frozen transaction byte-for-byte. The reviewer reconstructed the placement from its actual sealed baseline, actual source artifact, canonical source template, capacity and frozen timestamp; the complete actual audit, candidate and transaction match. The reviewer separately reconstructed the actual Delete candidate, complete audit and transaction from its own fresh baseline. Both authorization identities match their sealed bundles; Delete’s sealed restoration set equals the original eight-object envelope.

## Independent preservation and restoration proof

The independent no-repacker nested verifier accepts actual placement against the original baseline via its inverse. Direct content/padding, raw-record ordering, parent/marker ownership and established pointer/count transformations, sibling relationships, opaque header/trailer fields, checksums and timestamps pass. Independent supported-state derivation restores the original five protected objects from actual placement. The actual Delete independently passes the nested readback verifier against its actual fresh before archive.

The baseline has **454 records**, comprising **300 files** and **154 directory records**, including **79 native parent markers** and **75 ordinary directories**. Placement has 455 records and deletion returns to 454. Dynamic lengths are **2,210,432 → 2,220,816 → 2,210,432 bytes**. All 454 surviving record timestamps, 300 payload/prefix pairs, 79 markers, parent folders, siblings and supported protected associations are preserved under the reviewed model.

The final result is stronger than a host replay: the reviewer opened all eight actual final native objects and directly compared their full bytes with the original pre-placement objects. Every comparison passes, including the five protected responses, complete dynamic blob, `0x0024` auxiliary response and probe. Actual native placement supplied the two payload-dependent response/probe values; physical final restoration does not rely on copied host-simulation values.

| Restored native object | Final/original SHA-256 |
| --- | --- |
| `0x001b:response-001b` | `4ce9a1114cead9382ed4f202c7991cfa6e0d5f4743538970896432a9380696cb` |
| `0x001c:response-001c` | `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` |
| `0x001d:response-001d` | `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` |
| `0x001e:response-001e` | `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` |
| `0x001f:response-001f` | `1ea26ee6b56c771d47ea902c4f7b6af145781d7d22732097d822d20d377035eb` |
| `0x0024:response-0024` | `781bf5be3f07e5299b28139d82e6922f5331d4d6b791d8ce4c9f6ead9150043e` |
| `0x8004:backup-blob` | `6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8` |
| `0x8004:backup-blob-probe` | `c4ec295ac754a9ae63c8f2958169bc66c1e238280d41c1998e4bb3bc9ed63724` |

## Safety and original evidence preservation

Claims progress **26 → 27 → 28**, exactly one distinct consumed claim per operation. Each claim matches its candidate, transaction, authorization and frozen bundle. All 26 historical claim rows remain unchanged. Operation 2’s before-safety snapshot equals Operation 1’s after-safety snapshot. Both sender markers are terminally resolved; a final independent mode=ro SQLite check finds 28 claims, zero sender-in-flight markers and a valid database.

The installation-wide lock bytes remain unchanged at SHA-256 `21136ebb38a3d32a7d97b1ed9dab92850ea6015d8d77c52513ef45f7df3ddd74`, retaining the prior cleared historical incident. No retry, recovery or additional write was attempted.

All **1,550** pre-task private file/symlink anchors rehash or retain their exact link targets. Original P18-034 HEAD, exact dirty status and refs remain unchanged. The review performed no source edit, device command, hardware discovery, executor invocation, safety mutation or additional operation.

## Evidence limits and disposition

Physical conclusions derive from actual complete native archives, captured native completion, reviewed canonical execution/claim/marker audit and independent offline reconstruction/readback. Sender counts are audited observations. **No separate USB bus trace, human visual device inspection or legacy Manager observation is claimed.** The reviewer accessed production safety state only through mode=ro SQLite and lock-byte reads.

Final findings: **P0 = 0; P1 = 0; P2 = 0.** The specified placement-and-deletion experiment is complete, and all eight original objects are restored. This grants no standing write authority, general nested-BMP promotion, recovery authority, push or merge.

Detailed private evidence index and complete source identity:
`/private/tmp/p18-051-independent-physical-validation-20261026.json`.
Index SHA-256: `5ac5c66d2c83701c1c7b35ec60a7197c0ce92a5c0c9a646a41ea92d411d5c6df`.
Raw archives and transaction ranges remain outside Git.
