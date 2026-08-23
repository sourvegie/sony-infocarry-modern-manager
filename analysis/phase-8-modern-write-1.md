# Phase 8 modern write 1 — disposable record replay

Date: 2026-08-21

This report records the first explicitly authorized modern-tool write. The
operation used the normalized offline candidate, the existing fresh-backup
write gate, and the ordinary segmented `0x101b` path only. The separate unlock
workflow (`0x101d`) was not used.

## Authorization and candidate

The user supplied the exact final confirmation phrase `WRITE INFOCARRY`.
Authorization was bound to:

```text
backup:   analysis/phase-8-live-after-4/
candidate: analysis/phase-8-candidate-3/
candidate SHA-256: d733869aa08e1aafdb790047a0b89413f0538b05eb13a5b64c4b66400f3f2491
command: 0x101b
payload length: 2,129,464 bytes
```

The candidate combines the fresh device state ranges with the accepted decoded
blob containing exactly one disposable record, `root\\IC_TEST_01.txt`.

## Live result

The sender revalidated the backup and candidate immediately before request 2,
sent the segmented transaction through bulk-OUT endpoint `0x01`, and received
completion status `0x0000`. No `0x101d` request was sent.

## Post-write verification

A new complete read-only backup was taken immediately afterward:

```text
analysis/phase-8-live-after-5/
```

Its dynamic `0x8004` object is 2,063,928 bytes with SHA-256
`c86f5523565da644995c5a2c47ca7255fe18f70b374ad1c105c44a330e26940f`, matching
both the pre-write backup and the candidate's range-5 plus range-8 blob. The
fresh backup gate passes. The device contains:

```text
root\\IC_TEST_01.txt
```

with the expected 41-byte CRLF payload and SHA-256
`85c8e82f3547ace5c72f3f2c1c3817788cd134e4e6bbf4dca9032d4ca11e4c08`.

All eight post-write backup objects are byte-identical to the corresponding
pre-write backup objects, including the four fixed state responses and the
dynamic model blob. The replay was therefore idempotent at the observed
device-state level and did not create a duplicate or alter surrounding data.

## Milestone status

The guarded modern sender has now been exercised successfully on one known,
disposable, already accepted state. This validates the segmented transport,
completion handling, backup-bound authorization, and post-write read-back.
The sender remains intentionally outside the normal CLI; future writes should
repeat the same fresh-backup and explicit-confirmation gate.
