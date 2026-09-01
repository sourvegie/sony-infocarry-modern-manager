# P17-018 — Exact Library-package one-shot live smoke

Date: 2026-09-01
Base: canonical `main` at merged P17-017 commit `7039c33dca9b06a987cb40340837cb938272c73d`
Risk: R3 — device-state mutation and one-shot write boundary
Disposition: **COMPLETE — exact constrained scope only**

## Scope and authorization

The operation was limited to the sealed P17-018 immutable safety bundle
`3d2461ead56a7a339cde100f64f1530769d0bd2195f80f0a76d75f62322e126d` and its
one additive destination `root\IC_P17_LIBRARY_20260831_03`. The ordered
children were `01-introduction.txt`, `02-page-01.bmp`, and
`03-ending.txt`. The owner supplied these exact phrases after the P17-018
read-only preflight:

```text
APPROVE P17-018 MODERN LIBRARY PACKAGE PREFLIGHT 01
CONFIRM P17-018 ONE INFOCARRY MULTI-CHILD PACKAGE
```

No other target, package, mode, retry, deletion, restore, synchronization,
GUI/CLI operation, or device-changing action was authorized.

## Fresh gates and bindings

The production entrypoint allocated the new direct-child attempt root
`/Users/stardust/Projects/InfoCarry-Evidence/phase-17-p17-018-library-package-live-execution-20260901-01/p17-018-attempt-151c253bd93d4635bf159fd4e081b18f/`.
It then performed its final immediate revalidation in order:

- exactly one Sony `054c:001e` was detected at bus 2/address 3;
- native `0x0019` returned 64 bytes with raw SHA-256
  `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662`;
- parsed capacity was 3,145,728 bytes;
- the complete eight-object pre-write backup was verified with manifest
  SHA-256 `e655f9781546cf15955a8170f9ce062f331f3acb74fbb00a30789cada8678850`;
- its dynamic blob SHA-256 was
  `e3ac59cb5586a5dc35ea04f6bf24f5cc6509931761ece01bc2605a717335e741`;
- its raw-state identity was
  `6b330ac1b77960327f3532a0c5723d6b514ec06111344267fd2a2df888160510`;
- the destination was absent; and
- the package, catalog, source/prepared children, reviewed template,
  candidate, transaction, fixed/display-history policy, authorization, and
  seals matched the immutable bundle.

The candidate SHA-256 was
`a5e9ca7f429a6f75583c1c5701bb669ed2b7f79e068dda69c63bb06300174761`.
Candidate growth was 16,036 bytes, leaving 1,054,436 bytes of parsed native
capacity margin. The transaction SHA-256 was
`1d1adc02cee8b856e2e8281ff623e84e681ec893793bebacb247a82c788749d5`.

## Execution and read-back

The single-use authorization was consumed once. The guarded runner made one
logical sender call and transmitted one exact `0x101b`; the execution wrapper
recorded 20 bulk-write calls. Completion was the explicit integer `0x0000`.
No retry was attempted.

The complete post-operation backup was preserved and independently verified.
Its manifest SHA-256 was
`4bdf5c96f97cdd87cd7fb67b5cf219fb2a5eea67e2cafde4e1500c8c5e3edf77`, and
its dynamic blob matched the candidate SHA-256 exactly. Independent
read-back verified:

- exactly four added paths: the `_03` folder and its three ordered children;
- no removed paths;
- 331 shared paths unchanged;
- unchanged shared payloads and timestamps;
- exact fixed-state expectations; and
- semantic preservation of the six verified display-history references,
  including the reviewed metadata-delta rebasing.

The runner’s hash-only result manifest reports `readback_verified`,
`approval_consumed=true`, `sender_calls=1`, `completion=0x0000`, and
`automatic_retry_allowed=false`.

## Evidence and wrapper correction

Raw before/after backups, capacity capture, event logs, and result audit are
outside Git under the attempt root above. The external
`preservation-manifest-v1.json` contains 29 entries and replays with zero
mismatches. The runner result manifest and the corrected offline
reconciliation are also preserved there; candidate and transaction bytes
remain outside Git.

A surrounding audit wrapper raised a local `PreparedMultiVerificationError`
after the production runner had already returned its successful
`readback_verified` result. The wrapper passed the preflight core object to a
second disk-only verifier instead of `preflight.candidate.core`. This did
not affect the runner, the device result, approval consumption, or retry
behavior. The original `live-failure-audit.json` is preserved unchanged, and
`offline-result-reconciliation.json` records the corrected interpretation.
No further hardware access occurred.

## Evidence classification and boundary

- **Verified:** exact device identity, capacity response, fresh complete
  backups, raw-state equality, target absence, candidate/transaction/seal
  bindings, one `0x101b`, explicit `0x0000`, complete post-backup, exact
  four-path additive read-back, fixed state, display-history rebase, and
  unchanged shared paths.
- **Observed:** bus 2/address 3, 20 bulk-write calls recorded by the execution
  wrapper, runner result state, and the wrapper’s post-run type error.
- **Inferred:** the corrected P17-017 output lifecycle permits the same sealed
  safety identity to proceed from preflight into one live attempt without
  rebundling; this does not generalize package compatibility.
- **Unresolved:** physical human acceptance by opening all three children,
  interrupted-write atomicity/recovery, native completion semantics beyond
  this explicit result, and broader package/GUI/CLI behavior.

P17-018 is complete only for this exact one-folder Library package and its
ordered TXT/BMP/TXT children. The normal product transfer surface remains
disabled.
