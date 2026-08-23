# Phase 8 — Offline Payload-Generator Boundary

Date: 2026-08-21

This milestone composes the portions of command `0x101b` that are supported by
recovered byte rules. It is an offline artifact only: it never opens USB,
replays a capture, or sends a command.

## Fixture sufficiency check

The two user-provided fixture trees were compared read-only:

| File | `fixtures` SHA-256 | `fixtures-2` SHA-256 | Result |
| --- | --- | --- | --- |
| `Backup/VICDATA.bin` | `72142be59413acdbd4c065fad9d16c2e50bc05d77e316844528de802b689b728` | same | byte-identical |
| `Memo/VICMEM.bin` | `c7ab518475322928a1d6fc5817bb2d79f1ed77a285d24343f0c284612ea1dd83` | `ab40eeddf5fa8ba5cd4f9af533ccd35cf820447846a5f17b31c4ade30d955783` | differs |
| `Memo/VICLV.bin` | `86f79cd4d3edf092149203fb9d35dbe212d5651e24c3123f70d931a74d869eb2` | same | byte-identical |
| `order.vnw` | `5f41477311ce449952d8d0bee1039c4150fddd696b038497d0129d149a533230` | same | byte-identical |

Both `VICDATA.bin` files decode to the same 2,035-record, 1,856-path backup
with the same verified checksum. The second `VICMEM.bin` is useful for the
already documented mutable memo/view-state analysis, but it does not provide a
new manager content tree for the write builder. A different fixture is not
needed for the guarded composer below. A genuinely different manager-produced
`VICDATA.bin` would still be valuable later for learning source-field and
variable-range generation rules.

## Composer

`src/infocarry/payload_builder.py` provides two offline entry points:

- `build_offline_payload()` serializes the four fixed state records into range
  1, the grouped values into range 2, builds the verified `N/M` staging range 3,
  and serializes the exact fixed range-5 source object. Ranges 4, 6, 7, and 8
  are required as explicit opaque byte strings.
- `build_from_observed_capture()` parses the fixed ranges from a previously
  parsed native SnoopyPro transaction, reverses and reserializes range 5, and
  passes unresolved ranges through opaquely. It raises unless all eight ranges
  reproduce exactly.
- `build_from_decoded_vicdata()` accepts a validated decoded `VICDATA` blob and
  composes range 5 from its first 64 bytes plus range 8 from the exact remaining
  bytes. It still requires an independent fixed-state snapshot and deliberately
  leaves ranges 4, 6, and 7 empty; this is a constrained blob-to-ranges bridge,
  not a general content or sidecar generator.
- `build_from_replacements()` applies the constrained existing-record repacker
  before the decoded-blob split. It supports an offline payload change to an
  existing reachable file while preserving the record tree and unknown fields;
  it does not add/delete records or generate sidecars. Existing-file rename is
  provided separately by the bounded manager-bundle helper.

It also accepts `model_nodes=` for an explicit caller-supplied node forest.
`src/infocarry/model_range.py` applies the recovered fixed-prefix,
child/sibling, and `0xff` alignment grammar to those nodes. This is useful for
offline byte-level experiments, but it does not infer node objects or variable
text/path data from `VICDATA.bin`; the arbitrary-content generator remains
blocked on that source mapping.

The returned `ProspectiveWriteTransaction` still has the existing offline-only
manifest/preservation API. No USB backend or write-capable CLI path imports
this composer.

The first toolkit-authored replacement is preserved as
`analysis/phase-8-candidate-4/`; its gate authorization was checked offline
against `analysis/phase-8-live-after-5/`, with USB transmission disabled.

## Capture-backed result

The composer reproduces every recovered range of all three preserved ordinary
transactions:

| Capture | Record offset | Declared bytes | `N` | `M` | Header |
| --- | ---: | ---: | ---: | ---: | --- |
| baseline | `0x23641f` | `0x206b28` | `0` | `0x1f6b28` | `1b10286b2000` |
| selected, first | `0x237647` | `0x206b28` | `0` | `0x1f6b28` | `1b10286b2000` |
| selected, second | `0x467425` | `0x2077c8` | `0` | `0x1f77c8` | `1b10c8772000` |

This is a strong composition/regression result, but it is not yet a new
content generator: the ordinary range split is known, while the potentially
populated ranges 4, 6, and 7, state synchronization, and arbitrary model-tree
construction still come from explicit evidence rather than a recovered
`VICDATA`/sidecar algorithm.

## Next falsification target

The next useful offline work is to trace the caller assignments that produce
range-5 source fields and range-8 nodes for a genuinely different manager
content tree. Until that evidence exists, the composer must reject or require
explicit bytes for unresolved model ranges and must remain disconnected from
any USB write operation.
