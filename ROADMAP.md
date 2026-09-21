# Roadmap

This is the forward-looking delivery plan. Detailed milestone history remains
in `analysis/` and in the archived roadmap through P18-001A.

The post-P18-036 product direction is a simple Manager for the Local Library
and the connected InfoCarry Device Library. Current operation status remains
in [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md). This sequence sets product
priority; it does not authorize a device operation or expand a capability.

## Near-term sequence

1. **Focused UI/UX review.** Review the current Manager around the Local
   Library ↔ Device Library mental model. Walk through adding files and folders,
   selecting content, transfer, verified completion, and immediate device-tree
   refresh. Review the corresponding selected deletion and refresh flow, backup
   access, capacity visibility, and understandable failure states. Keep
   technical evidence available without making it the ordinary workflow. Use
   the review to focus subsequent changes.

2. **General library model and direct TXT/BMP transfer.** Build the reusable
   library and operation model around folders and typed TXT/BMP items. Make
   direct transfer of supported TXT and BMP content the first practical
   everyday path. Validate bounded structural rules across representative
   collections and edge cases instead of defining general validity as a set of
   exact leaf-order permutations. Keep each device operation behind its
   existing evidence, capability, authorization, backup, and verification
   gates.

3. **Realistic nested hierarchy.** Support browsing and selecting content in
   nested folders, and carry the structure through preparation and transfer
   review. Validate at a realistic scale of roughly 30–50 folders and many
   TXT/BMP items. Treat those figures as a planning and test target, not as a
   hard product limit. Document any limit only when an evidenced device,
   format, protocol, or resource constraint requires it.

4. **Guarded deletion.** Deliver selected file and folder deletion as a core
   Manager workflow. Require an operation-specific reviewed scope, fresh
   device state, the existing verified-backup and explicit-confirmation
   controls, bounded execution, and independent verification of the removal
   and unaffected content. Refresh the Device Library immediately after
   verified completion. Do not infer deletion from transfer or synchronization.

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
