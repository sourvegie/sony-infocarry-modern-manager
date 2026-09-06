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

## Fresh device preflight

Read-only USB enumeration found **zero** connected devices matching the exact
required session identity:

- VID: `0x054c`;
- PID: `0x001e`;
- profile: `sony-vnw-v15-reviewed-v1`.

No device session was opened and no native command was issued. Consequently,
the required fresh identity evidence, native `0x0019` 64-byte capacity
response, complete pre-write backup, fresh auxiliary-state assessment,
destination absence check, candidate construction, transaction construction,
runtime confirmation, and physical sender operation could not safely begin.

## Transaction and physical result

No current P18-011 candidate, transaction, preflight seal, authorization
binding, or operation-bundle hash was produced from fresh device evidence.
The prior P18-010 offline hashes were not reused as current physical evidence.

| Gate | Result |
| --- | --- |
| Fresh VNW-V15 identity/profile | Not obtained; device absent |
| Fresh native `0x0019` capacity | Not obtained |
| Fresh complete pre-write backup | Not attempted |
| Destination absence | Not assessed against a fresh device baseline |
| Fresh `0x001b`–`0x001f` state | Not assessed |
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

The previously completed independent P18-010 host-side R3 review remains the
review basis for the unchanged implementation. The P18-011 post-physical
evidence review is **not applicable/pending** because the external device
prerequisite was absent and no physical result exists to review. A new
operation-specific physical attempt would require fresh device availability
and a new review of the resulting evidence; this task authorizes no second
transaction.

`CAPABILITY_MATRIX.md` is unchanged. The fixed TXT → BMP → TXT operation has
not gained new physical evidence, and standing Experimental exposure remains
disabled.
