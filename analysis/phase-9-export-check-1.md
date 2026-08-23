# Phase 9 — offline export check

Date: 2026-08-22

The first complete post-write raw backup was exported without USB access:

```text
source: analysis/phase-8-live-after-4
output: analysis/phase-9-export-check-1
source blob SHA-256: c86f5523565da644995c5a2c47ca7255fe18f70b374ad1c105c44a330e26940f
summary: 57 directories, 252 files, 0 orphan records
```

The export manifest is `infocarry-export-v1`. It preserves the raw record
fields, native payloads, decoded CP932 text views, and source provenance. The
known `IC_TEST_01` record is exported both as native bytes and as a decoded
text view. No device was connected or accessed during this check.

This confirms the offline export path that will later be surfaced by the
desktop workflow. The GUI's current top-row overlap on legacy macOS Tk is a
cosmetic rendering issue only; the loaded records and their offsets remain
usable, and the write controls remain absent.
