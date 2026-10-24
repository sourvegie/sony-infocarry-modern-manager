# P18-049 placement template provenance investigation

Date: 2026-10-25, Asia/Tokyo. Read-only forensic work against preserved artifacts and an exact exported source snapshot of `4ba16dca6edafd0bfe8d4721b9e1ed4ee6fca358`. No USB access, production safety-state access, device write, source edit, or original-evidence edit occurred. All new files remain in this separate private forensic directory.

## Finding

The discrepancy is real and predates execution. The immutable approved task envelope names source template `0x1c0`. The original read-only sealed preparation already used `0x7180`; the later actual placement used that same `0x7180` source. The original bundle's stored candidate-audit digest matches a reconstructed `0x7180` audit and fails a reconstructed `0x1c0` audit. This is an original envelope-versus-bundle consistency failure, rather than a proven source substitution between the original sealed preparation and actual placement.

The source records are different files. They have different native paths and parents, names, metadata hashes, content pointers, payload lengths, payload bytes/hashes, timestamps, and allocation padding. They must not be described as equivalent source payloads. Private JSON records the complete raw records, names, paths, and payload hashes; personal source names/content are omitted here.

| Source attribute | Envelope source `0x1c0` | Sealed/executed source `0x7180` |
| --- | --- | --- |
| Parent depth | Device root | Existing nested folder |
| Source payload length | 53 bytes | 8,850 bytes |
| Source timestamp | 1788093256 (`0x6a942348`) | 1788093258 (`0x6a94234a`) |
| Source content pointer | `0x0` | `0x212608` |
| Name, raw record, payload | Distinct | Distinct |
| Copied flag/extension | `e0747874` | `e0747874` |
| Copied opaque word | `ffffffff` | `ffffffff` |
| Copied selector | `00000200` | `00000200` |
| Copied native prefix | Same exact 32 bytes | Same exact 32 bytes |

## Why final transaction bytes match

The existing `fresh_new_allocation=True` path clones a raw source record but overwrites bytes `0x04..0x0f` with the new content pointer, exact fixture payload length, and frozen new-record timestamp. It overwrites the entire 40-byte native name field at `0x18..0x3f` with the fixture stem and NUL fill. Only source record bytes `0x00..0x03` (flag/extension) and `0x10..0x17` (opaque/selector) survive. All those copied bytes match between these two source records.

The new content allocation copies the source's exact 32-byte native prefix, then writes the reviewed 34-byte fixture and two zero alignment bytes. It does not copy the source payload, source payload length, or source padding. Both source prefixes match exactly, SHA-256 `d0bcc6bc85dc36cdc1ad3882952c5d3d4414869c0bdd75b3b58ba28a32deb92a`. The frozen timestamp is 1792768350. Thus every difference in these two source identities is either overwritten or belongs to source payload/padding that is never copied. The original source files themselves survive unchanged apart from established metadata/content pointer rebasing.

An independent serializer, implemented in the new forensic script without calling the add/duplicate/repack builder, reconstructed the native blob from baseline records, the exact child-table insertion at `0x880`, content insertion `0x2a18`, preserved old content, copied fields, and known header/checksum rules. A separate direct fixed-state pointer transformation constructed all eight transaction ranges. Four combinations were checked: both templates against the original preparation baseline and against the actual placement baseline. Every candidate byte and every transaction range matched the corresponding production builder and preserved artifacts, not only the target payload hash.

All four produce candidate SHA-256 `a0d28fbbd8ce6bd354df9f91ccf0088c045f84053178e9f4523c6de615933475` and transaction SHA-256 `cfb0950d09b19458d7a6dc1a8c9d7203e7db08f8097f1845d00088db6ac25560`.

## Structural and protected-state effect

The independent nested inverse verifier accepts the reconstructed placement against the exact original baseline, proving survivor metadata/marker order and ownership, parent and sibling preservation, original content/prefix/padding bytes, timestamps, and opaque header/trailer bytes under the existing reviewed model. Removing only the new target reconstructs the original dynamic blob byte-for-byte. The added allocation is 68 bytes plus one 64-byte record: growth 132 bytes, total candidate 2,210,564 bytes.

Direct fixed-state reconstruction rebases seven established display-history references and one bookmark record pointer by 64 bytes. Counted state, opaque bookmark values and unused tails stay exact. The established auxiliary-state verifier independently agrees. Starting from the actual complete native post-placement backup, offline inverse deletion returns all five protected fixed-state blocks exactly to the original baseline. These results refute a native structural or protected-state difference caused by choosing these two particular templates. They do not weaken template identity as an authorization requirement.

The actual native post-placement dynamic blob matches the common candidate byte-for-byte, and all five native fixed-state objects match the common transaction. The complete backup verifier also validates all eight captured objects against their own manifests. Separately, the two payload-dependent native objects were checked: each probe equals the associated blob's first 64 bytes; `0x0024`'s first four bytes equal that blob's length and its remaining 60 bytes stay unchanged. These are observed relations for these two archives, not newly generalized format rules.

The original simulator copied `0x0024` and probe bytes unchanged. Its all-eight inverse restoration is a host replay and does not establish those two objects' actual physical post-placement prediction. Actual post-placement evidence supplies their values. Physical post-Delete all-eight restoration is still unperformed and must be verified against a fresh complete native backup after any separately approved deletion.

## Binding effect and cause

Raw state/capacity/fixture/new timestamp/candidate/transaction agree between original and actual preparation. Archive paths, capture manifests/provenance, audit digests, authorization digests and outer bundle/seal identities differ. The approved task allowed just-in-time operation identities, so different outer bundle hashes alone do not prove a defect. However, its explicit template field was not reconciled against the original sealed preparation or actual bundle audit.

The preparation script selects the first eligible file in serialized metadata `parsed.records` order, which is `0x1c0`. The guarded facade selects the first eligible file in reachable `parsed.paths` traversal order, which is `0x7180`. Identical copied native signatures let both paths build identical output. Candidate/transaction hashes cannot detect this semantic provenance difference; an explicit canonical source identity and comparison are required.

The original approval remains stopped. Successful native placement and identical output bytes do not retroactively approve inconsistent provenance, permit Delete, or change the preserved STOP record. This investigation grants no continuation authority. Any deletion-only approval must describe the existing placed target and fresh state, preserve this history, and permit no placement retry, cleanup, or extra write.

## Anchors and preservation

- Original envelope: `eae6909886fbbfc10ab2e21d7e773c71ea9624ab1843f837960d7466648200a5`.
- Original read-only bundle: `b2b71bb84f5e8db58f7afe3bb05db1b6e949bd649574d134d2c5d524dff736d8`.
- Actual placement bundle: `f37d3d09dfe0de989a033d21f63be6f1adb0895ba41bda76ed0692250d91ba7f`.
- Actual result: `be977c0ab9fd97dd49c43d414ce0a0fe0c72d96714080fb7a76aec27efab450b`.
- 103 original evidence files were hashed before and after investigation; all remained byte-identical. `original-file-anchors-before.json` and `original-file-anchors-after.json` contain full private path/digest anchors.
- `private-template-identities.json`, `private-independent-reconstruction.json`, and `private-field-impact-and-native-readback.json` contain detailed source identities, per-variant audit/hash checks, exact native fields, independent serializer geometry, pointer changes, and native readback verification.
- `private-native-derived-object-check.json` documents separately checked payload-dependent native-object relations and replay limits.

Disposition: structural/native placement checks PASS; original task provenance consistency FAIL; no new physical operation or continuation authorized.

## Correction and deletion-only preparation

The later engineering correction reuses one selector in the existing placement
facade and offline preparer, preserving the facade's established traversal.
Full source offset/path/raw-record/payload/prefix/copied-field hashes are bound
separately from native candidate hashes. A regression uses distinct source
identities that generate identical transaction bytes, then requires provenance
mismatches to fail explicitly.

The remaining operation is one Delete of the existing fixture; no placement
is repeated. A new task envelope must bind the current complete native state to
the independently verified actual placement, and bind restoration to all eight
original objects. It names no insertion template: Delete derives only from the
exact current target and verified archive. The existing Delete bundle seals the
restoration hashes. The existing Device Library service requires the immutable
one-write task binding before owner acceptance. Canonical readback compares all
eight freshly verified native hashes with restoration before terminal success;
auxiliary response/probe mismatches fail under the existing lock/no-retry path.
No new USB, sender, persistence or recovery pipeline is introduced.

Original evidence, approval, envelope and STOP records remain unchanged. The
separate correction record resolves the cause for a new reviewed task; it does
not retroactively validate the old envelope or reuse its unused second write.
The next scope requires its own single deletion-only owner approval. Ordinary
nested Delete remains disabled. No physical write, placement, push or merge is
authorized or performed by this resolution checkpoint.
