# Sony InfoCarry Modern Manager — Product Vision

## Vision

Sony InfoCarry Modern Manager is a simple file and library manager for moving
supported content between a computer and an InfoCarry. The main workspace
presents two clear places:

**Local Library ↔ InfoCarry Device**

A user should be able to add files and folders, select content, transfer it,
see verified completion, and immediately see the refreshed device tree. For
content already on the device, a user should be able to select items, delete
them through a guarded flow, verify the result, and see the refreshed tree.

Users should not need to understand transfer profiles, prepared-artifact
identities, protocol commands, claims, hashes, or validation stages to complete
normal library tasks. Technical evidence remains available when needed, behind
a clear technical-details view.

This describes the intended product workflow. The current operations available
on each model remain defined by [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md)
and their evidence and safety gates. This vision does not enable an operation.

## Primary areas

### Local Library

The Local Library contains content the user has added to the Manager. It
should let the user:

- add individual files and whole folders;
- browse nested folders in a familiar tree;
- select one or more files or folders;
- preview content where useful;
- remove items from the Manager's local library; and
- transfer selected content to the connected InfoCarry when that operation is
  supported and ready.

Removing an item from the Local Library only removes its local library entry
or managed copy according to the documented storage behavior. It does not
delete device content.

### Device Library

The Device Library shows the actual current contents of the connected
InfoCarry. It should let the user:

- refresh and browse the device tree, including nested folders;
- select one or more files or folders;
- export selected content where supported;
- delete selected content through the guarded deletion workflow;
- create and inspect backups; and
- see device capacity and connection status.

After a verified transfer or deletion, the Manager refreshes the Device
Library automatically. A completion message appears only after the operation's
independent verification succeeds. If the outcome is uncertain, the Manager
reports that clearly and provides read-only diagnosis.

### Everyday workflows

For adding content:

`Add files or folders → Select content → Transfer → Verify completion → Refresh the device tree`

For managing existing device content:

`Select files or folders → Delete → Verify removal → Refresh the device tree`

The normal interface presents clear names, destinations, conflicts, capacity,
backup state, progress, and completion. The user sees the selected logical
scope before confirming a device change. Technical identifiers and protocol
details stay out of the ordinary workflow.

Backup remains a normal safety and read-only function. It is a preserved copy
and diagnostic aid, not an undo operation.

## Realistic library model

The library model and its validation should serve real collections. A useful
planning and test target is tens of folders—roughly 30–50—and many TXT and BMP
items, including nested structures. These figures describe realistic scale;
they are not product hard limits. Any firm limit must come from demonstrated
device, format, protocol, or resource constraints and must be documented.

Future validation should establish reusable bounded structural rules for
folders and typed files. It should cover valid names and paths, supported item
types, parent-child relationships, uniqueness, nesting, item and folder counts,
payload sizes, conflicts, capacity, and relevant ordering rules. Tests should
exercise representative generated structures, boundary cases, and invalid
structures.

Exact captured shapes and named examples remain valuable evidence and
regression fixtures. They establish facts about those cases. They do not define
the complete future library model through a list of exact leaf permutations.
Generalizing a structural model does not by itself make any device operation
eligible; each operation remains behind its applicable capability and safety
gates.

## Product principles

1. Protect user data before adding convenience.
2. Make browsing, export, and verified backup useful without enabling a write.
3. Keep transfer and deletion scoped to the user's explicit selection. Do not
   infer synchronization, merge, send-all, or deletion of unmatched content.
4. Require a fresh review of target, conflicts, capacity, source state, and
   applicable device evidence before a device change. Discard stale reviews.
5. Preserve the existing verified pre-write backup, operation-specific
   authorization, explicit confirmation, bounded transfer, single-use durable
   claim, proof-bound sender-marker handling, and installation-wide
   indeterminate-write controls.
6. Keep device-changing operations labeled Experimental while physical commit
   atomicity and interrupted-write recovery remain unproven.
7. Never automatically retry a device-changing operation after it has started
   if its completion is missing, ambiguous, interrupted, timed out, cancelled,
   malformed, or otherwise indeterminate. Require read-only diagnosis under
   the existing persistent safety lock.
8. Report verified success only after the exact native integer result `0x0000`,
   a complete post-write backup, independent read-back of expected and
   unaffected state, a durable terminal result, and proof-bound sender-marker
   resolution.
9. Preserve original backups and unknown legacy bytes losslessly.
10. Keep current model-specific boundaries. VNW-V15 is the only verified model;
    VNW-V10 remains uncharacterized and does not inherit V15 behavior.
11. Explain the difference between the selected logical change and the physical
    transfer scope. The device protocol may rewrite a complete candidate
    library image, so operation time is not proportional to selected file size.
12. Keep protocol, conversion, and library logic portable where practical.
    Use typed outcomes and stable reason codes; render clear user-facing status
    from those values.
13. Keep claims, hashes, seals, artifact identities, and evidence manifests
    discoverable in technical details without making them normal user concepts.

A product-direction document, fixture, successful fake transfer, or previous
narrow live result cannot widen the current capability boundary. The matrix
and the project's review and authorization process remain authoritative.

## Toolkit integration

The InfoCarry Toolkit snapshot `97042a9` is an important source for future
conversion integration. Defer that integration until the core Manager
workflow is useful for adding, browsing, transferring, verifying, and managing
everyday TXT and BMP content.

Before that integration, avoid heavy polish of the separate Text Converter and
Ebook Renderer experiences. Keep conversion focused on the work needed for
the Manager's core workflow. The eventual integration should route supported
conversion through the Manager's Local Library and its ordinary review flow.
Toolkit integration does not establish device support or expand a capability.

## Explicitly deferred

- restore from backup, until it has its own tested recovery workflow;
- synchronization, removal of unmatched content, or bulk replacement;
- general bulk deletion, until its risks and safeguards are separately
  demonstrated;
- deliberate interrupted-write testing on the owner's only valuable device;
- firmware changes, unlocking, service modes, and alternate commands;
- broad format expansion without evidence for the full preparation and
  transfer path; and
- heavy polish of the standalone Text Converter and Ebook Renderer before
  Toolkit integration.

Selective deletion is a core product requirement. Its implementation remains
guarded by the evidence, model, and operation-specific safety gates.

## Distribution policy

The initial application is a limited-audience hobby project for rare legacy
hardware. The canonical source checkout and reproducible Python wheel are an
acceptable initial delivery. Developer ID signing and Apple notarization are
not required for this release profile and remain deferred until the audience
broadens or a public download is offered. An unsigned or ad-hoc-signed macOS
app may be added as a convenience without changing device-safety gates.

Windows packaging remains an investigation rather than a compatibility claim.
Clean-install testing must cover the selected Tk runtime, libusb deployment,
declared Windows x64 and ARM environments, and the packaged application before
any requirement is relaxed or compatibility is advertised.

## Success measure

The project succeeds when an ordinary user can manage a realistic Local
Library and InfoCarry Device Library, move supported files in both directions,
and manage selected device content with verified results and clear recovery
guidance. The Windows 2000 environment remains historical evidence rather than
a daily dependency.
