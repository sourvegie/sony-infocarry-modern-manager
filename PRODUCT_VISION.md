# Sony InfoCarry Modern Manager — Product Vision

## Vision

Create a safe, user-friendly modern replacement for the essential functions of
Sony InfoCarry Manager. A non-technical user should be able to connect an
InfoCarry, see its contents, download files to the computer, and upload
supported files without using Windows 2000 or understanding the USB protocol.

The product is a modern equivalent of the useful Manager workflow, not a
pixel-for-pixel port. Legacy operations that can erase or replace an entire
side are redesigned around backup, preview, confirmation, and verification.

## Product Principles

1. Protect the user's device and data before adding convenience.
2. Make read-only recovery useful before exposing any write operation.
3. Default to selected-file operations; do not expose destructive bulk
   replacement as a shortcut.
4. Make every device-changing operation previewable, explicitly authorized,
   and independently verified by reading the device back.
5. Preserve original backups and unknown legacy bytes losslessly.
6. Keep the protocol/conversion core portable even though macOS is the first
   supported platform.
7. Describe device-changing operations as experimental while commit atomicity
   and interrupted-write recovery remain unproven. Never turn an uncertain
   outcome into an automatic retry.
8. Distinguish logical selection from physical transfer scope: a selected item
   is the only intended content change, but the device protocol rewrites a
   complete candidate library image. Explain that timing is not proportional
   to the selected file size.

## Release Scope

### v0.1 — Read-only recovery manager

A user can:

- see whether a supported InfoCarry is connected;
- create a complete, verified backup;
- browse the device contents in a familiar folder view;
- download/export selected files or folders;
- understand errors and safely retry a failed read.

No device content can be changed in this release.

### v0.2 — Guarded selected upload

A user can additionally:

- select an existing supported text file on the device;
- choose replacement text from the computer;
- preview conversion, unsupported characters, size, and target path;
- receive an automatic fresh backup before transfer;
- explicitly confirm the selected change;
- see transfer progress and a read-back verification result.

The first upload scope is deliberately limited to the proven existing-record
text replacement path. General new-file creation is not implied.

### v0.3 — Guarded new TXT creation

A user can additionally:

- choose a new UTF-8 TXT source on the computer;
- preview the exact CP932/CRLF output, new device path, ordering/category
  effects, size, capacity result, and any unsupported characters;
- receive an automatic fresh verified backup;
- explicitly authorize creation of one new TXT record;
- see bounded progress with no automatic retry; and
- receive a complete read-back result proving the new item and all expected
  metadata while detecting unrelated changes.

This release begins only after a genuinely new legacy-created TXT fixture and
its metadata/sidecar effects are understood. It does not imply folders,
multi-file books, images, batch transfer, or delete.

The operation remains explicitly experimental for the limited hobbyist
audience until interrupted-write recovery is understood. A user may cancel
normally before transmission begins; after the device-changing request begins,
a disconnect, timeout, or cancellation is reported as an indeterminate outcome
requiring read-only diagnosis, never as a guaranteed rollback.

### v0.4 — Selective remove and prepared-content transfer

A user can additionally:

- remove one selected disposable or no-longer-needed supported item through a
  separately captured and tested delete path;
- review one explicitly prepared package with a proven exact folder and child
  shape;
- transfer one prepared supported item after capacity/conflict review; and
- verify every created or removed record and all affected sidecars.

Delete and multi-file creation have separate evidence and live-test gates.
Neither is inferred from successful single-TXT creation.

### v0.5 — Local Library and safe staged transfer

A user can additionally:

- import supported sources into a persistent local Library by picker or
  drag-and-drop;
- prepare and preview them using tested conversion profiles;
- select one explicitly grouped prepared package for a transfer-readiness
  review;
- review destinations, conflicts, prepared sizes, device capacity evidence,
  additions, and any explicitly requested removals before a future
  authorization boundary; and
- execute only operation types already proven by the earlier release gates.

The accelerated delivery plan keeps selection and physical transfer distinct:
one selected Library item is one logical package, while the device protocol
may transfer a complete candidate library image. It never means synchronize,
delete unmatched device content, restore a side, or reproduce the legacy
send-all operation. Unsupported, stale, conflicting, nested, multi-package,
or differently shaped items remain preview-only and cannot be sent.

For both single-item and future queued operations, selection describes a
logical Library item; it never means merge or synchronization. The
authoritative current capability boundary is
[`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md). It records that constrained
root TXT deletion, ordered four-TXT, flat TXT/BMP/TXT, and the exact P17-018
Library package have their own limited evidence gates. P18-001 adds an
Experimental review and guarded integration for exactly the P17-018-proven
Library shape: one root folder with ordered TXT, BMP, TXT children. P18-016
exposes that profile's host-only readiness review in the normal ttk Library
flow; P18-017 adds a product facade for fresh live preflight and the existing
guarded execution lifecycle. The default normal UI remains disabled until an
exact, separately authorized fresh VNW-V15 operation has passed the canonical
gates and transaction-specific confirmation. The code-reachable boundary is
still only one explicit root package at `IC_P18_LIBRARY_20260910_01` with
TXT → BMP → TXT children, target absence, no overwrite/delete/merge/nesting/
batch, one transaction, and no retry. This host integration is not physical
ttk validation and does not authorize a hardware transaction. A selected item
is the logical change, while the protocol operation transfers a complete
candidate library image.

### v1.0 — General content manager

Subject to format evidence and safety tests, a user can:

- upload and download all supported text, memo, and image content;
- create supported new files and folders;
- rename or delete selected items;
- perform safe batch operations;
- restore from a verified backup using a separately tested recovery workflow.

## Legacy Manager Parity

The initial product covers the old Manager's core purpose: connection status,
receive/backup, browsing, selected download, and selected send. Its destructive
"send all" and "receive all" behavior is not copied into early releases.

The current parity priority is protocol and package generalization. I.6 has
completed one narrowly constrained live one-folder/one-TXT package smoke with
completion `0x0000` and exact independent read-back. Capture 7 proves the
exact legacy one-folder/one-TXT fixture and supports an offline golden model;
the separate constrained modern policy is not legacy timestamp equivalence.
I.7 has completed offline timestamp/fixed-state characterization, one
separately approved controlled legacy root-TXT add, and a separate isolated
display-history/Mark-1/Bookmark-1 state experiment on that disposable record.
The evidence independently observed shared timestamp regeneration for add,
bounded fixed-state transitions for the three state families, and preserved
payloads, but did not establish a safe general timestamp or fresh-state rule;
eligibility still fails closed. I.8 now
provides an ordered source-bound multiple-TXT logical model with strict
authoring and no device candidate. I.9 now provides typed offline TXT/BMP
validation with no device candidate. I.10 now provides a flat manifest-driven
representative ebook plan that fails closed on nested sections; H.2 deletion
generalization and preserved-evidence hardening now have a relation-corrected
offline structural gate with zero unexplained non-timestamp differences after
timestamp-only normalization. One constrained modern root-level TXT deletion
smoke has also completed with `0x0000` and exact independent read-back. That
result is limited to its tested scope; the provisional modern timestamp
policy, physical recovery risk, generalized deletion, and separate owner
review requirement remain explicit. J.0–J.3 local Library foundations and
device-aware planning are complete. P18-002 defines the next conservative
machine-enforced envelope and host-only application façade; it does not enable
that envelope for live execution. Capability status belongs in
[`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md), not in repeated milestone
narratives.

The P18-001 UI surface is deliberately crude and review-only: it reports
ordered children, sizes, destination/conflicts, fresh-backup and capacity
requirements, hash-only operation identity, verification requirements, and
the no-retry policy without exposing authorization or a send control.
Unsupported combinations, nesting, multiple packages, batch actions,
generalized deletion, and recovery remain unavailable. Physical opening of
the exact P17-018 package remains a human acceptance check; interrupted-write
recovery and broader compatibility remain unresolved.

## Canonical Desktop Workflow

The accelerated product workflow is:

`Select files/folder → Arrange → Prepare → Preview → Review transfer → Back up → Confirm → Transfer once → Read back → Verify`

In the current normal ttk build, `Review transfer` is followed by
`Refresh live preflight` only when a fresh separately authorized VNW-V15
operation is injected. The UI then presents the exact operation before
transaction-specific confirmation; `Transfer once` remains disabled until the
immutable operation is ready. A future successful path ends only after
explicit `0x0000`, complete post-write backup, independent read-back, durable
result evidence, and marker closure. Missing evidence, conflicts, stale state,
or unsupported shapes remain blocked, and an indeterminate started operation
offers read-only diagnosis rather than retry.

Package grouping is explicit at selection/preparation time; selecting several
unrelated Library rows never merges them. The initial machine-enforced profile
allows one new flat root folder with 1–8 ordered strict TXT or validated 1-bit
BMP children, but is defined and reviewable only until its exact operation has
the required evidence and R3 enablement. The main window follows the approved
three-pane direction: local Library, content/selection workspace, and a
persistent Device Bay, with a collapsible System Console and optional Geek
Mode. Host Library capacity and device capacity must always be labeled
separately. Routine success uses status and console feedback; modal dialogs
are reserved for ambiguity, destructive risk, or unrecoverable failure.

## Device-model boundary

The first capability is explicitly bound to the reviewed Sony InfoCarry
VNW-V15 model profile (`0x054c:0x001e` for the observed USB session). VNW-V10
is also an intended compatibility target, but is currently
`UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED`; it does not inherit V15's
USB, protocol, storage, capacity, display, candidate, authorization, or write
rules. No V10 transfer, delete, restore, or capability-envelope claim is
available until a separate safe read-only characterization establishes it.
VID/PID and bus/address are session observations rather than proven
physical-unit identity. An ambiguous write therefore requires one persistent
installation-wide fail-safe lock, deliberately over-blocking all models until
the original incident/attempt is cleared through read-only diagnosis and a
documented recovery decision.

## Explicitly Deferred

- firmware flashing, unlocking, and alternate or service-mode commands;
- demo-program repair or special non-consumer content modes;
- restore, bulk delete, or synchronization until interruption and recovery
  behavior is separately demonstrated; selective single-item delete follows
  the active v0.4 evidence gate;
- deliberate interrupted-write testing on the owner's only valuable unit;
  such tests require a second or sacrificial VNW-V15 and a separate protocol;
- literal reproduction of destructive legacy bulk-replacement commands.

## Distribution Policy

The initial application is a limited-audience hobby project for rare legacy
hardware. The canonical source checkout and reproducible Python wheel are an
acceptable v0.1 delivery. Developer ID signing and Apple notarization are not
required for this release profile and are deferred until the audience broadens
or a public download is offered. An unsigned or ad-hoc-signed macOS app may be
added as a convenience without changing the device-safety gates. Any write
release remains labeled experimental until the recovery gate above is closed;
distribution convenience must not imply risk-free device mutation.

## Success Measure

The project succeeds when an ordinary user in the intended hobbyist audience
can safely move supported files in both directions using the reproducible
modern application, with verified backups and clear recovery guidance, while
the Windows 2000 environment is retained only as historical evidence rather
than a daily dependency.
