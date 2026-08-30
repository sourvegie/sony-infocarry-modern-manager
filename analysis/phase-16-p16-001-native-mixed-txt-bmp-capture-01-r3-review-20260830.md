# P16-001 — Capture 01 independent R3 review

Date: 2026-08-30
Disposition: **PASS — post-backup correction reconciled; native gate remains blocked for explicit unresolved evidence**
Risk: **R3 — device/safety critical**

This second-pass review covers the newly obtained complete post-operation
backup, its manifest and object hashes, the preserved Capture 01 raw tree,
the preserved native USB transaction, the exact sanitized fixture, and the
offline post-backup verification. It does not authorize another legacy
operation or any modern device transaction.

## Review checks

| Check | Result |
| --- | --- |
| Raw Capture 01 copied without normalization or overwrite | Pass; 20-file source/preserved hash trees match |
| Complete fresh pre-operation backup and target absence | Pass; 054c:001e, eight objects, 384 records, target absent |
| Exact source fixture and source hashes | Pass; three prepared sources retained and matched |
| Native log integrity and ordinary 0x101b parse | Pass; one header, declaration/range/N/M consistency, checksum-valid model |
| Complete post-operation backup | Pass; new backup is complete, eight object hashes validate |
| Post backup versus native transaction model | Pass; exact byte equality, same SHA-256 6c654fe4...f796b |
| Mixed folder, markers, child order, offsets, and fields | Pass for the checksum-valid post model |
| TXT/BMP payload equality | Pass; all three post-backup payloads equal exact sources |
| BMP native prefix persistence | Pass; 16-byte all-ff prefix is present in post state |
| Unrelated shared file payload/prefix preservation | Pass; zero shared file payload or prefix differences |
| Fixed-state comparison | Pass for 0x001b through 0x001f; each unchanged and all zero |
| Timestamp behavior | Observed and retained; all 323 shared timestamps changed |
| Manager-local before/after comparison | Pass as local bookkeeping; no device-state claim from it |
| Manager result/owner outcome observation | Unresolved; no separate verbatim observation supplied |
| Operation-specific capacity evidence | Unresolved; 0x0024/probe differences are retained without interpretation |
| Numeric completion decoding | Unresolved; no explicit 0x0000 is claimed |
| Modern mixed candidate, authorization, or hardware action | Correctly not prepared or performed |
| Normal GUI/CLI transfer exposure | Unchanged and disabled |

## Correction loop

The first review correctly blocked the native gate because the supplied
Capture 01 tree lacked a complete post-operation raw backup. A new read-only
backup was subsequently obtained at the non-overwriting external destination
05-post-operation/backup-20260830-02/. The independent verification record
confirms that the eight object hashes match, the dynamic object parses and
checksum-validates, and its bytes exactly equal the native range-5/range-8
transaction model.

The corrected evidence therefore verifies device persistence of the exact
three-child TXT/BMP/TXT shape and preservation of shared payloads and fixed
objects. It does not fill the remaining evidence gaps. The 0x0024 response,
0x8004 probe, timestamp rewrites, and raw transaction tail remain recorded as
observations; none is normalized into capacity, event meaning, or completion.

## R3 decision

The post-backup correction is accepted for the exact constrained native mixed
package. The native gate remains **BLOCKED_BY_EXTERNAL_EVIDENCE** because the
required Manager result/owner observation, timestamp event mapping,
operation-specific capacity semantics, and explicit numeric completion are
still unresolved. No modern mixed candidate, dossier, or device transaction
may proceed from this record. Any later evidence intake must be
non-overwriting, separately reviewed, and must not trigger a repeat write
automatically.
