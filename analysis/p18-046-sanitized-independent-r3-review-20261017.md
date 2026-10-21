# P18-046 sanitized continuation — independent R3 review

Date: 2026-10-17 JST.
Reviewed exact implementation commit: `f2d0e8ec97b49926223654f8cdb47f0fd1c0d3b3`.
Sanitized integration base: `d344f1e59664f38ebb8c3a3219c72b6eea8f79cd`.
Branch: `task/P18-046-sanitized-root-bmp`.

**PASS for the host-only checkpoint. P0/P1/P2 = 0/0/0; no unresolved findings.**
No material correction round was needed. Physical outcome remains
**BLOCKED_BY_EXTERNAL_EVIDENCE**, not ready for an executable BMP placement or
Delete. This review authorizes no hardware operation, merge or publication.

## Independently inspected scope

Read the applicable AGENTS/WORKFLOW requirements, current status/capability and
risk boundaries, exact base-to-head diff, all added source/CLI/tests/fixture and
operator documents, relevant retained BMP candidate/authorization/sender/readback
and Device Library admission, root-TXT placement, folder-package construction,
and specifically cited native P8/P16 evidence reports. Executor reports served
as navigation; the checks below were independently reproduced.

The sole outgoing commit has the sanitized base as its direct parent. Its code
changes are limited to the retained offline BMP addition in delete_workflow,
the offline CLI and its tests. Root-TXT execution/admission, transport and
production safety code have no diff.

## Port equivalence and retained safety gates

Independently compared committed bytes against original reviewed
`93a437cd300eaed28b2290160e032de88e86501a`, without importing its objects or ancestry.
All four ported implementation/test/fixture files are identical:

| File | SHA-256 |
| --- | --- |
| src/infocarry/delete_workflow.py | `6a358caee2ae2bb545d8456aa0ada9dd86c13d4137fb334bbe49fb1cd16371ac` |
| scripts/prepare_root_bmp_delete.py | `8be17752b5dcc7c55e7086baf98ba6b303dd3e8eec689a1ac9089f9813867505` |
| tests/test_disposable_root_bmp_delete.py | `0a6e0548a055cdff512c2295770f732c519de8adc1db1c66a09987b36f9a499b` |
| analysis/p18-046-disposable-root-bmp-fixture-20261016.json | `358590bf59fb0d500f753ca13e38b9a1972f71ed93aae960182b140632b54033` |

All 131 tracked source/script files also match that reviewed original. This is
source equivalence, not a claim that the original ancestry is safe to publish.

The exact helper admits only VNW-V15, the unique exact disposable payload/name,
unread 0xe0 and selector 0x100. It delegates native geometry, survivors and
protected references to the existing builders. Persisted artifacts, eight-range
transaction and type-bound host binding are independently reconstructed on use;
readback requires complete verified objects and actual integer zero completion.
Historical preparation is explicitly unsuitable for physical execution.

The sender gate derives the extension from the parsed baseline rather than
mutable audit labels. Changing the authorization label to TXT cannot admit a
BMP. Device Library admits TXT only before opening a runtime. The new helper
and CLI supply neither a runtime nor an owner execution identity, claim,
marker, installation lock or live adapter. Their reports clearly identify host
preparation, with execution and physical authorization false.

## Native placement proof and operator proposal

Re-executed the archive census against actual preserved external files:
57 complete archives / 456 verified objects / 13 distinct complete states;
four explicitly synthetic paths excluded; zero verification errors and zero
ordinary root BMP records. Separately verified the final cleanup archive:
454 records, zero root BMP and 163 nested BMP, all with 16-byte prefixes.
Manifest hash: `5d7cce4275b0d745d8fc1744cd1d20c5fc1a623fcd77f0c985001cbbbe0bac6c`.
Dynamic hash: `6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`.
The actual final baseline refuses exact BMP preparation because the specimen is
absent; its nine-file hash tree is unchanged before/after the check.

These archives establish nested BMP storage only. P16 records a BMP inside a
new folder, including native survivor timestamp rewrites. Existing package
builders construct folder hierarchies; guarded root placement remains TXT-only.
None supplies an ordinary root-BMP placement envelope. A root candidate cannot
be justified by changing a TXT type/template or moving a folder leaf.

The new proposal correctly requires non-sending native Manager staging first:
verify actual root-import controls and exact one-file pending scope, then stop
if scope/byte identity cannot be established. This is necessary because cited
P8 evidence copied two records despite a single highlighted row. The proposal
does not pretend this unverified UI step is currently runnable. One physical
placement becomes reviewable only after that staging, fresh complete backup
and capacity/protected-state checks, and a separate simple owner approval.
Complete post-backup and captured native buffer where available must establish
the exact root form and sole logical addition; unexplained changes block reuse.
Native timestamp rewrites must be recorded, never guessed or normalized away.
A BMP live adapter, exact-head review and separate one-Delete approval remain
subsequent requirements. No genuine device transaction can be frozen now.

## Privacy and preservation

Re-executed the candidate-history and preservation audit. The one outgoing
commit is directly based on sanitized main. The removed private JSON path is
absent from every outgoing tree; known blob
`ef7e5a2d05ebdaf008a3c04380251e6a26d291ed` and original unsanitized BMP head
are absent from the isolated repository object store. All nine outgoing blobs
passed the bounded personal-path/credential-pattern and 1 MiB size audit;
author/committer emails are the established GitHub no-reply address. This
pattern audit is not a universal secret detector.

Primary P18-034: branch, HEAD, status and all 1,591 recorded tracked/untracked
file contents/symlinks unchanged. Original BMP checkout: branch, HEAD, status
and all 579 recorded file contents/symlinks unchanged. No original repository
or raw evidence was edited. Reviewed candidate working tree remained clean.

## Validation independently run

- Supported Python 3.12 environment; focused new disposable BMP suite:
  **13 passed**, 7.116 seconds.
- Full portable offline suite: **1,210 run / 1,205 passed / five established
  evidence skips**, 178.418 seconds, exit 0. Skip conditions were not changed;
  they concern missing stable capture-04, external P18-012/P17 inputs and
  local-research-only native ranges.
- All three changed Python files compile; base-to-head diff check passes.
- Independent file equivalence, full archive census, actual-baseline refusal,
  history/privacy audit and original-checkout preservation checks pass.

External reproduction records are in `/private/tmp/p18-046-continuation-audit/`:
`independent-focused.log`, `independent-full-suite.log`,
`independent-equivalence.json`, `placement-evidence-census.json`,
`actual-baseline-refusal.json`, `candidate-history-audit.json`, and preservation
reports. Private archive index entries remain external and are not reproduced.

Review performed zero real USB operations, hardware writes, real 0x101b,
production claim consumption, marker/global-lock mutations or automatic retries.
No production safety state was accessed. Fake transport tests are host evidence
only and do not establish physical completion or bus-level sender counts.

## Disposition

Accept this sanitized local host-only checkpoint with no P0/P1/P2 findings.
Keep BMP live/UI execution disabled and retain the exact native-root placement
blocker. Next meaningful external action is non-sending native Manager scope
staging; no physical write is ready for authorization until its control/path
proof and fresh backup are reviewed. No push or merge is authorized.
