# Phase 9 — no-write desktop shell

Date: 2026-08-21

The first desktop slice is intentionally offline. `infocarry desktop` opens an
optional Tk window backed by `DesktopWorkflowModel`.

It can:

- load and validate a complete raw backup;
- display reachable record paths, kinds, sizes, and read states;
- select a reachable text record;
- choose UTF-8 source text and run the strict CRLF/CP932 preview; and
- save an inventory or preview report into a new directory; and
- perform a VID/PID-only device check from the **Check device** button.

The shell was exercised against `analysis/phase-8-live-after-4`, loading the
complete backup and showing its reachable records. On the system Tk build
available on macOS, long native-button rows can overlap near the top of the
scrollable list; this is cosmetic and does not change the selected offsets or
any offline model result. A reproducible export check is recorded in
`analysis/phase-9-export-check-1.md`.

The device check performs enumeration only; it does not claim an interface,
send an application command, or expose a write path. The shell has no
device-write button and no candidate-blob export. Headless installations can
still use the CLI and model APIs because Tk is imported only when the `desktop`
command is invoked. The separately gated transfer workflow remains a later
milestone.
