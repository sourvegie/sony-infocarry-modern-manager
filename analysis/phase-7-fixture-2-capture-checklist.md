# Phase 7 — Second fixture capture checklist

Only one manager-produced fixture is currently present:

`${RESEARCH_ROOT}/fixtures`

The second fixture must remain a separate, untouched directory. Do not replace
or rename the first fixture.

## Capture

1. Create a new destination such as
   `${RESEARCH_ROOT}/fixtures-2`.
2. Use the legacy manager's receive/backup/download-to-PC operation only. Do
   not choose restore, upload, delete, format, or settings operations.
3. Copy the manager-produced files from that same session, preserving their
   bytes and relative locations:

   ```text
   Backup/VICDATA.bin
   Memo/VICMEM.bin
   Memo/VICLV.bin
   ICM/<manager-created-folder>/order.vnw
   ```

4. Copy the files directly; do not open and save them in an editor or allow a
   cleanup tool to alter them. If possible, make a byte-for-byte duplicate of
   the new fixture before disconnecting the legacy environment.
5. Keep the original first fixture and the raw backup associated with each
   session. The second fixture may be from an unchanged device or from one
   deliberately documented, harmless state change; record which.

## Offline analysis after copying

Run this from `InfoCarry-Toolkit`:

```sh
.venv/bin/infocarry fixture-report \
  ${RESEARCH_ROOT}/fixtures-2 \
  analysis/fixture-report-2
```

The command reads the new files, verifies the observed XOR/checksum path, and
writes only a new `manifest.json` (for example,
`analysis/fixture-report-2-roundtrip/manifest.json`). It does not access USB
and does not write a decoded backup. Once that report exists, compare its
hashes, `VICDATA` encoding, sidecar auxiliary/tail values, ordering, and path
correlations with `analysis/fixture-report-1/manifest.json`.

Do not begin repacking or any device write operation from this comparison alone;
unresolved fields still require explicit evidence.

This second fixture has now been captured and analyzed. The results are in
`analysis/phase-7-fixture-2-comparison.md`; the next fixture, if needed, should
come from a genuinely different `VICDATA.bin` content state.
