# Phase 14 — flat representative ebook candidate

Date: 2026-08-27
Status: **Offline candidate connected; live transfer remains prohibited.**

`infocarry.prepared_ebook_candidate` connects the existing manifest-driven flat
ebook plan to the ordered TXT/BMP candidate and independent read-back models.
The supported shape is one new root folder with an explicit flat ordered list
of at least two validated children. The candidate binds the plan hash, package
manifest hash, source and payload hashes, item types/order, explicit frozen
timestamp, exact fresh all-zero fixed state, parsed native `0x0019` capacity,
candidate hash, and prospective transaction hash.

Nested sections remain rejected by the existing ebook plan. No flattening is
performed. This is not a claim for arbitrary ebook structures, unproven BMP
wrappers, multiple folders, or live package transfer. External owner content
was not copied; tests use generated synthetic TXT and BMP inputs only.

Focused tests cover flat-plan-to-candidate connection, ordered target paths,
USB neutrality, deterministic candidate identity, and nested-section rejection.
Together with the ordered candidate and independent verifier, the portable
suite is **493 passing tests with three intentional evidence-dependent skips**.
