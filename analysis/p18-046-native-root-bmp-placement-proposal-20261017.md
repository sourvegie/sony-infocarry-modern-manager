# P18-046 — bounded native root-BMP placement

Date: 2026-10-17 JST. **READY_FOR_HARDWARE_TEST / NOT PHYSICALLY VALIDATED.**

This preparation admits one disposable BMP placement on VNW-V15. It does not
enable a general BMP Add workflow or any BMP Delete operation. No device write,
USB session, production claim, sender marker, or global-lock mutation occurred
in preparing this candidate.

## Exact experiment

- Device model: Sony InfoCarry VNW-V15 only.
- Destination: `root\\IC_P18_046_DELETE_A.bmp`.
- Source: immutable P18-046 disposable fixture, a 237×320, 1-bit,
  bottom-up Windows BMP.
- Length: 10,302 bytes.
- SHA-256: `2701eb9214e2f0afec20b36c93ef739ef3bce35e931fd8c5721e15915447b26d`.
- Read state: candidate admission is limited to the observed unread BMP record
  profile (`flag=0xe0`, selector `0x100`, 16-byte all-`ff` payload prefix)
  and a baseline with a compatible, unambiguous BMP template.
- Owner confirmation at the later live preflight: **“ADD
  IC_P18_046_DELETE_A.bmp ONCE”**. The application must first show the actual
  fresh backup, device, filename, size, and exact one-file expected change.
  This proposal is not operation-specific physical authorization.

The operation is intentionally experimental and exact-fixture-only. At live
preflight it must still reject a changed device/model, existing target,
unsupported/ambiguous template, changed fixture, insufficient fresh capacity,
unsupported protected state, changed candidate or failed structural checks.

## Structural basis

The repository's `new_txt` candidate path already adds a complete native record
as a direct root child through `backup_duplicate.add_file_from_template` and
the common archive serializer. The P16 native mixed capture contains a complete
10,302-byte BMP record inside a root folder. That observed record supplies the
BMP-specific fields without guessing: the candidate clones the 64-byte record,
retains opaque fields outside its rewritten name and payload/pointer fields,
and updates only name, payload size, content pointer and record timestamp
through the established template operation. Its observed
record profile includes `flag=0xe0`, selector `0x100`, and a 16-byte all-`ff`
prefix; the fixture's actual BMP bytes are validated against the existing
monochrome BMP validator.

The existing root insertion logic then appends exactly one direct root child,
rebuilds directory-table sizes and metadata/content pointers, recalculates the
archive checksum, and rebases supported fixed-state references. The new
builder independently checks root parentage/order, unique paths, preserved
record fields/prefixes/payloads/timestamps, protected-state equality, allocation
alignment/non-overlap, capacity, and the existing eight-range transaction.
There is no unresolved BMP-specific field preventing host candidate
construction. What remains unproven is the physical behavior of this exact
root-BMP operation on the VNW-V15.

The earlier 2026-10-17 UTM screenshot attempt failed with ScreenCaptureKit
error `-3811` before exposing any Manager state. It did not stage a file or
observe a transfer. That failed observation is not treated as evidence, and a
legacy staging experiment is not a prerequisite for this structurally bounded
modern candidate.

## Existing protections and execution boundary

The adapter reuses the root-placement facade and canonical guarded transfer
coordinator. It binds the exact candidate, transaction, source fixture,
baseline, capacity response, and device session into an immutable operation
bundle. Existing durable claim-before-marker behavior, installation-wide
indeterminate-write lock, sender-start marker, one sender invocation, no retry
after sender start, explicit native completion check, complete post-write
backup, and independent readback remain required. No alternate sender or
approval framework is added. The normal Device Library UI does not expose this
BMP placement path, and BMP Delete remains unavailable.

## Bounded operator procedure

1. Use the reviewed exact-head build with the VNW-V15 connected and competing
   legacy clients closed. Obtain a fresh complete backup and fresh native
   capacity response through the existing read-only providers. Verify all
   backup artifacts, model, target absence, and global write-lock/marker/claim
   readiness.
2. Prepare the immutable P18-046 fixture and candidate using the reviewed
   facade. Confirm the live template is compatible and unambiguous; confirm
   the target is absent and candidate audit reports exactly one appended root
   BMP. If any check differs, stop without sending.
3. Present one readable confirmation showing VNW-V15, destination, exact
   fixture size, and “adds one disposable BMP file.” Obtain separate explicit
   owner approval for that exact operation. Do not ask for a typed hash or
   second confirmation phrase.
4. Invoke the existing guarded sender once. Require native `0x0000`; never
   retry after sender start. A missing, malformed, nonzero, disconnected, or
   ambiguous result ends write activity and preserves the marker/lock/evidence.
5. After native success, capture a complete independent backup and verify the
   exact root path and 10,302 payload bytes/hash, expected record profile,
   pointers/checksum and root-table change. Verify every unrelated path,
   payload, timestamp, prefix and protected state is preserved. Do not open the
   BMP on the device during this proof. If any difference is unexplained, stop;
   do not restore or attempt deletion.

The initial exact-head review found two host-side gaps: active fixed-state
pointers were not checked for resolution to the same surviving file, and
overlapping baseline/candidate content segments were not rejected. The
corrected builder now resolves each active list/bookmark pointer on both sides
of insertion and checks every reachable file segment for four-byte alignment,
bounds, and non-overlap. Focused regression tests cover both adversarial cases.
The exact-head correction review passed at
`3b525d833ad572ddc3d5dd9cfabb5084bfd2f9ef`, with P0/P1/P2=0/0/0. P18-046 has
not executed the procedure on hardware. A successful result would
demonstrate only this fixture and observed profile. It would not enable general
BMP Add or Delete, other BMP geometries, nested changes, VNW-V10, or recovery.

## Evidence references

- P16 native mixed BMP record: `analysis/phase-16-p16-001-native-mixed-txt-bmp-capture-01-results.md`.
- Root-TXT direct insertion and its guarded lifecycle: `analysis/p18-045-root-txt-delete-validation-20261011.md`.
- P18-039/040 existing BMP candidate/record handling and folder evidence:
  `CAPABILITY_MATRIX.md` rows for those exact shapes and the associated P18
  analysis records.
- Candidate implementation and focused tests: `src/infocarry/new_bmp.py`,
  `src/infocarry/root_txt_placement.py`, `tests/test_new_bmp.py`, and
  `tests/test_root_txt_placement.py`.
- Prior sanitized-port independent review (does not cover this placement
  extension): `analysis/p18-046-sanitized-independent-r3-review-20261017.md`.
- Root-BMP exact-head correction review: `analysis/p18-046-root-bmp-placement-r3-review-20261017.md`.
