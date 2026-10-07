# P18-041H2 — Reconnect-safe fixture-placement owner authorization

Date: 2026-10-07 (Asia/Tokyo)

Branch: `task/P18-041H2-reconnect-safe-owner-state`

Disposition: **FIXTURE PLACEMENT READY_FOR_HARDWARE_TEST — RECONNECT-SAFE OWNER AUTHORIZATION**

This checkpoint changes only the host-side guarded contract for the exact
P18-041G fixture placement. It performs no physical USB access, does not send
`0x101b`, consumes no claim, mutates no sender marker, and mutates no
installation-wide indeterminate-write lock. All physical-operation counters
remain zero.

## Frozen operation

The only admitted operation is one direct-root ordinary TXT addition on the
reviewed Sony VNW-V15 boundary:

- target: `root\\IC_P18_041G_CLOCK_01.txt`;
- payload: `P18-041G timestamp probe 01\\r\\n`;
- length: 29 bytes;
- SHA-256: `9541c1b9d09ee7d4ab91c704755c4bea8b2022c3bb8f50aa15c1a990bf80c35d`;
- target absent in the fresh complete baseline;
- no overwrite, replacement, rename, second addition, or removal;
- exactly one `0x101b`, no retry, native `0x0000`, complete post-backup, and
  independent exact readback.

The existing P18-039/P18-040 claim, sender-marker, global-lock, and post-write
verification machinery is reused. `OwnerAuthorizedOperationIdentity` binds the
sealed operation bundle, VNW-V15 boundary, baseline state identity, capacity,
candidate, transaction, and authorization. The USB handle is not part of the
owner fingerprint.

## Reconnect contract

The operation runtime token identifies the frozen in-memory operation runtime,
not a physical USB handle or a separate hardware serial number. A disconnected
or closed read session may be re-established after approval. The execution
revalidation boundary explicitly closes and rediscover/reopens the read session
first, because PyUSB can leave a physically unplugged session object appearing
open. That reconnect establishes one execution generation; baseline, capacity,
equivalence, and sender arming must all use it, and a later session change fails
closed rather than silently adopting a second reconnect.

Immediately before the durable claim and sender boundary, the runner performs a
read-only execution-equivalence check. It verifies the VNW-V15 identity, reads
current capacity and a complete current baseline, compares the current backup
identity and capacity with the sealed values, verifies the target is still
absent through the exact baseline identity, re-verifies the frozen candidate and
preserved transaction hashes, and inspects the persistent claim/marker/lock
state without mutation. The sender is armed only after this check. A mismatch
stops before claim and sender; it cannot regenerate the candidate, rebind the
transaction, adopt a new preflight, mint a new fingerprint, or silently repair
state. Wall-clock age alone does not invalidate the approval when state
equivalence holds.

The mutable `assert_execution_boundary_available()` call remains immediately
before claim consumption, preserving the existing durable marker reconciliation
and installation-wide lock behavior. After claim, the established sender
lifecycle remains one-shot: one sender, one `0x101b`, zero retry after start or
ambiguity, native `0x0000`, complete post-backup/readback, independent
verification, terminal marker resolution, and the canonical H1 placement report
at `01-fixture-prestage/placement-readback-or-backup-report.json`.

## Validation

Focused H2 tests cover exact admission, changed name/payload/nested/model,
target-present, stale backup/state, stale approval, candidate regeneration,
transaction rebinding, claim/sender non-mutation on mismatch, elapsed-time-only
non-invalidation, identical-state reconnect success, changed-state reconnect
failure, one-shot fake success, nonzero completion, disconnect, and post-readback
failure. The focused H2 suite passes 17 root-placement tests and 7 runtime-provider tests.

The portable suite passes 1,074 tests with 3 established intentional skips:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  /external/local-path \
  -m unittest discover -s tests -v

Ran 1074 tests in 110.377s
OK (skipped=3)
```

`git diff --check` passes. No hardware write was attempted.
