# H.2 constrained modern-delete smoke — attempt 01

Date: 2026-08-27

## Result

One separately approved, isolated modern delete smoke completed for the
owner-selected root-level ordinary TXT record:

`root\\IC_TEST_01.txt`

The isolated runner issued exactly one `0x101b` transaction. The sender
returned the accepted completion value `0x0000`, and the required independent
post-operation backup and read-back verification passed. No retry was issued.
This is evidence for the narrow tested case only; it is not generalized delete
compatibility or authorization for a normal product action.

The raw before/after backups and sealed preflight remain outside Git under:

`${EVIDENCE_ROOT}/phase-13-i7-h2-modern-delete-20260827-01/`

The final external manifest is
`checksums/SHA256SUMS-post-delete-01.txt` under that session and covers all
21 preserved files with zero hash mismatches. Its SHA-256 is:

`baa348b18ef0d2665baf861a7e980aad93021b187a5397479a231f5482036f87`

## Bound operation

- device: VID `0x054c`, PID `0x001e`, bus `2`, address `3`;
- pre-delete manifest SHA-256:
  `39323d69d27c55d342dd1c3c4129268ddad1a43c614d01be513c7100d67775c8`;
- pre-delete dynamic blob SHA-256:
  `fbfe0dc9898a0cd6c406bd26542859282a1a410b059b16812c32522a9ce8e450`;
- target record offset: `0x000001c0`;
- target payload length: 41 bytes;
- target payload SHA-256:
  `85c8e82f3547ace5c72f3f2c1c3817788cd134e4e6bbf4dca9032d4ca11e4c08`;
- candidate dynamic blob SHA-256:
  `d4e4fa74e4338c18aa366e016ba9cb756d0af4e84b3bd19045993553d3526f20`;
- prospective transaction SHA-256:
  `78636328fc7f386fcaf5a565421cd7feae0525a675a740019e7e1813aa148298`;
- exact confirmation phrase: `DELETE ONE INFOCARRY ITEM`;
- separate owner approval: `APPROVE H2 MODERN DELETE SMOKE 01`.

## Independent read-back

| Check | Result | Classification |
| --- | --- | --- |
| Completion | `0x0000` | verified by the one-shot runner |
| Record count | 373 → 372 | verified |
| Path delta | exactly `root\\IC_TEST_01.txt` removed; no path added | verified |
| Dynamic model | post-delete SHA equals candidate SHA | verified |
| Surviving payloads | all byte-identical | verified |
| Fixed state `0x001b`–`0x001f` | exact supported all-zero state preserved | verified |
| Unrelated backup objects | unchanged except payload-dependent `0x0024` and `0x8004` probe/model objects | verified under the documented verifier boundary |
| Post-delete manifest | `fc8a289c10564038f9fbeddb9dc933fc415fc3d7a7ade9ab7cbb3dd667119835` | verified |
| Post-delete dynamic blob | `d4e4fa74e4338c18aa366e016ba9cb756d0af4e84b3bd19045993553d3526f20` | verified |

The post-delete archive is complete. Its fixed-state object hashes are the
same all-zero digest used by the sealed preflight:

`f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b`

The runner's provisional modern deletion policy preserved surviving record
timestamps and cleared no fixed-state references because the authorized
pre-state was all zero. This smoke therefore does not validate deletion of a
record referenced by history, marks, or bookmarks.

## Boundary and remaining risk

The result establishes one live modern deletion effect for one existing,
reachable, root-level ordinary TXT record on one supported all-zero fixed
state. It does not prove arbitrary record deletion, nonzero-state handling,
timestamp generation, physical atomicity, rollback, or recovery after an
interruption. R15 remains open.

The delete runner remains outside the normal CLI and ttk imports. Normal delete,
restore, recursive/bulk operations, synchronization, and routine product
exposure remain disabled. Any future device-changing delete requires a new
operation-specific preflight and explicit approval; the strict completion,
fresh-backup, read-back, and no-retry gates remain mandatory.
