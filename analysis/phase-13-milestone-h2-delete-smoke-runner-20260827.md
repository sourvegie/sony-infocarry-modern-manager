# H.2 isolated modern-delete smoke runner — implementation checkpoint

Date: 2026-08-27

## Status

The isolated support runner is implemented in `src/infocarry/delete_smoke.py`.
This is an offline implementation checkpoint only. No device was detected,
backed up, or changed while preparing this slice.

The runner is not imported by the normal CLI or ttk application. It has no USB
discovery path of its own. A future owner-reviewed caller would have to inject
the existing one-shot sender and read-only callbacks explicitly.

## Read-only preflight boundary

`list_eligible_delete_targets()` accepts only a verified complete backup and
lists reachable root-level ordinary TXT leaves. It does not select a target.
`build_delete_smoke_preflight()` then binds the exact owner-selected path and
record offset to the existing generalized deletion candidate. The preflight
records, without embedding candidate bytes or payload contents:

- device identity, including optional detector bus/address fields;
- backup manifest and dynamic-model hashes, model length, and record count;
- target path, absolute and metadata-relative offsets, type, read state, prefix
  hash, payload length/hash, and root parent identity;
- candidate model/hash, record count, path delta, and complete transaction
  hash, length, and range lengths;
- fixed-state before/after hashes and the supported clearing classification;
- metadata/content capacity effect and the provisional timestamp policy;
- exact confirmation phrase, no-retry policy, and
  `live_transaction_performed: false`.

`seal_delete_smoke_preflight()` writes one canonical JSON artifact using
exclusive creation. `verify_sealed_delete_smoke_preflight()` verifies both the
artifact digest and the inner payload seal before any execute callback is
allowed. `create_delete_smoke_session()` creates a new non-overwriting
external-session skeleton with separate backup, Manager, SnoopyPro, result,
and derived-report locations.

## Execute-phase safeguards

The execute function is deliberately outside the normal product surface and
was not called during this checkpoint. It requires:

- a separately sealed matching preflight;
- `APPROVE H2 MODERN DELETE SMOKE 01`;
- `DELETE ONE INFOCARRY ITEM`;
- fresh read-only identity and backup revalidation;
- exact candidate reconstruction and binding;
- one injected sender call at most;
- completion `0x0000` only;
- a complete post-operation backup and independent existing read-back
  verifier.

Pre-start cancellation is classified as safe. Sender failures and read-back
failures after the sender is called are terminal, preserve the primary error,
and are classified as indeterminate where the device outcome cannot be known.
No automatic retry path exists. This does not prove physical interrupted-write
atomicity or recovery, and it does not authorize a live transaction.

## Verification

Focused runner tests: 11 passing.

Complete suite: 483 passing, 3 intentional evidence-dependent skips.

The normal CLI/GUI exposure audit remains clean. No raw evidence, backup,
capture, timestamp log, screenshot, candidate bytes, or private absolute path
was added to the repository.

Next gate: after the implementation commit is pushed, the owner may request a
separate guided read-only device detection, fresh complete backup, and
target-specific preflight. The preflight result must be reviewed before any
separate approval for a device-changing deletion transaction.
