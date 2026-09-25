# P18-039 — Hardware Validation Resume Preflight

Date: 2026-09-26  
Branch: `task/P18-039-generalized-flat-transfer`  
Fixed commit: `76c9641daa70835d4f7f2859bb741c22ac22787f`

## Result

`HARDWARE_VALIDATION_NOT_RUN`

The preflight stopped before claim consumption, sender entry, or any device
mutation. The required state is:

`AWAITING_EXACT_ARTIFACT_OWNER_AUTHORIZATION`

The supplied resume procedure requires fresh explicit owner authorization for
the corrected exact artifact. The procedure itself is not treated as that
authorization. No authorization covering the complete binary hash, this
candidate, and one VNW-V15 write attempt was supplied in this run.

## Read-only gate evidence

- The checkout was clean at the fixed commit above; no unrelated diff was
  present.
- The tested packaged executable is
  `dist/InfoCarry Manager.app/Contents/MacOS/InfoCarryManager` with complete
  SHA-256
  `86d9fa0ed0a2068c895625e5eb31de617facd60c77778df43832a9cd93a61cb1`.
  The bundle build-info SHA-256 is
  `dcff2ab1e8df8549f53a3c96f3308f0966b6a8f3253423524285c3643c61fdb5`.
  The unrelated `/Applications` copy was not used.
- The preserved candidate is
  `IC_P18_039_5LEAF_20260925_01` with ordered leaves:
  `01-alpha.txt`, `02-page-a.bmp`, `03-beta.txt`, `04-page-b.bmp`,
  `05-omega.txt`. The source fixture remained unchanged.
- The local catalog contains no P18-039 entries. The installation-wide lock
  is explicitly cleared, six historical execution claims remain consumed,
  and `sender_in_flight` has no row.
- Read-only USB enumeration returned no devices, and the system USB inventory
  exposed no connected device. The expected Sony VNW-V15 identity
  `0x054c:0x001e` therefore could not be confirmed.

## Boundary

Physical sender attempts: `0`  
`0x101b` operations: `0`  
Device mutation: none  
Further physical write authorization required: `YES`

Resume only after explicit exact-artifact owner authorization is supplied and
the expected VNW-V15 is visibly connected. Then repeat the read-only readiness
gate; do not consume a claim or enter the sender merely because authorization
is later supplied. A subsequent write remains limited to one canonical guarded
attempt.
