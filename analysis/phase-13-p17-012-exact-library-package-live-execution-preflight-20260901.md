# P17-012 — P17-011 exact Library-package live-execution preflight

Date: 2026-09-01
Base: canonical `main` merge commit `be4703c252f8a3f6bf7d40effdbc0b567fad9ad4`
Risk: R3 — device-state and one-shot write authorization boundary
Status: **READY_FOR_HARDWARE_TEST — host-only owner-approval boundary**

## Scope and authorization

PR #18 was confirmed open, mergeable, and CI-passing at head
`4702377b184e6305c046435233c32ad3a84bbe56`, then merged without rewriting
history at `be4703c252f8a3f6bf7d40effdbc0b567fad9ad4`. Local `main` was
fast-forwarded to `origin/main`, verified clean, and the dedicated
P17-012 branch was created from that merge.

The owner instruction authorizes this task's fresh read-only revalidation only.
It does not supply either operation phrase. No phrase was inferred, requested,
consumed, or used to construct a sender. No sender was constructed, no backend
write call was made, no `0x101b` was transmitted, and no device-changing
operation occurred.

The exact future operation remains one additive package at
`root\\IC_P17_LIBRARY_20260831_03` with ordered children
`01-introduction.txt`, `02-page-01.bmp`, and `03-ending.txt`. No other target,
package, transfer mode, retry, delete, overwrite, restore, or normal GUI/CLI
path is in scope.

## Ordered read-only sequence

The new non-overwriting evidence root is:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-17-p17-012-library-package-live-preflight-20260901-01/`

The first numbered sequence completed detection, capacity, and backup, but its
backup became older than the 300-second freshness limit while host-side
sealing was being prepared. It is preserved unchanged as superseded evidence;
it was not used as the authoritative preflight. A second numbered sequence
was then completed in order:

1. Exactly one Sony `054c:001e` was detected at bus 2/address 3. The
   authoritative `detection-0002/detection.json` SHA-256 is
   `464a4abafa73031c8063d22b9fa1dbc66c37d9e583012476b83d8348d08a3b9e`.
2. One native `0x0019` response was captured under `capacity-0002/raw`.
   It is 64 bytes with SHA-256
   `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662` and
   reports a parsed capacity limit of 3,145,728 bytes.
3. One complete ordered eight-object backup was captured under
   `backup-before-0002/archive` and verified for completeness, lengths,
   hashes, device identity, and dynamic-blob structure. Its manifest
   SHA-256 is `4d3394de6f62c44f1ae6a1e790f099347196c9a3edd17444d9e5c93b06060b8e`;
   the dynamic blob is 2,075,256 bytes with SHA-256
   `e3ac59cb5586a5dc35ea04f6bf24f5cc6509931761ece01bc2605a717335e741`.

The authoritative backup manifest was finalized at
`2026-09-01T06:17:49.571676+00:00` and accepted against a post-finalization
reference sampled at `2026-09-01T06:20:26.746755+00:00` under the corrected
freshness rule. The external audit retains the acquisition interval and the
superseded first sequence; no raw artifact was normalized or overwritten.

## State and package reconciliation

The fresh backup passed complete integrity verification before state identity
comparison. Its canonical raw `BackupStateIdentity` SHA-256 is
`6b330ac1b77960327f3532a0c5723d6b514ec06111344267fd2a2df888160510`, equal
to the sealed baseline. The comparison reports six acquisition-provenance
differences — archive directory, manifest hash, created time, updated time,
per-object received times, and verifier time — and zero raw-state differences.
These provenance fields remain preserved and visible outside Git and are not
part of raw device-state equality.

The preserved P17-004 Library package and catalog were revalidated without
modification:

- item ID: `f767f6ba-7ea2-5bd9-8e0d-9bf8443946ae`;
- package manifest SHA-256:
  `caa60795f9f5bc136f0faf8965addf28c48401641cdb2ea73aa705e5e361ba75`;
- catalog file SHA-256:
  `1c56c1ab76656d0f65bb1c5e8270303edcc2297df47d312a7b165d0aa03e7742`;
- canonical catalog binding SHA-256: `58cad0352fceff98433f5d688525454fa719b89c23c5fc517e869210f2d0bea1`;
- reviewed native template SHA-256:
  `6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b`.

The target path was absent from the verified fresh dynamic state. The
reconstructed candidate uses the established semantic display-history policy:
six active `0x001b` references rebase by the exact `0x140` metadata delta to
the same paths and records; `0x001c`–`0x001f` remain the supported zero state;
existing timestamps are preserved and new records use the reviewed explicit
`0x6a958595` timestamp.

The exact reconstructed candidate remains 2,091,292 bytes, growing by 16,036
bytes from the 2,075,256-byte baseline. Parsed capacity margin after the
candidate is 1,054,436 bytes. The P17-011 candidate and transaction hashes
remain unchanged:

- candidate SHA-256:
  `a5e9ca7f429a6f75583c1c5701bb669ed2b7f79e068dda69c63bb06300174761`;
- prospective `0x101b` transaction SHA-256:
  `1d1adc02cee8b856e2e8281ff623e84e681ec893793bebacb247a82c788749d5`.

The new seals bind the fresh acquisition and the exact operation:

- core preflight seal:
  `7294a989dd551985e6aa16b2a1cd0e7382f323551321e860dbfcf93071348da6`;
- outer live-preflight seal:
  `aeb656176aa9163d904f1f8fcbf9c588ef7a33be35dfcc2e64efa3b8235829a8`.

The candidate bytes and eight transaction ranges remain only in the external
sealed directory. The hash-only sealed report contains no candidate bytes.

## Approval boundary and evidence preservation

The authoritative hash-only sealed report is
`03-sealed-preflight-0001/sealed-preflight.json`. The versioned external
preservation manifest is `preservation-manifest-v1.json`; it covers 54 files
including both numbered read-only sequences, copied input bindings, audit
reports, candidate/transaction artifacts, and the sealed report, and replays
with zero mismatches.

The two newly bound phrases for the later exact operation are:

`APPROVE P17-011 MODERN LIBRARY PACKAGE PREFLIGHT 01`

`CONFIRM P17-011 ONE INFOCARRY MULTI-CHILD PACKAGE`

They are not authorization by implication and were not requested or consumed
in P17-012. A later task must freshly revalidate every binding and obtain both
phrases in a new owner message before constructing a sender.

## Evidence classifications and disposition

- **Verified:** PR #18 merge and clean canonical base; exact device detection;
  native capacity response and parsed limit; complete eight-object backup
  integrity; corrected post-finalization freshness acceptance; raw-state
  equality; target absence; Library/package/catalog/source/template hashes;
  candidate and transaction equality with P17-011; capacity fit; fixed and
  display-history policy; sealed report; external manifest replay; and zero
  sender, backend-write, approval-consumption, and `0x101b` activity.
- **Observed:** bus 2/address 3; capture timestamps and paths; the first
  complete-but-superseded stale sequence; and the successful second
  read-only sequence. Physical compatibility and file-opening behavior are
  not established by this task.
- **Inferred:** the exact additive post-state and future one-shot result,
  conditional on later immediate revalidation, new exact owner approval,
  explicit integer `0x0000`, and independent post-backup/read-back.
- **Unresolved:** native numeric completion decoding, operation-specific
  capacity semantics beyond the parsed response, physical compatibility of
  this Library content, and interrupted-write recovery.

P17-012 is **READY_FOR_HARDWARE_TEST** only at the final owner-approval
boundary. Sender calls are zero, backend write calls are zero,
`write_started=false`, approval consumption is false, completion is absent,
and no `0x101b` or device mutation occurred.
