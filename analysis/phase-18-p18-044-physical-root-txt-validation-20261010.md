# P18-044 — physical root-TXT Delete validation — 2026-10-10

Base `e1cfda6efc6cb8cfebcfe484fcb1e3bb69d54be3`; branch
`task/P18-044-root-txt-physical-validation`. R3 host preparation precedes every
new physical placement. The existing P18-043 A/B procedure and exact manifest
remain authoritative. No physical write approval has yet been received.

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
Independent exact-head review is pending. No tests or physical result are
claimed solely from a interrupted reviewer or an inferred runtime result.

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
