# Offline existing-record authoring boundary (2026-08-21)

The toolkit now has a complete offline path for changing the payload of an
existing reachable record without changing the record tree:

1. decode and structurally validate the existing `VICDATA` blob;
2. replace one or more existing file payloads with
   `repack_existing_records()`;
3. recompute offsets, lengths, padding, and the legacy checksum;
4. split the validated result into range 5 (the recovered 64-byte header
   transform) and range 8 (the exact remaining decoded blob);
5. combine those bytes with the fixed state responses from a fresh backup.

`build_from_replacements()` implements this boundary in
`src/infocarry/payload_builder.py`. The structural layer now adds two further
offline boundaries: a template-backed file add with an arbitrary replacement
payload, and a leaf-file delete with metadata/content offset remapping. The
encoded helpers and bundle layer also provide bounded rename and exact
`VICMEM.bin` path updates/removal. These are still narrower than a full manager
clone: model-node generation, directory/recursive operations, unresolved
ranges 4/6/7, and complete `VICMEM.bin`, `VICLV.bin`, and `order.vnw`
synchronization remain outside the contract.

The generated candidate is tested by parsing the rebuilt blob, checking the
target payload, and preserving all 309 reachable paths and 366 metadata
records.

## Candidate 4

`analysis/phase-8-candidate-4/` is a non-transmitting candidate built from the
post-write macOS backup (`analysis/phase-8-live-after-5/`). It changes only
`root\\IC_TEST_01.txt` at metadata offset `0x01c0` to:

```
InfoCarry toolkit authored test 02
Second line
```

with CRLF line endings and strict CP932 encoding. The rebuilt dynamic blob is
2,063,936 bytes (SHA-256
`2adf600deb1878144c23ed8fdada91531d51a238e330cd2a9691ae70ca27463d`), and
the complete eight-range candidate SHA-256 is
`ea4f291311dcf53032058195d8bdb3c7919cdcf2823b24ca875ba7028e761548`.
The preserved artifact remains marked offline-only; its bytes were later
loaded through the separate explicit write gate for modern write 2 and
verified by read-back. The artifact itself never performs USB I/O.
