# Risk Register

Date: 2026-09-02

This file lists open material risks only. Closed findings and chronological
evidence remain in `analysis/`, including the archived register through
P18-001A.

| ID | Risk | Level | Control / current boundary | Next action |
| --- | --- | --- | --- | --- |
| R2-18-01 | Capability-profile, package grouping, CP932/path limits, and Library drift could admit an unsupported shape. | R2 | One explicit versioned profile; deterministic hashes; explicit grouping; 1–8 flat ordered TXT/BMP children; fail-closed validation; no live enablement. | Focused tamper/migration/GUI tests and independent review before expanding exposure. |
| R2-18-02 | Cross-platform packaging, font/licensing, hermetic-test, and Windows CI gaps could make the desktop workflow unreliable. | R2 | Keep conversion core portable; record environment assumptions; do not call visual/macOS checks universal. | Resolve licensing and portable CI gaps before a device-changing GUI milestone. |
| R3-18-03 | A future path could accidentally reach authorization, candidate construction, sender, or live-success decisions outside the reviewed boundary. | R3 | Host façade is hash-only and disabled; normal GUI/CLI has no send action; reuse reviewed P17 runner only at a later R3 gate. | Add guarded execution/read-back integration only as a separately reviewed R3 task. |
| R3-18-04 | Ambiguous completion or interruption has no proven physical recovery/rollback. | R3 | No automatic retry; explicit `0x0000` only; persistent per-device indeterminate lock; read-only diagnostic backup and documented recovery decision required. | Keep restore/recovery and interruption experiments unavailable. |
| R2-18-05 | Legacy Manager semantics are incomplete for the broader capability envelope. | R2 | Legacy Oracle remains offline by default; exact-shape matrix limits claims; unexplained differences fail closed. | Map the legacy send/delete path and build an offline differential corpus. |

P18-001A responsive usability is closed for the owner-observed bounded sizes;
that human observation does not establish hardware or other display-environment
behavior. Historical P15–P18 risks and dispositions are preserved in the
archived register and their analysis records.
