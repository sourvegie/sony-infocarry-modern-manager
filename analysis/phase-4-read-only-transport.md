# Phase 4 Read-Only Transport Evidence

Status: verified offline and on the connected Sony InfoCarry VNW-V15 on
2026-08-20.

## Safety boundary

The hardware check used only device discovery, standard descriptor requests,
configuration inspection, `GET_INTERFACE`, interface claim/release, and resource
cleanup. The configuration and alternate setting were already the verified
values, so no change was necessary.

No InfoCarry vendor request (`bRequest` 1 through 5), bulk read, bulk write, or
application command was sent to the physical device. Commands `0x18` and `0x19`
remain Phase 5 work.

The production receiver has an empty command allowlist by default. The PyUSB
backend exposes `control_out`, `control_in`, and `bulk_read`; it deliberately has
no bulk-write operation. The CLI exposes only `detect`, `descriptors`, and
`open-check`.

## Implemented layers

- `infocarry.protocol` contains the six-byte header encoder, read-only receive
  state machine, strict status policy, explicit busy deadline, cancellation,
  exact-length validation, and 128 KiB maximum chunking.
- `infocarry.transport` validates `054C:001E`, reads and parses descriptors,
  selects interface 0 alternate 0 when necessary, discovers rather than
  hard-codes bulk endpoints, claims/releases the interface, and adapts PyUSB to
  the read-only protocol interface.
- `infocarry.usb_access` remains responsible for descriptor-only discovery.
- `infocarry.cli` adds `open-check`, which cannot construct or send an
  application command.

## Offline verification

Command:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Result: 20 tests passed.

The tests cover:

- exact little-endian header framing;
- denial of commands outside an explicit allowlist before any USB access;
- request-3 ready, busy, failure, and unexpected statuses;
- finite busy deadlines without real sleeps;
- request-4 completion handling;
- cancellation and best-effort completion query;
- short control transfers, empty reads, partial reads, and chunk bounds;
- strict VID/PID validation;
- descriptor-based endpoint discovery;
- alternate-0 selection;
- cleanup after successful open and failed interface claim;
- idempotent close; and
- absence of a bulk-write method on the PyUSB backend.

Python bytecode compilation also completed successfully with its cache directed
to a temporary writable directory.

## Hardware open/close verification

Detection outside the filesystem sandbox found:

```text
Sony InfoCarry 054c:001e on bus 2, address 4
```

Bus and address are temporary observations and are not stored in production
configuration.

Command:

```sh
.venv/bin/infocarry open-check --cycles 3
```

Result:

```text
Open/close cycle 1 succeeded: interface 0 alt 0, bulk OUT 0x01, bulk IN 0x82
Open/close cycle 2 succeeded: interface 0 alt 0, bulk OUT 0x01, bulk IN 0x82
Open/close cycle 3 succeeded: interface 0 alt 0, bulk OUT 0x01, bulk IN 0x82
```

All three sessions released the interface and disposed their PyUSB resources.
The device remained detectable throughout the repeated checks.

## Remaining boundary

Phase 4 proves safe detection, validation, interface ownership, endpoint
discovery, offline protocol behavior, and cleanup. It does not establish that
the device accepts the recovered vendor protocol. The first vendor request and
bulk read will occur only in Phase 5, initially for exact 64-byte command
`0x18`, with raw bytes preserved before parsing.
