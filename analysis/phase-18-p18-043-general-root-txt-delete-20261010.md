# P18-043 general root-TXT Delete — 2026-10-10

Approved owner task: general root-level TXT preparation/admission, GUI checks,
packaging smoke, bounded disposable validation plan and independent R3 review;
then root-BMP operation preparation when the TXT implementation is reviewed.
Base `3c3ab288d7fe9a6700898b904ecfc9b745efbf45`; branch
`task/P18-043-general-root-txt-delete`; isolated checkout
`/external/local-path`. Risk **R3**. No physical
write, real USB request, production claim/marker/lock mutation, push or merge.

## Implemented host profile and retained execution gate

The existing `delete_workflow.py` builder, frozen candidate/authorization/bundle,
facade and Device Library service now carry a selected filename, metadata offset
and payload identity. The exact P18-041 default remains compatible. Ordinary
VNW-V15 root TXT preparation requires one unique ordinary reachable TXT,
known read/unread flags, selector `0x00000200` / 32-byte native prefix,
1–39-byte NUL-terminated CP932 roundtrip name using the existing conservative
component rules, no case/native-basename ambiguity, non-overlapping content,
exact pointer/graph/checksum/survivor validation and supported protected state.
Active Marks and target history/bookmark associations refuse; other supported
history/bookmark pointers rebase only to the identical survivor.

No arbitrary deletion payload-size ceiling is inferred from the corpus. Native
segment/header bounds and the existing baseline/candidate capacity gate control
size. Empty, small alignment cases, larger payloads and CP932 names are tested
host-side; 16-byte TXT prefixes, high selector bits, nesting, directories,
unsupported flags/names and ambiguities stay outside this initial preparation
profile. New source copies use an internal generated filename, preventing native
names from becoming host paths. The operation freezes the actual path/offset,
source, capacity, baseline, candidate, transaction, audit and confirmation.

`vnw-v15-host-root-txt-delete-v1` is **host preparation only**. Ordinary execution
is blocked in the service, facade/coordinator and claim seam. No fake result or
saved evidence flips this gate. Normal Device Library explains that root TXT
Delete awaits physical validation and keeps its Delete action disabled for this
new class. No unvalidated personal-file deletion is enabled.

`vnw-v15-disposable-root-txt-delete-validation-v1` is an opt-in experiment for
only A/B in the [fixture manifest](phase-18-p18-043-disposable-delete-fixtures-20261010.json).
A validation service/launcher is bound to exactly one target and payload;
other files, including the old P18-041 fixture, cannot execute in that mode.
The future explicit `--allow-write --manager-validation-target` route delegates
to the same UI, pinned runtime, shared durable owner, coordinator, sender,
claim/marker/global lock and independent readback. It is not authorization to
run now. One ordinary Delete/Cancel decision binds the readable frozen target;
no entered fingerprint, extra dialog, transport or safety store is added.

## Evidence and validation

[Independent archive census](phase-18-p18-043-root-txt-corpus-20261010.md):
12 complete backups, 96 objects rehashed, nine distinct blobs; 55 root TXT
structural cases all pass independent raw survivor/content-excision/checksum
checks. Protected-state preparation passes 28; 26 active-Mark states and one
referenced target refuse. Real records cover first/middle/last root positions,
read/unread, ASCII names 10–21 bytes, 32-byte prefixes, payloads 29–1,863.
Broader physical behavior remains unproven. Originals are unchanged outside Git.

New portable tests exercise host admission, alignment/empty/larger payloads,
CP932 names, unsupported selectors/state/path, raw identities/ambiguities,
references/Marks, frozen candidate/source/audit/owner/gate tampering, class gate
reachability, stale/reconnect-equivalent state, wrong disposable payload,
no retry, nonzero/disconnect/bad readback, one sender and Device Library refresh.
Actual GUI callback tests cover both disposable targets and refuse ordinary
unvalidated selections before runtime setup. Existing Delete/placement/transfer/
backup/runtime regressions remain in the full suite.

Exact code head `2fe413418e5d3a825263d955590c80ad3c34332f` full portable suite:
**1,159 run / 1,156 passed / three established intentional evidence skips**
in 125.615 seconds. Seventeen new admission tests, 40 Device Library regressions
and 95 focused Delete/placement/provider/UI/model regressions pass. Python
3.12.14 / Tk 9.0 binding; `compileall` and `git diff --check` pass. The final
external corpus rerun confirms 55 targets, 28 prepared with identical archived
candidate hashes, 27 protected-state refusals, and unchanged original objects.
Logs remain outside Git under `/external/local-path`.

Independent reviewer `/root/p18_043_r3_review` inspected exact head `2fe4134`
against base `3c3ab28`, source/tests and canonical lifecycle. Its interim message
reported no P0/P1/P2 findings so far. The agent then failed with an account usage
limit before issuing its final review report. This is **not a completed R3
review or production-readiness decision**. No final independent findings count
is claimed. Resume independent review at the unchanged code head; no material
review-correction round has yet occurred. Resource exhaustion stops the task
before the root-BMP operation continuation. The previously reviewed pure BMP
model is preserved, with no new BMP transaction/authorization/execution.

macOS arm64 package build and ad-hoc signature verification passed. Existing
frozen runtime smoke passed with Tk runtime 9.0.4, resources/libusb loaded,
actual Manager startup/Add/workspace/close checks, locked/unavailable-runtime
regression, and all real device/sender/claim/marker counters zero. Its isolated
report is `/external/local-path`; no Windows
native package execution is claimed. Wheel build uses installed setuptools/
wheel via `pip wheel --no-deps --no-build-isolation` because the optional `build`
module is absent; no dependency was installed into the read-only reference
runtime. Two final same-epoch wheel builds compare identical: SHA-256
`0afce951443964f6cbd6da8236d8d4a5e14e64479ffa0c7ea4ddd878891c1bd1`.
Installing that wheel into an isolated `/private/tmp` target and importing the
new service/profile passes. Final package build log:
`/external/local-path`; full test log:
`/external/local-path`. No runtime dependency or
read-only checkout was modified.

GUI visual inspection is pending: native Computer Use could not identify the
isolated Tk process/test app, and timed out resolving its native app bundle.
The owner has been asked to authorize local macOS launch/screenshot tools as
an alternative, as the Computer Use rules require explicit authorization for
another GUI method. No screenshot/visual success is claimed. The actual native
package functional smoke is distinct from visual inspection.

## Hardware boundary

[Concise disposable validation procedure](phase-18-p18-043-disposable-root-txt-delete-procedure-20261010.md)
requires separate fixture-placement approval and fresh complete backup, exact
fixture verification, exclusive Manager/device ownership, separate Delete A/B
approval, one readable dialog per frozen operation, at most two deletes, native
zero and complete independent postverification. No personal files or interrupted
writes; no restore or automatic retry. This task has not run it. The original
P18-041 physical proof remains exact and does not establish the new class.

## Checkpoint disposition

IMPLEMENTED / TESTED OFFLINE: generalized root TXT preparation, immutable
selected-file binding, fail-closed execution gate and disposable-only UI route.
PHYSICALLY DEMONSTRATED: only the original P18-041 exact fixture; no new write.
PENDING: independent final R3, GUI visual inspection, separately approved
fixture placement and bounded A/B physical validation. This is a preserved
engineering checkpoint, not COMPLETE or READY_FOR_HARDWARE_TEST. General TXT,
BMP, nested, directory/subtree and VNW-V10 live deletion remain unsupported.
