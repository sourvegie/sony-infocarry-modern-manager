# Phase 7 — Manager-produced sidecar fixture procedure

Date: 2026-08-21

This procedure is for collecting evidence only. It must not use the legacy
manager's Send, Restore, Upload, or device-initialization functions.

## Required output

Create a new, timestamped directory under:

`${RESEARCH_ROOT}/fixtures/`

Copy the complete manager-created memo working directory into it, preserving
the files exactly. The useful names are:

- `VICDATA.bin`
- `VICMEM.bin`
- `VICLV.bin`
- `order.vnw`

If the manager stores these in separate directories, preserve that directory
structure instead of flattening or renaming files. In the observed layout,
the expected relative paths are:

```text
Memo/VICMEM.bin
Memo/VICLV.bin
Backup/VICDATA.bin
ICM/order.vnw
```

The `order.vnw` file does not need to sit beside `VICDATA.bin`; its `ICM`
location is acceptable as long as it was produced by the same receive session.
Include any companion manifest or log that the manager creates.

## Safe collection sequence

1. Keep the existing verified raw backup as the recovery baseline. Do not
   overwrite it.
2. Start from a fresh snapshot or disposable copy of the legacy Windows
   environment. This keeps registry settings and temporary files attributable
   to this one run.
3. Connect the InfoCarry and use only the manager's receive, read, download,
   or backup-to-PC workflow. Do not choose any operation that sends data,
   restores content, formats the device, or changes device settings.
4. Before closing the manager, locate the memo working directory. The DLL
   contains the path suffix `\\Sony\\infoCarry\\Memo` and the sidecar names
   above; use those strings to locate the generated files if the UI does not
   show the path. Locate `order.vnw` by its exact filename.
5. Copy the files to the timestamped fixture directory. Do not edit them,
   open-and-save them in an editor, or let a cleanup utility run first.
6. If possible, make a second copy of the same fixture directory and compare
   the copies byte-for-byte. Keep both the fixture and the original Windows
   snapshot.
7. Disconnect the device normally. No host-side write request is part of this
   procedure.

## What to provide for analysis

Provide the timestamped fixture directory and identify which existing
read-only raw backup corresponds to the same device state. The toolkit can
then hash every sidecar, parse the headers, correlate paths and record
offsets, and test the `ecd` extension branch without changing any source or
device data.

Two fixtures are now present and are documented in
`analysis/phase-7-fixture-inventory.md` and
`analysis/phase-7-fixture-2-comparison.md`. Static loop tracing separately
resolves manager ordering and collision behavior. Auxiliary words, tail dword
`0x104`, and XOR stability across genuinely different `VICDATA.bin` content
remain intentionally unresolved. For a repeatable offline check, use the
`fixture-report` command documented in `analysis/phase-7-fixture-report.md`.
