# Phase 8 — Offline structural content mutations (2026-08-21)

The toolkit now has a second, deliberately bounded authoring boundary for
decoded `VICDATA.bin` content. These operations are pure in-memory transforms;
they do not open USB, send a candidate, or modify a preserved fixture.

## Supported operations

- `add_file_from_template()` copies one existing reachable file record into an
  existing directory, exactly following the observed manager add shape. The
  copied record retains its extension, flag, native prefix, timestamp fields,
  and unknown bytes; the caller may then replace only the payload. This makes
  arbitrary text or other bytes possible for an already observed file type,
  while refusing to invent a new record grammar.
- `delete_existing_file()` removes one reachable leaf file. It shortens the
  parent child table, removes the file's native content segment, remaps later
  metadata/content offsets, preserves unrelated records and payloads, and
  recomputes the legacy checksum. Directory deletion, recursive deletion, and
  orphan repair are intentionally rejected.
- `rename_existing_file_bundle()` and `delete_file_bundle()` apply the decoded
  mutation through the XOR-`0xaa` `VICDATA.bin` layer. Rename replaces exact
  selected-file paths in `VICMEM.bin`; delete removes exact matching selected
  paths. Both sidecar operations preserve opaque record bytes and counts.

`VICLV.bin` and `order.vnw` are parsed and returned byte-for-byte. Their
directory/order update semantics remain insufficiently recovered for a
complete synchronizer, so the bundle helpers do not guess at those changes.
An added file is not automatically inserted into `VICMEM.bin`; selected,
marked, bookmark, and order state must be authored separately once their
semantics are established.

## Validation boundary

The mutation path reparses every result, checks the checksum, verifies the
target path change/removal, and compares all unrelated reachable paths and
file payloads with the source. Synthetic nested-tree tests cover insertion,
variable-length payload replacement, leaf deletion, metadata-pointer
remapping, and exact `VICMEM` category/tail removal. The full offline suite
passes with 174 tests.

## Remaining work

These operations do not solve the range-8 source-node/model-tree serializer,
unresolved ranges 4/6/7, or complete `VICMEM`/`VICLV`/`order.vnw`
synchronization. No new live write is authorized by this milestone. The next
evidence task is a genuinely different manager content tree and a controlled
read-only comparison of the sidecars after an add, rename, and delete.
