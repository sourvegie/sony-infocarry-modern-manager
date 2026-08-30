# P16-003A — verified display-history fresh-state correction

Date: 2026-08-31
Status: **ESCALATION_REQUIRED — exact fresh state conflicts with candidate geometry**
Risk: **R3 — device/safety critical**

## Boundary and owner confirmation

P16-003A is an offline correction to the constrained P16-002 mixed
TXT/BMP/TXT preflight. It does not authorize device access, a fresh capture,
or a modern `0x101b` transaction. The owner confirms that the P16-001 `_01`
TXT/BMP/TXT files were deliberately opened on the InfoCarry after their
transfer. The owner-confirmed interpretation is that the three child flags
changed from `0xe0` (unread) to `0x20` (read), and that command `0x001b` now
contains the corresponding display-history references. Phase 7 read-state
evidence supports these semantics. The P16-003 fresh backup is therefore
authoritative offline evidence and is not reverted or normalized.

The implementation is intentionally opt-in and limited to this verified
state shape. Normal package and fixed-state paths remain zero-state only.

## Preserved fresh evidence

The raw evidence remains outside Git and was not modified:

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
`0x0400`, `0x0440`, and `0x0480`. With metadata start `0x0040`, these resolve
to absolute record offsets `0x0440`, `0x0480`, and `0x04c0`, respectively;
they resolve to the three existing `_01` child records. They are aligned,
unique, and valid in the fresh backup. No active Mark/Bookmark state is
accepted by this policy.

The three `0xe0` → `0x20` differences are the only dynamic-blob differences
from the preserved P16-001 post-capture baseline at offsets `0x0440`,
`0x0480`, and `0x04c0`; source payloads, path set, length, and unrelated bytes
remain equal. This comparison is an evidence observation, not a license to
rewrite the fresh blob.

## Implemented narrow policy

The fixed-state assessor now has an explicit
`allow_verified_display_history=True` path. It:

1. parses the offset-list format of `0x001b`;
2. requires zero header words, aligned unique active references, and resolvable
   existing file records;
3. binds the relative and absolute offsets and resolved paths;
4. requires `0x001c`–`0x001f` to remain exactly the supported zero state; and
5. rejects malformed, dangling, duplicated, shifted, unfamiliar, or active
   Mark/Bookmark state.

The multi-child candidate builder permits a fresh baseline/template difference
only when each changed byte is the proven direct-child flag transition
`0xe0` → `0x20`, with equal payload, prefix, path, and record structure. It
binds the display-history policy, raw-preservation marker, metadata base,
record offsets, and resolved paths through the candidate and authorization
objects. The independent read-back verifier applies the same opt-in policy
and requires the preserved raw `0x001b` references to remain unshifted.

Focused tests cover explicit opt-in, dangling references, Mark-state
rejection, candidate-offset rejection, permitted read-state-only template
differences, candidate authorization binding, and read-back preservation.

## Exact geometry result

The reviewed P16-002 candidate inserts the new five-record package at the
root marker and grows metadata by 320 bytes. The actual fresh display-history
references point to records at absolute offsets `0x0440`, `0x0480`, and
`0x04c0`. Under that additive geometry those existing records move by the
metadata delta. Therefore the raw `0x001b` block cannot both remain byte-exact
and refer to the same unshifted record offsets in the prospective candidate.

The candidate builder fails closed with:

`fresh display-history state is incompatible with candidate geometry: display-history reference shifted in the prospective candidate`

This is an intentional safety result. No raw evidence was changed, no raw
`0x001b` block was rebased, and no candidate seal, authorization, transaction,
hardware access, or modern write was created for this actual fresh state.

## Evidence classifications

### Verified

- The fresh backup and external preservation hashes validate.
- The target `_02` is absent in the preserved fresh backup.
- The three active `0x001b` references parse, resolve to the three existing
  `_01` child records, and are aligned and unique.
- `0x001c`–`0x001f` are the supported all-zero state.
- The only baseline blob differences are the three owner-confirmed read-state
  flags; source payloads and unrelated bytes are unchanged.
- Opt-in parsing, binding, rejection, and read-back behavior pass focused
  offline tests.
- The exact candidate geometry shifts the referenced records, and the builder
  rejects the resulting mismatch.

### Observed

- The owner deliberately opened the transferred `_01` files.
- The owner-confirmed state meaning is read-state transition plus display
  history, consistent with Phase 7 evidence.
- The preserved P16-003 preflight obtained the stated capacity and backup.

### Inferred

- The `0x001b` references are display-history references for the three opened
  child records, based on their exact resolution and existing Phase 7
  characterization.
- A future supported candidate must either retain these references at their
  original offsets or use a separately reviewed geometry/state policy. This
  report does not choose that policy.

### Unresolved

- A safe offset-preserving additive geometry for the exact fresh state.
- Whether a new supported fresh state without active display history is
  available; this task does not request or perform another capture.
- Native numeric completion decoding and operation-specific capacity-response
  semantics remain unrelated unresolved observations from P16-001.

## Disposition

P16-003A is **ESCALATION_REQUIRED**, not `READY_FOR_HARDWARE_TEST`. The
current code safely recognizes the verified mutable state but refuses the
actual candidate because exact raw display-history preservation conflicts with
record movement. The Project Lead must decide on an offset-preserving geometry
or a separately supported state before another host-readiness review. Until
then, do not rebase `0x001b`, normalize the fresh backup, access hardware, or
perform a modern transaction.
