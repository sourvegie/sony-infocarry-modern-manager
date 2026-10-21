# P18-046 disposable root-BMP operator runbook

**BLOCKED_BY_EXTERNAL_EVIDENCE. No hardware operation is authorized.** This
checkpoint supplies an exact fixture and executable offline preparation and
verification. It does not supply a root-BMP placement or live Delete command.
Normal Device Library BMP Delete remains disabled. Do not use a TXT launcher,
rename a BMP to TXT, alter an admission flag, or submit the saved transaction
directly to USB.

## Exact specimen and host commands

Target: `root\IC_P18_046_DELETE_A.bmp`; 10,302 bytes; SHA-256
`2701eb9214e2f0afec20b36c93ef739ef3bce35e931fd8c5721e15915447b26d`.
It is a bottom-up 237×320 uncompressed 1-bit Windows BMP, 40-byte DIB,
black/white palette, 62-byte pixel offset and 32-byte scanlines, with a border
and checkerboard centre. The manifest fixes its identity independently of the
generator. This is the smallest payload length for the established full-screen
profile, not a device maximum or native root example.

Run from the P18-046 worktree with the supported Python 3.12 environment:

```sh
python scripts/prepare_root_bmp_delete.py fixture --output /private/tmp/p18-046-fixture-NEW
python scripts/prepare_root_bmp_delete.py prepare --backup /absolute/complete-baseline --output /private/tmp/p18-046-prepared-NEW
```

These commands are offline. The second requires the exact fixture already
present in the saved archive as an unread `0xe0` ordinary root BMP with native
selector `0x100` (16-byte prefix), unique safe name, unreferenced target and
supported complete protected state. It refuses the current saved baseline,
which has no root BMP. Prefix contents and every other opaque byte are
preserved/validated by the retained structural model; no wrapper is invented.
Broader BMP model variants remain offline research only.

Output contains the fixture, candidate, eight transaction ranges, candidate
audit, existing host-only authorization binding and preparation report. Keep
the entire directory private and outside every Git checkout. It contains
surviving device data. It is neither owner approval nor a production bundle;
historical preparation does not establish current device state or capacity.

## Missing evidence before an executable physical procedure

The P18-042/043 corpus has no root BMP. A fresh offline verification of the
P18-045 saved post-cleanup backup likewise has zero root BMP and 163 nested
BMP, all with 16-byte prefixes. Nested storage is evidence for the payload and
prefix geometry, not for root placement or Delete effects. No native root-BMP
add/delete pair or reviewed modern root-BMP placement adapter is available.

The next operator decision is whether to authorize a bounded native/Legacy
Oracle **placement evidence experiment** for this one specimen, with the
specific environment and procedure reviewed first. Neither existing modern
TXT placement nor generalized folder transfer implements that root-file
operation. Do not execute placement from this runbook alone. Once complete
root placement evidence establishes the actual record/prefix/state and sole
addition, a bounded live adapter can be checked against it through the current
frozen operation, owner identity, reconnect equivalence, claim/marker/global
lock, single sender/no-retry and independent readback framework. No second
transport or authorization system is needed.

## Separate placement and deletion approvals

1. Before placement, close other device clients, confirm the characterized
   VNW-V15 and save a fresh complete eight-object backup. Verify target absence,
   native capacity, protected state and specimen identity. Keep originals
   outside Git. A separately approved read-only command can use the existing
   CLI: `PYTHONPATH=src python -m infocarry backup --json /absolute/NEW-backup`.
   Any real USB command, including this backup, needs its own narrow
   out-of-sandbox permission; none has been run by P18-046.
2. Obtain new owner authorization for **one placement only**, identifying the
   exact file/hash, VNW-V15, selected native/modern procedure and full backup.
   Review the exact USB command permission if modern tooling is used. Capture
   the native placement buffer/effect when feasible; do not fabricate a
   modern owner claim for a native legacy operation. Run only one client.
3. Independently verify the complete post-placement backup: sole fixture
   addition, exact payload, real root record/prefix/flag, pointer/allocation
   geometry, protected associations and survivor preservation. Record any
   native timestamp changes as observed evidence. If the native form differs
   from the proposed host specimen, stop and review it; do not coerce it.
4. After the bounded live adapter has exact-head R3 approval, freeze a **new**
   Delete operation from a fresh backup and native capacity. Reuse the existing
   owner operation identity and ordinary Delete/Cancel interaction. Reconnect
   must check complete execution equivalence before claim/sender; no rebuild,
   rebinding or approval adoption is permitted. The offline preparation report
   is never an execution input or owner identity.
5. Obtain separate owner authorization for **one deletion only** and narrow
   permission for that reviewed exact write command. Placement approval does
   not authorize deletion. Preserve the complete pre-delete state, one durable
   claim before sender marker, installation lock and one guarded sender. No
   retry; no interruption/recovery experiment; no other target or personal file.
6. Accept success only on actual integer native `0x0000`, one audited sender,
   complete independent eight-object post-backup, byte-exact candidate,
   sole removal, every surviving payload/prefix/timestamp, protected state and
   unrelated objects preserved, durable terminal result and proof-bound marker
   resolution. A bus trace is separate evidence, never inferred from counters.
7. On missing/malformed/nonzero completion or any post-start ambiguity, retain
   the persistent installation-wide lock and all evidence. Do not retry,
   automatically restore, clear a lock or delete claims. Diagnose read-only
   under a separately approved procedure. Any cleanup is another approved write.

For a later supplied post-backup, independent offline comparison is available:

```sh
python scripts/prepare_root_bmp_delete.py prepare --backup /absolute/pre-delete-backup --output /private/tmp/p18-046-offline-verification-NEW --post-backup /absolute/post-delete-backup --completion 0x0000
```

Supply only the actually observed completion; this command does not establish
sender count, claim/marker state, owner authorization or physical execution.
Synthetic readback success never promotes general BMP Delete. Read-state BMP,
other payloads/names/prefixes, referenced/ambiguous files, nested files,
directories/subtrees, VNW-V10, restore and interrupted-write recovery remain
outside the experimental plan.
