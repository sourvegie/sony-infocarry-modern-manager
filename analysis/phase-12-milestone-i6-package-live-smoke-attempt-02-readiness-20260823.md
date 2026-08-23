# Milestone I.6 Package Live-Smoke Attempt 02 Readiness

Date: 2026-08-23

Status: offline readiness prepared; not authorized and not executed.

This record is for a possible second attempt after the owner supplies a new
explicit approval. It does not authorize a backup, USB ownership change,
device write, or any other live operation.

## Attempt 01 preservation

Attempt 01 remains permanently preserved at:

`${EVIDENCE_ROOT}/phase-12-milestone-i6-package-live-smoke-20260823-01/`

It stopped during fresh-backup verification with `write_started=false`; no
`0x101b` request was issued and no retry occurred. Its read-only tree digest
is `c8a1e9d16fd43d5af9494c2c1a9985520bfc9fa555a8c177ec77ab60e770c056`.
The principal preserved hashes are:

| Artifact | SHA-256 |
| --- | --- |
| `audit.json` | `8b00593bf584b81d7e38058e1b12ed59ff08df845ec0e14f3ac9c4545cb24995` |
| pre-operation `manifest.json` | `1c2d6b67946a188100f6ea0f8699d6d69806308381e71b6d872cd039f8356be4` |
| pre-operation dynamic blob | `bd73cb33adafacbcb0d5d0313606c94ad2de97e2810953387085234863b509d1` |
| raw `0x0019` response | `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a` |

No file in that root was modified during this readiness work.

## Freshness regression and correction

The first test invocation uses an invocation-time reference that predates the
capture completion. It reproduces the original “manifest timestamp is in the
future” stop and preserves the failed archive. A second invocation passes
`now=None`; `capture_and_verify_fresh_backup()` obtains its reference after
the injected capture completes and accepts the genuinely fresh archive. The
bounded maximum-age check remains enabled.

A complementary test writes a manifest one hour in the future and confirms
that it is still rejected. No future-timestamp validation was weakened.

Focused result: 14 `tests.test_write_gate` tests passed, including both new
regressions. Complete result after this slice: **359 tests passed**.

## Offline revalidation for attempt 02

| Binding | Result |
| --- | --- |
| Source | `tmp/i4-live-smoke-20260823-01/chapter.txt`; SHA-256 `187ba5ae05ef08f86d5f27e7de7ff445d4a32df7921d21bb9345ce158f205321` |
| Target folder | `root\\IC_I4_PACKAGE_20260823_01` |
| Target child | `root\\IC_I4_PACKAGE_20260823_01\\chapter.txt` |
| Latest read-only backup | Attempt-01 pre-operation backup; complete and hash-verified; both target paths absent |
| Template | `tmp/phase-12-milestone-i-folder-package-post-add-20260823-01/object-08-command-8004.bin`; SHA-256 `bd73cb33adafacbcb0d5d0313606c94ad2de97e2810953387085234863b509d1` |
| Fixed state | Commands `0x001b`–`0x001f` are each 64 zero bytes; common SHA-256 `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` |
| Capacity | The runner obtains a fresh native `0x0019` response and derives the limit from response field `+0x08`; no capacity constant, Manager display, `0x0024`, or unknown field is supplied as authorization input |

The attempt-01 pre-operation backup has dynamic-blob SHA-256
`bd73cb33adafacbcb0d5d0313606c94ad2de97e2810953387085234863b509d1` and
contains 370 records. It is used only for read-only target/state revalidation;
attempt 02 must still capture its own fresh complete backup.

## New evidence root and output paths

The new root is:

`${EVIDENCE_ROOT}/phase-12-milestone-i6-package-live-smoke-20260823-02/`

It did not exist during preparation. Every intended output path was also
absent:

- `pre-operation-backup/`
- `post-operation-backup/`
- `response-0019.bin`
- `preview.json`
- `audit.json`

The isolated runner refuses any existing output path and opens the device only
after both exact approval strings and all output-path checks pass.

## Exact unexecuted attempt-02 command

This command is recorded for owner review only. It has not been run. Every
attempt-02 output destination uses the new `-02` root; no attempt-01 path is
used as an output destination.

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python run_i6_prepared_package_live_smoke.py \
  --source tmp/i4-live-smoke-20260823-01/chapter.txt \
  --folder-name IC_I4_PACKAGE_20260823_01 --child-name chapter.txt \
  --template-blob tmp/phase-12-milestone-i-folder-package-post-add-20260823-01/object-08-command-8004.bin \
  --timestamp 0x6a8aba6f \
  --backup-destination ${EVIDENCE_ROOT}/phase-12-milestone-i6-package-live-smoke-20260823-02/pre-operation-backup \
  --post-operation-destination ${EVIDENCE_ROOT}/phase-12-milestone-i6-package-live-smoke-20260823-02/post-operation-backup \
  --capacity-response-destination ${EVIDENCE_ROOT}/phase-12-milestone-i6-package-live-smoke-20260823-02/response-0019.bin \
  --preview-audit-destination ${EVIDENCE_ROOT}/phase-12-milestone-i6-package-live-smoke-20260823-02/preview.json \
  --audit-destination ${EVIDENCE_ROOT}/phase-12-milestone-i6-package-live-smoke-20260823-02/audit.json \
  --confirmation 'ADD ONE INFOCARRY TEXT PACKAGE' \
  --owner-approval 'APPROVE I6 PACKAGE LIVE SMOKE'
```

The source and template remain immutable repository fixtures. The runner’s
fresh native `0x0019` query is the only capacity evidence for the possible
attempt; its raw response is written exclusively to the new `-02`
`response-0019.bin`. The operation-specific phrase and separate owner
approval are both required. If a later approved run starts `0x101b`, any
interruption, timeout, missing/ambiguous completion, or read-back failure is
terminal and must not be retried.

No live operation was performed for this readiness slice.
