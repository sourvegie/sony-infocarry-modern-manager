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
