# I7 legacy delete session — attempt 01

Date: 2026-08-25
Experiment ID: `I7-LEGACY-DELETE-01`
Status: **Prepared offline; not approved or executed.**

This protocol is for one evidence-only legacy Manager mutation. It targets
exactly the existing disposable record below. It does not authorize a modern
delete, a normal GUI/CLI delete action, a retry, or any other device mutation.

## Authoritative pre-delete target

The fresh macOS backup must prove all of these values before owner approval:

| Property | Required value |
| --- | --- |
| Device | Sony `054c:001e` |
| Path | `root\IC_I7_CLOCK_01.txt` |
| Absolute record offset | `0x00000380` |
| Metadata-relative reference | `0x00000340` |
| Payload length | 1,863 bytes |
| Payload SHA-256 | `3aa626dc1e0dbd2fe13b59fbea7eddf43358a522b9f55ed15ac18556b2a69d4b` |
| Record count | 374 |
| Dynamic blob SHA-256 | `5b081faf7cc733e9c63c13250d689d6e7beb52bcf10470503dd68684471ab61b` |

The current fixed-state bytes must match the preserved post-bookmark state
exactly: `0x001b` and `0x001c` each contain count 1 and reference `0x340`,
`0x001d` and `0x001e` contain all-zero state, and the first `0x001f` group is
`(0x340, 0, 0, 0x80000000, 0)` with the second group all zero. Any mismatch
blocks the session; do not rebuild the protocol around a changed device.

## Non-overwriting session

Create a new destination outside this repository and outside raw source
directories. The support command refuses an existing root:

```sh
SESSION_ROOT="${EVIDENCE_ROOT}/phase-13-i7-legacy-delete-20250825-01"
.venv/bin/python scripts/i7_experiment_support.py delete-session \
  --destination "$SESSION_ROOT"
```

If that destination exists, choose a new numbered destination. Never reuse,
rename, flatten, or delete an earlier session. The skeleton contains:

```text
00-timestamps/
01-pre-delete-backup/
02-manager-before-delete/
03-snoopypro-delete-capture/
04-manager-after-delete/
05-post-delete-backup/
06-analysis/
session-manifest.json
```

Raw backups, Manager files, SnoopyPro logs, screenshots, timestamp logs, and
their manifests remain in this external session only. The tracked repository
contains no raw evidence.

## macOS-only preflight

macOS must own the device exclusively. Windows 2000, Manager, SnoopyPro, and
any modern write-capable process must be closed or disconnected.

1. Run read-only detection and confirm Sony `054c:001e`.
2. Create a complete fresh backup under `01-pre-delete-backup/` without
   overwriting any earlier backup.
3. Copy the harmless Windows timestamp-tool dry-run logs into
   `00-timestamps/logs/`; keep their numbered filenames unchanged. The dry
   run must contain at least two valid files and must be validated before any
   device mutation.
4. Run the offline preflight, writing its report to a new path:

```sh
.venv/bin/python scripts/i7_experiment_support.py delete-preflight \
  "$SESSION_ROOT/01-pre-delete-backup" \
  --timestamp-directory "$SESSION_ROOT/00-timestamps/logs" \
  --session-root "$SESSION_ROOT" \
  --output "$SESSION_ROOT/06-analysis/pre-delete-preflight.json"
```

The report must say `eligible_for_live_capture: true` and show the exact
target, payload hash, dynamic-blob hash, record count, raw/parsed fixed state,
timestamp dry-run validation, and `usb_operation_performed: false`. Any
missing, malformed, stale, conflicting, or changed value is a stop condition.

Before any ownership change, show the owner the report and state:

- expected removal: exactly the target path above;
- expected additions: none;
- all shared payloads must remain byte-identical;
- the operation is one legacy Manager deletion only;
- no automatic retry is allowed.

Only after this review request the exact approval phrase:

```text
APPROVE I7 LEGACY DELETE 01
```

The phrase is not implied by preparing or reading this document.

## Four relevant timestamps

Use the existing self-contained Windows 2000 tool
`support/windows2000-timestamp/CaptureTimestamp.js`. Do not rename its raw
numbered files. Meanings belong in a separate session mapping. For the one
successful mutation, capture only:

1. immediately before the successful SnoopyPro `Restart Device` action;
2. after Manager reconnection/initialization completes and packet activity is
   idle;
3. immediately before the Manager delete action;
4. after Manager finishes and the correct SnoopyPro packet count is unchanged
   for approximately 2–3 seconds.

If logging works without Restart Device, use the first event immediately
before Manager launch and label it accordingly. Preserve any unsuccessful
setup attempt and its timestamp sequence; never overwrite or discard it.

## Windows deletion capture, only after approval

Windows 2000 must own the device alone. SnoopyPro is opened first and Manager
is started second. Confirm the correct InfoCarry log window packet count is
increasing. If Restart Device is necessary, wait until Manager initialization
is idle, capture timestamp 1, click Restart Device once, and wait for the
reconnection packets to finish. Capture timestamp 2 only when Manager is idle
and packet activity has stopped.

1. Select SnoopyPro target `USB\Vid_054c&Pid_001e`, never a root hub.
2. Confirm Manager displays and selects exactly
   `root\IC_I7_CLOCK_01.txt`; do not select another item.
3. Copy the four Manager artifacts into
   `02-manager-before-delete/`, preserving actual relative paths and names:
   `VICDATA.bin`, `VICMEM.bin`, `VICLV.bin`, and the applicable nested
   `order.vnw`. Include additional related sidecars if present. Hash every
   file. If locking prevents a complete copy, stop and ask the owner.
4. Capture timestamp 3 immediately before the delete action.
5. Perform exactly one ordinary legacy Manager Delete Selected operation for
   the target. Do not refresh, browse, send, receive, reorder, reopen, or
   perform another mutation.
6. Wait until Manager animation/progress stops and the correct SnoopyPro
   packet count remains unchanged for 2–3 seconds. Capture timestamp 4.
7. Record the exact Manager result and preserve a screenshot if available.
8. Stop and save the SnoopyPro log unchanged in
   `03-snoopypro-delete-capture/`. The log must contain one isolated delete
   transaction.
9. Copy and hash the same Manager files into
   `04-manager-after-delete/`. Never overwrite the BEFORE snapshot.

If logging is absent, the wrong row is selected, the target is absent or
duplicated, a file copy is incomplete, Manager reports failure/timeout/
disconnect/ambiguity, or unrelated traffic or mutation appears, stop. Save
all partial evidence; do not retry.

## Return and read-only postflight

Release Windows ownership and close Manager/SnoopyPro normally before macOS
reclaims the device. Never force-quit UTM, force-eject, restart the Mac, or
move USB ownership while an application or capture is active.

With macOS owning the device exclusively, create a new complete backup under
`05-post-delete-backup/`. Preserve it regardless of the Manager wording or
whether the target appears removed. Compare only after the complete backup is
verified. The offline result must report:

- exact added and removed paths;
- target payload identity before deletion;
- every shared payload comparison;
- all metadata timestamp changes;
- all `0x001b`–`0x001f` raw and parsed changes, including unused tails;
- candidate and post-backup dynamic-blob hashes;
- model growth/reclaimed space;
- Manager BEFORE/AFTER sidecar hashes; and
- completion status, including an explicit unresolved value if request 4 is
  not trustworthy in the native log.

The complete post-delete backup is authoritative for persisted device effect.
Manager wording and native completion are recorded separately. Missing or
ambiguous completion never authorizes a retry. Preparing this protocol does
not authorize execution.
