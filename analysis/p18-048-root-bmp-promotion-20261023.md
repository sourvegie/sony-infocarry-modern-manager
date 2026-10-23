# P18-048 — Experimental root-BMP promotion and nested host inspection

## Decision and evidence

Starting checkpoint `ad6aea0ac244497b884e1512160af33fa7679233`. The owner
explicitly approved a justified conservative capability expansion, with no new
physical write. The independent [evidence assessment](p18-048-independent-evidence-assessment-20261023.md)
rehashed actual P18-046/P18-047 backups/audits, reconstructed exact BMP deletion
candidates/transactions and independently verified complete actual post-states.
P18-047 B deletion preserves the A32 anchor and all eight objects equal actual
A32 placement state; final cleanup returns all eight original baseline objects.
Both disposables remain absent. No bus trace was captured or inferred.

P18-046 bottom-up A at `0x680` and P18-047 top-down/inverted B at `0x6c0` each
returned native zero, one audited sender/transaction and no retries. They
validate the same unread record/prefix/allocation and protected-state model
with different payload/orientation/slot and survivor rebasing. The reviewer
also reran 33 archived supported BMP payload records (22 unique payloads) in
three synthetic root positions: 99 candidates passed. The other 130 archived
BMPs have unsupported dimensions. Synthetic placement is not physical proof.
No additional physical experiment is essential for the following envelope.

## Exact enabled envelope

The authoritative scope is the ordinary unread root-BMP row in
[CAPABILITY_MATRIX.md](../CAPABILITY_MATRIX.md): VNW-V15, exactly one direct root
file with exact lowercase `.bmp`, safe unique NUL-terminated CP932 name of 1–39
stem bytes, unread `0xe0`, field `0x10 = 0xffffffff`, selector `0x100`, 16 all-FF
prefix bytes, existing canonical 10,302-byte uncompressed 1-bit 237×±320 Windows
BMP validator. Both supported orientations are admitted. The target must be
unreferenced, with supported protected state, inactive Marks, valid checksum,
unique parent/child tables and aligned/nonoverlapping content. Deletion removes
one 64-byte record and the 10,320-byte aligned allocation, preserving every
survivor's payload/prefix/timestamp and supported auxiliary association.

Other safe names, pixel patterns and structurally valid metadata slots are an
engineering inference from established invariants. Only offsets `0x680` and
`0x6c0` have modern BMP physical proof. No exact filename, payload hash or A32
anchor is required for ordinary admission. The retained explicit B validation
route still requires its original exact target/slot/anchor and cannot weaken
the ordinary gate. Read state, 32-prefix/unknown profiles, unsupported BMP
formats, referenced/ambiguous targets, active Marks, nested files, directories,
subtrees, multiple selection, VNW-V10 and interrupted-write recovery are excluded.

## Implementation

The existing Device Library service admits supported BMP selections and
reconstructs them from their verified source. The existing frozen bundle binds
ordinary BMP scope under `vnw-v15-unread-root-bmp-delete-v1`, exact selected
path/offset/payload, complete baseline, candidate, transaction, source artifact,
capacity and owner identity. Scope flags are sealed and cannot convert an
approved fixture or TXT operation into another operation. Exact validation
profiles remain separately reconstructed. The UI retains one readable
Delete/Cancel dialog, progress, safe pre-sender cancellation and refresh from
verified post-backup. Help now describes the supported unread TXT/BMP scope.

No low-level sender, persistent schema, claim store, lock, transport or success
verification algorithm changed. Every live attempt still requires a fresh
complete eight-object backup and separate native capacity, reconnect-safe state
comparison, explicit transaction-specific confirmation, one durable claim and
sender marker, installation-wide lock checks, exactly one sender/no automatic
retry, native integer zero, complete independent readback and terminal marker
resolution. Native nonzero retains the existing determinate-failure policy;
ambiguous send/readback failures retain the marker/global lock. A host candidate
or generalized BMP host authorization alone still cannot bind a sender.

## Nested host-only continuation

The existing preparation script adds `inspect-nested --backup ... --target ...
--record-offset 0x...`, returning one nested TXT/BMP candidate audit/hash without
creating a transaction, authorization, claim or runtime. New sequential host
removal tests independently verify each resulting complete backup and preserve
all parents, siblings, markers and protected state. No nested UI or sender gate
is enabled. No directory/subtree model is added.

## Validation and integration

The corrected portable run completed **1,256 tests: 1,251 passed, five existing
intentional skips**, 227.414 seconds. Focused promotion/expansion/nested/UI
regressions passed 72 tests; the independent reviewer reran those 72 tests and
all passed. The TXT/disposable regression passed 37 tests. Initial failures
exposed an overbroad new early preparation check that affected read-TXT host
preparation; the check was narrowed to BMP and original TXT behavior/messages
restored. Obsolete ordinary-BMP UI refusal assertions were updated to the
promoted scope. No new skip was introduced or failed attempt counted as passing.

A nonblocking review comment identified historical missing-proof labels in the
standalone offline preparation report. They now record completed fixture
validation and still require a fresh guarded operation/owner confirmation.
The report/expansion regression passed 24 tests after that metadata-only change.
It grants no execution authority. Final exact-head R3 disposition follows in
its independent report; no material safety finding was identified in the
critical implementation review.

The macOS package build, plist and strict/deep ad-hoc signature checks pass.
The existing frozen runtime smoke passed outside the sandbox with its isolated
profile: actual Tk startup/close, resources/libusb, Add/menu and unavailable/
locked-runtime behavior. All real USB enumeration/sender/claims/marker counters
were zero. Native visual inspection of a synthetic ordinary BMP confirmed the
single readable Delete/Cancel dialog (Cancel initially focused), exact filename/
model, no hash entry, consistent layout and cancellation retaining the row with
zero fake sends. Actual native widget checks confirmed button and menu enabled
for the supported selection and disabled with no selection/after the fake send.
The actual ttk callback tests independently cover success, errors, progress,
cancellation and verified readback/refresh. Post-result screenshot attempts
failed when the test window became unavailable to macOS capture; they are not
claimed as a visual success-footer check. Initial GUI test-driver errors and
failed captures are preserved outside Git and are not passing evidence. No
security setting changed or GUI automation infrastructure was installed.

All raw hardware evidence, synthetic GUI artifacts and test/package logs remain
outside Git. This record contains sanitized conclusions and hashes only. The
isolated repository retains published sanitized `d344f1e` as an ancestor and
passes complete Git integrity/diff checks. P18-034's branch, raw NUL-delimited
status digest and all 1,043 preserved file hashes were rechecked unchanged.
Read-only production safety inspection still finds the same 24 historical
claims, no sender marker and the byte-identical cleared global lock. No
physical operation, push or merge is performed.

Integration remains a separate owner action. The isolated task branch descends
normally from published sanitized `d344f1e`, preserves P18-046/047 source and
evidence documentation, and can be integrated by normal fast-forward if the
actual target branch is still an ancestor. Re-fetch/recheck that target before
any authorized update; do not force or import broken/private original ancestry.
No canonical checkout, private raw artifact or unfinished historical branch is
included in this task's outgoing change set. The next useful step is owner-
approved integration of the reviewed branch; nested physical validation remains
separately scoped and unauthorized.
