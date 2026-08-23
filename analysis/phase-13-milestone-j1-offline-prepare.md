# Milestone J.1 — offline Prepare workflow

Status: complete in the sanitized source-of-truth checkout.

## Supported scope

`prepare_library_item()` binds one current Library item whose source is one
regular UTF-8 `.txt` file to the existing `PreparedTextPackage` builder. The
caller supplies exactly one root-level folder name and one `.txt` child name.
The existing builder remains the sole authoring boundary: strict UTF-8 input,
strict CP932 encoding, CRLF normalization, NUL rejection, safe names, one
ordered child, deterministic prepared manifest, and native-wrapper metadata
requirements are reused without a competing serializer.

Preparation revalidates the catalog source immediately before building. A
changed or missing source, unsupported format, invalid source, or authoring
error is recorded as a blocked catalog state while preserving the original
source path/hash. An unchanged prepared item remains ready on revalidation.
The source is never copied over, moved, edited, or deleted.

## Audit and safety boundary

The returned audit includes the item identity, exact source path and SHA-256,
UTF-8 size and character count, prepared manifest hash, target folder/child
paths, encoded and aligned sizes, compatibility status, and the explicit
`OFFLINE PREPARATION ONLY — NO DEVICE CHANGE` notice. It records
`device_operation: none` and `usb_accessed: false`. No backup, capacity
preflight, fixed-state derivation, candidate construction, authorization, or
transport is called by this workflow.

## Verification

`tests/test_library_prepare.py` covers canonical package reuse, deterministic
re-preparation, no-device audit and source preservation, strict CP932 failure,
stale-source rejection with original-hash preservation, and invalid-target
failure. Together with the J.0 tests, the portable sanitized suite passes 378
tests with the three intentional evidence-dependent skips.

The next slice is a functional but deliberately crude ttk Library view. It
may import and prepare local TXT sources, but it must not expose or invoke a
routine package-transfer action.
