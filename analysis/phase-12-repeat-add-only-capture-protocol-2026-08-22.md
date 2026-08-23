# Repeat legacy add-only capture protocol

Date: 2026-08-22
Status: **Owner-approved capture 04 completed the clean native/device delta and
closed Milestone E.** The protocol remains the preserved evidence template;
future work is offline Milestone F only. Its unchanged Manager sidecars are a
verified negative result, while device-state rebasing, fail-closed capacity,
and checked completion handling remain explicitly bounded assumptions.

This is the next safe experiment after the first owner capture. It isolates
one additional new TXT record from the current device state. It must not clear
the device or repeat the earlier deletion workaround.

The approved attempt used `IC_E_ADD_20260822_02.txt` and preserved complete
pre/post backups, but SnoopyPro captured no native packets and no after-send
Manager snapshot or sidecars were supplied. That attempt is recorded in
`analysis/phase-12-repeat-add-only-attempt-2026-08-22.json`. If a future
capture is approved, verify native logging before beginning the add and use a
new unique filename because the attempted name now exists on the device.

A later attempt used `IC_E_ADD_20260822_03.txt`; its post-attempt backup proves
that the Manager add completed, but SnoopyPro was attached to the root hub
instead of `USB\\Vid_054c&Pid_001e`, so it also lacks usable native and Manager
snapshot evidence. That attempt is recorded in
`analysis/phase-12-repeat-add-only-attempt-03-2026-08-22.json`. The next
prepared source is `IC_E_ADD_20260822_04.txt`.

Capture 04 completed the native/device portion of this protocol. Its complete
evidence record is
`analysis/phase-12-repeat-add-only-capture-evidence-04-2026-08-22.json`. The
new record is proven by matching native range-5/range-8 bytes and complete
device pre/post backups. The Manager sidecars remain byte-identical before and
after, which is a verified negative result for Manager-local mutation in this
operation. The new-file category is intentionally not assigned offline;
completion and remaining-capacity interpretations remain checked Milestone F
assumptions.

The current state already contains `root\IC_E_ADD_20260822_01` and the
previously observed `root\IC_TEST_01`. The repeat therefore uses a different
name and a fresh current-state baseline.

## Hard safety rules

- Do not clear the device, delete any item, restore anything, refresh Manager,
  or perform any other mutation before or during this add capture.
- Do not use the prior pre-add backup as the new baseline. Make a fresh
  complete macOS backup immediately before preparing the repeat source.
- Exactly one new uniquely named TXT item is allowed:
  `IC_E_ADD_20260822_02.txt`. If that name already exists, stop and request a
  different name; do not silently rename it.
- Do not use Send All, Receive All, rename, folder selection, browsing after
  the isolated log begins, or a second transfer.
- If Manager reports insufficient space, stop and preserve the partial state
  and any native log. Do not delete files and do not retry in that session.
- Never allow Windows 2000 and macOS to own the device simultaneously. No
  modern-client write, delete, restore, or smoke test is part of this
  protocol.

## Evidence root

After explicit approval, create a new root that does not exist:

~~~text
${EVIDENCE_ROOT}/phase-12-new-txt-repeat-20260822-<HHMMSS>/
~~~

Create only:

~~~text
00-pre-add-backup/
01-manager-before-send/
02-snoopypro-add-capture/
03-manager-after-send/
04-post-add-backup/
~~~

Do not use the previous capture root for repeat evidence.

## Procedure

1. Keep the current device state untouched. With macOS owning the device,
   create one fresh complete verified read-only backup inside
   `00-pre-add-backup/`. Use a new child archive because the backup command
   refuses an existing destination. Preserve its complete manifest, all eight
   object hashes, device identity, dynamic-blob hash, and any available
   capacity information.

2. Release the device cleanly to Windows 2000. Verify SnoopyPro is attached to
   the actual `USB\Vid_054c&Pid_001e` row, not a hub. Do not start native
   recording yet.

3. Prepare exactly these bytes in the Manager source folder as
   `IC_E_ADD_20260822_02.txt`:

~~~text
InfoCarry Milestone E 20260822
DISPOSABLE ADD ONLY
~~~

   Both line endings, including the final one, must be CRLF. The expected size
   is 53 bytes and the expected SHA-256 is
   `2a3a3057a532d27bad9de6e7b3fb83bf3de95482202dcdf4580e7ecc53844e38`.
   Preserve the exact Windows source path and an untouched host copy.

4. Before any transfer, copy the source and every available relevant Manager
   file into `01-manager-before-send/`, preserving actual relative paths and
   creating an independent `snapshot-manifest.json`. Include:

~~~text
Backup/VICDATA.bin
Memo/VICMEM.bin
Memo/VICLV.bin
ICM/<actual-transfer-folder>/order.vnw
~~~

   If files are locked, close Manager normally without refresh or receive,
   copy them, and reopen only before the isolated log begins. Record any
   additional Manager-specific sidecar; if none exists, record
   `additional_related_sidecars: none present`. Exclude unrelated OS metadata.

5. Finish Manager startup, browsing, and selection. Select only the new
   `IC_E_ADD_20260822_02.txt` item. When Manager is idle, start a new native
   SnoopyPro log in `02-snoopypro-add-capture/`. The log must not contain
   startup, browsing, source preparation, or unrelated traffic.

6. Invoke only Transfer → Send Selected once. Confirm the dialog names
   `IC_E_ADD_20260822_02.txt`. Record the displayed Manager result, SnoopyPro
   version, timestamps, and native log SHA-256. Stop the log immediately after
   the result and before any read, receive, or refresh.

7. Preserve the Manager files immediately after the successful send in
   `03-manager-after-send/` with the same actual paths and a new independent
   manifest. If files are locked, close Manager normally without refresh or
   receive; do not reopen it before the post-add backup.

8. Release Windows ownership cleanly to macOS. Make one fresh complete verified
   read-only backup in `04-post-add-backup/`. Preserve its manifest, object
   hashes, device identity, dynamic-blob hash, and capacity information.

9. Do not perform the optional Manager refresh in this repeat capture. It is
   unnecessary for the clean before/after delta and would introduce another
   state transition.

## Review gate

The repeat can support offline model work only if the fresh pre/post pair
shows exactly one added reachable path, no unexplained shared-record changes,
and a complete transaction result. The new-file `VICMEM.bin`, `VICLV.bin`,
`order.vnw`, category, allocation/capacity, and completion evidence must still
be inspected independently. Sidecars that remain byte-identical are a
documented negative result, not proof of a general writer.

If any stop condition occurs, preserve the evidence and stop. Do not clear,
delete, restore, refresh, or retry without a separately approved protocol.
