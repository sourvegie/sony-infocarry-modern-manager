# P18-046 — exact disposable root-BMP Delete physical validation

## Result

On 2026-10-21, the owner-authorized modern guarded Delete removed exactly
`root\\IC_P18_046_DELETE_A.bmp` from the Sony InfoCarry VNW-V15. The target
was a 10,302-byte BMP with SHA-256
`2701eb9214e2f0afec20b36c93ef739ef3bce35e931fd8c5721e15915447b26d`, at
serialized record offset `0x680`, with unread state `0xe0`, selector `0x100`,
and a 16-byte `ff` prefix.

The native completion was `0x0000`. The persisted operation result records one
`0x101b` sender invocation and no automatic retry. A complete independent
eight-object post-delete backup passed; its dynamic archive SHA-256 is
`6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`, matching
the frozen candidate and the preserved pre-placement baseline byte-for-byte.
The independent verifier found exactly the requested path removed, no paths
added, 454 surviving records, unchanged survivor payloads and timestamps,
valid checksum/structure, and preserved protected/auxiliary state. The final
eight-object post-delete state matches the original pre-placement backup.

The durable claim for the frozen operation was consumed once. The terminal
resolution is `verified_terminal_success`; the sender marker is absent from
the store and the installation-wide lock is clear. No independent USB bus
trace was captured. No retry, restoration, or additional physical operation
occurred.

## Scope decision

This result establishes physical Delete only for the exact disposable VNW-V15
file and observed profile above. It supports the existing exact-fixture
Experimental Device Library profile, which continues to reject any other BMP
name, payload, record offset, read state, prefix profile, nested path, and
model. General BMP Delete, VNW-V10, and interrupted-write recovery remain
unsupported. The file is absent after validation; any future operation still
requires a fresh complete preflight and a separate owner confirmation.

The candidate is byte-identical to the original pre-placement archive, so the
experiment also returns the device to its pre-placement content state. The
physical procedure used the existing candidate builder, frozen operation
identity, durable claim, sender-marker/global-lock lifecycle, guarded one-shot
sender, and complete independent readback. No source-code changes were needed
after the exact-head R3 review.

## Preserved evidence

Raw device evidence remains outside Git in the existing application evidence
store under `Evidence/Library Transfer Operations/`. The operation evidence
folder is `p17-017-attempt-2a0f316a2da645748a51af54b146863d`; the prepared
frozen bundle remains under `prepared-root-bmp-delete-93f9615c2963480a99dc46c3c33d6e9b`.
The operation result manifest SHA-256 is
`30e9c7c4f9d3cf787a8b0a0f81af9ebbc9f9ae0646b398c0e880d3a268afb80f`; terminal
sender-marker resolution SHA-256 is
`4cc19801c7caa20963d7cdc4298b7875d74fbf781001e94355499c0014ff856e`; and the
independent root-BMP Delete report SHA-256 is
`9eb8eaff51a6600cec55c6584e0ef9ff3b8e05693182af3369158db734cd7f2f`.
The fresh pre-delete backup manifest SHA-256 is
`e0c935d6166754b410443563348777430c30b0710ab40871ff6c17c67e3bccfb`; the
complete post-delete backup manifest SHA-256 is
`fd1eb69cb729b993648ab093dc9bb8036d580a5164d891431b39c95ab681e806`.

The implementation remains the R3-reviewed code at
`2125278960c3754c7eeef34769b67e979f1f9f60` (P0/P1/P2 = 0/0/0). Its focused
BMP/Delete suites passed 60 tests and the full portable suite passed 1,222
with five established skips. This evidence closeout changes documentation
only. No push or merge was performed.
