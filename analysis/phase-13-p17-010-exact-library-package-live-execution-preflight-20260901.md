# P17-010 — Exact P17 Library package live-execution preflight

Date: 2026-09-01  
Risk: R3 — device-state candidate and one-shot execution boundary  
Status: **READY_FOR_HARDWARE_TEST** at the final owner-approval boundary  
Canonical merge base: `98ae3e14b36073f5bb41c30c4ae4ee6a85c9b390`  
External evidence root: `/Users/stardust/Projects/InfoCarry-Evidence/phase-17-p17-010-library-package-live-execution-20260901-01/`

## Scope and authorization boundary

PR #16 was verified open, mergeable, and CI-passing, then merged without
rewriting history. Local `main` was synchronized with `origin/main` at the
merge commit above before the dedicated P17-010 branch was created.

The owner authorized only a fresh read-only detection, native capacity query,
and complete backup. The preflight below performed no `0x101b`, constructed no
sender, called no backend write method, and changed no device state. The two
phrases in the final section are sealed bindings for a later task boundary;
they were not requested, supplied, or consumed by P17-010.

## Read-only sequence and preserved evidence

The physical sequence was performed in order:

1. Detection reported exactly one device: Sony `054c:001e`, bus 2, address 3.
2. A first capacity-output path was rejected by the CLI before device access
   because the path already existed. It is preserved as a superseded
   host-attempt record and is not used as evidence.
3. The successful native `0x0019` query produced one 64-byte response with
   SHA-256
   `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662`.
   The parsed `+0x08` capacity limit is 3,145,728 bytes.
4. One fresh complete eight-object backup was captured and verified. Its
   manifest SHA-256 is
   `2a581a9282e56cac31c1e7baa42593a5b15ed94c3e0f301f6f5c9321603f9ebf`;
   its dynamic blob is 2,075,256 bytes with SHA-256
   `e3ac59cb5586a5dc35ea04f6bf24f5cc6509931761ece01bc2605a717335e741`.

The actual raw capture is `01-preflight/backup-before-0001`. The adapter-bound
copy `01-preflight/adapter-bound-backup-0003` was made with an injected
offline callback over that captured archive so the merged adapter could
re-run its complete verifier and reconstruction gates. This was not a second
hardware capture. All raw objects and the generated candidate/transaction
artifacts remain outside Git. The external `preservation-manifest-v1.json`
covers 67 files and replays with zero mismatches. Later non-overwriting v2
and v3 manifests preserve their predecessors unchanged and replay with zero
mismatches; v2 covers 69 files and v3 covers 72 files. The v3 set includes
the corrected sealed projection and the scoped branch-boundary observation.

## P17-009 state reconciliation

The P17-009 baseline was re-verified before comparison. The fresh state is
equal under the corrected immutable `BackupStateIdentity`:

`6b330ac1b77960327f3532a0c5723d6b514ec06111344267fd2a2df888160510`

The comparison reports no raw-state differences. It retains, rather than
normalizes away, six acquisition-provenance differences: archive directory,
manifest SHA-256, created time, updated time, per-object received times, and
verification time. These fields are excluded from raw-state equality by the
reviewed P17-008 policy; device/protocol/object roles, filename semantics,
lengths, raw object hashes, dynamic blob, and fixed-state hashes remain
included.

The dynamic backup contains no
`root\\IC_P17_LIBRARY_20260831_03` path, so the intended additive destination
is absent. The fresh fixed state is eligible: `0x001b` has six valid active
display-history references, and `0x001c`–`0x001f` remain the supported
all-zero state. Candidate construction semantically rebases the six counted
references by the exact `0x140` metadata delta at the reviewed insertion
point; each resolves to the same preserved path and record.

## Exact package and candidate bindings

The preserved P17-004 Library item was revalidated without modifying its
catalog or package:

- catalog item: `f767f6ba-7ea2-5bd9-8e0d-9bf8443946ae`;
- package manifest binding:
  `caa60795f9f5bc136f0faf8965addf28c48401641cdb2ea73aa705e5e361ba75`;
- package profile: one root folder with ordered TXT/BMP/TXT children;
- destination: `root\\IC_P17_LIBRARY_20260831_03`;
- children: `01-introduction.txt` (3,294 bytes), `02-page-01.bmp`
  (10,302 bytes), `03-ending.txt` (2,036 bytes);
- payload hashes, source hashes, paths, order, and profile/template bindings
  are included in the sealed hash-only report;
- reviewed native template blob SHA-256:
  `6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b`.

The reconstructed operation remains byte-identical to the P17-009-approved
operation:

- baseline model: 2,075,256 bytes;
- candidate model: 2,091,292 bytes;
- growth: 16,036 bytes;
- baseline available growth: 1,070,472 bytes;
- post-candidate capacity margin: 1,054,436 bytes;
- candidate blob SHA-256:
  `a5e9ca7f429a6f75583c1c5701bb669ed2b7f79e068dda69c63bb06300174761`;
- prospective `0x101b` transaction SHA-256:
  `1d1adc02cee8b856e2e8281ff623e84e681ec893793bebacb247a82c788749d5`;
- new-record timestamp: `0x6a958595`;
- timestamp policy: preserve existing timestamps and use one explicit frozen
  value for new records only; do not reproduce legacy global rewriting.

The new P17-010 seals bind the fresh preflight and are not expected to equal a
prior outer seal when acquisition provenance changes:

- core preflight seal:
  `fa9f8fbed201648bc351dd65b3e206460fdf11576385806739d065b77866fbc4`;
- outer preflight seal:
  `d25ca9d32b9417f7784cbecbce8bc25b8324aa55ee1cc88519249aa04f2f3a91`.

The original non-overwriting sealed projection remains preserved. Its capacity
label is clarified by
`02-sealed-preflight/sealed-preflight-corrected-0001.json`, which explicitly
records 1,070,472 bytes of baseline available growth and 1,054,436 bytes of
post-candidate headroom. The adapter's actual preflight seal, candidate, and
transaction are unchanged because this correction is a projection-label
clarification, not a change to the sealed adapter audit.

The expected additive path delta is exactly the new root folder and its three
ordered children; no removal, overwrite, merge, rename, restore, or sync is
bound. The adapter remains unregistered and unreachable from normal GUI/CLI
imports. Automatic retry is false.

## Evidence classifications

- **Verified:** PR #16 merge base; one-device detection record; native `0x0019`
  length/hash/parsed capacity; complete eight-object backup integrity; raw
  state identity; target absence; package/catalog/source/template hashes;
  fixed/display-history eligibility; candidate/transaction equality with
  P17-009; capacity fit; sealed report integrity; sender call count zero; and
  external manifest replay.
- **Observed:** bus 2/address 3; capture acquisition timestamps and archive
  paths; the CLI's non-overwrite refusal for the superseded capacity path;
  the fact that the authorized read-only physical sequence completed; and the
  working tree being clean when the task branch was created. The last fact is
  retained as a branch-boundary observation and is not independently
  reconstructible from Git afterward.
- **Inferred:** the future operation's exact additive post-state and
  successful one-shot behavior, conditional on a later fresh revalidation,
  new approval, explicit `0x0000`, and independent post-backup/read-back.
- **Unresolved:** physical compatibility of this new Library content, native
  numeric completion semantics, operation-specific capacity semantics beyond
  the observed response, and interrupted-write recovery/atomicity.

## Independent review and disposition

The independent R3 review covers the fresh-evidence boundary, raw/provenance
identity separation, target absence, exact candidate/transaction equality,
approval phrase freshness, sender construction ordering, single-send/no-retry
rule, and the no-write stop. The reviewer required explicit capacity-margin
terminology and scoping of the transient branch-cleanliness observation;
both corrections were completed with the original external artifacts
preserved. The corrected review and re-review are recorded in
`analysis/phase-13-p17-010-r3-review-20260901.md`.

P17-010 stops at **READY_FOR_HARDWARE_TEST**. A later task must perform an
immediate final read-only revalidation and obtain both exact phrases before
constructing a sender:

`APPROVE P17-009 MODERN LIBRARY PACKAGE SMOKE 01`  
`CONFIRM P17-009 ONE INFOCARRY MULTI-CHILD PACKAGE`

No phrase is authorization by implication, and no phrase from an older task
may be reused.
