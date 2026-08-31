# P16-003A — verified display-history fresh-state correction

Date: 2026-08-31
Status: **READY_FOR_HARDWARE_TEST — exact offline correction verified**
Risk: **R3 — device/safety critical**

## Boundary and owner confirmation

P16-003A is an offline correction to the constrained P16-002 mixed
TXT/BMP/TXT preparation. It does not authorize device access, a fresh capture,
or a modern `0x101b` transaction. The owner confirms that the P16-001 `_01`
TXT/BMP/TXT files were deliberately opened on the InfoCarry after transfer.
The owner-confirmed interpretation is that the three child flags changed from
`0xe0` (unread) to `0x20` (read), and that command `0x001b` contains the
corresponding display-history references. Phase 7 read-state evidence supports
those semantics. The preserved P16-003 fresh backup is authoritative offline
evidence and was not reverted or normalized.

The implementation is opt-in and limited to this exact verified state shape.
Normal package and fixed-state paths remain all-zero-state only.

## Preserved fresh evidence

Raw evidence remains outside Git and was not modified:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-16-p16-003-modern-mixed-txt-bmp-20260831-02/`

The preserved fresh evidence records:

| Item | Result |
| --- | --- |
| expected device | Sony `054c:001e` |
| target | `IC_P16_MIXED_20260830_02` absent |
| parsed native `0x0019` capacity | 3,145,728 bytes |
| raw capacity SHA-256 | `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662` |
| complete backup model | 2,064,268 bytes; 389 records; 327 reachable paths |
| fresh backup manifest SHA-256 | `dc45ecd912a27d94bc01bea557eebacea85e9af9064e46d42b46374c59c342c4` |
| fresh dynamic blob SHA-256 | `4b2999c1cec9aeaab3973ae99e4203fa0a52af7fa5a3686205c29803886d4b9f` |
| fixed `0x001b` SHA-256 | `9a21d818b11939a1b640c264fe26b69d8ee907104e5c895bfbea9ed40a2dfeac` |
| fixed `0x001c`–`0x001f` | all-zero supported state; SHA-256 `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` each |

The raw `0x001b` response parses as three metadata-relative references
`0x0400`, `0x0440`, and `0x0480`. With metadata start `0x0040`, they resolve
to absolute record offsets `0x0440`, `0x0480`, and `0x04c0`, respectively,
and resolve to the three existing `_01` child records. They are aligned,
unique, and valid. No active Mark or Bookmark state is accepted by this
policy.

The three `0xe0` → `0x20` differences are the only dynamic-blob differences
from the preserved P16-001 post-capture baseline at offsets `0x0440`,
`0x0480`, and `0x04c0`; source payloads, path set, length, and unrelated bytes
remain equal. This remains an evidence observation. The fresh raw block is
preserved as the before-state; the modern candidate applies only the reviewed
semantic reference rebase required by candidate geometry.

## Narrow semantic-preservation policy

The fixed-state assessor accepts the fresh state only through an explicit
`allow_verified_display_history=True` path. It:

1. parses the offset-list format of `0x001b`;
2. requires zero header words, aligned unique active references, a clean
   reserved tail, and resolvable existing file records;
3. binds each before-state relative/absolute offset and resolved path;
4. requires `0x001c`–`0x001f` to remain exactly the supported all-zero state;
5. rejects malformed, dangling, duplicated, unfamiliar, or active
   Mark/Bookmark state; and
6. uses the existing `rebase_fixed_state_responses` helper only for counted
   references at or after the exact insertion point, shifting them by the
   exact aligned metadata delta while preserving all other bytes.

For this policy, `0x001b` is preserved semantically rather than
byte-identically. Count, header words, unused tail, entry order, and every
unshifted reference remain byte-identical. Each shifted reference must resolve
to the same path and the same preserved record, including its record bytes,
native prefix, and payload. No general state generator or broader state rule
was added.

## Exact offline reconciliation

The authoritative P16-003 fresh backup was used as the before-state. The
preserved P16-001 post-operation blob was used as the validated native
TXT/BMP template. The exact P16-002 source fixture and reviewed root insertion
geometry then reconstructed the candidate without hardware access:

| Binding | Result |
| --- | --- |
| candidate root | `root\IC_P16_MIXED_20260830_02` |
| candidate children | `01-introduction.txt`, `02-page-01.bmp`, `03-ending.txt` |
| order/kinds | TXT → BMP → TXT |
| insertion point | relative `0x03c0`; absolute `0x0400` |
| metadata delta | `0x0140` (320 bytes; five records) |
| before relative refs | `0x0400`, `0x0440`, `0x0480` |
| candidate relative refs | `0x0540`, `0x0580`, `0x05c0` |
| before absolute refs | `0x0440`, `0x0480`, `0x04c0` |
| candidate absolute refs | `0x0580`, `0x05c0`, `0x0600` |
| target record offsets | `0x0400`, `0x0480`, `0x04c0`, `0x0500` |
| new-record timestamp policy | one explicit `0x6a942500` value for the five new records |
| candidate model | 2,075,256 bytes; 394 records |
| capacity reference | 3,145,728 bytes; sufficient offline |
| candidate blob SHA-256 | `c3b8569aa2252cb8509ee29dfd5243fa887f5c50fa66e74c717b6c5e2973958a` |
| transaction SHA-256 | `3f6cfeb6b660b6f84ae0beff0b423826bce63db2280e87ee626521eb2cbb7337` |
| before fixed hashes | `9a21d818b11939a1b640c264fe26b69d8ee907104e5c895bfbea9ed40a2dfeac`; then four times `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` |
| candidate `0x001b` hash | `88ce42e5f4072c0db09a3df9d1c78a7f024899f4cc31c896c5467ec6ba7fa38a` |

All three active references rebase by `0x0140` and resolve to their original
`_01` paths and preserved records. The candidate retains the fresh `0x20`
read flags, payloads, prefixes, timestamps, names, and unknown record fields.
Only the justified `0x001b` reference words differ in fixed state; the
remaining fixed-state objects remain all-zero. The candidate authorization
binds the before and candidate fixed-state hashes, insertion point, absolute
insertion point, metadata delta, old/new reference pairs, resolved paths,
semantic policy, candidate, transaction, and expected read-back.

The native P16-001 timestamp `0x6a942449` remains an observed legacy value
and is not substituted into this modern candidate. The reviewed modern policy
uses the explicit `0x6a942500` value recorded by P16-002 for all five newly
created records; the hashes above are generated from that exact value.

The independent read-back verifier requires the candidate blob, the exact
rebased `0x001b` bytes, same-path resolution, all-zero `0x001c`–`0x001f`, the
exact ordered TXT/BMP/TXT payload delta, and unchanged unrelated backup
objects. It rejects the original unrebased `0x001b` state after transmission;
there is no automatic correction or retry.

## Evidence classifications

### Verified

- The external P16-003 preservation manifest and fresh backup hashes validate.
- The target `_02` is absent from the authoritative fresh backup.
- The three active `0x001b` references are aligned, unique, parseable, and
  resolve to the existing `_01` child files.
- `0x001c`–`0x001f` are the supported all-zero state.
- The exact fresh state reconstructs the reviewed mixed candidate offline.
- The exact semantic rebase yields the expected old/new reference pairs,
  same-path/same-record resolution, and exact candidate fixed-state hashes.
- Candidate authorization and independent read-back bind the semantic policy
  and reject unrebased or otherwise changed fixed state.
- Focused tests cover shifted and unshifted references, binding mutations,
  malformed state, active Mark/Bookmark rejection, template mutations, and
  read-back mismatch; the complete portable suite and audits pass.

### Observed

- The owner deliberately opened the transferred `_01` files.
- The owner-confirmed state meaning is a read-state transition plus display
  history, consistent with Phase 7 evidence.
- The preserved P16-003 preflight obtained the stated capacity and complete
  backup.

### Inferred

- `0x001b` is display history for the three opened child records, based on
  exact resolution and existing Phase 7 characterization.
- The established metadata-offset rebase helper reproduces the exact
  evidence-backed relation needed for this candidate geometry.

### Unresolved

- Native numeric completion decoding remains unresolved.
- Operation-specific native capacity response behavior remains unresolved;
  any future live runner must query and validate fresh `0x0019` evidence.
- This correction does not establish arbitrary display-history, Mark,
  Bookmark, nested-package, or broader transfer behavior.

## Disposition

P16-003A is **READY_FOR_HARDWARE_TEST** for this exact offline correction and
the constrained mixed TXT/BMP/TXT candidate only. The status is a host
readiness boundary, not a device authorization. No device was accessed, no
fresh live preflight was sealed, no owner write phrases were requested, and no
`0x101b` transaction was transmitted. A later operation-specific task must
perform a new fresh preflight and obtain new exact owner approvals before any
device-changing action.
