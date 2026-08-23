# Phase 9 — v0.1 desktop usability check

Date: 2026-08-22

The project owner performed a manual smoke test of the canonical Tkinter/ttk
desktop manager from the supported Python 3.12.13/Tcl-Tk 9.0 environment.
The four main toolbar actions were exercised and reported working normally:

- **Check device** — device-status check;
- **New backup…** — complete read-only backup workflow;
- **Open backup…** — loading an existing complete backup; and
- **Download selected…** — selected file/folder export.

The same usability pass confirmed that the folder tree follows the encoded
device child order rather than alphabetical order. A BMP record was then
selected and its image preview was confirmed working after the preview path
was changed to Tk pixel-row rendering. The preview remains read-only.

This is user-reported smoke-test evidence, not a claim of broad hardware or
macOS compatibility. Automated offline verification remains 199 passing tests
and does not access USB. A signed/notarized package, support-matrix testing,
and a release-package smoke test remain open under risk R9.
