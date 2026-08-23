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
- create any proven folders and multiple records required for one prepared
  book/content package;
- transfer one prepared supported item after capacity/conflict review; and
- verify every created or removed record and all affected sidecars.

Delete and multi-file creation have separate evidence and live-test gates.
Neither is inferred from successful single-TXT creation.

### v0.5 — Local Library and safe staged transfer

A user can additionally:

- import supported sources into a persistent local Library by picker or
  drag-and-drop;
- prepare and preview them using tested conversion profiles;
- select one or more ready items for a transfer queue;
- review destinations, conflicts, estimated size, device capacity, additions,
  and any explicitly requested removals before authorization; and
- execute only operation types already proven by the earlier release gates.

The batch label is **Transfer all ready items**, not “full transfer.” It means
queue every compatible prepared item. It never means synchronize, delete
unmatched device content, restore a side, or reproduce the legacy send-all
operation. Unsupported queued items remain preview-only and cannot be sent.

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

The current parity priority is offline preparation of one minimum text package:
one root-level folder with one TXT child. Capture 7 proves the exact legacy
one-folder/one-TXT fixture and supports an offline golden model; arbitrary
folder and multi-record creation remain unproven. A separate constrained
modern policy is active offline: preserve existing timestamps, use one explicit
frozen timestamp for the folder, marker, and TXT child, and accept only the
capture-7 all-zero fixed state without assigning category, mark, bookmark,
selection, history, or sidecar membership. This is not legacy timestamp
equivalence. The I.4 offline safety gate and I.6 live-smoke evidence are
complete for this exact constrained shape; one separately approved smoke
completed with independent full read-back. Arbitrary package transfer and
normal GUI/CLI exposure remain prohibited. The
offline candidate now uses a fail-closed complete-growth capacity gate and
exact capture-7 fixed-state preflight, and its package-specific authorization
binding, independent read-back verifier, and fake-only guarded workflow are
transport-free outside the isolated runner.
Milestone H.1
selective-delete generalization remains blocked and parked pending independent
evidence, so no delete control or live-delete protocol is authorized while
this offline package work proceeds.

## Canonical Desktop Workflow

The primary workflow is:

`Import → Prepare → Inspect → Queue → Transfer → Verify`

The main window follows the approved three-pane direction: local Library,
content/selection workspace, and a persistent Device Bay, with a collapsible
System Console and optional Geek Mode. Host Library capacity and device
capacity must always be labeled separately. Routine success uses status and
console feedback; modal dialogs are reserved for ambiguity, destructive risk,
or unrecoverable failure.

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
