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
green on PR [#67](https://github.com/sourvegie/sony-infocarry-modern-manager/pull/67):
macOS and Windows Python 3.12 offline suites, Apple Silicon macOS package,
and Windows x64 package all passed. The PR remains unmerged. The final PR
documentation tip is the final branch head reported in the milestone
handoff; the code-bearing reviewed head remains the SHA above.

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
independent review and package/CI validation. Owner authorization is still
required for any later hardware work. This record is not itself an
authorization.

## Follow-up: macOS existing-directory picker gate

The exact pre-fix macOS build reproduced the reported native-panel failure:
after the existing P18-039 root folder was selected, the macOS `Choose` button
remained disabled. The source used `tkinter.filedialog.askdirectory()` without
`mustexist=True` for both source-folder actions. On macOS, Tk's
`tk_chooseDirectory` command defaults `mustexist` to false and enables native
directory creation when that option is false. That is the wrong native-panel
mode for an existing source-directory import and caused the observed gate on
this host.

The correction passes `mustexist=True` to both folder pickers. It changes no
transfer bounds, candidate construction, authorization, persistence logic,
sender, USB, or hardware-facing behavior. A focused regression test asserts
both picker calls retain the option.

Host-only validation after the correction:

- The rebuilt exact checkout artifact was opened in the native macOS panel;
  the preserved `IC_P18_039_5LEAF_20260925_01` folder displayed its five
  direct leaves and `Choose` was enabled. The choice was exercised without
  entering transfer or device code.
- The packaged smoke passed with the Add controls enabled, host-only transfer
  created, guarded send disabled, and physical counters all zero
  (`device_enumeration_calls=0`, `sender_calls=0`, `real_0x101b=0`,
  `claims_consumed=0`).
- The focused desktop suite passed 42/42 and the full portable suite passed
  1,014 tests with 3 intentional skips. `git diff --check` passed.
- The one catalog-only import created for the UI demonstration was removed by
  restoring the verified pre-demo catalog snapshot; the catalog content hash
  now matches its prior snapshot. No device write, `0x101b`, claim
  consumption, sender activity, or hardware mutation occurred.

This remains a host/UI correction only. The P18-039 disposition stays
`READY_FOR_HARDWARE_TEST`; no new hardware authorization or executable
hardware-facing risk was introduced.

## Physical evidence review — 2026-09-28

The owner reported the Manager UI message “Transfer complete — content verified
on the InfoCarry.” That message prompted inspection; it is not the basis of
this result. The actual terminal record is the excluded external evidence at
`~/Library/Application Support/SonyInfoCarryModernManager/Evidence/Library Transfer Operations/p17-017-attempt-ef18b96b487d4ba99a858e4fb3635f5a/`.
Its `result-manifest-0001.json` has SHA-256
`c22fb9672268cc03fa6a628901e2edae41ab6cc4dd4e990a06c608334f0057aa`.
The paired preflight is `ui-preflight-20260928-204148-599694` in the same
external evidence namespace. These complete backup and operation files remain
outside Git; this section contains only sanitized identities and conclusions.

### Actual terminal and safety evidence

- The production result audit says `state=readback_verified`,
  `usb_transmission_performed=true`, `device_changing_operation_performed=true`,
  `workflow.sender_calls=1`, one `single_0x101b_transaction` step, native
  completion `0x0000`, and `automatic_retry_allowed=false`. Thus the Manager
  records one real sender/`0x101b` operation and zero retries. There is no
  separate external USB bus capture for an independently measured packet count.
- The complete before and after backups each contain eight objects and all
  object lengths and SHA-256 hashes match their manifests. The post-backup
  manifest SHA-256 is
  `5a62df773befe6684c652a278c50ce098b359e100aecced4176b79cf94ee642c`;
  the post-backup blob SHA-256 is
  `60f664f4a2a37b1b89f377fa83bef9e8bc8d14a482361b821314f812d9c1b106`.
  The Manager's independent readback verifier reports `success=true`,
  `ordered_children_verified=true`, `shared_path_count=360`,
  `shared_payloads_unchanged=true`, `shared_timestamps_unchanged=true`,
  `fixed_state_exact=true`, and no removed paths. Display-history and bookmark
  references were semantically rebased as expected; opaque bookmark values
  and unrelated state were preserved under the reviewed policy.
- Readback confirms the new target
  `root\IC_P18_039_FLAT_20260925_01` with exactly these ordered direct leaves:
  `01-intro.txt`, `02-page-a.bmp`, `03-middle.txt`, `04-page-b.bmp`,
  `05-ending.txt`. Their prepared payload SHA-256 values, in that order, are
  `d16567039a003110d246cc6a0a4d0b2042efa9f2240485f6a5facbb09c00dcb1`,
  `f795a8e1466c3988b804f344645a6208bdcfa27e9d51d8b314c99d9a5973aadd`,
  `0323580a5e02206cc0b06d85744a8ef78b449e30d184cef3867152ca4792671a`,
  `f795a8e1466c3988b804f344645a6208bdcfa27e9d51d8b314c99d9a5973aadd`,
  `a31b66d8b27676dc0af07d32ba4d17b90c54ffa39f406c37a9475672e9e46eec`.
- The executed claim `815429097814474a97374042c8bff6fd` is durably
  `consumed`. The sender marker started `in_flight`, was resolved as
  `verified_terminal_success` by `sender-marker-resolution-0001.json`, and
  the claim database now has zero active sender markers. The installation-wide
  indeterminate-write lock is `cleared`.

### Material identity discrepancy and disposition

The frozen `_02` Manager executable currently hashes to the requested
`46954025f3ffe119263377a01d59d8e0bfad2ba81172d5782dbf994df8d76b00`;
its stated source commit is `397f29d5c741772674ec445843a7af33f9772e8c`.
However, the executed terminal result is bound to operation
`vnw-v15-library-operation-8d9016888b3f8451ecf8bc1865c6d40e648a0d11c47c6567095133ef1736b55a`,
candidate `60f664f4a2a37b1b89f377fa83bef9e8bc8d14a482361b821314f812d9c1b106`,
transaction `bab3787af7de707aba1f54c1f1b1afb88b6853713411265a628f26425878b879`,
and preflight seal
`cec5fa1477e9529b7e934b9b39e6449c39bc7453b358727ca5597153f25352cc`.
The fresh preflight uses a different record timestamp and operation binding,
although the selected target, ordered leaf names, prepared manifest identity,
and five payload hashes match the frozen shape.

The specified frozen operation
`vnw-v15-library-operation-732d10fb442fb463c1907461c5e538317bc8869958c5acb068923185076c67b5`,
candidate `86eee55cecdadb6bb57dc295adeb109a2dd08d9ad80b827abfaf0b2a33ffb1a4`,
transaction `e52b021275b7a35bf675ed35f1adc82f5d081232c6edfc4f712eec8684524ab3`,
and seal `94ba5bd223c0751a4f715a13d829c45d79629b02b01aacb295368515abe2ad8d`
appear only in the 2026-09-27 read-only preflight. Its seal has no consumed
claim and there is no matching terminal result. The later terminal result
cannot be relabeled as that exact frozen operation.

**Outcome:** physical transfer/readback for the specific five-leaf target and
payload is **SUCCESS**, but closure against the exact approved frozen
transaction is **FAILURE / ESCALATION_REQUIRED**. A material authorization
identity discrepancy needs owner/PM disposition before P18-039 can be marked
`COMPLETE`, declared merge-ready, or promoted in `CAPABILITY_MATRIX.md`.
This does not authorize a repeat write. The generalized 1–8-leaf host bounds
remain host bounds; VNW-V10, nesting, overwrite/merge, deletion, restore,
multipackage, and arbitrary hierarchy remain outside this validation.

Closure validation used the supported Python 3.12 runtime: 63 focused
live-adapter/claim-store tests passed; the full portable suite passed 1,014
tests with 3 established skips. `compileall` and `git diff --check` passed.
An independent R3 evidence and documentation review found P0=0, P1=0, P2=0
additional findings and confirmed the unresolved identity mismatch above as
a material closure blocker. No further hardware write or read was performed
during this review.

## Authorization identity mismatch investigation — 2026-09-29

### Field-by-field comparison and first semantic divergence

The authorized `ui-preflight-20260927-222840-976819` bundle and executed
`ui-preflight-20260928-204148-599694` bundle agree on the Sony VNW-V15
identity `0x054c:0x001e`, native capacity-response bytes/hash, semantic
baseline-state identity and backup blob, target absence, prepared-package
manifest bytes, target name, five ordered leaf names/kinds/payload hashes,
fixed/auxiliary-state inputs, expected post-operation delta, and safety policy.

The fresh backup manifest byte hash changed from `09556361…` to `11b237a3…`
because a new complete backup recorded new archive/receipt times; its device
blob and semantic state identity remained unchanged. The staged catalog hash
and Library binding also changed because the new operation-owned staging root
and observation time were recorded. Those are provenance/binding differences,
not device-content or prepared-payload changes.

The first content-affecting candidate input divergence is
`new_record_timestamp_be32`: `1790515721` (`0x6ab91a09`) became `1790595708`
(`0x6aba527c`). The production provider supplies current Unix time whenever
`refresh_live_preflight()` constructs a candidate. Binary comparison shows
the two 2,188,536-byte candidates differ in 24 bytes: three checksum bytes and
three changed low-order timestamp bytes in each of the seven newly inserted
records. No other candidate bytes differ. That yields candidate
`86eee55c…` → `60f664f4…` and transaction `e52b0212…` → `bab3787a…`.
The authorization hash and core preflight seal consequently changed. The
outer seal also binds the fresh Library/provenance artifacts; operation ID is
derived from that outer seal, so it changed from `732d10fb…` to `8d901688…`.

The `8d901688…` operation was therefore created by the final fresh preflight
immediately before the physical run. It was not a mutation of the frozen
`732d10fb…` operation and the latter was not executed.

### Root cause and authorization gap

Fresh-evidence rebinding is expected: each fresh backup, operation-owned stage,
timestamped candidate, authorization, and seal intentionally receives a new
identity. The defect was allowing that newly created identity to inherit
authorization procedurally. The external owner authorization was never a
typed input to the Manager. In the no-binding production path,
`LibraryTransferOperationIntent.authorize()` accepted only the target-derived
phrase `ADD <target> ONCE`. The ordinary Confirm Transfer OK supplied that
phrase immediately before coordinator entry, creating an authorized binding
for whichever fresh preflight was current. No comparison existed against the
externally authorized operation ID, candidate SHA, transaction SHA, or seals.
Thus software enforced internal consistency for the new operation, while the
owner-authorized frozen identity existed only in operating procedure.

### Narrow correction

`OwnerAuthorizedOperationIdentity` now projects the complete sealed operation:
operation ID, full bundle SHA-256, VNW-V15 identity, semantic baseline identity,
capacity response, candidate, transaction, authorization hash, and core/outer
preflight seals. The bundle hash covers every remaining bound bundle field and
artifact. After fresh preflight, the Manager displays these exact identifiers
and requires a separate exact approval phrase derived from the complete
identity. It shows the full fingerprint for the post-preflight authorization
handoff but deliberately does not display or supply the accepted phrase;
that phrase must be supplied separately by the owner. Ordinary Confirm
Transfer OK remains the final transaction consent
but cannot create owner identity approval. The execution facade compares the
stored approval with the operation presented for execution before it creates
an executable binding or enters the coordinator. Missing or changed approval
clears the prepared operation and stops before claim consumption, sender-marker
creation, or sender entry. A new preflight or adopted operation clears any
previous approval. The canonical coordinator, USB transport, sender, retry,
completion, backup, readback, marker, and lock behavior are unchanged.

Regression coverage changes the approved baseline, candidate, transaction,
and operation ID independently and proves that every mismatch stops with zero
claims, zero markers, zero backend/sender calls, and no lock mutation. A
separate regression proves normal UI confirmation cannot substitute for exact
owner identity approval. Existing success coverage now supplies matching exact
approval and still reaches one guarded `readback_verified` transaction.

Disposition remains `P18-039 = OPEN — PHYSICAL TRANSFER VERIFIED,
AUTHORIZATION IDENTITY MISMATCH`. `CAPABILITY_MATRIX.md` remains unpromoted.
The correction is host-verifiable and changes only the pre-sender authorization
gate. Another physical write is not needed to establish the fixed comparison:
host tests can prove all mismatches stop before the claim/sender seam and that
the matching identity reaches the existing fake guarded path. Any future live
validation would still require a new operation-specific owner authorization;
it should be considered only if the owner wants end-to-end UI evidence of the
new two-step approval UX, not as a prerequisite for accepting the root-cause
or pre-sender fix.

This is an identity-enforcement control, not local user authentication. The
software proves that the separately supplied approval matches the exact bundle
presented for execution. Establishing that the human or channel supplying the
phrase is the owner remains part of the approved operating procedure unless a
future task introduces a separately provisioned trusted signing key or account
identity. The Manager no longer makes procedural approval transferable to a
new identity merely by displaying an OK dialog or its expected approval phrase.

The new external-owner identity comparison is intentionally at
`LibraryTransferExecutionFacade.execute_once()`, the sole production Manager
entry to the guarded coordinator. Lower-level experimental/test APIs retain
their existing internal binding and coordinator checks and are not claimed to
authenticate or ingest external owner approval. No other production caller
reaches those lower-level entry points.

Host validation passed 138 focused execution/UI/runtime/live-adapter tests and
the full portable suite passed 1,016 tests with 3 established skips. After the
bounded review correction, 79 focused execution/UI tests and 42 desktop tests
passed; `compileall` and `git diff --check` passed. Independent strong R3
re-review of exact code/documentation head
`07557b9ca837d7fac77572b181dfab245da9999c` found P0=0, P1=0, P2=0 and
required no further correction. No USB request, claim consumption, sender
entry, `0x101b`, hardware retry, or other device access occurred during this
investigation.

## Final closure disposition — 2026-09-30

The owner directed final closure and merge of the corrected P18-039 branch.
This supersedes the earlier OPEN disposition; it does not revise the historical
fact that the physical run used `8d901688…` / `60f664f4…` / `bab3787a…`
instead of the earlier authorized frozen `732d10fb…` / `86eee55c…` /
`e52b0212…`. Fresh preflight rebinding caused the identity change; allowing
ordinary OK to serve as external owner approval was the software defect. The
separate post-preflight exact-identity approval gate resolves that defect for
future execution. It was verified by host regressions and independent R3
review; no second physical write is required to prove a pre-sender comparison.

The preserved 2026-09-28 terminal evidence proves one actual five-leaf VNW-V15
transfer for `root\IC_P18_039_FLAT_20260925_01`: one sender call, one real
`0x101b`, zero retries, native completion `0x0000`, complete post-transfer
backup, independent `readback_verified`, the five ordered TXT/BMP/TXT/BMP/TXT
leaves and exact payloads, and preservation of shared/unrelated state. The
executed claim is consumed, its marker is resolved, and the installation-wide
indeterminate-write lock is clear. It does not prove the whole 1–8 flat
envelope, other payloads/targets, nesting, overwrite/merge, deletion, restore,
multipackage transfer, arbitrary hierarchy, or VNW-V10.

P18-039 is `COMPLETE`. Final documentation-head tests and PR CI are required
as the merge gate. The reviewed code-bearing head is
`07557b9ca837d7fac77572b181dfab245da9999c`, with independent R3 findings
P0=0, P1=0, P2=0. The corrected checkpoint
`10bbbd6c2b61b2350e2cb769560e8fafb538d76c` adds only documentation.
No hardware write is authorized or performed in this closure.
