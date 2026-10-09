# P18-042 follow-on Delete analysis — 2026-10-10

**HOST-ONLY INVESTIGATION. No wider capability admitted.** The smallest next
extension is one ordinary root-level BMP file, using the existing file
repacker, protected-state derivation and guarded operation framework. No
alternative sender, claim store, lock or authorization system is needed.

## Inputs and evidence boundary

Read-only input is the actual complete P18-041 post-delete backup preserved
outside Git. Its manifest SHA-256 is
`b6005c9dc85b74574cc6adea2d543f4db0c4c35d30b3d958e474bcd8e94e48d4`;
dynamic blob SHA-256 is
`6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`.
See the [physical closeout](phase-18-p18-041-physical-delete-closeout-20261010.md)
for its external archive location and hash inventory. Private names and
payloads are omitted here.

**Observed in this archive:** 454 serialized records, 75 reachable logical
directories (including root), 300 files: 136 TXT, 163 BMP and one other file.
There are four root TXT files, **zero root BMP files**, 132 nested TXT files
(38 at depth 2, 37 at depth 3, 57 at depth 4), and no logically empty
directories. All 163 BMP records have 16-byte native prefixes; 161 are unread
and two read. This census is storage evidence, not deletion behavior.

Relevant existing evidence is the
[two-case parent-marker matrix](phase-13-milestone-h2-parent-marker-two-case-matrix-20260826.md),
[offline hardening record](phase-13-milestone-h2-offline-delete-hardening-20260826.md),
[P18-041F calibration](phase-18-p18-041f-root-leaf-calibration-20261004.md),
and P18-041 physical closeout. The historical root-TXT cases establish
relation-based marker shortening and one-record metadata/content rebasing;
they do not establish directory/subtree marker-removal ownership. P18-041F's
referenced P18-041A/B branch names and external research checkout are absent
in this task checkout/environment; their original subtree records were not
independently inspected here. No additional subtree rule is inferred from
those references.

## Priority 1: root BMP

**Verified host behavior:** `backup_repack.delete_existing_file` is already
type-neutral for known ordinary files. `delete_model.build_one_txt_delete_model`
adds an explicit TXT admission gate and rejects BMP; the production Delete
gate stays closed for BMP. The parser exposes identical metadata/content
geometry for TXT/BMP, with their existing native-prefix lengths.

Synthetic valid 237×320 monochrome BMP experiments use the existing test
builders and pure repacker only. A 32-byte-prefix root BMP with one surviving
TXT sibling parses after deletion and preserves every surviving raw byte
except permitted pointers/child counts, plus exact native prefixes, payloads,
timestamps and checksum. A second 16-byte-prefix case matches the prefix
length observed in the actual BMP records: three → two records, 10,384 bytes
reclaimed; source SHA-256
`88b4ef42779054b03babcd8b3f5a8679f9b754a5d2ed0188199ad1700751b9f8`,
candidate SHA-256
`0c4cb643bb0ba35b6ac9544c11548ed5af008d78b0ab5ca5a3c48342f99c1463`.
No synthetic bytes are written to Git or used for owner approval.

The sibling-preservation case has five → four records and reclaims 10,400
bytes; source SHA-256
`143d669e76ce0712df149b11880569949126809c7ba1e3b37a095e51e6c9c61b`,
candidate SHA-256
`8a36e98fd46ce7da9de38cd0e9a776bcf7851be0091b8591f029e329d522c46f`.
One actual nested BMP also passes the pure structural and protected-state
derivation (454 → 453 records; candidate SHA-256
`ed2fafab35bce0aa1769829ab6466d62a8e3cd66a1717cd94a1dc6bf5b8c2bad`).
It is a host probe of a nested file, not root-BMP deletion evidence.

**Inferred engineering direction:** factor the existing one-file structural
invariants into a shared helper, retain exact TXT behavior, and add bounded
ordinary root-BMP admission only in an explicitly reviewed extension. Check
known read/unread flags, supported prefix geometry, non-overlapping aligned
content, exact target identity, protected-reference refusal, and complete
survivor preservation. Reuse the current frozen operation and independent
readback path. This investigation does not modify that code.

**Unknown physical behavior:** no root-BMP Delete before/post pair is available
here; nested BMP presence or synthetic success cannot establish it. Keep BMP
outside live admission until the future extension's required review and
separately authorized physical validation are complete.

## Priority 2: individual nested TXT

The existing pure TXT model already handles a nested leaf and preserves its
parent directory even when it becomes empty. Existing tests cover related
versus unrelated `..` markers, coincidental field values, pointer rebase,
alignment, overlap refusal and exact survivor bytes. The two-case historical
matrix supports the marker relation but supplies root-level physical deletes;
it does not make nested physical Delete proven.

**Verified actual-archive host result:** all **132 nested TXT files** pass
the existing pure model and an additional direct raw-survivor comparison
against the established pointer-only transformation. Every successful
candidate preserves exact survivor prefixes/payloads, serialized timestamps
and unknown metadata. Protected-state derivation passes for **127**; it
correctly refuses the other **five** because the target is referenced by
protected auxiliary state. No unexplained structural or auxiliary refusal
was observed. SHA-256 of the ordered newline-separated 132 candidate
hashes is `4967f3dd0a2405ded97a002725b201887f83bef33a351e7917af17595a4464df`.
The experiments reconstruct one independent candidate per selected file
from the same preserved source, without chaining operations or constructing
final transactions/authorizations. Nested UI admission, frozen selection
binding, depth and parent-marker validation would need a scoped future review;
physical nested-file deletion remains unproven.

## Priorities 3–4: empty directory and bounded subtree

**Verified host behavior:** removing the last TXT child in the existing
synthetic nested fixture produces a valid empty directory while retaining
its native `..` markers. The directory still has a marker-bearing child
table; logical emptiness does not imply a zero-byte table or a single
serialized record. The current pure file repacker rejects both ordinary
directory and root selections.

That synthetic empty-folder image has six serialized records, two reachable
logical directories, four serialized parent markers, and a 64-byte folder
child table. Its SHA-256 is
`ec1c181c1ba1f26b8d5b24f251366c063b6b6377c37ca0e8c6cd15fced78a32f`.

`DeviceLibraryDeletePlan` already computes an exact logical closure and
expected path delta with resolved/unreferenced auxiliary state, rejects
system/root/overlapping/stale selections, and remains host-only. A synthetic
folder-plus-file closure correctly removes two logical nodes and leaves
root. It constructs no raw candidate or transaction.

**Unresolved:** which serialized markers belong to the removed directory,
which outside-marker relations require adjustment, and how to remap a set of
removed metadata/content intervals while preserving all opaque bytes and
surviving auxiliary associations. Existing single-file code cannot resolve
these by repeated logical deletion; that would leave empty directories and
would not define directory marker removal. Do not implement a guessed
directory/subtree serializer merely to produce a checksum-valid image.
The smallest useful later directory investigation is one empty-directory
before/after native effect with complete marker mapping, rather than a
general recursive mutator.

## Validation and safety

Existing `test_delete_hardening.py` and `test_backup_repack.py`: **21 tests
passed**, no skips. The actual source archive remains unchanged. USB requests,
physical writes, production claim/marker/lock access or mutations, final
transactions and authorization construction: **0**. No production source,
capability gate or independent success decision was changed by this
investigation. All additional classes remain **NOT PHYSICALLY DEMONSTRATED**
and **NOT LIVE-ENABLED**.

Reproduction script and sanitized host results remain outside Git at
`/external/local-path` and
`/external/local-path`. No raw candidates were
saved. All probes completed; none are reported from an interrupted run.

## General root-TXT admission assessment

Additional executor host checks of all four surviving root TXT files in this
same preserved post-delete archive passed the existing pure structural model
and complete protected-state candidate derivation (4/4). No saved historical
output or private payload was substituted. External sanitized count report:
`/external/local-path`. Independent R3 assessed
this as host corroboration, not proof for arbitrary physical content/prefix
geometry, marker placement or auxiliary associations. It agreed to retain the
exact fixture gate. General root TXT remains prepared by existing host helpers
only and unavailable for GUI execution until scoped extension/validation.

## Authorized continuation: root-BMP structural model

The owner instructed “continue” after reviewed UI checkpoint `67d029b`.
`delete_model.build_one_root_bmp_delete_model` now exposes a pure host model
for exactly one ordinary root-level 237×320 uncompressed 1-bit BMP. The
existing one-TXT body is factored into a private shared one-file validator;
`build_one_txt_delete_model` still fixes admission to TXT and retains its
candidate/audit behavior. BMP uses the existing `validate_bmp_payload`, known
read/unread flags and native 16/32-byte prefixes. The common repacker/checks
prove sole path removal, every survivor record's permitted pointer changes,
exact payloads/prefixes/timestamps/unknown bytes and parsed checksum. Its audit
explicitly says `host_offline_not_live_enabled`; no complete fixed-state
transaction, authorization, sealed bundle, sender or Device Library gate is
added. Protected-state derivation is exercised independently in tests.

Nine new portable tests cover 12 first/middle/last × prefix × read-state
combinations, sole files/top-down images, invalid BMP headers and profiles,
nested/root/directory/identity rejection, unsupported native geometry/state,
overlap/ambiguity, before/after survivor auxiliary references and target
reference refusal, deterministic source preservation, and continued rejection
by existing TXT candidate and Device Library execution admission. All nine
pass; 89 existing Delete/model/state/exact-facade/UI regressions pass.
The full portable run passes **1,142 run / 1,139 passed / three established
skips**, 119.630s. Independent strong R3 review passes P0/P1/P2=0/0/0 at
`ba0d36c20385678a08f9c9854ef9e85097a7a72d`, with 107 focused tests and
273 old/new TXT candidate/audit comparisons across all actual 137 pre-delete
and 136 post-delete TXT files. Original exact physical candidate, transaction
and saved readback are unchanged. See the
[canonical continuation review](phase-18-p18-042-root-bmp-independent-r3-review-20261010.md).

This is IMPLEMENTED / TESTED OFFLINE only. It is not a complete runnable BMP
operation or physical evidence, and it does not change the exact TXT fixture
execution scope. No additional physical operation is authorized.

Continuation checkpoint: **COMPLETE for the bounded pure host BMP model**;
not a runnable BMP operation or hardware-ready full BMP workflow. No code
connects it to final transactions, authorization or Device Library execution.
The integrated exact TXT UI remains READY_FOR_HARDWARE_TEST, conditional on
new operation-specific owner authorization; all other class execution remains
unavailable. Final continuation closure changes documentation only.
