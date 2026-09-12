# Roadmap

This is the forward-looking delivery plan. Detailed milestone history remains
in `analysis/` and in the archived roadmap through P18-001A.

The Astra architecture/product review is an advisory input whose project
decisions are recorded in
[`analysis/phase-18-astra-architecture-product-review-disposition-20260912.md`](analysis/phase-18-astra-architecture-product-review-disposition-20260912.md).
P18-020 is complete on canonical `main` and resolves the known
application-wide existing-text write-safety bypass. The next physical attempt
is still a new, separately authorized operation; this disposition does not
authorize hardware use or expand a capability row.

## Current sequence

1. **P18-021 — Fresh UI-driven physical validation:** if separately approved,
   repeat only the exact host-ready VNW-V15 TXT → BMP → TXT operation with a
   fresh target, fresh evidence, and fresh owner authorization. No P18-018 or
   earlier approval carries forward.
2. **P18-022 — Prepared-content/product workflow consolidation:** make
   manager-prepared and imported content use one prepared-content contract;
   integrate conversion into Library preparation and simplify the
   Select → Prepare → Preview → Transfer experience without changing the
   capability matrix.
3. **P18-023 — Responsive operation controller and typed outcomes:** move
   long-running preparation, backup, preflight, and transfer work behind one
   background controller; use typed readiness/outcome reasons and keep
   engineering evidence in Technical details.
4. **P18-024 — Useful bounded flat-package expansion:** consider variable
   TXT/BMP package shapes only after fresh physical UI validation and a new
   evidence/review gate. No automatic grouping, hierarchy, batch, or recovery
   claim follows from this sequence.
5. **Library-integrated ebook preparation and Windows packaging
   investigation:** extend the offline conversion pipeline and test clean
   packaged Windows environments, including Tk, libusb, x64, and ARM
   assumptions. Do not relax runtime requirements or advertise compatibility
   before those tests pass.
6. **Later separately gated capability work:** prioritize only evidence-backed
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
