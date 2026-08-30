# P16-001 — Capture 01 independent R3 review

Date: 2026-08-30
Disposition: **PASS — COMPLETE for the exact constrained native mixed evidence scope**
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
| Manager result/owner outcome observation | Pass; owner confirms normal completion without an error and device accessibility; no dialog text invented |
| Timestamp event mapping | Pass; owner confirms idle, immediately pre-send, and completed/packet-idle meanings |
| New-record timestamp placement | Pass; 0x6a942449 = 2026-08-30T12:38:33Z within the confirmed Send Selected interval |
| Operation-specific capacity evidence | Unresolved and non-blocking for this native structural gate; future modern preflight must validate fresh 0x0019 evidence |
| Numeric completion decoding | Unresolved and non-blocking; normal Manager completion plus persistent post-state are independently established |
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
objects. The owner-supplied outcome confirms normal Manager completion and
device accessibility, and the three timestamp events are now mapped. The
0x0024 response, 0x8004 probe, global timestamp rewrites, and raw transaction
tail remain recorded as observations; none is normalized into capacity or
numeric completion.

## R3 decision

The post-backup correction and owner confirmation are accepted for the exact
constrained native mixed package. P16-001 is **COMPLETE** for this native
evidence scope. Operation-specific capacity semantics and numeric completion
decoding remain explicit non-blocking unresolved observations; any future
modern runner must independently obtain and validate fresh 0x0019 capacity
evidence during preflight. No modern mixed candidate, dossier, or device
transaction is prepared by this task, and no conclusion is generalized
beyond this exact package shape.
