# P17-014 — exact Library-package live attempt

Date: 2026-09-01
Base: canonical `main` at `9043c2db712fb6384b3769f549126fd004cb8b4c`
Risk: **R3 — device-state and one-shot write boundary**
Disposition: **FAIL CLOSED — aborted before hardware access**

## Scope and authorization

This record covers the single owner-authorized attempt to execute the exact
sealed P17-014 operation for
`root\\IC_P17_LIBRARY_20260831_03` and its reviewed TXT/BMP/TXT children. The
owner supplied the two exact P17-014 phrases after the host-only preflight
review. They were not consumed because the strict loader stopped before any
hardware callback. The approval is expired and must not be reused.

No other package, target, retry, delete, rename, restore, batch operation,
GUI/CLI transfer, or alternate mode was in scope.

## Observed safe failure

The runner was invoked from clean canonical `main`, but its offline setup
paired the P17-014 sealed report with the older P17-012 baseline backup. The
canonical P17-013 loader correctly rejected the reconstructed core with:

```text
core_preflight_seal_sha256 does not match the reconstructed core
```

The error occurred before the new live-attempt directory was created and
before the detection callback. No hardware callback ran. A separate
non-overwriting audit was then created to preserve this outcome:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-17-p17-014-library-package-canonical-loader-preflight-20260901-01/04-live-attempt-0001/`

The failure audit is
`03-result/offline-loader-failure.json`, SHA-256
`f59801c1b582a820c985a03663395ed8e9123dff911b68579a9b30940d7554d2`. The
one-entry preservation manifest is
`preservation-manifest-v1.json`, SHA-256
`3a293f48e790e5b6f055e4a3dc486b90a0c8704482497139dc0e57ddc42264ae`.
Neither artifact contains candidate, transaction, or device bytes.

The exact recorded counters are:

| Control | Result |
| --- | --- |
| device detection callbacks | 0 |
| capacity query callbacks | 0 |
| backup capture callbacks | 0 |
| `write_started` | `false` |
| sender calls | 0 |
| backend write calls | 0 |
| approval consumed | `false` |
| completion | none |
| `0x101b` transmitted | no |
| device mutation | no |
| automatic retry | no |

## Evidence classifications

- **Verified:** canonical `main` was clean at the stated commit; the P17-014
  sealed report failed the strict loader when paired with the wrong offline
  baseline; the external failure audit and its hash manifest verify; no USB
  callback or sender path was reached.
- **Observed:** the host process returned the exact core-seal mismatch shown
  above and created no live-attempt evidence until the post-failure audit was
  preserved.
- **Inferred:** because the loader failed before its detection callback and
  the audit counters are zero, the InfoCarry was not accessed by this attempt.
- **Unresolved:** physical compatibility, completion semantics, post-write
  persistence, and physical opening of the three children remain untested.

## Disposition and required follow-up

This is a safe host-preparation failure, not a device result. Do not retry
under the expired phrases. A later correction must load the P17-014 report
with the P17-014 preflight backup, independently review that correction, and
perform a new fresh read-only preflight before requesting new exact approval.
No claim is made about the device state or the physical package.
