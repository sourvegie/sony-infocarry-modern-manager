# Roadmap

This is the forward-looking delivery plan. Detailed milestone history remains
in `analysis/` and in the archived roadmap through P18-001A.

The post-P18-036 product direction is a simple Manager for the Local Library
and the connected InfoCarry Device Library. Current operation status remains
in [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md). This sequence sets product
priority; it does not authorize a device operation or expand a capability.

## Near-term sequence

1. **P18-038 — Responsive operation UX + simple confirmation.** Keep the
   Manager responsive throughout backup, preflight, transfer, post-write
   backup, and verification. Show plain-language progress while the existing
   guarded operation runs outside Tk's main thread. Replace the ordinary
   transfer typed-key ritual with a clear OK/Cancel confirmation that summarizes
   the exact target and scope; internally retain the same operation-specific
   binding, durable claim, sender marker, no-retry rule, lock, and independent
   verification. The confirmation dialog is the cancellation boundary for a
   device-changing transfer; once guarded execution begins, keep the UI
   responsive but do not offer a mid-write cancel or allow the window to close.

2. **P18-039 — Generalized flat TXT/BMP transfer (host implementation in
   independent-review readiness).** Promote a bounded
   structural rule for one root-level folder containing an ordered collection
   of supported TXT/BMP leaves, rather than enumerating exact three-/four-leaf
   permutations. Validate names, ordering, source freshness, formats, conflicts,
   capacity, candidate construction, and preservation invariants. Use
   representative boundary cases and separate physical promotion evidence. The
   implementation uses the existing safety lifecycle for host preflight and
   authorization seams, but the structural host model does not itself authorize
   live execution or permit a physical operation in this milestone.

3. **P18-040 — Nested library transfer.** Carry ordinary nested Local Library
   hierarchy through preparation, planning, guarded transfer, verification, and
   Device Library refresh. Validate realistic collections of roughly 30–50
   folders and 100+ mixed TXT/BMP leaves as a planning/test target, not a hard
   device limit. Preserve selected hierarchy and ordering without introducing
   synchronization or unmatched-content deletion.

4. **P18-041 — Guarded Device Library deletion.** Deliver selected file and
   folder deletion as a normal Device Library action. Require a fresh complete
   backup, explicit Delete/Cancel confirmation, bounded one-shot execution,
   no automatic retry after an ambiguous start, complete post-operation
   read-back, unaffected-content preservation checks, and immediate Device
   Library refresh. Deletion remains a separate capability from transfer.

5. **InfoCarry Toolkit integration.** Integrate the important Toolkit snapshot
   `97042a9` after the core Manager workflow is useful. Bring supported
   conversion into Local Library preparation and review instead of investing
   first in heavy polish of the separate Text Converter and Ebook Renderer
   experiences. Treat conversion and Toolkit evidence as preparation inputs;
   integration does not enable new device operations.

## Permanent safety and model boundaries

Preserve the existing write-safety invariants throughout this roadmap:

- the capability matrix remains the authority for current device operations;
- model-specific rules remain explicit: VNW-V15 is verified, and VNW-V10
  remains uncharacterized and does not inherit V15 capabilities;
- every device change uses a fresh target and readiness review, including
  current conflicts and capacity evidence;
- create and verify the required full backup before a write;
- require operation-specific authorization and explicit confirmation;
- retain bounded execution, single-use durable claims, proof-bound
  sender-marker resolution, and the installation-wide indeterminate-write
  lock;
- keep write operations labeled Experimental while commit atomicity and
  interrupted-write recovery remain unproven;
- never automatically retry an indeterminate operation after device-changing
  execution starts; use read-only diagnosis;
- report verified success only after the exact native integer result `0x0000`,
  a complete post-write backup, independent read-back, a durable terminal
  result, and sender-marker resolution; and
- explain when the physical protocol changes a complete candidate library
  image even though the user's logical selection is smaller.

A broader structural model is not a capability promotion. Each device operation
still requires the evidence and reviews applicable to its model and scope.
Restore, synchronization, unmatched-content deletion, firmware/service modes,
and interrupted-write recovery remain separately gated work. Do not test
interrupted-write recovery on the owner's only valuable device.

## Later work

After the near-term sequence, prioritize only product work that advances
everyday file management while preserving the safety boundary. Keep broad
format expansion, Windows compatibility claims, storage migrations, and
additional destructive operations behind their own evidence and review.
