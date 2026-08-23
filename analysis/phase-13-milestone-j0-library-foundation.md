# Milestone J.0 — local Library foundation

Status: complete in the sanitized source-of-truth checkout.

## Scope

The Library foundation is a framework-independent catalog for original local
source files. The initial supported import is one regular UTF-8 `.txt` file per
logical item. The catalog does not copy, move, edit, overwrite, or delete the
source. It performs no USB operation and does not construct a device
transaction.

Unsupported extensions remain visible as `unsupported`. A `.txt` file that
cannot be decoded as UTF-8 remains in the catalog as `blocked`; its original
bytes and path are not replaced.

## Catalog format and storage

The serialized format is `infocarry-library-v1`, version `1`, with deterministic
sorted JSON keys and a sorted item list. The default per-user macOS location is:

`${HOME}/Library/Application Support/SonyInfoCarryModernManager/library.json`

Tests inject a temporary path. The catalog is outside the repository and
outside reverse-engineering evidence. Writes use a same-directory temporary
file, flush and `fsync`, atomic replacement, directory synchronization where
available, and a recoverable `library.previous.json` copy of the prior catalog.
Malformed or unsupported catalogs are rejected without repair or overwrite.

Each item records a stable source identity, original path and filename, import
time, original SHA-256 and size, detected format, support/state fields,
preparation fields, target names and prepared-manifest fields when available,
current observation status, validation error, and an observation history.
Unchanged present-source imports are true no-ops. Changed or missing sources
retain the original catalog identity and hash while becoming stale; removal
removes only the catalog entry.

## Verification

Focused coverage is in `tests/test_library.py` and covers identity/hashes,
idempotent import, unsupported and invalid sources, changed/missing detection,
non-destructive removal, atomic previous-version preservation, malformed
catalog rejection, duplicate/version checks, preparation metadata, and
directory rejection. The portable sanitized suite passes 373 tests with the
three intentional evidence-dependent skips.

This slice does not claim prepared-package readiness, folder transfer
eligibility, or any live operation. Those remain later Milestone J.1 and
transfer-safety gates.
