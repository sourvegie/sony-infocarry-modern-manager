# P15-002 modern multi-chapter TXT package

This is a host-prepared, text-only package for the isolated P15-002 modern
smoke path. It contains one new root-level folder,
`IC_P15_MULTI_20260828_02`, and four explicitly ordered CP932-compatible TXT
children. The `_01` Capture 01 package is a separate preserved evidence item
and is not a source or target of this package.

## Ordered contents

1. `root\\IC_P15_MULTI_20260828_02\\chapter-01.txt` — 121 bytes — `01 of 04`
2. `root\\IC_P15_MULTI_20260828_02\\chapter-02.txt` — 121 bytes — `02 of 04`
3. `root\\IC_P15_MULTI_20260828_02\\chapter-03.txt` — 121 bytes — `03 of 04`
4. `root\\IC_P15_MULTI_20260828_02\\chapter-04.txt` — 121 bytes — `04 of 04`

All four sources are strict ASCII subsets of CP932 with CRLF line endings,
explicit order markers, and unique end markers. No BMP, nested folder, second
folder, candidate bytes, transaction bytes, or hardware artifact is included.

## Baseline and safety boundary

The latest preserved post-capture state is the external P15-001 Capture 01
post-operation backup. Its dynamic model SHA-256 is
`08d8eead50a177b2dc143e7f1d3274b45fe2a45f81d43c5d21cf98f33e25ac99`, and the
new `_02` destination is absent from that verified state. P15-002 must obtain
and verify a new complete backup immediately before any future execution; the
Capture 01 pre/post backup is not reusable as a live-operation baseline.

## Checksums

See `SHA256SUMS.txt` for the exact manifest and source hashes.
The checked-in `manifest.json` SHA-256 is
`e6143502a393385ecbc9b62bd9a831917f758dfdcd1e83456321a5af3a37a044`.
