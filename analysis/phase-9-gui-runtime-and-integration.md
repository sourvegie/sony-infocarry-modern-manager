# Phase 9 — Desktop Runtime and Conversion Integration Decision

Status: approved and implemented as the Milestone B foundation (2026-08-22).

## Approved desktop stack

The user approved the existing Python desktop direction:

- Tkinter/ttk for the native desktop interface;
- the canonical project's Python 3.12.13 virtual environment;
- Tcl/Tk 9.0;
- no local browser interface and no Qt/PySide migration at this stage.

`src/infocarry/runtime.py` checks the interpreter and Tk versions before a
window is created. The macOS system Python 3.9/Tk 8.5 path is rejected with a
recovery message instead of opening the previously observed blank window.
`pyproject.toml` declares Python 3.12 or newer, while the release-tested
environment is pinned operationally to Python 3.12.13/Tk 9.0.

## Safe integration architecture

The canonical application and `${INFOCARRY_TOOLKIT_ROOT}`
both use a top-level package named `infocarry`. The conversion project is
currently dirty and remains read-only. It must not be installed beside this
project or copied over it blindly. Integration is therefore staged at module
boundaries:

```text
canonical infocarry package
├── device/transport/protocol     USB discovery and read-only commands
├── backup/backup_format          verified raw backup and lossless export
├── conversion/                   future extracted text/EPUB/BMP services
├── desktop_ttk.py                Device Manager (Tkinter/ttk)
└── future app shell               shared tabs and settings/recovery help
```

The eventual user-facing application will contain four explicit areas:

1. **Device Manager** — connection status, verified backup, tree browsing, and
   selected read-only download/export;
2. **Text Converter** — the existing conversion project's reusable text
   normalization and CP932 preparation, imported only after a clean source
   snapshot and namespace review;
3. **Ebook Renderer** — EPUB/TXT extraction and deterministic 240 x 320,
   1-bit BMP pagination, kept independent from USB transport;
4. **Settings and recovery help** — runtime checks, destination policy,
   backup/retry guidance, and later platform-specific permissions.

The first integration slice is intentionally only Device Manager. Conversion
services remain a read-only reference until their uncommitted changes are
reviewed and their package names are mapped into the canonical namespace.
This avoids duplicate `infocarry` installations and keeps the protocol core,
conversion core, and UI independently testable.

## Milestone B implementation boundary

`desktop_ttk.py` provides a `ttk.Treeview` hierarchy rather than the old
canvas with one button per record. It exposes only:

- VID/PID-only device status checking;
- complete backup loading and validation;
- one-click device-to-computer backup with progress, cancellation, and
  preserved incomplete archives;
- selected file/folder export into a new destination;
- read-only TXT preview and clear recovery messages.

The tree follows the insertion order recovered from each directory's stored
child table, so it does not alphabetize siblings. The detail pane also renders
the preserved uncompressed 1-bit BMP records through a dependency-free
read-only decoder; unsupported image variants are reported rather than
guessed.

No GUI or CLI path calls the isolated writer. Live backup is still opt-in and
must be explicitly approved before it is run; routine tests use preserved
fixtures and synthetic transport responses.
