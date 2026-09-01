# P17-011 — Corrected-clock fresh Library-package hardware preflight

Date: 2026-09-01
Base: canonical `main` merge commit `457f03dc73024e259fe2e2d412a612257d030779`
Risk: R3 — device-state candidate and future one-shot write boundary
Status: **READY_FOR_HARDWARE_TEST — host-only owner-approval boundary**

## Scope and authorization

P17-011 performed the newly authorized read-only preflight for the one
explicitly imported P17-004 Library item. The exact future destination is
`root\\IC_P17_LIBRARY_20260831_03` with the ordered children
`01-introduction.txt`, `02-page-01.bmp`, and `03-ending.txt`. This record does
not generalize compatibility beyond that package and does not authorize a
write.

No sender was constructed, no approval was consumed, no backend write call was
made, no `0x101b` was transmitted, and no device-changing operation occurred.
The two phrases below are newly generated sealed bindings for a later task;
they were not requested or supplied during P17-011.

## Ordered read-only evidence

The new non-overwriting external evidence root is:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-17-p17-011-library-package-fresh-preflight-20260901-01/`

The authorized physical sequence completed in order:

1. Exactly one Sony `054c:001e` was detected at bus 2/address 3. The
   preserved detection record SHA-256 is
   `464a4abafa73031c8063d22b9fa1dbc66c37d9e583012476b83d8348d08a3b9e`.
2. One native `0x0019` response was captured. It is 64 bytes, has SHA-256
   `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a`, and
   parses to a capacity limit of 3,145,728 bytes.
3. One complete ordered eight-object backup was captured and integrity
   verified. Its manifest SHA-256 is
   `c2a53b4c2e45f4a536229d82b61ef479c769c170df1137cd4ee4765998663293`, its
   dynamic blob is 2,075,256 bytes with SHA-256
   `e3ac59cb5586a5dc35ea04f6bf24f5cc6509931761ece01bc2605a717335e741`, and
   its raw `BackupStateIdentity` SHA-256 is
   `6b330ac1b77960327f3532a0c5723d6b514ec06111344267fd2a2df888160510`.

The raw backup is preserved at
`01-preflight/backup-before-0001/archive`. The target folder is absent from
the verified dynamic state. Earlier adapter-bound copies created during
host-only staging remain preserved as superseded external artifacts; neither
the raw capture nor any prior P17 evidence was overwritten.

## Corrected freshness boundary

The backup manifest was finalized at
`2026-09-01T05:41:51.261937+00:00`. A wall-clock reference was sampled after
finalization at `2026-09-01T05:42:19+00:00`; the verified age at that reference
was 27.738063 seconds. This is the corrected PR #17 rule: freshness is
evaluated against a reference sampled after the complete backup manifest has
been finalized, not against a pre-capture clock.

The adapter's delayed offline copy replay correctly refused a 300-second
freshness check once that copy was older. The already captured hardware
backup was then verified with the recorded post-finalization acquisition
interval and used by the reviewed offline bridge. This does not weaken the
future live boundary: a later live attempt must capture and verify another
fresh complete backup at its own post-finalization reference.

## Raw state and package reconciliation

The fresh backup was compared only after complete integrity verification with
the preserved P17-009 baseline. The comparison reports
`raw_state_equal=true` and six acquisition-provenance differences: archive
directory, manifest SHA-256, created time, updated time, per-object received
times, and verification time. These remain preserved and visible; they are
excluded from raw-state equality by the reviewed P17-008 identity policy.

The preserved P17-004 Library item was revalidated without modification:

- item ID: `f767f6ba-7ea2-5bd9-8e0d-9bf8443946ae`;
- package manifest SHA-256:
  `caa60795f9f5bc136f0faf8965addf28c48401641cdb2ea73aa705e5e361ba75`;
- catalog file SHA-256:
  `1c56c1ab76656d0f65bb1c5e8270303edcc2297df47d312a7b165d0aa03e7742`;
  canonical sealed catalog binding SHA-256:
  `58cad0352fceff98433f5d688525454fa719b89c23c5fc517e869210f2d0bea1`;
- reviewed native template SHA-256:
  `6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b`.

The exact ordered package remains:

| Order | Kind | Path | Payload bytes | Payload SHA-256 |
| ---: | --- | --- | ---: | --- |
| 0 | TXT | `root\\IC_P17_LIBRARY_20260831_03\\01-introduction.txt` | 3,294 | `38391cc8f2ea488c09990562539c206df14cfef5bad6148ab7e73b2af49ad9ad` |
| 1 | BMP | `root\\IC_P17_LIBRARY_20260831_03\\02-page-01.bmp` | 10,302 | `f795a8e1466c3988b804f344645a6208bdcfa27e9d51d8b314c99d9a5973aadd` |
| 2 | TXT | `root\\IC_P17_LIBRARY_20260831_03\\03-ending.txt` | 2,036 | `1dcafec84c06a52c24d898f389bb94fefea1c0569457ae92476c86a906fb5151` |

The candidate reconstructs to 399 records and 2,091,292 bytes. Growth is
16,036 bytes; baseline available growth is 1,070,472 bytes, leaving a
post-candidate capacity margin of 1,054,436 bytes. Candidate SHA-256 is
`a5e9ca7f429a6f75583c1c5701bb669ed2b7f79e068dda69c63bb06300174761` and the
prospective `0x101b` transaction SHA-256 is
`1d1adc02cee8b856e2e8281ff623e84e681ec893793bebacb247a82c788749d5`.

The fixed-state policy is the reviewed semantic display-history rebase plus
supported zero `0x001c`–`0x001f` state. Six active `0x001b` references resolve
to the same preserved paths/records after the exact `0x140` metadata delta;
count, headers, unused tail, order, and unshifted bytes remain protected.
Existing timestamps are preserved and one explicit `0x6a958595` value is used
for new records only. Legacy operation-wide timestamp rewriting is not
reproduced.

## Sealed host-only boundary

The hash-only sealed report is preserved externally at
`02-sealed-preflight-0003/sealed-preflight.json`. Its core seal is
`0a0ce4f38d0e5c417253408b1a438b520481efdd29902228889070ea0e561543` and its
outer preflight seal is
`ab80b18459586edb71af31785151f9d0e178a699bdaba98796c6fad3702f3ad5`.
The external `preservation-manifest-v1.json` covers 65 files and replays with
zero mismatches.

The newly generated later-task phrases are:

- `APPROVE P17-011 MODERN LIBRARY PACKAGE PREFLIGHT 01`
- `CONFIRM P17-011 ONE INFOCARRY MULTI-CHILD PACKAGE`

They are sealed as explicit operation phrases but were not requested,
supplied, or consumed in P17-011. Any later device-changing task must perform
another fresh detection/capacity/complete-backup preflight and obtain new
owner approval; these phrases are not authorization by implication.

## Evidence classification and disposition

- **Verified:** PR #17 merge at `457f03d`; one-device detection; native
  `0x0019` length/hash/capacity; complete eight-object integrity; corrected
  post-finalization freshness acceptance; raw-state equality; target absence;
  package/catalog/source/template hashes; ordered children and payloads;
  fixed/display-history eligibility; candidate, transaction, and seal
  hashes; capacity fit; preservation-manifest replay; and zero sender,
  backend-write, approval-consumption, and `0x101b` activity.
- **Observed:** bus 2/address 3; acquisition times and paths; the successful
  read-only sequence; and the two superseded host-only adapter staging
  refusals. The physical content remains untested by this task.
- **Inferred:** the exact additive post-state and future one-shot result,
  conditional on a later fresh revalidation, renewed approval, explicit
  `0x0000`, and independent post-backup/read-back.
- **Unresolved:** native numeric completion decoding, operation-specific
  capacity semantics beyond the parsed response, physical compatibility of
  this content, and interrupted-write recovery.

P17-011 is **READY_FOR_HARDWARE_TEST** only at the host-only owner-approval
boundary. No sender construction or write is part of this task.
