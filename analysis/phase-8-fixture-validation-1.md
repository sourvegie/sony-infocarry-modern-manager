# Phase 8 — fixture validation rerun

Date: 2026-08-22

The preserved `fixtures-3` tree was re-read without modification and passed
the current fixture-report validator:

```text
source: ${RESEARCH_ROOT}/fixtures-3
report: analysis/fixture-report-3-rerun-1/manifest.json
records: 2035
reachable files: 1677
directories: 179
correlations: VICMEM 12, VICLV 2, order.vnw 5
```

The rerun hashes and structural summary are byte-for-byte identical to the
previous `analysis/fixture-report-3/manifest.json`. This validates the
ordinary parser and the exact `VICLV.bin`/`order.vnw` preservation boundary
against a real manager-produced fixture, not only synthetic unit data.

`fixtures-4` was not passed to the validator because it contains `ICM.zip`
instead of an extracted `order.vnw`; its raw files remain preserved and were
not changed.
