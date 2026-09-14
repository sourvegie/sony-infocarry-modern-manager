# Roadmap

This is the forward-looking delivery plan. Detailed milestone history remains
in `analysis/` and in the archived roadmap through P18-001A.

The Astra architecture/product review is an advisory input whose project
decisions are recorded in
[`analysis/phase-18-astra-architecture-product-review-disposition-20260912.md`](analysis/phase-18-astra-architecture-product-review-disposition-20260912.md).
P18-020 and the subsequent P18-025 physical proof are complete on canonical
`main`. The P18-025 proof remains a narrow, separately authorized VNW-V15
operation; it does not authorize new hardware use or expand a capability row.
P18-026 is now the canonical prepared-content foundation, and P18-027 is the
current host-only normal-manager productization step.

## Current sequence

1. **P18-027 — Normal manager workflow productization:** complete the
   host-only `Add content → Preview → Prepare → Review transfer → Send to
   InfoCarry → Verified` flow using the canonical prepared-content artifact,
   typed readiness explanations, Technical Details diagnostics, and one
   background controller. No physical write or capability expansion belongs
   in this step.
2. **Next separately approved physical work:** if approved after the P18-027
   host exit gate, repeat only the exact verified VNW-V15 TXT → BMP → TXT
   operation with fresh target, evidence, and owner authorization. No earlier
   approval carries forward.
3. **Library-integrated ebook preparation and Windows packaging
   investigation:** extend the offline conversion pipeline and test clean
   packaged Windows environments, including Tk, libusb, x64, and ARM
   assumptions. Do not relax runtime requirements or advertise compatibility
   before those tests pass.
4. **Later separately gated capability work:** prioritize only evidence-backed
   selective deletion and other exact shapes; keep restore, synchronization,
   interruption recovery, and broad format expansion outside the live product.

The repository should gradually remove milestone-specific production
identities as generic validated operation data becomes available. Historical
P18 identifiers remain useful in evidence and regression fixtures. SQLite/JSON
storage consolidation is explicitly deferred; first keep one safety-state
owner over the existing persistence boundary.

## Model boundary

VNW-V15 remains the only verified model and the only model associated with the
current transfer profile. VNW-V10 is a declared product target, but its next
step is a separately reviewed read-only characterization: identify USB
descriptors, use only independently established safe read commands, and
validate its complete baseline/capacity semantics before any profile work.
Do not reuse V15 protocol or format assumptions. The indeterminate-write
control remains one installation-wide persistent lock across all sessions and
models because no stable physical-unit identity is proven.

## Later, separately scoped work

Deletion remains a separate delete/re-add lifecycle. Restore, synchronization,
interruption recovery, firmware/service modes, arbitrary package shapes,
nested content, batch operations, and broad format expansion require their own
evidence and review. Backup is a preserved diagnostic/recovery aid, not undo.
