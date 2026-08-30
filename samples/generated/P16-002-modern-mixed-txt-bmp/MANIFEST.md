# P16-002 modern mixed TXT/BMP package manifest

This is the exact sanitized, host-only package for the P16-002 readiness
dossier. It is derived byte-for-byte from the P16-001 Capture 01 fixture, but
uses the distinct destination `IC_P16_MIXED_20260830_02`. It has one new flat
root folder and exactly three ordered children:

1. `root\IC_P16_MIXED_20260830_02\01-introduction.txt`
2. `root\IC_P16_MIXED_20260830_02\02-page-01.bmp`
3. `root\IC_P16_MIXED_20260830_02\03-ending.txt`

The sources contain no private or copyrighted ebook material. The TXT files
are strict CP932-compatible CRLF source bytes. The BMP is the validated
237x320, bottom-up, one-bit, uncompressed Windows BMP profile from P16-001.
The source hashes and machine-readable details are authoritative in
`manifest.json` and `SHA256SUMS.txt`.

The native P16-001 evidence supports the exact flat TXT/BMP/TXT structure,
the 64-byte folder/marker records, 32-byte TXT prefixes, 16-byte all-`FF`
BMP prefix, exact payload preservation, four-byte alignment, fixed-state
preservation, and existing-timestamp preservation as the approved modern
policy. It does not establish a general package format. Native numeric
completion decoding and operation-specific capacity semantics remain
unresolved; a future live preflight must obtain fresh parsed `0x0019` evidence
and accept only explicit completion `0x0000`.

This directory contains no backup, USB capture, candidate, transaction, or
private device data. P16-002 generated candidate and fake-run audit artifacts
are preserved separately outside Git.
