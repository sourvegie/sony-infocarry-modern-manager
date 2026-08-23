# Phase 8 — sidecar synchronization boundary

Date: 2026-08-21

The toolkit now performs only exact, evidence-backed sidecar mutations. All
functions are offline and return new bytes; none opens USB or edits the
preserved legacy package.

## `VICMEM.bin`

Existing-file rename replaces exact NUL-terminated selected paths while
preserving post-NUL scratch bytes and tail dwords. Leaf delete removes exact
matching paths while preserving section headers, auxiliary bytes, and tail
fields.

## `VICLV.bin`

The recovered file is a sequence of category byte + 260-byte path fields.
`replace_viclv_exact_path()` and `remove_viclv_exact_path()` now update/remove
only exact path matches, retaining category values, entry order, header bytes,
and opaque post-NUL padding. The manager bundle rename/delete wrappers invoke
these helpers in addition to the corresponding `VICMEM` update.

This is deliberately not a new-file category policy: static evidence shows
categories 1 and 2 derive from parity of unresolved internal record words, so
the toolkit does not guess which category to append for a newly authored file.

## `order.vnw`

The legacy manifest stores generated basenames, not full relative paths. Its
counter, extension override, collision probe, and metadata-order traversal are
implemented as pure helpers. Rename/delete therefore retain `order.vnw`
byte-for-byte; generating or removing entries requires a manager-produced
fixture that establishes the exact lifecycle and collision behavior for the
changed content set.

## Remaining evidence request

No additional capture is needed for the ordinary existing-file replacement
path. To finish arbitrary add/delete synchronization, the smallest useful
read-only evidence is one fresh manager-produced bundle containing a newly
created file in a directory that already has `VICLV` and `order.vnw` entries,
plus the post-operation backup. A legacy manager operation would be used only
to create that evidence; the modern sender remains gated and unchanged.
