# Sony InfoCarry Modern Manager — Risk Register

Risks are reviewed before expanding device-write scope. A release cannot pass
its gate while a critical risk assigned to that release remains untreated.

Source-of-truth boundary: this sanitized checkout is the future development
source and verified commits are pushed normally to the approved private
remote. The sibling evidence-bearing `modern-client` checkout is a read-only
local research archive. Older commit SHAs refer to that local history unless
explicitly marked as sanitized-repository commits. Raw evidence is intentionally
absent from this checkout.

| ID | Risk | Level | Required treatment and release gate | Status |
| --- | --- | --- | --- | --- |

Current checkpoint: I.4/I.5/I.6 are complete for the constrained policy; I.6
completed one approved live one-folder/one-TXT package smoke with `0x0000` and
exact independent read-back. I.7 offline timestamp/fixed-state characterization
is complete as a fail-closed negative result: no safe general rule was
established. I.8's ordered multiple-TXT logical model and I.9's typed TXT/BMP
model are complete offline; I.10's flat ebook plan is complete offline, while
H.2 deletion generalization is complete for its supported offline structural
scope while live eligibility remains unexecuted and J.3 device-aware Library
planning remains deferred. The current portable suite is **472 tests** with three
intentional evidence-dependent skips. Arbitrary package behavior, generalized
deletion, normal GUI/CLI transfer, and physical recovery remain unproven.
The I.7 controlled legacy add protocol was approved and completed as
`I7-LEGACY-ADD-01`: one synthetic root TXT was added and independently
verified in the post-add backup. Shared timestamp regeneration and unchanged
all-zero fixed state are observed. A later separately approved state experiment
on that record isolated display history, Mark 1, and Bookmark 1 in complete
backups, but timestamp generation and generalized nonzero-state derivation
remain unresolved. The separately approved I7 deletion observation now verifies
one persisted stateful legacy deletion effect: exactly one path removed, no
path added, shared payloads preserved, active display/Mark 1/Bookmark 1
references cleared, and the native candidate matching the post-delete blob.
Request-4 completion, the causal timestamp rule, physical recovery, and live
generalized deletion remain unresolved. The offline model now preserves
surviving timestamps, derives only supported fresh fixed state, binds the
exact candidate, and verifies fake read-back with no retry; this is not live
eligibility. The 2026-08-26 preserved-evidence comparison passes path/count/
payload checks and, after the relation-based parent-marker correction, leaves
zero unexplained non-timestamp differences after timestamp-only normalization.
H.2's offline structural gate is complete, while the
timestamp tool and offline validator are preparation-only and do not authorize
a modern device mutation.

Historical I.4/I.5/I.6 status: the constrained offline/fake-only gate and
unexecuted owner protocol are complete at the **329-test** I.4 checkpoint;
native ordinary-worker total-limit capacity semantics are resolved offline in
I.5 at the **336-test** checkpoint; I.6 adds hash-bound parsed `0x0019`
capacity evidence, native-only live eligibility, ordered fake workflow
coverage, and an isolated owner-approved runner. Attempt 02 completed one
narrow approved live package smoke with `0x0000` and independent offline
read-back verification after the verifier correction in `cf7803b`; the suite
is now **360 tests**. Arbitrary folders and normal GUI/CLI package action
remain blocked. The Manager UI free-space mapping remains separate and
unresolved.
R3's current I.6 evidence is recorded in
`analysis/phase-12-milestone-i6-package-live-smoke-attempt-02-result-20260823.md`:
the package candidate and authorization bind the complete parsed `0x0019`
response, raw SHA-256, native limit, baseline/candidate lengths, growth, and
remaining growth. The constrained live result is not a claim for arbitrary
package transport.
Command `0x0024` is observed to equal the current dynamic-model length and
excluded from capacity authorization; broader semantics unresolved. Physical
package transport, live completion behavior, interrupted-write recovery, and
normal package exposure remain blocked.
Owner-approved preflight attempt 01 stopped before candidate construction due
to a stale backup-verification clock; no `0x101b` was issued and no retry was
performed. The offline readiness regression corrected that clock boundary
while preserving future-timestamp rejection. Attempt 02 used a new evidence
destination and one approved transaction; its initial terminal audit remains
preserved, and the corrected offline verifier confirms the constrained result.
| R1 | Device data can be corrupted or lost by an incomplete or incorrect write. | Critical | Keep v0.1 read-only. For every later write: verify a fresh immutable backup, limit the target, preview the exact change, require explicit authorization, never retry an interrupted write automatically, and verify by full read-back. Do not expose legacy send-all. | Constrained existing-text replacement and one narrow root-level-TXT add each passed one approved live smoke on 2026-08-22 with preserved before/after archives and full read-back verification; broader writes remain blocked. |
| R2 | Restore, delete, and recovery after an actual partial device commit are not proven. | Critical | Keep restore absent. For selective delete, preserve the completed legacy deletion-effect fixture, generalize only from independently supported fresh-backup rules, add failure-injection tests and recovery guidance, then require a separate approved modern smoke only after the live gate closes. Never combine delete proof with creation proof. | The separately approved `I7-LEGACY-DELETE-01` session adds a verified stateful persisted-effect fixture: exactly one target removed, no path added, all surviving file payloads preserved, all three active target references cleared, and the native candidate exactly matching the post-delete dynamic blob. The corrected offline H.2 comparison now has zero unexplained non-timestamp differences after masking only surviving timestamp fields and the derived checksum. The modern model preserves surviving timestamps, derives only supported fixed-state forms, binds the fresh backup/target/candidate/transaction, and verifies fake read-back with no retry. The causal legacy timestamp rule, trustworthy request-4 completion, physical atomicity/recovery, and live modern delete remain unresolved; modern delete and normal GUI/CLI actions remain prohibited. |
| R3 | Arbitrary new files require proven metadata/state construction, capacity handling, and guarded execution. | Critical | Use clean capture 04 as the golden legacy add fixture and capture 7 as the exact folder/package golden fixture. Require exact or documented normalized offline equivalence, unrelated-byte preservation, fail-closed capacity, exact operation binding, one-shot failure behavior, and full read-back before any approved live modern package smoke. | I.6 completed one approved constrained folder/TXT smoke with `0x0000`, exact candidate read-back, preserved shared records/payloads/timestamps, and fixed-state equality after offline verifier correction. I.7 add-01 and the stateful delete observation independently verified narrow legacy effects, but neither resolved a general timestamp or fresh-state rule. I.8, I.9, and I.10 remain offline-only. The relation-corrected offline H.2 deletion model and fake-only workflow are complete for their supported structural scope; the suite is **472 tests** with three intentional skips. Arbitrary packages, modern deletion, normal GUI/CLI package action, and interrupted-write recovery remain blocked. |
| R4 | Development could continue in the evidence-bearing research archive instead of the sanitized source-of-truth checkout. | Critical | Commit product changes only in this sanitized repository, push each verified commit normally to `origin/main`, and keep the sibling research archive read-only. Preserve the complete local research bundle separately. | Mitigated for the migration checkpoint: sanitized commit `02df1fb` is pushed to the private `sourvegie/sony-infocarry-modern-manager` repository; the original research checkout remains read-only. |
| R5 | The prototype GUI uses macOS system Python 3.9 and deprecated Tk 8.5; it already renders incorrectly. | High | Select a supported runtime/UI stack, pin dependencies, and reproduce backup loading and browsing without layout defects. Do not spend release effort polishing the deprecated Tk 8.5 rendering path. | Mitigated on 2026-08-22: Tkinter/ttk with Python 3.12.13 and Tcl/Tk 9.0 is approved, guarded by `src/infocarry/runtime.py`, and the backup browser, text preview, and BMP preview passed the hobby-release usability test. |
| R6 | Rare original hardware and obsolete Windows software make evidence difficult to recreate. | High | Preserve original ISO, captures, raw backups, fixtures, hashes, and manifests. Keep live tests opt-in and use offline fixtures for routine development. | Mitigated; ongoing. Milestone G live-smoke and Milestone H attempt-01/02 raw and derived artifacts were copied without modifying their originals into stable evidence roots and verified by SHA-256 manifests on 2026-08-22. |
| R7 | Unknown legacy bytes or formats may be silently changed during conversion. | High | Preserve raw objects and unknown fields, use lossless exports, reject unsupported mutations, and require parser/rebuilder round trips against fixtures. | Mitigated for read/export and constrained replacement. |
| R8 | Evidence, generated test output, and distributable source are mixed and large, increasing packaging and audit errors. | Medium | Separate immutable evidence, generated output, and application source in the canonical repository; exclude generated output from release packages and retain hash manifests. | Partially mitigated on 2026-08-22. Canonical source excludes environments/output and large live captures while retaining required regression evidence. |
| R9 | Broader macOS distribution would require native packaging, Gatekeeper handling, USB-permission validation, and a tested support matrix. | High | For the limited hobby audience, deliver the canonical source checkout and reproducible wheel with pinned runtime instructions and recovery guidance. Reopen Developer ID signing, notarization, native packaging, and broader support testing before public distribution. | Accepted for limited-audience v0.1 on 2026-08-22. The owner explicitly deferred signed distribution; see `analysis/phase-10-hobby-distribution-decision.md`. Reopens if the audience broadens. |
| R10 | Firmware/unlock or alternate service commands could be mistaken for normal transfer operations. | Critical | Keep alternate modes outside the normal client and protocol API. Require a separate research plan and explicit authorization if ever studied. | Avoided by scope. |
| R11 | The canonical application and the separate conversion project both use the Python package name `infocarry`; combining environments could silently import the wrong implementation or overwrite user work. | High | Keep `InfoCarry-Toolkit` read-only, do not install both projects into one environment, reimplement or deliberately copy reviewed concepts into the canonical tree, and test the canonical conversion boundary without external checkout imports. | Partially mitigated by `offline_conversion.py` and the documented namespace boundary; remains under review during EPUB/MOBI integration. |
| R12 | Logical page previews or newly rendered BMPs could be mistaken for verified device-compatible output before font metrics, rasterization, and legacy display behavior are proven. | High | Keep conversion offline and label compatibility claims conservatively. Validate exact dimensions, bit depth, palette, stride, determinism, and representative glyph output before enabling any device workflow. Record any new rendering dependency and packaging impact. | Open; blocks a device-compatibility claim for rendered pages, but does not block v0.2 or offline v0.3 development. |
| R13 | Local Library import, generated output, and original user files could be confused, overwritten, or deleted together. | High | Use a versioned catalog and explicit source/prepared relationships. Import non-destructively, never overwrite an existing output silently, preserve source paths and hashes, mark stale output, and make Library removal non-destructive by default. Keep Library storage separate from immutable reverse-engineering evidence. | J.0/J.1/J.2 local foundation complete in `35f4406`, `7650aaa`, and `9dada7b` with 379 tests: per-user versioned catalog, atomic previous-version recovery, idempotent import, stale/missing detection, strict offline Prepare, source preservation, and catalog-only removal. Drag-and-drop, generated output lifecycle, and device transfer remain open. |
| R14 | Selective or “full” batch transfer could amplify an incorrect operation, be misunderstood as destructive synchronization, or imply a payload-sized physical copy when `0x101b` actually carries a complete candidate model. | Critical | Name the batch operation **Transfer all ready items** and define it as an additive logical queue only. Explain that selected items limit the intended change set but do not reduce the physical write to those payload bytes. Preflight every item, destination, conflict, complete candidate size, and capacity result; require a fresh backup and exact authorization; stop on first failure; never retry automatically; verify supported results. Keep unsupported/new-record items preview-only until their individual gates are proven. | Open; blocks general batch execution and any sync/replace semantics. Does not block offline queue planning. The legacy same-duration warning corroborates the captured complete-model write structure. |
| R15 | The device's commit point and recovery behavior after an interrupted `0x101b` transaction are unknown. A nominal file operation transmits broad device state and may not be atomic. | Critical | Permit ordinary cancellation before the device-changing request starts. After it starts, treat disconnect, timeout, cancellation, or missing completion as an indeterminate outcome; never retry automatically and perform only read-only diagnosis/backup. Keep writes explicitly experimental. Do not intentionally interrupt the owner's only valuable unit; require a second or sacrificial VNW-V15 plus a separate approved recovery protocol for deliberate testing. | Offline sender and new-TXT integration tests now enforce the distinction and no-retry rule. Physical atomicity, rollback, and recovery remain unproven; R15 stays open and blocks any risk-free write claim or broad public write release. |
| R16 | Proprietary evidence, credentials, or private device data could be accidentally published through a source remote or a complete Git-history push. | Critical | Before every remote checkpoint, audit all tracked files and `git rev-list --objects --all`; reject original Sony software, ISO content, device backups, USB captures, raw live evidence, credentials, private information, generated output, and temporary artifacts. Keep the remote private only as an additional source/history backup, never as the sole evidence backup. Never force-push or upload excluded evidence. | Controlled for this sanitized remote: the candidate history contains no excluded evidence, the remote is private, and the initial commit is pushed. The original research history and bundle remain local-only; re-audit every future commit. |

## Immediate Risk Order

1. Preserve R3's narrow Milestone G live-smoke evidence without enabling a
   normal write control or generalizing beyond one root-level TXT case.
2. Apply R15 to every write design: distinguish safe pre-transfer cancellation
   from an indeterminate interruption after `0x101b` begins, never retry, and
   keep deliberate recovery testing off the only valuable unit.
3. Preserve R2's closed captured-fixture Milestone H gate in `b5bae4b` and
   `c8162c0`, while keeping H.1 blocked and parked pending new independent
   evidence. Do not request another capture automatically. Before any modern
   delete smoke, the constrained modern timestamp-preservation and supported
   fixed-state gates must be reviewed and a separate approval is required;
   accept only `0x0000`, do not retry missing/ambiguous/malformed/nonzero
   completion, and keep restore deferred. Physical interrupted-write recovery
   remains open.
4. Keep H.2 live eligibility unexecuted while its corrected offline structural
   gate remains limited to the supported model. The I7 stateful deletion
   observation closes only the one captured persisted-effect boundary; the
   modern model does not resolve legacy timestamp generation, request-4
   completion, or physical recovery. Do not request another capture
   automatically and do not authorize a modern delete.
5. Keep R14's batch queue disabled until single-item create/delete operations
   and every queued content type have individual proof.
7. Retain both completed constrained-write and narrow new-TXT live-smoke
   evidence and require fresh explicit authorization before every subsequent
   live hardware write.
8. Treat R11–R13 during the completed J.0–J.2 Library foundation and later
   J.3 device-aware planning. R10 remains outside the product entirely.

## Stop Conditions for Any Device Write

Do not start or continue a write when any of the following is true:

- no fresh complete backup has been verified;
- the device identity or current state differs from the authorized candidate;
- the target or resulting capacity is ambiguous;
- unsupported characters or unresolved metadata would be introduced;
- the user has not confirmed the exact selected operation;
- a disconnect, timeout, cancellation, or unexpected completion value occurs.

After a stop condition, preserve the error and current evidence, perform only
read-only detection/backup checks, and never automatically repeat the write.
If the stop occurs after `0x101b` begins, describe the device state as
indeterminate until a complete read-only backup can be obtained and assessed.

## H.2 isolated-delete runner checkpoint (2026-08-27)

The new unregistered `delete_smoke` support module is limited to one
owner-selected reachable root-level ordinary TXT record. It provides a
read-only eligible-target listing and a sealed, hash-bound preflight; it does
not select a target, include raw candidate bytes, or connect the normal CLI or
ttk application to deletion. Its optional execute phase requires a separate
owner approval, the exact delete phrase, fresh read-only revalidation, one
injected sender call at most, strict `0x0000` completion, and independent
post-operation read-back. The slice has **483 passing tests and three
intentional skips** and performed no hardware operation.

This reduces accidental integration risk but does not resolve R15: the live
adapter is not supplied or executed, and physical interrupted-write
atomicity/recovery remain unproven. A future preflight is not write
authorization; a separate explicit approval is still required for any live
delete transaction.

The owner-approved read-only preflight subsequently completed for
`root\\IC_TEST_01.txt`. It used a new complete backup and sealed the exact
device, backup, target, payload, candidate, fixed-state, transaction, path,
capacity, completion, and no-retry bindings. No `0x101b` request was issued and
no device change occurred. Raw artifacts remain external and the sanitized
preflight summary contains hashes and lengths only. The next boundary is a new
explicit owner approval for exactly one live delete; R15 physical atomicity and
recovery remain unproven.
