# P18-003 — hierarchical Library evidence and boundary

Date: 2026-09-02
Status: host implementation, independent R2 review, and CI complete; PR #28
is open after push. No hardware/live validation is claimed.

## Product boundary

P18-003 delivers the host workflow Select files/folder → Arrange → Prepare →
Preview. Multi-file and recursive-folder chooser imports preserve a local
ordered hierarchy. Move-up/move-down changes explicit sibling order; removal
changes only the local Library. The approved Tk runtime has no external
file-drop API, so drag-and-drop remains unavailable without an optional TkDND
dependency.

The machine-readable `host-offline-hierarchical-library-txt-bmp-v1` profile is
`host_offline_draft_not_live_enabled` and accepts:

- exactly one prepared root;
- 1–8 TXT/BMP leaves;
- maximum directory depth 2 below the conceptual device root;
- no empty directories;
- maximum 9 directories and 17 logical nodes;
- maximum 39 CP932 bytes per component and 259 CP932 bytes per relative path;
- maximum 1 MiB source and prepared payload per leaf;
- maximum 4 MiB aggregate source and 1 MiB aggregate prepared payload.

TXT uses strict CP932 with CRLF normalization and no replacement. BMP uses the
validated 237×320, uncompressed 1-bit Windows profile. Sibling order is stored,
not alphabetized. Unsupported types, CP932 errors, invalid BMPs, duplicates,
stale sources, excessive limits, and capability mismatch fail closed. A fresh
verified device-path baseline, when supplied to preview, makes destination
conflicts visible precisely; conflicts remain preview-only and cannot authorize
a device operation.

The existing `experimental-flat-root-folder-txt-bmp-v1` V15 profile is unchanged
and remains `defined_not_live_enabled`. The nested draft produces a deterministic
prepared manifest and exact device-tree preview through the unified P18-002
façade; it cannot construct a candidate, authorize, send, clear, or decide live
success.

## Evidence and limit rationale

The 40-byte zero-terminated metadata name field supports the 39-byte CP932
component limit. The Manager's `0x104`-byte path buffers support the conservative
259-byte zero-terminated relative-path limit. Preserved backups contain nested
trees, but nested creation and live compatibility are not proven. Depth 2 is the
smallest useful evidence-bounded nested profile; keeping 1–8 leaves preserves
the reviewed content-count envelope. With no empty directories, one prepared
root plus at most one distinct nested directory per leaf gives maxima of 9
directories and 17 logical nodes.

The raw format's unsigned 32-bit lengths are representation ceilings, not safe
product limits. Likewise, the previously observed 3,145,728-byte V15 response
is not reusable capacity authorization. Without a fresh verified baseline and
fresh native evidence, the preview reports **Not evaluated** for total model
limit, fresh baseline model length, candidate growth, and remaining after
transfer.

## Bounded bookmark warning

The VNW-V10 manual statement supplied with P18-003 says a new Manager transfer
clears Bookmarks. The owner reports corresponding VNW-V15 documentation. The
V10 statement is documentary evidence supplied by the task; the V15 statement
is owner-reported and is not independently page-cited in this repository.

This supports only a user-facing Bookmark warning. It does not establish that
Marks, display history, or other auxiliary state are cleared, does not transfer
V15 protocol assumptions to V10, and does not enable a clear or write action.

## Verification record

Focused hierarchy/order/preparation/preview/tamper and bounded GUI support
checks pass (37 tests). The full portable suite passes (688 tests, 3
intentional skips); compilation and `git diff --check` pass. Independent R2
review and correction re-review both completed with no remaining material
findings. The exclusion audit found no changes under `samples/reference/` and
no private evidence paths in the task diff. GitHub CI for PR #28 passed (Python
3.12 offline suite, 1m22s). No hardware/live validation occurred.

The first independent R2 pass identified four material issues: a missing
legacy `simpledialog` import, an offline capacity-attachment escape, root-folder
symlink resolution before rejection, and conflict wording that overstated
preparation blocking. One correction round fixed all four; the independent
re-review returned PASS.
