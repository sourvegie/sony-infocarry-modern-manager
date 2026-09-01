# P17-009 — corrected raw-state Library-package fresh preflight

Date: 2026-09-01
Base: canonical `main` at `cd086b5e292f7d0ff6f4eefe8a2a5350864f9ad9`
Risk: R3 — device-state candidate and future one-shot write boundary
Disposition: **READY_FOR_HARDWARE_TEST — host-only approval boundary**

## Scope and boundary

P17-009 produced a fresh, read-only, operation-specific preflight for the
existing P17-004 Library item. The exact future target is
`root\\IC_P17_LIBRARY_20260831_03` with one folder and the ordered children
`01-introduction.txt`, `02-page-01.bmp`, and `03-ending.txt`. This record does
not claim generalized package compatibility.

The owner authorized only read-only preparation. Sony detection, capacity
query, and complete backup capture were performed in order. No sender was
constructed, no backend write call occurred, no USB transmission occurred,
and no `0x101b` request or device-changing operation was performed. No
operation phrase was requested or consumed.

## Fresh preflight evidence

The new non-overwriting external evidence root is:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-17-p17-009-corrected-raw-state-preflight-20260901-01/`

The fresh detection observed exactly Sony `054c:001e` at bus 2/address 3.
The preserved native `0x0019` response is 64 bytes with SHA-256
`c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a` and a
parsed capacity limit of 3,145,728 bytes.

The fresh complete eight-object backup is preserved under
`01-preflight/adapter-bound-backup-0003`. Its manifest SHA-256 is
`b143485b76935c69a427c13f17f01fc2ebf2c1e0a7fbe596bd3b678eff88d403`, its
dynamic blob is 2,075,256 bytes with SHA-256
`e3ac59cb5586a5dc35ea04f6bf24f5cc6509931761ece01bc2605a717335e741`, and its
canonical raw-state identity SHA-256 is
`6b330ac1b77960327f3532a0c5723d6b514ec06111344267fd2a2df888160510`.
The target folder was absent from this verified fresh state.

The original versioned external preservation manifest
`preservation-manifest-v1.json` remains immutable and covers 67 preserved
entries, including superseded host-only attempts. Its metadata listed the
authoritative `02-sealed-preflight-0002` report as both authoritative and
superseded. Without modifying v1 or any raw evidence, the non-overwriting
`preservation-manifest-v2.json` corrects that index, records v1 as preserved
evidence, and covers 68 entries; its replay produced zero mismatches.
Candidate and transaction bytes remain external under the sealed preflight
directory; this repository record contains hashes and structural facts only.

## Raw-state identity and provenance

The fresh backup was compared with the preserved P17-004 refresh backup only
after both backups passed the complete/integrity verifier. The comparison
reported `raw_state_equal=true`; both canonical identities are
`6b330ac1b77960327f3532a0c5723d6b514ec06111344267fd2a2df888160510`, and no
raw-state differences were reported.

Five acquisition-only provenance differences remain explicitly recorded:
archive directory, archive created time, archive updated time, the full
manifest SHA-256, and the eight per-object received timestamps. These values
are retained in both backup records and in
`03-audit/backup-state-comparison-0001.json`; they are excluded from raw-state
equality by the reviewed P17-008 identity rule. No byte normalization or
archive rewriting was performed.

## Library/package and candidate bindings

The preserved P17-004 catalog item is
`f767f6ba-7ea2-5bd9-8e0d-9bf8443946ae`. The package contract is
`infocarry-prepared-typed-media-package-v1`, with explicit one-item grouping
and no inferred grouping. The canonical package manifest binding is
`caa60795f9f5bc136f0faf8965addf28c48401641cdb2ea73aa705e5e361ba75`; the
preserved manifest file SHA-256 is
`ab344dc414d2e84c6e4ff52544bffe859d519a53987bce7083b87c9d1b512cfc`.
The catalog file SHA-256 is
`1c56c1ab76656d0f65bb1c5e8270303edcc2297df47d312a7b165d0aa03e7742`; its
canonical binding hash in the sealed candidate is
`58cad0352fceff98433f5d688525454fa719b89c23c5fc517e869210f2d0bea1`.

The ordered child bindings are:

| Order | Kind | Relative name | Prepared bytes | Payload SHA-256 |
| ---: | --- | --- | ---: | --- |
| 0 | TXT | `01-introduction.txt` | 3,294 | `38391cc8f2ea488c09990562539c206df14cfef5bad6148ab7e73b2af49ad9ad` |
| 1 | BMP | `02-page-01.bmp` | 10,302 | `f795a8e1466c3988b804f344645a6208bdcfa27e9d51d8b314c99d9a5973aadd` |
| 2 | TXT | `03-ending.txt` | 2,036 | `1dcafec84c06a52c24d898f389bb94fefea1c0569457ae92476c86a906fb5151` |

The reviewed native template identity is
`6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b`.
The candidate preserves the validated 32-byte TXT and 16-byte BMP template
prefix identities and the exact payload hashes above. The sealed candidate
has 399 records, length 2,091,292 bytes, and SHA-256
`a5e9ca7f429a6f75583c1c5701bb669ed2b7f79e068dda69c63bb06300174761`.
It adds exactly the root folder and these three child paths; no paths are
removed. The candidate growth is 16,036 bytes from the 2,075,256-byte
baseline, leaving 1,054,436 bytes of parsed-capacity margin.

The prospective transaction is command `0x101b`, payload length 2,156,828
bytes, with SHA-256
`1d1adc02cee8b856e2e8281ff623e84e681ec893793bebacb247a82c788749d5`.
The explicit modern timestamp policy uses one frozen new-record value
`0x6a958595` and preserves every existing record timestamp. It does not
reproduce legacy operation-wide timestamp rewriting.

## Fixed state and display history

The accepted fixed-state policy is
`verified_display_history_0x001b_semantic_rebase_plus_zero_0x001c_to_0x001f`.
The fresh `0x001b` block contains six valid active references. Each resolves
to the same preserved record and path after the exact insertion relation is
applied: insertion offset `0x400`, absolute offset `0x440`, metadata delta
`0x140`, six references rebased. Count, headers, unused tail, entry order,
and unshifted bytes remain protected. The candidate `0x001b` bytes are
therefore semantically preserved but not raw-byte identical. The `0x001c`-
`0x001f` blocks remain the supported all-zero state. Unrelated paths,
payloads, timestamps, unknown record bytes, and fixed-state objects remain
bound by the candidate preservation policy.

## Approval boundary and evidence classifications

The preflight is sealed under
`02-sealed-preflight-0002/sealed-preflight.json` with seal SHA-256
`183660f73c586474878a4242ebc2c219c41d96f8f4fa7363235edd695c408e79`.
The operation-specific phrases bound into that sealed, future operation are:

- owner approval: `APPROVE P17-009 MODERN LIBRARY PACKAGE SMOKE 01`
- confirmation: `CONFIRM P17-009 ONE INFOCARRY MULTI-CHILD PACKAGE`
- policy: `explicit_operation_phrase_v1`

These phrases were generated for this boundary, but neither was requested or
consumed. The expired P17-007 phrases are rejected under the explicit policy.
Any later live task must create a new fresh preflight and obtain separate
owner approval; this record does not authorize a write.

The isolated adapter consumes a thread-safe, process-local single-use claim
keyed by the sealed preflight hash immediately before sender construction.
Repeated execution calls, including calls using a same-seal copied preflight,
fail closed after a sender attempt; a fresh preflight and new approval are
required for another operation. Cancellation or a failed gate before that
claim is consumed performs no sender call.

Classification of the conclusions:

- **Verified:** complete backup integrity; raw-state identity equality;
  Sony identity; parsed capacity; target absence; package/catalog/child
  hashes and order; reviewed template; candidate, transaction, and seal
  hashes; capacity fit; fixed-state eligibility; semantic display-history
  rebase; preservation manifest replay; zero sender/backend/USB/write
  activity.
- **Observed:** detection location bus 2/address 3 and the acquisition
  timestamps/provenance differences recorded by the external comparison.
- **Inferred:** the exact candidate is a reproducible offline construction
  from the fresh verified backup, the preserved package, and the reviewed
  templates; the frozen timestamp policy is suitable for the constrained
  future operation.
- **Unresolved:** native numeric completion decoding, operation-specific
  capacity-response semantics beyond this parsed preflight, and physical
  compatibility of this new Library content. These do not invalidate this
  read-only host preflight, but they require future operation-specific gates.

## Review and final disposition

Focused adapter/gate/bridge tests pass after adding explicit-policy phrase
binding, rejection of expired phrases, and same-seal second-execution
refusal. The complete portable suite passes with **599 tests and 3
intentional evidence-dependent skips**. `git diff --check`, compilation,
excluded-evidence/history audit, external preservation-manifest v2 replay,
and independent R3 review pass. The review record is
`analysis/phase-13-p17-009-r3-review-20260901.md`.

P17-009 is **READY_FOR_HARDWARE_TEST** only at the host-only owner-approval
boundary, with sender calls 0, backend write calls 0, and no `0x101b`. No
hardware write is part of P17-009.
