# Minimal legacy new-TXT evidence protocol

Date: 2026-08-22
Status: **Owner participation required; do not execute automatically.**

This protocol is required because the existing audit proves the new
`IC_TEST_01.txt` record but does not preserve the affected new-file sidecar
state. It describes one controlled legacy-Manager add capture. The optional
delete is a separate operation and is not required for the Milestone E
creation gate.

## Non-negotiable rules

- Preserve every existing capture, fixture, backup, export, and analysis note.
  Create a new timestamped root that does not exist; never overwrite, rename,
  normalize, or delete an original.
- Never allow Windows 2000 and macOS to own the device simultaneously. The
  device must be released cleanly before the other system connects.
- Exactly one new, uniquely named, disposable TXT item is allowed. Do not
  browse, rename, select a folder, use Send All, use Receive All, restore,
  cancel, unplug, or perform a second transfer in the add session.
- No modern-client write, delete, restore, or live smoke is part of this
  protocol. Each later action needs its own explicit approval and gate.
- Do not retry automatically. On any ambiguity or unexpected result, stop and
  preserve the partial evidence.
- Startup, browsing, source preparation, and item selection must be complete
  before the standalone add log begins. The add log must contain only the
  single Send Selected operation and its required protocol traffic.

## Add capture — one disposable TXT

1. Obtain explicit owner approval for this capture and confirm that the
   Windows 2000 VM, SnoopyPro, the legacy Manager, and the device are ready.
   On macOS create this new root outside the source checkout, for example:

   ~~~text
   ${EVIDENCE_ROOT}/phase-12-new-txt-20260822-<HHMMSS>/
   ~~~

   Confirm that the root does not exist. Create only these stage directories:

   ~~~text
   00-pre-add-backup/
   01-manager-before-send/
   02-snoopypro-add-capture/
   03-manager-after-send/
   04-post-add-backup/
   05-manager-after-refresh/       (optional, only after stage 04 is safe)
   ~~~

   Each manager stage must also have its own `snapshot-manifest.json`.

2. With macOS owning the device, make one complete verified read-only backup
   into `00-pre-add-backup/`. Preserve the complete backup manifest, every
   object hash, device identity, dynamic-blob hash, and pre-add capacity
   information where the device or Manager exposes it. Do not reuse a prior
   Phase 8 backup.

3. Attach the device to the Windows 2000 guest and verify the actual
   `USB\Vid_054c&Pid_001e` device row in SnoopyPro, never a hub row. Start the
   legacy Manager normally and finish all detection, source preparation, and
   item selection before starting the add log.

   Prepare exactly these host source bytes for
   `IC_E_ADD_20260822_01.txt`:

   ~~~text
   InfoCarry Milestone E 20260822
   DISPOSABLE ADD ONLY
   ~~~

   The two line endings must be literal CRLF bytes (`0x0d 0x0a`), not the
   four characters `\r\n`. The expected 53-byte source SHA-256 is
   `2a3a3057a532d27bad9de6e7b3fb83bf3de95482202dcdf4580e7ecc53844e38`.
   Record the actual original host path, bytes, size, and SHA-256 even if the
   observed value differs; do not silently rewrite the source.

4. Before any device transfer, preserve the exact source file and the current
   Manager-produced files in `01-manager-before-send/`, after the source is
   prepared but before Send Selected. Preserve the actual relative paths under
   a `source/` or `manager/` subtree rather than flattening names. Include
   every available relevant file, including:

   ~~~text
   Backup/VICDATA.bin
   Memo/VICMEM.bin
   Memo/VICLV.bin
   ICM/<actual-transfer-folder>/order.vnw
   ~~~

   Also preserve every additional related sidecar and record its actual
   Windows-relative path. Hash every copied source and Manager file
   independently in `snapshot-manifest.json` with its relative path, size, and
   SHA-256. If Windows file locking prevents a copy, close Manager normally
   without refreshing or receiving, copy the files, and reopen it only to
   return to the already prepared idle/selection state. Do not start SnoopyPro
   until any such startup or browsing traffic is complete.

5. With the one item selected and Manager idle, start a new standalone native
   SnoopyPro log in `02-snoopypro-add-capture/`. Do not include Manager
   startup, browsing, source preparation, or unrelated traffic. If SnoopyPro
   cannot isolate the add operation without those actions, stop and do not
   capture.

6. Invoke only `転送 → 選択送信` / **Transfer → Send Selected**. Confirm that
   the dialog names `IC_E_ADD_20260822_01.txt`. Let exactly this one operation
   finish normally. Record the displayed Manager result verbatim, the
   SnoopyPro version, VM/device handoff times, and the native log SHA-256.
   Save the unconverted native log as:

   ~~~text
   02-snoopypro-add-capture/01-add.usblog
   ~~~

   If a warning, password prompt, unexpected dialog, timeout, disconnect, or
   non-success result appears, stop and preserve the partial log without a
   retry.

7. Stop SnoopyPro immediately after the successful Send Selected result and
   before any read, receive, refresh, browse, or backup-to-PC action. Preserve
   the Manager files immediately after the send in
   `03-manager-after-send/`. This snapshot must be distinct from both the
   before-send and refreshed snapshots. Include the same `VICDATA.bin`,
   `VICMEM.bin`, `VICLV.bin`, applicable `order.vnw`, and any additional
   sidecars using their actual relative paths. Hash every file independently
   in a new `snapshot-manifest.json`.

   If file locking prevents immediate copying, close Manager normally without
   refreshing or receiving, copy the files, and do not reopen it until the
   separately identified optional refresh stage. Never substitute a later
   refreshed file for this after-send snapshot.

8. Close Manager and SnoopyPro normally, shut down Windows 2000 cleanly, and
   release USB ownership to macOS. With macOS owning the device, make one
   fresh complete verified read-only backup into `04-post-add-backup/`.
   Preserve its complete manifest, all object hashes, device identity,
   dynamic-blob hash, and post-add capacity information where available.

9. Only after stages 01–04 are complete and safely preserved, optionally
   reconnect the legacy Manager for one separately identified read/receive
   refresh. Do not send, delete, rename, or browse beyond what is needed to
   perform that refresh. Save the resulting Manager files under
   `05-manager-after-refresh/` with an independent manifest and hashes. This
   optional snapshot is comparative context only; it must never replace the
   immediate after-send snapshot.

10. Preserve a capture-notes file in the root recording the exact source bytes
    and SHA-256, displayed Manager result, device identity, pre/post capacity
    values or “not exposed,” complete backup manifests/object hashes, SnoopyPro
    version, native log hash, stage timestamps, and any stop condition. Provide
    the owner evidence-root path and hashes for offline analysis. No modern
    replay will be attempted.

## Optional separate delete capture

Only after the add evidence is safely preserved and the owner gives separate
explicit approval, capture deletion in a new timestamped evidence root and a
separate session. Begin from a verified post-add backup, preserve a complete
pre-delete backup and the Manager files before deletion, start a standalone
native log only after startup and selection are complete, invoke only the
single-item delete action, stop at completion, preserve the native log and
post-delete Manager sidecars, and make a complete verified post-delete backup.
Do not combine add and delete in one capture or use deletion as Milestone E
completion; deletion is independent Milestone H evidence.

## Protocol validation and stop conditions

This procedure has been reviewed against the required safety boundary:

- New roots and stage manifests prevent overwrite and preserve original
  evidence; actual relative paths and independent hashes prevent normalization
  or snapshot conflation.
- macOS and Windows ownership are explicitly serialized, with clean release
  before handoff in either direction.
- The add log contains exactly one uniquely named TXT Send Selected operation;
  startup, browsing, rename, Send All, Receive All, and unrelated mutation are
  excluded.
- A failed or ambiguous operation stops without automatic retry. A file-lock
  workaround closes Manager without refresh and reserves refresh for its own
  stage.
- Capture approval, any later modern new-file smoke approval, and optional
  deletion approval are separate. No live modern write or delete is enabled by
  this document.

Stop and preserve everything already captured if the device is not `054c:001e`,
the item is not uniquely identified, the source hash is not recorded, a
required snapshot or complete backup is unavailable, SnoopyPro attaches to a
hub, the log includes unrelated actions, Manager reports anything other than
the expected single-item result, capacity is ambiguous at a required gate, a
device disconnects, or any file would be overwritten. Ask the owner before
changing the procedure or attempting any retry.
