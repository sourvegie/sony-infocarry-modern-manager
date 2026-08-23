# Minimal legacy selective-delete capture protocol — attempt 02

Date: 2026-08-22
Purpose: obtain one successful isolated legacy deletion fixture for Milestone
H. This owner-operated protocol does not authorize a modern-client delete.

## Why the target changed

Attempt 01 targeted modern-created
`root\\IC_G_LIVE_20260822_01.txt`. Manager reported failure, and the complete
post-attempt backup proved that the record remained. That basename is absent
from the captured Manager `order.vnw`, while the earlier legacy-created
disposable basename below is present. This is an observed bookkeeping
difference and a plausible, not proven, contributor to failure.

Attempt 02 must therefore target exactly:

```text
root\IC_E_ADD_20260822_04.txt
```

This file was created by the legacy Manager during clean capture 04, remains
on the device, is listed in captured `order.vnw`, and has preserved add
evidence. Do not target the Milestone G file again. Do not substitute another
record if `_04` is missing or ambiguous.

## Approval boundary

Do not begin this protocol without the owner's explicit approval for this
exact legacy Manager deletion. Approval does not authorize a modern delete.
Use a new non-overwriting evidence directory under:

```text
${EVIDENCE_ROOT}/
```

## Stage 1 — fresh macOS pre-delete backup

1. Close Windows Manager and the normal modern app. Ensure macOS exclusively
   owns the device.
2. Create a new complete raw backup and verify all eight objects, device
   identity, manifest hashes, object hashes, and dynamic blob structure.
3. Confirm offline that `root\\IC_E_ADD_20260822_04.txt` exists exactly once.
   Record its metadata offset, payload length/hash, and the dynamic-blob hash.
4. Confirm that `root\\IC_G_LIVE_20260822_01.txt` remains present but is not the
   selected target.
5. Stop if the backup is incomplete, the identity is wrong, or `_04` is absent
   or duplicated.

## Stage 2 — clean Windows ownership and Manager snapshot

1. Close the modern client and transfer USB ownership cleanly to Windows 2000.
2. Start Manager and allow it to reach a stable device listing before starting
   the standalone delete log.
3. Confirm visually that `_04` is the selected root-level TXT record. Do not
   select the Milestone G record or any unrelated item.
4. In SnoopyPro select `USB\\Vid_054c&Pid_001e`, never a root/parent hub.
5. Preserve a complete Manager-before snapshot containing the actual relative
   paths for `VICDATA.bin`, `VICMEM.bin`, `VICLV.bin`, `order.vnw`, and any
   additional related sidecar. Record sizes and SHA-256 hashes.
6. Verify that `order.vnw` contains `IC_E_ADD_20260822_04.txt`. Stop if it does
   not.

## Stage 3 — one standalone delete

1. Start a new SnoopyPro log containing only this deletion.
2. With `_04` selected and reconfirmed, perform exactly one ordinary Manager
   Delete action and accept only its normal confirmation for that exact path.
3. Wait for Manager's final displayed result. Record the exact Japanese text,
   any numeric/status result, item count, capacity display, and whether `_04`
   remains visible.
4. Stop the log immediately after the final result and preserve it unchanged.
5. Do not retry, refresh, send, receive, browse another item, reorder, close and
   reopen during the log, or perform any second mutation.

If Manager reports failure, timeout, disconnect, or ambiguity, stop. Preserve
the attempt and do not repeat it in the same session.

## Stage 4 — Manager-after snapshot

1. Without refreshing or another operation, close Manager normally only if
   necessary to release file locks.
2. Copy the same Manager files into a distinct after-delete directory,
   preserving paths and names.
3. Hash each file independently and record missing files explicitly.
4. Preserve screenshots/notes of the final Manager result and displayed list.

## Stage 5 — fresh macOS post-delete backup

1. Close Windows ownership cleanly and return the device exclusively to macOS.
2. Create a new complete eight-object backup in a new directory.
3. Verify identity, manifests, hashes, and structure.
4. Confirm whether exactly `_04` was removed. Record every added, removed, or
   changed path and every shared payload comparison.
5. Preserve the backup even if Manager reported failure or the result is
   unexpected.

## Success gate

The capture is a successful legacy delete fixture only if all are true:

- Manager reports success unambiguously;
- the native log contains one complete isolated transaction and successful
  completion evidence;
- the post-delete backup is complete and structurally valid;
- exactly `root\\IC_E_ADD_20260822_04.txt` is absent;
- no other path is added or removed;
- every unrelated shared payload is unchanged; and
- all Manager before/after files and raw evidence are preserved and hashed.

Anything else remains failure evidence. Do not infer rollback, retry, or run a
modern delete. After capture, return all hardware to a safe read-only state and
wait for offline analysis.
