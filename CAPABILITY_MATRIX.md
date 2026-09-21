# Capability Matrix

This is the authoritative operation-status register. `CURRENT_STATUS.md` is
the concise current-sprint view; `ROADMAP.md` and `analysis/` preserve the
chronological evidence and decision history. A row is limited to the exact
shape named in its first column. No row authorizes a broader package, target,
or recovery behavior.

| Operation / exact shape | Legacy evidence | Offline model | Live proof | Product exposure | Remaining blocker | Next authorized action |
| --- | --- | --- | --- | --- | --- | --- |
| Initial conservative envelope: one new flat root folder with 1–8 ordered TXT/BMP children | Per-shape constrained evidence only; no envelope-wide native proof | Machine-enforced profile and host-only façade; exact package grouping, hashes, limits, conflict/capacity rules | None for the envelope as a whole | Preparation/review only; `defined_not_live_enabled` | Exact evidence and later R3 enablement for each operation shape; recovery remains unresolved | Continue selection/order/prepare/preview and offline Legacy Oracle work |
| One host/offline hierarchy: one prepared root, 1–8 TXT/BMP leaves, depth/count/path/size limits below | Existing nested backup trees and format constraints support offline modeling; nested creation is not proven | Machine-enforced `host-offline-hierarchical-library-txt-bmp-v1`; deterministic ordered manifest and exact device-tree preview through the unified façade | None | Host prepare/preview only; `host_offline_draft_not_live_enabled` | No nested candidate, authorization, sender, completion proof, or recovery model | Continue offline validation and independent R2 review; do not enable live transfer |
| Generic Local Library → Device Library logical plan (ordered TXT/BMP files and arbitrary nested folders) | Existing Library source references and read-only backup hierarchy; no new native-format inference | `LibraryDeviceTransferPlan` preserves selection/sibling order and subtree paths, validates source bytes and CP932 components, detects conflicts, and emits an independent expected path delta; scale fixture covers 61 folders/150 mixed leaves | None; no candidate or transaction is constructed | Host-only destination/conflict planning from a loaded backup; the normal `Transfer` action does not authorize or send | Candidate growth, metadata overhead, device auxiliary state and physical fit remain unknown unless separately evidenced; no hierarchy candidate model | Keep the logical model separate from capability and execution policy; no live generalization |
| Existing root TXT replacement | Guarded existing-TXT Manager/USB captures and read-back records | Candidate, authorization, fresh backup, and independent read-back verifier | One constrained existing-TXT replacement is read-back verified | Existing guarded Device Manager write remains available behind the shared persistent application-wide claim/marker/lock boundary; offline preview remains available | Recovery after an indeterminate write; generalized replacement semantics | Keep the existing narrow flow and shared safety owner; diagnose indeterminate outcomes read-only |
| One root-level TXT creation | Clean native add capture and one-folder package evidence | Exact one-record construction and no-retry guarded workflow | One constrained modern root TXT add/read-back smoke | Experimental/narrow only; not a general Library transfer | Arbitrary names, state, and package shapes | Separate operation-specific review and approval for the proven shape |
| Constrained root-level TXT deletion | Native deletion-effect evidence | Narrow surviving-state/delete candidate and verifier | One constrained modern root TXT deletion/read-back smoke | Not exposed as a normal destructive action | Recovery, generalized delete, and overwrite semantics | Preserve read-only diagnosis; no general delete exposure |
| Generalized selected-file/subtree deletion plan | Existing logical hierarchy only; generalized record/reference effects are unresolved | Host-only `DeviceLibraryDeletePlan` computes a deterministic closure and expected removals; rejects root/system, stale, overlapping and auxiliary-state-unsafe selections | None | Not exposed; Device Library Delete remains disabled for arbitrary selections | No candidate construction, auxiliary-reference policy, sender, or live verifier for generalized deletion | Keep offline planning only; do not connect it to hardware |
| Ordered four-TXT package | P15-001 native ordered four-child capture | Exact ordered multi-child candidate and fake workflow | P15-003 exact four-TXT smoke/read-back | Not enabled by the P18 mixed-package product path | General child counts, profiles, and package combinations | Keep as historical constrained evidence |
| Flat TXT → BMP → TXT Library package | P16-001 native mixed Capture 01; P16-003B exact mixed smoke; P17-018 and P18-015 exact Library-package read-back | P17-002/P17-003 package contract, P17-017 output lifecycle, P17-019 wrapper reconciliation; P18-010/P18-014 host proofs bind exact fixed targets and established display-history/bookmark preservation | P17-018 returned explicit `0x0000` and verified its exact `_03` folder. P18-015 separately returned `0x0000`; P18-025 physically validated the exact reviewed VNW-V15 UI/adapter/canonical lifecycle for `IC_P18_LIBRARY_20260913_03`: one logical sender, one real `0x101b`, retries `0`, exact `0x0000`, complete post-backup, independent `readback_verified`, and preserved auxiliary/shared state | Reviewed narrow shape; normal readiness and the shared guarded path accept this exact reviewed VNW-V15 shape when fresh evidence and separate owner authorization are supplied; default UI state remains authorization-gated and no generalized live transfer is enabled | No blocker for this exact recorded proof; interrupted-write recovery, other shapes, broader targets, and VNW-V10 remain unavailable | Preserve the exact guarded path and require fresh operation-specific evidence and owner authorization for any future run; do not enable V10 or broader shapes |
| Flat TXT → BMP → TXT → TXT Library package | P18-030 deterministic direct-content preparation; P18-032 physically validated the exact VNW-V15 shape and shared auxiliary-state policy in the preserved evidence namespace | `verified-vnw-v15-four-leaf-direct-v1`, exact ordered four-child profile, generic multi-package candidate/authorization/workflow/read-back seams, fresh-backup/capacity/conflict gates, and typed operation binding | P18-032 exact proof: one reviewed disposable VNW-V15 root, one logical sender, one real `0x101b`, retries `0`, explicit `0x0000`, complete post-write backup, independent `readback_verified`, exact four-leaf target, and preserved shared/unrelated state; physical counters for P18-033 remain zero | Physically verified narrow shape; normal readiness accepts the exact order and the generic guarded path remains available when fresh evidence and separate owner authorization are supplied; default UI/CLI action remains authorization-gated and no generalized live transfer is enabled | Interrupted-write recovery, broader targets, other shapes, destructive semantics, and VNW-V10 remain unavailable | Preserve the exact guarded path and require fresh operation-specific evidence and owner authorization for any future run; do not enable arbitrary four-leaf permutations or broader counts |
| Other flat TXT/BMP combinations, nesting outside the host/offline profile, multiple packages, or batch | No sufficiently specific native evidence | Preparation may remain reviewable only where an exact profile accepts it | Not proven for transfer | Unavailable / preview-only with a precise reason | Missing exact evidence and safety model; no automatic grouping | Obtain a separately scoped evidence and review task |
| Restore, synchronization, recovery, or alternate modes | Not established for this product boundary | No enabled candidate or execution path | Unproven | Unavailable | Physical recovery and broader state semantics | Read-only diagnosis and evidence work only |

## Exposure policy

Only a row with an exact reviewed shape and complete safety gates may be
labeled **Experimental**. The P18 product integration covers only the exact
flat TXT → BMP → TXT and TXT → BMP → TXT → TXT Library rows and keeps
unsupported items preview-only.
Library selection identifies the logical change; the protocol still sends a
complete candidate library image. Every future operation requires a fresh
complete backup, immediate revalidation, exact operation-specific confirmation,
one logical transaction maximum, explicit integer `0x0000`, complete post-write
backup, independent read-back, and no automatic retry. An indeterminate result
directs the user to read-only diagnosis and preserved evidence.

This matrix records capability status; it is not an owner approval, a hardware
preflight, or permission to transmit `0x101b`.

## P18-025 exact physical proof

P18-025 is the exact recorded physical proof for one owner-authorized normal
UI/adapter/canonical guarded VNW-V15 operation targeting
`IC_P18_LIBRARY_20260913_03`. Fresh native `0x0019` capacity was 3,145,728
bytes; the target was absent before the write; one logical sender call and one
real `0x101b` returned exact native `0x0000` with zero retries. The durable
claim was consumed once, the sender marker completed `none → in-flight →
resolved` with an empty final marker store, and the installation-wide lock
remained cleared. Complete post-write backup and independent semantic
readback verified the exact TXT → BMP → TXT target, shared/unrelated-state
preservation, the reviewed display-history/bookmark policy, no removed paths,
and 343 shared paths. The durable terminal result records independently
verified success.

Evidence is preserved outside Git at the terminal summary and result manifest
for this operation; the allocator's `p17-017` attempt-directory label is kept
unchanged as historical evidence. This proof does not authorize another run or
broaden any row beyond the exact reviewed profile and lifecycle.

## Device-model boundary

The only verified device-model profile is `sony-vnw-v15-reviewed-v1` for Sony
InfoCarry VNW-V15. Its observed session USB identity is `0x054c:0x001e` and
its supported capacity interpreter is read-only `0x0019`, a 64-byte response
with the big-endian total candidate-model capacity at `+0x08`. Session
capacity observations are fresh and bind total capacity, verified baseline
model length, candidate growth, remaining-growth capacity (total minus
baseline), and remaining-after-transfer margin (total minus candidate); a
previous session's capacity is never reused.

Sony InfoCarry VNW-V10 is an explicit product target with profile
`sony-vnw-v10-uncharacterized-v1`, status **UNCHARACTERIZED / READ-ONLY
DISCOVERY REQUIRED**. Its USB identity, protocol, storage format, capacity
query/interpreter, display profile, and write envelope are not established.
It has no candidate, authorization, transfer, delete, or restore capability;
do not infer V15 behavior from the model name.

VID/PID and bus/address are session observations, not proven physical-unit
identity. Until a stable unit identifier is established, any ambiguous
device-changing outcome sets one installation-wide persistent fail-safe lock
that deliberately blocks every model/session. A lock never auto-clears from
matching VID/PID or reconnect; clearing requires the original incident and
attempt, complete read-only diagnostic evidence, and a documented recovery
decision.

## Machine-enforced initial envelope

The conservative product envelope is defined by the versioned
`experimental-flat-root-folder-txt-bmp-v1` profile in
`src/infocarry/capability_profile.py` (profile SHA-256
`bd556ba933213e36b9bfc121c8f349a9022cebcdbbccdd1623b6b1ec814cb15b`). It is
`defined_not_live_enabled`: one explicitly grouped, new, absent flat root
folder with 1–8 ordered children, strict supported TXT or validated 237×320
1-bit monochrome BMP only. The profile machine-enforces CP932-safe names,
child/source/prepared-size limits, duplicate/path rejection, capacity and
verification requirements, no overwrite/merge/delete/nesting, one package,
one logical transaction, explicit `0x0000`, and no automatic retry.
The profile is explicitly associated with
`sony-vnw-v15-reviewed-v1`; it is not a generic InfoCarry profile.

This envelope is broader than any one physical proof. Until each exact shape
has its own evidence and later R3 enablement, it is preparation/review-only;
unsupported or differently shaped items remain unavailable with a precise
reason. The host-only application foundation is implemented in
`src/infocarry/transfer_foundation.py`; it records the staged contract without
USB access, a sender, or candidate bytes.

## Host/offline hierarchical draft

`host-offline-hierarchical-library-txt-bmp-v1` is a separate preview-only
profile, not an expansion of the V15 transfer envelope. It accepts exactly one
prepared root with 1–8 ordered TXT/BMP leaves, maximum directory depth 2 below
the conceptual device root, no empty directories, maximum 9 directories and
17 logical nodes, maximum 39 CP932 bytes per component and 259 CP932 bytes per
relative path. Source/prepared limits remain 1 MiB per leaf, 4 MiB aggregate
source, and 1 MiB aggregate prepared payload. Any mismatch fails closed.

The preview reports hierarchy, types, order, prepared sizes, destinations,
validation, and conflicts. Without a fresh verified baseline and fresh native
capacity evidence, total model limit, baseline model length, candidate growth,
and remaining after transfer are **Not evaluated**. No nested candidate,
authorization, sender, or write path exists.

P18-037 adds a separate generic logical tree/transfer model that does not
inherit this draft's 1–8-leaf, depth-2, 9-directory, or 17-node bounds. Its
offline scale fixture contains 61 directories and 150 mixed TXT/BMP leaves.
The model checks names, source freshness, ordering and conflicts, but does not
serialize a candidate or imply that a larger tree fits on any device. Its
normal UI `Transfer` action only produces this host-side plan. The generalized
delete model is likewise a closure/expected-delta plan only; the product Delete
control remains disabled for arbitrary selections.

## P18-016 normal product readiness exposure

The normal ttk Library workflow now exposes a host-only reviewed-shape
readiness review for exactly one explicitly selected prepared root package with
authoritative TXT → BMP → TXT or TXT → BMP → TXT → TXT direct children. It
shows the destination, prepared sizes and hashes, verified-baseline conflict
information, lower-bound capacity information when available, and the fresh
evidence still required for any future operation. The legacy Prepare/Review/
Refresh Checks/Send controls remain outside the normal Library surface. The
P18-037 primary Transfer action routes only an exact package through the
existing guarded facade; this is not reusable authorization or generalized
live transfer capability. VNW-V10 remains uncharacterized.

## P18-017 host execution integration

The normal ttk path now delegates fresh live preflight and any future
`Transfer once` interaction through
`src/infocarry/library_transfer_execution.py`. The facade has no operation
binding or runtime in the default desktop launch, so the ordinary UI remains
disabled until a separately authorized exact fresh VNW-V15 operation is
supplied and all canonical gates pass. When supplied, the facade delegates to
the existing guarded coordinator and adapter; it does not implement native
transfer semantics or a GUI-specific write path. P18-025 physically validated
one exact fresh VNW-V15 operation for target
`IC_P18_LIBRARY_20260913_03` and the TXT → BMP → TXT shape through that guarded
path. This is evidence of the narrow reviewed profile, not reusable
authorization; every future operation still requires its own fresh evidence
and owner approval, and this matrix does not authorize it.

The P18-037 primary **Transfer →** action now admits that existing facade only
after the generic plan proves one explicit imported package maps exactly to a
root-level reviewed three- or four-leaf profile. It continues through the
same readiness, fresh preflight, typed operation-specific confirmation, and
one-shot execution callbacks; unsupported plans stop host-only. No second
candidate builder, coordinator, authorization, persistent safety owner,
sender, or live-success decision was added. The default app remains inert
without its separately supplied operation binding/runtime. This is UI
reachability repair, not capability promotion.
