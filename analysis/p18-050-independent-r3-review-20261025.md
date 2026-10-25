# P18-050 independent exact-code-head R3 review

Date: 2026-10-25 JST. Final disposition: **PASS for the reviewed offline implementation. P0/P1/P2 = 0/0/0.** This review grants no physical-write, integration, push or merge authority.

Reviewed source/script/test head: **`cb5714ddf9f149d7febe3dfe9d29224316769125`**. Comparison baseline: `cb12b186b05957dc5d84a6c75bcd9eab9e8bfdf2`. Published sanitized ancestor: `25bfddda7232617f7fc84ada4c44c9440306b584`. Final working changes inspected after the source checkpoint are documentation only; source, scripts and tests still match the exact reviewed head.

## Independence and scope

A separate reviewer agent independently inspected the exact production/test diff, AGENTS/WORKFLOW requirements, product vision/roadmap, capability matrix, risk register, relevant preserved evidence and validation results. The executor's delivery summary was used only for navigation. Review covered promoted admission, native model/marker/allocation constraints, protected-state derivation, frozen authorization/seal identity, fresh/reconnect equivalence, one-use claim/marker/global-lock lifecycle, integer native completion, no-retry handling, independent readback, UI confirmation/cancel/refresh, and the host-only BMP preparation path.

The reviewer invoked no USB discovery, production runtime factory, hardware command, physical sender, production safety-state mutation or Git publication operation. Automated sends and safety stores used isolated fakes. Original evidence and the primary checkout were read-only. Only this new sanitized repository report was written by the reviewer.

## Initial finding and correction

Initial source `f660bfc7b99eb8332f69861109bbf690ab566e7f` had **P0/P1/P2 = 0/0/1**. The P2 was reproducible: the promoted nested TXT builder accepted a baseline whose two unrelated surviving files shared overlapping allocations. The inherited nested model checked the selected allocation against survivors, but did not check survivor-versus-survivor overlap. This violated the promoted complete-allocation admission contract even though the candidate preserved those bytes.

One correction round added the established aligned/bounded/disjoint geometry check to the complete baseline and candidate inside **only** the promoted nested TXT builder. New regressions refuse unrelated overlap and misalignment before opening a runtime. The reviewer independently reran the original overlap reproduction against the corrected head and confirmed refusal. Existing root admission functions and the generic nested sender gate were not broadened. No material finding remains.

## Independently checked evidence and capability boundary

- All **15/15** anchors in the preserved final P18-049 independent verification record rehash correctly. The reviewer separately loaded the actual original pre-placement and final native archives and directly compared all **eight native objects byte-for-byte**. The actual final Delete also passes the independent nested readback verifier against its actual fresh transaction-before archive.
- Direct inspection confirms the historical source records at `0x1c0` and `0x7180` and their 53-byte/8,850-byte payloads differ. Their copied record slices and complete native prefix match. Rebuilding placement from each source produces the same complete candidate SHA-256 `a0d28fbbd8ce6bd354df9f91ccf0088c045f84053178e9f4523c6de615933475`. This corroborates the field-overwrite explanation; it does not retroactively repair the original envelope mismatch or erase its historical P1/STOP.
- The promoted prefix is exactly `01fffffffdffffffffffffffffffffffffffffffffffffffffffffffffffffff`, SHA-256 `d0bcc6bc85dc36cdc1ad3882952c5d3d4414869c0bdd75b3b58ba28a32deb92a`, rather than all-FF32. Independent replay at the corrected head retains **36** matching archived TXT candidates, with payload-length remainders **11/9/10/6** for modulo-four values 0/1/2/3.
- Physical proof remains only the exact P18-049 34-byte fixture at `0x880`. The enabled class is explicitly an engineering inference: one unique unread `e0`/`ffffffff`/`200` TXT leaf under exactly two existing ordinary folders, exact observed prefix, nonempty surviving parent, safe exact CP932 identities, supported graph/markers, complete aligned/disjoint allocation and unreferenced supported protected state. Other depths, emptied parent, alternate state/prefix, references/active Marks, ambiguity, unsupported geometry, directories/subtrees and VNW-V10 refuse.
- The normal single Delete/Cancel confirmation binds the frozen operation. Preparation and final execution retain complete fresh backup/capacity, reconnect equivalence, claim/marker/global lock, one sender, zero automatic retries, native integer zero, complete independent readback and verified refresh. Root TXT/BMP gates are preserved; arbitrary nested sender binding stays closed.

## Nested BMP boundary

Nested BMP remains **host-only**. The separate entry point requires exact existing parent identity, canonical unread BMP template/prefix/opaque fields, explicit capacity budget/timestamp, distinct source-record/payload/copied-field provenance, survivor preservation, protected-state cross-check and exact inverse restoration. The private two-operation rehearsal is correctly labeled unexecutable and not hardware-ready. It creates no live nested-BMP Delete adapter or UI admission and no nested-BMP Delete transaction/authorization.

The potential future sequence is one exact disposable placement followed by deletion of that same leaf, maximum two senders total, each with fresh guards and independent native readback, and final actual restoration of all eight original objects. An exact reviewed execution adapter, fresh native baseline/capacity and one immutable owner-approved task envelope are still required. Copied probe/auxiliary simulation values are explicitly not predictions of native post-placement responses. This review neither freezes an executable hardware envelope nor requests approval for this rehearsal.

## Validation and publication checks

The reviewer independently ran **91 focused tests** at the initial head (all passed, 115.442 seconds), then all **15 promoted TXT/BMP tests** at the corrected head (all passed, 32.000 seconds), including the new geometry refusal. The executor's completed corrected full log was independently inspected: **1,296 run, 1,291 passed, five established skips**, 322.113 seconds. The five skips remain the existing external-capture/raw-evidence omissions; no new skip masks a failure.

Corrected package build/plist/ad-hoc signature verification, portable wheel build, isolated frozen runtime and native Tk workflow results were inspected and pass. Native Tk automation exercised actual selection, enabled Delete, one actual Delete/Cancel dialog, fake completion and verified refresh; it records zero real USB calls/writes. The frozen runtime reports zero device-enumeration, sender, claim-consumption and sender-marker counters. These are automated host results, not human visual inspection, Windows execution or new physical-device proof.

Independent `git diff --check` and full Git integrity checks pass. Sanitized published ancestry is confirmed; the excluded private JSON blob is absent from outgoing objects. The reviewed outgoing range's largest blob is **117,881 bytes**. Before/after preservation snapshots are byte-identical, including primary HEAD/status/refs and captured file hashes. No new raw native evidence or private payload was added by this review. Final documentation-only closeout still requires the executor's final privacy/clean-tree audit; no local-main integration, push or merge is authorized here.

Final open findings: **P0 = 0; P1 = 0; P2 = 0**. The historical provenance P1 and this review's resolved initial allocation P2 remain recorded above. Zero physical writes were performed during this review.
