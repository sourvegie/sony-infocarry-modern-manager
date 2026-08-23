# Phase 8 — model-object static boundary

Date: 2026-08-21

This note records the additional offline inspection of `VicTwo.dll`. It does
not authorize a device write and does not claim that the legacy model builder
has been ported.

## Source-object initializer

`0x10003330` clears a 0x40-byte source object and applies these literal stores:

| Object offset | Native store | Evidence |
| ---: | --- | --- |
| `0x00` | dword from data `0x100152f8` | zero bytes |
| `0x04` | dword from data `0x100152fc` | `info` bytes |
| `0x08` | word from data `0x10015300` | `y` plus NUL before the next overlapping store |
| `0x09` | dword from data `0x100152f0` | version-literal bytes |
| `0x0d` | word from data `0x100152f4` | trailing version bytes |
| `0x0e` | word `0x0100` | little-endian object bytes |
| `0x10` | word `0x0040` | little-endian object bytes |
| `0x12` | word `0xffff` | unresolved sentinel |
| `0x3c` | dword `0xffffffff` | unresolved sentinel |

The writes overlap by design; the modern helper preserves that order exactly.
The field meanings are intentionally not named.

## Node-object initializer

`0x100033a0` allocates/clears 0x16c bytes, copies the source object to
`node+0x04`, sets `node+0x50` to `0xff`, clears the 0x104-byte path buffer at
`node+0x51`, and writes `0xffffffff` at node offsets `0x154`, `0x158`, and
`0x15c`. Later allocation/link routines populate child and sibling pointers.

These exact bytes are available through `src/infocarry/model_tree.py` for
offline regression checks. The path parser, source-field population, special
mode branches, and recursive model semantics remain outside the helper.

## Ordinary-path conclusion

The preserved native transactions and worker call graph show that the ordinary
write path does not require independently synthesizing this tree: range 5 is
the transformed first 64 bytes of decoded `VICDATA.bin`, range 8 is its exact
remaining body, and ranges 4, 6, and 7 are empty. The named
`build_ordinary_from_decoded_vicdata()` entry point makes this policy explicit.
Alternate modes still require a genuinely different manager fixture before
any model-tree generator is considered safe.
