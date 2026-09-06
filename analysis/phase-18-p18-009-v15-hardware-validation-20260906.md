# P18-009 — Owner-approved VNW-V15 physical validation

Date: 2026-09-06  
Base: `c5877a53988f603f765f5c89acbacf624bcd5d67`  
Branch: `task/P18-009-v15-hardware-validation`  
Outcome: **BLOCKED_BY_EXTERNAL_EVIDENCE**

## Authorization and scope

The owner explicitly authorized exactly one bounded physical validation of the
reviewed `sony-vnw-v15-reviewed-v1` path for one new absent root with exactly
three ordered children: TXT → BMP → TXT. The expected session identity was
`0x054c:0x001e`. This record does not authorize a second attempt, a broader
shape, VNW-V10, recovery, interruption, or standing Experimental exposure.

The branch was created directly from canonical P18-008 commit
`c5877a53988f603f765f5c89acbacf624bcd5d67`. No production-code change was
made.

## Host preconditions

- Focused durable-claim, guarded-transfer, persistent-lock, exact-profile, and
  capacity checks: 94 passed.
- Full portable suite: 746 passed, 3 intentional evidence-dependent skips.
- Python 3.12 compilation: passed.
- `git diff --check`: passed.
- Real installation-stable SQLite claim-store schema: validated.
- Active sender marker: none.
- Installation-wide indeterminate-write lock: absent/inactive.

## Physical disposition

Read-only USB enumeration returned no matching Sony InfoCarry device. The task
therefore stopped before all device/session-dependent gates. No interface was
claimed; no `0x0019` capacity response or complete backup was captured; no
destination conflict, auxiliary-state, candidate, transaction, or hash-only
runtime review was performed; no runtime confirmation was accepted; and no
durable claim or sender-in-flight marker was consumed or created.

Sender calls: 0.  
`0x101b` transmission began: no.  
Completion: not applicable.  
Retry: 0 / false.  
Post-write backup: not applicable.  
Independent semantic read-back: not applicable.  
Human physical acceptance: not applicable.

No incident or indeterminate lock was created. The claim store remains
unconsumed with no sender marker, and the global lock remains inactive. Raw
device evidence and private backups were not created.

## Capability boundary

This result adds no live evidence to the capability matrix. The broader flat
profile remains non-live, hierarchy remains preview-only, VNW-V10 remains
non-write-capable, and standing Experimental physical-write exposure remains
disabled.

Independent P18-009 physical-evidence review is not applicable because the
physical phase did not start; the existing P18-008 R3 review and host evidence
remain unchanged.
