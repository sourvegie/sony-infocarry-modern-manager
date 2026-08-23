# Milestone I.7 — legacy add attempt 01 result

Date: 2026-08-23
Status: **Add evidence complete; timestamp and nonzero-state generalization remain blocked.**

This report records the separately approved legacy Manager add of exactly one
synthetic root-level TXT item. It does not authorize deletion, modern package
transfer, or a normal GUI/CLI write action. The machine-readable synthesis is
`analysis/phase-13-milestone-i7-legacy-add-01-results-20260823.json`.

## Evidence gate

| Item | Result | Classification |
| --- | --- | --- |
| Source identity | 1,863-byte strict ASCII-subset UTF-8/CRLF source; SHA-256 `3aa626dc1e0dbd2fe13b59fbea7eddf43358a522b9f55ed15ac18556b2a69d4b` | byte-verified |
| Device identity | Sony `054c:001e` before and after | verified |
| Native add transaction | One ordinary `0x101b` transaction in `01-add.usblog` | verified |
| Persisted path delta | 373 records to 374; exactly `root\\IC_I7_CLOCK_01.txt` added; no path removed | independently verified |
| Payload | New payload is 1,863 bytes and exactly matches the source hash | byte-verified |
| Model growth | 2,051,420 to 2,053,380 bytes; growth 1,960 bytes | byte-verified |
| Fixed state | `0x001b`–`0x001f` byte-identical, all-zero, before and after | verified for this state only |
| Manager result | Device preview visibly contains the new item; no explicit success wording was preserved | observed success display; wording unresolved |
| Request-4 completion | Offline parser did not decode a trustworthy request-4 value | unresolved |

## Manager-side separation

The first snapshot supplied from before source preparation had `VICMEM.bin`
hash `6b5ec744...7d5f0`. The immediate-before-send snapshot supplied in the
capture9 intake had `VICMEM.bin` hash `d06a8a46...7efaff1`; its 20 bytes differ
only at the observed `+0x0a` field (`af 01` to `e2 01`). This is classified as
source-preparation/bookkeeping change, not as a Send Selected device-state
change.

The immediate-before-send and after-send snapshots are byte-identical for the
observed relevant sidecars:

- `VICDATA.bin`: `72142b...9b728`
- `VICMEM.bin`: `d06a8a...7efaff1`
- `VICLV.bin`: `86f79c...d869eb2`
- `ICM/転送元フォルダ/order.vnw`: `6dff6f...575059`

Therefore this add confirms that the observed Manager sidecars can change
during local source preparation while remaining unchanged during the native
Send Selected transaction. It does not prove that sidecars are irrelevant to
other Manager operations or record types.

## Timestamp result

The metadata field at `+0x0c` continues to parse as a big-endian Unix-style
seconds value. In this add:

- all 314 shared record timestamps changed;
- shared post-add values were `0x6a8c4ba3` (99 records), `0x6a8c4ba4`
  (132 records), and `0x6a8c4ba5` (83 records);
- the new TXT record used `0x6a8c4e78`;
- the known source fixture birthtime was `2026-08-23T12:52:20.846306Z`, while
  the new record value decodes to `2026-08-24T14:00:24Z`.

This is an independent observation that legacy add rewrites shared metadata
timestamps and gives the new record a distinct later value. The available
wall-clock observations are screenshots rather than exact event records, and
the Windows source-copy time and device clock were not captured as machine
data. Consequently the evidence still cannot distinguish operation time,
Manager preparation time, a converted local time, or another generated input.
Do not use current time, source birthtime, a copied timestamp, or the attempt's
observed map as an implicit general rule.

## Fixed-state result

All five fixed-state responses were byte-identical before and after this add:
each offset-list count was zero, both `0x001f` groups were zero, and all unused
tails were zero. This strengthens the exact all-zero constrained policy but
does not characterize history, marks, bookmarks, selection, or other nonzero
references. A future state experiment must remain separate and must not be
combined with deletion.

## Native candidate

The offline ingest found one ordinary transaction with declared length
2,118,916, candidate model length 2,053,380, record offset `0x00000380`, and
candidate record count 521. The dynamic candidate's new record fields were:

```text
flag       = 0xe0
timestamp  = 0x6a8c4e78
field_04   = 0x000001ac
field_08   = 0x00000747
field_10   = 0xffffffff
field_14   = 0x00000200
```

These are preserved observations for the captured add, not a generalized
builder contract.

## Gate decision and next boundary

The isolated legacy add evidence gate is complete. I.7 remains open only for
the negative generalization boundary: timestamp generation and nonzero
fixed-state derivation are not safe to promote. H.2 deletion remains blocked;
the device currently has the disposable add and no state-reference experiment
has been performed. No deletion is to be attempted from this evidence alone.

The next permissible work is offline synthesis, evidence preservation, and a
reviewed decision about the smallest separate nonzero-state experiment. Any
future state-changing capture requires a new operation-specific approval and
must not be combined with deletion.
