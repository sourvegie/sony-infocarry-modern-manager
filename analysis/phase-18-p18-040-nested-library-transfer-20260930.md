# P18-040 — Nested Library transfer host decision record

Date: 2026-09-30
Base: canonical `main` `8c970263edf365c32671ccdce2a0da4bcb1c4496`
Branch: `task/P18-040-nested-library-transfer`
Disposition at the host checkpoint: **READY_FOR_HARDWARE_TEST**. The
2026-10-01 physical-evidence review below supersedes that checkpoint.

## Scope and evidence labels

P18-040 implements one new, absent root containing a bounded ordered TXT/BMP
hierarchy. It uses the existing `LibraryDeviceTransferPlan` and canonical
VNW-V15 candidate, operation bundle, owner-identity gate, guarded coordinator,
claim/marker/lock owner, post-backup verifier, and Device Library model. It
does not add a planner, sender, authorization path, synchronization, deletion,
overwrite, merge, Restore, VNW-V10, multiple roots, or arbitrary hierarchy.

At the host checkpoint documented in this section, all P18-040 transfer
results were synthetic host fixtures or fake transport results, with zero
hardware writes, real sender entries, real `0x101b` requests, or real claim
consumption. The later physical-evidence review below supersedes those
historical counters. A physical attempt required a separately approved exact
procedure and fresh operation-specific owner authorization.

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

The exact small fixture has **4 directories including the root and 5 leaves**:
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
pass. Independent exact-head R3 review of implementation commit
`18c97ab2716f4018ef719141331d946ac4fe9936` found **P0=0, P1=0,
P2=0**, after one staging-bypass finding was fixed and retested. Its parent is
the requested canonical base `8c970263edf365c32671ccdce2a0da4bcb1c4496`.

Pull request [#68](https://github.com/sourvegie/sony-infocarry-modern-manager/pull/68)
ran all required checks on the implementation commit: macOS and Windows
Python 3.12 portable suites, macOS Apple Silicon package and runtime smoke,
and Windows x64 package and runtime smoke all **passed**. The package jobs
exercise frozen application startup without making a device write. The final
status update is documentation-only; no nested physical capability is
promoted by this record.

## Read-only physical preflight blocker and host correction

The 2026-09-30 read-only preflight for `IC_P18_040_NESTED_20260930_01`
confirmed that the target root was absent in the fresh complete backup. The
logical planner would append it at device-root sibling position **22**.
Preparation stopped before sealing because the nested adapter compared that
destination insertion position with the prepared hierarchy root's local
ordinal **0**. These numbers describe different parent lists. No operation
identity, candidate hash, transaction hash, or approval phrase was issued.
The attempt recorded zero sender calls, real `0x101b` requests, device-changing
writes, and consumed claims.

The adapter now checks the planned root position against the fresh logical
baseline's device-root child count, while requiring the prepared root's
tree-relative ordinal to remain zero. Descendant orders still match the
prepared hierarchy exactly. Planned additions must also match the expected
delta's paths, kinds, and destination sibling orders. Existing target names
still conflict in the planner, and the delta's snapshot enforces contiguous
destination order. This changes no owner-authorization, coordinator, sender,
or recovery code. The exact prior preflight remains unsealed; any later
physical attempt needs a fresh frozen operation and separate owner approval.

## Physical-evidence review — 2026-10-01

The owner observed “Transfer complete — content verified on the InfoCarry.”
The image shows that terminal message only. Findings below use the excluded
live records in `~/Library/Application Support/SonyInfoCarryModernManager/Evidence/Library Transfer Operations/`.
Raw backups, application-state databases, and bundles remain outside Git.

### Identity and disposition

The dialog identified operation
`vnw-v15-library-operation-a784e9d213585b46acb3c92774c4e75616e2c83eab68c01172e154ce28ca4d53`,
candidate `735fe632576728dafb4d91a2f1e1cb0606b21341ac7e606f5a2c1b781ccc377c`,
transaction `39696705b9ba2cb6aad4cb1da663d8d8d68fcc774eebedb8d408108d1c40b349`,
seal `f948210ddd9608c80efe000b4396375b268e55a80c6ec978797b1e0586c3d440`,
and authorization fingerprint
`94e194f3a68162ad7c41305f82de5dbe7dc84b45e1d23d2c9ba1bbb58b0412d2`.
The matching `ui-preflight-20260930-235735-920041` is host-ready with zero
sender calls. The claim database has **no row** for that seal, and no terminal
manifest has its candidate, transaction, or seal.

The actual terminal result belongs to later preflight
`ui-preflight-20261001-000041-313292`: operation
`vnw-v15-library-operation-914f4f0ae89d6c8b5d9c296affb33ef2864d646b87cc8b9c0f360fff38793dc5`,
candidate `6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`,
transaction `e5831e0e363cab494c3f4aa859763808fa5a7676b01c6fd4ddb15edd4d58c452`,
and seal `c280a9cf797f7d0097871e594432753335217193de3e134b751aa66a4b361519`.
Both preflights bind prepared manifest
`faccb4026d356349d0554b3ff18d238648420117d09cb4bb3ff0e0cad575786f`,
but their operation identities are not interchangeable. The terminal result
proves the actual nested content physically transferred; it does not prove
execution of the specified owner-authorized transaction. No independent
evidence here establishes owner authorization of the later identity.
**P18-040 is not COMPLETE or merge-ready** pending review of this discrepancy
and owner disposition. No further write is proposed to resolve it.

### Post-approval identity investigation — 2026-10-01

Read-only comparison of the two preserved `operation-bundle.json` and
`sealed-preflight.json` files shows the same device, target, selected item,
prepared hierarchy manifest, five payloads, baseline raw-state identity
`f3f9aeb5…`, and byte-identical native capacity response. All eight raw
preflight backup objects are byte-identical. Backup capture timestamps and
manifest provenance differ. The first **content-bearing** divergence is the
new-record timestamp, `1790780256` (`0x6abd2360`) versus `1790780441`
(`0x6abd2419`), 185 seconds later. That changes the candidate
`735fe632…` to `6d50eb4c…`, transaction `39696705…` to `e5831e0e…`,
core/outer seals, and operation ID `a784e9d2…` to `914f4f0a…`.

The creation point is `library_live_preflight_action` calling
`LibraryTransferExecutionFacade.refresh_live_preflight`, then its success
callback calling `adopt_prepared_operation`. The facade obtains a new record
timestamp, native capacity, and full fresh backup and constructs a new sealed
bundle. `library_transfer_once_action` accepts owner approval and opens the
ordinary Confirm Transfer dialog; its worker calls `execute_once` on the
stored bundle. The coordinator does not replace that bundle. After claim
consumption, the live adapter rechecks device/capacity and captures a fresh
backup, then reconstructs the candidate with the **sealed** timestamp and
requires exact equality before sender entry. Those checks cannot explain a
new operation ID. The saved files prove a second UI preflight happened; they
do not record the dialog sequence or independently prove whether the in-app
approval for the second identity was supplied. The first seal has no claim.

Before this correction, `refresh_live_preflight(store=True)` and
`adopt_prepared_operation` cleared `_owner_authorized_identity` and installed
the new prepared operation. The ordinary UI preflight action also cleared
the facade's approval before calling the refresh, which is why a guard only
inside the refresh could not catch the UI route. That is approval invalidation, but permits a
new operation to be presented and approved without enforcing the earlier
external approval boundary. `execute_once` compares the in-memory approval
against the **current** bundle only; it cannot compare against an earlier
external dialog once its identity has been discarded. The defect combines a
missing freeze of the accepted owner approval with a late preflight path that
could seal a new operation. The confirmation and sender paths themselves do
not rebuild identity.

The host correction makes an accepted approval a one-operation boundary:
refresh and late worker adoption reject and discard the approved operation.
UI transfer/review/preflight actions stop an approved attempt before clearing
state, and UI review invalidation clears the facade's prepared operation and
approval together. A new preflight requires an explicit new review and new exact owner
approval; ordinary Confirm Transfer can only execute the retained bundle.
Regression tests cover an attempted post-approval refresh, a late worker
result for a different identity, the UI stop followed by a new B that cannot
execute with ordinary confirmation alone, zero claims/sender calls after
these attempts, and successful exact-match fake guarded execution. Independent
strong R3 review of the final correction found P0=0, P1=0, P2=0. This host fix
does not retroactively establish approval of the physical second identity.

Final host validation: 109 focused tests passed; 1,046 portable tests passed
with three established skips; `compileall` and `git diff --check` passed.
The Apple Silicon package built with the supported Python 3.12/Tk 9 runtime
and passed package signature verification. The packaged runtime smoke could
not be completed on this host: direct launch aborted and LaunchServices
returned `kLSNoExecutableErr` despite the executable existing in the bundle.
Windows package CI was not run locally. None of these checks accessed hardware.
The existing PR's passing CI belongs to the earlier `48720d2` head. Current-head
remote CI remains unrun: automatic approval review rejected pushing this
checkpoint because `origin` is a public repository and the task did not
explicitly authorize exporting this payload there. The local branch is ahead
of `origin` by the documentation checkpoint and this correction commit.

### Actual terminal, backup, and safety evidence

The actual attempt is `p17-017-attempt-b9e02330d4c74ed98b7017f3e44a9dd5`.
Its `result-manifest-0001.json` SHA-256 is
`dcaf3d9134a0df3073c571a41dd1b20d8d2945204a5def3e9637c46ad07e80e7`.
The audit reports `state=readback_verified`, transmission and device change
performed, one sender call, one `single_0x101b_transaction`, completion
`0x0000`, and no automatic retry. The independent verifier itself reports
`success=true` and `state=readback_verified`. Production records therefore
support one real sender call, one real `0x101b` step, and zero retries; there
is no separate USB bus capture counting packets.

Before and after backup manifests each say `state=complete` and contain eight
objects. A separate read-only check matched every object length and SHA-256
to its manifest. The post-transfer manifest SHA-256 is
`b458d839d0c312caa78556ee442477f45dce44ba2ad33496a8e7cba322567b9a`;
the post-transfer blob SHA-256 is
`6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`.
The pre-transfer blob SHA-256 is
`60f664f4a2a37b1b89f377fa83bef9e8bc8d14a482361b821314f812d9c1b106`.

Claim `baf632f1855a41d6acf9e646b2db0450` is durably `consumed` for the
actual seal; the earlier expected seal has no claim. The sender marker began
`in_flight`; `sender-marker-resolution-0001.json` records
`verified_terminal_success`, `terminal_state=readback_verified`, and zero
active markers. The read-only claim database currently has zero active marker
rows. The installation-wide indeterminate-write lock is `cleared`.

### Exact nested result and limits

Independent readback reports the following exact preorder additions with
`ordered_children_verified=true`; the actual sealed operation binds these
prepared payload hashes:

| Path below `root/IC_P18_040_NESTED_20260930_01` | Kind | Prepared payload SHA-256 |
| --- | --- | --- |
| `.` | directory | — |
| `01-intro.txt` | TXT | `1294cace32343fd906b4f103c2c23d7ccd4f86ee2c4c2eb105406a160d8fdbb2` |
| `Section-A` | directory | — |
| `Section-A/02-page.bmp` | BMP | `d3f03cf2b000e38d06825353033fe1f2a64a3e50b58c1b407d4433fffd7a3ccb` |
| `Section-A/03-notes.txt` | TXT | `779aab99368e6eb963b34fa16b66240f76991a228624d2db59fb041cbef163f9` |
| `Section-B` | directory | — |
| `Section-B/Detail` | directory | — |
| `Section-B/Detail/04-page.bmp` | BMP | `d3f03cf2b000e38d06825353033fe1f2a64a3e50b58c1b407d4433fffd7a3ccb` |
| `Section-B/Detail/05-ending.txt` | TXT | `835e7cec6de800b5f59cf0e2195caf5b89c267a275d01e4a4f4e1372331724d7` |

The verifier reports no removed pre-existing paths; 366 shared paths retain
their payloads and timestamps, fixed state is exact, and display-history and
bookmark references follow the reviewed semantic rebase while opaque bookmark
values remain preserved. The Manager emits the exact observed terminal message
only after `refresh_device_library_from_verified_transfer`, `refresh_tree`,
and `update_device_home_display` return without a caught error. Thus its
programmatic Device Library refresh succeeded; the retained image does not
independently show the refreshed tree.

This physical result supports this exact four-directory/five-leaf target
and payload set only. It does not validate arbitrary nested trees, the
41-directory/120-leaf planning fixture, other counts or depths, VNW-V10,
overwrite, merge, delete, restore, multiple packages, or synchronization.
