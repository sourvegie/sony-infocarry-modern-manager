# Phase 7 — Offline fixture report

The toolkit now has a reproducible, read-only report command for preserved
manager output. It does not open USB, send a device request, or write a decoded
copy of `VICDATA.bin`.

## Invocation

The fixture root is the directory containing `Backup/`, `Memo/`, and the
manager-created `ICM/.../order.vnw` file:

```sh
.venv/bin/infocarry fixture-report \
  ${RESEARCH_ROOT}/fixtures \
  ${RESEARCH_ROOT}/analysis/fixture-report-1
```

The destination must be new. The command creates only `manifest.json` there;
it refuses to overwrite an existing report directory. The input files are
hashed and remain untouched.

## What is verified

The command applies the currently observed single-byte XOR key `0xaa` to
`VICDATA.bin` in memory, then validates the `infoCarry 2.00` header, metadata
tree, payload bounds, BMP records, and legacy checksum. The report records both
the encoded and in-memory decoded SHA-256 values, but does not save the decoded
blob. The key remains an observation from one fixture, not a future protocol
guarantee.

It also parses `VICMEM.bin`, `VICLV.bin`, and `order.vnw` with the lossless
offline parsers. Paths are correlated against reachable backup-record paths;
unmatched sidecar paths are retained as unresolved rather than being guessed.
Opaque auxiliary words, tail fields, raw hashes, and section metadata remain in
the report. Each sidecar must serialize back to its exact original bytes;
`round_trip_exact` records that check.

## First fixture result

Running the command against the preserved fixture found:

- 2,648,900 encoded bytes and 2,035 backup records;
- 1,856 reachable records, including 358 directories and 1,677 files;
- no orphan records and no overlapping file payload intervals;
- 16-byte and 32-byte payload prefixes, including the observed `0x00010200`
  high-state variant of the 32-byte selector;
- 13 `VICMEM`, 2 `VICLV`, and 5 `order.vnw` correlation entries.

These results make the current parser/report path repeatable, but they do not
resolve the remaining encoding, sidecar auxiliary/tail, or ordering semantics.
Those still require a second comparable manager fixture before any repacking or
device write work is considered.
