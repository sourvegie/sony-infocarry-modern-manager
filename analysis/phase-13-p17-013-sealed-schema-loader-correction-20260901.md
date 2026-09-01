# P17-013 — Sealed-report loader schema correction

Date: 2026-09-01
Base: canonical `main` at `3c1ec5c76dff2417a3d13cdef598401fc086ebd8`
Risk: R3 — sealed authorization and future one-shot write boundary
Disposition: **READY_FOR_HARDWARE_TEST** after independent review, CI, and merge; no hardware is authorized by this correction

## Trigger and preserved failure

P17-012 attempt 03 stopped offline before hardware access. The loader used by
that attempt expected `transaction_sha256` at the top level of the sealed
report. The canonical P17-012 producer and the preserved sealed report bind
the prospective transaction at the exact nested path
`authorization.candidate_transaction_sha256`.

The external non-overwriting evidence root
`/Users/stardust/Projects/InfoCarry-Evidence/phase-17-p17-012-library-package-live-execution-20260901-03/`
is preserved outside Git. Its `offline-loader-failure.json` records the safe
pre-hardware outcome: `write_started=false`, `sender_calls=0`,
`backend_write_calls=0`, `approval_consumed=false`, no completion, no
`0x101b`, no mutation, and no retry. The raw file and its verified
preservation manifest were not changed. No prior approval phrase is reused or
requested in P17-013.

## Schema authority and correction

The schema was checked against four sources: the live-preflight producer's
`to_dict()`/audit construction, `PreparedLibraryPackageLivePreflight.verify_seal()`,
the P17-012 sealed report, and the P17-012 sanitized dossier/review. The
sealed report has one exact top-level field set, including execution-state
flags (`approval_consumed`, `sender_calls`, `backend_write_calls`,
`write_started`, `completion`, and `zero_x101b_transmitted`). The
transaction identity is not a top-level field. The nested authorization
object is compared in full with the reconstructed authorization, so its
candidate transaction binding and every other authorization field remain
covered by the existing core seal.

The isolated adapter now exposes
`load_prepared_library_package_live_preflight()`. It:

1. loads JSON with duplicate-key rejection at every object level;
2. requires the exact P17-012 top-level key set, rejecting missing fields and
   stale or contradictory top-level aliases;
3. validates all read execution-state scalars, supported phrase/policy types,
   digest syntax, and the bounded new-record timestamp;
4. reconstructs the candidate using the existing Library bridge from the
   caller-supplied verified backup, parsed reviewed template, capacity
   response, catalog, and selected item;
5. compares `authorization.candidate_transaction_sha256` with the
   independently reconstructed transaction and requires the reconstructed
   core and outer seals to match; and
6. returns the sealed preflight only after the existing full seal verifier
   passes.

There is no fallback alias, silent field discard, candidate-byte authority,
hardware callback, sender construction, approval consumption, or transmission
path in this loader. The producer now records read-only detection/capacity/
backup as `hardware_accessed=true` and
`read_only_hardware_accessed=true`; write and USB-transmission flags remain
false, matching the P17-012 report's semantics.

## Regression coverage

The focused live-adapter tests use the exact P17-012-shaped report, including
the P17-011 operation phrases recorded in that historical sealed report. They
cover:

- valid nested transaction binding and exact seal replay;
- missing nested transaction hash;
- top-level-only stale alias;
- contradictory top-level alias alongside the nested field;
- malformed nested digest;
- valid-format but mismatched nested digest; and
- duplicate JSON keys.

Each failure is exercised with the injected capture/backend counters and
proves that loading performs no new backup callback, sender call, approval
consumption, or transmission. Existing one-shot, no-retry, pre-send failure,
post-start indeterminate, and GUI/CLI isolation tests remain in the suite.

## Evidence classification and boundary

- **Verified:** the canonical nested transaction path; strict top-level
  schema; duplicate/alias/malformed/mismatch rejection; reconstruction and
  seal equality against the preserved P17-012 report; no hardware activity;
  and focused regression behavior.
- **Observed:** the P17-012 attempt-03 safe loader abort and its preserved
  audit values, as recorded outside Git.
- **Inferred:** a future live attempt can reach its existing one-shot gates
  from a loaded report when all fresh device, capacity, backup, package, and
  approval bindings independently revalidate.
- **Unresolved:** physical compatibility, native numeric completion meaning,
  operation-specific capacity semantics, and interrupted-write recovery.

P17-013 is host-only. It is **READY_FOR_HARDWARE_TEST** only after this
correction has passed independent R3 review, complete validation, CI, and
merge. The complete portable suite passes with 609 tests and 3 intentional
evidence-dependent skips; `git diff --check`, compilation, and the
external-evidence exclusion audit also pass. A later task must perform a new
fresh read-only preflight and obtain new exact operation-specific approval.
No sender was constructed and no hardware, `0x101b`, retry, or prior phrase
was used here.
