# P18-039 — Authorized Hardware Validation Attempt

Date: 2026-09-26  
Authorized commit: `76c9641daa70835d4f7f2859bb741c22ac22787f`  
Authorized binary SHA-256:
`86d9fa0ed0a2068c895625e5eb31de617facd60c77778df43832a9cd93a61cb1`  
Candidate: `IC_P18_039_5LEAF_20260925_01`  
Authorized shape: `TXT / BMP / TXT / BMP / TXT`

## Result

`HARDWARE_VALIDATION_NOT_RUN`

The owner supplied explicit authorization for exactly one attempt using the
commit, complete binary hash, candidate, and five-leaf shape above. The run
still stopped at the first physical precondition: the expected Sony VNW-V15
was not detected. No pre-write backup, capacity query, claim consumption,
sender entry, `0x101b`, or device-changing action occurred.

## Fresh device gate

Read-only PyUSB enumeration returned no devices. macOS USB inventory showed
connected hubs and unrelated peripherals, but no Sony device and no
`0x054c:0x001e` identity. The expected VNW-V15 session therefore could not
be established.

## Boundary and disposition

Physical sender attempts: `0`  
Device mutation: none  
Claim consumption: none for this attempt  
Installation-wide lock: unchanged; previously cleared  
Further physical write authorization required: `YES`

Do not continue this attempt opportunistically when a device appears. Re-run
the complete read-only readiness gate and preserve the one-attempt limit under
the existing authorization; any later physical write still requires new
explicit owner authorization.
