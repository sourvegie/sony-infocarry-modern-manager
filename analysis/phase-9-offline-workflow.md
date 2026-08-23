# Phase 9 — offline workflow foundation

Date: 2026-08-21

The first Phase 9 slice is device-independent and can be used against any
complete raw backup archive.

## Inventory

`infocarry inventory` validates the backup manifest and dynamic-blob hash,
parses the record tree, and reports reachable directories/files, paths,
read-state flags, payload lengths, native prefix sizes, and payload hashes.
The report contains no payload bytes and can be saved only into a new
directory.

## Text preview

`infocarry preview-text BACKUP RECORD UTF8_TEXT_FILE` reads the source text as
UTF-8, normalizes all line endings to CRLF, applies strict CP932 encoding, and
optionally enforces a caller-supplied encoded-byte limit. It reuses the
existing replacement audit, verifies the target is a reachable `txt` record,
and preserves the native prefix in the audit metadata. The report contains
hashes and invariants only; it does not save a candidate blob or contact USB.
The raw backup blob is decoded VICDATA, so the CLI applies the already verified
in-memory XOR involution before calling the manager-side preview; no transformed
bytes are written.

## Safety boundary

Both commands refuse to overwrite report directories. They are suitable for a
future desktop front end: the inventory supplies browse rows, and the preview
supplies capacity/encoding warnings before a separate, still-gated transfer
plan is created. The write authorization phrase and fresh-backup binding are
unchanged.
