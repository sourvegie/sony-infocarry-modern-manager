# Milestone I.6 Package Live-Smoke Attempt 02 Result

Date: 2026-08-23

Status: constrained live smoke completed and independently verified offline;
no retry performed.

## Execution record

The owner approved exactly one attempt using the exact operation phrase
`ADD ONE INFOCARRY TEXT PACKAGE`. The isolated runner used only the new
evidence root:

`${EVIDENCE_ROOT}/phase-12-milestone-i6-package-live-smoke-20260823-02/`

The recorded sequence was:

```text
owner approval -> exact phrase -> device detected -> native 0x0019 query
-> fresh complete pre-operation backup -> candidate reconstruction
-> authorization -> one 0x101b transaction -> completion 0x0000
-> fresh complete post-operation backup -> read-back assessment
```

The original runner audit is preserved unchanged. It first reported
`indeterminate_after_transaction_start` at `post_operation_readback` because
the package verifier treated two model-dependent objects as unrelated:

- `0x0024:response-0024`
- `0x8004:backup-blob-probe`

The audit records `write_started=true`, `completion=0x0000`,
`automatic_retry_allowed=false`, and no retry. This initial terminal audit is
not overwritten.

## Preserved evidence hashes

| Artifact | SHA-256 |
| --- | --- |
| `audit.json` | `e3a3ea6a0c272a7b0194684cacd2d1e3f2c732a3524ee5be9b199d849a4b511a` |
| `response-0019.bin` | `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a` |
| pre-operation `manifest.json` | `7615e3252a2b5675067c79791b1f476eab15b1578f20ff8884ef397666fd9058` |
| post-operation `manifest.json` | `0464f8f08a2fd21212566789fd1a2fd45430adbdc509552ff4e8f622af772bcc` |
| pre-operation dynamic blob | `bd73cb33adafacbcb0d5d0313606c94ad2de97e2810953387085234863b509d1` |
| post-operation dynamic blob | `fbebd82001f2b833e4bfe6af8922c03b4bffbbd42a18f3a9149c501107f1fd47` |
| preview | `4da9a69d7937c0a92e4ad162dfdb6c6b63fafa0cec935db6e83b2ee62bd38552` |

The complete captured evidence tree digest is
`748a235e754b23e71fae631b7289ae45de268619c0c9b7f827a6ff029787c7c8`.

## Independent offline assessment

After the live run, the package verifier was corrected offline to use the
same established payload-dependent boundary as the existing guarded write
verifier. Only `0x0024:response-0024`,
`0x8004:backup-blob-probe`, and the dynamic `0x8004:backup-blob` are excluded
from the unchanged-object comparison. All other backup objects remain
required to match exactly.

The preserved pre/post backups then pass independent verification with:

| Check | Result |
| --- | --- |
| Device | `0x054c:0x001e` |
| Native capacity | Parsed fresh `0x0019` field `+0x08`: `3,145,728` bytes |
| Candidate growth | `288` bytes; remaining growth `1,094,596` bytes |
| Completion | `0x0000` |
| Candidate blob | Exact match; SHA-256 `fbebd82001f2b833e4bfe6af8922c03b4bffbbd42a18f3a9149c501107f1fd47` |
| Record count | 370 to 373: folder, leading marker, and TXT child |
| Added paths | Exactly `root\\IC_I4_PACKAGE_20260823_01` and `root\\IC_I4_PACKAGE_20260823_01\\chapter.txt` |
| Removed paths | None |
| Fixed state | All five objects exact; common SHA-256 `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` |
| Shared records | 312 reachable records preserved |
| Shared payloads/prefixes/timestamps | Unchanged |
| Unchanged backup objects | 5 exact non-payload-dependent objects |
| Expected dynamic objects | Only `0x0024` and the `0x8004` probe changed besides the candidate blob |

The original terminal audit and the derived offline verification are both
retained so the verifier-boundary correction is auditable. The correction did
not trigger a second sender call or any additional device access.

## Scope and remaining risk

This is verified live evidence for the constrained policy of one root folder
with one TXT child, one explicit frozen timestamp, exact capture-7-compatible
all-zero fixed state, and no category/mark/bookmark/selection/sidecar
assignment. It does not prove arbitrary folders, multiple children, nested
content, bitmap packages, or interrupted-write recovery. R15 remains open.

No normal GUI or CLI package action is enabled, and no further live operation
is authorized by this result.
