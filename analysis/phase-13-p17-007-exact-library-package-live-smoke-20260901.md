# P17-007 — exact Library-package one-shot live smoke

Date: 2026-09-01
Baseline: canonical `main` at `ca57b33` (PR #13)
Disposition: **ESCALATION_REQUIRED — stopped before transmission**
Risk: **R3 — device/safety critical**

## Authorized scope

The owner supplied both exact operation phrases for one additive operation only:

```text
APPROVE P17-003 MODERN LIBRARY PACKAGE SMOKE 01
ADD ONE INFOCARRY MULTI-CHILD PACKAGE
```

The requested package was the previously reviewed, explicitly imported Library
item `f767f6ba-7ea2-5bd9-8e0d-9bf8443946ae`, targeting
`root\\IC_P17_LIBRARY_20260831_03` with the ordered children
`01-introduction.txt`, `02-page-01.bmp`, and `03-ending.txt`. No broader
package or transfer scope was authorized.

## External evidence

All P17-007 evidence is preserved outside Git, without overwriting prior
evidence, at:

`/Users/stardust/Projects/InfoCarry-Evidence/phase-17-p17-007-library-package-live-smoke-20260901-01/`

The final version-2 preservation manifest contains 73 entries, replays with
zero hash/size mismatches, and has SHA-256
`a2608ff31defabdefb08b41bf6c85cc82a40ddfad0f7d33fc933483666c32f60`.
The earlier version-1 manifest remains preserved as a historical checkpoint.
Raw candidate and transaction bytes remain external.

## Fresh preflight and revalidation

The first fresh preflight attempt completed the physical read-only sequence but
stopped during host-only report generation because of a reporting attribute
typo. It did not modify the device. The corrected second preflight was sealed
non-overwriting under `02-sealed-preflight/sealed-preflight-0002.json`.
Its sealed preflight SHA-256 is
`316fee2ad9713a7cca5e48b6fab51e1b273f2572d88bc865185c0be6915acb5b`.

The corrected preflight verified, in order:

1. exactly one Sony `054c:001e` device, observed on bus 2/address 3;
2. a fresh native `0x0019` response with SHA-256
   `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a`;
3. parsed capacity limit **3,145,728 bytes**;
4. a complete eight-object backup with target absent, manifest SHA-256
   `46688511f03e9f5ebf7e25bef0017a64a3ebc92482c10b535ecd70fc75ef92fe`,
   dynamic-blob SHA-256
   `e3ac59cb5586a5dc35ea04f6bf24f5cc6509931761ece01bc2605a717335e741`,
   and baseline model length **2,075,256 bytes**; and
5. exact package/catalog/source/template reconstruction and candidate sealing.

The candidate model was **2,091,292 bytes**, with **16,036 bytes** of growth
and **1,054,436 bytes** of parsed-capacity margin. Its candidate blob SHA-256
was `0e3af665c6046c91d1096e8570f8b63b1fc82d35788027becf65ff942ca8883f`,
and its prospective transaction SHA-256 was
`1abab51a9ddb069154fba4d411ffbe31359125270b1438d78acd47b745a54439`.
Both matched the approved P17-006 candidate and transaction exactly. The
target was absent, the four expected additive paths were bound, the reviewed
template and explicit timestamp policy were retained, and no sender was
constructed during either preflight.

## Fail-closed execution result

With both exact phrases supplied, the merged P17-005 adapter performed its
mandatory immediate revalidation: fresh identity, fresh capacity, sealed
preflight backup revalidation, and one new complete fresh pre-write backup.
The new pre-write backup was complete and independently verified. Its manifest
SHA-256 was
`35a203ba8df6c351b473c18b364c52b1e507973f6e27f49fd5bfbf56f18a2636`; its
dynamic blob SHA-256 was the same
`e3ac59cb5586a5dc35ea04f6bf24f5cc6509931761ece01bc2605a717335e741`; and it
contained eight verified objects.

P17-005 then rejected the fresh pre-write backup because its full backup
identity did not equal the sealed baseline identity. The preserved comparison
shows equal device identity, filenames, object count, dynamic blob, protocol,
and all raw object hashes. The differing archive metadata includes
`created_at_utc`, `updated_at_utc`, and per-object `received_at_utc` values,
which necessarily change the manifest SHA-256. These differences were not
normalized away. The comparison is preserved at
`04-audit/backup-identity-comparison-0001.json`.

The adapter failure is preserved at
`04-audit/execution-failure-0001.json` and records:

- stage: `preflight_revalidation`;
- state: `failed`;
- `write_started`: `false`;
- sender calls: `0`;
- write backend opened: `false`; and
- automatic retry: prohibited.

The USB audit at `04-audit/usb-audit-0001.json` records zero backend method
calls and zero USB transmission. No `0x101b` request was issued, no completion
value exists, no post-operation backup was attempted, and no corrective write,
retry, deletion, overwrite, or restore occurred.

## Evidence classification

### Verified

- the exact selected Library package, catalog item, ordered children, source
  hashes, prepared hashes, and reviewed template;
- exact Sony identity, fresh native `0x0019` response, and parsed capacity;
- two corrected fresh complete eight-object preflight backups and the fresh
  complete execution pre-write backup;
- target absence, exact candidate and transaction equality with P17-006,
  candidate capacity fit, and sealed preflight integrity;
- raw object hashes and payload/model identity were equal between the sealed
  preflight and fresh execution pre-write backup;
- the P17-005 full-identity revalidation rejected the fresh backup before the
  sender boundary; and
- the external 73-entry preservation manifest replayed with zero mismatches.

### Observed

- the device enumerated as Sony `054c:001e` on bus 2/address 3;
- the read-only capacity queries and complete backups completed normally; and
- the adapter returned a preflight-revalidation failure before transmission.

### Inferred

- the differing backup identity is attributable to capture-generated archive
  timestamps because all preserved raw objects and protocol fields compare
  equal; this explains the host gate result but does not authorize relaxing it.

### Unresolved

- whether P17-005 should bind exact archive metadata identity or a narrower,
  explicitly reviewed raw-state identity for the additional fresh pre-write
  backup;
- physical compatibility or persistence of this Library package;
- native numeric completion decoding and operation-specific capacity semantics;
- interrupted-write atomicity/recovery; and
- all broader package, batching, nesting, retry, synchronization, and normal
  GUI/CLI transfer behavior.

## Disposition

P17-007 is **ESCALATION_REQUIRED**. The complete evidence is not externally
incomplete; the safe merged execution adapter rejects its own newly captured
fresh backup under the exact identity gate before it can send. The operation
must not be retried, the approval phrases must not be reinterpreted, and no
new approval can safely overcome this host-boundary conflict without a
Project Lead decision and a separately reviewed correction. No hardware write
occurred.

The independent R3 review confirms this disposition and the zero-transmission
boundary; it is recorded in
`analysis/phase-13-p17-007-r3-review-20260901.md`.

## Validation checkpoint

- Focused P17-005 adapter, P17-003 Library bridge, and independent read-back
  verifier tests: **27 passed**.
- Complete portable offline suite: **591 passed, 3 intentional skips**.
- `git diff --check`: passed.
- The external P17-007 version-2 preservation manifest replayed **73 entries
  with zero hash/size mismatches**; all three captured eight-object backup
  archives independently verified.
- The excluded-content/history audit found no tracked or reachable forbidden
  proprietary/live-evidence extensions or evidence directories.
- Independent strong R3 review: **ESCALATION_REQUIRED**, with no material
  finding about the evidence preservation or pre-send boundary; the material
  unresolved item is the P17-005 backup identity policy.
