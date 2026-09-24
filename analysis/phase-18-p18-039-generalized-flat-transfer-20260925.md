# P18-039 — Generalized Flat TXT/BMP Transfer

Date: 2026-09-25  
Base: canonical `main` at `a1d0d0c1a635ab55fefc0b312f5ec824ac17c3ee`  
Branch: `task/P18-039-generalized-flat-transfer`
Code-bearing reviewed head: `f05190e8dcb509ce01f23b4d07c3ea5030654b8a`

## Decision

P18-039 generalizes host admission for one ordinary Local Library folder at
the Device Library root. The selected folder is the single transfer unit. Its
direct children are the persisted ordered sequence; each child must be a
supported TXT or validated 237×320, uncompressed, 1-bit BMP leaf. The profile
is `generalized-flat-root-folder-txt-bmp-v1` with status
`host_reviewed_not_live_proven`.

This is a host implementation and review-readiness milestone. It does not
claim a device capacity maximum, physical proof for five-leaf or other new
orders, or permission to perform a device-changing operation.

## Machine-enforced invariants and bounds

- Exactly one selected root-level ordinary folder; target is one new absent
  folder directly under `root`.
- Direct children only; no nested folder, arbitrary hierarchy, multiple
  package, batch, or automatic grouping behavior.
- One to eight leaves, in source/catalog sibling order. The 1–8 count is a
  host safety/resource envelope retained from the existing conservative
  profile, not a device capacity statement.
- TXT uses the existing strict UTF-8 source validation and CP932/CRLF
  preparation. BMP uses the existing validated 237×320, 1-bit, uncompressed
  profile. Unsupported extensions and malformed content fail closed.
- Names are unique case-insensitively, one CP932-safe path component, and
  folder/child names are at most 39 CP932 bytes.
- Existing resource bounds remain 1 MiB source per child, 1 MiB prepared
  payload per child, 4 MiB source aggregate, and 1 MiB prepared aggregate.
  These are host limits chosen from the existing implementation/profile, not
  tested device maxima.
- No overwrite, merge, replacement, delete, restore, sync, VNW-V10,
  firmware, Toolkit integration, or arbitrary package structure.
- Existing target/folder/content conflicts, duplicate names, source drift,
  invalid order/path projections, capacity uncertainty, template mismatch,
  and fixed/shared/auxiliary-state violations fail closed before authorization
  or sender activity.

## Reused safety seams

The generalized path uses the existing canonical Library façade and does not
add a sender or safety pipeline. It preserves source revalidation, the
operation-owned staged package, dynamic ordered child binding, fresh backup
and native capacity gates, deterministic candidate construction, explicit
authorization and OK/Cancel confirmation, durable claim, sender marker,
global indeterminate-write lock, exact native completion handling, complete
post-write backup, independent semantic readback, terminal marker-resolution
evidence, and no-automatic-retry behavior. The normal Tk controller and
selection/drag/close guards remain the P18-038 path.

The generalized profile remains host-reviewed and not live-proven. Host
preflight and authorization seam tests use injected fixtures only; no USB
discovery, claim, `0x101b`, sender call, live claim consumption, or device
mutation is part of this milestone.

## Implementation and tests

The old exact 3-/4-leaf adapter remains available for compatibility tests;
the normal folder UI now uses the bounded flat adapter. Shape assessment,
readiness, operation intent/binding, package bridge, coordinator review, and
candidate/readback projections accept dynamic ordered child kinds while
retaining exact profile checks for the physically verified subsets.

Representative tests cover all-TXT, all-BMP, alternating mixed order, the
five-leaf mixed boundary, one-leaf and count/byte limits, nesting, unsupported
types, duplicate/conflicting names, existing target conflicts, source/path
drift, and denial before authorization/claim/marker/sender. A five-leaf
candidate is also independently read back for exact ordered child identity,
shared/unrelated-state preservation, and terminal no-retry semantics.

Fresh exact-head review on 2026-09-25 re-read the generalized admission,
package bridge, readiness, operation binding, coordinator review, UI gating,
and readback projections against canonical `main`. Review findings: P0 = 0,
P1 = 0, P2 = 0. No code-bearing changes followed that review. Exact-head
validation passed 117 focused tests and 1,013 portable tests with 3 skipped;
compilation and `git diff --check` also passed. Local Windows host/package
smoke passed with USB enumeration, sender calls, persistent claims, and
sender-marker activity prohibited. Pull-request macOS/Windows package CI is
pending publication.

## Explicit exclusions and next validation

P18-040 nesting and P18-041 deletion are not started. A later owner-authorized
physical validation should use a fresh disposable VNW-V15 unit/state, a fresh
complete backup, a non-existing root-level target, and a five-leaf mixed
TXT/BMP folder (for example TXT/BMP/TXT/BMP/TXT). It must first complete
read-only identity, capacity, conflict, template, and auxiliary-state checks;
then use the existing one-shot confirmation and safety lifecycle; and retain
the complete pre/post backups, exact completion, independent semantic
readback, and terminal sender-marker evidence. Stop without retry on any
uncertain boundary. No such validation was performed here.

Disposition at this record: `READY_FOR_HARDWARE_TEST` after exact-head
independent review, package/CI validation, and owner authorization. This
record is not itself an authorization.
