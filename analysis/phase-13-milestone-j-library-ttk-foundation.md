# Milestone J — crude ttk Library foundation

Status: complete for the local import/prepare slice; device transfer remains
disconnected.

The existing Tkinter/ttk desktop application now has a separate `Library` tab
with:

- a Library item Treeview showing item state, source path, and prepared target;
- `Import TXT…`, which uses a file picker and records one source non-
  destructively;
- `Remove from Library`, which removes only the catalog entry after explicit
  confirmation and never deletes the source;
- `Prepare…`, which asks for one root folder and one TXT child and invokes the
  framework-independent offline Prepare workflow;
- a read-only item/audit pane and status area that identify the source hash,
  prepared manifest, target, errors, and the explicit no-device-change state.

The tab exposes no package Transfer, Send, Upload, delete, restore, sync, or
live-runner control. It does not place USB logic in ttk handlers. The existing
Device Manager, read-only backup, preview, and guarded existing-text workflow
remain separate.

The UI is intentionally crude and file-picker based. Drag-and-drop, EPUB/MOBI,
PDF/BMP packages, directories, multiple children, and routine package transfer
remain later gated work. The application uses the candidate checkout's approved
Python 3.12.13/Tcl-Tk 9.0 environment; no InfoCarry-Toolkit package is
installed or imported.

Focused coverage includes the Library catalog, offline Prepare, and explicit
offline UI audit formatter. The complete portable suite passes 379 tests with
the three intentional evidence-dependent skips. A GUI smoke is deferred to
owner usability review; no hardware operation was performed.
