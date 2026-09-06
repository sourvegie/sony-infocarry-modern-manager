# P18-009 — Owner-approved VNW-V15 physical validation

Date: 2026-09-06  
Base: `c5877a53988f603f765f5c89acbacf624bcd5d67`  
Branch: `task/P18-009-v15-hardware-validation`  
Outcome: **ESCALATION_REQUIRED**

## Authorization and scope

The owner explicitly authorized exactly one bounded physical validation of the
reviewed `sony-vnw-v15-reviewed-v1` path for one new absent root with exactly
three ordered children: TXT → BMP → TXT. The expected session identity was
`0x054c:0x001e`. The prior unavailable-device checkpoint did not consume that
authorization. This resumed run used only the existing reviewed implementation
and did not request a second approval.

The branch was created directly from canonical P18-008 commit
`c5877a53988f603f765f5c89acbacf624bcd5d67`. No production code changed.

## Host and persistent preconditions

- Focused durable-claim, guarded-transfer, persistent-lock, exact-profile, and
  capacity checks: 94 passed before hardware access.
- Full portable suite before the physical phase: 746 passed, 3 intentional
  evidence-dependent skips; Python 3.12 compilation and `git diff --check`
  passed.
- Real installation-stable SQLite claim store schema: user version 1 with
  `claim_metadata`, `execution_claims`, and `sender_in_flight` tables.
- Claim rows: 0. Sender-in-flight marker: none. Global indeterminate-write
  lock: inactive/absent. No safety state was cleared.

## Fresh read-only physical evidence

Read-only enumeration and descriptor validation matched exactly:

- model/profile: Sony InfoCarry VNW-V15 / `sony-vnw-v15-reviewed-v1`;
- session identity: VID `0x054c`, PID `0x001e`;
- active reviewed transport: interface 0, alternate 0, bulk OUT `0x01`,
  bulk IN `0x82`.

Authoritative fresh native capacity evidence was captured at `0x0019`:

- response length: 64 bytes;
- big-endian capacity field: `+0x08`;
- total model capacity: `3,145,728` bytes;
- raw response SHA-256:
  `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a`.

A complete fresh pre-write backup was captured and independently verified:

- manifest SHA-256:
  `4f1119294cc51290cf67596ff07af2fc272c252c5dc7ef6a0fdc897bc3e78953`;
- dynamic backup blob SHA-256:
  `4d17326ef236015321bbad71e5ebde837c12f928c98b59cc4f4d0c34751f4ea9`;
- canonical backup-state identity SHA-256:
  `a6ea8922c0a1fa3231b04cbcf5de9791acf7536329b4eaf8d65a64352cacf9b9`;
- 8 raw objects; parsed record count 399; no orphan records;
- raw evidence root:
  `/Users/stardust/Projects/InfoCarry-Evidence/phase-18-p18-009-v15-validation-20260906-01`.

The first read-only capacity capture directory was rejected before persistence
because the harness had pre-created it. It contains no raw response and was not
used. The authoritative response above was captured into a new non-overwriting
directory (`capacity-0002`); no prior session evidence was reused.

## Stop condition and auxiliary-state disposition

The fresh backup showed that the exact required destination was already
present:

`root/IC_P17_LIBRARY_20260831_03`

Its existing children were `01-introduction`, `02-page-01`, and `03-ending`.
The reviewed candidate builder stopped with `destination path already exists`.
No overwrite, merge, deletion, rename, alternate destination, candidate
construction, transaction construction, hash-only runtime review, or runtime
confirmation occurred. The exact authorization therefore cannot be used for
this physical write without changing the operation scope.

The independent read-only fixed-state assessment also found unresolved
auxiliary state in the fresh backup:

- `0x001b`: 7 active display-history references;
- `0x001f`: 4 nonzero bookmark values;
- `0x001c`, `0x001d`, and `0x001e`: zero active entries.

The reviewed candidate policy can preserve an established display-history
shape, but this backup's nonzero bookmark state is not an established exact
physical proof for this operation. No auxiliary state was zeroed or mutated.

## Physical execution disposition

Sender calls: 0.

Sender-in-flight marker committed: no.

`0x101b` transmission began: no.

Runtime transaction-specific confirmation: not presented/accepted.

Durable execution claim: not consumed.

Completion: not applicable.

Retry: 0 / false.

Post-write backup: not applicable.

Independent semantic read-back: not applicable.

Human physical acceptance: not applicable.

No incident was created and the installation-wide indeterminate-write lock
remains inactive. The absence of a post-start ambiguity means no recovery or
lock-clearing action is authorized or required.

## Required escalation

Outcome is `ESCALATION_REQUIRED`. The minimum change required before any
future physical write would be a fresh R3 review and owner decision for a
different exact destination, together with an explicit disposition for the
observed bookmark/display-history state. This task does not choose that
destination, delete the existing folder, or retry the sender.

## Capability boundary

This result adds no live evidence to the capability matrix. Only the exact
reviewed TXT → BMP → TXT scope was evaluated read-only; broader flat shapes
remain non-live, hierarchy remains preview-only, VNW-V10 remains
non-write-capable, and standing Experimental physical-write exposure remains
disabled.

Independent R3 evidence review of a device-changing result is not applicable:
no device-changing transaction occurred. The sanitized evidence above is
available for independent review of the stop decision and fresh read-only
preconditions.
