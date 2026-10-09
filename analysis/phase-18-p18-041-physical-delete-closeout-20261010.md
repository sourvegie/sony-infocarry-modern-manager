# P18-041 physical Delete evidence closeout — 2026-10-10

**COMPLETE for the exact observed operation. PHYSICALLY DEMONSTRATED: one
bounded modern root-level TXT deletion on VNW-V15.** The target was only
`root\IC_P18_041G_CLOCK_01.txt`, the exact 29-byte fixture with SHA-256
`9541c1b9d09ee7d4ab91c704755c4bea8b2022c3bb8f50aa15c1a990bf80c35d`.
The owner-authorized reviewed implementation was commit
`5966933388137138230140deca7b244d5bb74a8b`.

The original reports remain unaltered outside Git in
`/external/local-path`:
`PHYSICAL_EXPERIMENT_REPORT.md`, `INDEPENDENT_POST_DELETE.md`, their two
verification JSON files, independent preflight, owner-release receipt and
launcher output. The directory date is October 9; execution-time before and
post backups completed on **October 10 JST**, at 00:11:27 and 00:12:28.
The [sanitized inventory](phase-18-p18-041-physical-delete-closeout-20261010.json)
hash-binds those reports and all 43 referenced frozen/actual artifacts to their
preserved external roots. No raw backup, private payload, transaction binary
or production safety store is copied into Git.

## Independent host re-verification during P18-042

Read-only offline inspection recomputed every referenced artifact's SHA-256
and byte length, verified both complete eight-object archives, reconstructed
the existing exact candidate from the actual execution-time before archive,
and reran the existing independent Delete readback verifier. Candidate and
all eight preserved transaction ranges match the frozen operation. The actual
before archive's eight raw objects match the approved baseline despite
different capture provenance. The result bundle equals the frozen bundle;
owner-release receipt, audit, claim and marker terminal record bind its seal.

Direct raw comparison confirms exactly one removed path, no additions,
455 → 454 records, all 300 surviving reachable payloads/native prefixes and
454 serialized survivor timestamps preserved. Structure and checksum parse
successfully (before `cf6b02e4`, after `f57a2c50`); all five auxiliary blocks
match the derived protected state. The exact post image equals candidate
SHA-256 `6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`;
transaction SHA-256 is
`e5831e0e363cab494c3f4aa859763808fa5a7676b01c6fd4ddb15edd4d58c452`.

The preserved result audit records native `0x0000`, `readback_verified`, one
sender invocation, one transaction and no retry. The owner report records
launcher exit 0. **No independent USB bus trace exists.** Count/no-retry
evidence is the reviewed one-shot code, durable lifecycle and execution audit.
The terminal-resolution artifact binds the immutable result manifest and
records consumed claim / `verified_terminal_success`; its result manifest
retains the historical in-flight marker snapshot. The original independent
review additionally inspected canonical safety state read-only and recorded
zero active markers and a clear installation-wide lock. This closeout
re-verifies saved terminal evidence; it does not inspect or mutate current
production safety state.

All original evidence hashes remained unchanged through re-verification.
P18-042 closeout USB requests, physical writes, and production
claim/marker/lock mutations: **0**. No visual/device-display observation is
claimed.

## Boundary retained

NOT YET DEMONSTRATED: arbitrary root TXT deletions, BMP deletion, nested
files, directories, recursive/subtree deletion, VNW-V10, physical atomicity
or interrupted-write recovery. This single fixture proves its exact observed
state only and grants no standing authorization for another write. Broader
admission requires its own structural validation and review; any further
physical attempt requires separate operation-specific owner authorization.
