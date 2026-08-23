# Milestone I.5 — legacy capacity semantics (offline)

Date: 2026-08-23
Status: native write-path capacity semantics resolved offline; Manager UI
mapping to device capacity remains separate and partially unresolved. No USB
write, package transfer, or device mutation was performed.

## Result

The preserved `VicTwo.dll` data flow establishes one total model limit for the
ordinary `0x101b` worker:

```text
0x0019 response +0x08
        -> GetHardwareInfo local model field
        -> ordinary-worker context +0x24
        -> dispatcher compares context +0x24 with N + M
```

The check is at `VicTwo.dll` `0x10004c90`–`0x10004cee`:

```text
N = dispatcher descriptor +0x38
M = prospective variable length
N + M <= ordinary-worker context +0x24
```

The ordinary captured transaction uses `N=0` and `M=len(dynamic blob)`, so
the complete candidate dynamic model length is the quantity that must remain
at or below the device limit. This is not a remaining-space value.

The native mapping is supported by independent static data flow and the
captured `0x0019` response. It does not depend on the Manager’s displayed KB
line, a guessed free-space value, or command `0x0024`.

## Static data-flow evidence

| Item | Evidence | Classification |
| --- | --- | --- |
| Preserved `VicTwo.dll` | `../legacy/extracted/program files/Sony/infoCarry/infoCarry Manager/VicTwo.dll`; SHA-256 `a02e5927d2e5ded988556e0be0e79a38313ce91f6491ad0ac8835971d3db0dae` | verified artifact |
| `0x0019` exchange | `GetHardwareInfo` `0x10007bc0` sends command `0x0019` and receives 64 bytes | verified static fact |
| Response `+0x08` parse | `0x10007c84`–`0x10007c97` parse the four-byte response field into the device-info model | verified static fact |
| Context copy | `0x10007cb8`–`0x10007cbb`: model `+0x74` to worker context `+0x24` | verified static fact |
| Ordinary send refresh | `VICCTR.dll` `VICSendData` refreshes device information when the context is not already initialized; the hardware callback reaches `GetHardwareInfo` | verified static call path |
| Dispatcher capacity check | `0x10004ce4` loads `[arg1+0x24]`; `0x10004ce9` adds descriptor `+0x38` to `N`; `0x10004cee` rejects when `N+M` is above the context value | verified static fact |
| Transaction declaration | the dispatcher declares `0x10000 + N + M`; ordinary range-5/range-8 captures have `N=0`, `M` equal to the dynamic blob length | verified from code and captures |
| `0x0019` response `+0x14` | current response value `4,194,304`; this field is not copied by the `GetHardwareInfo` path into context `+0x24` | verified field separation; semantic name unresolved |

The unknown response field remains named `field_14_be32`. It is not renamed to
capacity and is not used by the candidate model.

## Manager UI display trace

Preserved Manager artifacts:

- `infoCarryManager.exe` SHA-256
  `a195c898de9f619a9978ba9bb8bc71c18692bf28cfca915ea0b747edc4ee4d76`
- `icmres.dll` SHA-256
  `94c6e123514d67d88ed17907c9a8f60e45d787180147d9018f067c1f0ad6ee15`

The display function at `infoCarryManager.exe` `0x41a130` uses two Manager
object fields:

- `this+0x528` is formatted as the denominator with resource `0x7d6` and is
  rounded upward to `ceil(value / 1024)`, with a minimum of 1 for a positive
  value.
- `this+0x52c` is formatted as the numerator with the same signed-safe KB
  rounding. A negative value produces `----` using resource `0x80e`.
- Resource `0x7d6` is `ﾒﾓﾘ使用量 %6dKB / %8dKB`; resource `0x80e` is
  `ﾒﾓﾘ使用量    ----  / %8dKB`.

Static Manager code at approximately `0x41a350`–`0x41a5b6` initializes and
accumulates `this+0x528` while walking Manager-local records, including
per-record `+0x40` accounting. A separate status update at approximately
`0x41a000` sets `this+0x52c` from a dynamically resolved callback result and
uses `-1` on failure. The exact callback implementation is not present in
this static path, so the relationship of `+0x52c` to any one device response
field is unresolved.

Therefore the UI line is verified as a rounded Manager-local “used / total
KB” display, but it is not evidence that the denominator is the native
dispatcher limit or that the numerator is device-free capacity. The owner’s
observed `---- / 1997KB` display is recorded as an observation only; it does
not match `0x0019` `field_08_be32 / 1024` and is not used for authorization.

## Cross-check table

All model sizes below are dynamic-blob lengths. For ordinary transactions,
`N=0`, so `N+M` equals the candidate model length.

| Evidence | Total limit | Baseline N+M | Candidate N+M | Growth | Derived remaining growth | Classification |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `0x0019` response used by current device | 3,145,728 | — | — | — | — | verified native limit; response `field_08_be32` |
| Capture 04 pre/add | 3,145,728 | 2,050,696 | 2,050,848 | 152 | 1,094,880 after candidate | verified blobs and transaction |
| Capture 7 pre/package | 3,145,728 | 2,050,848 | 2,051,132 | 284 | 1,094,596 after candidate | verified blobs and transaction |
| I.4 provisional package preview | 3,145,728 | 2,051,132 | 2,051,420 | 288 | 1,094,308 after candidate | offline derived preview; no transmission |

For completeness, the pre-candidate allowances are `1,095,032` for capture
04, `1,094,880` for capture 7, and `1,094,596` for the I.4 baseline. These
are derived as `capacity_limit_bytes - baseline_model_bytes`; they are not
values read from the Manager UI.

Existing complete backup manifests and dynamic-blob hashes support the model
lengths. The successful legacy TXT add and folder-package captures show the
candidate growth and exact native range-5/range-8 payloads. They do not by
themselves establish a free-space display semantic; the static dispatcher
trace supplies the total-limit meaning.

Command `0x0024` is **observed to equal the current dynamic-model length and
excluded from capacity authorization; broader semantics unresolved.** Its
current response begins with `0x001f4c3c` (2,051,132), exactly the current
dynamic-blob length. No independent evidence makes it a free-capacity response.

## Model change and safety boundary

The package candidate now records and binds these distinct quantities:

- `capacity_limit_bytes`: the native total model limit;
- `baseline_model_bytes`: fresh backup dynamic model length;
- `candidate_model_bytes`: complete prospective dynamic model length;
- `candidate_growth_bytes`: candidate minus baseline;
- `remaining_growth_bytes`: limit minus baseline;
- `capacity_source`: explicit evidence source.

The candidate is accepted only when
`candidate_model_bytes <= capacity_limit_bytes`. The prior
`available_capacity_bytes` argument remains only as an explicitly labeled
offline compatibility path for callers that have a remaining-growth budget;
it is converted to a synthetic total and is not device evidence. New audits
must use the explicit total-limit fields.

This resolves the native capacity ambiguity that blocked the I.4 preview, but
does not authorize a live package write. Physical transport behavior,
package completion handling, interrupted-write recovery, and the exact
Manager callback feeding `+0x52c` remain outside this result. The normal
package GUI/CLI action stays disabled.

## Tests and provenance

The capacity model and package authorization tests are in commit `9657e85`.
The complete canonical suite passes **336 tests** at the I.5 checkpoint; I.6
extends the current implementation to **357 tests**:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -q
```

Focused coverage includes exact boundary, one byte over capacity, missing or
malformed evidence, inconsistent model lengths, and invalidation when any
capacity-bound audit value changes.
