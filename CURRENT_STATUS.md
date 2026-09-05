# Current Project Status

Date: 2026-09-05

## Canonical checkpoint

Canonical `main` is `359c27adf473c86a8f2770de64712b81dc893e25` (merged P18-006 /
PR #32). P18-004 is complete and P18-005 is merged with its R3 review
complete. P18-005 macOS and Windows Python 3.12 offline CI both passed in
[PR #31 workflow run 33944258579](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/33944258579).
No physical device work is authorized by the current governance task.

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

## P18-005/P18-006 guarded-boundary checkpoint

P18-005 is merged on canonical `main`. Its guarded coordinator reaches only
the exact reviewed logical shape: one new absent root folder with ordered
TXT → BMP → TXT children. It requires the exact reviewed VNW-V15 profile, the
Experimental capability identifier, one sealed operation bundle, current
hash-only confirmation, fresh backup/capacity revalidation, one sender claim,
complete post-backup, and independent semantic read-back. The broader flat
profile remains non-live; the hierarchical profile remains preview-only; VNW-
V10 remains uncharacterized and non-write-capable.

P18-006 adds the offline/fake A–O adversarial matrix and positive control. It
covers shape/profile/content/binding/backup/capacity/drift/confirmation/lock/
transport/one-shot/post-backup/read-back/auxiliary-state/GUI-CLI boundaries,
including concurrent sender attempts. The matrix passes with no hardware or
USB access. It found and corrected two R3 safety issues: exact reviewed
profile-value substitution was not rejected, and malformed or boolean
post-start completion values were not classified as indeterminate. The latter
now activates the existing installation-wide persistent lock; nonzero integer
completion remains determinate failure. No automatic retry is allowed.
Independent R3 review passed with no correction round required. The reviewer
recorded a P2 carry-forward: the one-shot claim is process-local, so crash or
cross-process claim persistence is not proven. That limitation does not block
this host-only gate because normal GUI/CLI surfaces do not expose the
coordinator; it must be resolved or explicitly accepted before standing
physical-write enablement.

## P18-007 Legacy Oracle checkpoint

P18-007 is `COMPLETE` for the offline Legacy Oracle boundary and representative
differential corpus. Corpus A covers one TXT, B covers four ordered TXT
children, and C covers the exact TXT → BMP → TXT product shape. A retains an
unexplained four-byte allocation/offset discrepancy; B normalizes only the
independently established timestamp/checksum differences; C is
`NOT_COMPARABLE` as a whole blob because the preserved native and modern
baseline/target identities differ, while its typed package projection matches.
Hierarchical Corpus D was not available and remains exploratory external
evidence only.

The final preserved host-side boundary is the `0x101b` command header and
payload immediately before driver/USB submission. No transmission, hardware,
or live Oracle operation occurred. The reusable comparator preserves raw
differences alongside any normalized view, and no production transfer code or
capability row was broadened. Independent R2 review/re-review passed with no
remaining material findings. The focused PR is [PR #33](https://github.com/sourvegie/sony-infocarry-modern-manager/pull/33), with both [macOS](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/33962042514/job/101295488675)
and [Windows](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/33962042514/job/101295488741)
Python 3.12 CI passing. A same-baseline P16 whole-blob observation or
hierarchical fixture is not required for the completed A–C host-side result.
The P18-006 process-local one-shot claim remains unresolved pre-hardware work.

## Verified recent result

P18-004's foundation-quality closure is implemented on the fresh
`task/P18-004-foundation-quality` branch from canonical `main`: the portable
Python 3.12 workflow targets both macOS and Windows, the README records the
offline-suite boundary, and the project declares the owner-authorized MIT
License in [`LICENSE`](LICENSE) and package metadata. The focused suite passes
38 tests with the same 3 intentional evidence skips; the full suite passes
688 tests with 3 intentional skips both normally and under a sanitized
environment. No test writes preserved evidence or uses hardware, network, the
separate toolkit, or user application data. Post-change macOS and Windows
GitHub CI both pass in [PR #30 workflow run 33886273729](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/33886273729)
on `macos-latest` and `windows-latest` with Python 3.12. The generated
evidence-package trees are explicitly preserved as byte-exact non-text files
so their manifests and source hashes remain portable across checkout
platforms.

The MIT License applies only to this project's own source code. It does not
grant rights to Sony proprietary software, firmware, documentation,
trademarks, captures, backups, private evidence, or the separate
`InfoCarry-Toolkit` and reference archives. The guarded execution and
independent read-back boundary is now host-reviewed under P18-005/P18-006;
no live behavior is enabled for normal application surfaces and no physical
compatibility is claimed.

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

- This task is host/offline verification with two bounded R3 corrections. No
  hardware access, approval phrase, sender construction, `0x101b`, or live
  enablement is authorized.
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

The two active streams are Product Delivery and Legacy Oracle. P18-004 through
P18-006 are merged, and P18-007 closes the offline Legacy Oracle
differential/comparison gate. The pre-hardware sequence is:

P18-007 Legacy Oracle complete
↓
pre-hardware crash/cross-process one-shot persistence closure
↓
required R3 host-side review/validation
↓
separate owner approval
↓
combined GUI hardware validation of the exact enabled profile

The one-shot persistence issue remains unresolved and has not been accepted by
the owner. Hardware validation is not the immediate next task.

Portable baseline figures through P18-006 remain recorded below for history.
P18-006 focused validation is 17 passing; the guarded/P17 focused validation
is 155 passing; the full portable suite is 714 passing with 3 intentional
skips. Compilation and `git diff --check` pass.
Independent R2 re-review is PASS with no remaining material findings. PR #28
was merged after its GitHub Python 3.12 offline-suite check passed; no hardware
or live validation is claimed.

Task outcome: `COMPLETE` for the bounded host GUI/workflow gate. The owner
reported “Everything works as expected” and supplied the offline Prepare and
device-tree Preview artifacts for the expected ordered TXT/BMP/TXT package.
This is bounded human GUI/workflow evidence only; it does not claim hardware,
USB, candidate, authorization, or live-write behavior.

P18-006 outcome: `COMPLETE` for host-verifiable offline guarded-transfer and
tamper coverage, with the documented P2 cross-process claim carry-forward.
This does not authorize a device write. The exact
TXT/BMP/TXT shape remains the only guarded-execution shape; broader flat,
hierarchical, and V10 paths remain unavailable or preview-only.
The required GitHub Python 3.12 offline workflow passed on both
`macos-latest` and `windows-latest` in [PR #32 workflow run 33950704593](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/33950704593).

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
