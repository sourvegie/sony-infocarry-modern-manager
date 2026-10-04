# P18-041H — Bounded physical root-delete timestamp experiment

Date: 2026-10-04 (Asia/Tokyo)

Preparation branch: `task/P18-041H-bounded-physical-root-delete-timestamp-experiment`
Starting head: `da8f75ad053a2bc8a74cca48ca075fbd736e3174` (P18-041G)
Base: `origin/main` at `5bca280ffbd673fa56a2646a65b0329a4dc496f2`

Disposition: **FIXTURE PRE-STAGING REQUIRED — PREPARE SEPARATE AUTHORIZED PLACEMENT FIRST**

This checkpoint prepares the smallest physical experiment justified by
P18-041G. It does not authorize or perform the delete, fixture placement,
Manager automation, USB session, sender call, claim, marker mutation, lock
mutation, or any hardware write.

The authoritative P18-041G evidence is the timestamp-rule characterization at
[`phase-18-p18-041g-timestamp-rule-characterization-20261004.md`](phase-18-p18-041g-timestamp-rule-characterization-20261004.md)
and its machine-readable comparison. The P18-041F structural candidate remains
offline-only because the native timestamp rule is unresolved.

## Exact experiment identity

The only accepted device boundary is the verified Sony InfoCarry VNW-V15:

| Field | Frozen value |
| --- | --- |
| Model | `VNW-V15` |
| Session USB observation | `USB\\Vid_054c&Pid_001e` |
| VID/PID | `0x054c:0x001e` |
| Operation | one legacy/native root-level ordinary TXT `Delete Selected` |
| Target device path | `root\\IC_P18_041G_CLOCK_01.txt` |
| Experiment delete count | exactly one |

The disposable fixture is exact and must already exist on the device before the
sealed delete experiment starts:

| Field | Value |
| --- | --- |
| Filename | `IC_P18_041G_CLOCK_01.txt` |
| Content bytes | `P18-041G timestamp probe 01\\r\\n` |
| Encoding | ASCII subset / CP932-compatible |
| Line ending | CRLF |
| Length | 29 bytes |
| SHA-256 | `9541c1b9d09ee7d4ab91c704755c4bea8b2022c3bb8f50aa15c1a990bf80c35d` |

Read-only repository evidence contains no copy of this fixture and no device
presence observation. A stable physical-unit identity beyond VID/PID and a
pre-execution native candidate/transaction identity are also not available in
this preparation workspace. Therefore the package must not mint an owner
approval identity or advance to execution. A separately authorized placement
operation is required first; do not combine placement and delete. The tooling
machine-enforces this gate with the canonical
`01-fixture-prestage/placement-readback-or-backup-report.json` artifact, which
must prove separate authorization, one placement operation, independent
readback/backup verification, and completion before the delete session. After
that placement, the future delete run must still satisfy the stable-unit and
pre-execution-candidate identity gates described below.

The machine-readable contract is
[`phase-18-p18-041h-experiment-manifest-20261004.json`](phase-18-p18-041h-experiment-manifest-20261004.json).

## Safety boundary and pre-staging gate

The placement operation is a separate owner-authorized operation. If the
fixture is absent, the operator must:

1. prepare and review a separate exact fixture-placement identity using the
   already-proven guarded transfer path, if that path is appropriate for the
   actual VNW-V15 state;
2. obtain separate operation-specific owner approval for placement;
3. perform and independently verify placement, including a fresh complete
   backup/readback and exact fixture identity; and
4. start a new P18-041H session with a new fresh complete pre-delete backup.

This task performs none of those actions. A successful placement does not
authorize the later delete.

The existing production Delete UI remains disabled. The new host-only tooling
is [`src/infocarry/p18_041h_experiment.py`](../src/infocarry/p18_041h_experiment.py)
and the CLI wrapper is [`scripts/p18_041h_experiment.py`](../scripts/p18_041h_experiment.py).
They only read or create caller-selected local evidence files.

## Prepared evidence layout

Create a new, non-overwriting session directory with the `session` command.
The prepared layout is:

```text
P18-041H-<unit>-<run>/
  session-manifest.json
  00-identity/
    device-boundary-readonly.json
    capture-plan.json
    recovery-plan.json
    owner-authorization-identity.json
  01-fixture-prestage/
    separate-placement-authorization.json
    placement-readback-or-backup-report.json
    fixture-source-copy.txt
  02-pre-delete-backup/
    manifest.json
    object-*.bin                         # exactly eight objects
  03-manager-before/
    <exact Manager files and sidecars>
    snapshot-manifest.json
  04-time-observations/
    before-manager-initialization.json
    after-initialization-idle.json
    immediately-before-delete.json
    immediately-after-delete-return.json
    event-map.json                       # separate semantic mapping
  05-native-delete-capture/
    raw-delete.usblog                    # immutable raw capture
    native-transaction-report.json
    candidate-artifact/                  # if preserved
    native-terminal-result.json          # Manager result and 0x0000
  06-manager-after/
    <exact Manager files and sidecars>
    snapshot-manifest.json
  07-post-delete-backup/
    manifest.json
    object-*.bin                         # exactly eight objects
  08-sealed-evidence/
    evidence-seal.json
    hashes.txt
  09-recovery-decision/
    recovery-decision.json
  10-analysis/
    delete-evidence-verification.json
```

The pre-delete backup and raw native capture are immutable evidence. Preserve
the complete backup, every object hash, exact Manager-before files and
sidecars, raw capture, native terminal result, and all generated reports before
any recovery discussion.

## Preflight checklist

The operator must stop before Delete unless every item below is true.

- The device is the exact VNW-V15 boundary. VID/PID is only a session
  observation; a typed, read-only, hash-bound stable physical-unit identity
  artifact beyond VID/PID is also required for owner approval. Any ambiguous
  model or unit identity stops the experiment.
- The fixture was placed in a separate, completed, independently verified
  operation. It is present exactly at `root\\IC_P18_041G_CLOCK_01.txt`, has
  length 29, and has the sealed SHA-256 above.
- No other add, delete, subtree selection, directory selection, rename,
  replacement, synchronization, restore, or unrelated Manager mutation is
  planned or pending.
- The fresh pre-delete backup is complete, independently re-verified, has
  exactly eight objects, and is retained immutably. It contains the exact
  fixture payload and records the device/model boundary.
- Exact Manager-before files and sidecars are copied and hash-manifested.
- The recovery plan in
  [`phase-18-p18-041h-recovery-plan-20261004.json`](phase-18-p18-041h-recovery-plan-20261004.json)
  has been reviewed. It does not assume an unproven modern Delete/Restore
  path.
- All four time-observation destinations are fresh and empty, and the raw
  event map will remain separate from the observation files.
- The exact owner-authorization identity exists before approval. Its
  fingerprint binds the device, stable physical-unit identity, fresh
  pre-backup, target, fixture, capture plan, no-retry policy, recovery-plan
  reference, and independently verified pre-execution candidate/transaction
  hashes and artifacts.
- If a candidate or transaction hash is only available after the Delete, the
  identity is not frozen and approval is rejected. No procedural approval is
  accepted in its place.
- The installation-wide indeterminate-write lock is clear and the durable
  single-use claim/marker lifecycle is ready in the normal native environment;
  this preparation package does not mutate either one.

## Time-observation checklist and tool

The host-side tool records local time, UTC, epoch milliseconds, timezone name
and offset, host identity, and fixture filesystem creation/last-write values
when a local source copy is available. It never queries a device clock. A
device-clock observation may be supplied only from an already-safe/read-only
path; the tool stores its hash and provenance rather than asserting a value it
did not observe.

Run once at each exact event point, keeping the event names unchanged:

```text
PYTHONPATH=src .venv/bin/python scripts/p18_041h_experiment.py observe-time \
  --destination <session>/04-time-observations/before-manager-initialization.json \
  --event before_manager_initialization

PYTHONPATH=src .venv/bin/python scripts/p18_041h_experiment.py observe-time \
  --destination <session>/04-time-observations/after-initialization-idle.json \
  --event after_initialization_idle

PYTHONPATH=src .venv/bin/python scripts/p18_041h_experiment.py observe-time \
  --destination <session>/04-time-observations/immediately-before-delete.json \
  --event immediately_before_delete

PYTHONPATH=src .venv/bin/python scripts/p18_041h_experiment.py observe-time \
  --destination <session>/04-time-observations/immediately-after-delete-return.json \
  --event immediately_after_delete_return
```

If the exact local fixture source is available, pass
`--fixture-source <path-to-IC_P18_041G_CLOCK_01.txt>` at each point. Build the
separate map only after all four files exist:

```text
PYTHONPATH=src .venv/bin/python scripts/p18_041h_experiment.py event-map \
  --destination <session>/04-time-observations/event-map.json \
  --before-manager-initialization <session>/04-time-observations/before-manager-initialization.json \
  --after-initialization-idle <session>/04-time-observations/after-initialization-idle.json \
  --immediately-before-delete <session>/04-time-observations/immediately-before-delete.json \
  --immediately-after-delete-return <session>/04-time-observations/immediately-after-delete-return.json
```

## Native transaction capture

The owner/operator uses the normal native Manager/Terminal environment because
Work-managed USB visibility is not assumed. Configure the existing native USB
capture tool before Manager initialization and preserve the raw capture
without editing it.

Before any future owner approval, obtain a stable native pre-execution
candidate capture if the normal Manager environment exposes one without
sending. Inspect it offline and preserve its candidate artifact and report in
`05-native-delete-capture/`. If the native environment cannot expose a stable
candidate/transaction identity before sender start, stop: the approval
fingerprint cannot be frozen and procedural approval is invalid.

Create the immutable operation-binding metadata first; the capture parser
requires it and rejects any target or operation mismatch:

```text
PYTHONPATH=src .venv/bin/python scripts/p18_041h_experiment.py operation-binding \
  --output <session>/00-identity/operation-binding.json
```

```text
PYTHONPATH=src .venv/bin/python scripts/p18_041h_experiment.py capture-report \
  <pre-execution-native-capture> \
  --capture-phase pre-execution \
  --operation-binding <session>/00-identity/operation-binding.json \
  --artifact-destination <session>/05-native-delete-capture/pre-execution-candidate-artifact \
  --output <session>/05-native-delete-capture/pre-execution-candidate-report.json
```

The pre-execution candidate report, exact fresh backup, separate fixture-
placement report, fixture source, read-only device-boundary observation,
capture plan, and recovery plan are the
inputs to the owner identity command. It must succeed before the exact owner
phrase is requested. The candidate report is never a historical expected
output lookup table.

The physical sequence is exactly:

1. capture the first time point before Manager initialization;
2. initialize Manager and wait for the explicitly defined idle point;
3. capture the third time point immediately before invoking Delete;
4. invoke exactly one legacy/native root-level Delete Selected for the exact
   fixture;
5. do not click again, retry, reopen a dialog, select another item, or run any
   other Manager action after sender start or ambiguity;
6. require the normal native terminal success result and record its explicit
   value (`0x0000`); any malformed, missing, nonzero, interrupted, timed-out,
   disconnected, or ambiguous result stops the sequence;
7. capture the fourth time point immediately after normal Delete return;
8. preserve Manager-after files/sidecars and take the complete post-delete
   eight-object backup; and
9. seal all evidence before considering recovery.

For owner approval, preserve the candidate report/artifact and its exact
operation-binding sidecar with
`--capture-phase pre-execution` before approval. If the native environment
cannot expose a stable candidate/transaction identity at that point, stop;
procedural approval is not accepted. After the physical operation, inspect
the separate post-execution raw capture. The parser rejects zero or multiple
ordinary `0x101b` transactions and preserves a candidate artifact without
replaying it:

```text
PYTHONPATH=src .venv/bin/python scripts/p18_041h_experiment.py capture-report \
  <session>/05-native-delete-capture/raw-delete.usblog \
  --operation-binding <session>/00-identity/operation-binding.json \
  --capture-phase post-execution-evidence \
  --artifact-destination <session>/05-native-delete-capture/candidate-artifact \
  --output <session>/05-native-delete-capture/native-transaction-report.json
```

The report records the one transaction, exact one-delete fixture binding,
command header, declared length, all
eight range lengths and hashes, candidate dynamic-blob hash, and aggregate
transaction hash. The parser does not decode native request-4 completion;
that result must be preserved independently from Manager, bound to the
transaction-report hash, and must be exactly normal terminal success. The
terminal JSON must contain `format:
infocarry-p18-041h-native-terminal-result-v1`,
`status: normal_terminal_success`, `normal_return: true`,
`native_completion: "0x0000"`, `sender_invocations: 1`, `retry_count: 0`,
`physical_operation_count: 1`, `add_count: 0`, `subtree_operation: false`,
the exact target path, matching native-log/candidate/transaction hashes, and
`transaction_report_sha256` over the final transaction report. Any missing,
nonzero, interrupted, timed-out, disconnected, or ambiguous result stops the
sequence without retry.

## Independent post-delete verifier

The verifier requires the exact fixture in the pre-backup, exactly one removed
reachable path, no added reachable paths, a complete eight-object post-backup,
byte-identical shared file payloads, valid checksums, and a complete
surviving-record table. The table includes before/after serialized order and
offset, reachability, path/name/type metadata, pointer fields, payload lengths
and hashes, the full four-byte timestamp values, and the changed byte offsets.

The preserved candidate artifact and operation-binding sidecar, separate
fixture-placement report, post-execution transaction report, terminal result,
and event map are mandatory inputs. The verifier
independently derives the expected structural delete from the fresh baseline,
masks only surviving timestamps and the derived checksum, and requires the
native candidate to match that exact fixture deletion. It then requires the
post backup to match the candidate under the same timestamp-only
normalization, rejects unexplained surviving serialized-record changes,
fixed-state changes without native demonstration, altered shared payloads,
and any path delta beyond the one exact fixture removal. The independent
report still does not make a live-success claim.

```text
PYTHONPATH=src .venv/bin/python scripts/p18_041h_experiment.py verify-delete \
  --before <session>/02-pre-delete-backup \
  --after <session>/07-post-delete-backup \
  --candidate-artifact <session>/05-native-delete-capture/candidate-artifact \
  --fixture-prestage-report <session>/01-fixture-prestage/placement-readback-or-backup-report.json \
  --event-map <session>/04-time-observations/event-map.json \
  --native-transaction-report <session>/05-native-delete-capture/native-transaction-report.json \
  --terminal-result <session>/05-native-delete-capture/native-terminal-result.json \
  --output <session>/10-analysis/delete-evidence-verification.json
```

Seal independently valid evidence before any recovery discussion:

```text
PYTHONPATH=src .venv/bin/python scripts/p18_041h_experiment.py seal \
  --session-root <session> \
  --verification-report <session>/10-analysis/delete-evidence-verification.json \
  --destination <session>/08-sealed-evidence/evidence-seal.json
```

The seal command independently reparses the canonical raw capture and reruns
the verifier against the canonical backups, separate fixture-placement report,
event map, transaction report, terminal result, candidate artifact, and raw
capture; it refuses fabricated validity flags, incomplete sessions, external
raw captures, and overwrite. Do not
declare the result complete if any required report, terminal result, event
map, post-backup, exact path/payload/checksum condition, or seal is missing.

## Owner-authorization identity

The exact approval identity is generated only from immutable pre-execution
inputs. The host-only identity builder binds:

- VNW-V15 device/model boundary;
- fresh pre-delete manifest, dynamic-blob, and object hashes;
- exact target path and fixture identity;
- candidate dynamic-blob and complete transaction SHA-256 values, but only
  when their phase is explicitly `pre-execution`;
- the raw pre-execution capture and preserved candidate-artifact hashes;
- the exact operation-binding metadata and sidecar hash;
- a typed, hash-bound stable physical-unit identity artifact beyond the
  volatile VID/PID observation;
- the capture-plan hash and required event set;
- the literal no-retry policy; and
- the recovery-plan id and hash;
- the separately authorized, independently verified fixture-placement report
  and its post-placement backup identity.

The device-boundary JSON must identify a stable unit value that is not merely
the VID/PID, and must state `observation_mode: "read_only"` plus a named
`identity_source`. This preparation workspace contains no such observation;
inventing a serial or accepting a procedural label is forbidden.

It emits one fingerprint and the only accepted future phrase format:

```text
AUTHORIZE P18-041H PHYSICAL ROOT DELETE <fingerprint_sha256>
```

The phrase is not an authorization in this preparation task. The CLI identity
step independently verifies the complete pre-backup, exact fixture source,
separate placement report, candidate/raw-capture artifact, canonical plans,
and stable unit-boundary observation. Altered or partial capture/recovery
plans are rejected:

```text
PYTHONPATH=src .venv/bin/python scripts/p18_041h_experiment.py owner-identity \
  --pre-delete-backup <session>/02-pre-delete-backup \
  --capture-plan <session>/00-identity/capture-plan.json \
  --recovery-plan <session>/00-identity/recovery-plan.json \
  --candidate-report <session>/05-native-delete-capture/pre-execution-candidate-report.json \
  --fixture-prestage-report <session>/01-fixture-prestage/placement-readback-or-backup-report.json \
  --fixture-source <path-to-IC_P18_041G_CLOCK_01.txt> \
  --device-boundary <session>/00-identity/device-boundary-readonly.json \
  --output <session>/00-identity/owner-authorization-identity.json
```

If the native environment cannot expose a stable candidate/transaction
identity before owner approval, the identity builder refuses to produce an
approval identity; the operation must stop and be redesigned. A post-delete
capture cannot be used to retroactively authorize the operation.

## Recovery plan

Retain the complete fresh pre-delete backup immutably. No recovery is
automatic. After the delete evidence is sealed, recovery requires a separate
reviewed and owner-authorized operation whose identity is bound to the exact
retained backup, fresh device evidence, recovery candidate, transaction, and
post-recovery verification plan. The package does not assume that the
unproven modern Delete/Restore path can recover the device. If no reviewed
recovery route can be frozen, preserve evidence and stop for owner direction.

The detailed machine-readable plan is
[`phase-18-p18-041h-recovery-plan-20261004.json`](phase-18-p18-041h-recovery-plan-20261004.json).

## Validation and review boundary

The focused P18-041H tests cover exact fixture identity, non-overwriting
session preparation, all four time events plus separate mapping, the separate
fixture-placement gate, canonical manifest/recovery-plan identity, raw-capture
reparsing, the pre-execution owner-identity gate, and the independent
before/after verifier.
They pass 10 tests. The full portable suite passes 1,056 tests with 3
established skips. `git diff --check` and Python bytecode compilation also
pass.

This is an R3 preparation package. An independent reviewer must inspect the
exact branch diff, this report, both JSON plans, the host-only module/script,
focused and full test results, and the safety counters. Review must report
P0/P1/P2 and must confirm that no production Delete UI or live sender path was
added. Physical execution remains a separate owner decision after the package
reaches the hardware-test boundary.

The first independent read-only R3 review reported P0=0, P1=3, P2=0. Those
findings were remediated by requiring the canonical separate-placement report,
independently reparsing raw captures during report loading/sealing, and
requiring exact canonical capture/recovery plans. A fresh exact-head R3 review
then reported **P0=0, P1=0, P2=0 — PASS**, confirming the corrected package,
the disabled production Delete UI, and zero hardware/write/sender/claim/
marker/lock activity. No owner approval identity or physical operation is
authorized by this package.

## Current counters and disposition

Evidence from this preparation task:

```text
hardware/USB sessions              0
hardware writes                    0
real 0x101b                        0
production sender calls            0
claims consumed                    0
sender-marker mutations            0
installation-wide lock mutations  0
```

The fixture is not present in repository evidence and no device observation
was performed. A separately authorized placement operation is required before
a new sealed delete session can begin; the stable device identity and
pre-execution candidate must then be captured before owner approval. Final
disposition is therefore:

**FIXTURE PRE-STAGING REQUIRED — PREPARE SEPARATE AUTHORIZED PLACEMENT FIRST**
