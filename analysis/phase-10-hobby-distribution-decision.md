# Phase 10 — hobby distribution decision

Date: 2026-08-22

The project owner confirmed that Sony InfoCarry hardware is rare and the
modern manager will be used by a very limited hobbyist audience rather than
commercially distributed. For that release profile, Developer ID signing and
Apple notarization are not required to complete v0.1.

The accepted v0.1 delivery is the canonical source checkout plus the
reproducible Python wheel, supported by the pinned Python 3.12.13/Tcl-Tk 9.0
runtime, the user guide, 199 offline tests, and the completed manual read-only
GUI smoke test. An unsigned or ad-hoc-signed `.app` may be added later as a
launching convenience.

This is a scope decision, not a claim that unsigned software provides the same
installation experience as Developer ID distribution. Apple documents
Developer ID signing and notarization as the mechanism for Gatekeeper-friendly
software distributed outside the Mac App Store:

- https://developer.apple.com/support/developer-id/
- https://developer.apple.com/documentation/xcode/distributing-your-app-for-beta-testing-and-releases/

If the audience broadens or non-technical third parties download the app, the
project must reopen R9 and add Developer ID signing, notarization, supported
macOS-version testing, and a packaged release smoke test before calling that
distribution supported.
