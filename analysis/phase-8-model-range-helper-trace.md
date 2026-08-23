# Phase 8 — Model-Range Helper Trace

Date: 2026-08-21

This note records the bounded static inspection of helper `VicTwo.dll`
`0x10004420` and the worker's remaining range slots. It does not reconstruct
an upload candidate and does not access USB. The companion call-graph note in
`analysis/phase-8-static-worker-callgraph.md` records the complete ten-argument
dispatcher map and the worker's range-length aggregation.

## Helper `0x10004420`

The entry sequence reads three cdecl arguments: the values at `[esp+0x4]`,
`[esp+0x8]`, and `[esp+0xc]`. After its prologue they are held in `EAX`,
`EBP`, and `ESI`, respectively. The helper then:

1. Rejects null arguments and skips nodes whose flag byte at `arg3+0x04` has
   bit `0x10` set.
2. Reads the node length at `arg3+0x0c`, a nibble from `arg3+0x19`, and the
   node text/data beginning at `arg3+0x51`.
3. Appends the selected bytes into a caller-supplied base/position pair,
   applying the observed 16-byte group calculation and the existing bounded
   copy routine.
4. Calls helper `0x100042f0` to append the node's fixed record contribution,
   aligns the running position to four bytes, and fills alignment bytes with
   `0xff`.
5. Recurses through the linked child pointer at `arg3+0x168`, carrying the
   updated position, and returns the final position.

Its fixed-record subhelper `0x100042f0` is also partially mapped. It fills a
record of `arg2` bytes with `0xff`, writes the flag byte from `arg3+0x50`, and
(when the flag's low bit is clear) writes fields from `arg3+0x44`, `+0x46`,
`+0x48`, and `+0x4c` at output offsets `+0x05`, `+0x06`, `+0x08`, and `+0x0c`.
The dword fields are emitted big-endian. It then sums the big-endian dwords
from output `+0x04` through the record end, subtracts the number of 4-byte
words, negates the result, and stores that big-endian checksum at output
`+0x00`. The fixed record is followed by the node's variable text/data and
four-byte alignment padding in the caller. This is a verified byte rule, but
the source-object construction and complete range-8 concatenation are not.

The fixed-record boundary is now implemented offline as
`serialize_legacy_prefix()` in `src/infocarry/view_wrapper.py`. For a 16-byte
or larger multiple-of-four prefix it reproduces the helper's `0xff` fill,
flag-gated fields, big-endian field copies, and checksum. It is validated by
the existing 16/32-byte view-wrapper fixtures and a new synthetic 16-byte
record test. This does not make the variable model-range record format
recovered: the caller still determines the prefix length and the bytes that
follow it.

The recursive caller's safe structural grammar is therefore:

```text
fixed prefix (length selected from the node)
variable node text/data (length and optional path adjustment from the node)
0xff padding to a four-byte boundary
child recursion, then sibling recursion
```

For a non-empty node, the observed prefix-length input is the byte at
`node+0x19` shifted left four; the empty-node branch uses the verified `0x10`
constant. The copy path uses `node+0x51` and has an additional `node+0x1a`
bit-`0x08` branch that can adjust the copied amount. Those control-flow facts
are now recorded, but the source-node construction, adjusted text length,
and complete range-8 concatenation remain unresolved. No range-8 serializer
is inferred from this grammar alone.

The three-argument shape and recursive child traversal are verified. The
complete meaning of the base/position arguments and the resulting range-8
record grammar are not yet established. The worker call at `0x10005285`
supplies the saved `ESI` value from `0x10005272` plus the same local value
twice; this is a distinct append path and is not a direct pointer to the
range-4 slots. After the append, the worker computes the declared variable
length by summing decoded big-endian words from range 5, any range-7 blocks
(normalized through `0x10001ab0`), and range 8. On the captured ordinary path
range 7 is zero-length, giving the observed `M = len(range 5) + len(range 8)`
invariant.

## Range-4 alias check

Let `L` be the worker's stable local stack base after `0x10004ed0`. The
transaction call passes `L+0x30` as range-4 pointer and `L+0x54` as its length.
Both slots are zero-initialized at `0x10004ed5` and `0x10004ee1`.

The model-builder call passes `&L+0x30` and `&L+0x54` as its output pointer and
`N` destinations, and clears both outputs before walking the tree. No later
direct worker store populates `L+0x30`. This statically explains the ordinary
path's captured `N = 0`; a different worker or model mode could still use the
same slots differently, so the general range-4 format remains unresolved.

## Consequence

The safe boundary is now:

- range 5 has a complete fixed byte transform and an offline serializer;
- range 8 has a verified allocation, padding policy, and recursive append
  helper boundary, but no complete payload grammar; and
- range 4 is cleared and remains empty on the ordinary path, while ranges 6
  and 7 are skipped by the literal-null/zero-length call-site values.

The next falsifying evidence would be either a manager-produced `0x101b`
payload or a complete static signature/alias trace for the remaining helper
calls. No additional serializer is justified yet.
