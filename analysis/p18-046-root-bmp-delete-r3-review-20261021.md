# P18-046 exact disposable root-BMP Delete — independent R3 review

Reviewed commit: `2125278960c3754c7eeef34769b67e979f1f9f60`

## Disposition

Independent exact-head review passed with **P0/P1/P2 = 0/0/0**. The review
covered the candidate and admission gate, frozen owner identity, claim/marker/
global-lock lifecycle, one-sender/no-retry behavior, post-write verification,
Device Library integration, regression coverage, and the applicable VNW-V15
capability boundary.

The reviewer independently inspected the exact commit diff and relevant
source, tests, project instructions, status, capability matrix, and risk
register. No files were changed during review.

## Host validation

- Focused BMP/Delete suites: **60 passed**.
- Full portable suite: **1,222 passed, 5 established skips**.
- The implementation admits only `root\\IC_P18_046_DELETE_A.bmp` with the
  exact 10,302-byte fixture payload and hash, at serialized record offset
  `0x680`, in unread `0xe0` state with selector `0x100` and a 16-byte `ff`
  prefix.
- The Device Library test exercises one fake guarded send, native success,
  complete independent readback and refresh. A separate injected disconnect
  verifies no retry and preservation of claim, sender marker, and global lock.

## Hardware boundary

The independent review does **not** establish physical Delete behavior. The
physical evidence available to this task demonstrates only the placement of
this exact disposable BMP on VNW-V15. The Delete is ready only for a separate
owner-authorized physical validation using a new complete backup, one sender,
no retry, native `0x0000`, and complete independent post-delete readback.
General BMP deletion, other BMP files or record profiles, nested files,
VNW-V10, and interrupted-write recovery remain unsupported.
