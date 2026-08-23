# Phase 8 — Static Worker and Model Call Graph

Date: 2026-08-21

This note records the offline disassembly pass over `VicTwo.dll`'s ordinary
`0x101b` worker and its model-building helpers. It is a static result only:
the DLL was inspected read-only, no code was executed, and no USB or device
write path was opened.

## Ordinary worker

The worker begins at `0x10004ec0` and uses a 0x110-byte local frame. Its
control flow is:

```text
validate input/context
  -> initialize model source object (0x10003330)
  -> build/normalize tree (0x10002d00, 0x10002d80, 0x100034b0)
  -> optional tree pruning (0x10003d30)
  -> assign tree indices / count fixed nodes (0x10003cc0)
  -> build fixed model records (0x10004880)
  -> build recursive variable model region (0x10003f30 -> 0x10004420)
  -> derive range-8 declared length and validate fields
  -> serialize ranges 1, 2, and 5 (0x10004660, 0x10004760, 0x10001550)
  -> dispatch one segmented 0x101b transaction (0x10004c90)
  -> release temporary allocations and return status
```

The worker's model source object is initialized at local `+0x60`; the fixed
range-5 destination is at `+0xa0` and is always 0x40 bytes on this path. The
ordinary path also allocates a 4-record temporary area at local `+0x24`, a
one-record area at `+0x28`, a model-record area at `+0x18`, and the variable
range-8 area at `+0x20`. Those allocations are internal staging buffers, not
evidence that every corresponding wire range is non-empty.

## Range-5 source-object initialization and caller assignments

The worker initializes the 0x40-byte source object at local `+0x60` through
`0x10003330`. That helper zero-fills the object and writes the following
stable bytes before model-dependent fields are overlaid:

```text
source[0x00:0x08] = b"infoCarry"
source[0x08:0x0e] = b" 2.00\0"
source[0x0e:0x10] = 0x0100 (little-endian)
source[0x10:0x12] = 0x0040 (little-endian)
source[0x12:0x14] = 0xffff (little-endian)
source[0x3c:0x40] = 0xffffffff (little-endian)
```

The source object is then accompanied by ordinary worker-local bookkeeping
assignments at `0x100052b5`–`0x1000530a` and `0x100053d1`. The disassembly
proves the following neutral values without assigning semantic names:

```text
A = local[+0x14]                 # recursive-builder position component
B = local[+0x1c]                 # alignment/position component
C = 0x40 * model_record_count   # fixed-record allocation size
M = A + B + C + 0x40            # range-5 (0x40) plus generated region
```

The worker computes the generated-buffer size from `A` and its four-byte
alignment expression, allocates/fills the range-8 buffer, and later sums the
range-5, range-7, and range-8 words into `M`. The recovered source candidates
correlate the stable and aggregate fields as follows:

| Source offset | Observed relation | Evidence status |
| ---: | --- | --- |
| `+0x14` | fixed `0x20` | matches the worker's fixed range-6 length field; pointer is null on this path |
| `+0x18` | `M - 1` | exact in both recovered candidates |
| `+0x28` | fixed `0x40` | exact in both recovered candidates; range-5 length |
| `+0x2c` | advances with `C` | exact candidate difference is `0x40` when one fixed record is added |
| `+0x30` | `+0x2c + 0x40` | exact in both candidates |
| `+0x34` | `A`-like position component | matches the captured ordinary-worker sizing relationship |
| `+0x38` | `M` | exact in both recovered candidates |
| `+0x3c` | `0xffffffff` | initializer default, exact in both candidates |

The remaining source dwords are intentionally not aliased to a descriptor
slot from this stack-only view: one is affected by the final aggregate write,
and its exact local-frame correspondence is not stable enough to name without
a trusted debugger trace. This explains the repeatable candidate relations
while keeping the source-node construction and semantic field meanings
unresolved.

## Transaction argument map

At `0x1000546e` the worker pushes exactly ten cdecl arguments for
`0x10004c90`. After the dispatcher prologue, the meaningful slots are:

| Dispatcher argument | Worker value | Meaning established by dispatcher |
| ---: | --- | --- |
| 1 | worker context | device/model context; capacity is read at `arg1+0x24` |
| 2 | local descriptor/context pointer | descriptor whose `+0x38` contributes `M` |
| 3 | pointer to range-5 destination | required; dispatched directly as the fixed 0x40-byte range-5 source |
| 4 | literal null | range-6 payload pointer; therefore range 6 is skipped on this ordinary path |
| 5 | local `+0x18` allocation | range-7 payload pointer |
| 6 | local `+0x20` allocation | range-8 payload pointer |
| 7 | local `+0x30` slot | range-4 payload pointer |
| 8 | local `+0x54` value | `N`, the generated-region length |
| 9 | temporary staging buffer | 0xfec0-byte range-3 staging region |
| 10 | temporary 0x40-byte state buffer | fixed range-2 source; range 1 is the separate 0x100-byte worker staging |

The dispatcher rejects null required arguments, checks `N + M` against the
device capacity, allocates a `0xfec0` staging region, writes the command
`0x101b`, and iterates the eight ranges. Its range table at `0x10004db4`–
`0x10004e09` confirms the fixed sizes `0x100`, `0x40`, and `0xfec0`, the
variable range-4/5/6/7/8 slots, and the special range-8 formula
`4 * floor(field(+0x34)/4) + 4`.

## Range-slot assignment results

The worker zero-initializes the range-4 pointer/length slots at local `+0x30`
and `+0x54`. The model-builder call passes `&local[+0x30]` as its output
pointer and `&local[+0x54]` as its `N` output. The builder itself clears both
outputs before walking the tree. No later direct worker store populates the
range-4 pointer, so the preserved ordinary transactions' `N = 0` is
consistent with the static path; alternate model modes remain a separate
question.

Range 6 is unconditionally passed as a literal null at the transaction call.
Range 7's buffer is allocated, but its descriptor field at local `+0x7c`
(descriptor `+0x2c`) is zero-initialized and is not passed to the model
builder as an output. Therefore the ordinary path has no range-7 bytes even
though a temporary buffer may exist.

Range 8 is different: the builder returns a running position at local `+0x14`;
the worker rounds it with the intentionally non-standard expression
`4 * floor(position/4) + 4`, allocates/fills the pad with `0xff`, and calls
`0x10004420` to append the recursive tree records.

## Fixed model-record builder `0x10004880`

The builder walks the child/sibling tree (`+0x164` then `+0x168`) and admits
only nodes whose flag byte does not contain bit `0x10`. For each admitted node
it validates the text at `node+0x51`, clamps the recorded length at `node+0x0c`,
and adds:

```text
round_up_4(clamped_text_length + 0x24) + 0x40
```

The total is rounded to a 0x100-byte allocation boundary. A fixed model header
and per-node fields are emitted, and helper `0x10001930` serializes each
64-byte node prefix. The same byte transformation is duplicated by helper
`0x10001ab0`, which is used by the worker's validation loop; both helpers
zero-fill 64 bytes, preserve bytes 0–3, emit five little-endian source dwords
as big-endian output dwords, and copy the 40-byte name area with the dangling
Shift-JIS lead-byte rule.

This establishes allocation and fixed-record mechanics, but not the semantic
meaning of the model header fields or the source values supplied by the
manager's higher-level tree builder.

## Recursive variable builder `0x10003f30` / `0x10004420`

`0x10003f30` normalizes node metadata, serializes the fixed 64-byte prefix,
then recursively visits the child pointer at `+0x168` and sibling pointer at
`+0x164`. It delegates the variable part to `0x10004420`.

The verified append grammar in `0x10004420` is:

```text
for each admitted node:
    prefix length = (node+0x19) << 4       (empty node uses 0x10)
    optional text/path bytes from node+0x51
    fixed prefix from 0x100042f0
    0xff alignment to a 4-byte boundary
    recurse child, then sibling
```

The node's `+0x1a` low three bits select a special text path (values 0 and 7
take the ordinary branch); bit `0x08` can subtract a fixed suffix length and
append that suffix after the copied text. These branches, the path helper
calls, and the fixed-prefix checksum are fully visible in the disassembly.
The exact source-node construction, text transformation helper semantics, and
the meaning of the variable record fields are still not proven.

### Special-text helper boundary

The special branch is not an inline byte copy that can safely be promoted to a
portable serializer from this call site alone. It calls:

* `0x10008550`, a buffer wrapper that initializes a state object, delegates to
  `0x10008590`, and then finalizes the state. The inner helper uses a bounded
  copy loop and, for one state shape, a further device/stream callback; its
  effective source and destination contracts depend on the surrounding object
  layout.
* `0x100014b0`, which mutates the selected buffer and then delegates to
  `0x10001100`. The latter is a table-driven, stateful XOR/mixing routine over
  variable-length blocks (using the DLL's table at `.data+0x30`), not a fixed
  field endian conversion.
* `0x100084a0`, which normalizes a node/string state flag and may invoke
  lifecycle helpers before the append continues.

These helpers establish that special text/path records can be transformed and
possibly split before the fixed prefix is appended, but they do not establish a
stable public record grammar. Reproducing them would require recovering their
object layouts, state initialization, and all callback contracts; no such
serializer is added to the modern toolkit. The guarded composer therefore
continues to pass captured range-8 bytes through opaquely.

## Range-8 declared-length aggregation

After the recursive append, the worker computes the descriptor length at local
`+0x84` by summing decoded big-endian dwords:

1. eight words from range-5 output offsets `0x20`–`0x3c`;
2. every four-byte word in the temporary range-7 buffer, with each 64-byte
   block normalized through `0x10001ab0` and its contribution adjusted; and
3. every four-byte word in the range-8 buffer.

The helper `0x100014f0` performs the 1-, 2-, or 4-byte big-endian reads used by
these loops. On the captured ordinary path range 7 has length zero, so the
observed invariant reduces to `M = len(range5) + len(range8)`; the aggregate
logic explains why that invariant must not be generalized to alternate modes.

## Static conclusion

The ordinary worker's framing, fixed state ranges, fixed range-5 transform,
range-6 null path, range-7 zero-length path, range-8 allocation/padding, and
declared-length aggregation are now documented. A general arbitrary-content
generator is still blocked by the manager's source-node construction and the
variable text/path record grammar. The guarded composer therefore continues to
require ranges 4, 6, 7, and 8 as explicit evidence and remains disconnected
from USB and device writes.
