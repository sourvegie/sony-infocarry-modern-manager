# Capability Matrix

This is the authoritative operation-status register. `CURRENT_STATUS.md` is
the concise current-sprint view; `ROADMAP.md` and `analysis/` preserve the
chronological evidence and decision history. A row is limited to the exact
shape named in its first column. No row authorizes a broader package, target,
or recovery behavior.

| Operation / exact shape | Legacy evidence | Offline model | Live proof | Product exposure | Remaining blocker | Next authorized action |
| --- | --- | --- | --- | --- | --- | --- |
| Initial conservative envelope: one new flat root folder with 1–8 ordered TXT/BMP children | Per-shape constrained evidence only; no envelope-wide native proof | Machine-enforced profile and host-only façade; exact package grouping, hashes, limits, conflict/capacity rules | None for the envelope as a whole | Preparation/review only; `defined_not_live_enabled` | Exact evidence and later R3 enablement for each operation shape; recovery remains unresolved | Continue selection/order/prepare/preview and offline Legacy Oracle work |
| Existing root TXT replacement | Guarded existing-TXT Manager/USB captures and read-back records | Candidate, authorization, fresh backup, and independent read-back verifier | One constrained existing-TXT replacement is read-back verified | Existing guarded Device Manager write remains available | Recovery after an indeterminate write; generalized replacement semantics | Keep the existing narrow flow; diagnose indeterminate outcomes read-only |
| One root-level TXT creation | Clean native add capture and one-folder package evidence | Exact one-record construction and no-retry guarded workflow | One constrained modern root TXT add/read-back smoke | Experimental/narrow only; not a general Library transfer | Arbitrary names, state, and package shapes | Separate operation-specific review and approval for the proven shape |
| Constrained root-level TXT deletion | Native deletion-effect evidence | Narrow surviving-state/delete candidate and verifier | One constrained modern root TXT deletion/read-back smoke | Not exposed as a normal destructive action | Recovery, generalized delete, and overwrite semantics | Preserve read-only diagnosis; no general delete exposure |
| Ordered four-TXT package | P15-001 native ordered four-child capture | Exact ordered multi-child candidate and fake workflow | P15-003 exact four-TXT smoke/read-back | Not enabled by the P18 mixed-package product path | General child counts, profiles, and package combinations | Keep as historical constrained evidence |
| Flat TXT → BMP → TXT Library package | P16-001 native mixed Capture 01; P16-003B exact mixed smoke; P17-018 exact Library-package read-back | P17-002/P17-003 package contract, P17-017 output lifecycle, P17-019 wrapper reconciliation | P17-018 returned explicit `0x0000`; complete post-backup and independent read-back verified the exact `_03` folder and three ordered children. Physical opening remains a human acceptance check | Physical human opening, interrupted-write recovery, and broader shapes | P18-001 Experimental review/guarded path; later separately approved hardware use only |
| Other flat TXT/BMP combinations, nesting, multiple packages, or batch | No sufficiently specific native evidence | Preparation may remain reviewable where the P17-002 contract accepts it | Not proven for transfer | Unavailable / preview-only with a precise reason | Missing exact evidence and safety model; no automatic grouping | Obtain a separately scoped evidence and review task |
| Restore, synchronization, recovery, or alternate modes | Not established for this product boundary | No enabled candidate or execution path | Unproven | Unavailable | Physical recovery and broader state semantics | Read-only diagnosis and evidence work only |

## Exposure policy

Only a row with an exact reviewed shape and complete safety gates may be
labeled **Experimental**. The P18-001 product integration is limited to the
flat TXT → BMP → TXT Library row and keeps unsupported items preview-only.
Library selection identifies the logical change; the protocol still sends a
complete candidate library image. Every future operation requires a fresh
complete backup, immediate revalidation, exact operation-specific confirmation,
one logical transaction maximum, explicit integer `0x0000`, complete post-write
backup, independent read-back, and no automatic retry. An indeterminate result
directs the user to read-only diagnosis and preserved evidence.

This matrix records capability status; it is not an owner approval, a hardware
preflight, or permission to transmit `0x101b`.

## Machine-enforced initial envelope

The conservative product envelope is defined by the versioned
`experimental-flat-root-folder-txt-bmp-v1` profile in
`src/infocarry/capability_profile.py` (profile SHA-256
`ec69e0076e57f2eeca1634966777413f205880303dd8be7528218c77b3a7abc4`). It is
`defined_not_live_enabled`: one explicitly grouped, new, absent flat root
folder with 1–8 ordered children, strict supported TXT or validated 237×320
1-bit monochrome BMP only. The profile machine-enforces CP932-safe names,
child/source/prepared-size limits, duplicate/path rejection, capacity and
verification requirements, no overwrite/merge/delete/nesting, one package,
one logical transaction, explicit `0x0000`, and no automatic retry.

This envelope is broader than any one physical proof. Until each exact shape
has its own evidence and later R3 enablement, it is preparation/review-only;
unsupported or differently shaped items remain unavailable with a precise
reason. The host-only application foundation is implemented in
`src/infocarry/transfer_foundation.py`; it records the staged contract without
USB access, a sender, or candidate bytes.
