# Phase 8 — Explicit Model-Range Composition and Write Safety Gate

Date: 2026-08-21

## Scope

This milestone advances the two safe prerequisites for a future writer without
adding a device-write transport. The work is entirely offline and covered by
the regression suite.

## Explicit model-range composition

`src/infocarry/model_range.py` implements the bounded grammar recovered from
the legacy recursive append helper:

1. serialize the fixed legacy prefix with `serialize_legacy_prefix()`;
2. append caller-supplied variable node bytes;
3. fill to a four-byte boundary with `0xff`;
4. recurse through children, then the optional sibling.

`ExplicitModelNode` requires the legacy internal object and exact variable
bytes as inputs. It applies the observed flag gate and prefix-length selector,
but does not construct those objects from `VICDATA.bin`, assign unresolved
field meanings, or guess path/text length adjustments. A flagged node is
skipped together with its descendants rather than silently inventing a tree
policy.

`build_offline_payload(..., model_nodes=...)` now feeds an explicit node forest
into range 8. The existing `range8=<bytes>` path remains available for native
capture reproduction. Both paths produce only a
`ProspectiveWriteTransaction`; neither opens USB or exposes a write command.

This is a structured candidate generator, not completion of arbitrary
manager-content generation. The remaining blocker is source-node construction
from an independent manager-produced content tree.

## Fresh-backup and confirmation gate

`src/infocarry/write_gate.py` adds two offline-only layers:

- `verify_fresh_backup()` checks the complete-backup state, verified device
  identity, timestamp freshness (24 hours by default), every listed object's
  length and SHA-256, and the dynamic blob's structural parser validation.
- `authorize_write_session()` requires the explicit write flag and the exact
  phrase `WRITE INFOCARRY`, then binds the resulting authorization to the
  backup manifest/blob hashes and prospective transaction hash.

`WriteAuthorization.revalidate()` must be called immediately before any
future transmission. It rejects a changed backup or candidate and rechecks
freshness. `interactive_confirmation()` supplies the deterministic prompt
boundary for a CLI or GUI.

The gate itself records `usb_transmission_performed: false`. A separate
`AuthorizedWriteSender` now implements the ordinary segmented `0x101b` path
and a `PyUsbWriteBackend` is available only when deliberately constructed;
neither is imported by the normal CLI. The sender revalidates the gate before
request 2, polls request 3 before each chunk, and makes a best-effort request-4
query after failures. The first device-changing experiment remains a separate
user checkpoint after a genuinely disposable candidate is prepared.

The `capture-artifact` CLI command extracts a selected ordinary `0x101b`
transaction from a native `.usblog`, re-composes it through the verified fixed
serializers, and writes a new hash-checked artifact directory. The original
capture is never changed. The artifact loader re-verifies every range before a
caller can pass it to the sender.

## Verification

The complete suite now contains 153 tests, including explicit model-node
ordering/alignment checks, backup tamper/freshness checks, confirmation
rejection, and post-authorization revalidation. No device operation was
performed.
