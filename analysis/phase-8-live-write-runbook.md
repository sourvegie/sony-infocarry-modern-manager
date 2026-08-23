# Phase 8 — New Fixture and First Modern-Write Runbook

Date: 2026-08-21

This runbook has two distinct operations:

1. capture one new, genuine manager transfer and preserve its manager files;
2. hand the device to macOS for analysis and, only after a candidate is
   approved, perform one modern-tool write.

Do not replay the existing `00-read-baseline` or `01-selected-send` files.
Those traces document a previous operation and are not a disposable target.

## Part A — Prepare a new capture

1. On the Mac, create new empty destinations. Do not reuse old directories:

   ```text
   ${RESEARCH_ROOT}/usbsnifferlogs/02-manager-test/
   ${RESEARCH_ROOT}/fixtures-3/
   ```

2. Preserve the original ISO, software package, existing fixtures, and raw
   backups. Do not rename or edit any existing file.
3. Take a snapshot of the Windows 2000 VM if practical.
4. Leave networking as it is. USB capture does not require networking to be
   disabled; keep the private/remote-control arrangement that is already
   working.
5. Boot Windows 2000 and attach the InfoCarry to the guest. Close InfoCarry
   Manager before touching SnoopyPro.
6. In SnoopyPro, verify that the USB Devices list contains the actual device
   row with `USB\\Vid_054c&Pid_001e`. Select that row, not a `ROOT_HUB` row.
   If the bridge is not available, use **File → Install Service**. Install the
   sniffer only on the InfoCarry row. Restart the device at most once if
   SnoopyPro explicitly requires it.
7. Keep the automatically attached InfoCarry log window. Do not use
   **File → New** when that window is already present; a new blank window will
   not receive the device traffic.

## Part B — Record a safe baseline

1. Start a fresh SnoopyPro session and leave the attached log running.
2. Start InfoCarry Manager and allow normal detection/startup to finish.
3. Perform only a read/receive/backup-to-PC action. Do not send, restore,
   delete, format, or change device settings.
4. Stop the capture after the read operation completes.
5. Save the native log as:

   ```text
   .../usbsnifferlogs/02-manager-test/00-read-baseline.usblog
   ```

   Save the native format. Do not convert it, replay it, or overwrite an older
   capture. Record the manager result and approximate time.

If the baseline cannot be saved, stop. Do not proceed to the selected send.

## Part C — Select one disposable manager item

1. Choose one small item in the manager's host-side transfer source area. A
   throwaway text/memo item with a unique name is preferred. If the manager
   cannot create a new memo, use one existing item that is safe to duplicate
   or replace; do not guess at an undocumented menu.
2. Ensure exactly one file is selected—not a folder, category, or all-device
   selection.
3. Record its displayed name, extension, and manager path. Avoid any item that
   exists only on the device unless it has first been safely received to the
   host.

## Part D — Immediate approval checkpoint

Stop and verify all of the following before changing the device:

- a complete read-only backup exists and will not be overwritten;
- the baseline `.usblog` is saved;
- exactly one disposable item is selected;
- the destination capture path is new;
- **Send All** / `一括送信` is not selected.

The selected send is device-changing. Do not continue if a same-name warning,
password prompt, unexpected dialog, or different operation appears.

## Part E — Capture one manager selected-send

1. Keep the same attached SnoopyPro log that contains the baseline. Do not
   create a blank **File → New** log. If that log cannot continue, start a new
   attached session and record that the selected-send capture is standalone.
2. Ensure capture is running before invoking the send.
3. In InfoCarry Manager choose:

   ```text
   転送 → 選択送信
   ```

   (`Transfer → Send Selected`), or the equivalent selected-item action.
4. Confirm that the dialog names the one disposable item. Never choose
   `一括送信` / Send All.
5. Let it finish normally. Do not cancel, eject, unplug, or force-quit during
   the transfer.
6. If a same-name warning appears, stop and preserve the partial capture. Do
   not accept overwrite/duplicate behavior without a new decision.
7. After successful completion, stop SnoopyPro immediately and save the native
   capture as:

   ```text
   .../usbsnifferlogs/02-manager-test/01-selected-send.usblog
   ```

8. Do not perform another send in that capture session.

## Part F — Preserve the new manager fixture

1. Keep InfoCarry Manager open after saving the selected-send capture. Stop
   SnoopyPro first so this read-only refresh is not mixed into the selected-send
   trace.
2. Use only the manager's read/receive/backup-to-PC workflow to refresh its
   local working files after the selected send. If the manager was already
   closed, reopen it and perform the same read-only workflow. This is for
   evidence and is not a second send.
3. After the refresh completes, close InfoCarry Manager normally.
4. Copy the manager-produced files into the new `fixtures-3` directory,
   preserving bytes and relative paths:

   ```text
   fixtures-3/Backup/VICDATA.bin
   fixtures-3/Memo/VICMEM.bin
   fixtures-3/Memo/VICLV.bin
   fixtures-3/ICM/<actual-folder>/order.vnw
   ```

   Keep any six-digit prefixes and the actual `order.vnw` folder name. Do not
   open and save the files in an editor.
4. Keep the original Windows copies and the VM snapshot. Do not replace the
   existing `fixtures` or `fixtures-2` directories.

## Part G — Hand USB ownership back to macOS

1. Close the manager and SnoopyPro normally.
2. Shut down Windows 2000 cleanly. Do not force-quit UTM or use a Windows
   eject command while the manager is active.
3. In UTM, release/detach the USB device from the guest and attach it to the
   Mac host. The host must own the device for the modern sender.
4. After the guest is fully powered off, tell Codex that the USB is attached
   to macOS and provide the paths to the new capture and `fixtures-3`.

## What happens next on macOS

The toolkit will then:

1. verify the new fixture hashes and compare `VICDATA.bin` with the earlier
   fixtures;
2. parse `01-selected-send.usblog` and preserve a new offline artifact using
   `capture-artifact` (transaction index normally `1` when baseline and send
   are cumulative);
3. run a fresh complete read-only backup into a new directory;
4. verify the artifact, backup, device identity, and candidate hashes;
5. review the range-8 differences and decide whether a modern candidate can be
   generated without replaying the manager transaction.

Only if that review produces a genuinely disposable modern candidate will the
live sender be opened. Immediately before request 2 it will require the exact
interactive confirmation phrase `WRITE INFOCARRY`. It will never send
`0x101d` or an unlock workflow in this first test.

## Stop conditions

Stop and preserve all evidence if the manager hangs, requests a password,
shows an unexpected menu, reports a timeout, loses the device, or if the Mac
does not detect `054c:001e` after the USB handoff. Do not retry automatically.
