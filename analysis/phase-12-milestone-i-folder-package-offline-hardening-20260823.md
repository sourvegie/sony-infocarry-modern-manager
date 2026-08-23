# Milestone I.3 — offline folder-package hardening

Date: 2026-08-23
Status: **Complete for the capture-7 offline fixture boundary; fresh package
construction and all live package actions remain blocked.**
Implementation commit: `465120f` (`Harden offline folder fixture boundaries`)
Evidence source: capture-7 exact fixture, recorded in
`analysis/phase-12-milestone-i-folder-package-capture7-20260823.md`.

## Hardened behavior

The offline folder builder now validates the preserved post-capture template
before using it. The template must retain every baseline reachable path,
shared record identity, native text prefix, and shared file payload, and must
contain exactly the three additional metadata records represented by capture
7. A changed shared payload or an unexpected path is rejected before a
candidate is returned.

The focused tests explicitly cover:

- the observed root child-table-width update and exact boundary pointer
  rebasing;
- empty and one- through four-byte CP932/CRLF payload alignment boundaries;
- deterministic candidate and audit output;
- explicit timestamp and complete baseline timestamp-map requirements;
- unsafe names, unmappable text, and captured-shape rejection; and
- rejection of a template that changes a shared payload.

The transfer-plan preview now labels the exact capture-7 one-folder/one-TXT
reproduction as an offline proven primitive while listing fresh timestamp
generation, fresh fixed-state derivation, exact growth/capacity semantics,
request-4 completion decoding, and live package transaction as blocked
primitives. It remains ineligible and includes no candidate bytes or USB
operation.

## Verification

The focused folder and transfer-plan suite passes **10 tests**. The complete
canonical suite passes **301 tests**. `git diff --check` is clean. The
pre-existing `test_text_authoring.py` invalid-escape `SyntaxWarning` remains
unchanged and does not affect the result.

No original capture, backup, fixture, Manager sidecar, or read-only toolkit
file was modified. The implementation is a pure offline fixture-boundary
hardening slice; it does not authorize or expose a package sender.

## Remaining boundary

The builder still requires a preserved capture-shaped template and an
explicit timestamp map. This is deliberate: the available evidence does not
establish a general timestamp rule, fresh fixed-state derivation, folder
capacity semantics, or trustworthy native request-4 completion decoding.
Capture-7 exact reproduction must not be presented as arbitrary fresh-backup
eligibility. Milestone H.1 remains parked, Milestone J remains deferred, and
no live hardware operation is required for this slice.
