# UNEXECUTED OWNER PROTOCOL — constrained modern package smoke

Status: prepared for review only. This document does **not** authorize a live
transport, a device-changing command, or a hardware operation. I.6 adds the
native-capacity evidence requirement; the values below are a preserved offline
reference and must be regenerated from a fresh response and backup before any
separate approval.

## Exact operation

The only proposed operation is one additive package:

```text
root\IC_I4_PACKAGE_20260823_01\chapter.txt
```

`IC_I4_PACKAGE_20260823_01` is a new disposable root folder name distinct
from capture 7's `IC_I_FOLDER_20260823_01`. The package contains exactly one
short TXT child, no bitmap, no second child, no nested folder, no category,
mark, bookmark, selection, history, sidecar, rename, delete, or unrelated
mutation.

The source must be a new local UTF-8 TXT prepared under the strict CP932/CRLF
rules. Record its exact path and SHA-256 in the preview. Do not modify the
source after preview.

## Values that must be recorded before any separate approval

These values are produced by the offline preview from the fresh backup. A
blank field is a stop condition; do not fill one by guessing.

```text
device vendor/product: 0x054c / 0x001e
source path (offline reference): tmp/i4-live-smoke-20260823-01/chapter.txt
source SHA-256 (offline reference):
  187ba5ae05ef08f86d5f27e7de7ff445d4a32df7921d21bb9345ce158f205321
prepared package manifest SHA-256 (offline reference):
  9d2389e9aaa3f32eff361004d37bd40ecb04422a4710ef379a9c29fa0c2f8c1d
target folder: root\IC_I4_PACKAGE_20260823_01
target child: root\IC_I4_PACKAGE_20260823_01\chapter.txt
folder record offset: 0x340 (offline reference)
child record offset: 0x3c0 (offline reference)
child prepared payload SHA-256 (offline reference):
  581564dc30a425edb06a4c2216ade4eb6b707381b81267e8df9a721e722daa8a
frozen new-record timestamp (uint32 hex): 0x6a8aba6f (offline reference)
pre-operation backup directory:
  future: ${EVIDENCE_ROOT}/
    phase-12-milestone-i6-package-live-smoke-20260823-01/pre-operation-backup
  reference: tmp/i4-live-smoke-20260823-01/pre-backup-01
pre-operation manifest SHA-256 (reference):
  7c238571179430cf91b657ce1fd9f0ffaf30bd12a73acc3d2ac23cb6df611fa4
pre-operation dynamic blob SHA-256 (reference):
  bd73cb33adafacbcb0d5d0313606c94ad2de97e2810953387085234863b509d1
post-operation backup directory (future, non-overwriting):
  ${EVIDENCE_ROOT}/
    phase-12-milestone-i6-package-live-smoke-20260823-01/post-operation-backup
candidate dynamic blob SHA-256 (offline reference):
  fbebd82001f2b833e4bfe6af8922c03b4bffbbd42a18f3a9149c501107f1fd47
prospective 0x101b transaction SHA-256 (offline reference):
  2965f96bb13206a57e8efdec96c6722a10862a39f56d6cba15f950c3794c938b
baseline dynamic blob length: 2051132 bytes (reference)
candidate dynamic blob length: 2051420 bytes (reference)
metadata growth bytes: 192 (reference)
aligned content growth bytes: 96 (reference)
complete candidate growth bytes: 288 bytes (reference)
native capacity response command: 0x0019
native capacity response field: +0x08, big-endian
native capacity response file (reference):
  tmp/i4-live-smoke-20260823-01/info-01/command-0019-hardware.bin
native capacity response SHA-256:
  c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a
native capacity evidence source/version:
  parsed_device_info_0x0019 / infocarry-native-capacity-evidence-v1
capacity limit bytes: 3145728 (reference parsed value)
remaining growth before candidate: 1094596 bytes (reference)
remaining growth after candidate: 1094308 bytes (reference)
capacity result: candidate_model_bytes <= capacity_limit_bytes
fixed-state hashes 0x001b..0x001f:
```

The five fixed-state objects must be exactly the fresh verified bytes and must
each match the supported capture-7 all-zero SHA-256:

```text
f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b
```

The workflow must use those verified bytes, not newly synthesized zero blocks.
Any nonzero, unfamiliar, malformed, or unresolved fixed-state value stops the
procedure.

## Separate approval gates

1. Offline preview and protocol review: no device change.
2. Opening a write-capable modern transport: requires a new explicit owner
   approval after the values above are recorded.
3. Executing this one package transaction: requires the exact phrase below
   and the separate approval in step 2.

Approval of this document, the earlier root-TXT smoke, or any fake-transport
test does not authorize this package operation.

## Preconditions

Before a future approved execution:

1. macOS owns the device. Create a fresh complete non-overwriting backup in a
   new destination and verify its manifest, all object hashes, device identity,
   dynamic blob, and fixed-state objects.
2. Confirm the exact target folder and child are absent from that fresh backup,
   including case-insensitive conflict checks.
3. Confirm the fresh fixed-state objects are the exact supported all-zero state.
4. Rebuild the candidate from that fresh backup and the preserved capture-7
   template. Compare every displayed value with the recorded values above.
5. Query and preserve a fresh parsed `0x0019` response using the verified
   device session. Bind its complete raw 64-byte bytes and SHA-256, command,
   `+0x08` field, and parsed `capacity_limit_bytes`. Reject a caller constant,
   Manager UI value, `0x0024`, or `field_14_be32` as capacity evidence.
6. Confirm capacity using the total model rule:
   `candidate_model_bytes <= capacity_limit_bytes`. Record baseline model,
   candidate model, growth, and remaining growth. Do not substitute a
   compatibility `available_capacity_bytes` budget.
7. Preserve the source, preview audit, candidate audit, and prospective
   transaction manifest in new non-overwriting evidence destinations.
8. Close all other device software. No Manager, legacy capture, delete,
   restore, send-all, receive-all, synchronization, or unrelated operation may
   run concurrently.

## One approved transaction only

After the separate approval, and only if every precondition still matches:

1. Require the exact operation-specific phrase:

   ```text
   ADD ONE INFOCARRY TEXT PACKAGE
   ```

2. Send exactly one `0x101b` transaction using the authorized candidate. Do
   not deliberately cancel, disconnect, timeout, refresh, retry, or start a
   second transaction.
3. Show bounded progress for the prospective transaction. Accept only
   completion `0x0000`. Missing, malformed, ambiguous, or nonzero completion
   is terminal.
4. Immediately stop the transfer workflow. Do not infer success from a
   progress bar or a host-side return alone.

## Independent read-back

After a successful `0x0000`, create a complete fresh post-operation backup in
a new destination. Verify independently:

- exact device identity and complete manifest;
- dynamic blob byte-equivalence to the authorized candidate;
- exactly the two added paths and no removed or additional path;
- exact folder and child offsets recorded by the candidate;
- every shared payload, native prefix, timestamp, and preserved field;
- all five fixed-state objects byte-identical to the authorized fresh bytes;
- every unrelated backup object unchanged;
- candidate, transaction, source, and backup hashes;
- no Manager-side sidecar assumption.

Preserve the native transaction, pre/post backups, source, preview, candidate,
read-back report, screenshots, and SHA-256 manifests in a new stable evidence
directory. Do not overwrite capture 7 or any prior evidence.

## Stop and recovery rules

Stop immediately for any missing value, conflict, capacity uncertainty,
fixed-state difference, source mutation, preview mismatch, wrong device,
unexpected path, malformed data, disconnect, timeout, cancellation, partial
completion, nonzero/missing/ambiguous completion, or read-back mismatch.

Once `0x101b` begins, the device outcome is indeterminate after any
disconnect, timeout, cancellation, missing completion, or read-back failure.
Preserve the primary error and all before/audit evidence. Never retry and do
not start another write. Reconnect only for later read-only detection and a
complete recovery backup; do not claim rollback or unchanged device state.

This protocol intentionally stops before execution. A future live result must
be labeled observed, simulated, verified, or unresolved; fake-transport tests
do not prove physical atomicity or recovery. Command `0x0024` is observed to
equal the current dynamic-model length and excluded from capacity
authorization; broader semantics unresolved.
