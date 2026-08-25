# H.2 offline deletion hardening — preserved-evidence comparison

Date: 2026-08-26
Status: **offline hardening active; modern live deletion remains fail-closed**

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
| Modern candidate | 373 records; 2,051,420 bytes; SHA-256 `74bdf2887430357a6d08fb0cbaccaec0d15cc1c6c35d720c696b27ee39d58f9e` | derived offline |
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

After that timestamp-only normalization, twelve non-timestamp bytes remain
different. They are the last byte of `field_08_be32` in twelve parent-marker
records at these post-operation offsets:

`0x00003d80`, `0x00003ec0`, `0x00004180`, `0x00004440`,
`0x00004700`, `0x000049c0`, `0x00004c80`, `0x00004f40`,
`0x00005200`, `0x000054c0`, `0x00005780`, `0x00005a40`.

The modern candidate retains the rebased value `0x00000340` in those fields;
the legacy post-delete model contains `0x00000380`. This is a real
non-timestamp structural difference, not a permitted normalization. The
normalized comparison therefore fails closed. No rule has been inferred from
this difference and no builder bytes were changed to imitate it.

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
  send, and post-entry expiry as indeterminate with no retry.

## Supported and rejected boundary

The offline model remains limited to one existing reachable ordinary TXT leaf.
It supports all-zero fixed state and only the exact target-reference clearing
forms justified by the preserved stateful deletion observation. It rejects
root records, directories, malformed or overlapping segments, ambiguous or
unsupported targets, unfamiliar fixed-state bytes, unresolved references,
nonzero/missing/malformed completion, read-back mismatch, and every condition
that would require retry.

The captured comparison does **not** close H.2 live readiness because the
twelve parent-marker differences are unexplained after timestamp normalization.
R2 and R15 remain open: legacy request-4 completion is not trustworthy in the
preserved capture, and physical interrupted-write atomicity/recovery is not
proven. The normal GUI/CLI remains disconnected and no live delete operation
is prepared or authorized by this report.

## Verification checkpoint

- Complete suite: **467 passing tests, 3 intentional skips**.
- Focused deletion suite: **32 passing tests**.
- `git diff --check`: required before commit and push.
- No external evidence, device backup, raw capture, Manager file, or live
  operation artifact is tracked.

The exact next step is offline review of the twelve parent-marker
`field_08_be32` differences or a documented decision to keep that boundary
fail-closed. No live-USB approval is requested from this checkpoint.
