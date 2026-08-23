# Milestone E — genuinely new TXT evidence matrix

Date: 2026-08-22
Status: **Evidence audit complete; stable evidence preservation complete;
controlled owner capture complete; Milestone E evidence gate closed on
2026-08-22.** Clean capture 04 proves one genuinely new root-level TXT device
record, exact native range-5/range-8 to post-add blob equivalence, complete
before/after backups, independently hashed Manager snapshots, unchanged
observed Manager-local sidecars, and no unrelated shared payload changes.
Remaining state-rebasing, fail-closed capacity, and checked completion work is
explicitly carried into Milestone F.

This is a read-only audit of the preserved Phase 7/8 notes, manager fixtures,
native SnoopyPro captures, complete backups, and offline exports. The original
binary evidence remains outside this checkout and was not modified. The
separate `InfoCarry-Toolkit` checkout was used only as a read-only evidence
mirror; no package or import path from it was used.

## Stable evidence preservation

The five requested mirror roots were copied, never moved, renamed, normalized,
or deleted, to:

```text
${EVIDENCE_ROOT}/phase-12-audit-source-20260822/analysis/
```

The complete file-level manifest is:

```text
${EVIDENCE_ROOT}/phase-12-audit-source-20260822/manifest.json
```

It contains source path, destination path, size, and SHA-256 for all 390 copied
files (11,552,532 bytes). Every source/destination size and SHA-256 matched
before this matrix was updated. The manifest SHA-256 is
`5a4093e7b641ce61c1af8acc478dd4ca6168ba5d1d039105a62b22504f9dc157`. The
tracked locator and verification record is
`analysis/phase-12-evidence-manifest-2026-08-22.json`; the raw evidence and
full manifest are intentionally not in the `modern-client` Git repository.

Stable paths for the mirrored evidence used below are:

- Pre-add backup: `${EVIDENCE_ROOT}/phase-12-audit-source-20260822/analysis/phase-8-live-before-1/`
- Post-add backup: `${EVIDENCE_ROOT}/phase-12-audit-source-20260822/analysis/phase-8-live-after-4/`
- Candidate ranges: `${EVIDENCE_ROOT}/phase-12-audit-source-20260822/analysis/phase-8-candidate-2/` and `${EVIDENCE_ROOT}/phase-12-audit-source-20260822/analysis/phase-8-candidate-3/`
- Native export and decoded files: `${EVIDENCE_ROOT}/phase-12-audit-source-20260822/analysis/phase-9-export-check-1/`

## Evidence identity

The strongest existing candidate is manager test 4:

- Baseline capture: `${RESEARCH_ROOT}/usbsnifferlogs/03-manager-test/00-read-baseline.usblog`, 2,318,627 bytes, SHA-256 `2018cc0ef9fca5db8e760251244299a4a11ea45c46e3903b85e087658a47c1ec`; the canonical parser finds no `0x101b` transaction.
- Selected-send capture: `${RESEARCH_ROOT}/usbsnifferlogs/03-manager-test/01-selected-send.usblog`, 4,621,665 bytes, SHA-256 `526b7864dbad26c7290faea7f77fe6cade35dfd4b0c1997b33ee8b7c1fe41cef`; the canonical parser finds one complete transaction at `0x239d17`.
- Pre-add complete backup: stable `phase-8-live-before-1/` path above, device `0x054c:0x001e`, 8 objects, dynamic blob 2,063,788 bytes, SHA-256 `51fb612e78369170feb1851c644f498350ab387a23722977168f862988036f11`.
- Post-add complete backup: stable `phase-8-live-after-4/` path above, device `0x054c:0x001e`, 8 objects, dynamic blob 2,063,928 bytes, SHA-256 `c86f5523565da644995c5a2c47ca7255fe18f70b374ad1c105c44a330e26940f`.
- The selected-send range 5 plus range 8 is byte-identical to the post-add dynamic blob. The stable native export of the added payload is `phase-9-export-check-1/native/0001c0_IC_TEST_01.txt` under the stable path above, SHA-256 `85c8e82f3547ace5c72f3f2c1c3817788cd134e4e6bbf4dca9032d4ca11e4c08`.

## Matrix

| Area | Confidence | What the preserved evidence establishes | Remaining gap |
| --- | --- | --- | --- |
| Record/model node | verified for one result | Clean capture 04 adds exactly one reachable metadata record at `0x02c0`: flag `0xe0`, extension `txt`, `field_04=0x154`, payload length `53`, `field_10=0xffffffff`, `field_14=0x00000200`; raw-record SHA-256 `54ed029033e8f37900711c2de6623a8559404093823caabf3ea6c318dc5c104a`. Its 32-byte native prefix and source-identical payload are preserved. | No general source-node/model-tree builder or independent proof that this shape is valid for other names, parents, or payload sizes. Milestone F remains limited to one root-level TXT case. |
| Directory/path | verified for one result | The new path is `root\IC_TEST_01.txt`; reachable paths grow from 308 to 309, no path is removed, and the root child table grows from 320 to 384 bytes. | No evidence for a new directory, nested insertion, sibling ordering beyond this one root insertion, or collision behavior. |
| Source/name/encoding | verified for capture 04 | The exact host source is preserved at the stable capture root, is 53 bytes of CP932-compatible CRLF text, and has SHA-256 `2a3a3057a532d27bad9de6e7b3fb83bf3de95482202dcdf4580e7ecc53844e38`. The device record name is `IC_E_ADD_20260822_04` with raw extension `txt`. | Filename collision/encoding policy is proven only for this narrow case; Milestone F must reject ambiguous or unsupported names. |
| Category membership | verified as no inferred assignment | Static analysis maps `0x001b` to display history and `0x001c`–`0x001e` to mark lists 1–3. Capture 04 shows no new-record entry in those responses and no new path in the observed Manager-local category files. The correct offline policy is to preserve/rebase existing entries only and assign no category, mark, bookmark, or selection state automatically. | The legacy Manager's broader category assignment policy remains unknown and is intentionally not generalized. |
| `VICMEM.bin` | verified unchanged in capture 04 | Before/after snapshots are byte-identical, independently hash-verified, and neither contains `IC_E_ADD_20260822_04`. `VICMEM.bin` is a Manager-local category/bookmark bookkeeping file in this evidence, not the device-resident fixed response itself. | Category record fields, auxiliary bytes, tail lifecycle, and any future insertion policy remain unresolved; Milestone F must preserve/rebase rather than invent them. |
| `VICLV.bin` | verified unchanged in capture 04 | Before/after snapshots are byte-identical, independently hash-verified, and neither contains the new path. It is a Manager-local path/parity sidecar, not evidence that the device fixed state was unchanged. | A general new-file parity/category policy is not proven; preserve it byte-for-byte in the narrow add candidate. |
| `order.vnw` | verified unchanged and pre-populated | Before/after snapshots are byte-identical, independently hash-verified, and both already contain the new basename. It is Manager-local source-order/bookkeeping state; Send Selected did not modify the observed file. | This capture does not prove collision counters or deletion lifecycle; no add-induced order mutation is inferred. |
| Identifiers/offsets | verified only as offsets | Metadata offsets are relative to metadata start `0x40`; the added record is at `0x01c0` and existing state references shift accordingly. No stable record ID separate from position/name/fields is present in the recovered evidence. | Whether the manager/device assigns another identifier or uses a sidecar-specific key is unknown. |
| Allocation/capacity | verified for observed allocation; enforcement moves to F | Blob growth is exactly `+152` bytes: metadata `+64`, content `+88` (`32`-byte prefix + `53`-byte payload + `3` bytes alignment). The transaction has `N=0`, `M=0x1f4c00`, and `M = len(range 5)+len(range 8)`. | Remaining-capacity field interpretation is not proven. Milestone F must calculate complete candidate size and fail closed when safe available capacity is insufficient or ambiguous. |
| USB transaction ranges | verified for one ordinary add | Parsed ranges are `0x100, 0x40, 0xfec0, 0, 0x40, 0, 0, 0x1f7df8`; range-5 plus range-8 exactly reproduces the post-add blob. The capture has 524 native payload records. | Ranges 4/6/7 are empty only on this ordinary path; no general new-content serializer is proven. |
| Completion | Manager success observed; numeric handling bounded | Manager-level success is observed in clean capture 04. Existing modern replacement transactions support successful `0x101b` completion value `0x0000`. | Applying `0x0000` as the new-add success rule remains a checked protocol assumption until independently confirmed; no undocumented completion claim is hardcoded. |
| Unrelated changes | verified for shared payloads and expected references | Across 309 shared reachable paths, all shared file payloads are byte-identical. The only dynamic-blob content changes are the new 64-byte record, its 32-byte prefix plus 53-byte payload and alignment, expected metadata/content offset rebasing, and dynamic timestamp/checksum changes. | Fixed state objects `0x001b`, `0x001e`, `0x001f`, `0x0024`, and the dynamic blob change; their complete semantic causes are not all proven. Milestone F must preserve unknown bytes and rebase only established record offsets. |
| Manager-produced fixtures | supporting local-sidecar context | Stable fixture reports establish the formats and correlations used to audit `VICMEM`, `VICLV`, and `order.vnw`; capture 04 independently proves the four observed Manager files were unchanged around Send Selected. | The fixture set is not a general post-add synchronizer specification. No broader sidecar mutation is inferred. |

## Interpretation boundary and Milestone E closure

Capture 04 separates two classes of state. `VICDATA.bin`, `VICMEM.bin`,
`VICLV.bin`, and `order.vnw` are the observed Manager-local preparation and
bookkeeping files. The four Manager files were independently copied and
hashed before and after Send Selected; all four are byte-identical. Therefore
the unchanged sidecars are a verified negative result, not a missing transfer
artifact. In particular, `order.vnw` already contained the new basename before
the transfer.

The device-resident protocol state is separate: the dynamic `0x8004` blob and
fixed responses `0x001b`–`0x001f` carry device state and metadata-relative
references. A fresh add candidate may safely rebase established references to
records shifted by the new 64-byte metadata record, while preserving all
unknown fields and unused tails. It must not automatically assign a category,
mark, bookmark, selection, or new sidecar entry. This is an offline safety
policy, not a claim that the legacy Manager never maintains such state.

Completion is recorded precisely: Manager-level success is observed in the
clean legacy capture; existing modern replacement transactions support
successful `0x101b` completion value `0x0000`; applying that numeric result to
new-file addition remains a checked protocol assumption until independently
confirmed. Capacity interpretation and fail-closed enforcement move to
Milestone F; the observed `152`-byte blob growth is not a remaining-capacity
claim.

## Owner capture result

The owner-approved capture was preserved under:

```text
${EVIDENCE_ROOT}/phase-12-new-txt-20260822-133050/
```

The original `${OWNER_DESKTOP}/capture` directory was copied, never
moved or overwritten. The tracked evidence summary and all capture-stage
manifest hashes are in
`analysis/phase-12-owner-capture-evidence-2026-08-22.json`.

The capture establishes the following for the later successful send:

- The exact Windows-host source `IC_E_ADD_20260822_01.txt` is preserved at
  the stable source path with 53 bytes and SHA-256
  `2a3a3057a532d27bad9de6e7b3fb83bf3de95482202dcdf4580e7ecc53844e38`.
- The standalone native log is 2,288,416 bytes with SHA-256
  `dae79fdb4639219fe5f3f749433f105e86daac81f231121255d874e0d132fe57`.
  Offline parsing finds one ordinary `0x101b` transaction with range lengths
  `0x100, 0x40, 0xfec0, 0, 0x40, 0, 0, 0x1f4918` and `N=0`, `M=0x1f4958`.
- The complete pre-add and post-add backups both identify device `0x054c:0x001e`
  and contain eight objects. The post-add backup contains the new reachable
  path `root\\IC_E_ADD_20260822_01`.
- The three removed paths were deliberate owner actions taken after the
  earlier insufficient-space attempt and before the successful captured send;
  they are not classified as unrelated changes in this capture.

The capture does not close the gate. The pre-add backup predates the failed
attempt and deliberate deletions, so it is not a clean baseline for the
successful send. The post-add blob is 2,050,392 bytes versus 2,063,920 bytes
pre-add, and the existing `root\\IC_TEST_01` payload changes from 32 to 41
bytes. The four Manager sidecars are byte-identical before and after and do not
contain the new `IC_E_ADD_20260822_01` path. The earlier insufficient-space
failure has no separate native capture. A clean repeat add-only capture is
therefore required before promoting the general new-record model.

## Repeat add-only attempt

The owner approved a clean repeat add-only capture, and the fresh evidence root
is:

```text
${EVIDENCE_ROOT}/phase-12-new-txt-repeat-20260822-145157/
```

The exact `IC_E_ADD_20260822_02.txt` source is preserved at the root's
`01-manager-before-send/source/windows-host-copy/` path. It is 53 bytes,
CRLF-terminated, and has SHA-256
`2a3a3057a532d27bad9de6e7b3fb83bf3de95482202dcdf4580e7ecc53844e38`.

The fresh pre-add backup is complete with eight objects, manifest SHA-256
`0d8d281242dd35beaf85fc62768be478f475212a9c8fc2f1a796526686631e0c`, and
dynamic-blob SHA-256
`92cd4513d27f87ad6c5330b26e41bfc3c8f320d94b8477d4fb12e6377dc542b9`. The
fresh post-add backup is also complete with eight objects, manifest SHA-256
`36939ca427165d19005d6b63fa6037f7a5888ab41239a27f306e93328acece42`, and
dynamic-blob SHA-256
`5125e5c838beccf6d16dd492d5d943e6148035db337e0d9d01fe2e4eb6d61f38`.

Offline parsing finds exactly one added reachable path,
`root\\IC_E_ADD_20260822_02.txt`, with no removed paths. The added record is at
`0x0240`, has flag `0xe0`, extension `txt`, payload length 53,
`field_10=0xffffffff`, `field_14=0x00000200`, record SHA-256
`e7bbb620966959e80bf9edae60b8c56e22aa7ba81cf74d017aae4c7fc6689dbe`, and a
payload SHA-256 matching the original source. All shared file payloads are
byte-identical; the only shared semantic metadata change is the expected root
child-table growth from `0x1c0` to `0x200`.

This attempt is incomplete for Milestone E: SnoopyPro produced no native log,
and no after-send Manager snapshot or new-file sidecars were preserved. The
full attempt record, including all paths and hashes, is
`analysis/phase-12-repeat-add-only-attempt-2026-08-22.json`. The record is
preserved as evidence and is not promoted to the complete evidence gate.

## Repeat add-only attempt 03

The next owner attempt used the preserved current-state pre-add backup under:

```text
${EVIDENCE_ROOT}/phase-12-new-txt-repeat-20260822-151839/
```

The pre-add archive is complete with eight objects, manifest SHA-256
`546246477c68ee740e956ce9a6ccd975c2dc605be8b71233b1d5a62aee423846`, and
dynamic-blob SHA-256
`5125e5c838beccf6d16dd492d5d943e6148035db337e0d9d01fe2e4eb6d61f38`. The
post-attempt archive is complete with eight objects, manifest SHA-256
`720eee0a750f8523b76b77eb90dd3bf9a562459d61423db6529e2f865b16d49a`, and
dynamic-blob SHA-256
`f25819688d9bd2d22e9520adff401b397c26319d4ee89cc3a6824d610bebd319`.

The owner reported that SnoopyPro targeted the root hub instead of
`USB\\Vid_054c&Pid_001e`; no usable native log or Manager snapshots were
preserved. The Manager transfer nevertheless added exactly one reachable path,
`root\\IC_E_ADD_20260822_03.txt`, with no removed paths. Its 53-byte payload
has the exact source SHA-256, the new record is at `0x0280` with flag `0xe0`,
extension `txt`, `field_10=0xffffffff`, and `field_14=0x00000200`. All shared
file payloads are byte-identical; the expected root child-table change is
`0x200` to `0x240`.

The full record is `analysis/phase-12-repeat-add-only-attempt-03-2026-08-22.json`.
The next source, `IC_E_ADD_20260822_04.txt`, is prepared under the fresh root
`${EVIDENCE_ROOT}/phase-12-new-txt-repeat-20260822-152959/`
with the same 53-byte source hash. Its fresh pre-add backup is complete with
eight objects, manifest SHA-256
`b41db730ca73e19d7c9d3773db3d9ee97a9f30dba45dfd16c9ddb3be03ce0919`, and
dynamic-blob SHA-256
`f25819688d9bd2d22e9520adff401b397c26319d4ee89cc3a6824d610bebd319`. No
existing disposable record is to be deleted.

## Repeat add-only capture 04

The fourth attempt is preserved under the same stable root. It contains a
complete source, native log, independent before/after Manager snapshots, and
complete device pre/post backups. The native log is 2,288,872 bytes with
SHA-256
`4d934dbae6e849c9e6a3711612f44864e0f1d0c20cbb7075713190d2d4dc9d97` and
contains one ordinary `0x101b` transaction with range lengths
`0x100, 0x40, 0xfec0, 0, 0x40, 0, 0, 0x1f4c00`. Its offline range-5 plus
range-8 candidate SHA-256 is
`153f446520f556cb0d0c93061e14230664833d1320c25c9f86acf5c0ff7bc8dd`, exactly
matching the post-add device blob.

The pre-add device backup is complete with manifest SHA-256
`b41db730ca73e19d7c9d3773db3d9ee97a9f30dba45dfd16c9ddb3be03ce0919` and blob
SHA-256
`f25819688d9bd2d22e9520adff401b397c26319d4ee89cc3a6824d610bebd319`. The
post-add backup is complete with manifest SHA-256
`64cce92b52d417482ae9dda32d608795ebc3e27acef97fd0f545b8579964e5f3` and blob
SHA-256
`153f446520f556cb0d0c93061e14230664833d1320c25c9f86acf5c0ff7bc8dd`.

Offline parsing finds 366 to 367 metadata records and 309 to 310 reachable
records: exactly one added path, `root\\IC_E_ADD_20260822_04.txt`, with no
removed paths. The record is at `0x02c0`, flag `0xe0`, extension `txt`,
`field_04=0x154`, payload length 53, `field_10=0xffffffff`, and
`field_14=0x00000200`. Its record SHA-256 is
`54ed029033e8f37900711c2de6623a8559404093823caabf3ea6c318dc5c104a`; its
payload SHA-256 matches the preserved source. All shared file payloads are
byte-identical and the root child table grows from `0x240` to `0x280`.

The four Manager snapshot files are independently hash-verified and
byte-identical before/after. `VICMEM.bin` and `VICLV.bin` contain no `04` path.
`order.vnw` already lists `IC_E_ADD_20260822_04.txt` in both snapshots, so it
does not establish an add-induced change. The complete record is
`analysis/phase-12-repeat-add-only-capture-evidence-04-2026-08-22.json`.

## Gate decision

The audit and owner captures prove that legacy Manager activity can produce a
genuinely new TXT record; this is not merely an assumption based on a
selected-send capture. Capture 04 closes Milestone E: stable preservation is
complete; the exact source, native transaction, complete before/after backups,
independent Manager snapshots, one-record device delta, unchanged observed
sidecars, and shared-payload preservation are all verified. The unchanged
`VICMEM.bin`, `VICLV.bin`, and `order.vnw` files are the observed result of
Send Selected, not missing transfer artifacts.

This closure does not promote a general production writer. Milestone F owns
the narrow offline model: safe state-offset rebasing without invented
category/mark/bookmark/selection membership, fail-closed capacity
interpretation, and checked completion handling. No normal CLI/GUI new-file
control, modern write, delete, restore, or live operation is enabled. The
repeat protocol remains the preserved evidence template in
`analysis/phase-12-repeat-add-only-capture-protocol-2026-08-22.md`.

The repeat attempt used only owner-approved legacy Manager activity followed by
read-only macOS backups. No modern write, delete, restore, refresh, or evidence
overwrite was performed. Both repeat backups, the source, and the incomplete
capture stages remain preserved outside the source checkout. The canonical
suite remains at 226 passing tests.
