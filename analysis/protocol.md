# InfoCarry USB Transport Protocol

Status: Phase 2 static-analysis specification, completed 2026-08-20.

No request in this document was sent to the physical device during Phase 2. The
mapping was recovered from the preserved Windows driver and manager binaries.
Phase 1 supplied the independently observed USB descriptors and active alternate
setting.

## Evidence labels

- **Verified**: directly established by binary control flow, constants, data
  layout, or Phase 1 descriptor observations.
- **Observed**: behavior seen on the connected device without an InfoCarry
  application command.
- **Inferred**: a semantic name or modern-client rule supported by the evidence
  but not explicitly named by the legacy software.

## Preserved inputs

| File | SHA-256 |
| --- | --- |
| `VICUSB.sys` | `8843cd80ca88b606580c692731139dfdf52903abdc062d55e85d293f8e653814` |
| `VICCTR.dll` | `9c315655496fffe4ed74699d524018f9473b380e7833795e28d169de66eda164` |
| `VicTwo.dll` | `a02e5927d2e5ded988556e0be0e79a38313ce91f6491ad0ac8835971d3db0dae` |

The files were inspected in place and not modified. Addresses below are PE
virtual addresses for the DLLs and RVAs for the driver's retained symbols.

## USB interface and pipes

**Verified/observed:** the VNW-V15 has interface 0 with two alternate settings:

| Alternate | Bulk OUT | Bulk IN | Use by shipped manager |
| --- | --- | --- | --- |
| 0 | `0x01` | `0x82` | **Verified:** selected and used |
| 1 | `0x02` | `0x81` | No call site found |

`VICUSB.sys` selects the first matching interface descriptor while configuring
the device. Alternate 0 occurs first in the configuration descriptor.
`VICCTR.dll` has an internal wrapper at `0x100019a1` for IOCTL `0x22000C`, but
there is no call to that wrapper and no other `0x22000C` reference in the shipped
manager binaries. `VICOpen` at `0x10002237` instead queries the driver's current
pipe information and opens `PIPE00`, `PIPE01`, and so on. It assigns a bulk pipe
to the read or write field according to the endpoint direction recorded by the
driver.

Therefore a modern client for this device should claim interface 0 and select
alternate 0, then discover the bulk endpoint addresses from the descriptors.
It must not switch to alternate 1 without new evidence.

## Driver IOCTL map

`VICUSB.sys` retains symbols including `_EBXUsb_ProcessIOCTL@8` at RVA `0x1270`,
`_EBXUsb_SelectInterface@16` at `0x0710`, `_EBXUsb_ResetPipe@8` at `0x08A4`,
and `_EBXUsb_StagedReadWrite@12` at `0x15F4`.

**Verified:** `_EBXUsb_ProcessIOCTL@8` dispatches the complete private range as
follows:

| Windows IOCTL | Driver operation | USB operation or returned data | Used by `VicTwo.dll` |
| --- | --- | --- | --- |
| `0x220000` | Get configuration descriptor | Copies the driver's cached configuration descriptor; no bus request | No |
| `0x220004` | Reset device | Queries port state and may reset the parent USB port | No |
| `0x220008` | Reset pipe | Synchronous reset/clear-stall for a selected pipe | No |
| `0x22000C` | Select interface | Selects interface 0; caller supplies alternate setting as a 32-bit value | No |
| `0x220010` | Get interface information | Copies cached pipe/interface information; no bus request | No |
| `0x220014` | Begin device-to-host command | Vendor-device control OUT, request 1, six-byte header | Yes |
| `0x220018` | Begin host-to-device command | Vendor-device control OUT, request 2, six-byte header | Yes |
| `0x22001C` | Query transfer state | Vendor-device control IN, request 3, two-byte result | Yes |
| `0x220020` | Query completion result | Vendor-device control IN, request 4, two-byte result | Yes |
| `0x220024` | Additional result query | Vendor-device control IN, request 5, two-byte result; higher-level meaning unknown | No |

The semantic names “begin”, “state”, and “completion” describe how `VicTwo.dll`
uses the operations. The underlying request numbers, directions, recipients,
sizes, and values are verified.

### Exact control transfers

The driver builds `URB_FUNCTION_VENDOR_DEVICE` requests. It sets `wValue` and
`wIndex` to zero. OUT URBs have no direction flag; IN URBs set
`USBD_TRANSFER_DIRECTION_IN`.

| IOCTL | `bmRequestType` | `bRequest` | `wValue` | `wIndex` | Data stage |
| --- | --- | --- | --- | --- | --- |
| `0x220014` | `0x40` (host-to-device, vendor, device) | `0x01` | `0x0000` | `0x0000` | 6 bytes OUT |
| `0x220018` | `0x40` (host-to-device, vendor, device) | `0x02` | `0x0000` | `0x0000` | 6 bytes OUT |
| `0x22001C` | `0xC0` (device-to-host, vendor, device) | `0x03` | `0x0000` | `0x0000` | 2 bytes IN |
| `0x220020` | `0xC0` (device-to-host, vendor, device) | `0x04` | `0x0000` | `0x0000` | 2 bytes IN |
| `0x220024` | `0xC0` (device-to-host, vendor, device) | `0x05` | `0x0000` | `0x0000` | 2 bytes IN |

`VICCTR.dll` and both model DLLs pass identical input and output buffer sizes to
`DeviceIoControl` because these are buffered Windows IOCTLs. That Windows detail
does not add a second USB data stage: request 1 and 2 are USB OUT transfers, and
request 3 through 5 are USB IN transfers.

## Command header

**Verified:** requests 1 and 2 carry exactly six bytes:

```text
offset  size  type       meaning
0x00    2     uint16_le  command ID
0x02    4     uint32_le  total bulk payload length
```

For example, both information queries request a 64-byte receive:

```text
GetConfigInfo:   18 00 40 00 00 00
GetHardwareInfo: 19 00 40 00 00 00
```

The header declares the total bulk length, not the size of the next chunk.

## Generic receive sequence

**Verified:** the receive helper at `VicTwo.dll` `0x10003220` performs this
sequence:

1. Send the command header with control OUT request 1.
2. Before each bulk chunk, poll control IN request 3 for a little-endian 16-bit
   transfer-state value.
3. When the state permits progress, read from the bulk-IN pipe.
4. Continue until the declared number of bytes has been accumulated, accepting
   partial positive-length reads.
5. Issue control IN request 4 and return its little-endian 16-bit completion
   value to the caller.

Each bulk read is bounded to `min(bytes_remaining, 131072)`. The Windows driver
may internally stage that request further, but 128 KiB is the model DLL's
verified application-level maximum.

The equivalent libusb operation skeleton is:

```python
header = command.to_bytes(2, "little") + length.to_bytes(4, "little")
ctrl_out(0x40, 0x01, 0, 0, header)
while received < length:
    state = u16le(ctrl_in(0xC0, 0x03, 0, 0, 2))
    # Apply the bounded status policy below.
    received += bulk_read(discovered_bulk_in, min(131072, length - received))
completion = u16le(ctrl_in(0xC0, 0x04, 0, 0, 2))
```

This is a representation of verified operations, not executable production
code. A modern implementation must additionally enforce exact control-transfer
lengths, finite per-operation timeouts, an overall deadline, and cancellation.

## Read-only commands `0x18` and `0x19`

**Verified:** both exported information functions use the generic receive
sequence with an expected bulk length of exactly 64 bytes:

| Export | Command | Bulk direction | Exact length | Required completion |
| --- | --- | --- | --- | --- |
| `GetConfigInfo` at `0x10007D60` | `0x0018` | IN | 64 bytes | `0x0000` |
| `GetHardwareInfo` at `0x10007BC0` | `0x0019` | IN | 64 bytes | `0x0000` |

Both functions reject a failed receive helper or a nonzero request-4 completion
value. The field-level interpretation of the 64-byte responses depends on the
model/hardware discriminator and remains Phase 5 work. Phase 2 establishes only
the safe raw transaction.

## Transfer-state and completion behavior

The following behaviors are **verified** at `VicTwo.dll` `0x10003110` and
`0x10003220`:

| Request-3 value | Legacy behavior | Safe modern interpretation |
| --- | --- | --- |
| `0x0003` | Sleep 100 ms, then poll again within the retry bound | Busy/not ready |
| `0x0001` | Do not perform the next bulk operation | Transfer failure (specific name unknown) |
| `0x0002` | Do not perform the next bulk operation | Transfer failure (specific name unknown) |
| Any other value | Proceed with the next bulk operation | Only `0x0000` should initially be accepted by the modern client |

The legacy retry-limit constant is 1000. Because the loop increments the poll
counter before comparing it, its exact off-by-one behavior can issue a 1001st
poll before failing. It sleeps 100 ms for every busy response, including the
last one. A modern client should preserve the approximately 100-second upper
bound while expressing it as an explicit deadline rather than copying the
off-by-one behavior.

Request 4 returns a completion/result word. **Verified:** commands `0x18` and
`0x19` require `0x0000`; nonzero values are failures. The specific names of
other completion values are unknown.

If request 1/2 fails, the helper fails without querying completion. If request 3
fails, the retry bound is exceeded, request-3 returns 1 or 2, a bulk operation
returns zero, or cancellation is noticed, the helper leaves the data loop and
still issues request 4. The legacy helper's Boolean return then reflects whether
that final control request succeeded; callers also inspect the returned result
word. A modern client must separately track transport success, exact byte count,
cancellation, and device completion instead of collapsing them into one Boolean.

## Generic send sequence

**Verified, documented for future work but not executed:** the send helper at
`VicTwo.dll` `0x10003110` mirrors receive:

1. Send `[command:uint16_le, length:uint32_le]` with control OUT request 2.
2. Poll control IN request 3 before every bulk chunk.
3. Write up to 128 KiB to the bulk-OUT pipe and accumulate positive partial
   writes until the declared total has been sent.
4. Query the final 16-bit result with control IN request 4.

No modern write implementation should be enabled from this specification alone.
The backup and guarded-write gates in the roadmap still apply.

Phase 8 subsequently traced the higher-level ordinary write path. It uses one
segmented command `0x101b`, sends eight ordered byte ranges, and makes one final
request-4 query; no separate ordinary commit or abort request exists in the
host code. A command `0x101d` found in the distinct unlock workflow is not a
proven general commit. See `analysis/phase-8-write-transaction.md` for the
evidence, cancellation boundary, and remaining safety blockers.

### Selected operation versus physical transfer scope

The owner reports that the legacy Manager warns that a selected-file transfer
takes approximately the same time as an all-file transfer. The exact Japanese
wording is not preserved, so this remains a corroborating UI observation rather
than a verbatim software artifact. It agrees with the captured ordinary-write
structure: selection determines the logical mutation, while `0x101b` carries
the complete prospective dynamic model in its model-dependent ranges rather
than only the selected file payload.

Accordingly, **selected** describes the intended content change, not a
payload-sized physical patch. A modern selected add, replacement, or delete
must be presented as rebuilding and writing one complete candidate library
image, followed by a complete read-back verification. Transfer duration and
progress must not be estimated from the selected source-file size alone. This
also reinforces the fresh-backup, indeterminate-interruption, and no-automatic-
retry requirements for every ordinary write.

## Cancellation and errors

**Verified:** `VICStopTransfer` sets a flag at offset `0x18` in the open-device
context. The send and receive helpers test it before each request-3/bulk
iteration. They do not send a distinct cancellation control request. After
noticing the flag they leave the loop and query request 4.

The old path uses synchronous `DeviceIoControl`, `ReadFile`, and `WriteFile`.
There is no application-level finite timeout visible in these helpers, and the
flag cannot interrupt a synchronous call already blocked in Windows. This is a
legacy limitation, not behavior to reproduce. The modern transport needs finite
USB timeouts, a cancellable outer loop, and clear distinction between timeout,
disconnect, short transfer, device status, and user cancellation.

Pipe recovery operations exist in the driver, but neither `VicTwo.dll` nor its
normal send/receive helpers invoke the reset-pipe, reset-device, or alternate-
interface IOCTLs. Recovery policy therefore remains inferred and should not be
triggered automatically during the first read-only implementation.

## Unknowns and Phase 3 decision

- Request 5 (`bRequest = 5`) is implemented by the driver and wrapped by
  `VICCTR.dll`, but no shipped `VicTwo.dll` path uses it. Its meaning is unknown
  and it must not be sent.
- The human-readable meanings of request-3 values 1 and 2 are unknown, although
  their failure behavior is verified.
- The human-readable meanings of nonzero request-4 results are unknown.
- Alternate setting 1 is present but unused by the shipped VNW-V15 path.
- The 64-byte information-response field names are not yet fully verified.

None of these unknowns blocks raw read-only commands `0x18` and `0x19`. A Windows
traffic capture is therefore not required before implementing those two queries.
A capture remains conditionally useful before full backup support and required
before relying on any ambiguous write, cancel, or recovery behavior.

## Reproducing the static analysis

With LLVM `objdump`, the principal evidence can be revisited without executing
the legacy software:

```sh
shasum -a 256 VICUSB.sys VICCTR.dll VicTwo.dll
objdump -t VICUSB.sys
objdump -d -Mintel VICUSB.sys
objdump -d -Mintel VICCTR.dll
objdump -p VicTwo.dll
objdump -d -Mintel VicTwo.dll
```

Relevant locations:

- `VICUSB.sys`: `ProcessIOCTL` RVA `0x1270`, `SelectInterface` RVA `0x0710`,
  `ResetPipe` RVA `0x08A4`, `StagedReadWrite` RVA `0x15F4`.
- `VICCTR.dll`: IOCTL wrappers `0x10001933` through `0x10001C85`, and
  `VICOpen` at `0x10002237`.
- `VicTwo.dll`: control wrappers `0x10002E70` through `0x10002F8F`, bulk
  wrappers `0x10002F90` and `0x10002FD0`, send helper `0x10003110`, receive
  helper `0x10003220`, and information exports `0x10007BC0` and `0x10007D60`.

Preserve the input hashes when comparing another installer or driver revision;
addresses and behavior must not be assumed identical across revisions.
