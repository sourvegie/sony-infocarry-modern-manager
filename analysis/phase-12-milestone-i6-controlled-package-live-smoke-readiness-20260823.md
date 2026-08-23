# Milestone I.6 — controlled package live-smoke readiness

Date: 2026-08-23
Status: **owner-approved preflight stopped before write; no live package write performed**

Milestone I.5 established the native total model limit used by the legacy
ordinary worker. I.6 adds a hash-bound evidence object and requires that
native evidence for any future live-eligible constrained package candidate.
The compatibility `available_capacity_bytes` path remains offline-only.

## Native capacity evidence

`src/infocarry/capacity_evidence.py` creates `NativeCapacityResponse` only from
an actual parsed `RawInfoResponse` for command `0x0019`. The object preserves
the complete 64-byte response and binds:

| Field | Required value / rule | Classification |
| --- | --- | --- |
| device identity | VID `0x054c`, PID `0x001e` | verified binding |
| response command | `0x0019` | verified parser input |
| capacity field | raw response `+0x08`, big-endian | verified static data flow |
| raw response | complete 64 bytes and SHA-256 | verified evidence binding |
| capacity limit | parsed `3,145,728` bytes in the preserved response | verified fixture value |
| source/version | `parsed_device_info_0x0019` / `infocarry-native-capacity-evidence-v1` | explicit provenance |

The bound `NativeCapacityEvidence` additionally records baseline model bytes,
candidate model bytes, candidate growth, and remaining growth. It rejects a
wrong device, malformed/truncated response, changed raw hash, changed parsed
limit, inconsistent lengths, and a candidate above the native total limit.
Manager UI values, command `0x0024`, `field_14_be32`, and caller-supplied
constants cannot create this evidence object.

## Preserved offline reference values

These values are calculated from the existing I.4 preparation artifacts. They
are not a fresh live authorization and must be regenerated before any future
owner review:

| Item | Value | Source |
| --- | --- | --- |
| device | `0x054c:0x001e` | preserved I.4 raw-info manifest |
| `0x0019` raw response | `tmp/i4-live-smoke-20260823-01/info-01/command-0019-hardware.bin` | preserved preparation artifact |
| raw response SHA-256 | `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a` | verified file hash |
| capacity field | `+0x08` | native evidence object |
| capacity limit | `3,145,728` bytes | parsed response |
| baseline model | `2,051,132` bytes | I.4 pre-backup dynamic blob |
| candidate model | `2,051,420` bytes | constrained offline candidate |
| candidate growth | `288` bytes | candidate minus baseline |
| remaining growth after candidate | `1,094,308` bytes | `3,145,728 - 2,051,420` |
| folder record | `0x340` | constrained candidate |
| child record | `0x3c0` | constrained candidate |
| candidate blob SHA-256 | `fbebd82001f2b833e4bfe6af8922c03b4bffbbd42a18f3a9149c501107f1fd47` | constrained candidate |
| transaction SHA-256 | `2965f96bb13206a57e8efdec96c6722a10862a39f56d6cba15f950c3794c938b` | exact prospective ranges |

The owner-approved attempt-01 evidence root is preserved as:

```text
${EVIDENCE_ROOT}/
  phase-12-milestone-i6-package-live-smoke-20260823-01/
```

It contains the raw `0x0019` response, the complete pre-operation backup, and
the terminal preflight audit. It is immutable evidence; it is not an output
root for a later attempt. The current `tmp/i4-live-smoke...` paths are
reference inputs, not future output destinations.

## Guarded fake workflow

`GuardedPreparedPackageWorkflow` now models this order when native evidence is
required:

```text
explicit fake transport assertion
  -> fresh device detection
  -> parsed 0x0019 capacity query
  -> fresh complete backup
  -> candidate reconstruction
  -> displayed-candidate revalidation
  -> package authorization and sender binding
  -> at most one 0x101b transaction
  -> exact 0x0000 completion
  -> fresh complete post-operation backup
  -> independent read-back verification
```

The isolated `prepared_package_live_smoke.py` runner adds a separate owner
approval token, requires the exact phrase `ADD ONE INFOCARRY TEXT PACKAGE`,
requires a preview callback, and never retries. It is not imported by the
normal CLI or ttk application. Importing it performs no USB operation; fake
tests are the only execution coverage in this checkpoint.

Failure coverage includes changed capacity response, wrong device,
malformed/truncated capacity response, exact and over-limit capacity,
disconnect before the transaction, disconnect or timeout after it begins,
nonzero/missing/malformed completion, read-back mismatch, displayed-preview
mutation, and zero automatic retry. Post-start interruption remains an
indeterminate device outcome. Fake transport does not prove physical
atomicity or recovery.

## Updated command `0x0024` boundary

Command `0x0024` is **observed to equal the current dynamic-model length and
excluded from capacity authorization; broader semantics unresolved.** It is
not used to construct or authorize native capacity evidence.

## Command and approval boundary

The owner-readable protocol is
`analysis/phase-12-milestone-i4-unexecuted-modern-package-smoke-protocol-20260823.md`.
The exact future owner-reviewed runner binding would be an isolated call to
`run_prepared_package_live_smoke` using the proven `InfoCarrySession`,
`DeviceInfoClient.read_hardware`, `BackupClient`, `PyUsbWriteBackend`, and
`AuthorizedWriteSender` adapters. It is not connected to the normal CLI/GUI,
has not been run, and is not authorized by this document.

The prepared launcher is
`run_i6_prepared_package_live_smoke.py`. The following command is retained as
the historical attempt-01 command reference. It was executed under the
separate approval recorded below, stopped before any `0x101b`, and must not be
rerun because its output destinations belong to the preserved attempt-01
evidence root:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python run_i6_prepared_package_live_smoke.py \
  --source tmp/i4-live-smoke-20260823-01/chapter.txt \
  --folder-name IC_I4_PACKAGE_20260823_01 --child-name chapter.txt \
  --template-blob tmp/phase-12-milestone-i-folder-package-post-add-20260823-01/object-08-command-8004.bin \
  --timestamp 0x6a8aba6f \
  --backup-destination ${EVIDENCE_ROOT}/phase-12-milestone-i6-package-live-smoke-20260823-01/pre-operation-backup \
  --post-operation-destination ${EVIDENCE_ROOT}/phase-12-milestone-i6-package-live-smoke-20260823-01/post-operation-backup \
  --capacity-response-destination ${EVIDENCE_ROOT}/phase-12-milestone-i6-package-live-smoke-20260823-01/response-0019.bin \
  --preview-audit-destination ${EVIDENCE_ROOT}/phase-12-milestone-i6-package-live-smoke-20260823-01/preview.json \
  --audit-destination ${EVIDENCE_ROOT}/phase-12-milestone-i6-package-live-smoke-20260823-01/audit.json \
  --confirmation 'ADD ONE INFOCARRY TEXT PACKAGE' \
  --owner-approval 'APPROVE I6 PACKAGE LIVE SMOKE'
```

The command is intentionally not part of the normal application entry points
and requires both exact strings. The exact unexecuted attempt-02 command uses
only the new `phase-12-milestone-i6-package-live-smoke-20260823-02` output
root and is recorded in
`analysis/phase-12-milestone-i6-package-live-smoke-attempt-02-readiness-20260823.md`.
It requires a new explicit owner approval and has not been run.

The exact operation-specific phrase is:

```text
ADD ONE INFOCARRY TEXT PACKAGE
```

A separate owner approval token is required by the isolated runner:

```text
APPROVE I6 PACKAGE LIVE SMOKE
```

No live package write, backup, USB ownership change, or other hardware
operation was performed for I.6.

## Owner-approved preflight attempt 01

The exact owner approval and operation phrase were supplied on 2026-08-23.
The isolated launcher detected the InfoCarry and captured the native response,
then completed a complete pre-operation backup. It stopped before candidate
construction because the launcher had passed a stale `now` value into fresh
backup verification; the backup completed after that reference time and was
correctly rejected as a future-dated backup. The error was terminal and no
`0x101b` request was issued; no retry was performed.

Preserved attempt artifacts are at:

```text
${EVIDENCE_ROOT}/
  phase-12-milestone-i6-package-live-smoke-20260823-01/
```

Verified read-only facts from the preserved artifacts:

| Artifact | SHA-256 / result |
| --- | --- |
| raw `0x0019` response | `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a` |
| pre-operation backup manifest | `1c2d6b67946a188100f6ea0f8699d6d69806308381e71b6d872cd039f8356be4` |
| pre-operation dynamic blob | `bd73cb33adafacbcb0d5d0313606c94ad2de97e2810953387085234863b509d1` |
| audit | `state=failed`, `stage=fresh_backup`, `write_started=false`, `automatic_retry_allowed=false` |

The launcher clock correction is committed as `6e43927` and uses the current
verification clock for live fresh backups. The preserved attempt remains
failure/preflight evidence and
must not be overwritten. A second live attempt requires a new non-overwriting
evidence destination and separate explicit owner approval; it is not an
automatic retry.

## Tests and commits

The implementation and fake-transport coverage are in commit `09452be`.
Focused tests cover the native evidence object, candidate and authorization
binding, native workflow order/failures, and isolated runner approvals and
no-retry behavior. The complete canonical suite passes **357 tests**:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -q
```

`git diff --check` was clean before the implementation commit. The next
boundary is owner review of the unexecuted protocol; execution requires a
separate explicit approval and remains outside this checkpoint.
