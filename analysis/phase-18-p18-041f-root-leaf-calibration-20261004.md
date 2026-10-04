# P18-041F — Guarded single root-level leaf deletion calibration

Date: 2026-10-04 (Asia/Tokyo)
Risk: R3 boundary investigation; no execution path reached
Disposition: **ROOT-LEAF DELETE EVIDENCE INSUFFICIENT — STOPPED BEFORE EXECUTION PATH**

## Starting state and provenance

The canonical Git starting point was `origin/main` at
`5bca280ffbd673fa56a2646a65b0329a4dc496f2`, the P18-040 merge checkpoint. The
local task branch is `task/P18-041F-guarded-root-leaf-delete`. The local checkout
was clean before work began.

The available local P18-041 Git refs were inspected before branching:

| Evidence | Local ref/checkpoint | Availability |
| --- | --- | --- |
| P18-041 admission investigation | `task/P18-041-guarded-device-library-deletion` at `b46917a730803eafa93178f45a112cbc05376cdb` | Local reviewed branch |
| P18-041A native marker characterization | `task/P18-041A-native-subtree-marker-characterization` at `b707c097809717e0a038ae79f958dc2f82bf272c` | Local reviewed branch |
| P18-041B disconnected/oracle evidence | `task/P18-041B-disconnected-oracle-subtree-markers` at `b37b290418bf240a2391dcd56da2fd5455b44f63` | Local reviewed branch; not used as a code base |
| P18-041C/D/E | No local Git ref or checkpoint | Supplemental read-only files only |

P18-041C, P18-041D, and P18-041E were available under the external,
read-only research package `/external/local-path` rather
than in the local Git refs. Their exact report identities were recorded as:

| Report | SHA-256 |
| --- | --- |
| `phase-18-p18-041c-disconnected-native-delete-harness-20261003.md` | `dae2a09eef0a70871a2c45088efff77238982e0b4a1f31144ee1254dc16a9d5a` |
| `phase-18-p18-041c-calibration-audit-20261003.json` | `fc4730d95ec59d0d97313f68759513828c53963c1b6b7aafb8789f3d8c8ed8eb` |
| `phase-18-p18-041d-legacy-delete-invocation-contract-20261003.md` | `970f2c28d0012cefd76262751dff20652cf0158d983728eb1c52f46afc17ec80` |
| `phase-18-p18-041e-native-receive-staging-20261004.md` | `03ccbc177000b743ac2e80cff853584cc2bf6983f02b28ebdc0651e01ed0962e` |
| `phase-18-p18-041e-staging-validation-20261004.json` | `459c29297c881638fe33157461f2617ee7dbf7d4d627f7fd6af4d6757def14d2` |
| `phase-18-p18-041e-independent-review-20261004.md` | `6a4db200bc22114315e1331cf9fc257e0ca753a4df87b3ed78820e961a7ad656` |

Those reports consistently preserve the relevant boundary: P18-041C did not
validate a disconnected native harness, P18-041D did not recover a complete
legacy Delete invocation contract, and P18-041E did not complete Receive
staging or run Delete/Send. Their conclusions were used as evidence, not as
instructions to guess missing native behavior. No file under `sources/` or any
external evidence checkout was edited.

## Exact calibration gate

The authoritative calibration inputs were read from the preserved external
evidence root; the raw files were not copied into Git:

```text
/external/local-path
  evidence/phase-12-milestone-h-delete-attempt-20260822-02/
  00-pre-delete-backup/object-08-command-8004.bin
  02-post-delete-backup/object-08-command-8004.bin
```

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| Exact baseline model | 2,051,000 | `aec90438c1323400b2f4d4210541c599600f4e9493596edc710bd676dee8adf6` |
| Historical native candidate/post backup | 2,050,848 | `88b95f8bc158ab89253faea8c9085799cebba76abf0a3f416afa62df8b55f287` |

The current `src/infocarry/delete_model.py` transformation was run against the
parsed baseline with the exact target path
`root\\IC_E_ADD_20260822_04.txt` and exact record offset `0x2c0`. No timestamp
map, normalization, expected-output patch, or disconnected Receive output was
provided to the transformation.

| Result | Value |
| --- | --- |
| Modern candidate bytes | 2,050,848 |
| Modern candidate SHA-256 | `dc099dca21169054c4643ed346fc617f3e991e9ae9f93e7c3b07fedb57895df9` |
| Required historical SHA-256 | `88b95f8bc158ab89253faea8c9085799cebba76abf0a3f416afa62df8b55f287` |
| Candidate equals historical post backup | `false` |
| Baseline record count → candidate record count | `368 → 367` |
| Removed logical path | exactly `root\\IC_E_ADD_20260822_04.txt` |
| Target metadata offset | `0x2c0` |
| Target baseline metadata offset supplied by task | `0x2c0` |

The exact byte comparison found 737 differing bytes in 368 contiguous ranges:

- 734 bytes are the `+0x0c..+0x0f` timestamp fields of all 367 surviving
  records;
- 3 bytes are the derived header checksum;
- zero non-timestamp record bytes differ;
- all 253 surviving logical file payloads are byte-identical; and
- the independent structural comparison reports the exact one-path removal,
  no added path, valid candidate/post paths, and no non-timestamp difference.

The structural match is useful diagnosis, but it does not satisfy the required
calibration gate. A normalized comparison is not being promoted to equality.

## Admission and implementation decision

The existing `DeviceLibraryDeletePlan` remains a host-only generalized logical
closure planner. It accepts nested selections and directory closures by design,
so it cannot be used as the P18-041F admission profile. The existing
`build_one_txt_delete_model` verifies one reachable TXT record and preserves
surviving timestamps, but its current model accepts nested TXT paths and is a
structural model rather than a proven root-level native-delete profile.

The older `delete_gate.py` comparison helper can only reproduce the historical
candidate when a complete opaque per-record timestamp map is supplied by the
caller. That map is not derived from the fresh baseline, and its presence would
be timestamp substitution rather than a recovered transformation rule. It is
therefore not a production-safe admission source for this task.

The evidence gap is precise: no independently established rule currently maps
a fresh baseline and operation context to the 367 historical surviving-record
timestamps. P18-041E additionally leaves the native staging/query environment
incomplete. The generalized marker/subtree questions remain unresolved and
were not broadened or inferred from this root-leaf structural match.

Accordingly, no root-leaf execution profile, candidate authorization path,
sender integration, claim consumption ordering change, marker lifecycle, UI
exposure, or hardware-ready claim was added. Delete remains disabled in the
normal product surface. The task stopped before any execution path.

## Validation and safety

Focused offline checks passed:

- deletion, evidence, model, readiness, smoke, state, transport, and workflow
  tests plus backup repacker and Device Library delete-plan tests: **81 passed**;
- full portable suite: **1,046 tests, OK, 3 established skips**;
- no physical or USB test was run.

Safety counters for this task are all zero:

```text
hardware/USB sessions       0
hardware writes             0
real 0x101b                 0
production sender calls     0
claims consumed             0
sender-marker mutations     0
installation-wide lock mutations 0
```

No push, merge, production sender call, claim consumption, marker mutation, or
installation-wide lock mutation occurred.
