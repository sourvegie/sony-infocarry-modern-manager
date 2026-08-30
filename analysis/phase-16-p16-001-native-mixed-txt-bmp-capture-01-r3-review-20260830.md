# P16-001 — Capture 01 independent R3 review

Date: 2026-08-30  
Disposition: **PASS — blocked gate correctly applied; corrections resolved**  
Risk: **R3 — device/safety critical**

This is an independent second-pass review of the supplied Capture 01 intake,
the external preservation records, the offline native parser output, and the
sanitized model correction. It does not authorize another legacy operation or
any modern device transaction.

## Review checks

| Check | Result |
| --- | --- |
| Raw capture copied without normalization or overwrite | Pass; 20-file source/preserved hash trees match |
| Complete fresh pre-operation backup and target absence | Pass; `054c:001e`, eight objects, 384 records, target absent |
| Exact source fixture and source hashes | Pass; three prepared sources retained outside Git and committed fixture unchanged |
| Native log integrity and ordinary `0x101b` parse | Pass; one header, declaration/range/N/M consistency, checksum-valid staged model |
| Mixed folder, marker, child order, offsets, and fields | Pass for the parsed transaction model |
| TXT/BMP transaction payload equality | Pass for the parsed staged model |
| Native BMP prefix observation | Pass; exact 16-byte all-`ff` prefix recorded without claiming persistence |
| Manager-local before/after comparison | Pass; unchanged VICDATA/Memo and changed order.vnw retained as local bookkeeping |
| Complete post-operation raw backup | Missing; material gate blocker |
| Manager result/owner outcome observation | Missing; material gate blocker |
| Timestamp event mapping | Missing; raw sequence values retained unresolved |
| Capacity/fixed-state post evidence | Missing; no estimate substituted |
| Numeric completion decoding | Unresolved; no `0x0000` normalization |
| Modern mixed candidate, authorization, or hardware action | Correctly not prepared/performed |
| Normal GUI/CLI transfer exposure | Unchanged and disabled |

## Correction loop

The first offline model correction changed BMP size accounting and template
validation from the prior generic 32-byte assumption to the observed 16-byte
BMP prefix while preserving 32-byte TXT behavior. The focused test pass
initially exposed a synthetic template whose BMP `field_14` still declared a
32-byte prefix; that fixture was corrected to `0x100`. The candidate audit
payload-offset calculation was also corrected to use the selected type's
actual template prefix length. The focused suite then passed all 17 tests.

No raw evidence was edited. No unexplained difference was normalized away.
The missing post backup, result, mapping, capacity, fixed-state, and numeric
completion evidence remains explicitly unresolved.

## R3 decision

The corrected offline model change is limited to an exact rule observed in the
native transaction. The capture does not close the native compatibility gate
because it cannot prove device persistence or the required post-operation
comparisons. The final task disposition remains
**BLOCKED_BY_EXTERNAL_EVIDENCE**. No modern mixed-package dossier or device
operation may proceed from this result.

