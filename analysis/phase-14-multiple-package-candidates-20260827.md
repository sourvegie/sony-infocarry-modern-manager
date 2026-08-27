# Phase 14 — ordered multi-child package candidates

Date: 2026-08-27
Status: **Offline candidate slice complete; no live package operation is authorized.**

`infocarry.prepared_package_multi_candidate` extends the captured root-folder
geometry to one newly inserted root folder with an explicitly ordered list of
at least two children. It reuses the existing backup parser, native record
prefix extraction, four-byte alignment, checksum calculation, exact capture-7
fixed-state preflight, parsed `0x0019` total-capacity evidence, and the
staging-range transaction artifact.

The package input is either the existing ordered multi-TXT model or the typed
TXT/BMP model. Every source is reread and hash checked before construction.
Each kind requires an explicitly supplied validated native record template;
the builder does not invent a BMP wrapper. New folder, leading marker, and
children receive one explicit frozen timestamp. Existing record bytes outside
the proven offset/length fields, timestamps, payloads, and prefixes remain
byte-identical. Candidate paths, child order, record count, aligned growth,
capacity, fixed-state hashes, and transaction hashes are recorded without
including candidate or source bytes in tracked reports.

The mixed TXT/BMP candidate is an offline structural model only. The template
requirement and the absence of a native multi-child capture leave live
multi-child eligibility closed. The existing one-folder/one-TXT golden and
live-supported paths are unchanged. Nested folders, arbitrary record types,
additional children beyond the explicitly ordered package, GUI/CLI transfer,
and live hardware operations remain outside this slice.

Focused synthetic coverage is in
`tests/test_prepared_package_multi_candidate.py` and
`tests/test_prepared_package_multi_verify.py`: ordered multi-TXT and TXT/BMP
candidate construction, exact BMP payload preservation, explicit kind-template
requirements, native-capacity-only construction, source-change rejection,
record/timestamp preservation, deterministic output, independent child-order
and type verification, complete backup-object comparison, terminal completion
handling, and source immutability. At this checkpoint the portable suite is
**495 passing tests with three intentional evidence-dependent skips**.
