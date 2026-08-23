# Phase 1 USB Descriptor Evidence

Status: verified from the connected Sony InfoCarry VNW-V15 on 2026-08-19.

Only standard USB read requests were used:

- `GET_DESCRIPTOR(Device)`
- `GET_DESCRIPTOR(Configuration)`
- `GET_INTERFACE(interface 0)`

No InfoCarry application command, vendor-specific request, bulk transfer, interface change, or device write was performed.

## Environment

- macOS/Darwin on Apple Silicon
- libusb 1.0.30 from Homebrew
- PyUSB 1.3.1 in the project `.venv`
- Device enumerated as bus 2, address 4 during this observation; these numbers are temporary and must not be hard-coded.

## Device Descriptor

| Field | Verified value |
| --- | --- |
| Vendor ID | `0x054C` (Sony) |
| Product ID | `0x001E` |
| USB version | `0x0100` (USB 1.0 descriptor; full-speed connection) |
| Device version | `0x0100` |
| Device class/subclass/protocol | `0x00 / 0x00 / 0x00` (defined at interface) |
| Endpoint-zero maximum packet | 8 bytes |
| Configurations | 1 |
| Manufacturer/product/serial strings | None |

Raw 18-byte descriptor:

```text
12 01 00 01 00 00 00 08 4c 05 1e 00 00 01 00 00 00 01
```

SHA-256 of raw bytes:

```text
be73294d6d5caf2e0f339a33088ea2eec59abc630139c67ba0947a9bae7f5608
```

## Configuration Descriptor

| Field | Verified value |
| --- | --- |
| Configuration value | 1 |
| Total descriptor length | 55 bytes |
| Interfaces | 1 |
| Attributes | `0x80` (bus powered) |
| Maximum power | 100 mA |

Raw 55-byte descriptor tree:

```text
09 02 37 00 01 01 00 80 32
09 04 00 00 02 ff 00 ff 00
07 05 01 02 40 00 00
07 05 82 02 40 00 00
09 04 00 01 02 ff 00 ff 00
07 05 81 02 40 00 00
07 05 02 02 40 00 00
```

SHA-256 of raw bytes:

```text
8863a7f476eca4c672111c981593011c65bd8426b62ec08e02e249d590558a08
```

## Interface and Endpoint Map

Interface 0 is vendor-specific: class `0xFF`, subclass `0x00`, protocol `0xFF`.

| Alternate setting | Active during observation | Endpoint | Direction | Type | Maximum packet |
| --- | --- | --- | --- | --- | --- |
| 0 | Yes | `0x01` | OUT | Bulk | 64 bytes |
| 0 | Yes | `0x82` | IN | Bulk | 64 bytes |
| 1 | No | `0x81` | IN | Bulk | 64 bytes |
| 1 | No | `0x02` | OUT | Bulk | 64 bytes |

Standard `GET_INTERFACE` returned alternate setting 0. Therefore the current/default transport pair is bulk OUT `0x01` and bulk IN `0x82`.

The purpose of alternate setting 1 is not yet verified. Phase 2 must determine whether the Windows driver ever selects it and whether it corresponds to a different hardware generation or transfer mode.

## Reproducible Fixture

The exact raw descriptors and active alternate setting are stored in:

```text
tests/fixtures/infocarry_usb_descriptors.json
```

Fixture file SHA-256:

```text
204131a803be6b42c45c73043246195cc6c05610e8349334847434224002aeea
```

The offline parser tests verify both alternate settings, endpoint directions, transfer types, packet sizes, and malformed-length rejection.
