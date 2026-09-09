# P18-015 — VNW-V15 Physical Validation

Date: 2026-09-09  
Repository: `sourvegie/sony-infocarry-modern-manager`  
Canonical base: `5d23e8b219507535b2db4b57028602073aa23c61`  
Branch: `task/P18-015-v15-physical-validation`  
Risk: **R3 device-changing**  
Initial disposition: **AUTHORIZED — NOT YET EXECUTED**
Current disposition: **PHYSICAL VALIDATION COMPLETE — TERMINAL READ-BACK VERIFIED**

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

## 2026-09-09 physical-validation attempt

The requested branch was fetched and checked out cleanly at
`d6ce5d186042792983d9ad12fa5978790384ae52`, the expected P18-015 owner-
authorization commit. The installation-owned safety state was inspected
before any live-device operation:

- claim-store SQLite integrity: `ok`;
- historical P18-011 claim `827bfde0b93d4b2da57ee646ff6aaa1d`:
  permanently `consumed`;
- new P18-015 claim: absent / not consumed;
- active sender marker: none;
- installation-wide indeterminate-write lock: `cleared`.

The initial filtered PyUSB enumeration, run inside the managed command sandbox,
returned zero matching devices with Sony VID/PID `0x054c:0x001e`. That result
did not establish that no physical USB device was attached. Consequently,
exact VNW-V15 identification, a fresh native `0x0019` response, and a fresh
complete pre-write backup were not obtained during the initial attempt. The
procedure failed closed at the first external-evidence gate with disposition
**BLOCKED_BY_EXTERNAL_EVIDENCE** pending read-only diagnosis.

The runtime confirmation was not presented or accepted. No candidate,
authorization, audit, preflight seal, operation bundle, transaction, or
capacity identity was created from stale evidence as a substitute. No claim
was consumed, no sender marker was established, no sender was invoked, and no
`0x101b` request was transmitted. Counts remained:

```text
logical transactions: 0
sender invocations:    0
0x101b transmissions:  0
retries:               0
```

Native sender return, post-write backup, terminal verifier result, and
physical target/content/auxiliary-state results are not applicable because no
device-changing operation began. P18-014's offline identities remain review
references only and are not reported as fresh physical evidence. No capability
claim or matrix row is broadened.

Host closure validation passed on the sanitized documentation diff:

- focused guarded-transfer, P18-006 adversarial, live-adapter, verifier,
  claim-store, lock, and real-evidence suites: 100 tests passed;
- full portable suite: 757 tests passed with 3 intentional
  evidence-dependent skips;
- Python 3.12 compilation: passed;
- `git diff --check`: passed.

The focused closure is [PR #41](https://github.com/sourvegie/sony-infocarry-modern-manager/pull/41).
Python 3.12 CI passed on commit `3e8c949` in workflow run
`34347598259`:

- [macOS](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/34347598259/job/102452807217);
- [Windows](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/34347598259/job/102452803521).

### Read-only enumeration diagnosis continuation

The Project Owner reported that the InfoCarry was physically attached during
the initial stop and was observed at bus 1, address 1. A bounded read-only
diagnosis was therefore performed without opening an interface, reading USB
strings, sending a standard or vendor request, calling `set_configuration()`,
or changing device state.

The execution environment was independently recorded as:

| Field | Result |
| --- | --- |
| `sys.executable` | `/Users/stardust/Projects/sony-infocarry-modern-manager/.venv/bin/python` |
| Python | `3.12.14` |
| machine architecture | `arm64` |
| PyUSB | `1.3.1` |
| PyUSB backend | `usb.backend.libusb1._LibUSB` |
| loaded libusb | `/opt/homebrew/lib/libusb-1.0.dylib` |
| libusb package | Homebrew `1.0.30`, arm64 Mach-O |

Python and PyUSB match the known-good P18-011 versions. The earlier record did
not capture enough backend/library detail to claim complete environment
equivalence; the current backend and loaded library are now explicit.

`system_profiler -json SPUSBDataType` returned an empty USB array. The more
direct read-only macOS IORegistry plane did enumerate the device. `ioreg -p
IOUSB -r -c IOUSBHostDevice -l -w 0` reported one unnamed node at location
`0x01100000`, USB address 1, `idVendor=1356` (`0x054c`), `idProduct=30`
(`0x001e`), and `bcdDevice=256` (`0x0100`). The node has `iProduct=0` and
`iManufacturer=0`, so product and manufacturer strings were unavailable and
were not read. Its controller location corresponds to bus 1, establishing
that the owner's bus-1/address-1 observation was the exact Sony VID/PID node,
not an unrelated device.

The same unfiltered `usb.core.find(find_all=True)` call produced different
results across execution contexts:

- inside the managed command sandbox: zero devices total, including no object
  at bus 1/address 1 and no `054c:001e` object;
- outside that sandbox, using the same Python, PyUSB backend, and libusb:
  seven devices total; bus 1/address 1 was `054c:001e`, `bcdDevice=0x0100`;
  exactly one `054c:001e` object was present;
- the existing filtered `find_devices()` helper then returned exactly that one
  device at bus 1/address 1.

Five bounded enumeration-only repetitions outside the command sandbox were
stable. Every repetition returned seven total devices, one unfiltered
`054c:001e` object at bus 1/address 1, and one matching result from the existing
filtered detector.

This is diagnostic classification **A — macOS and host-visible PyUSB both see
`054c:001e`**. The earlier zero result was specific to the restricted process
context, not VID/PID filtering and not demonstrated physical absence. No
production detection change is justified. P18-015 execution was not resumed;
PM review and separate authorization to resume remain required.

The durable state was reconfirmed after diagnosis: global lock `cleared`, no
active sender marker, SQLite integrity `ok`, and exactly one claim—the
historical P18-011 claim `827bfde0b93d4b2da57ee646ff6aaa1d`, still
permanently `consumed`. No P18-015 claim exists or was consumed.

Read-only diagnosis totals remained:

```text
device writes:       0
sender invocations:  0
0x101b transmissions: 0
claim consumption:   0
```

## Authorized execution continuation

After PM review, the owner separately authorized resumption of the already
approved P18-015 operation. All execution work used the host-visible Python
environment established by the read-only diagnosis. No production detector
change was made.

Fresh live gates passed before confirmation or claim consumption:

- exact device: `0x054c:0x001e`, `bcdDevice=0x0100`, bus 1/address 1;
- fresh native `0x0019`: 3,145,728-byte capacity, 64-byte response SHA-256
  `c33328b686dee7fdc005731a5ded428d76415e91ced03edad63646063394662a`;
- complete initial preflight backup manifest SHA-256
  `0f4551093adb59e45d2820692e4a018f824a5cd936c3efa854de5046b1fa3f9b`;
- pre-write state identity
  `e603fecc087bd615bada4dd37f6636eba7af257a75d0f1baa0b913764e7797b4`;
- exact destination absent, auxiliary state eligible, claim-store integrity
  `ok`, global lock `cleared`, and no sender marker;
- historical P18-011 claim remained permanently consumed and no P18-015
  claim existed;
- fresh candidate: 2,123,364 bytes, SHA-256
  `2d21044987668c55d06aaa202fa678d760f9dbca99a96679eb4dff26e5e818ac`;
- fresh transaction: 2,188,900 bytes, SHA-256
  `82be7e81b213fbb07eba86894ee525970b8a48a1101da5b4324857b1003d2fc8`;
- core preflight seal
  `afab46439256839a813d6c947b83ba61b4c66fb2c45391482e2f686ee0f05e3f`;
- preflight seal
  `a7e97e9aeffc69c2fc6b288eb8d388d1aa0bf632cb1c40ca4888e2b50668a05b`;
- operation bundle
  `acc8d3e5264a56a6e68b402f0dc984d78b15e0d0edfaed6c334428e8b26db039`;
- authorization
  `65f088897613e9d0b4da831eb6ebb339b20cdfcdc47a3e3646d68005fcd5b69c`;
- remaining capacity after candidate: 1,022,364 bytes.

Only after these gates passed, the exact runtime confirmation
`ADD IC_P18_LIBRARY_20260907_01 ONCE` was presented and accepted. The existing
guarded coordinator consumed P18-015 claim
`e921b09cb11d475c96730566a0e65108`, established the normal sender marker,
and invoked the sender once. Exactly one logical transaction and one `0x101b`
header were sent; there were no retries. The native sender returned explicit
integer `0x0000`.

The execution-time pre-write backup manifest SHA-256 is
`1f9600fba7241bc606fb8418ce5c4a7316844ae613d3f30c569b3837f9e8fca4`.
Its dynamic blob SHA-256 is
`6fd27699ca6c13a46f8d75467ba72860af8b865b7cf19046b7a91f63bf471e01`
and its state identity agrees with the fresh preflight. The complete post-write
backup manifest SHA-256 is
`b617b99133799f8f567a8a0d78594d26a6739779e8117c0822c324fb2f90164c`;
its dynamic blob is byte-exact with the sealed candidate and its state identity
is `7d422761a586a752097128dbf5c6ff720abec66116df189ee29e4f2fe9aab1fc`.

The existing durable APIs recorded result manifest SHA-256
`8be66b0addd29985806c7c8fea0328a87213378dd8a91a8fca7cd32daf6ad90d`
with state `readback_verified`. Independent disk-only revalidation using the
corrected terminal verifier passed: the exact destination exists with ordered
children `01-introduction.txt`, `02-page-01.bmp`, and `03-ending.txt` and exact
payloads; all 339 shared paths, payloads, and timestamps are retained; there
are no removed paths; fixed and unrelated state is unchanged except reviewed
relocations. All seven display-history paths and the established bookmark path
are preserved, all four bookmark opaque values and the unused tail are exact,
and `0x001c`-`0x001e` remain zero-count.

After durable terminal success, the temporary operator script's final
reporting helper raised because it still asserted that the claim database
contained only the historical P18-011 claim. This was a post-result reporting
error: it encountered the legitimate newly consumed P18-015 claim. It did not
affect the coordinator result, post-write evidence, result manifest, or safety
state, and it triggered no retry or additional USB command. Final durable
state is claim `e921b09cb11d475c96730566a0e65108` permanently `consumed`, no
active sender marker, global lock `cleared`, and claim-store integrity `ok`.
Raw evidence remains outside Git.

Final physical counts:

```text
logical transactions: 1
sender invocations:    1
0x101b transmissions:  1
retries:               0
```

Post-attempt host validation passed:

- focused guarded-transfer, P18-006 adversarial, live-adapter, verifier,
  claim-store, lock, and transport suites: 115 tests passed;
- P18-014 real-evidence regression: 2 tests passed;
- full portable suite: 757 tests passed with 3 intentional
  evidence-dependent skips;
- Python 3.12 compilation: passed;
- `git diff --check`: passed.

The P18-014 real-evidence regression was corrected to assert its intended
durable invariant—that the historical P18-011 claim remains consumed—without
assuming no later valid claims can exist. All claims in the installation store
must remain consumed. This test-only correction neither changes production
execution behavior nor broadens capability.
