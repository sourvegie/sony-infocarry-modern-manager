# Risk Register

Date: 2026-09-05

This file lists open material risks only. Closed findings and chronological
evidence remain in `analysis/`, including the archived register through
P18-001A.

| ID | Risk | Level | Control / current boundary | Next action |
| --- | --- | --- | --- | --- |
| R2-18-01 | Capability-profile, hierarchy persistence, ordering, CP932/path limits, and Library drift could admit an unsupported shape. | R2 | P18-006 table-driven A–G matrix covers non-exact counts/order/types, package/content/binding drift, backup/capacity/conflict changes, and hierarchy/grouping substitution; deterministic hashes and ordering remain fail-closed; no nested candidate or live enablement. | Retain the exact host/offline boundary and add no live nested path; future capability changes require a new reviewed task. |
| R2-18-02 | Cross-platform packaging, font/licensing, hermetic-test, and Windows CI gaps could make the desktop workflow unreliable. | R2 | Keep conversion core portable; record environment assumptions; do not call visual/macOS checks universal. | Resolve licensing and portable CI gaps before a device-changing GUI milestone. |
| R3-18-03 | A future path could accidentally reach authorization, candidate construction, sender, or live-success decisions outside the reviewed boundary. | R3 | Normal GUI/CLI remains review-only; P18-006 proves A–O fail-closed reachability, exact reviewed V15 profile matching, one-shot sender accounting, concurrent-call resistance, and independent post-backup read-back around the isolated coordinator. The one-shot claim is process-local. | Retain the isolated boundary; resolve or explicitly accept crash/cross-process claim persistence before any standing physical-write enablement, and keep broader flat/hierarchical paths non-live until Legacy Oracle comparison and later owner-approved hardware validation. |
| R3-18-04 | Ambiguous completion or interruption has no proven physical recovery/rollback. | R3 | No automatic retry; explicit integer `0x0000` only; malformed/boolean post-start completion is now indeterminate; persistent installation-wide lock; read-only diagnostic backup, original incident/attempt binding, and documented recovery decision required. | Keep restore/recovery and interruption experiments unavailable; preserve the new completion regression coverage. |
| R2-18-05 | Legacy Manager semantics are incomplete for the broader capability envelope. | R2 | Legacy Oracle remains offline by default; exact-shape matrix limits claims; unexplained differences fail closed. | Map the legacy send/delete path and build an offline differential corpus. |
| R2-18-06 | VNW-V10 may differ from VNW-V15 in USB identity, protocol, storage/format, capacity, display, or write behavior. | R2 | VNW-V10 is `UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED`; no V15 constants, candidate, authorization, or write capability are inherited. | Conduct separately reviewed read-only V10 characterization before defining any capability. |
| R2-18-07 | No stable physical-unit identifier is proven, so a per-unit recovery lock would create false precision. | R2 | Use one installation-wide persistent lock across models/sessions; deliberately over-block all writes after ambiguity; clear only with original incident/attempt, complete diagnostic backup, and documented recovery decision. | Keep lock global until a future reviewed identity fact changes the contract. |
| R2-18-08 | Users may mistake a host device-tree preview or stale capacity figure for transfer eligibility. | R2 | Label the nested profile `host_offline_draft_not_live_enabled`; show all four capacity quantities as Not evaluated without fresh verified evidence; expose no nested send action. | Retain explicit preview-only language in GUI/docs and cover capability mismatch in focused tests/review. |

P18-001A responsive usability is closed for the owner-observed bounded sizes;
that human observation does not establish hardware or other display-environment
behavior. Historical P15–P18 risks and dispositions are preserved in the
archived register and their analysis records.
