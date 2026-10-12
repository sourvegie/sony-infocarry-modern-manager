# P18-045 — minimum additional root-TXT validation

Starting checkpoint `6acb3af32ec03153405c75ec1afbb7bf4c43384c`, branch
`task/P18-045-root-txt-delete-validation`. **Preparation only; no physical
placement or Delete is authorized by this document.** The owner requires a
separate approval for each frozen operation. Normal general-TXT execution
remains disabled pending actual results and independent review.

## Evidence and minimum experiment

P18-041/044 A/B demonstrated exact 29/32/51-byte root TXT deletion on VNW-V15:
native zero, one audited sender/transaction, no retry, complete independent
readback, unchanged survivors/timestamps/protected state. Their serialized
targets were at `0x680`; payload remainders modulo four were 1, 0 and 3. The
remaining useful dimensions are remainder 2 and a different serialized target
with survivors on both sides of the removal boundary. Three demonstrations
are not proof of every filename/offset/state; equally, uniform validated offset
arithmetic does not require a physical test of every numerical position.

The existing evidence-backed placement builder inserts immediately before the
root closing marker. One added file always occupies the current marker slot
(`0x680` in the preserved baseline). Relocating it or editing personal records
would require a new unproven mechanism. The smallest setup using the current
one-file placement path therefore uses two disposable files:

1. Place the exact previously demonstrated 32-byte A as an anchor at `0x680`.
2. Place new 34-byte C at the next serialized slot, `0x6c0`.
3. Delete C first, leaving A before it; independently verify all later record,
   payload and protected-reference rebases. This is the sole new scientific
   Delete case: remainder 2 and a different record position together.
4. After independent C success and separate approval, delete A as cleanup.

Two placements and two Deletes, each separately approved, are required to
restore the original state without leaving disposable content. C must not be
deleted at `0x680` and counted as new-position proof. The fixture manifest is
[p18-045-disposable-root-txt-fixtures-20261011.json](p18-045-disposable-root-txt-fixtures-20261011.json).
C is `root\IC_P18_045_DELETE_C.txt`, exact text
`Disposable P18-045 root TXT C++.` followed by CRLF: 34 bytes, SHA-256
`dc318d18b0410bfbabfa2ad8619cece0dd7ef4166bc10e2fd1213f06d0bcca3c`.
It has 32 native prefix bytes, 34 payload bytes and two alignment bytes; total
archive growth/removal is 132 bytes including its 64-byte metadata record.
A retains its original manifest identity and 128-byte archive growth/removal.

The reviewer additionally inspected the preserved
[H.2 physical Delete](phase-13-milestone-h2-modern-delete-smoke-20260827.md):
41-byte `IC_TEST_01` at `0x1c0`, with four surviving direct-root TXT siblings
at `0x200`, `0x240`, `0x280`, `0x2c0` shifting to `0x1c0`, `0x200`, `0x240`,
`0x280`. That native-zero, complete-readback proof used the earlier all-zero
fixed-state boundary and older safety implementation. It supports the uniform
root-sibling ordering/rebase invariant, not current protected-state safety or
automatic class promotion. C's current-state validation is still needed for
the missing alignment case and current preserved associations at a different
offset. A third disposable solely to provide a root sibling after C would
therefore duplicate existing ordering evidence; the two-file setup is enough.

## Actual baseline and host verification

External session:
`/external/local-path`.
The existing read-only backup and native hardware-info commands were run with
command-specific out-of-sandbox access. Complete eight-object backup manifest
SHA-256 `ef0941f98985364513c279c04013d497a0ec4429de1e3a46c3fcdc3005812df6`;
all eight objects equal the independently verified B post-delete/original
preparation state. Dynamic blob SHA-256
`6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`:
300 files / 454 serialized records; A/B/C absent. The existing `0x0019` response
is `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a`,
native capacity 3,145,728 bytes from established field +0x08.
Read-only immutable SQLite verification: fourteen consumed historical claims,
zero sender markers, retained global lock cleared; all inspected safety bytes
remain unchanged. No claim, marker or lock was reset or consumed.

`host-sequence-check.py` constructs offline candidates through the existing
new-TXT builder, then reconstructs both Delete candidates through the existing
generic root-TXT model and complete independent readback verifier. Host-only
derived archives are explicitly labeled and cannot be adopted as physical
preflight baselines. Actual serialized A/C offsets are `0x680` / `0x6c0`;
both have flag `0xe0` and field14 `0x200`. Before C deletion there are 26
records before the target and 429 after; five files before and 296 after.
A's record/prefix/payload is preserved at the same offset; later file and
directory records move by exactly 64 bytes, later content by 68 bytes, and
protected references preserve their associations. C's Delete candidate equals
the A-only model; A cleanup equals the original dynamic image and all five
protected blocks. Inputs are rehashed unchanged. This is offline model proof,
not a physical observation. Report: `host-sequence-verification.json`.

## Implementation and review boundary

Only the immutable exact-fixture map is extended with C. Existing validation
selection, target/payload binding, candidate reconstruction, frozen operation,
reconnect equivalence, claim/marker/global lock, one-shot sender and complete
independent readback are reused. C's placement report names P18-045; A/B report
labels and bytes stay compatible. The prior A/B manifest is unaltered. No
generic execution gate, sender, transport, persistence format or safety owner
is changed. New tests verify the paired synthetic serialized-position inverse,
the exact manifest, and the disabled ordinary C path; existing exact-fixture
loop tests exercise C placement/authorization/one-shot behavior as well.

Independent exact-head R3 and the completed portable suite are required before
any first placement approval. Record their final results here; source changes
after review invalidate the review boundary.

Host validation completed: 19 focused root-TXT admission tests pass (2.468s),
full portable suite **1,192 run / 1,189 passed / three established evidence
skips** (123.416s). Full log is `full-portable-suite.log` in the external
session. `git diff --check` passes. No hung/interrupted test is counted as
passed. Independent exact-head R3 at
`1461f9294027158a48ae2e023922b6a38f1f9514` is **PASS, P0/P1/P2=0/0/0**, with
no correction round. Reviewer independently ran 108 focused tests (all pass),
checked the completed full-suite log and reconstructed all four model steps
against 40 independently rehashed archive objects. The minimum A/C design is
accepted as READY_FOR_HARDWARE_TEST; normal general execution is not promoted.
External report `INDEPENDENT_HOST_R3.md`, SHA-256
`6182767632206bf5ead1c07f4b0f083284fe62c0e6c724a01e28b082f3eebc63`;
machine verification `independent-host-sequence-verification.json`, SHA-256
`25327fc0d5c3becd39930c4fa0d0e759205047aef8de05ddef7fc96872e8dd3e`.
No first placement is approved. Subsequent changes are documentation only.

## Actual first anchor-A operation — frozen and independently reviewed

The existing launcher obtains its own new complete baseline/native capacity
and stops at its sole readable confirmation, without any answer or sender
start. Actual prepared root is application `Evidence/Library Transfer Operations/`
`prepared-root-txt-c94e93c5f84f4c658d964c49fd1f1937`.
External `anchor-A-frozen-review.json` and `anchor-A-preapproval-inventory.json`
preserve its original identity and all 22 immutable artifacts. Complete fresh
backup manifest `7a00d8585c91ab91fc75e203d3d827968ceb48f6e286a721a5d3c755bf9cee46`;
all eight raw objects equal the verified original state. Only A is added at
`0x680`: exact 32-byte original fixture, 128-byte archive growth, survivor
prefixes/payloads/timestamps and protected associations preserved.

Frozen seal `74de2a324725c7dcdefeb24ee082f524f463a0931e1d319cfb22fb82506da632`;
candidate `bc4966a9f6d6f87faa9a8c08771cdb5a58a978c35fd62d9954e59b32a56467d0`;
transaction `1440e8a18c4dfdc751d49a2defaf3e32f62ae68c3d9174da1fac9d17daaccaf5`;
authorization `32ce87b4fd9b228a1202892351090a384ca2f8d87fcd8399c613f2e1b4a4ca1d`.
Reconstruction is comparison only, not regenerated/adopted execution evidence.
The actual waiting launcher retains this exact operation.

Independent frozen preplacement review **PASS, P0/P1/P2=0/0/0**:
`INDEPENDENT_ANCHOR_A_PREPLACEMENT.md`, SHA-256
`ee1cc227a43117f46ec82bf1a9b4fa93a6e27e975fb0a85732a0de79c6c4853f`;
machine verification `independent-anchor-A-preplacement-verification.json`,
SHA-256 `9c105a1113b79e44b99d6eca03c3247b69c93f8aec1913d91f274e9b82137083`.
Read-only safety remains fourteen consumed historical claims, no claim for
this seal, zero sender markers, global lock clear; inspected bytes unchanged.
The first owner decision is **A placement once only**. C placement, C Delete
and A cleanup each require later separate preparation/approval; none follows
automatically. A failed/ambiguous result stops the entire physical plan.

## Hardware procedure and capability decision

For each placement use the existing placement launcher with the manifest
source, target and a new external frozen-review output. Preparation obtains
fresh native capacity and a complete backup. Independently verify the source,
candidate, serialization geometry and preservation invariants before showing
one readable owner summary. Execution receives only that operation's separate
approval; no rebuild/adoption after approval, one send, explicit integer
`0x0000`, no retry and complete independent post-backup are mandatory.

After A placement succeeds independently, prepare C against a new actual
backup. Require A's exact manifest bytes at `0x680` and C's prospective record
at `0x6c0` before seeking C placement approval. After C placement succeeds,
use the existing Manager validation launcher for its exact target; Back Up,
select C, Delete, review one dialog. Independently inspect the frozen actual
candidate and exact serialized positions, then obtain C Delete approval.
After verified C removal, obtain a new backup and a separate A cleanup approval
through its existing Device Library path. Any failure/ambiguity stops all
physical work, preserves evidence and locks according to the existing policy;
never retry automatically or restore. No personal content is a test target.

The capability decision follows actual C/cleanup results and exact-head review,
not this preparation. A defensible initial live envelope may retain only the
observed VNW-V15 native profile (32-byte prefix, `0xe0` unread flag), exact
unique CP932-safe root TXT identity, unreferenced target, supported fixed state
and nonoverlapping aligned allocation. The host validator already enforces
these structural invariants and independently proves all survivors. Names are
identity data and payload bytes are copied/preserved or removed as opaque
content; they do not select a different offset-rebase algorithm. Numerical
positions use the same checked before/after arithmetic. A different parent
shape, prefix or state rule needs specific justification; host-only `0x20`
read-state preparation need not be promoted automatically. BMP, nested files,
directories/subtrees, referenced files, ambiguous identities, VNW-V10 and
recovery remain outside this task's live scope. No general gate is enabled
until the actual evidence and required review support it.

## October 12 — exact owner-authorized A placement COMPLETE

The owner explicitly authorized the original frozen A placement once, target
`root\IC_P18_043_DELETE_A.txt` at `0x680`, native zero and complete independent
verification; C and all Deletes remain separately unauthorized. The receipt
`anchor-A-owner-approval-20261012.json` is preserved external, SHA-256
`c50413d34049bc1fcf0bd1c3dc68107009d0b011d356db273ccf130ca64a19e7`.

The original waiting terminal no longer existed, and command-specific process
inspection confirmed no matching launcher. All 22 frozen artifacts remained
unchanged; immutable read-only SQLite found no claim for this seal, no marker,
and global lock clear. A new read-only backup independently matched all eight
approved baseline objects. No write had started; this was not interrupted-write
recovery or a retry. Existing `RootTxtPlacementBundle` constructors and
`RootTxtPlacementFacade.adopt_prepared_operation` load the original candidate,
transaction, source, baseline, capacity and seal using a new canonical pinned
runtime. Old timestamp/template reconstruction is comparison only and must
match original audit/authorization hashes; candidate execution bytes and
approved identity are unchanged. No `prepare`, current timestamp, replacement
transaction or persistence reset is used.

The exact bounded external runner received independent R3 **PASS,
P0/P1/P2=0/0/0**, thirteen independently run fake tests all passed (seven supplied
plus six extra adversarial checks). Runner SHA-256
`d583d5076713b1157b120d6ea0e7d0a00e85f1c78f06b0462a8e3769e4ff91e9`;
review `INDEPENDENT_FROZEN_A_RUNNER_R3.md`, SHA-256
`6df7c220854600b664e8d0663d820821168aee8a45b11a0479147188ef39d103`.
An initial fake-test setup failed because its isolated evidence directory had
not been created; the corrected fixture passed, no runner/source change, and
the failed log remains preserved/not counted as passing. The existing safety
framework, transport, sender and production source remain unchanged.

After rehashing the reviewed runner and original frozen artifacts, one human
answer derived solely from the owner's above authorization was released once
to its readable prompt. The canonical coordinator obtained a new complete
execution-time backup and native capacity and proved exact state equivalence
before claim/marker/sender. Native **0x0000**, launcher exit **0**, one audited
sender/transaction, no automatic retry, complete independently verified
post-backup. Original seal `74de2a32…`, candidate `bc4966a9…`, transaction
`1440e8a1…`, authorization `32ce87b4…` recorded above are unchanged.

Actual attempt under application `Evidence/Library Transfer Operations/`:
`p17-017-attempt-3a8135f966e540419e172856c7cfbfa9`. Actual fresh before manifest
`e823c2e251cc3b3a8b822d80b7652c31da929088710906e2be40031b34b29ada`;
after `332dbf4ce5af005ac60f136a3223a87e56242323d33aec2a1eaa278bbb1c3a58`.
The actual post dynamic blob equals the original frozen candidate. Sole
addition is exact A32 at `0x680`, `0xe0`, native prefix32; +128 bytes,
300→301 files / 454→455 records. All 300 prior prefixes/payloads and 454
timestamps, raw surviving metadata outside checked pointer/table adjustments,
entire original content/gaps/trailer, valid graph/checksum and eight history/
bookmark associations across five protected blocks are independently verified.

Independent actual post-placement **PASS, P0/P1/P2=0/0/0**:
`INDEPENDENT_ANCHOR_A_POSTPLACEMENT.md`, SHA-256
`9db7fe05a2952f701ead25ec8609640c27aea94b4b04b6a256b57eae2862afe6`;
machine verification SHA-256
`13579621f9c99ec401ebd542a518d993c6eecd61c0cda6eeac940f28d24e4e86`.
Actual result manifest SHA-256
`8e654fe1c09117a5ec70cba4b73a67361669005f095f840c2218014b1632d196`
is bound by terminal resolution. Exact claim consumed, fifteen historical
claims, zero current sender markers, global lock clear. The embedded in-flight
audit snapshot remains unchanged; separate terminal proof establishes normal
resolution. No manual clearing or retry. The canonical placement report retains
the reviewed P18-044 fixture-origin label for A; current attempt/date and exact
owner identity identify this P18-045 placement. No independent USB trace exists.
No C placement, Delete or cleanup follows this approval automatically.

## Fresh frozen C placement — awaits separate owner authorization

Only after actual A passed independent post-verification, the unchanged exact
placement launcher prepared C and stopped at its single readable confirmation.
Prepared root under application `Evidence/Library Transfer Operations/`:
`prepared-root-txt-a365e0b902044fe7a20c29004851045c`.
The new complete eight-object baseline equals actual A post-state, manifest
`ac6d17166e7a725a4afc07e813077de6400c8f001ceea5ef650b7c06cf0d78c8`.
External `C-frozen-review-20261012.json` and
`C-preapproval-inventory-20261012.json` preserve all 22 frozen files.

Exact C source is 34 bytes / SHA-256
`dc318d18b0410bfbabfa2ad8619cece0dd7ef4166bc10e2fd1213f06d0bcca3c`.
Prospective serialized record `0x6c0`, flag `0xe0`, native prefix32, payload34,
two zero alignment bytes. Sole addition, 132-byte archive growth;
301→302 files / 455→456 records. A remains at `0x680`, its raw metadata,
prefix/payload unchanged. All prior 301 prefixes/payloads, 455 timestamps,
full content/gaps/trailer, pointer/table geometry and checksum are preserved
outside the intended insertion/rebases. All eight protected associations across
five blocks retain their same surviving targets.

Frozen seal `4c937a68c220f49a22dd1a752c2cc0dac3c36093527767c9037724e53dcf59de`;
candidate `b9e4138ce1ebfbf5dd396f69b7399f48cd0d0ed02a43211952c53570e6221558`;
transaction `96116b385a01dddb69c0e9abae538930be5b424677453c9a3e9a5c4fb63305b6`;
authorization `aa8ece29049c2ebe6bd183610bda3489b1261d6ebe0da8da81678c5f77b6b4f2`.
Independent exact frozen verification **PASS, P0/P1/P2=0/0/0**:
`INDEPENDENT_C_PREPLACEMENT.md`, SHA-256
`5f98ee3cc6951fb0710f4d04afd2f80bb2cb1823a280ff30a47dd1a903331887`;
machine verification SHA-256
`be2a9fc05f492b850dea47803005cdafd45c7c1fad2c36cc0739c33e25fee110`.
The reviewer separately builds a temporary host-only C Delete inverse; dynamic
blob and all five fixed blocks return exactly to actual A post-state. This
temporary model is not adopted, sealed or treated as physical evidence.

Current read-only safety: fifteen consumed historical claims, no claim for
this C seal, zero sender markers, global lock clear; inspected evidence and
safety bytes unchanged. No C approval, claim, sender or transaction exists.
The first subsequent decision is **C placement once only** using this exact
frozen operation; C Delete and A cleanup still require separate later approvals.
General TXT gate remains disabled. Production source/scripts/tests are
unchanged from R3-reviewed `1461f92`; this checkpoint is documentation only.
