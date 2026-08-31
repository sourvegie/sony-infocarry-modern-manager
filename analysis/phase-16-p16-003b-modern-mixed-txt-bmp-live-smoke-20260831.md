# P16-003B — exact modern mixed TXT/BMP/TXT live smoke

Date: 2026-08-31
Status: **COMPLETE — exact constrained live scope only**
Risk: **R3 — device/safety critical**

## Scope and authorization

P16-003B executed the separately authorized modern operation for exactly one
new root-level package:

```text
root\IC_P16_MIXED_20260830_02
├── 01-introduction.txt
├── 02-page-01.bmp
└── 03-ending.txt
```

The owner supplied both exact operation-specific phrases after the fresh
sealed preflight:

```text
APPROVE P16-002 MODERN MIXED TXT BMP SMOKE 01
ADD ONE INFOCARRY MULTI-CHILD PACKAGE
```

No broader package, nesting, batch, delete, restore, synchronization, or
normal GUI/CLI transfer behavior was exercised. The P16-001 `_01` package was
not deleted, overwritten, or restored.

## Fresh preflight binding

The fresh read-only preflight captured one Sony `054c:001e` device and one
complete backup. The first verification attempt used a reference clock
sampled before the capture finished and correctly failed closed on the
future-timestamp check. The complete captured archive was not recaptured or
modified; it was copied once to a new re-verification directory and verified
with the runner's normal current-time freshness behavior before execution.

| Binding | Result |
| --- | --- |
| device | Sony `054c:001e`; bus 2, address 3 |
| fresh backup objects | 8 |
| fresh backup model | 2,064,268 bytes; 389 records; 327 reachable paths |
| fresh backup manifest SHA-256 | `703c6d919db0a5e96bfdbad209adecc25207b24c82130740091e9dd86b8d1633` |
| fresh backup dynamic blob SHA-256 | `4b2999c1cec9aeaab3973ae99e4203fa0a52af7fa5a3686205c29803886d4b9f` |
| raw `0x0019` response SHA-256 | `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662` |
| capacity field `+0x08` | 3,145,728 bytes |
| target absence | `_02` absent from the fresh backup |
| template SHA-256 | `6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b` |
| preflight seal SHA-256 | `f01a31d8e7caa06456288d5c668ad0775ef440e8124b30507fe729aaf4a27fe0` |

The exact source files were 144-byte introduction TXT, 10,302-byte validated
one-bit BMP, and 139-byte ending TXT. Their SHA-256 values, in transfer order,
were:

```text
d16567039a003110d246cc6a0a4d0b2042efa9f2240485f6a5facbb09c00dcb1
f795a8e1466c3988b804f344645a6208bdcfa27e9d51d8b314c99d9a5973aadd
a31b66d8b27676dc0af07d32ba4d17b90c54ffa39f406c37a9475672e9e46eec
```

The candidate model was 2,075,256 bytes, a 10,988-byte increase over the
fresh baseline. Remaining growth was 1,081,460 bytes, leaving a capacity
margin of 1,070,472 bytes. The candidate SHA-256 was
`c3b8569aa2252cb8509ee29dfd5243fa887f5c50fa66e74c717b6c5e2973958a`, and the
prospective `0x101b` transaction SHA-256 was
`3f6cfeb6b660b6f84ae0beff0b423826bce63db2280e87ee626521eb2cbb7337`.

## Execution and independent read-back

After exact revalidation, the isolated runner issued exactly one `0x101b`
transaction. It accepted only the explicit integer completion `0x0000`; no
retry was attempted. The post-operation backup was complete and independently
verified:

| Binding | Result |
| --- | --- |
| post backup objects | 8 |
| post model | 2,075,256 bytes; 394 records; 331 reachable paths |
| post backup manifest SHA-256 | `8915be2b3dd1ae12ee523a15f1f8381f68a76af110713dcdfb7de21089826103` |
| post dynamic blob SHA-256 | `c3b8569aa2252cb8509ee29dfd5243fa887f5c50fa66e74c717b6c5e2973958a` |
| sender calls | 1 |
| completion | explicit integer `0x0000` |
| automatic retry | false |

The post-state contains the exact folder and ordered TXT → BMP → TXT children.
The independent verifier confirms exact payloads and validated native prefixes,
shared payload and timestamp preservation, fixed-state equality, no removed
paths, and unchanged unrelated objects. Existing `_01` child records remain
read (`0x20`); the new `_02` records carry the reviewed new-record state and
the explicit modern timestamp policy `0x6a942500`.

## Display-history preservation

The authoritative fresh `0x001b` response had SHA-256
`9a21d818b11939a1b640c264fe26b69d8ee907104e5c895bfbea9ed40a2dfeac`; the four
other fixed-state responses were the supported all-zero value with SHA-256
`f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b`.

The exact semantic rebase preserved count, headers, tail, order, and same-path
record resolution while shifting the three active references by `0x140`:

| Before relative | Candidate relative | Resolved preserved path |
| ---: | ---: | --- |
| `0x0400` | `0x0540` | `_01\01-introduction` |
| `0x0440` | `0x0580` | `_01\02-page-01` |
| `0x0480` | `0x05c0` | `_01\03-ending` |

The candidate/post `0x001b` SHA-256 is
`88ce42e5f4072c0db09a3df9d1c78a7f024899f4cc31c896c5467ec6ba7fa38a`; the
post `0x001c`–`0x001f` responses remain the exact all-zero state. Native
numeric completion decoding and operation-specific capacity semantics remain
unresolved observations; they were not normalized into the result.

## Evidence preservation

Raw and derived evidence remains outside Git under:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-16-p16-003b-modern-mixed-txt-bmp-20260831-01/`

The versioned `preservation-manifest-v3.json` covers 65 files and verifies with
zero hash or size mismatches. The initial fresh capture, re-verification copy,
preflight artifacts, authorization, transaction audit, post-operation backup,
independent read-back result, and final summary are preserved. No raw evidence
was added to the repository.

## Evidence classification and disposition

### Verified

- exact device identity, fresh capacity response, fresh complete backup, and
  target absence at preflight;
- exact source hashes/order, template, candidate, transaction, seal, and
  timestamp policy revalidation;
- one transaction with explicit `0x0000` and no retry;
- exact post-operation folder, ordered children, payloads, prefixes, read flags,
  semantic display-history rebase, zero fixed-state objects, and unrelated-data
  preservation; and
- complete post-backup and independent read-back verification.

### Observed

- the host-side initial timestamp-reference rejection and subsequent
  non-overwriting re-verification of the already captured archive; and
- the physical operation's device identity, capacity response, transaction
  completion, and post-operation backup contents.

### Inferred

- compatibility of this exact modern mixed package and fresh display-history
  state with the tested device under the reviewed constrained runner.

### Unresolved

- native numeric interpretation of the completion response;
- operation-specific capacity-response semantics beyond this observed value;
- interrupted-write atomicity/recovery; and
- arbitrary display-history, BMP, nested, batch, or broader transfer behavior.

P16-003B is **COMPLETE** only for this exact approved flat
TXT/BMP/TXT operation. Normal GUI/CLI transfer remains disabled, and any
future device-changing operation requires a separately briefed task, fresh
preflight, and new exact owner approval.
