# P18-015 — VNW-V15 Physical Validation

Date: 2026-09-09  
Repository: `sourvegie/sony-infocarry-modern-manager`  
Canonical base: `5d23e8b219507535b2db4b57028602073aa23c61`  
Branch: `task/P18-015-v15-physical-validation`  
Risk: **R3 device-changing**  
Initial disposition: **AUTHORIZED — NOT YET EXECUTED**

## Owner authorization

The Project Owner explicitly authorized exactly one bounded VNW-V15 physical validation for the P18-014 reviewed operation.

Exact owner-approval identity:

```text
APPROVE P18-015 V15 PHYSICAL VALIDATION 01
```

Exact runtime confirmation required immediately before the one-shot sender invocation:

```text
ADD IC_P18_LIBRARY_20260907_01 ONCE
```

Authorization is limited to the exact fixed operation below. It is not standing Send authorization.

## Exact physical operation

Device/model boundary:

- Sony VNW-V15 only;
- reviewed V15 profile/session only;
- expected USB VID/PID `0x054c:0x001e`;
- V10 remains out of scope.

Exact destination:

```text
root/IC_P18_LIBRARY_20260907_01
```

Exact ordered children:

```text
01-introduction.txt
02-page-01.bmp
03-ending.txt
```

Exact shape: **TXT → BMP → TXT**.

P18-014 sealed host identities:

```text
candidate length:     2123364
candidate SHA-256:    2d21044987668c55d06aaa202fa678d760f9dbca99a96679eb4dff26e5e818ac
transaction length:   2188900
transaction SHA-256:  82be7e81b213fbb07eba86894ee525970b8a48a1101da5b4324857b1003d2fc8
package manifest:     d2f78866bc05a79d46bdb9fdf47beec8d5c38920f0bbbd53799bdc137dabd6d1
core preflight seal:  57a605445b8a5fb9c8e0ae51aac2180487081bfc3e1c28cea8cfdf18e569cdf2
preflight seal:       601a500cf73ea5df1e89558737c0ad8f7531e8dcbfc8a4258fea39a311281410
candidate audit:      ada9cb88328e63bfaced559d5e4fe6f44b24d848f90033d99b0d13ec1bd526db
authorization:        0b15f3bb6f51cef55b177f6701487e607281a0ab84e1fb512598b79a5452750f
operation bundle:     d34ed9b00f133eb3c4b24fb55eaea7c7868a7c45e0da5d68c4ec710f9e823539
```

These P18-014 hashes are host-review reference identities only. The physical execution must rebuild and reseal from **fresh** live pre-write evidence; it must fail closed if fresh evidence changes any required operation binding.

## Auxiliary-state policy

Preserve exactly:

`verified_display_history_0x001b_and_bookmark_0x001f_semantic_rebase_plus_zero_count_0x001c_to_0x001e`

Required semantics:

- all seven established `0x001b` display-history logical paths remain the same after exact metadata rebasing;
- the one established `0x001f` bookmark logical path remains the same;
- its four opaque values remain byte-exact;
- unused bookmark tail remains byte-exact;
- `0x001c`–`0x001e` remain supported only as zero-count state;
- malformed, dangling, unaligned, unsupported, or inconsistent auxiliary state fails closed.

Do not infer broader bookmark/mark/history semantics.

## Mandatory fresh pre-write gates

Before any claim is consumed or any device-changing command is sent:

1. identify the attached device as the reviewed VNW-V15 profile;
2. obtain a fresh native `0x0019` capacity response;
3. obtain a fresh complete eight-object pre-write backup;
4. validate backup integrity and model binding;
5. prove `root/IC_P18_LIBRARY_20260907_01` is still absent;
6. rebuild the exact candidate from the fresh backup;
7. verify exact destination, ordered package, payloads, capacity, shared-path/payload/timestamp preservation, unknown-record preservation, and reviewed auxiliary semantics;
8. rebuild authorization, bundle, audit, and sealed preflight from the fresh evidence;
9. require the installation-wide indeterminate-write lock to be `cleared`;
10. require no active sender marker;
11. require the historical P18-011 claim `827bfde0b93d4b2da57ee646ff6aaa1d` to remain permanently consumed;
12. require claim-store integrity `ok`;
13. require no new claim to have been consumed yet.

Any pre-write mismatch must stop before the write. Use `BLOCKED_BY_EXTERNAL_EVIDENCE` for an unavailable/non-actionable external precondition and `ESCALATION_REQUIRED` for conflicting or unsafe evidence.

## One-shot execution boundary

Maximum authorized device-changing activity:

```text
logical transactions: 1
sender invocations:    1
0x101b transmissions:  1
retries:               0
second transaction:    prohibited
```

Only after every fresh pre-write gate passes:

- require runtime confirmation exactly `ADD IC_P18_LIBRARY_20260907_01 ONCE`;
- consume exactly one new durable execution claim;
- create/use the sender marker according to the existing guarded-transfer API;
- execute the exact reviewed transaction once.

Do not retry an ambiguous or failed live operation.

## Completion and post-write verification

The native sender must return explicit integer `0x0000` before terminal verification proceeds.

Then obtain a complete post-write backup and run the corrected P18-012 terminal verifier. Require:

- post dynamic blob equals the sealed fresh candidate;
- exact new target exists;
- exact TXT → BMP → TXT order and payloads;
- every pre-existing logical path preserved;
- all shared payloads and timestamps preserved;
- unknown/unrelated record bytes preserved except reviewed metadata relocations;
- all seven `0x001b` references preserve logical paths;
- the established `0x001f` bookmark preserves its logical path and opaque bytes/tail;
- `0x001c`–`0x001e` remain zero-count;
- no unrelated mutation.

Terminal success may be recorded only through the existing durable result/claim/marker contracts. Do not synthesize a missing result manifest or infer success from device appearance alone.

If an operation may have started but terminal state is not independently verified, do not retry. Record the installation-wide indeterminate-write lock and sender marker according to the established APIs and return `ESCALATION_REQUIRED`.

## Not authorized

The owner did **not** authorize:

- any second transaction or retry;
- overwrite/merge of an existing destination;
- deletion;
- corrective write;
- restore/rollback;
- interruption/recovery experiments;
- hierarchy/broader package expansion;
- V10 operation;
- firmware/destructive work;
- standing/general Send capability.

## Closure gates

After the physical attempt:

- preserve raw evidence outside Git;
- update this analysis record and `CURRENT_STATUS.md` with sanitized evidence only;
- run focused safety tests, P18-006 adversarial coverage, full portable suite, Python compilation, and `git diff --check`;
- obtain macOS + Windows CI on the reviewed commit;
- obtain a fresh independent strong R3 review with final `P0=0, P1=0, P2=0 — PASS` before merge.

Do not merge automatically.
