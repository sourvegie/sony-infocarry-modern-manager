# P17-008 — verified raw backup-state identity correction

Date: 2026-09-01
Baseline: canonical `main` after PR #14, commit `a79ceca`
Risk: **R3 — device-state authorization boundary**
Disposition: **READY_FOR_HARDWARE_TEST — host-only; stop before hardware**

## Decision and scope

P17-007 stopped fail-closed before sender construction because P17-005
compared the entire `VerifiedBackup` archive identity. The sealed preflight and
the independently captured fresh pre-write backup contained the same Sony
identity, eight raw objects, dynamic blob, and fixed-state data, while their
capture-generated manifest/object timestamps and archive locations differed.
P17-008 implements the approved distinction between immutable raw device state
and acquisition provenance. It does not alter P17-007 evidence, normalize an
archive, access USB, invoke a sender, or reuse its approval phrases.

The correction remains limited to the existing P17-005 one-selected-Library-
item, flat TXT/BMP/TXT, additive future operation. Normal GUI/CLI transfer is
still disconnected, and this task makes no physical compatibility claim.

## Canonical state identity

`src/infocarry/backup_state_identity.py` defines the frozen
`BackupStateIdentity` and `BackupObjectStateIdentity` records. Derivation first
re-runs the existing `verify_fresh_backup` complete/integrity verifier, then
rejects anything outside the canonical eight-object backup shape:

| Included in raw-state equality | Bound rule |
| --- | --- |
| device identity | exact Sony vendor/product identity from the verified manifest |
| protocol identity | exact current direction, command-header, and reviewed source values |
| ordered objects | exactly six fixed responses, the `0x8004` probe, then the `0x8004` dynamic blob |
| object identity | sequence, key/role, command, expected filename semantics, requested/received length, and SHA-256 |
| dynamic model | dynamic blob length and SHA-256 |
| fixed state | SHA-256 for responses `0x001b` through `0x001f` |

The object order, role, command, filename spelling/semantics, length, and
hashes are all checked. A missing, extra, reordered, malformed, or changed
object fails closed. The compact filename spelling retained by older portable
synthetic fixtures is accepted only when its sequence semantics are valid;
arbitrary filename forms are rejected. Production command-bearing filenames
are bound exactly.

The following remain preserved and visible but are excluded from state
equality because they describe acquisition rather than the device contents:

- archive directory/path;
- whole `manifest.json` SHA-256;
- manifest `created_at_utc` and `updated_at_utc`;
- per-object `received_at_utc`; and
- process-side `verified_at_utc`.

No bytes are rewritten and no provenance difference is discarded. The full
backup reports retain their original manifest hashes/timestamps, and
`BackupStateComparison.to_dict()` reports raw-state equality, identity hashes,
material identity differences, and every excluded provenance difference in a
deterministic JSON shape.

## Adapter reconciliation

The isolated P17-005 adapter now uses `derive_backup_state_identity()` for the
sealed baseline and the additional fresh pre-write backup, after each archive
has passed complete/integrity verification. It still requires:

1. exact candidate bytes;
2. exact prospective transaction bytes and hash;
3. exact candidate bindings apart from the fresh archive manifest hash;
4. exact non-provenance Library/package, source, template, capacity,
   fixed/display-history, timestamp, destination, and expected-post-state
   bindings;
5. a newly built fresh-backup authorization; and
6. the existing one-shot sender, explicit `0x0000`, no-retry, and independent
   post-operation read-back gates.

The sole candidate/authorization comparison exception is the baseline
manifest hash, which is acquisition provenance. Full before/after backup
reports remain bound to the evidence manifest, and the result audit now
includes `backup_state_comparison` so provenance changes are explicit rather
than silently ignored.

## Evidence classification

### Verified

- P17-007’s external failure evidence is complete and remains immutable at
  `/Users/stardust/Projects/InfoCarry-Evidence/phase-17-p17-007-library-package-live-smoke-20260901-01/`.
- P17-007 proved the relevant fresh archives have equal raw objects and
  capture-generated provenance differences; its sender call count remained
  zero.
- The new identity re-verifies a complete archive and rejects material device,
  protocol, object-set, role, command, filename-semantics, length, raw-hash,
  dynamic, and fixed-state changes.
- The adapter’s fake-host success path accepts equal raw state with different
  archive path/timestamps, retains exact candidate/transaction equality, and
  preserves the complete backup/provenance audit.
- Focused and complete portable tests pass; normal CLI/GUI import isolation
  remains intact.

### Observed

- The P17-007 preserved comparison records the actual differing archive paths,
  manifest hash, and capture timestamps. Those differences are not replayed or
  rewritten by this task.

### Inferred

- The P17-007 manifest differences are capture provenance because the verified
  raw object set and hashes are equal. This inference is now represented by an
  explicit, reviewable identity/comparison policy rather than by normalization.

### Unresolved

- Native numeric completion decoding and operation-specific capacity response
  semantics remain unresolved, as recorded by prior tasks.
- No physical compatibility, persistence, or read-back result is established
  for a future P17-005 operation.
- Bus/address remains acquisition provenance; no serial identity is invented.
- Broader profiles, overwrite/delete/restore/synchronization, retry, nesting,
  batching, and normal product transfer remain out of scope.

## Validation boundary

The implementation was exercised only with injected fake backup/transport
boundaries. No USB device was detected, queried, backed up, written, or read
back by P17-008. Raw external evidence and source artifacts were not modified.

The final host-only checkpoint is **READY_FOR_HARDWARE_TEST**. A later task
must perform a new fresh read-only preflight and obtain new operation-specific
approval before any device-changing operation.
