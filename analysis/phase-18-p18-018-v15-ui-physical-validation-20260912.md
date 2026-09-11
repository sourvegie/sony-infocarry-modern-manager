# P18-018 — VNW-V15 UI-Driven Physical Validation

Date: 2026-09-12
Repository: `sourvegie/sony-infocarry-modern-manager`
Canonical base: `0338a7ddce3757bd5e273c2d644ef3bbbd1c0341`
Branch: `task/P18-018-v15-ui-physical-validation`
Risk: **R3 physical validation**

## Owner authorization

The owner explicitly authorized exactly one bounded physical validation with:

`APPROVE P18-018 V15 UI PHYSICAL VALIDATION 01`

This authorization permits one VNW-V15 device-changing transaction only after every fresh pre-write gate below passes. It does not authorize overwrite, delete, retry, restore, V10, broader package shapes, a second transaction, or reuse of a consumed historical operation.

The runtime transaction confirmation remains separate and must not be accepted before the final send gate:

`ADD IC_P18_LIBRARY_20260910_01 ONCE`

## Exact operation boundary

Device/model:
- Sony InfoCarry VNW-V15 only
- exact reviewed VID/PID `0x054c:0x001e`
- VNW-V10 remains `UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED`

Exact target:

`IC_P18_LIBRARY_20260910_01`

Exact package:

```text
IC_P18_LIBRARY_20260910_01/
├── 01-introduction.txt
├── 02-page-01.bmp
└── 03-ending.txt
```

Authoritative child order: **TXT → BMP → TXT**.

No overwrite, merge, delete, nesting, second package, automatic grouping, batch, alternate target, restore, corrective write, or capability expansion is authorized.

Maximum live activity:
- logical transactions: 1
- sender invocations: 1
- `0x101b` transmissions: 1
- retries: 0

## Fresh pre-write gates

All execution evidence must be freshly acquired/rebuilt in the proven host-visible USB environment. Historical P18-015/P18-017 hashes are reference/regression evidence only.

Before runtime confirmation, claim consumption, sender marker creation, or any device-changing request, require all of the following:

1. Exact VNW-V15 detected by the canonical filtered detector.
2. Host-visible USB context; do not treat the restricted managed sandbox as authoritative for USB presence.
3. Fresh native `0x0019` capacity response captured and validated.
4. Fresh complete eight-object pre-write backup captured.
5. Backup integrity/model binding validated.
6. Global installation-wide indeterminate-write lock is `cleared`.
7. No active sender marker exists.
8. Claim-store integrity is valid.
9. Historical P18-011 and P18-015 consumed claims remain historical/consumed and are not reused.
10. No P18-018 claim exists or has been consumed.
11. Exact target `root/IC_P18_LIBRARY_20260910_01` is absent.
12. Exact package is rebuilt from the selected prepared Library item.
13. Candidate is rebuilt from fresh device state.
14. Exact TXT → BMP → TXT order/payloads are validated.
15. Capacity is sufficient under the canonical candidate/transaction sizing rules.
16. Reviewed auxiliary-state policy is valid.
17. Fresh operation identity/bundle/authorization/preflight seal are rebuilt and mutually consistent.
18. P18-015/P18-017 stale identities, seals, claims, candidates, transactions, confirmations, or result manifests cannot validate the P18-018 attempt.
19. Normal ttk UI review shows the exact operation and no unsupported capability.
20. Final pre-send revalidation passes immediately before confirmation/claim consumption.

If the target is present, any supported-state assumption fails, capacity is insufficient, the lock/marker/claim state is unsafe, or any identity mismatch exists: stop before write. Do not auto-select another target.

## Auxiliary-state policy

Preserve exactly:

`verified_display_history_0x001b_and_bookmark_0x001f_semantic_rebase_plus_zero_count_0x001c_to_0x001e`

Require:
- all established `0x001b` logical paths preserved;
- established `0x001f` bookmark logical path preserved;
- four opaque bookmark dwords byte-exact;
- unused bookmark tail byte-exact;
- `0x001c`–`0x001e` zero-count;
- malformed/dangling/unaligned/inconsistent/unsupported state fails closed.

## Device-changing boundary

Only after every fresh pre-write gate passes, the normal UI may present the exact runtime confirmation:

`ADD IC_P18_LIBRARY_20260910_01 ONCE`

Require explicit acceptance at that final gate. Only then may the canonical guarded lifecycle:

1. consume exactly one new P18-018 durable execution claim;
2. establish the sender marker through the existing API;
3. enter the existing sender once;
4. transmit at most one `0x101b` operation;
5. never automatically retry.

No second click/replay may reuse a consumed operation.

## Terminal success

Native sender completion must pass the exact integer `0x0000` gate. Then require:

1. complete post-write backup;
2. independent terminal verifier;
3. post dynamic blob equals the freshly sealed candidate;
4. exact target present;
5. exact TXT → BMP → TXT order and payloads;
6. all baseline shared paths/payloads/timestamps preserved;
7. reviewed auxiliary-state semantics preserved;
8. unrelated/unknown state preserved except reviewed relocation effects;
9. durable result manifest written by the canonical path;
10. claim/marker/lock closure is correct.

Only after all ten conditions may the UI/product report `Transfer verified` or equivalent terminal success.

Do not reconstruct or synthesize a missing result manifest.

## Indeterminate handling

If sender start may have occurred but terminal success cannot be independently established for any reason (timeout, disconnect, malformed/nonzero ambiguity, missing post-backup, failed read-back/reconciliation, missing durable result, or equivalent):

- no retry;
- no second transaction;
- persist/retain the installation-wide indeterminate-write lock according to the canonical API;
- preserve the sender marker according to the canonical lifecycle;
- surface `ESCALATION_REQUIRED`;
- stop for read-only diagnosis.

## Validation and evidence

Before the physical attempt, rerun the relevant focused safety/UI/facade/coordinator/adapter/claim/lock/verifier suites and the full portable Python 3.12 suite, plus Python compilation and `git diff --check`.

After the attempt, capture and report at minimum:
- observed VID/PID and bus/address;
- host Python/PyUSB/libusb environment;
- fresh capacity size and response SHA-256;
- pre-write backup manifest SHA-256;
- pre-write dynamic blob/state identity;
- fresh package/candidate/transaction identities;
- operation/bundle/preflight identities;
- runtime confirmation accepted/not accepted;
- P18-018 claim ID/state;
- sender call count;
- `0x101b` count;
- native sender return;
- post-write backup manifest SHA-256;
- durable result manifest SHA-256 if produced;
- terminal verifier result;
- target/order/payload result;
- auxiliary-state result;
- unrelated-state preservation result;
- final lock/marker/claim state;
- focused/full tests, CI, and independent R3 disposition.

Raw/private evidence remains outside Git. Commit only sanitized durable conclusions.

## Exit

Possible final outcomes:
- `COMPLETE` only if terminal read-back and durable result are independently verified and final review passes;
- `BLOCKED_BY_EXTERNAL_EVIDENCE` if stopped safely before any device-changing operation for an external/host visibility reason;
- `ESCALATION_REQUIRED` for any indeterminate started operation or unresolved material safety/review issue.

Do not merge automatically.