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

Independent [root-TXT R3](phase-18-p18-043-independent-root-txt-r3-review-20261010.md)
completed at `e35aab4`: **PASS / P0/P1/P2=0/0/0**. The earlier usage-limit
interruption is resolved. Reviewer independently ran 93 focused tests, direct
adapter refusal, twelve archives / 96 object hashes / 55 targets and all 43
P18-041 saved artifact hashes/candidate/readback. The diff since `2fe4134` was
four documentation files only. No general physical operation was enabled.

## Native GUI acceptance and packaging

The owner explicitly authorized isolated local macOS GUI inspection when
Computer Use could not identify the test app. Actual production Tk widgets,
callback bodies, menus and one confirmation ran with synthetic complete backups,
a fake transport, a fresh isolated profile and real USB/backend calls blocked.
Window-only screenshots were captured with local `screencapture` and inspected.
The [hash inventory](phase-18-p18-043-native-visual-checks-20261010.json) references
preserved external screenshots, widget snapshots, harness scripts and counters.

The first screenshot exposed a clipped Delete toolbar. The heading now occupies
its own line; Refresh/Back Up/More and Details/Delete occupy two compact rows.
Backup, capacity and Delete status wrap to the Device pane width. A later
minimum-window screenshot exposed a clipped status footer: progress and wrapped
status now have separate full-width rows, reserved ahead of the expandable tree.
Default 1320×800 and minimum 1080×680 layouts are visually checked after repair.
No general UI redesign or framework was introduced.

Verified visually: supported/unsupported selection and matching button/menu
states; complete filename/model/storage warning and one Delete/Cancel dialog;
Cancel button and Escape; preparing backup/validating operation, transferring,
verifying result and complete states; readable synthetic backup failure;
pre-send Stop-and-close prompt and zero send; independent verified success,
post-backup label, removed target and surviving file in the refreshed tree.
A and B each completed one separate fake send with integer zero and verified
readback. Terminal reports show real discovery/backend counters **0**, fake
sender calls **1** per success, no retry and no production safety state used.
The final pre-send close session shows fake begin/sender **0**. After-start close
and no-cancel protections also remain covered by actual callback regression
tests; no physical or interrupted-write experiment is claimed.

Python 3.12.14 / Tk runtime 9.0.4. Final corrected portable suite:
**1,172 run / 1,169 passed / three established evidence skips**, 128.933 seconds,
`/external/local-path`. Thirteen new BMP tests plus
64 relevant existing tests pass; 43 desktop regressions pass. `compileall` and
`git diff --check` pass. Eighteen old/new TXT candidates, transactions, audit
and authorization dictionaries compare identical. Existing full-suite transfer,
backup, browsing, authorization, claim, marker, lock and no-retry coverage passes.

Final corrected macOS arm64 package/signature build and established frozen
runtime smoke pass: `/external/local-path` and
`/external/local-path`. Actual native startup,
Add/workspace/close and locked/unavailable-runtime checks pass; libusb/resources
load and all real device/sender/claim/marker counters are zero. This is separate
from the observed native GUI visual checks. No Windows native execution is claimed.
Two final same-epoch wheels match SHA-256
`b73f843d52d5d168c3bd8516f9368eb21548ce2493b98e38f267b323d325a270`.
No optional dependency was installed into the reference runtime.

## Reviewed-model root-BMP continuation

`build_root_bmp_delete_candidate` shares the existing private candidate builder,
fixed-state derivation and eight-range transaction. Admission requires one
ordinary unique root BMP, exact safe NUL-terminated CP932 identity, lowercase
extension, known read/unread flag, exact 16/32-byte prefix, and the existing
237×320 uncompressed monochrome BMP parser/model. Active Marks and referenced
targets refuse; understood survivor history/bookmark pointers rebase while
opaque bytes, survivor prefixes/payloads/timestamps and checksum are preserved.

The existing host authorization binds target type from reparsed hashed baseline
bytes, not mutable audit. BMP authorization independently reconstructs the
complete candidate/state/transaction from the verified archive. Wrong target,
type, payload, state, candidate, transaction, changed/stale archive and malformed
readback are tested. Existing sender-binding construction, helper and
revalidation explicitly reject BMP; changing an audit/type label cannot enable
it. Existing complete post-backup verifier requires integer native zero,
byte-exact candidate, sole removal, protected state and unrelated objects.
No BMP GUI, pinned live bundle, runtime, claim, marker, global-lock mutation or
parallel sender is introduced. This is an offline operation/authorization model;
physical validation requires a later separately reviewed bounded live adapter.

Independent BMP archive census rehashed the same twelve complete archives / 96
objects and found **zero root BMP records**. There are 1,826 related nested BMP
occurrences, all 16-byte prefixes; this does not prove root behavior. No absent
case is counted as a candidate pass or new test skip. BMP preparation is tested
synthetically only. Census scripts/reports remain external in the visual inventory.
Final combined continuation R3 is pending at the source checkpoint.

## Hardware boundary

[Concise disposable validation procedure](phase-18-p18-043-disposable-root-txt-delete-procedure-20261010.md)
requires separate fixture-placement approval and fresh complete backup, exact
fixture verification, exclusive Manager/device ownership, separate Delete A/B
approval, one readable dialog per frozen operation, at most two deletes, native
zero and complete independent postverification. No personal files or interrupted
writes; no restore or automatic retry. This task has not run it. The original
P18-041 physical proof remains exact and does not establish the new class.

## Checkpoint disposition

IMPLEMENTED / TESTED OFFLINE: generalized root TXT and narrow root-BMP host
preparation; disabled general/BMP execution; disposable-only TXT UI workflow.
VISUALLY CHECKED: isolated native macOS synthetic Manager after layout repairs.
PHYSICALLY DEMONSTRATED: only the original P18-041 exact fixture; no new write.
TXT R3: PASS. Final GUI/BMP continuation R3: pending.
Hardware acceptance remains separate: A/B fixture placement and Delete require
new specific owner approvals. General TXT class promotion is a later reviewed
owner decision; BMP needs a separately reviewed bounded live adapter before its
own disposable validation. Nested/directory/subtree/VNW-V10 deletion unsupported.
