# Current Project Status

Date: 2026-08-30
Canonical checkpoint: `c1cf621` (`Merge workflow migration W-001/W-002`)

## Portable offline validation

- 524 passing tests
- 3 intentional evidence-dependent skips

These are host/offline results only. They do not claim physical-device verification.

## Proven or delivered scopes

- Canonical sanitized repository established as the development source of truth.
- Read-first modern manager, backup, browsing, export, and preview workflows delivered for the supported VNW-V15 scope.
- Constrained existing-text replacement has passed its approved guarded live scope with read-back evidence.
- One narrowly scoped root-level TXT creation path has passed an approved live smoke with read-back evidence.
- One constrained one-folder/one-TXT package path has passed an approved live smoke with read-back evidence.
- Selective-delete modeling/hardening has completed its supported offline structural scope, and one constrained modern root-level TXT delete smoke has passed with independent read-back.
- Local Library foundation and offline Prepare workflow exist; normal generalized transfer remains disconnected from the product workflow.
- Ordered multi-child TXT and mixed TXT/BMP logical preparation, candidate construction, authorization binding, fake-only workflow, readiness preview, and independent offline read-back exist for their defined offline scopes.

## P15 status boundary

Capture 01 remains preserved outside Git as historical native evidence. The
earlier P15-001 modern dossier was prematurely classified and is now retained
as **IMPLEMENTATION_READY** historical material; it must not be used as an
executable operation. Its native legacy operation-wide timestamp rewrite and
child-4 one-second serialization remain observed behavior, not normalized into
the modern candidate policy. The native numeric request-4 word remains
unresolved, while the owner-supplied normal Manager return and complete
post-backup persistence remain explicitly recorded as non-contradictory
observed/verified evidence.

P15-002 now has a distinct `_02` root destination, rebuilt source/path/order,
capacity, candidate, authorization, transaction, and verification bindings
from the latest preserved Capture 01 post-state. Its isolated live runner is
host-tested only through injected fake hardware boundaries, is not exposed by
the normal CLI or GUI, and is **READY_FOR_HARDWARE_TEST** after R3 review.
No modern `0x101b` transaction has been performed. Any later hardware test
requires a new complete backup, revalidation of all exact bindings, and a new
operation-specific owner approval; this status document does not authorize it.

## P15-001 native evidence checkpoint

The sanitized four-child package and operation-specific legacy Manager
procedure are recorded at
`samples/generated/P15-001-native-multi-chapter-txt/` and
`analysis/phase-15-p15-001-native-multi-chapter-txt-evidence-protocol-20260828.md`.
The package is one new root folder with four 120-byte, ASCII/CP932-compatible
CRLF TXT children in explicit order. Exact source hashes and a preservation
manifest template are included. No backup, capture, candidate, transaction,
or private device data is in the repository.

Capture 01 was supplied from the approved owner path and preserved at
`/Users/stardust/Projects/InfoCarry-Evidence/phase-15-p15-001-native-multi-txt-20260828-01/`.
The four child payloads, folder/parent-marker relationships, capacity fit,
fixed-state objects, and native range-to-post-blob equality are verified in
`analysis/phase-15-p15-001-native-multi-chapter-txt-capture-01-results.md`.
The owner event mapping and Project Lead timestamp decision are recorded, and
the constrained candidate/authorization/verifier dossier is reviewed
offline. Raw evidence remains outside Git and no modern hardware transaction
was performed.

## Current product safety boundary

Normal product-facing controls remain disabled for:

- generalized/new arbitrary package transfer;
- generalized deletion;
- bulk/destructive synchronization;
- restore;
- firmware/unlock and alternate modes.

Do not intentionally test interrupted-write recovery on the only valuable unit. Physical write atomicity and recovery remain unproven.

## External/hardware boundaries still unresolved

- physical modern multi-child compatibility beyond the prepared dossier;
- newly constructed mixed TXT/BMP live compatibility;
- generalized deletion beyond the exact supported smoke scope;
- physical interrupted-write atomicity, rollback, and recovery;
- broader arbitrary/nested package behavior.

## Development priority

Preserve functional parity and proven transfer-safety boundaries before investing in aesthetic polish or broad transfer exposure. Continue offline engineering only where requirements/evidence support deterministic fail-closed behavior. Do not use additional model reasoning as a substitute for missing native evidence.

## Next approved engineering task

Obtain a separate operation-specific owner approval for the exact P15-002
`_02` modern smoke, then perform only its read-only fresh-backup preflight and
revalidation. A later write may send at most one `0x101b` transaction, accepts
only explicit `0x0000`, and treats interruption, timeout, disconnect, missing,
ambiguous, malformed, or nonzero completion as terminal with no retry. No
modern `0x101b` transaction is authorized by this status document.

## Canonical reading order

1. `AGENTS.md` — compact operational rules for coding agents.
2. `CURRENT_STATUS.md` — this current snapshot.
3. `WORKFLOW.md` — human/AI task lifecycle, risk, review, and verification rules.
4. `PRODUCT_VISION.md` — stable product scope.
5. `RISK_REGISTER.md` — material safety and release risks.
6. `ROADMAP.md` — longer-term milestone/history record.
7. Relevant `analysis/` files only when the task needs their evidence.
8. `README.md` for setup, commands, and current supported developer/user entry points.

Update this file after meaningful verified checkpoints. Keep historical detail in `ROADMAP.md` and `analysis/` rather than growing this document into another project diary.
