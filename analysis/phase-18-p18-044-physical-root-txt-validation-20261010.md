# P18-044 — physical root-TXT Delete validation — 2026-10-10

Base `e1cfda6efc6cb8cfebcfe484fcb1e3bb69d54be3`; branch
`task/P18-044-root-txt-physical-validation`. R3 host preparation precedes every
new physical placement. The existing P18-043 A/B procedure and exact manifest
remain authoritative. At initial preparation no physical write approval had
been received; the final, separately approved A placement closeout is below.

## Read-only preparation evidence

External session:
`/external/local-path`.
The owner specifically approved the complete backup and hardware-info query,
then authorized necessary out-of-sandbox commands throughout this task.
That permission is not fixture-placement or Delete authorization.
Legacy Manager was confirmed closed for read-only access.

`preparation-backup-01`: eight complete objects, all manifest/object hashes
verified, structural/checksum parse valid; 300 file payloads / 454 records.
Blob SHA-256 `6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`;
manifest `44ed6023384c87f2b5d0217d20b0a7d4c577c4dd67c55ec2c4b39c0b36457b99`.
This is the preserved P18-041 post-delete blob, not a newly performed deletion.
Neither exact A nor B path exists. `current-device-fixture-inspection.json`
contains only fixture identities/counts and archive hashes.

`preparation-info-01/command-0019-hardware.bin`: existing read-only hardware
query, SHA-256 `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a`.
The native capacity parser derives 3,145,728 bytes from established +0x08;
no capacity meaning is assigned to other fields.

`current-safety-inspection.json`: SQLite opened URI mode=ro/query_only,
integrity check OK, ten consumed historical claims, sender marker count zero,
no alternate safety files, database unchanged hash
`b679330cdf40622ec9f1756e6e2b568b969ec55cd611d10947fd1c6a7a10ebb3`.
The global record is retained with state cleared / canonical `.locked=False`.
The initial diagnostic mistakenly classified record presence as active; the
corrected report supersedes that derived field. No production safety file was
modified or cleared. Canonical execution will recheck the existing owner.

Local ASCII/CRLF fixture sources match the immutable manifest exactly:
A 32 bytes (`d5011189…`), B 51 bytes (`5a5bdff8…`). Raw personal backups,
candidates and transaction ranges stay outside Git.

## Necessary fixture-placement preparation

The existing placement profile admits only the old P18-041 clock fixture.
An explicit bounded A/B opt-in now uses the same facade, frozen bundle, native
capacity/backup, operation identity, reconnect equivalence, canonical durable
claim/marker/global lock, one sender, no retry and complete readback. No generic
Add action, new transport, persistence store or live pipeline is introduced.
A/B names and payloads come from the immutable P18-043 manifest; missing opt-in,
other target/payload/model, existing case/native-stem collision and unsupported
TXT prefix/state refuse. Disposable reports cannot masquerade as P18-041H.

The real baseline's eligible templates have 53-byte payloads and three alignment
bytes. The default duplicate-then-replace model retains copied alignment and
adds final alignment, yielding four/five new-file padding bytes for A/B; the
existing 0..3-byte validator correctly refused. `fresh_new_allocation=True`
is explicit and used only by this bounded placement: the existing duplication
model constructs the new prefix/payload/alignment in one pass. Original content
including opaque gaps is byte-exact, with only the new insertion added. Default
existing behavior and every prior operation's opt-in state remain unchanged.
Seal verification independently reconstructs the frozen candidate, allocation,
transaction, audit and protected state from baseline/template/timestamp/capacity.

Tests cover source and new payload alignment 0..3, both native prefix lengths,
opaque old gaps, wrong opt-in/payload type, all survivor bytes/prefixes/payloads/
timestamps, default compatibility, exact A/B admission and frozen rebinding,
changed/reconnected state, cancellation, one sender, native failure, disconnected/
bad readback, and canonical claim/marker/lock lifecycles. Launcher defaults do
not initialize runtime/safety; its one readable owner answer binds the existing
complete internal identity, with no entered fingerprint. Confirmation cannot
silently adopt another candidate. No automatic retry exists.

`placement-current-state-host-check.json` prepares both A/B against copies of
the actual saved complete archive with fake capacity/runtime and no sender.
`offline-placement-delete-inverse.json` independently exercises the existing
placement builder then root-TXT deletion model: A grows 128 bytes / zero pad,
B 148 bytes / one pad. Each deletion returns the exact original dynamic blob
and protected responses; all 300 payloads and 454 timestamps match. These are
host checks, not physical results. Original raw evidence remained unchanged.

Portable Python 3.12 suite: **1,190 run / 1,187 passed / three established
intentional skips**, 137.547 seconds, `/external/local-path`.
30 focused placement/launcher regressions pass; compileall and diffcheck pass.
Independent strong exact-head R3 at `52c75c802212c3ca652305e1890cc3d187021100`
is **PASS: P0/P1/P2=0/0/0**, no correction round. Reviewer independently ran
92 focused tests (90 pass / two established capture-04 skips), rehashed all
eight saved backup objects and native capacity, checked both fixtures across
all four actual eligible templates, proved raw survivor/content/gap preservation
and eight exact deletion inverses, and compared old/new default bytes,
transactions and audit. The full completed log was inspected independently.
Report `/external/local-path`, SHA-256
`098c1954d97e5577f31b62c14b63d2a62fb7d93d553a0be4a0920136ed9ff1c4`.
No source changed after the reviewed head; only review closeout documentation.
Exact disposable placement is READY_FOR_HARDWARE_TEST, not physically proven;
no placement/Delete approval has yet been received. No interrupted test or
inferred runtime result is counted as a pass.

## Physical execution boundary

After required review, prepare and retain one fresh exact A placement review,
then obtain its operation-specific owner answer before the first sender start.
The existing guarded framework must independently verify exact placement and
unaffected content before Delete. Use reviewed Device Library A validation:
select A, Delete, one readable frozen confirmation; obtain explicit A Delete
approval, execute once and independently verify full readback/terminal evidence.
Stop all physical operations on A failure/ambiguity. Prepare B for execution
only after A's complete independent success, then repeat separate placement and
Delete approvals. No personal content is a test target.

This serial A-then-B placement order minimizes simultaneous disposable writes;
it retains the authoritative maximum of two separately approved Deletes and
its no-retry/evidence requirements. It does not authorize an operation.
`experimental_root_txt_placement.py` only delegates the existing facade, with
explicit --allow-write and a waiting readable owner confirmation. The Delete
launcher/UI remains the reviewed P18-043 route. Read-only permission never
supplies the owner answer. Do not mutate locks/markers manually.

A/B physical results, native completion, physical sender/transaction counts:
**NOT RUN / zero**. No independent USB bus trace captured. General root-TXT
execution remains disabled; no capability promotion follows from host evidence.

## Fresh frozen A preparation — awaiting separate owner approval

The reviewed launcher captured a new complete baseline and native capacity,
then stopped at its sole readable owner prompt. No confirmation has been
supplied, no A claim consumed and no sender started. Review is preserved as
`placement-A-frozen-review.json` in the external session, SHA-256
`2c45c2fc1ccec4f4f66fe2e3660777141923ab57c3b118cd91c3497d7b698441`.
Frozen seal `66d8b016efeba68df34450e85d706a21dc414ed016aacd9d802602326faaae61`;
candidate `fb912fed8176549f2fd938a685e1545c00a3f66bb0faccb890446abdf5233710`;
transaction `0be2d941affb0deed2a2c003434dfaeb24b95284726189eaa3e04ff245c0bc06`.

Independent fresh artifact verification is PASS: all eight before objects equal
the earlier saved raw state, A/B absent, exact A payload/template/timestamp,
reconstructed authorization/candidate/audit/all eight transaction ranges match,
300 survivor payloads and 454 timestamps preserved, protected associations
unchanged. Current read-only SQLite/lock inspection finds ten historical claims,
no A claim, no markers, cleared global lock and unchanged safety bytes.
`INDEPENDENT_A_PREPLACEMENT.md` external report SHA-256
`676ed2137e870b191e93ce9e233104faeb498681b46df2c5ebd7413563888a98`.
`placement-A-preapproval-evidence-inventory.json` freezes 22 prepared files.
An operation-specific request now awaits the owner's answer for **A placement
once only**; it authorizes neither A Delete nor any B operation. Source/tests/
scripts remain identical to reviewed `52c75c8`; subsequent commits are only
documentation. Do not rebuild or replace the pending frozen operation after
approval; the existing coordinator must revalidate equivalence before sending.

## Owner-approved exact A placement — independently verified COMPLETE

The owner explicitly selected **Authorize this A placement once** for the
already frozen operation. Receipt `placement-A-owner-approval.json` binds the
unchanged review/complete owner identity. All 22 prepared artifacts rehashed
unchanged immediately before the sole answer was supplied to the already
waiting launcher. Process launched at documentation head `652aaee`, owner
answer released at documentation-only `ebfe114`; source/tests/scripts remained
identical to R3-reviewed `52c75c8`. No candidate or timestamp regenerated.

Actual result: native **0x0000**, launcher exit **0**, **one sender / one audited
transaction / zero retries**, complete eight-object pre/post archives and
`readback_verified`. Sole added path `root\IC_P18_043_DELETE_A.txt`, exact
manifest 32-byte payload. Actual post blob equals frozen candidate
`fb912fed8176549f2fd938a685e1545c00a3f66bb0faccb890446abdf5233710`;
archive growth 128 bytes, 300→301 files and 454→455 records. All 300 surviving
prefixes/payloads and 454 surviving timestamps, full original content/gaps/
trailer, checksum/structure, all eight protected associations and five protected
response blocks independently verified. Permitted reference rebases preserve
the same survivors. Nothing unrelated removed, changed or normalized.

Evidence root: application `Evidence/Library Transfer Operations/` directory
`p17-017-attempt-5b0e325cba594f47a5fe5af6b2ca4393`. Actual before manifest
`341eeeff4102535adc4c2c6750bebdaae17e5eb77c137e86b6b7fc87cf3d03f8`;
actual after manifest
`a06894f58d5c7dc875bf5d8fb33c0f6db2f7dbdc6e19f177fb609d909051c61c`.
Result manifest
`7ff0e168b292b28d433c2a46aa5aaad9d922bbf1a4be41dd8a48f165cb9c1653`
is hash-bound by verified terminal resolution. Exact A claim consumed; current
store contains eleven consumed claims, zero sender markers and a cleared global
lock. No manual claim/marker/lock cleanup or automatic retry. Safety inspection
and evidence review were read-only; original physical evidence remains external.

External session reports:
`PHYSICAL_A_PLACEMENT_REPORT.md`, SHA-256
`3aebb7ad613035c7cec3665d16f6e2b8abd4d15404f92a3a07fa2fc83bca3925`;
`INDEPENDENT_A_POSTPLACEMENT.md`, SHA-256
`6363828cd5bd2a4c62d16ae188e406cbefa07bdd3afc83b59595dc8973df715c`,
**PASS**. Reviewer independently inspected actual complete archives, raw
survivor/content/protected-state invariants, exact approval/result binding,
claim/marker/lock and chronological ordering. Machine verification, original
approval, frozen/execution inventories and safety reports remain beside them.

No independent USB bus trace exists. One-transaction/no-retry evidence is the
actual execution audit, durable lifecycle and reviewed one-shot implementation,
not an independent bus capture. This is only one exact A placement on the
observed VNW-V15 state. **A Delete and all B operations are not authorized or
started.** No new GUI hardware proof, generic TXT addition/deletion, BMP,
nested/directory/subtree, VNW-V10, physical atomicity or recovery is established.
Normal general Delete remains disabled. No physical operation follows this
approval automatically; stop pending a new separate owner-authorized operation.
Source/test code unchanged, full completed 1,190-test validation and R3 remain
applicable; final closeout changes are documentation only. No push or merge.

## Actual Device Library A Delete preparation — READY_FOR_HARDWARE_TEST

The owner authorized narrow local macOS screenshot/accessibility inspection
and **read-only preparation only**, not a Delete. Native Computer Use could
not identify the running Python validation Manager. Existing system tools
locate PID 64693 / InfoCarry Manager. Tk coordinate actions initially did not
invoke backup; the native Device → Back Up menu succeeded. No implementation
change, installed automation infrastructure, injected Tk hook or alternate
USB pipeline was used. The backup-complete information sheet was acknowledged;
this was not a write confirmation. The live Device Library was filtered to A,
its sole exact row selected, then the normal Device → Delete action prepared
its candidate and opened one real **Confirm Delete** dialog. Both menu commands
invoke the same existing toolbar callbacks. **Delete remains unclicked.**

Fresh displayed backup:
application `Backups/InfoCarry-backup-20261010-235604`, all eight objects
verified, manifest
`ff2c10f72751c6239388ee1267c1566b1a3df8c89fe597320dceb4d61b8945af`.
A's exact 32-byte payload and native record at `0x680` match the immutable
fixture manifest. Canonical raw state equals the independently verified actual
A-placement post state; no intervening device content drift is observed.

Actual service-prepared root under application `Evidence/Library Transfer Operations/`:
`prepared-root-txt-delete-b60d36c89b0a487d9da0ae45911b7a94`. Its own fresh
eight-object baseline manifest is
`011c7571c2959bb05327800e6fa26f82f2ff822e4e55dbf4a9d1911bf5b75f1a`.
Frozen seal `4d40b06da105a0da740c57cd548cf29cbe761d41a56861aa8ba8ac89af1afa42`;
candidate `6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`;
transaction `e5831e0e363cab494c3f4aa859763808fa5a7676b01c6fd4ddb15edd4d58c452`;
authorization `fc5e4482d04ab7322e42a7af1399dd5ba6d707275300daa17a359636546296f6`.
`delete-A-frozen-review.json` is read-only navigation derived from this actual
sealed envelope and existing canonical identity fields, not a substituted or
newly adopted operation. `delete-A-preapproval-evidence-inventory.json` freezes
all 22 prepared files. The UI retains its own prepared bundle and single modal.

Independent actual GUI pre-Delete review **PASS**, P0/P1/P2 findings **0/0/0**:
`INDEPENDENT_A_PREDELETE.md` external session report SHA-256
`6d007f00309775cb38a1db41c5b28d1e0f94944c93856acec789775720ab5511`.
The reviewer verifies all fresh/displayed/placed archive identities, exact
source/candidate/transaction ranges/audit/authorization/capacity, sole A
removal, all 300 survivor prefixes/payloads and 454 surviving timestamps, raw
content/gaps/trailer, valid structure/checksum and eight protected associations.
Candidate and prospective five protected blocks exactly reproduce the original
pre-A-placement state. This is candidate proof, not future physical success.

Actual native screenshots preserve selected A and the single readable dialog;
`Delete-A-final-confirmation.png`, SHA-256
`2180445ac39f89efa79697d1ceaa02c924a2d3a025f146ca7c0daccef2672857`,
shows filename, VNW-V15, storage warning and Delete/Cancel. Cancel is the
focused/default action. Current read-only safety verification passes: eleven
historical consumed claims, **zero claims for this Delete seal**, **zero active
markers**, retained global lock cleared; DB hash `6b967147…` unchanged during
inspection. No physical Delete approval, sender invocation or transaction.
76 relevant UI/service/admission/facade regressions pass, 10.986 seconds,
external log `/external/local-path`. Full
1,190-test checkpoint remains applicable; no source/tests/scripts changed.

**Stop at the one unconfirmed dialog.** Owner approval must bind this already
frozen operation; do not regenerate or adopt another candidate. If approved,
click Delete once through the reviewed UI, require exact native integer zero
and complete independent actual post-backup/sole-removal/survivor/protected/
terminal verification, with no automatic retry. A ambiguity stops physical
work; no B preparation or execution follows automatically. No push or merge.

## Exact A Device Library physical Delete — independently verified COMPLETE

After the single frozen GUI modal was presented, the owner asked whether to
click Delete and supplied a completed Manager screenshot. Parent did not
click/release the confirmation. Canonical audit records `approval_consumed=true`
for the same sealed A identity. No separate chat approval receipt or independently
observed physical click is asserted. Actual in-app decision binds unchanged
seal `4d40b06d…`, candidate `6d50eb4c…`, transaction `e5831e0e…`, authorization
`fc5e4482…` recorded above. No refresh/adoption/rebinding or implementation change.

Actual evidence namespace:
`p17-017-attempt-c955a03c396e484193236a21751ef927`, under the application
`Evidence/Library Transfer Operations/` directory. Native **0x0000**,
`readback_verified`, **one audited sender / one transaction / zero retries**.
Both actual before/post backups contain all eight verified objects. Only A
removed: 301→300 files, 455→454 records, 128-byte archive decrease.
All **300 surviving prefixes/payloads and 454 serialized timestamps**, original
content/gaps/trailer, valid graph/checksum and eight protected associations
preserved. All five protected blocks equal the exact prospective result.
**All eight actual post-backup objects are byte-for-byte identical to original
read-only `preparation-backup-01`.** This is a validated placement/Delete
inverse, not a Restore operation.

Actual before manifest
`84b8148e52ae89fd5ae05a2ccb51908bbc2cd9626c0a91fd745f1bb3ad4fee60`;
after manifest
`a8db674c6cd6e9e7da80ec8a1a753bdfc448776bda1066fb5aa0ab92000b30ed`.
Verified terminal result manifest
`f29d439ea99f32a63137191e9a63ed97dfbe9146865c97f44a15cc6e24046710`.
Exact claim consumed, current store twelve consumed claims / zero active
sender markers; global lock clear. No manual clearing, reset or retry.
The historical in-flight marker snapshot remains immutable in the result;
separate terminal proof and current store establish its normal resolution.

Actual user-supplied screenshot is preserved byte-exact as
`Delete-A-owner-supplied-completion.png`: post-backup loaded, A absent under
its exact search filter, verified-completion status. This proves the supplied
GUI display; full survivor integrity comes from raw complete backups.

Independent actual saved-evidence review **PASS**,
`INDEPENDENT_A_POST_DELETE.md`, SHA-256
`4ef0b438a02668062608349715caf5e98f51ec1f6fcf08e8b8c34433bb8ac685`;
external complete closeout `PHYSICAL_DELETE_A_REPORT.md`, SHA-256
`76ebf9f51a46a636caf77e962811854d3b4c35172f4e95106785403616b7b27b`.
Machine independent/parent checks and frozen/execution inventories are retained
beside them. Reviewer verifies all 22 frozen and 21 execution artifacts, source
and approval binding, direct raw preservation, current safety and chronology,
without USB, GUI input, evidence changes or production safety mutation.

**Physical proof is limited to this one exact ordinary 32-byte root TXT A on
VNW-V15 through the Device Library workflow.** B not placed/prepared/deleted;
general class gate remains disabled. No BMP/nested/directory/subtree/V10,
atomicity/recovery or independent USB bus trace inferred. No repeat A operation,
B action, push or merge follows this result. All code unchanged; 76 focused
Delete tests and full 1,190-run / 1,187-pass / three-established-skip checkpoint
remain valid. Closeout documentation only. This A claim is terminally consumed;
any delayed chat answer cannot authorize replay.

## Fresh B placement preparation — awaiting separate physical approval

Owner task continuation from clean `7185313` authorizes read-only B
preparation and later assessment, with separate B placement and Delete
approvals. The unchanged exact placement launcher captures current native
capacity/full backup, freezes B, and waits at one readable owner prompt.
No input, claim or sender start has been released.

Exact source: `root\IC_P18_043_DELETE_B.txt`, 51 bytes,
`Disposable P18-043 root TXT B: alignment case-01.` followed by CRLF, SHA-256
`5a5bdff8c2dd352322bc81445be4677534f5c75e5e4ba5f902bf5854c59bbf2e`.
Prepared root under application `Evidence/Library Transfer Operations/`:
`prepared-root-txt-dfcbf34d905241868284da0bdecb1f72`.
Fresh eight-object backup manifest
`9ae819e9d8570d3f576cc2d5c28b406e80101569ee85a59fd5dd0529bc0d2137`,
all raw objects equal original and verified A post-Delete; A/B absent.
Frozen seal `4b0585648fad995aa2359ff58782decf3e4cea2b2f5449c24ee596438e37ac1d`;
candidate `59481c11300b85e8ec3e4d314dd946b4d789f51a75a7605973802c07a6baeaaf`;
transaction `0c5c72946d121842406912dc91b21030af1571b58aa9996fddd69f786652a0ff`;
authorization `38087f67b74bfb84ab8e5bb1aebf832d4707686580ead59334176b52dcd27595`.
Expected sole addition: one 64-byte record, 32-byte native prefix + 51-byte
payload + one zero alignment byte; **148-byte total growth**. All existing
payloads/timestamps/content/gaps and eight protected associations preserved.

Independent actual frozen review **PASS**, no P0/P1/P2 findings:
`INDEPENDENT_B_PREPLACEMENT.md`, external session SHA-256
`a2e2f1c372ae7e644c74748f0a1eb526b65190ddcdfd169b2b2bde167060a0ed`.
Reviewer independently rehashes all 22 frozen artifacts, reconstructs candidate/
transaction/audit/authorization/capacity from actual fresh source/template/
timestamp, verifies raw survivor metadata/content and direct protected-state
rebases, and reads current safety without mutation. Current store twelve
historical consumed claims, zero B-seal claims, zero markers; global clear;
database `d2b618fd…` and lock bytes unchanged during inspection.

External `placement-B-frozen-review.json`, frozen evidence inventory, parent
preparation and safety reports retain exact operation identity and source.
B placement remains **unapproved / not run**. After explicit approval only,
release the sole readable answer to this waiting frozen operation; require
native integer zero, one sender/no retry and independently verified full actual
postbackup before any B Delete preparation. No personal target or class-gate
change, source edit, push or merge. A late A approval cannot replay its consumed
operation. The stale matrix sentence claiming Clock as the only completed
modern proof is corrected to include bounded A, without widening exposure.

## Owner-authorized Fixture B placement and Delete — COMPLETE

The owner separately approved the frozen B placement once, then after its
independent success separately authorized the frozen B Delete once. No other
physical operation followed. The exact target was
`root\\IC_P18_043_DELETE_B.txt`; its fixture-manifest payload is 51 bytes,
SHA-256 `5a5bdff8c2dd352322bc81445be4677534f5c75e5e4ba5f902bf5854c59bbf2e`.
Placement and Delete both used the existing guarded Manager path with their
own frozen identities, fresh complete backups, one readable confirmation,
single-use claims, sender markers and the installation-wide lock. Both
reported native **0x0000**, one audited sender/transaction, and zero retries.

The placement added only B and was independently verified against a complete
eight-object post-backup. Delete then used a newly prepared complete baseline
and independently verified frozen candidate. Actual before/after manifests
are `3e208f8df315898ceb3b8e6436fb71ffc49eeb14cee17f2ed7440ddb39e86ba3` and
`7c5ca7263b1430992ebc6e4b6c8a799705fae283bf858ff26435d4d5ccb1f3a6`; the
target was the sole removed path. The archive returned from 301 files / 455
records to 300 / 454, shrinking 148 bytes. All 300 survivor prefixes and
payloads, 454 timestamps, protected references and blocks, remaining content,
trailer, structure and checksum were independently verified. All eight
post-delete objects match the original `preparation-backup-01` bytes. The
claim is consumed, the marker resolved, and the global lock is clear. The
owner-supplied screenshot shows the refreshed exact B filter empty and the
Manager's verified-completion status; it is presentation evidence, not an
independent USB trace or a separately observed click.

Independent actual post-delete review: **PASS, P0/P1/P2=0/0/0**, report SHA-256
`f928c0cbe0e075ef9e40f0f2e9eb1461642099d3711ea97b84fc9b2222825f7c` at
`/external/local-path`;
machine verification SHA-256
`9b05d2f2ad5d90086168b1265f16d52686ab0e69231a01dee205b05c12d91448`.
The original B placement independent report SHA-256 is
`bd9df4a345b824dc89e25dfeb002f0382dcb5fa5447efe359ab4ebce624451fa`.
The report inspected actual complete backups and terminal state without
running USB, sender, GUI input, or safety-state mutations. No independent USB
bus trace was captured.

## Evidence comparison and capability disposition

P18-041 physically removed its exact 29-byte root TXT fixture;
P18-044/A removed the exact 32-byte disposable fixture; and P18-044/B removed
the exact 51-byte disposable fixture. All were VNW-V15 root-level records and
all completed with native zero, one sender and no retry, independently verified
complete readback, and preservation of unrelated content. Their payload-length
remainders modulo four are respectively **1, 0, and 3**. They therefore do not
exercise the remaining remainder-2 allocation case. The three targets also
share the observed record position (`0x680`) and native 32-byte prefix/state
profile; record positions outside this one have not been physically exercised.

The P18-043 host admission is broader than these physical samples: it accepts
additional safe root names, payload geometry and record positions under its
structural and protected-state validators. Offline corpus/synthetic coverage
and the exact P18-041/A/B results do not establish those combinations on the
device. A useful narrow gate limited to the exact three names would not deliver
ordinary file management, while promoting the existing general admission
would exceed the physical evidence. Therefore **ordinary root-TXT execution
remains disabled** at the UI/service/coordinator/claim boundaries; no source
gate was changed. The bounded named-fixture validation route is not general
admission and permits no personal target. The next smallest useful physical
evidence should cover a disposable payload with length remainder 2 and a
different record position; any such placement and deletion require their own
operation-specific owner approvals and the existing guarded workflow.

No new code was changed for this closeout. The reviewed source/tests at
`52c75c802212c3ca652305e1890cc3d187021100` remain the implementation baseline;
the existing full portable result (1,190 run, 1,187 passed, three established
skips) remains applicable. The independent actual B review completes the
evidence-review requirement for this bounded experiment. Root-BMP remains
host-only; BMP, nested/directory/subtree Delete, VNW-V10 compatibility, physical
atomicity and interrupted-write recovery are not demonstrated. Raw backups,
candidates and transaction evidence remain external and unmodified.
