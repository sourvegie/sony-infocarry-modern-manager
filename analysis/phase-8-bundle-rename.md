# Offline synchronized rename boundary (2026-08-21)

The toolkit now supports a conservative existing-file rename entirely in
memory:

1. `rename_existing_record()` changes one reachable `VICDATA` metadata name
   field, rejects traversal/separator names and sibling collisions, recomputes
   the legacy checksum, and validates the resulting path index.
2. `rename_existing_vicdata()` applies the same operation through the observed
   `VICDATA.bin` XOR-`0xaa` layer.
3. `rename_existing_file_bundle()` updates exact matching selected-file paths
   in `VICMEM.bin`, preserving post-NUL scratch bytes and tail fields.
4. `VICLV.bin` and `order.vnw` are parsed and preserved byte-for-byte. Their
   directory/order update semantics are not sufficiently recovered to mutate
   them safely for a general rename.

The operation does not add or remove records, change directory structure,
generate model ranges, or access USB. Tests cover checksum/path validation,
CP932 and field-size limits, exact `VICMEM` replacement, and preservation of
unrelated sidecars.
