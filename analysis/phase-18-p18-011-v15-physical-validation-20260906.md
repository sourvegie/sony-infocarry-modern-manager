# P18-011 — VNW-V15 physical validation

Date: 2026-09-06  
Repository: `sourvegie/sony-infocarry-modern-manager`  
Canonical base: `1c16d48856328de53171a13f8e5665da0a46e47a`  
Branch: `task/P18-011-v15-physical-validation`  
Risk: R3 physical validation  
Outcome: **ESCALATION_REQUIRED**

## Scope and repository gate

The owner-approved operation was the fixed P18-010 VNW-V15 package:

`root\\IC_P18_LIBRARY_20260906_01`

with exactly three ordered children:

1. `01-introduction.txt`
2. `02-page-01.bmp`
3. `03-ending.txt`

The required fresh branch was created from the exact upstream canonical main
commit. The checkout was clean at branch creation, the merged P18-010
implementation and required persistent claim/lock modules were present, and
no production code was changed. The exact owner confirmation supplied for this
run was `ADD IC_P18_LIBRARY_20260906_01 ONCE`.

## Host validation

The supported bundled Python 3.12.14 runtime was used with the declared
`PyUSB==1.3.1` dependency in a temporary directory outside the repository.

- Focused safety suite: **128 passed**.
- Full portable suite: **751 passed, 3 intentional evidence-dependent skips**.
- Python compilation: passed.
- `git diff --check`: passed.
- No test used USB hardware or a device-changing operation.

The focused coverage included durable claim persistence and race behavior,
global-lock behavior, auxiliary-state eligibility and rebasing, exact
candidate/transaction/confirmation bindings, completion typing, no-retry
behavior, post-write backup/read-back handling, and the P18-006 adversarial
matrix.

## Installation safety state

Before this run, fresh read-only inspection of the installation-owned state
found:

- persistent execution-claim SQLite schema: valid, integrity check `ok`;
- committed execution claims: `0`;
- sender-in-flight markers: `0`;
- global indeterminate-write lock: inactive (no lock record present).

After the single authorized live attempt, the same store is still integrity
valid with exactly one consumed claim. Its sender-start marker is
`lock_recorded`, and the installation-wide indeterminate-write lock is
`locked` for the VNW-V15 incident. Neither record has been cleared or
resolved.

## Fresh device preflight and live attempt

The authoritative restart used the new external namespace
`/private/tmp/p18-011-authoritative.RjFTQ4`. The adapter's host-level USB
preflight enumerated the exact device shown by the owner: VID `0x054c`, PID
`0x001e` (Sony InfoCarry VNW-V15; bus 2, address 3 in the host observation).
Every gate was rebuilt from fresh session data; no previous capacity, backup,
candidate, seal, transaction, or derived identity was reused:

- fresh descriptors confirmed active configuration 1, interface 0 alternate 0,
  bulk OUT `0x01`, bulk IN `0x82`, and 64-byte packets;
- a new native `0x0019` response was captured and parsed as a 3,145,728-byte
  capacity (`c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a`);
- a new complete eight-object backup was captured and verified: manifest
  `2a686bcc2907cd395712fc809f0c69793df356c753a0f42a683610bb0da33816`, dynamic
  blob `4d17326ef236015321bbad71e5ebde837c12f928c98b59cc4f4d0c34751f4ea9`
  (2,091,292 bytes), and state identity
  `a6ea8922c0a1fa3231b04cbcf5de9791acf7536329b4eaf8d65a64352cacf9b9`;
- the fresh baseline contained 399 records / 335 paths, the exact target was
  absent, seven display-history entries and one bookmark group were valid for
  the reviewed semantic-preservation policy, and `0x001c`–`0x001e` were
  zero-count.

The complete adapter preflight then passed again on the live execution-time
capacity query. The fresh package manifest was
`848beb19e4d8475dff9e2aa23f0a050162d8dc26902de13e4712d0b69121db4d`; the
sealed candidate blob was
`6fd27699ca6c13a46f8d75467ba72860af8b865b7cf19046b7a91f63bf471e01`; and the
transaction hash was
`9373330cd78f58faaa0cfe61590e4cd0ce489ea5c8069c3112144e69aafe10f4`.
The exact confirmation was accepted once. The sender-start claim was consumed
and the single sender entered; no second transaction or retry was attempted.

## Transaction and physical result

The sender reported the one authorized `0x101b` transfer header and payload
progress. Adapter control flow reached post-write backup and independent
read-back handling only after the native sender returned the exact integer
`0x0000`. The live process then ended before durable terminal result-manifest
handling.
The preserved complete post-write backup has manifest
`8bf3d26ddbd28e9c91c0861889943548dc5082d5c5f20bf14ac6496b1b953c6f` and
dynamic blob
`6fd27699ca6c13a46f8d75467ba72860af8b865b7cf19046b7a91f63bf471e01`, matching
the sealed candidate blob. That is useful post-write evidence, but it is not a
terminal completion record.

| Gate | Result |
| --- | --- |
| Fresh VNW-V15 identity/profile | Passed; exact `0x054c:0x001e` |
| Fresh native `0x0019` capacity | Passed; 3,145,728 bytes |
| Fresh complete pre-write backup | Passed; eight objects, integrity verified |
| Destination absence | Passed against the fresh 335-path baseline |
| Fresh `0x001b`–`0x001f` state | Passed reviewed class; `0x001b`/`0x001f` semantic-preservation inputs, `0x001c`–`0x001e` zero-count |
| Runtime confirmation | Accepted once: `ADD IC_P18_LIBRARY_20260906_01 ONCE` |
| Durable execution claim | One claim consumed |
| Sender-in-flight marker | `lock_recorded` after live-process failure |
| Sender invocations | `1`; no retry |
| `0x101b` transmissions | One authorized transfer entered; no second transaction |
| Native sender return | Passed the exact integer `0x0000` gate |
| Durable terminal-success closure | Not established; no durable result manifest or independently verified terminal-success record exists |
| Post-write backup | Complete and verified; dynamic blob matches candidate |
| Independent read-back | Not safely closable: verifier rejected nonzero `0x001f` bookmark values |
| Human screen acceptance | Not captured |
| Global lock after attempt | Active installation-wide indeterminate-write lock |

Native sender return: passed the exact integer `0x0000` gate.

Durable terminal-success closure: not established because no durable result
manifest or independently verified terminal-success record exists.

The approved bookmark-preservation preflight allowed the nonzero `0x001f`
bookmark group, but the terminal read-back verifier was invoked without the
corresponding `allow_verified_bookmarks` allowance and returned a failure for
that preserved state. This verifier/closure failure cannot be converted into
physical success evidence. The absent terminal manifest and preserved
sender-start marker therefore require escalation. No overwrite, deletion,
alternate destination, corrective write, retry, or capability expansion is
authorized. No raw device evidence or private backup was added to Git.

## Independent R3 review disposition

The independent R3 review found:

```yaml
P0: none
P1: none
P2: corrections required
```

The production-code P2 is that
`prepared_package_multi_verify.py` does not derive and pass the sealed P18-010
bookmark-preservation allowance during terminal read-back assessment. This
defect is deferred to a separate host/read-only P18-012 closure task. It is
not fixed in this documentation-only PR.

## Review disposition

The result is **ESCALATION_REQUIRED**, not `COMPLETE` and not
`READY_FOR_HUMAN_TEST`. The previously completed independent P18-010 host-side
R3 review remains the review basis for the unchanged implementation. The
installation-wide lock must remain active. Recovery is limited to a later
read-only diagnostic and an explicit documented recovery decision; another
write or automatic retry is prohibited. The P18-012 closure task must address
the deferred host verifier defect before any terminal-success assessment.

`CAPABILITY_MATRIX.md` is unchanged. The fixed TXT → BMP → TXT operation has
not gained new physical evidence, and standing Experimental exposure remains
disabled.
