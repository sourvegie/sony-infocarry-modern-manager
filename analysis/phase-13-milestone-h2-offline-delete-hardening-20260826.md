# H.2 offline deletion hardening — preserved-evidence comparison

Date: 2026-08-26
Status: **offline structural hardening complete; modern live deletion remains
unexecuted and requires separate owner review**

This report contains derived hashes and structural results only. The complete
backups, USB log, Manager files, and transaction ranges remain in the local
evidence store and were not modified or copied into Git.

## Preserved comparison

The comparison used the complete I7 pre-delete backup and complete post-delete
backup from:

`${EVIDENCE_ROOT}/phase-13-i7-legacy-delete-20260825-01/`

The provisional modern candidate was rebuilt from the pre-delete backup using
the current one-existing-ordinary-TXT model, target
`root\\IC_I7_CLOCK_01.txt`, and its verified pre-delete record offset
`0x00000380`. The candidate was built offline only.

| Result | Derived value | Classification |
| --- | ---: | --- |
| Pre-delete model | 374 records; 2,053,380 bytes; SHA-256 `5b081faf7cc733e9c63c13250d689d6e7beb52bcf10470503dd68684471ab61b` | verified preserved input |
| Modern candidate | 373 records; 2,051,420 bytes; SHA-256 `4a3b57001d72ff4824519464ee648eac47f27a91f9da1bb070babc0698e04e24` | derived offline with relation-based marker handling |
| Legacy post-delete model | 373 records; 2,051,420 bytes; SHA-256 `fbfe0dc9898a0cd6c406bd26542859282a1a410b059b16812c32522a9ce8e450` | verified preserved input |
| Path delta | exactly the target removed; no path added | verified |
| Candidate/post path equality | true | verified |
| Surviving payloads | 255 compared; 0 mismatches | verified |
| Record count | candidate and post are baseline minus one | verified |
| Candidate parsing and pointer validity | both candidate and post parse independently | verified |

All surviving record timestamps differ between the provisional modern
candidate and the legacy post-delete model because the modern policy preserves
surviving timestamps while the legacy Manager regenerates them. The comparison
masked only record bytes `[0x0c:0x10]`. It observed 373 records with changed
timestamp fields and 1,119 changed timestamp bytes. The four-byte header
checksum also differs; it is reported as a derived consequence of the model
timestamp changes, not accepted as an independent structural allowance.

After the relation-based correction, timestamp-only normalization leaves zero
non-timestamp bytes different. The twelve disputed I7 markers now preserve
`field_08_be32=0x380` while their independently moved `field_04_be32` values
rebase from `0x3a00` to `0x39c0`, matching the legacy post-delete model. The
earlier case independently supports shortening `field_08` only where the
marker's pre-delete `field_04` equals the exact parent directory whose direct
child table lost the target. This is a relation-based result, not a broader
semantic name for the marker fields.

The machine-readable comparison contract is implemented in
`src/infocarry/delete_evidence_compare.py`. It reports hashes, path/count
deltas, payload mismatches, timestamp normalization, checksum status, and
remaining structural offsets without emitting payload bytes.

## Offline hardening completed in this slice

- Synthetic coverage exercises root targets at the beginning, middle, and
  end; nested TXT deletion; multiple surviving siblings; alignment boundaries;
  a substantially larger payload; overlapping content rejection; unsupported
  target types; ambiguous target identity; all-zero/proven stateful fixed
  state; source immutability; timestamp preservation; pointer validity; and
  deterministic output.
- Authorization now validates every fixed-state hash as an exact lowercase
  SHA-256 digest and validates the bound target offset, metadata start, record
  size, baseline/candidate model lengths, and transaction N/M values for type,
  range, alignment, and consistency. The same checks apply to manually
  constructed authorization objects.
- The fake workflow now requires an explicit `FakeDeleteTransport` capability
  wrapper. The workflow module has no import path to the live sender. This is
  defense against accidental integration, not a cryptographic or language
  security boundary; the absence of a live delete adapter remains the decisive
  control.
- A finite timeout/deadline is passed through the fake transport contract.
  Deterministic fake-clock tests classify pre-start expiry as safe with no
  send, and post-entry expiry as indeterminate with no retry. This is
  cooperative enforcement: the workflow cannot forcibly interrupt an
  arbitrary Python callback that hangs forever. Actual bounded USB calls and
  low-level transport timeouts remain responsibilities of a future isolated
  live adapter; none is present here.

## Corrected relation-based evidence gate

The full I7 comparison was rerun from the preserved 374-record pre-delete
backup and compared with the preserved 373-record post-delete model. Only
surviving record timestamp bytes `[0x0c:0x10]` and the header checksum derived
from those timestamp differences were masked. No marker, pointer, flag, name,
payload, padding, unknown field, or other byte was normalized.

The result is exact for the supported structural scope: one target path was
removed, no path was added, both models contain 373 records, 255 surviving
payloads match, pointers parse independently, and the remaining
non-timestamp difference count is zero. The machine-readable result is
`analysis/phase-13-milestone-h2-offline-delete-hardening-20260826.json`; the
two-case relation matrix is
`analysis/phase-13-milestone-h2-parent-marker-two-case-matrix-20260826.md`.

## Supported and rejected boundary

The offline model remains limited to one existing reachable ordinary TXT leaf.
It supports all-zero fixed state and only the exact target-reference clearing
forms justified by the preserved stateful deletion observation. It rejects
root records, directories, malformed or overlapping segments, ambiguous or
unsupported targets, unfamiliar fixed-state bytes, unresolved references,
nonzero/missing/malformed completion, read-back mismatch, and every condition
that would require retry.

The corrected comparison closes the normalized structural evidence gate for
this offline scope. It does not prove a general legacy timestamp rule,
arbitrary fixed-state rebasing, trustworthy legacy request-4 completion, or
physical interrupted-write atomicity/recovery. The provisional modern policy
preserves surviving timestamps and accepts only the existing supported
fixed-state/reference forms. The normal GUI/CLI remains disconnected and no
live delete adapter or transaction has been prepared or executed by this
report. A future disposable modern smoke requires separate explicit owner
approval.

## Verification checkpoint

- Complete suite: **472 passing tests, 3 intentional skips**.
- Focused deletion suite (`test_backup_repack`, `test_delete_model`,
  `test_delete_hardening`, `test_delete_generalized`, and
  `test_delete_workflow`): **40 passing tests**.
- `git diff --check`: required before commit and push.
- No external evidence, device backup, raw capture, Manager file, or live
  operation artifact is tracked.

The exact next step is owner review of an unexecuted, narrowly scoped modern
delete smoke decision. Any such smoke would require a fresh complete backup,
exact target/candidate binding, one transaction, completion `0x0000`, complete
read-back, and no automatic retry. No live-USB approval is requested or
executed from this offline checkpoint.
