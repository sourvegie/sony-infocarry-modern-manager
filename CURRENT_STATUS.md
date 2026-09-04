# Current Project Status

Date: 2026-09-04

## Canonical checkpoint

Canonical `main` is `00d4836` (merged PR #28). P18-003 is complete, including
the bounded owner-observed human workflow check. No live device work is
authorized by the current governance task.

## Current product checkpoint

P18-003 adds the host workflow Select files/folder → Arrange → Prepare →
Preview through the P18-002 façade. Normal multi-file and recursive-folder
choosers are available; the approved Tk runtime has no external file-drop API,
so drag-and-drop remains unavailable without an optional TkDND dependency.

The separate `host-offline-hierarchical-library-txt-bmp-v1` profile is
`host_offline_draft_not_live_enabled`: exactly one prepared root, 1–8 TXT/BMP
leaves, at most two directory levels below the conceptual device root, no
empty directories, at most 9 directories and 17 logical nodes, 39 CP932 bytes
per component, and 259 CP932 bytes per relative path. It retains the existing
1 MiB per-leaf, 4 MiB source-total, and 1 MiB prepared-total limits.

The exact V15 `experimental-flat-root-folder-txt-bmp-v1` profile remains
unchanged and `defined_not_live_enabled`.

The flat profile is explicitly associated with reviewed model profile
`sony-vnw-v15-reviewed-v1`; it is not generic InfoCarry capability. VNW-V15
is the only verified model, with observed session identity `0x054c:0x001e`.
VNW-V10 is an explicit target with status
`UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED`: no V10 protocol, capacity,
format, candidate, authorization, or write behavior is enabled or implied.
V15 sessions must freshly obtain `0x0019` capacity evidence (64-byte response,
big-endian `+0x08`) and bind total, baseline, candidate growth, remaining-growth
capacity (total minus baseline), and remaining-after-transfer margin (total minus
candidate); V10 capacity semantics remain unknown.

The host façade records `PreparedItem[] → TransferPlan → CandidateLibrary →
Authorization → ExecuteOnce → ReadBackVerification` without USB access,
candidate bytes, sender construction, or a GUI/CLI write action. The
persistent indeterminate-write lock is installation-wide, not per-device:
an ambiguous outcome blocks every model/session across restart and reconnect.
It deliberately over-blocks because no stable physical-unit identifier is
proven. It never auto-clears from VID/PID; clearing binds the original
incident/attempt, complete read-only diagnostic evidence, and a documented
recovery decision.

## Verified recent result

P18-004's foundation checkpoint is implemented on the local task branch at
`0281633`: the portable Python 3.12 workflow now targets both macOS and
Windows, and the README records the offline-suite boundary. The focused suite
passes 38 tests with the same 3 intentional evidence skips; the full suite
passes 688 tests with 3 intentional skips both normally and under a sanitized
environment. No test writes preserved evidence or uses hardware, network, the
separate toolkit, or user application data. The branch is not pushed, so
post-change macOS and Windows GitHub CI results remain pending. No project or
package license has been authorized; owner selection is still required before
adding licensing metadata or distribution terms.

P18-001A’s bounded responsive Library correction is **COMPLETE** based on the
owner’s human-observed retest at approximately 980×680 and 1120×760 or
larger. This observation covers the tested GUI sizes only; it does not infer
hardware behavior, transfer execution, or other display environments.

The exact P17-018 TXT/BMP/TXT Library transfer remains the only integrated
Experimental physical proof. Physical opening of its folder and all three
children remains a separate human acceptance check where still noted by the
evidence records. The capability authority is
[`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md).

## Safety posture

- This task is R2 host/offline work. No hardware access, approval phrase,
  sender construction, `0x101b`, or live enablement is authorized.
- Nested content is host preparation/preview only within its exact draft
  profile. Unsupported shapes, excessive limits, automatic grouping, batch
  operations, overwrite/merge/delete, restore, synchronization, and recovery
  remain unavailable with a precise reason.
- Without fresh verified evidence, total model limit, fresh baseline model
  length, candidate growth, and remaining after transfer are **Not evaluated**.
- The supplied V10 manual statement says a new Manager transfer clears
  Bookmarks, and the owner reports corresponding V15 documentation. Do not
  infer that Marks or display history are cleared; no clear or write action is
  enabled here.
- A later enabled Experimental operation must use fresh verified backup and
  capacity evidence, exact in-app confirmation, one logical transaction,
  explicit integer `0x0000`, complete post-write backup, independent semantic
  read-back, and no automatic retry. Backup is not undo.
- Any ambiguous live outcome requires persistent installation-wide read-only
  diagnosis before a documented recovery decision can clear the lock.

## Delivery and review

The two active streams are Product Delivery and Legacy Oracle. The required
sequence is recorded in the P18-002 ADR: close visual usability, resolve
licensing/hermetic/Windows CI concerns, define the capability profile and
façade, add selection/order/prepare/preview, then separately review guarded
execution, offline tamper coverage, Oracle comparison, and one combined GUI
hardware smoke before standing Experimental enablement.

Portable baseline through merged P18-002/P18-002B: 673 passing, 3 intentional
skips. P18-003 focused validation is 37 passing; the full portable suite is
688 passing with 3 intentional skips. Compilation and `git diff --check` pass.
Independent R2 re-review is PASS with no remaining material findings. PR #28
was merged after its GitHub Python 3.12 offline-suite check passed; no hardware
or live validation is claimed.

Task outcome: `COMPLETE` for the bounded host GUI/workflow gate. The owner
reported “Everything works as expected” and supplied the offline Prepare and
device-tree Preview artifacts for the expected ordered TXT/BMP/TXT package.
This is bounded human GUI/workflow evidence only; it does not claim hardware,
USB, candidate, authorization, or live-write behavior.

## Execution workflow

The canonical working model is one **Fresh Codex Task Executor** per meaningful
task. It implements directly inside an approved scope, validates, updates only
affected durable documentation, coordinates required independent review, and
escalates material decisions. Dispatch is a responsibility rather than a
permanent intermediary; there are no permanent Junior Engineer or Secretary
roles. Hardware, capability-expansion, fail-safe lock, indeterminate-write,
and no-automatic-retry boundaries are unchanged.

Use the model for the next 3–5 meaningful engineering tasks before considering
further workflow restructuring. Record only material findings from that
evaluation.

## Historical records

The pre-P18-002 long-form status, risk register, and roadmap are preserved in
[`analysis/archive-current-status-through-p18-001a-20260902.md`](analysis/archive-current-status-through-p18-001a-20260902.md),
[`analysis/archive-risk-register-through-p18-001a-20260902.md`](analysis/archive-risk-register-through-p18-001a-20260902.md),
and [`analysis/archive-roadmap-through-p18-001a-20260902.md`](analysis/archive-roadmap-through-p18-001a-20260902.md).
