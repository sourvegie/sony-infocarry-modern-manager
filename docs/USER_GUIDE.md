# Sony InfoCarry Manager — user guide

The manager provides a read-only recovery workflow and one separately guarded
v0.2 operation: replacing the contents of one already-existing TXT record.
No new-file creation, delete, rename, restore, firmware, unlock, alternate
mode, or bulk replacement is available.

## Supported setup

- Verified device: Sony InfoCarry VNW-V15 (`VID 054c`, `PID 001e`). Other
  models are not claimed to be compatible.
- Verified development runtime: Python 3.12.13 with Tcl/Tk 9.0.4,
  `PyUSB==1.3.1`, and macOS 26.5.2 on arm64.
- The system Python 3.9/Tk 8.5 path is unsupported. The desktop command
  stops with a recovery message when it detects an older runtime.
- The conversion project at `${INFOCARRY_TOOLKIT_ROOT}`
  remains a separate, read-only project. Its conversion tabs are not yet
  integrated into this manager.

This limited-audience hobby release uses the project virtual environment or
reproducible wheel. Developer ID signing and notarization are optional future
distribution work, not a v0.1 requirement. Broader public distribution would
require reopening that gate and testing an explicit macOS support matrix.

## Start the manager

From the canonical repository:

```sh
cd ${PROJECT_ROOT}
.venv/bin/infocarry desktop
```

If the window is blank or the old Tk deprecation warning appears, close it and
launch with the command above. Do not use the macOS system `python3`.

## Library review layout

The supported Library review geometry is a minimum of `980x680` pixels and a
default opening size of `1120x760`. The toolbar uses separate grouped rows for
**Import / prepare**, **Offline review**, and the **Experimental boundary —
review only**. The persistent Experimental notice and bottom status wrap when
the window narrows. The Library list/detail divider is user-adjustable; its
pane minima are 360 and 440 pixels, enforced on resize and sash release. The
table uses concise filenames,
shape, state, and target values. Select an item to see full paths, hashes,
ordered children, and diagnostics in the scrollable detail report.

For the human visual check, open the Library tab at `980x680`, confirm every
action label, the no-send notice, the table headers, the detail heading, and
the bottom status are readable, then drag the sash toward each pane in turn.
Resize to `1120x760` or larger and confirm the same information remains
visible without losing selection or keyboard focus. The Experimental review
must continue to show no approval or send control.

## Read-only workflow

1. Connect one InfoCarry and close the legacy Windows manager before starting
   a read operation.
2. Click **Check device**. This performs VID/PID enumeration only; it does
   not claim the interface or send a content command.
3. Click **New backup…**, choose a destination folder, and wait for the
   progress bar to finish. The manager creates a new timestamped directory,
   preserves every raw object, writes hashes and protocol metadata, and
   verifies the completed archive. Never choose an existing backup directory.
4. Click **Open backup…** and select the complete backup directory produced in
   step 3. A preserved fixture or previously completed backup can be opened
   the same way without connecting the device.
5. Browse the hierarchy. Sibling order follows the order stored in the
   device's directory child tables; it is not an alphabetical sort.
6. Select a TXT file to view its decoded read-only text. Select a supported
   uncompressed 1-bit BMP record to view its image. The preview never writes
   back to the backup or device.
7. Select one or more files/folders and click **Download selected…**. Choose
   a parent folder. The manager creates a new timestamped export directory
   containing native bytes, decoded views where available, and a manifest.

## Guarded existing-text replacement (v0.2)

Use this only when the device is connected directly to the modern client and
the legacy Manager is closed. The operation changes exactly one existing TXT
record and always creates two new backup directories: one before the write and
one after it.

1. Open a complete backup and select exactly one existing TXT record.
2. Click **Preview replacement…**, choose a local UTF-8 text file, and inspect
   the offline report. It must show the expected path, record offset, strict
   CP932/CRLF conversion, source and encoded sizes, and no device access.
3. Click **Replace selected text…**. Choose a parent folder for the before and
   after backups.
4. Read the warning and type exactly `REPLACE INFOCARRY TEXT`. A checkbox or a
   generic acknowledgement is not accepted.
5. Leave the device connected and wait for the fresh backup, bounded transfer,
   and complete read-back verification to finish. The result must show the
   completion word and all three independent verification checks as passed.

If the operation stops after the write begins, do not click the action again.
Keep both backup directories, preserve the error message, and perform only
read-only detection or backup checks until the discrepancy is reviewed. The
client never retries an interrupted or failed write automatically.

The status line and progress bar report completion, cancellation, and
verification. Keep the original backup unchanged as the recovery source.

### Why a selected transfer can take as long as a larger transfer

Selecting one item limits the intended library change; it does not make the
USB operation a small per-file copy. The InfoCarry ordinary-write protocol
transmits a complete candidate library image even when only one selected item
is added, replaced, or removed. Transfer time is therefore governed mainly by
the complete device model and USB speed, not by the selected TXT or BMP size.
Do not disconnect the device merely because a small selected file appears to
be taking longer than expected.

## Recovery and troubleshooting

- **Device not detected:** close the legacy manager, reconnect the device,
  and click **Check device** again. Connect only one InfoCarry.
- **Disconnect or timeout during backup:** preserve the incomplete output and
  create a fresh backup in a new destination. If it occurs after the guarded
  replacement begins, do not repeat the write automatically; keep the before
  and partial after evidence for review.
- **Malformed or incomplete backup:** keep the original directory, do not
  overwrite it, and open a newly completed backup instead.
- **Permission error:** choose a folder writable by the current macOS user.
- **Insufficient disk space:** choose a destination on a volume with more
  free space. Backups and exports are never silently truncated.
- **Cancellation:** allow the status to settle, keep the partial output for
  diagnosis, and start a new operation in a new directory.
- **Unsupported runtime:** use the canonical `.venv/bin/infocarry desktop`
  command and confirm that it reports Python 3.12/Tk 9.0 or newer.

Do not unplug the device while a read is active. Do not run the legacy manager
and this client against the device at the same time. If a process becomes
unresponsive, close both applications, reconnect the device, and perform only
read-only detection or backup checks.

## Deliberate limitations

The Text Converter and Ebook Renderer tabs are offline-only first slices; full
EPUB/MOBI parsing and font-backed page rendering remain separate milestones.
All device operations outside the single existing-TXT replacement remain
blocked by the project risk register.

## Offline conversion tabs

The **Text Converter** tab accepts a UTF-8 TXT file and previews the strict
CP932/CRLF authoring result without connecting to the device. **Export offline
package…** creates a new directory containing the CP932 text, a UTF-8 archival
copy, deterministic logical page text files, and a manifest. Existing output
directories are never overwritten.

The **Ebook Renderer** tab currently previews the logical page plan using the
240 × 320 / 1-bit target profile. It does not yet parse EPUB/MOBI files or
claim font-backed BMP page rendering. Those remain offline follow-up work and
do not change the guarded device workflow.

The **Settings & Help** tab records the supported runtime/device and the
recovery rule: after a started write stops, preserve the evidence and do not
retry automatically.
