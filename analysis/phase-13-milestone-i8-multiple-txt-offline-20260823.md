# Milestone I.8 — offline multiple-TXT package

Date: 2026-08-23
Status: **Logical offline model complete; device candidate blocked.**

The new `infocarry.prepared_multi_text` model extends the existing strict
UTF-8 → CP932/CRLF authoring boundary to an explicitly ordered list of at least
two TXT children. It is source-bound and deterministic, performs no USB
operation, and never constructs a dynamic device blob or Manager sidecar.

## Supported logical scope

- one named root-level package folder;
- two or more ordered TXT children;
- strict UTF-8 source decoding;
- strict CP932 encoding;
- CRLF normalization;
- embedded NUL and unsupported-character rejection;
- case-insensitive child-name conflict rejection;
- unique source-path enforcement;
- source SHA-256, encoded payload SHA-256, order, paths, sizes, and wrapper
  requirements in the manifest;
- non-overwriting export to a new offline directory.

The logical lower-bound accounting is explicit: two structural records for the
folder and observed leading marker, one metadata record per child, one native
32-byte wrapper requirement per TXT child, and four-byte alignment for each
wrapper-plus-payload segment. This is an estimate only. Exact native growth,
record offsets, timestamps, fixed-state transformations, capacity binding, and
transaction hashes are not fabricated.

## Compatibility boundary

The manifest reports preparation and ordered multiple-TXT authoring as ready
offline. It reports root-folder construction, multi-record device construction,
and USB operation as blocked. I.7 found no independently verified timestamp or
fresh fixed-state rule, and capture 7 proves only the one-folder/one-child
fixture. No package action is connected to the normal CLI or ttk interface.

Focused synthetic tests cover deterministic ordering, hashes, sizes, strict
authoring errors, duplicate/case-conflicting names, duplicate source paths,
source changes, non-overwriting export, and USB neutrality. Copyrighted owner
source material is not copied into the repository.
