# P18-011 — VNW-V15 physical validation

Date: 2026-09-06  
Repository: `sourvegie/sony-infocarry-modern-manager`  
Canonical base: `1c16d48856328de53171a13f8e5665da0a46e47a`  
Branch: `task/P18-011-v15-physical-validation`  
Risk: R3 physical validation  
Outcome: **BLOCKED_BY_EXTERNAL_EVIDENCE**

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
no production code was changed.

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

Fresh read-only inspection of the installation-owned state found:

- persistent execution-claim SQLite schema: valid, integrity check `ok`;
- committed execution claims: `0`;
- sender-in-flight markers: `0`;
- global indeterminate-write lock: inactive (no lock record present).

The store and lock were inspected under the existing user application-data
location. No claim, marker, lock, or recovery state was created, consumed,
cleared, or modified by this task.

## Resumed fresh device preflight

The resumed run began with new read-only gates in the external run namespace
`/private/tmp/p18-011-run.zCOJwz`:

- `infocarry detect --json` found one device matching the exact profile
  identity: VID `0x054c`, PID `0x001e`;
- fresh descriptors confirmed active configuration 1, interface 0 alternate 0,
  bulk OUT `0x01`, bulk IN `0x82`, and 64-byte packets;
- a new native `0x0019` response was captured and parsed as a 3,145,728-byte
  capacity (`c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662`);
- a new complete eight-object backup was captured and verified: manifest
  `83a9e6b111e195a50b78ce7fafe31a10390490077308bd402581a52be28ee38b`, dynamic
  blob `4d17326ef236015321bbad71e5ebde837c12f928c98b59cc4f4d0c34751f4ea9`
  (2,091,292 bytes), and state identity
  `a6ea8922c0a1fa3231b04cbcf5de9791acf7536329b4eaf8d65a64352cacf9b9`;
- the fresh baseline contained 399 records / 335 paths, the exact target was
  absent, seven display-history entries and one bookmark group were valid for
  the reviewed semantic-preservation policy, and `0x001c`–`0x001e` were
  zero-count.

The required full adapter preflight then re-ran its first detection callback,
but the device was no longer enumerable. A follow-up `detect --json` also
returned an empty list. The adapter therefore stopped before its authoritative
fresh capacity/backup callback sequence could complete and before candidate
construction. No sender was created and no device-changing operation was
attempted.

### Further fresh restart

At the user's request, a new run namespace
`/private/tmp/p18-011-resume.8lrxpY` was created and the authoritative gates
were restarted at detection. Both the initial `infocarry detect --json` and a
single two-second read-only reconnect recheck returned an empty device list.
No descriptor, capacity, backup, package, candidate, or derived identity from
the earlier run was reused. This restart stopped at the first gate.

## Transaction and physical result

No current P18-011 candidate, transaction, preflight seal, authorization
binding, or operation-bundle hash was produced because the device disappeared
before the complete adapter preflight could reach candidate construction. The
prior P18-010 offline hashes were not reused as current physical evidence.

| Gate | Result |
| --- | --- |
| Fresh VNW-V15 identity/profile | Prior run passed initially; current fresh restart absent at detection |
| Fresh native `0x0019` capacity | Passed; 3,145,728 bytes |
| Fresh complete pre-write backup | Passed; eight objects, integrity verified |
| Destination absence | Passed against the fresh 335-path baseline |
| Fresh `0x001b`–`0x001f` state | Passed reviewed class; `0x001b`/`0x001f` semantic-preservation inputs, `0x001c`–`0x001e` zero-count |
| Runtime confirmation | Not presented or accepted |
| Durable execution claim | Not consumed |
| Sender-in-flight marker | Not committed |
| Sender invocations | `0` |
| `0x101b` transmissions | `0` |
| Completion type/value | Not applicable |
| Post-write backup/read-back | Not applicable |
| Human screen acceptance | Not applicable |
| Global lock after attempt | Inactive |

This attempt therefore stopped before any transaction began. No retry,
overwrite, deletion, alternate destination, corrective write, or capability
expansion occurred. No raw device evidence or private backup was added to Git.

## Review disposition

The latest fresh restart remains blocked at detection. The previously completed independent P18-010 host-side R3 review remains the
review basis for the unchanged implementation. The P18-011 post-physical
evidence review is **not applicable/pending** because the external device
was not enumerable at the current first gate. A new operation-specific
physical attempt would require the device to remain enumerable through the
fresh adapter gates; this run authorized no transaction.

`CAPABILITY_MATRIX.md` is unchanged. The fixed TXT → BMP → TXT operation has
not gained new physical evidence, and standing Experimental exposure remains
disabled.
