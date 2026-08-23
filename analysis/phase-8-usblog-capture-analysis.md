# Phase 8 — Native SnoopyPro Capture Analysis

Date: 2026-08-21
Status: **Native eight-range split recovered; payload generation and device writes remain disabled.**

## Evidence identity

The two files below are preserved native SnoopyPro traces. They were inspected
read-only; neither capture was rewritten, converted, or replayed.

| Capture | Size | SHA-256 |
| --- | ---: | --- |
| `00-read-baseline.usblog` | 4,601,913 bytes | `70ebd381ccf8864130230dd91caba644f525437c562ddb323528ef2a23046afa` |
| `01-selected-send.usblog` | 6,903,007 bytes | `c8b3812682e1d1974c7d3843e25b7a7fa471dc1de4bcd83a7acec66c447f4a5c` |

The files are binary native `.usblog` files, not XML exports. They contain the
SnoopyPro record type names (`CURB_ControlTransfer`,
`CURB_BulkOrInterruptTransfer`, and `CURB_SelectConfiguration`) and the
InfoCarry device path `USB\\Vid_054c&Pid_001e&Rev_0100`.

## Command inventory

The six-byte command headers are visible inside the serialized control-transfer
records. The ordinary-send preflight sequence is present immediately before
each observed `0x101b` transaction:

```text
0x101e (16-byte exchange), 0x0010, 0x0019, 0x0018, 0x0024, 0x0025, 0x101b
```

The baseline contains one such sequence. The selected-send capture contains
the same baseline sequence plus a second complete sequence after the selected
item was sent. No general-purpose `0x101d` transaction appears in either
capture, which is consistent with the ordinary send path and not the separate
unlock workflow.

### `0x101b` transaction headers

| Capture occurrence | Command-header payload offset | Declared length | Staging fields observed |
| --- | ---: | ---: | --- |
| Baseline | `0x236425` | `0x00206b28` = 2,124,584 | `N = 0`, `M = 0x001f6b28` |
| Selected-send, first | `0x23764d` | `0x00206b28` = 2,124,584 | same as baseline |
| Selected-send, second | `0x46742b` | `0x002077c8` = 2,127,816 | `N = 0`, `M = 0x001f77c8` |

The staging block is the fixed `0xff`-filled range-3 buffer documented in
`phase-8-write-transaction.md`. Its first eight payload bytes are the observed
big-endian pair `[N, M]`; the second selected-send transaction changes only
`M`, by `0x0ca0` (3,232) bytes. The declared-length difference is exactly the
same 3,232 bytes.

## Recovered native payload records and ranges

The native record layout can now be parsed without converting or rewriting the
captures. A host-to-device payload record is identified by marker
`48 00 09 00`, a 16-bit length at marker `+0x14`, a 16-bit flags field at
`+0x18`, and payload bytes at `+0x1a`. Its matching completion record has the
same marker, kind `2` at `+0x14`, and the payload length at `+0x18`. The
payload-length sum stops exactly at each `0x101b` declared length.

The verified ordinary-send sequence contains 523 payload records with this
distribution:

| Payload length | Count |
| ---: | ---: |
| `0x1000` (4,096) | 517 |
| `0x100` (256) | 1 |
| `0x40` (64) | 2 |
| `0xec0` (3,776) | 1 |
| final tail | 2 |

The two final tails are `0xac0` (2,752) and `0x28` (40) in the baseline and
first selected-send transaction, and `0xb00` (2,816) and `0xc88` (3,208) in
the second selected-send transaction. Their sums match the declared lengths.

The records split into the eight logical ranges below. Ranges 4, 6, and 7
have no payload record on this ordinary path; their zero lengths are therefore
an observed wire absence, not a claim that every future command uses zero
buffers.

| Range | Baseline / selected first | Selected second | Evidence |
| ---: | ---: | ---: | --- |
| 1 | 256 | 256 | first payload record |
| 2 | 64 | 64 | second payload record |
| 3 | 65,216 (`0xfec0`) | 65,216 (`0xfec0`) | 8-byte big-endian `N/M` prefix followed by `0xff` fill |
| 4 | 0 | 0 | no payload record observed |
| 5 | 64 | 64 | next fixed 64-byte record, begins with `infoCarry 2.00` |
| 6 | 0 | 0 | no payload record observed |
| 7 | 0 | 0 | no payload record observed |
| 8 | 2,058,984 | 2,062,216 | all remaining records; model/content region |

The first three ranges fill exactly `0x10000` bytes. The staging fields satisfy
`N = 0`, `M = len(range 5) + len(range 8)`, and
`declared_length = 0x10000 + N + M` for all three transactions. This is a
byte-level consistency check on both the record parser and the recovered range
boundaries.

The parser and synthetic round-trip tests are in
`src/infocarry/usblog.py` and `tests/test_usblog.py`. The JSON-safe comparison
helpers are in `src/infocarry/usblog_report.py` with tests in
`tests/test_usblog_report.py`. They are deliberately offline-only and do not
expose a USB write path.

### Range hashes

The following SHA-256 hashes are over reconstructed range bytes, not over
native record headers:

| Range | Baseline | Selected first | Selected second |
| ---: | --- | --- | --- |
| 1 | `f747d974b82d06b539c1146538dd8a8c3881792bc392c6d499d1a7654745484d` | same | `95f9ff6d5ee30142e32428f5cec396c5e702774a595d1be8bd2662a1a157af78` |
| 2 | `747c8c52392918da47931b73851a15c37342764685e3f3b4e83d66d19dccc5f7` | same | same |
| 3 | `d7afcd861e9a613ee686a4a98d4297b547dcc3580a698775cada2d9aa22704ab` | same | `a3b51c8cd31a3de35354fa1c2aaefb7157ffac0ef21c98279585267747dfe4f2` |
| 4 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | same | same |
| 5 | `92c153b2f6121b9615fdad833bbd52f71ea073c389a38f1c68e79e6db0709835` | same | `24c3d597b7aff3ebb92729fe5c8c5ac0ace18466f614f0076ff67435f9f908d0` |
| 6 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | same | same |
| 7 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | same | same |
| 8 | `a5dc53408b4f1f6045993d022473e8cd8cb995543f193d2df70ab59da261a41e` | same | `98e88fe9246b8a5d725d881fc1b24aba7a620e7f705c429c8050c883a49e8dc0` |

The first selected-send transaction is byte-identical to baseline in all eight
ranges. The second transaction differs only in ranges 1, 3, 5, and 8; ranges
2, 4, 6, and 7 remain identical. Range 3 changes its `M` prefix from
`0x001f6b28` to `0x001f77c8`. Range 8 grows by exactly 3,232 bytes. Its
baseline/second-transaction common prefix is 135 bytes and common suffix is
2,028,941 bytes, localizing the changed model region without assuming whether
the manager replaced or duplicated the same-name item.

The deterministic comparison report measures 9 positional changes in range 1,
2 in range 3, 13 in range 5, and 1,536,753 differing/shifted bytes in range 8
for the second transaction. The large range-8 count is expected from the
3,232-byte growth and subsequent positional shift; it is not evidence that
every model field changed independently.

## Fixed-state serializer comparison boundary

Applying the existing range-1 and range-2 serializers to the preserved Phase 6
and Phase 7 backup response snapshots does not produce byte-identical capture
ranges. This is not treated as a serializer failure: those backups were made
in separate device states, and the capture's manager-side source arrays and
ordering are not preserved as standalone response objects. The comparison is
recorded as a reproducible negative result so future snapshots can be tested
without silently promoting an approximate match.

## What this proves

1. The native trace contains a genuine manager host-to-device `0x101b`
   transaction, not merely a static string or a random occurrence in content.
2. The selected-send action generated a second ordinary-send transaction after
   the baseline traffic.
3. The selected transaction used the expected six-byte little-endian header and
   a successful-length relationship of `0x10000 + N + M` with `N = 0`.
4. The selected item caused the model-side declared region `M` to grow by
   exactly 3,232 bytes. This is a byte-level observation, not yet a semantic
   claim about whether the manager replaced an existing record or created a
   duplicate after the same-name warning.
5. The final request-4 control-transfer record is present at the end of each
   ordinary-send trace (`0x463811` in the baseline and `0x6954b7` in the
   selected-send capture). Its setup packet is confirmed below; the result
   word itself remains unresolved in the native representation.

## Request-4 boundary

The final native control-transfer records contain the expected request-4 setup
packet `c0 04 00 00 00 00 02 00` at setup offsets `0x463811` (baseline) and
`0x6954b7` (selected-send). The next two bytes are `1e 00`, followed by the
ASCII device path `USB\\Vid_054c&Pid_001e&Rev_0100`; `0x001e` is its
30-character length prefix, not the two-byte device completion result. The
native record therefore confirms the request-4 boundary and requested result
length, but does not expose a safely decoded result word in this
representation. The completion value remains unresolved pending a trustworthy
XML/native-record field mapping.

## Boundary comparison

The selected-send trace's first `0x101b` transaction is byte-identical to the
baseline transaction when aligned by the 4,648-byte native-session preamble,
until the final completion-region records. The second selected-send transaction
then runs to the end of the file. The transaction spans differ by the same
3,232 bytes as the declared `M` difference, supporting the interpretation that
the extra bytes are an added model-range payload rather than unrelated USB
traffic.

## Remaining offline work

- Range 5 is now exactly reversible for the ordinary 64-byte helper output.
  `analysis/phase-8-range5-source-recovery.md` records the recovered source
  candidates and hashes for the baseline and changed selected transaction.
- Compare the range-1 and range-8 changes with the existing offline serializers
  and structural repacker, keeping unresolved fields opaque.
- Confirm the nested request-4 result word and record the manager's success
  boundary.

No new device operation is requested for these tasks. If native parsing remains
ambiguous, the least-invasive next step is to export XML copies from SnoopyPro
while preserving these native files as the authoritative originals.
