# P18-046 — sanitized-base root-BMP continuation

Date: 2026-10-17 JST. This record describes the sanitized-base continuation
checkpoint before the bounded placement extension below. Its former
`BLOCKED_BY_EXTERNAL_EVIDENCE` disposition was superseded by offline candidate
construction using the existing root-TXT serializer and observed P16 BMP record.
The initial review of that extension found two corrections, addressed in one
round. The exact-head correction review passed with P0/P1/P2=0/0/0; the exact
disposable placement is `READY_FOR_HARDWARE_TEST` subject to fresh live
preflight and separate owner authorization. No push, merge, or physical
operation occurred.

## Integration and equivalence

The new isolated repository is based on freshly fetched published main
`d344f1e59664f38ebb8c3a3219c72b6eea8f79cd`. Branch:
`task/P18-046-sanitized-root-bmp`. No old branch was fetched, merged, rebased
or cherry-picked. Only an audited file patch from original `f232f62..93a437c`
was applied. The original BMP branch remains evidence, not integration history.

Four files are byte-identical to original reviewed `93a437c`:
`src/infocarry/delete_workflow.py`, `scripts/prepare_root_bmp_delete.py`,
`tests/test_disposable_root_bmp_delete.py`, and the disposable fixture manifest.
All other application source/scripts/tests retain sanitized-base bytes. The
conditional runbook is ported unchanged; new proposal/status/matrix text records
the current evidence boundary. Original runtime smoke evidence is historical;
this continuation does not claim a new packaged runtime or physical run.

The retained implementation admits only the exact unread `0xe0`, selector
`0x100`/16-byte-prefix, unique ordinary root specimen with supported protected
state and unreferenced target. It delegates structural/survivor checks,
protected-state derivation, eight ranges, immutable type-bound host binding and
complete readback to existing reviewed code. No live bundle, owner identity,
BMP UI admission, sender or production safety-state access is added. Root-TXT
experimental admission and existing guarded transfer architecture are unchanged.

## Placement evidence and smallest next action

The independently re-inspected preserved native corpus has no ordinary root
BMP: **57 complete archives / 456 verified objects / 13 distinct complete
states**, including duplicate snapshots; four explicitly fake archive paths were
excluded. There were zero verification errors. See the aggregate external census. The saved final-cleanup backup manifest
is `5d7cce4275b0d745d8fc1744cd1d20c5fc1a623fcd77f0c985001cbbbe0bac6c`,
dynamic blob `6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`.
It has 454 records, zero root BMP and 163 nested BMP, all 16-byte-prefix.
This is saved-state evidence, not a current device observation. The exact BMP
helper independently refuses this actual backup because the target is absent;
all nine source archive files retain the same hash tree before/after.

| Evidence / implementation | What it establishes | Missing root proof |
| --- | --- | --- |
| P16 native capture 01 and modern mixed-package smoke | Exact BMP payload/16-prefix inside a new root folder | Ordinary root BMP placement, record/prefix/state and sole-add effect |
| P18-039 flat / P18-040 nested transfer | Their exact reviewed folder hierarchies | No root-leaf placement envelope |
| P18-041H2 / P18-044 / P18-045 root placement | Guarded TXT-only candidate and physical TXT additions | No BMP template/admission/native root record |
| P18-042/043/046 BMP model and host binding | Synthetic root-BMP candidate/transaction and independent offline readback | No physical placement or Delete behavior |

At this earlier checkpoint, the root-TXT facade called
`build_new_root_txt_add` and rejected other fixtures, so no modern root-BMP
placement code had yet been prepared. The current extension is documented in
the [bounded native placement procedure](p18-046-native-root-bmp-placement-proposal-20261017.md).
It copies the complete observed BMP record template into the same root-child
serializer, with opaque BMP fields retained and no new format field inferred.

Legacy staging is optional and was not used to justify this modern candidate.
The prior UTM capture attempt exposed no state, so it supplies no observation.
The bounded modern operation instead requires a fresh complete backup/capacity,
an exact compatible BMP template, the immutable fixture, one separate owner
approval, and complete post-backup. No fingerprint for the owner to type.

The host fixture was generated privately and its 10,302-byte/hash identity
verified. A live candidate/transaction bundle is prepared only at a fresh
hardware preflight against the current verified backup and native capacity;
offline synthetic candidates do not substitute for a device backup or consume
production safety state.

## Privacy, preservation and execution boundary

Publication remains complete. The private timestamp JSON tree path is absent
from all new outgoing commit trees; known removed blob
`ef7e5a2d05ebdaf008a3c04380251e6a26d291ed` and original unsanitized BMP head
are absent from this isolated repository. The outgoing audit checks every
reachable new blob for personal paths, common credential patterns and size
above 1 MiB, plus no-reply commit emails. This is a bounded audit, not a guarantee
against every possible secret form. Raw backups, candidate/range binaries,
record inventories, private library metadata and original proprietary software
remain outside Git. Only counts and existing evidence hashes are reported here.

Before/after hash inventories cover the primary P18-034 checkout's 1,591
tracked/untracked paths and original BMP checkout's 579 paths, branch, HEAD,
status, contents and symlink targets. No original repository mutation was used.
Production claims, sender markers and global lock were not accessed or changed.
Real USB operations, physical writes, real `0x101b`, production claim consumption,
production marker mutations, global-lock mutations and automatic retries: **0**.
Offline fake-transport tests do not count as physical operations or physical proof.

## Validation and independent exact-head review packet

- Python 3.12.14, retained supported environment. Focused disposable BMP suite:
  **13 passed**. Compile and diff checks pass.
- Full portable suite: **1,210 run / 1,205 passed / five established evidence
  skips**, 155.210 seconds, exit 0. The skips are two missing stable capture-04
  cases, two external P18-012/P17 evidence cases, and local-research-only native
  ranges. No test skip condition was changed. One preliminary system-runtime
  attempt lacked PyUSB; the complete run used the retained supported environment.
- Earlier sanitized-base host-only R3: **PASS, P0/P1/P2=0/0/0** at
  `f2d0e8ec97b49926223654f8cdb47f0fd1c0d3b3`; it did not review root-BMP
  placement reachability. Its findings and full-suite result are retained in
  the [sanitized-port review](p18-046-sanitized-independent-r3-review-20261017.md).
- The later exact-head root-BMP review, initial findings, one correction round,
  and final test results are recorded in the
  [root-BMP placement R3 report](p18-046-root-bmp-placement-r3-review-20261017.md).

Review must independently inspect evidence rather than trust this navigation.
No USB or production safety-state access is permitted in review. Keep corrections
within the existing two-material-round budget. External validation, census,
fixture and audit results are under `/private/tmp/p18-046-continuation-audit/`;
raw hardware evidence remains at its preserved locations outside this repository.
See the [sanitized-port review](p18-046-sanitized-independent-r3-review-20261017.md)
and [root-BMP placement review](p18-046-root-bmp-placement-r3-review-20261017.md).
The closure adds documentation only; no source/test/fixture changes follow the
reviewed implementation commit. Final closure-head acknowledgment and repeated
privacy/preservation audits remain in the external audit directory.
