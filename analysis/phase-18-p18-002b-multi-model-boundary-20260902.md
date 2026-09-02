# P18-002B — Multi-model boundary and global lock correction

Date: 2026-09-02
Risk: R2
Status: host/offline correction in PR #27; independent R2 PASS; no hardware access authorized

## Decision

The owner declared Sony InfoCarry VNW-V10 as an intended compatibility target.
Existing evidence and code verify only VNW-V15 with observed session USB
identity `0x054c:0x001e`. The product must not infer V10's PID, descriptors,
protocol, storage format, capacity, display profile, candidate rules, or write
safety envelope from V15.

The initial capability profile is explicitly associated with
`sony-vnw-v15-reviewed-v1` and remains `defined_not_live_enabled`. VNW-V10 is
represented by `sony-vnw-v10-uncharacterized-v1` with status
`UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED`; it has no transfer, delete,
restore, candidate, authorization, or capacity capability. A future V10 task
may characterize USB identity/descriptors and only independently established
safe read commands, followed by a complete baseline and capacity relationship
when the read protocol is validated.

Each application connection is a new session. Exactly one matching device is
required for an actionable session; model validation is performed against an
explicit model profile. VID/PID and bus/address are session observations and
are not persistent physical-unit identity.

## Lock contract

The absence of a proven stable unit identifier rules out a truthful per-device
lock. `PersistentIndeterminateWriteLock` therefore stores one
installation-wide lock. An ambiguous post-start outcome blocks writes for all
models and sessions across restart and reconnect; read-only detection and
diagnostic backup remain allowed. This deliberate over-blocking is the
approved fail-safe behavior. Model keys in diagnostic evidence are validated
profile metadata and provenance only; they do not create separate lock slots.

Clearing requires an actual `DiagnosticBackupEvidence` instance with the
exact built-in-`True` `complete`, `read_only`, and `integrity_verified` flags,
the original incident and attempt identifiers, the original model-key
provenance, a complete read-only verified backup, a documented recovery
decision, and a hash-bound decision record. A matching VID/PID, reconnect, or
unrelated diagnostic evidence cannot clear the lock. Unknown keys and legacy
V15-only lock documents fail closed rather than being migrated implicitly.

## Session capacity contract

VNW-V15 has the only verified capacity interpreter: read-only `0x0019`, a
64-byte response, with the big-endian field at `+0x08` representing total
candidate-model capacity. Each fresh session must bind that response hash,
total capacity, verified baseline model length, candidate model length/growth,
remaining-growth capacity, and remaining-after-transfer margin to the host
`TransferPlan` and future authorization. The remaining-growth value is total
capacity minus the fresh baseline length; the remaining-after-transfer value
is total capacity minus the candidate length. `0x0024` and unresolved `+0x14`
semantics remain excluded.
VNW-V10 has no accepted capacity query/interpreter; no V10 capacity value may
be reused or assumed.

## Evidence classification

- **Verified:** V15's existing constrained transfer profile and capacity
  interpretation; exact-`True` diagnostic evidence validation; lock persistence
  across process instances; no automatic lock clear.
- **Observed:** owner-declared existence of a second VNW-V10 model target.
- **Inferred:** none about V10 hardware behavior or persistent unit identity.
- **Unresolved:** V10 USB identity/descriptors, protocol, storage/format,
  capacity, display behavior, write rules, and any stable physical-unit
  identifier.

## Host validation boundary

The correction is limited to model/profile metadata, session capacity binding,
the installation-wide lock contract, focused tests, and documentation. It
does not access hardware, probe V10, construct a sender, expose a GUI/CLI
write action, request approval, or transmit `0x101b`.

## Validation checkpoint

Focused model/profile, session, capacity, façade, global-lock, exact-`True`,
and Experimental-contract tests pass (51 tests). The complete portable offline
suite passes 673 tests with 3 intentional evidence-dependent skips. Compilation
to an external `PYTHONPYCACHEPREFIX`, `git diff --check`, and the
tracked/reachable history exclusion audit pass. Independent R2 review is PASS;
CI and the normal PR boundary remain open. No hardware access, approval phrase,
sender, or `0x101b` occurred.
