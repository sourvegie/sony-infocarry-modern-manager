# Phase 7 — `VICLV.bin` Format

Date: 2026-08-21

## Evidence and scope

This format was recovered offline from preserved `VicTwo.dll`. The original
software package contains no produced `VICLV.bin` sample; the first
user-provided image is documented in `analysis/phase-7-fixture-inventory.md`.
The layout is verified against the legacy loader, creator, appender, and lookup
routines plus synthetic exact-round-trip fixtures. No device command was sent
and no legacy file was modified.

Relevant legacy routines:

- loader/creator: `0x100027f0`;
- append entry: `0x10002a70`;
- lookup by category and path: `0x10002b30`;
- 16-bit parity helper: `0x10005720`.

## Header

The file begins with this exact 16-byte structure:

| Offset | Size | Encoding | Meaning |
| ---: | ---: | --- | --- |
| `0x00` | 10 | bytes | signature `VICVLBIN  ` |
| `0x0a` | 2 | bytes | reserved; legacy creator writes zero |
| `0x0c` | 4 | little-endian unsigned | version 1 |

The loader compares all ten signature bytes and requires version 1. The two
reserved bytes are not checked by the recovered routine, so the lossless parser
preserves them.

## Entry layout

All remaining bytes are consecutive 261-byte (`0x105`) entries:

| Offset | Size | Meaning |
| ---: | ---: | --- |
| `0x00` | 1 | category byte |
| `0x01` | 260 | NUL-terminated path field |

The legacy creator zero-initializes all 261 bytes, writes the category at byte
zero, copies the relative path at byte one, and appends the entry without
sorting or deduplication. A base-directory entry uses an empty path. Nonempty
paths omit the configured base directory and its following separator. They are
Windows paths encoded in the active Japanese ANSI code page, represented as
CP932 by the modern implementation.

The loader obtains the entry count from `(file_size - 16) / 261`, allocates
exactly that many entries, and reads them in order. The modern parser adds two
safety checks not present in the recovered code: it rejects a trailing partial
entry and a path field with no NUL terminator. These are modern validation
policies, not claims about additional legacy checks.

## Category byte

The recovered writer calls the append routine with only category 1 or 2:

- category 2 is emitted when the internal record word at offset `0x14` has odd
  bit parity;
- category 1 is emitted when the internal record word at offset `0x16` has odd
  bit parity.

Both may be emitted for one path. The lookup routine matches the category and
relative path exactly. These internal words have not yet been mapped safely to
specific raw backup-record fields, so the modern module preserves the category
as a neutral byte and does not invent semantic labels. Unknown category values
and nonzero post-NUL padding are retained losslessly when parsing.

This also corrects an earlier working hypothesis: `VICLV.bin` is not a direct
serialization of display history, marks, and bookmarks. Those device responses
affect the manager's in-memory record representation; `VICLV.bin` separately
preserves the two path-associated parity categories used by that representation.

## Modern implementation

`src/infocarry/viclv.py` provides:

- `parse_viclv(data)` for bounded, lossless parsing;
- `build_viclv(entries)` for deterministic version-1 generation;
- `VicLvEntry.from_path_bytes(...)` for exact byte paths;
- `VicLvEntry.from_cp932_path(...)` for generated legacy-compatible paths.

Parsed files serialize back byte-for-byte, including reserved bytes, category
values, path padding, and entry order. Generated paths are limited to 259 bytes
so the 260-byte field always contains its NUL terminator.

Five dedicated fixtures cover canonical generation, CP932 paths, empty base
paths, preservation of unknown bytes, malformed headers, partial entries,
unterminated paths, and exact round trips. The complete project now has 55
passing offline tests.
