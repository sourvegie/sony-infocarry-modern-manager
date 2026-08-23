# Phase 8 write hardening (2026-08-21)

The first live write proved that the modern segmented `0x101b` sender can
complete an idempotent, manager-accepted candidate. This follow-up hardens
the boundary before another device-changing operation.

## Fixed-state binding

`WriteAuthorization` now binds the first two candidate ranges to the exact
fresh backup responses:

- range 1 is split into responses `0x001b` through `0x001e`;
- range 2 is response `0x001f`;
- each response is matched by SHA-256 during authorization and again during
  pre-send revalidation.

This prevents the stale three-byte range-1 state discovered in candidate 2
from passing a future write gate. The gate still verifies every raw backup
object and the decoded dynamic blob as before.

## Post-write verification

`verify_post_write_backup()` compares a fresh read-back archive with the exact
authorized transaction. It requires all five fixed responses and the dynamic
`0x8004` blob (`range 5 + range 8`) to match, while requiring all unrelated
backup objects to remain unchanged. Payload-dependent response `0x0024` and
the `0x8004` length probe are allowed to change with the candidate blob.
`AuthorizedWriteSender.send_and_verify()`
provides a single caller-facing path that sends once and then requires this
verification against a caller-provided fresh backup archive.

The verifier performs no USB operation itself; the caller must first complete
the normal read-only backup after the send. This keeps the transport sequence
explicit and makes a failed read-back visible instead of silently retrying a
write.

## Interruption and recovery tests

The test suite now injects a cable/disconnect failure after a bulk chunk and
checks that the sender:

1. does not retry the failed transfer;
2. performs one best-effort request-4 completion query; and
3. preserves the original transfer exception.

Cancellation after a successful chunk is covered by the same assertions.
No unlock (`0x101d`) or implicit recovery write is introduced.
