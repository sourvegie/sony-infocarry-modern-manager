# P18-010 — Fresh target and auxiliary-state preservation closure

Date: 2026-09-06
Repository: `sourvegie/sony-infocarry-modern-manager`
Base: `a67d448a803838c6f16b4c21961496ce3e8d9fc9`
Branch: `task/P18-010-aux-state-preservation`
Risk: R3 host-only safety work
Outcome: **READY_FOR_HARDWARE_TEST**

## Scope and evidence identity

This closure reuses the established Library TXT → BMP → TXT pipeline for one
fixed new destination only:

`root\IC_P18_LIBRARY_20260906_01`

It does not create a parallel transfer path or enable arbitrary destinations,
other package shapes, hierarchy, VNW-V10 writes, overwrite, delete, restore,
synchronization, or standing Send exposure.

The required real case is the preserved, read-only P18-009 evidence. Its
verified identities are:

- manifest SHA-256:
  `4f1119294cc51290cf67596ff07af2fc272c252c5dc7ef6a0fdc897bc3e78953`;
- dynamic blob SHA-256:
  `4d17326ef236015321bbad71e5ebde837c12f928c98b59cc4f4d0c34751f4ea9`;
- canonical state identity SHA-256:
  `a6ea8922c0a1fa3231b04cbcf5de9791acf7536329b4eaf8d65a64352cacf9b9`;
- baseline length: 2,091,292 bytes; parsed records: 399.

The fixed P18-010 path is absent from all 335 baseline logical paths. Candidate
construction also rejects any destination conflict, so no overwrite or merge
fallback exists.

## Auxiliary-state policy

The candidate uses policy
`verified_display_history_0x001b_and_bookmark_0x001f_semantic_rebase_plus_zero_count_0x001c_to_0x001e`.
Only record pointers independently resolved to baseline file records may move.
Every opaque value, unused tail byte, zero-count mark block, referenced payload,
and unrelated record remains exact.

| Command | Baseline disposition and SHA-256 | Candidate disposition and SHA-256 |
| --- | --- | --- |
| `0x001b` | 7 counted references; `bf0713e771906724512ad9299610d34c160d18c3f60944934db3b894ab9ce80a` | the same 7 logical references rebased; `edcdda12e1ba34c12bb8f6ae359ec091827169cff4af6b543c93733b3253cca8` |
| `0x001c` | zero count; `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` | byte-exact |
| `0x001d` | zero count; `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` | byte-exact |
| `0x001e` | zero count; `f5a5fd42d16a20302798ef6ed309979b43003d2320d9f0e8ea9831a92759fb4b` | byte-exact |
| `0x001f` | group 0 has 4 nonzero values; `cc867c802ba3f659f3954408fcd2f5b1dbf88562c2b7e3190961d7d7990746f0` | only group-0 dword 1 rebased; `11554c96607bad8c7ca1e8615311414b2540cf7afddf6fcb913050d173d1cf21` |

The metadata insertion is relative `0x00000440`, absolute `0x00000480`.
Five metadata records add an exact delta of `0x00000140` (320 bytes).

### Display-history pointer proof

All offsets below are metadata-relative. Each candidate pointer resolves to the
same logical path and the referenced existing record/content is preserved.

| Before | Logical path | After |
| --- | --- | --- |
| `0x00001240` | `root\簡易マニュアル\infoCarry端末の便利な機能\ファイルにしおりをはさむ／表示する` | `0x00001380` |
| `0x00000600` | `root\IC_P16_MIXED_20260830_02\03-ending` | `0x00000740` |
| `0x000005c0` | `root\IC_P16_MIXED_20260830_02\02-page-01` | `0x00000700` |
| `0x00000580` | `root\IC_P16_MIXED_20260830_02\01-introduction` | `0x000006c0` |
| `0x00000680` | `root\IC_P16_MIXED_20260830_01\01-introduction` | `0x000007c0` |
| `0x000006c0` | `root\IC_P16_MIXED_20260830_01\02-page-01` | `0x00000800` |
| `0x00000700` | `root\IC_P16_MIXED_20260830_01\03-ending` | `0x00000840` |

The counted header and unused tail are unchanged. Seven of seven references
move by exactly `0x140`; there are no unbound references.

### Bookmark-group proof

`0x001f` contains two five-dword groups. Group 0 is
`(0x00001240, 0x00000c00, 0x00000000, 0x00000014, 0xfff101c5)`;
group 1 is all zero. Only group-0 dword 1 is established as a metadata-record
pointer. It maps as follows:

| Group | Before pointer | Bound logical path | After pointer |
| --- | --- | --- | --- |
| 0 | `0x00001240` | `root\簡易マニュアル\infoCarry端末の便利な機能\ファイルにしおりをはさむ／表示する` | `0x00001380` |

Group-0 dwords 2–5 remain opaque and byte-exact. Group 1 and the complete
unused tail also remain byte-exact. The combined opaque-value SHA-256 is
`7a432732d8b32e64bd0fdbad9da48cb531ac9c907419823de7e890458aad2943`.
The authorization binds the bookmark snapshot and semantic validation with
SHA-256 `c944887c515a2f48855fc65be599243191a4aa39324872ff41557f163e8599e7`.

## Exact candidate and capacity

- new-record timestamp: `0x6a9cad00` (one frozen value for new records only);
- candidate records: 404;
- candidate length: 2,107,328 bytes;
- candidate SHA-256:
  `6fd27699ca6c13a46f8d75467ba72860af8b865b7cf19046b7a91f63bf471e01`;
- aligned content growth: 15,716 bytes;
- candidate growth: 16,036 bytes;
- transaction payload length: 2,172,864 bytes;
- transaction SHA-256:
  `9373330cd78f58faaa0cfe61590e4cd0ce489ea5c8069c3112144e69aafe10f4`;
- native `0x0019` capacity: 3,145,728 bytes;
- baseline remaining capacity: 1,054,436 bytes;
- projected post-candidate margin: 1,038,400 bytes.

The final offline replay binds:

- core preflight seal:
  `9377f0f4b9b799f79c6895990e485dd052a953df93e5e19d659cacc4d82c38f9`;
- outer preflight seal:
  `7df88536d1e66174e6986f3d844acba103e8b879902398b1ce4b0ceed9127835`;
- operation-bundle SHA-256:
  `8720074a7e53755085003ac7262548ea1be911071c70467414532d53dd90ed6f`.

The candidate adds exactly the root folder and its ordered
`01-introduction.txt`, `02-page-01.bmp`, and `03-ending.txt` children. All 335
baseline paths, all 271 existing file payloads, all existing timestamps, and
all unknown record bytes are preserved. No baseline path is removed.

## Verification and safety disposition

Focused auxiliary-state/candidate/gate/adapter/review/adversarial coverage:
109 tests passed. Full portable suite: 751 tests passed with 3 intentional
evidence-dependent skips. Python 3.12 compilation and `git diff --check` pass.

The replay used only callbacks over the preserved read-only evidence. Sender
calls: 0. No USB transfer, `0x101b` transmission, durable execution claim,
sender-in-flight marker, hardware access, or device-changing operation
occurred. Existing no-retry, global indeterminate-lock, profile, capacity,
fresh-backup, and capability boundaries remain in force.

Independent strong R3 review completed in two bounded correction rounds. The
initial review found generic bookmark opt-in, stale P17 approval-token reuse,
and missing nonzero-bookmark full-chain coverage. Round 1 closed those findings;
re-review found one remaining product-review approval-binding gap. Round 2
bound the exact P18 owner phrase, confirmation phrase, and explicit policy in
the product review and added six negative cases. Final re-review: **PASS**, no
remaining P0–P2 findings. The final real-evidence product review reports
`ready_for_hardware_test` with no reasons.

The focused [PR #36](https://github.com/sourvegie/sony-infocarry-modern-manager/pull/36)
passes the Python 3.12 portable suite and whitespace gate on
[macOS](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/34026718806/job/101468883272)
and [Windows](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/34026718806/job/101468883228).
The host-side disposition is therefore `READY_FOR_HARDWARE_TEST`. This is not
authorization to begin physical validation.
