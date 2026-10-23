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

Validation results and exact-head review are pending final completion. All raw
hardware evidence, synthetic GUI artifacts and test/package logs remain outside
Git. This record contains sanitized conclusions and hashes only. The isolated
repository retains the published sanitized ancestry; P18-034 and its dirty
files remain untouched. No physical write, push or merge is performed.
