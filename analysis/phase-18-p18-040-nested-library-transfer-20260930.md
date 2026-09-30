# P18-040 — Nested Library transfer host decision record

Date: 2026-09-30
Base: canonical `main` `8c970263edf365c32671ccdce2a0da4bcb1c4496`
Branch: `task/P18-040-nested-library-transfer`
Disposition while review/CI is pending: **HOST IMPLEMENTED; NOT YET READY FOR HARDWARE TEST**

## Scope and evidence labels

P18-040 implements one new, absent root containing a bounded ordered TXT/BMP
hierarchy. It uses the existing `LibraryDeviceTransferPlan` and canonical
VNW-V15 candidate, operation bundle, owner-identity gate, guarded coordinator,
claim/marker/lock owner, post-backup verifier, and Device Library model. It
does not add a planner, sender, authorization path, synchronization, deletion,
overwrite, merge, Restore, VNW-V10, multiple roots, or arbitrary hierarchy.

All P18-040 transfer results in this record are synthetic host fixtures or
fake transport results. They are **not** physical-device evidence. Hardware
writes, real sender entries, real `0x101b` requests, and real claim consumption
for P18-040 are zero. A future physical attempt requires a separately approved
exact procedure and fresh operation-specific owner authorization.

## Prepared tree and staging

The existing `PreparedContentArtifact` provides one semantic identity over
root name, preorder node list, node type, parent path/ID, sibling order,
source bytes/hash, and prepared payload bytes/hash. Temporary absolute host
paths are excluded from that identity. The nested host profile admits one
root, 1–8 TXT/BMP leaves, at most four directory levels below device root,
and the existing CP932, size, and path bounds. It rejects empty directories,
unsupported names/types, malformed paths, duplicate siblings, and collisions
after native TXT/BMP extension projection. Those are host safety bounds, not
observed device limits.

The selected Local Library root is copied into `prepared-package/source`
under the operation evidence directory. Validated CP932 TXT and BMP bytes
are placed in `prepared-package/prepared`; a hierarchy manifest and catalog
copy live alongside them. Reload requires the exact path set and all source
and payload hashes, rejects symbolic links, and rechecks TXT encoding and BMP
validation. The seal and operation ID are bound to a durable
`operation-binding.json` file. Removing the original import path after the
sealed preflight does not change the staged operation.

## Candidate and one-shot binding

The canonical candidate builder adds exactly the new root hierarchy to a
fresh complete baseline. It serializes ordered native child tables and
TXT/BMP payloads, preserves pre-existing metadata and payloads, applies the
reviewed auxiliary-state rebase, and checks actual final serialized candidate
size against fresh native `0x0019` evidence. The audit separately reports
source bytes, prepared payload bytes, candidate growth, final candidate size,
and remaining capacity. The candidate is a complete library image at the
transport boundary; the logical operation remains exactly one add.

Fresh preflight constructs the final candidate and transaction, then seals the
operation identity. Owner approval is supplied for that exact identity before
ordinary Confirm Transfer OK. A changed baseline, candidate, transaction,
operation ID, authorization identity, or seal invalidates prior approval.
Mismatch or missing staged bytes stops before coordinator entry, claim,
marker, and sender. The P18-039 historical mismatch remains recorded in its
own decision record and is not treated as nested-transfer authorization.

## Independent host readback and UI refresh

The readback verifier derives expected paths, direct sibling order, kinds,
and TXT/BMP hashes from the sealed prepared tree, independently of candidate
record-construction logic. It requires a complete verified post-backup,
exact expected additions, no missing/extra nested path, no removed pre-existing
path, unchanged shared file payloads/metadata, and the reviewed auxiliary
state. After a successful fake guarded run, the Manager's current Device
Library model reloads the verified post-backup and displays the nested tree
without restart.

A second synthetic baseline already contains an unrelated nested folder and
TXT leaf. The candidate and independent readback preserve that folder, its
payload, and the reviewed template paths while adding the requested root.

## Fixtures and host checks

The exact small fixture has **3 directories including the root and 5 leaves**:
`01-intro.txt`, `Section-A/{02-page.bmp,03-notes.txt}`,
`Section-B/Detail/{04-page.bmp,05-ending.txt}`. It covers exact candidate
paths, ordering, payloads, independent readback, guarded fake execution,
and Device Library refresh.

The scale fixture has **41 directories and 120 TXT/BMP leaves** over multiple
depths. It tests only the existing logical plan and report serialization;
the bounded candidate profile does not admit that scale and no hardware
capacity or file-count limit is inferred from it.

Adversarial host cases cover source drift/missing source, missing sealed
payload, identity changes for bytes/order/rename/move/add/remove/type,
invalid CP932/overlong/deep paths, duplicate and native-projected names,
existing target, insufficient native capacity, candidate/transaction
tampering, missing or stale owner approval, a new preflight after approval,
and fake nonzero or ambiguous sender completion without a second sender entry.
The ambiguous case sets the installation-wide indeterminate-write lock and
does not retry. Pre-sender cases
assert zero fake sender calls, zero claims, no active sender marker, and no
indeterminate lock. The existing P18-039 and durable claim/marker/lock suites
remain regression gates.

The focused P18-040 suite passes 23 tests. The full portable suite passes
1,039 tests with 3 established skips. `compileall` and `git diff --check`
pass. Independent R3 worktree review found **P0=0, P1=0, P2=0**, after one
staging-bypass finding was fixed and retested. Final committed-head review
and macOS/Windows CI/package checks remain required before changing the
disposition to `READY_FOR_HARDWARE_TEST`.
