# Phase 8 — Controlled InfoCarry Write-Capture Protocol

Date: 2026-08-21
Status: **Prepared; device-changing step requires explicit approval immediately before execution.**

## Purpose

Capture one genuine host-to-InfoCarry transfer from the original Windows 2000
manager. The capture is evidence only; it will not be replayed or used to
write the device from the modern toolkit.

## Required equipment and files

- Windows 2000 UTM guest with the original InfoCarry manager installed.
- InfoCarry VNW-V15 connected through UTM.
- SnoopyPro 0.22 (historical Win32 USB sniffer). Do not install USBPcap in
  Windows 2000.
- A preserved, verified read-only backup of the device.
- A host-side capture directory, for example:

  `${LOCAL_USER_ROOT}/Projects/Sony-InfoCarry-Captures/2026-08-21-selected-send-01/`

The USB capture must run inside the Windows 2000 guest because UTM owns the
USB device after it is attached to the guest.

## Safety rules

1. Keep the original ISO, extracted software, and existing backups unchanged.
2. Take a VM snapshot before installing or running the sniffer. Guest-network
   isolation is recommended for this obsolete Windows 2000 environment, but
   it is not required for USB capture and does not control USB passthrough.
   Leave the Mac/host network and TeamViewer connection alone. If the guest
   must remain reachable for remote control, do not expose it directly to the
   Internet; use the existing private/shared-folder arrangement instead.
3. Do not create, rename, delete, format, restore, or cancel a transfer.
4. Do not use `一括送信` (Send All). The manager warns that it erases all
   device data before repopulating it.
5. Do not modify or manually upload `VICDATA.bin`, `VICMEM.bin`, `VICLV.bin`,
   or `order.vnw`.
6. If the manager requests a password, reports an error, hangs, or shows a
   different operation than described here, stop and preserve the capture.

## Part A — Prepare the environment (no device write)

1. Create a new timestamped capture directory on the Mac. Do not reuse an old
   capture directory.
2. Shut down or snapshot the Win2000 VM before installing SnoopyPro. Copy the
   sniffer into the guest using the existing shared-folder/ISO method; this
   does not require guest Internet access.
3. Close InfoCarry Manager and any other program that may be using the
   InfoCarry. Do not perform a device transfer while installing the sniffer.
4. In SnoopyPro's **USB Devices** window, choose **File → Unpack Drivers**.
   Accept the default SnoopyPro directory if prompted. If it reports a
   missing driver file or asks to download an unknown file, stop and preserve
   the message.
5. Choose **File → Install Service** and accept the Windows service prompt.
   The “Snoopy's bridge is not available” message should clear after the
   service starts. If it does not, close and reopen SnoopyPro once; do not
   install the device sniffer until the bridge is available.
6. In the device list, select the InfoCarry entry containing
   `USB\\Vid_054c&Pid_001e` (not a `ROOT_HUB` entry). This is the device shown
   in the supplied screenshot. If duplicate identical rows appear, select
   the currently present entry and stop if installation does not change its
   status.
7. With the InfoCarry row selected, choose **Edit → Install sniffer**. If
   SnoopyPro does not restart it automatically, choose **Edit → Restart
   device** once. Wait for the row to disappear and reappear. This only
   re-enumerates the USB device; it is not an InfoCarry content transfer.
8. A USB log window should open. This automatically opened window is the one
   attached to the InfoCarry and should be kept. Do not use **File → New** if
   this window is already present; that creates a separate blank log which
   will not receive the device traffic. If no log window opens, do not start
   the manager; send a screenshot of the USB Devices window and status
   instead. If a log window is present, use **File → Save/Save As** to confirm
   that a native trace can be saved.
9. If possible, configure a filter for Sony VID/PID `054C:001E`; otherwise
   capture all USB traffic and filter during analysis.
10. Verify that the latest read-only backup is identifiable and stored outside
    the new capture directory. Never overwrite it.

## Part B — Validate capture with a safe read

1. Start a new SnoopyPro session before connecting the InfoCarry to Win2000.
2. Attach the device to the Win2000 guest and let the manager detect it.
3. Perform only a normal detect, read, selected receive, or backup-to-PC
   operation. Do not select any Send or Restore command.
4. Stop the capture after the read operation completes.
5. Save the automatically attached native log as `00-read-baseline` in the
   new capture directory. Do not use **File → New** when an attached log is
   already present; that menu item opens a separate blank log.
6. Confirm that the file is non-empty and record the SnoopyPro version, VM
   date/time, device VID/PID, and operation performed.

If this baseline capture cannot be saved, stop here. Do not proceed to a write
test until the capture problem is resolved.

## Part C — Select the single test item

1. In the manager's host-side carrying/transfer-source area, locate one small,
   already-existing manager-recognized item. Prefer one item in the
   `簡易メモ` (Simple Memo) category if present.
2. The item should already exist in the carrying area; do not author a new
   text file and do not alter the item's contents.
3. If the item exists only on the InfoCarry, use the manager's safe
   **Selected Receive** operation first, then select the resulting host-side
   copy. This receive step does not modify the device.
4. Ensure exactly one file/item is selected—not a folder, category, or entire
   device. Record its displayed name and path in the session notes.

## Part D — Explicit approval checkpoint

**STOP HERE.** The next operation changes the InfoCarry.

Do not continue until the user explicitly approves “one selected-send capture
using the original manager.” The approval must be given immediately before
starting Part E, after the backup and item selection have been checked.

## Part E — Capture one selected send (device-changing)

1. Keep the same attached SnoopyPro log that contains the baseline. Save a
   second copy as `01-selected-send` only after the selected send completes;
   this preserves the cumulative trace and avoids accidentally creating a
   blank File → New log.
2. In the manager, use:

   `転送` → `選択送信`  (Transfer → Send Selected)

   or the equivalent context action:

   `infoCarry端末へ送信`  (Send to InfoCarry terminal).

3. Confirm that the manager is sending the one selected item. Do not choose
   `一括送信`.
4. Allow the operation to finish normally. Do not click Cancel, unplug the
   device, or use an eject command during the transfer.
5. When the manager reports successful completion, stop SnoopyPro immediately.
6. Save the native capture without conversion or replay. Record the exact
   success message and start/stop times. If a same-name warning appears, stop
   and obtain explicit confirmation before accepting it; do not infer that an
   overwrite and a duplicate have identical protocol behavior.

## Part F — Close and preserve evidence

1. Do not perform another transfer in the same capture session.
2. Close the InfoCarry manager normally.
3. Shut down the Win2000 guest cleanly before releasing the USB device. If the
   guest becomes unresponsive, stop and report the state; do not force-eject
   or repeatedly reconnect the device.
4. Copy the native SnoopyPro sessions and notes to the Mac capture directory.
   Preserve the original guest copies as well.
5. Include:

   - `00-read-baseline` capture;
   - `01-selected-send` capture;
   - operation notes and timestamps;
   - item name/path and manager result;
   - SnoopyPro and Windows 2000 versions;
   - the identifier of the corresponding pre-test backup;
   - any manager log produced by the session.

Do not edit the capture files. Send the capture-directory path for offline
analysis; the modern toolkit will not transmit or replay it.

## Failure handling

- **No `選択送信` menu or context action:** stop and provide a screenshot of
  the manager window/menu; do not guess another command.
- **SnoopyPro cannot install or capture:** stop; do not force a driver or use
  USBPcap in Win2000.
- **Password prompt, transfer error, timeout, or hang:** preserve the partial
  capture and screenshot/message; do not retry automatically.
- **Device disappears after the operation:** leave the VM powered down and
  report the exact last manager message before attempting recovery.

## Expected result

The useful result is one native USB session containing the manager's command
`0x101b`, its ordered host-to-device ranges, and the completion response. A
successful capture will let us compare the observed range 5 and remaining
model ranges against the offline serializers without sending any modern
client-generated payload.
