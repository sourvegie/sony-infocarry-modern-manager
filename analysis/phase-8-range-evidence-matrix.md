# Phase 8 — Range 4–8 Evidence Matrix

Date: 2026-08-21

This is an offline inventory of the eight ordered ranges sent by the legacy
`0x101b` worker. It separates verified sizes and byte rules from unresolved
payload semantics. It does not generate a write candidate, open USB, or claim
that any inferred range would be accepted by the device.

## Transaction-level facts

| Item | Status | Evidence |
| --- | --- | --- |
| Control OUT command | verified | `VicTwo.dll` `0x10004d77`–`0x10004e57` sends command `0x101b` with declared length `0x10000 + N + M` |
| Range order | verified | Same worker visits eight ordered range cases before completion request 4; the common guard sends only non-null, nonzero pairs |
| Range 1–3 total | verified | `0x100 + 0x40 + 0xfec0 = 0x10000` |
| Range 4 length | verified | `N`, the generated-region length used in the command header and staging prefix |
| Ranges 5–8 total | verified on the captured ordinary path | Native parser reconstructs ranges 5, 6, 7, and 8; their sum equals captured `M`. This does not yet reproduce model generation for new content |
| Decoded-blob split | verified on all preserved ordinary captures | `range 5 == decoded VICDATA[0:0x40]` and `range 8 == decoded VICDATA[0x40:]`; the concatenation is byte-identical |
| Completion | verified | One control IN request 4 follows the eight ranges; success requires result `0x0000` |
| Manager write capture | observed and parsed | Two preserved native SnoopyPro traces contain three complete ordinary-send `0x101b` transactions; exact range lengths and hashes are recorded in `analysis/phase-8-usblog-capture-analysis.md` |

## Per-range matrix

| Range | Length rule | Source/evidence | Known byte rule | Unresolved | Smallest useful falsification test |
| ---: | --- | --- | --- | --- | --- |
| 1 | `0x100` | Worker serializer `0x10004660`; `src/infocarry/write_state.py`; capture range hashes | Four 64-byte state records; verified big-endian dword/word fields; zero-filled remainder | Exact manager stale-tail behavior and semantic names | Compare the captured bytes with independently generated state fixtures |
| 2 | `0x40` | Worker serializer `0x10004760`; `src/infocarry/write_state.py`; capture range hashes | Ten big-endian dwords from two groups; zero-filled final 24 bytes | Exact manager stale-tail behavior and semantic names | Compare the captured bytes with independently generated state fixtures |
| 3 | `0xfec0` | Staging allocation at `0x10004cf4`; `build_staging_range()`; captured `N/M` and `0xff` bytes | First 8 bytes are big-endian `N` and `M`; remaining bytes are verified `0xff` fill | Whether any alternate caller mutates the fill before transmission | Obtain a different manager path only if a non-`0xff` staging byte appears |
| 4 | `N` | Dispatcher argument 7: worker local pointer `L+0x30`; length argument 8: local `L+0x54`; both outputs are cleared by the worker/model-builder boundary | No payload record observed; `N = 0` in all captures; no later direct worker store populates the pointer | Whether a distinct workflow invokes another builder that fills this slot, plus record/tree serialization | Prove a nonzero assignment in another path before writing code |
| 5 | `0x40` | Worker helper `0x10001550`; destination is passed as range 5; capture range hashes | Zero-filled 64-byte destination; exact raw copies, packed words, and big-endian dword fields; both preserved manager blocks reverse exactly | Header byte meanings and relationship to model nodes; source-generation rules for a new candidate | Compare a different manager fixture or trace the caller's source-object assignments |
| 6 | field at `+0x24` | Dispatcher argument 4 is literal null; length reads descriptor `L+0x50+0x24` | No payload record observed; descriptor length is `0x20` but the null pointer skips this range | Whether another call path supplies a range-6 buffer and what its 0x20 bytes mean | Trace any indirect assignment to the argument-4 slot before adding a serializer |
| 7 | field at `+0x2c` | Dispatcher argument 5 is worker local pointer `L+0x18`; length reads descriptor `L+0x50+0x2c`, which is zero-initialized and not a model-builder output | No payload record observed; ordinary path has a temporary buffer but zero wire length | Whether alternate model paths populate the field, plus node contents and boundaries | Prove a nonzero assignment in another path before writing code |
| 8 | `4 * floor(field(+0x34) / 4) + 4` | Dispatcher argument 6 is local `L+0x20`; captured range hashes; buffer is allocated at `0x1000524c`–`0x1000527d` | Captured payload grows by 3,232 bytes in the selected transaction; prior `0xff` pad/checksum helper evidence remains | Payload meaning, source-node construction, exact append records, and link from new content to `M` | Compare manager range 8 with fully traced helper inputs |

## Verified helper boundary

The following helpers are safe to reuse in further offline work:

- `serialize_offset_list_state()` and `serialize_grouped_values_state()` for
  ranges 1 and 2;
- `build_staging_range()` for range 3;
- `model_node_contribution()` and `range8_payload_length()` for size checks;
- `serialize_range5_model()` for the verified fixed range-5 byte transform;
- `build_offline_payload()`, `build_from_observed_capture()`, and
  `build_from_decoded_vicdata()` for composing verified ranges while requiring
  unresolved model bytes explicitly;
- `ProspectiveWriteTransaction` for checking all eight lengths and the `N`/`M`
  relationships.

The range-5 helper fills only its verified fixed transformation; range 4 and
the generation semantics of ranges 6–8 remain unresolved even though the
ordinary-path capture provides their observed wire boundaries. A future change
must add a focused evidence note and a falsifying test before adding another
serializer. In particular, a plausible size formula is not evidence of a
payload layout, and a structurally valid artifact is not evidence of device
acceptance.

## Targeted range-5 inspection

The range-dispatch code at `VicTwo.dll` `0x10004ddb` loads the range-5 pointer
from its transaction argument at stack offset `+0x1c` and assigns length
`0x40`. This independently verifies the fixed size and the pointer's position
in the eight-range call.

The worker initializes a 0x40-byte source object at stack-local offset
`+0x60` through helper `0x10003330`. That initializer zero-fills the object,
sets its fixed header fields, and leaves the later model-dependent dwords for
the worker. At `0x100052ef` the worker calls `0x10001550` with destination
`&local[0xa0]` and source `&local[0x60]`; after the validation scans, it calls
the same helper again at `0x100053c4` with the same pair.

The transaction preparation at `0x10005484` occurs after six range-argument
pushes. Its `lea [esp+0xb8]` therefore resolves to `&local[0xa0]`. The worker
then pushes that pointer as the third dispatcher argument. After the
dispatcher prologue, `0x10004ddb` reads argument 3 from `[esp+0x1c]`, proving
that range 5 is exactly the helper's destination, not a partially overlapping
stack object.

Helper `0x10001550` is now mapped at byte level. It zero-fills the length
stored in source `+0x10` (the ordinary worker supplies `0x40`), copies source
dwords at `+0x00` and `+0x04`, copies the byte at `+0x08` and bytes
`+0x09`--`+0x0d`, emits the words at `+0x0e` and `+0x10` in big-endian order,
copies `+0x12` raw, byte-swaps each dword from `+0x14` through `+0x38` at the
same output offsets, and copies source `+0x3c` to output `+0x3c`. All 64
wire bytes are therefore represented by this fixed transform. The pure
implementation and fixture-free tests are in `src/infocarry/range5_model.py`
and `tests/test_range5_model.py`.

The new `recover_range5_source()` helper applies the exact reverse map to a
captured 64-byte range and verifies a byte-for-byte forward round trip. It
recovers the baseline source candidate
`696e666f436172727920322e303000014000ffff20000000276b1f00b731d468000000000000000040000000c05a0000005b000024101f00286b1f00ffffffff`
and the selected-send candidate
`696e666f436172727920322e303000014000ffff20000000c7771f00be675141000000000000000040000000005b0000405b0000841c1f00c8771f00ffffffff`.
These are recovered source-object bytes, not semantic field names or a
general model generator.

Classification: **verified** — range 5 is 64 bytes, is sent in position 5,
is the complete output of `0x10001550`, and the fixed transform is exactly
invertible for the observed length; **observed** — the two manager source
candidates recovered from the preserved captures, the caller's model-dependent
source values, and the helper's validation scans; **unresolved** — semantic
names and acceptance rules for the fields, plus the payloads and boundaries of
ranges 4 and 6–8. The serializer and recovery helper remain offline and are
not wired to any USB or write path.

## Remaining model-range pointer trace

Let `L` denote the worker's stable local `esp` after its prologue at
`0x10004ed0`. The transaction call at `0x1000546e` pushes ten arguments. The
dispatcher therefore receives the following range slots:

| Range | Dispatcher argument | Worker-local value | Length source |
| ---: | ---: | --- | --- |
| 4 | 7 | `L+0x30` | argument 8, `L+0x54` |
| 5 | 3 | `L+0xa0` | fixed `0x40` |
| 6 | 4 | literal null | descriptor `L+0x50+0x24` = `L+0x74` |
| 7 | 5 | `L+0x18` | descriptor `L+0x50+0x2c` = `L+0x7c` |
| 8 | 6 | `L+0x20` | descriptor `L+0x50+0x34` = `L+0x84` |

The pointer at `L+0x50` is the descriptor whose `+0x10` source object is
initialized at `L+0x60`. The worker sets `L+0x74` to `0x20`, `L+0x7c` to
zero, and later replaces `L+0x84` with the aggregate computed by the validation
loops at `0x10005320`–`0x100053bd`. The range-8 buffer at `L+0x20` is allocated
from the generated length plus its alignment pad, filled with `0xff` in the
pad region, and passed through helper `0x10004420`; the helper's complete
record format remains unmapped. That helper trace is recorded separately in
`analysis/phase-8-model-range-helper-trace.md` and
`analysis/phase-8-static-worker-callgraph.md`.

This resolves call-site pointers, length sources, and the observed ordinary-path
wire boundaries, but not the remaining payload-generation semantics. No
additional serializer is justified by this evidence.

## Current blocker

The byte-level range-5 transformation and both manager-produced ordinary-path
range-5 source candidates are now preserved and round-trip exactly, but a
complete device-write candidate is still blocked by unresolved model-dependent
source-generation rules and payload semantics for ranges 4 and 6–8. The next
useful comparison is the range-1/range-8 change against the existing offline
helpers; no device-facing path is justified yet.
