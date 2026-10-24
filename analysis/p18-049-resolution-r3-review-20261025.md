# P18-049 provenance resolution — independent R3 review

Reviewed exact source: `51d6b75166a164c2fba707506fbeb3d2164f37d2`.
Compared with owner checkpoint: `4ba16dca6edafd0bfe8d4721b9e1ed4ee6fca358`.
Review date: 2026-10-25, Asia/Tokyo.

## Code and preserved-evidence conclusion

Code/evidence review: PASS, P0/P1/P2 = 0/0/0. This is an offline readiness review, not device-change approval or physical Delete success. Final fresh read-only staging/envelope and future executor review also PASS below. No reviewer USB access, production safety-state mutation, physical write, repository source edit, push or merge occurred.

The provenance inconsistency is real. The sources are distinct records/files: native identity, paths/parents, content pointers, lengths (53 and 8,850 bytes), payloads and timestamps differ. The original sealed preparation's candidate-audit digest matches reconstruction with `0x7180`, and rejects `0x1c0`; actual placement also used `0x7180`. Therefore the conflict predates execution, and is an envelope-versus-prepared-operation failure. Identical final bytes do not repair the original authorization contract.

I inspected and independently reran the forensic manual reconstruction against immutable original evidence in a separate reviewer directory. Four combinations (two baseline archives by two source records) reproduce every candidate byte and all eight transaction ranges. The inspected production allocator overwrites the differing source pointer, length, timestamp and full name field; only matching flag/extension, opaque/selector and native prefix survive. Original source payloads/padding are not copied into the new allocation. The independent nested inverse model and protected-state transformation restore the original dynamic blob and all five fixed state blocks. No template-induced structural or protected-state difference remains unexplained for this exact recorded operation. Physical restoration of the two native derived responses is not claimed; the new canonical all-eight post-readback gate must establish it.

I rehashed all 103 preserved original evidence files against `immutable-evidence-before.json`; none changed. Original envelope, original approval, execution and STOP disposition remain unchanged. The separate resolution record explicitly preserves `FAIL_PRESERVED` and `original_authority_reused=false`.

## Reviewed controls

- Shared nested selector preserves the guarded facade's original reachable-path traversal; both preparer and facade now choose the same source. Full offset/path/raw-record/payload/prefix/copied-field provenance is checked independently of candidate/transaction equality. The regression recreates distinct sources with identical candidate bytes and refuses identity drift.
- Deletion-only preparation accepts the trusted original envelope/result identities, verifies complete preserved placement and restoration archives, requires all eight fresh current objects equal actual verified placement, validates exact existing target offset/profile/payload, and derives the same existing-target Delete transaction. It performs no placement or send.
- Restoration hashes are an immutable sealed component of the existing Delete bundle. Preflight validates predicted dynamic/five protected objects against restoration. Canonical readback compares all eight verified native object hashes before terminal success/marker resolution. A mismatch in `0x0024` or probe remains a failed write verification with claim consumed, sender marker unresolved and existing global fail-safe lock.
- Existing Device Library service requires exact one-write task binding before owner acceptance for restoration profile. Target, record/profile/payload identity, parent, capacity, candidate/transaction, baseline raw-state identity/all eight hashes, restoration hashes, maximum one sender, no retry and no extra writes are compared to the sealed operation.
- Normal root TXT/BMP behavior takes the default no-restoration path. General nested Delete remains unavailable; the exact named fixture profile remains explicit opt-in. VNW-V10, other targets and generalized nested sender stay closed. No new sender, lock, persistence or recovery pipeline was introduced.
- Existing native integer-zero completion, fresh pre/post backup, reconnect raw-state equivalence, durable claim, sender marker, no-retry and confirmation architecture remains in use.

## Independent validation

- Inspected exact six-file diff, relevant safety/capability/process documents, source allocator, nested inverse builder/verifier, canonical writer's verification-before-terminal ordering and relevant regression tests.
- Forensic exported source: 121 Python files independently compared byte-for-byte to Git checkpoint `4ba16dca6edafd0bfe8d4721b9e1ed4ee6fca358`; PASS.
- Reviewer forensic reconstruction: PASS, four variants/eight ranges; details `/private/tmp/p18-049-resolution-r3-forensics-20261025-01/`.
- Reviewer focused regression run: PASS, 106 tests in 106.091 seconds, `/private/tmp/p18-049-resolution-r3-tests.log` (new provenance/deletion-only, nested execution/placement/preparation, Device Library UI, root TXT admission/execution, disposable BMP and ordinary BMP promotion).
- `git diff --check 4ba16dc..51d6b75`: PASS. Reviewed tree clean at inspection.
- Inspected executor full portable log `/private/tmp/p18-049-resolution-full.log`: PASS, 1,281 tests in 275.138 seconds, five established skips; no test errors/failures.

## Final fresh read-only staging/envelope

Final stage: PASS, P0/P1/P2 = 0/0/0. This review grants no hardware authority.

Frozen new deletion-only envelope: `0fbc9a8216bd383b9b86e7f1632fdd8ebc0d3025a4620bdbdbece2fd76d556e1`.

I independently read/hashed the fresh staging artifacts, verified complete captured archive manifests/objects, reconstructed exact target Delete at `0x880`, compared all candidate/transaction bytes with the preserved frozen task, and ran the independent nested inverse verifier against the original complete baseline. Current all-eight native hashes match actual successful placement. Restoration all-eight native hashes match the original pre-placement envelope. Target raw record, unread state, prefix and exact 34-byte fixture hashes match; parent is `0x700`. Candidate dynamic hash is `6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`; transaction is `e5831e0e363cab494c3f4aa859763808fa5a7676b01c6fd4ddb15edd4d58c452`.

The newly staged bundle seal includes exact all-eight restoration hashes. Staging recorded no owner acceptance or sender invocation. Safety before/after snapshots agree: 25 existing claims, no sender markers and unchanged cleared global lock. Rehash of all 103 original evidence files still passes. No owner approval or final-delete attempt record exists.

I inspected the future unexecuted opt-in executor `/private/tmp/p18-049-final-delete-executor.py`, SHA-256 `f91a115782e223c19836e24f95d47fd4dd836b46612fcf86acef6bb5c60fe0f2`. It requires explicit write opt-in, a new matching owner approval record and this independent review record, frozen envelope hash and source ancestry/code identity, unchanged immutable evidence and application safety state. It creates a non-resumable attempt directory before fresh prepare; binds the fresh operation to the frozen one-write task before owner acceptance; invokes the canonical sender once; requires native integer zero, verified terminal marker, canonical all-eight restoration and independent reconciliation; and has no retry, placement, recovery or extra-write path. I compiled its source without executing it. The owner approval record was not created.

Inspected package/signature log and isolated frozen GUI/Tk runtime report: PASS; physical counters all zero. Independent executor review record is separately preserved in the new staging directory. New owner approval remains required; the original stopped experiment's unused second write is not reused.
