# Milestone I.9 — offline mixed TXT/BMP package

Date: 2026-08-23
Status: **Typed offline model complete; device candidate blocked.**

`infocarry.prepared_media_package` adds a typed ordered package model for TXT
and BMP sources. It reuses the strict UTF-8 → CP932/CRLF boundary for TXT and
the existing monochrome BMP decoder, then applies a stricter package profile:

- Windows `BM` payload with a 40-byte `BITMAPINFOHEADER`;
- exactly 237×320 pixels, accepting either BMP row orientation;
- one bit per pixel, one plane, `BI_RGB`/uncompressed;
- two-entry palette and pixel offset immediately after header and palette;
- four-byte-aligned rows whose pixel bounds exactly cover the source.

The package preserves explicit item order, source and prepared payload hashes,
typed metadata, source sizes, row geometry, wrapper requirements, and an
offline lower-bound growth estimate. It supports a mixed TXT/BMP sequence such
as TXT → BMP → TXT, rejects duplicate case-insensitive target names and source
paths, and exports only to a new destination. Synthetic tests cover valid
ordering, deterministic manifests, BMP dimensions/format/bounds, strict TXT
errors, conflicts, source preservation, and non-overwriting export.

This is not a device candidate. Exact BMP native wrapper fields, metadata
records, timestamps, fixed-state behavior, total-limit capacity authorization,
transaction construction, independent read-back, fake sender coverage, and
live eligibility remain blocked. No package operation is exposed through the
normal CLI or ttk interface. Owner-provided copyrighted material was not copied
into the repository.
