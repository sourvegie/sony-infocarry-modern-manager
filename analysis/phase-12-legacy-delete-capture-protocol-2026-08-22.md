# Minimal legacy selective-delete capture protocol

> Historical protocol for failed attempt 01. Do not reuse it. The corrected
> Manager-known target and procedure are in
> `analysis/phase-12-legacy-delete-capture-protocol-02-2026-08-22.md`.

Date: 2026-08-22
Purpose: obtain one isolated deletion evidence package for Milestone H.  This
protocol is owner-operated and does not authorize a modern-client delete.

## Scope and exact target

Perform exactly one deletion of the existing disposable item:

```text
root\IC_G_LIVE_20260822_01.txt
```

Do not create another item, clear the device, rename, browse unrelated items,
send, receive, refresh, reorder, or combine deletion with any other mutation.
Do not delete any other file if the target is missing, duplicated, or not the
expected root-level TXT record.

Preserve all previous evidence. Use a new evidence directory, for example:

```text
${EVIDENCE_ROOT}/phase-12-delete-20260822-<time>/
```

Never overwrite an existing log, backup, snapshot, manifest, or source file.

## Stage 1 — macOS pre-delete backup

1. Confirm the normal modern app and Windows Manager are closed. macOS owns the
   device exclusively.
2. Create a complete raw device backup in a new directory and verify all eight
   objects, the device identity, manifest hashes, object hashes, and dynamic
   blob structure.
3. Confirm offline that the backup contains exactly one reachable target path,
   `root\IC_G_LIVE_20260822_01.txt`, and record its metadata offset, payload
   length, payload hash, and full dynamic-blob hash.
4. Preserve the complete manifest and object hashes. Do not refresh, open, or
   mutate the device after this backup.

Stop if the backup is incomplete, stale, unreadable, has the wrong device
identity, or does not contain exactly the target once.

## Stage 2 — Manager-side before snapshot

1. Close the modern client and disconnect the device cleanly before changing
   host ownership.
2. On Windows 2000, connect only the InfoCarry. Do not let macOS or another
   process retain the device.
3. Start Manager and SnoopyPro only after the device is ready. In SnoopyPro,
   select the InfoCarry device row identified by `USB\Vid_054c&Pid_001e`, not
   the root hub or a parent hub.
4. Prepare a new before-delete snapshot directory. Copy, without renaming or
   normalizing, every available relevant Manager file at its actual relative
   path, including:

   - `VICDATA.bin`;
   - `VICMEM.bin`;
   - `VICLV.bin`;
   - `order.vnw`;
   - any additional related sidecar Manager presents.

5. Record the exact relative path, byte size, and SHA-256 for every copied
   file. Also record the Manager version, displayed device identity, and the
   Manager's displayed item list/capacity before deletion.

If Windows file locking prevents a copy, close Manager normally without
refreshing or performing another operation, copy the files, and record that
the close was required. Do not reopen Manager until the separately identified
after-delete stage.

## Stage 3 — standalone SnoopyPro delete capture

1. Start a new SnoopyPro native log for this deletion only. Record the log
   filename and SnoopyPro version.
2. With the target already selected and verified, perform exactly one ordinary
   Manager Delete action for the target.
3. Capture the complete request/response traffic through the Manager's final
   displayed result. Do not click Delete again, retry, cancel, Send, Receive,
   refresh, browse another item, or close/reopen Manager during the captured
   operation unless the stop rule below requires a normal close.
4. Record the exact displayed result, any confirmation text, and any displayed
   capacity/item count after the operation.
5. Stop the native log immediately after the operation reaches its final
   result. Hash the native log and preserve the original file unchanged.

The log must contain no startup, browsing, unrelated selection, second
attempt, or other device mutation. If SnoopyPro is attached to the wrong USB
row, the log has unrelated traffic, or the Manager performs more than the
single requested deletion, stop and classify the attempt as invalid without
retrying.

## Stage 4 — Manager-side after snapshot

1. Without refreshing or performing another operation, close Manager normally
   if needed to release file locks.
2. Copy the same complete set of Manager files into a new after-delete
   snapshot directory, preserving actual relative paths and filenames.
3. Hash every after-delete file independently. Record missing files explicitly;
   do not silently compare a missing file as an empty file.
4. Record the Manager's displayed result and any visible item/capacity change.

## Stage 5 — macOS post-delete backup

1. Close Manager and disconnect Windows ownership cleanly. Do not reconnect it
   to the modern client simultaneously.
2. On macOS, create a new complete raw backup in a new post-delete directory.
3. Verify all eight objects, manifests, object hashes, device identity, and
   dynamic blob. Confirm the target path is absent exactly once and record all
   added, removed, and changed paths/payloads.
4. Preserve the complete post-delete archive even if the result is unexpected
   or the target remains present.

## Stop conditions and recovery boundary

Stop immediately and do not retry if:

- the target is missing, duplicated, or not a root-level TXT;
- macOS and Windows ownership overlap;
- SnoopyPro is attached to the root hub instead of the InfoCarry;
- the Manager asks for an unrelated operation or the native log contains
  unrelated mutation traffic;
- the displayed result is failure, timeout, disconnect, or ambiguous;
- file locks prevent a complete snapshot and the missing scope cannot be
  recorded; or
- any path other than the selected target changes unexpectedly.

Preserve the pre-delete backup, native log, Manager snapshots, and any partial
post-delete backup. Do not attempt a second deletion. No modern-client write,
delete, restore, or read/write smoke is part of this capture.

## Approval boundaries

Owner approval for this exact legacy capture is separate from approval for a
future modern delete. After the evidence audit, a modern delete would still
require a new offline candidate, target-bound authorization, fake-transport
failure tests, a fresh backup, exact confirmation, one-shot transfer, and
complete independent post-delete read-back verification. Until those gates
close, the normal CLI/GUI remains read-only for deletion.
