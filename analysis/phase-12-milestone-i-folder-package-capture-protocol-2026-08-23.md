# Milestone I.3 — isolated folder/package evidence protocol

Status: **Executed once by owner on 2026-08-23; do not repeat automatically.**

This protocol was used for the one owner-approved Windows 2000 session that
produced capture 7. The resulting evidence and exact offline comparison are
recorded in
`analysis/phase-12-milestone-i-folder-package-capture7-20260823.md` and its
machine-readable companion. No second capture is requested by this record.

## Exact disposable operation

Use exactly one new root-level folder named:

```text
IC_I_FOLDER_20260823_01
```

Place exactly one child in it named:

```text
chapter.txt
```

The child content must be short ASCII/CP932-safe text with explicit CRLF
bytes:

```text
Milestone I folder child\r\nDisposable one-capture package.\r\n
```

Record the exact source bytes and SHA-256 before Send Selected. Do not add an
image, second child, nested folder, mark, bookmark, category, selection state,
rename, or other source item. The folder and child must be absent from the
fresh pre-operation device backup and must not collide with an existing name.

## Preconditions and ownership

1. Obtain separate explicit owner approval for this capture. Documentation of
   this protocol is not approval.
2. On macOS, create a new non-overwriting destination for a complete pre-add
   backup. Verify the backup is complete, identifies `0x054c:0x001e`, and
   contains neither the folder nor the child.
3. Preserve the complete backup manifest and every object hash. Keep all prior
   evidence and backups unchanged.
4. Close all device-accessing software on macOS. Transfer USB ownership cleanly
   to Windows 2000. Never let macOS and Windows own the device simultaneously.
5. On Windows 2000, prepare one new transfer-source folder containing exactly
   the named folder and child. Preserve the source tree and source-byte hash.

## Before-send snapshot

Before selecting the operation, preserve separately:

- the exact source folder tree and child bytes;
- Manager-produced `Backup/VICDATA.bin`;
- Manager-produced `Memo/VICMEM.bin`;
- Manager-produced `Memo/VICLV.bin`;
- the actual relative-path `ICM/転送元フォルダ/order.vnw` and any additional
  related sidecar that is present;
- independent size/SHA-256 entries for every snapshot file;
- the displayed Manager tree showing exactly the new folder and one child; and
- the device identity shown by the selected SnoopyPro row.

If Windows file locking prevents copying, close Manager normally without
refreshing, receive, browsing, or changing the device. Copy the files, then
reopen Manager only for the separately recorded after-send snapshot.

## One isolated capture

1. Start a new SnoopyPro native log and target exactly:
   `USB\\Vid_054c&Pid_001e&Rev_0100`.
2. Confirm the log is attached to the InfoCarry device row, not a root hub or
   another USB row. Record SnoopyPro version and the native-log destination.
3. In Manager, select exactly the new root folder
   `IC_I_FOLDER_20260823_01`, not its child and not any other item.
4. Use only the ordinary selected-send action. Do not use Send All, Receive,
   Receive All, startup refresh, browsing refresh, rename, reorder, delete, or
   any unrelated operation.
5. Wait for the Manager result and record it exactly, including a screenshot.
6. Stop SnoopyPro immediately after this one operation. Do not retry, refresh,
   send, receive, reorder, or perform a second mutation in the same session.

Stop immediately and preserve everything if the folder is absent or duplicated,
the child is absent, the wrong USB row is selected, Manager reports failure or
ambiguity, SnoopyPro records no transaction, a timeout/disconnect occurs, or an
unrelated item changes. A failed or indeterminate attempt is still evidence;
it is never retried automatically.

## After-send preservation

1. Close Manager normally without a read/receive refresh and preserve the
   Manager-after files under a new non-overwriting directory. If a separate
   refresh snapshot is desired, perform it only after the after-send snapshot
   and label it separately.
2. Stop and preserve the native SnoopyPro log. Hash the native file before any
   XML/export conversion; preserve native and derived forms separately.
3. Return USB ownership cleanly to macOS.
4. Create a complete non-overwriting post-operation backup. Preserve its
   manifest, all object hashes, and device identity.
5. Preserve the complete source, Manager-before, Manager-after, native log,
   pre-backup, post-backup, result screenshot, versions, timestamps, and notes.
   Copy rather than move; never modify original Desktop or evidence sources.

## Offline acceptance gate

The capture can support a later offline folder model only if analysis proves
all of the following:

- exactly one new directory record for the named root folder;
- exactly one new reachable TXT child and the expected parent marker(s);
- parent, child, sibling, metadata, content, alignment, and padding pointers
  are reconstructed without unexplained changes;
- the native range-5/range-8 candidate exactly matches the post-operation
  dynamic device blob, or every normalization is narrow and documented;
- all unrelated record metadata and payloads are byte-identical;
- fixed-state references and unknown bytes are preserved or safely rebased;
- timestamp behavior is observed and independently justified;
- the native transaction count is established as one or more operations;
- the completion/result behavior is recorded and trustworthy;
- Manager sidecar before/after changes, if any, are separately identified and
  not silently treated as device state; and
- capacity/growth is measured from the complete before/after evidence.

Anything short of this remains failure, incomplete, or unresolved evidence.
It does not authorize a modern package sender, a normal GUI/CLI action, a
delete, or another capture.

## Execution record

Capture 7 completed normally according to the owner report. Its native log
contains one ordinary `0x101b` transaction, and the range-5 plus range-8
candidate exactly matches the complete post-operation dynamic blob. The
folder/multi-record evidence gate is satisfied for this captured fixture only;
timestamp generation, general fixed-state derivation, capacity semantics, and
modern package transfer remain offline-only or unresolved.
