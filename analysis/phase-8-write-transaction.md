# Phase 8 — Legacy Write Transaction and Safety Boundary

Date: 2026-08-21

This note records offline static analysis of the VNW-V15 write path in the
preserved legacy software. No USB device was opened, no application command was
sent, and no legacy or fixture file was modified while preparing it. The normal
modern CLI remains read-only. A separately gated sender was added later in
`src/infocarry/write_protocol.py`; it is not imported by the CLI and requires a
backup-bound authorization before request 2.

## Evidence identity

- File: preserved `VicTwo.dll`
- SHA-256: `a02e5927d2e5ded988556e0be0e79a38313ce91f6491ad0ac8835971d3db0dae`
- Image base: `0x10000000`
- Exported ordinary-send entry point: `SendVICData` at `0x10007ec0`
- Ordinary-send worker: `0x10004ec0`
- Segmented device transaction: `0x10004c90`
- Poll-and-bulk-OUT helper without completion query: `0x10003010`
- Generic send helper: `0x10003110`
- Exported unlock entry point: `UnlockVICDevice` at `0x10007fe0`
- Unlock worker: `0x10006e40`

Addresses are PE virtual addresses. Semantic names below are deliberately
neutral unless the legacy export or control flow establishes them.

## Ordinary `SendVICData` flow

The following behavior is **verified by static analysis**.

`SendVICData` validates its context and source arguments, then runs worker
`0x10004ec0` synchronously or on a legacy worker thread depending on whether
callbacks were supplied. The worker performs local parsing, validation,
allocation, checksum preparation, and state serialization before reaching the
only device-changing transaction at `0x10004c90`.

Before that transaction, the worker can perform these read-only/preparation
steps:

1. If the caller context requests the check, receive command `0x0024` as 64
   bytes and require completion `0x0000` (`0x10004c30`).
2. Receive command `0x0025` as 64 bytes and require completion `0x0000`
   (`0x10007150`). The helper returns one conservatively decoded byte from the
   response. A nonzero value enters additional local preparation at
   `0x10007520`; this is not a bulk-OUT transaction.
3. Build the content tree and side-state buffers locally. Cancellation and
   allocation failures can stop the operation before request 2 is issued.

The meanings of command `0x0025` and its returned byte are **unresolved**. A
future implementation must not invent a label or skip the check without
additional evidence.

## Command `0x101b` transaction

At `0x10004d77`–`0x10004e57`, the legacy worker performs one host-to-device
transaction. This order and the sizes below are **verified**:

1. Issue vendor control OUT request 2 with the six-byte little-endian header
   `[command = 0x101b, length = 0x10000 + N + M]`.
2. Send eight ordered byte ranges. Each nonempty range is passed to helper
   `0x10003010`, which polls request 3 before each bulk-OUT chunk and writes at
   most 128 KiB per chunk.
3. After all eight ranges, issue one control IN request 4.
4. Report success only if request 4 succeeds and its result is `0x0000`.

The ranges are:

| Order | Length | Static source | Conservative description |
| ---: | ---: | --- | --- |
| 1 | `0x100` | caller buffer, built at `0x10004660` | Four serialized 64-byte state blocks |
| 2 | `0x40` | caller buffer, built at `0x10004760` | One serialized 64-byte state block containing two groups |
| 3 | `0xfec0` | temporary buffer built at `0x10004cf4` | Fixed staging region, initialized to `0xff`; its first two dwords encode `N` and `M` in byte-swapped order |
| 4 | `N` | dispatcher argument 7, worker local slot `L+0x30`; ordinary model-builder output is cleared | Empty on the preserved ordinary path (`N = 0`); a distinct workflow could still use another builder |
| 5 | `0x40` | helper `0x10001550` destination | Fixed serialized model region |
| 6 | model field at `+0x24` | dispatcher argument 4 is a literal null | Descriptor length is `0x20`; ordinary path skips the range |
| 7 | model field at `+0x2c` | dispatcher argument 5, worker local slot `L+0x18`; descriptor length remains zero | A temporary buffer exists, but the ordinary path sends no range-7 bytes |
| 8 | `4 * floor(field(+0x34) / 4) + 4` | dispatcher argument 6, worker local slot `L+0x20` | Rounded variable model region with observed `0xff` pad; append format unresolved |

The first three ranges total exactly `0x10000` bytes. The transaction declares
the remaining total as `N + M`, where `M` is the model field at `+0x38`.

The preserved native SnoopyPro sessions independently verify this ordinary-path
split: ranges 1–3 total `0x10000`, ranges 4, 6, and 7 carry no payload record,
and ranges 5 and 8 sum to the captured `M`. The exact lengths, hashes, and
selected-send comparison are recorded in
`analysis/phase-8-usblog-capture-analysis.md`; this is a capture invariant,
not yet a generator for new model content. Earlier validation and generation
code constrain some model fields, but their complete semantic names and the
conditions that produce this captured split for new content are not yet safe
production assumptions. The complete static worker/dispatcher map is recorded
in `analysis/phase-8-static-worker-callgraph.md`.

## Offline fixed-range serializers

The first two ranges now have small, USB-independent candidate serializers in
`src/infocarry/write_state.py`. This is a **verified static layout milestone**,
not completion of payload generation.

- Function `0x10004660` receives a zero-filled 0x100-byte destination and a
  source containing exactly four 0x40-byte records. For each record it writes
  the dword at `+0x00`, the words at `+0x04` and `+0x06`, and the declared
  dword entries beginning at `+0x08`, byte-swapped to big-endian. The remaining
  bytes stay zero.
- Function `0x10004760` receives a zero-filled 0x40-byte destination and a
  source containing exactly two records of five dwords. It writes ten
  big-endian dwords at offsets `0x00`–`0x27`; the final 24 bytes stay zero.
- The source records correlate conservatively with the ordered fixed responses
  `0x001b`–`0x001e` and `0x001f`, respectively, based on the surrounding
  category/order flow. Existing parsed response objects can therefore be fed
  to these helpers without importing USB transport code.

The serializers intentionally do not copy parser `unused_tail_hex` bytes.
That choice follows the legacy zero-filling allocator, while live captures show
that parser response buffers can retain stale tail slots. Exact manager output
for every stale-tail state is therefore still unproven; the candidate bytes are
for offline comparison only. The variable generated region and model range 8
remain unresolved, so these helpers cannot yet form a transmissible
`ProspectiveWriteTransaction` by themselves.

The same offline boundary now includes `build_staging_range()`, which produces
the statically verified range 3 from explicit `N` and `M` values. It rejects
values outside unsigned 32-bit bounds and makes no claim about the contents of
range 4 or the unresolved model range 8.

`src/infocarry/payload_builder.py` now composes those fixed serializers into a
validated `ProspectiveWriteTransaction`. Its caller must supply ranges 4, 6, 7,
and 8 as opaque bytes. A parsed native capture can be re-composed exactly as a
regression check, but this convenience path is not a new-content generator and
has no USB integration.

## Verified fixed range-5 transformation

The worker initializes a 0x40-byte source object at local offset `+0x60` with
helper `0x10003330`. Helper `0x10001550` zero-fills the length stored at source
`+0x10` (0x40 on the ordinary path), copies the fixed header bytes and
`+0x09`--`+0x0d`, emits the words at `+0x0e` and `+0x10` in big-endian order,
copies `+0x12`, byte-swaps each dword from `+0x14` through `+0x38` at the same
output offsets, and copies the final source dword at `+0x3c` to destination
`+0x3c`. All 64 output bytes are represented. The worker calls this helper
once before validation scans and once after updating a model-dependent
checksum/aggregate field.

At the transaction call site `0x10005484`, stack accounting resolves the
third dispatcher argument to that same local destination `+0xa0`. The
dispatcher selects it as range 5 at `0x10004ddb` and assigns the fixed length
`0x40`. This establishes the complete byte-level range-5 mapping. The offline
`recover_range5_source()` helper reverses it for preserved 64-byte captures;
both captured transactions round-trip exactly. Semantic names and device
acceptance rules for the fields remain unresolved. The pure serializer and
recovery helper are in `src/infocarry/range5_model.py`; they are deliberately
not connected to `ProspectiveWriteTransaction`, the USB backend, or any
write-capable CLI path.

## Model-builder size formulas

Further static tracing of the worker and its model builder establishes size
formulas, but not payload semantics. The alignment constant at data address
`0x10015230` is the literal `0x100`. In builder function `0x10004880`, each
admitted linked-list node contributes

```text
round_up_4(node_length + 0x24) + 0x40
```

to an allocated model buffer after the initial 0x100-byte base. The worker
separately computes range 8 at `0x10005238` as

```text
4 * floor(field(+0x34) / 4) + 4
```

The latter is deliberately not ordinary 4-byte alignment: an already aligned
field still receives four bytes. These formulas are available as pure helpers
in `src/infocarry/model_layout.py` and are unit-tested. They do not identify
the meaning of the node fields, reproduce the model headers, or prove how the
resulting allocation is split among ranges 5–8; those remain unresolved.

## Verified 64-byte node serializer

Function `0x10001930`, called from the recursive tree builder at `0x10003f30`,
fully establishes one record transformation:

1. Zero a 64-byte destination.
2. Copy source bytes `0x00`–`0x03` unchanged. In observed backup records these
   are the flag byte and three-byte extension storage.
3. Byte-swap the five host-order dwords at source offsets `0x04`, `0x08`,
   `0x0c`, `0x10`, and `0x14` into big-endian destination dwords.
4. Copy the 40-byte source storage area at `0x18` into the destination.

The last step has one verified boundary rule. The legacy code recognizes lead
bytes only in ranges `0x81`–`0x9f` and `0xe0`–`0xef`. If source byte `0x3f` is
such a lead byte while byte `0x3e` is not, it copies only 39 bytes and leaves
destination byte `0x3f` zero. This prevents that specific dangling final
Shift-JIS lead byte. Otherwise it copies all 40 bytes.

`src/infocarry/node_record.py` reproduces this transformation without USB
dependencies. Its output layout matches the existing read-only backup parser,
but this component alone does not reconstruct tree offsets, timestamps,
checksums, or the complete range containing these records.

An offline observed-record comparison used preserved backup blob
`tests/output/phase-6-backup-complete-1/object-08-command-8004.bin` (2,050,100
bytes; SHA-256
`1ff7521cc2b96df8c64f322c41501e45d5efdf21189a9abb39176d99d6cfc14a`).
For each of its 362 parsed metadata records, the five wire dwords were reversed
back to the verified little-endian in-memory representation and passed through
the serializer. All 362 rebuilt records matched their original 64 bytes; there
were zero mismatches. This validates the component against observed device
records, not against a captured manager-produced `0x101b` write payload.

## Structural backup repacker boundary

`src/infocarry/backup_repack.py` now provides an offline structural candidate
repacker for an existing parsed blob. It preserves the full record tree, all
unknown record fields, native payload prefixes, content gaps, and trailer; a
caller may replace payload bytes only for existing file records. The helper
updates affected content offsets and lengths, aligns the content region,
recomputes the verified checksum, and runs the result back through the parser.
Focused tests cover unchanged identity, same- and different-length payloads,
checksum validation, and rejection of unknown or non-file targets.

This is deliberately narrower than a manager-compatible `VICDATA.bin`
repacker: it cannot add/delete records, regenerate tree ordering, or
manager-specific model fields, or prove that a device would accept the result.
An additional read-only check replaced one real captured file payload (record
`0x200`, 3,135 bytes) with a 3,156-byte candidate; the rebuilt blob grew from
2,050,100 to 2,050,124 bytes, preserved all 305 reachable paths, and passed
the complete parser/checksum validation.

## Constrained manager-file round trip

`src/infocarry/vicdata.py` connects the structural repacker to the single-byte
XOR-`0xaa` layer observed in both preserved manager fixtures. The helper first
decodes and parses the backup, permits replacements only for existing file
record offsets, rebuilds and validates the decoded blob, reapplies the XOR
layer, and decodes the result once more for final validation. It performs no
filesystem or USB writes and is not exposed through the command-line client.

An in-memory validation used the preserved manager file
`fixtures/Backup/VICDATA.bin` (2,648,900 encoded bytes; SHA-256
`72142be59413acdbd4c065fad9d16c2e50bc05d77e316844528de802b689b728`).
The decoded backup contained 2,035 metadata records and 1,856 reachable paths.
With no replacements, the re-encoded bytes were exactly identical. A second
run extended reachable file record `0x480` (`root\\system\\demo.dem`) from 556
to 592 payload bytes. The encoded candidate grew to 2,648,936 bytes, retained
all 1,856 paths, reproduced the replacement exactly, and passed the complete
parser and checksum validation.

This result verifies a constrained manager-file transformation, not a device
write format. The XOR key remains an observation rather than a universal rule;
the repacker still cannot add, delete, or reorder records; a bounded existing-file
rename helper now exists but does not regenerate tree ordering. A separate
native manager write capture is now preserved for range-level comparison, but
it does not by itself establish a general `VICDATA`-to-model serializer.

`src/infocarry/vicdata_audit.py` adds a deterministic review boundary around
one such replacement. It returns a JSON-safe report containing source,
candidate, and payload hashes; target record/path details; checksums; preserved
tree invariants; and header, metadata, content, and trailer difference counts.
It deliberately omits the candidate bytes and records that no USB operation or
filesystem output occurred. Against the same real fixture and record `0x480`,
the report found 7 changed header positions, 1,918 changed metadata positions,
and 2,316,433 changed same-position content bytes; the four-byte trailer was
identical. The large positional content difference is expected because a
36-byte early insertion shifts subsequent content, not because millions of
independent semantic fields were rewritten.

## Conservative text-authoring preview

`src/infocarry/text_authoring.py` adds the next offline boundary for a known
existing text record. It normalizes input line endings to CRLF, matching the
observed convention in all 1,661 reachable `txt` records of the preserved
manager fixture, then encodes with strict CP932. Unsupported Unicode raises an
error with the offending code points; no replacement character is emitted.
NUL is rejected. The target's existing native prefix is copied unchanged and,
when it is the observed 32-byte text-view wrapper, its raw fields and checksum
status are included for review without assigning unresolved semantic names.

Capacity is checked only against a caller-supplied byte limit. The project does
not claim to know the device's total capacity from this policy. The preview
passes the encoded payload to the existing in-memory replacement audit and
returns hashes and invariants, not candidate bytes.

Against the preserved manager fixture, the first reachable text record
(`0x6c0`, `root\\デモ用データ\\PDA機能\\飲み会のお知らせ!.txt`) was previewed with
the text `InfoCarry offline preview` plus a Japanese line. Its 564-byte payload
became a 33-byte CP932 candidate; the 32-byte native prefix was preserved, all
records and paths remained intact, and final payload verification passed. No
USB operation, filesystem output, or device-acceptance claim was made.

The ordinary path uses command `0x101b` exactly once. There is no second
host-to-device command after its successful request-4 result.

## Completion versus commit

The following distinction is important:

- **Verified:** request 4 is the last USB operation in an ordinary successful
  `SendVICData` transaction, and the caller requires result `0x0000`.
- **Unresolved:** whether request 4 merely reports a commit already performed
  by the device, triggers finalization when queried, or reports some other
  transaction result. Static host code cannot distinguish these possibilities.
- **Verified absence:** the ordinary send path contains no separately named or
  separately issued commit command.

Therefore the modern design must treat a successful zero completion as the
only known success boundary, while describing the actual device commit point
as **unknown** until a controlled trace and read-back test establish it.

## Cancellation and failure behavior

The following behavior is **verified**:

- The legacy stop operation sets the transfer-context flag at offset `+0x18`.
- Local preparation checks this flag at several boundaries and can stop before
  command `0x101b` begins.
- Helper `0x10003010` checks the flag before each request-3/bulk-OUT iteration.
- There is no distinct USB cancel or abort request.
- If request 2 fails, a state poll or bulk write fails, or cancellation is
  noticed after the transaction begins, `0x10004c90` still makes a best-effort
  request-4 query and returns failure.
- A synchronous Windows call already in progress could not be interrupted by
  the legacy flag.

Static analysis does **not** establish whether the device buffers the entire
declared transaction or mutates storage incrementally. It follows that a cable
disconnect, timeout, or cancellation after request 2 may leave device state
unchanged, partially changed, or internally recoverable. Until this is tested,
the first modern writer must not promise safe mid-transfer cancellation.

## `0x101d` is not a proven general commit

The separate exported `UnlockVICDevice` workflow at `0x10006e40` can call the
ordinary-send worker and then send four zero bytes using command `0x101d` via
the generic send helper at `0x100070c1`. This command requires a successful
request-4 result of `0x0000`.

This is **verified control flow**, but the meaning of `0x101d` is
**unresolved**. It appears only in the unlock workflow and is absent from
ordinary `SendVICData`. It must not be relabeled or reused as a general commit,
unlock, reset, or recovery command without a controlled reference trace.

The unlock workflow also performs additional reads, including commands
`0x0024` and `0x0022`, and host-file work involving `VICDATA.bin`. It is a
separate, device-changing protocol path and remains out of scope for the first
minimal ordinary-write experiment.

## Safe modern implementation boundary

The normal CLI must remain read-only. The offline-only
`ProspectiveWriteTransaction` validates and preserves candidate bytes for
comparison, while the separate `AuthorizedWriteSender` is available only to a
caller that has passed the write gate. Its artifact contains:

- the exact command and declared length;
- all eight ranges as separately hashed byte strings;
- their concatenated SHA-256 and exact total;
- the source fixture and parser/build version;
- validation proving the declared and concatenated lengths agree;
- a declaration that no USB operation was performed.

Before any later hardware write is enabled, all of these gates remain
mandatory:

1. Produce and independently verify a fresh full backup.
2. Require an explicit write-enabling option and interactive confirmation.
3. Start with a disposable minimal record and preserve the before-state hashes.
4. Read back a complete backup immediately afterward and compare every object,
   not just the inserted record.
5. Do not test cancellation until an ordinary minimal round trip succeeds and
   a recovery plan has been agreed with the user.
6. Do not send command `0x101d` or any unlock workflow command in the first
   experiment.

## Remaining blockers

- A complete arbitrary-record, byte-exact `VICDATA` builder has not been
  validated. Only existing-record payload replacement is implemented.
- The fixed-range serializers are shape-verified and unit-tested; range-5
  source values now recover exactly from both preserved manager captures.
  Range-1 caller values and semantic names remain unresolved.
- The variable fields and generator-level checks tying the model ranges to `M`
  need reproducible builder-level proof despite the captured ordinary-path
  length invariant.
- No different-content manager fixture yet demonstrates that the `0xaa` layer
  and all generated fields remain stable across content changes.
- The device's atomicity and recovery behavior after an interrupted `0x101b`
  transaction are unknown.
- The semantics of command `0x0025`, command `0x101d`, and nonzero completion
  values remain unknown.

These blockers prevent a safe device write, but they do not prevent offline
payload generation and comparison work.
