# Phase 8 manager test 4 — disposable text record

Date: 2026-08-21

This is a read-only analysis of the new native capture and fixture copy. No
modern-tool USB transmission was performed, and the original capture and
fixture files were not modified.

## Preserved inputs

```text
${RESEARCH_ROOT}/usbsnifferlogs/03-manager-test/00-read-baseline.usblog
${RESEARCH_ROOT}/usbsnifferlogs/03-manager-test/01-selected-send.usblog
${RESEARCH_ROOT}/fixtures-3/
```

| input | size | SHA-256 |
| --- | ---: | --- |
| `00-read-baseline.usblog` | 2,318,627 | `2018cc0ef9fca5db8e760251244299a4a11ea45c46e3903b85e087658a47c1ec` |
| `01-selected-send.usblog` | 4,621,665 | `526b7864dbad26c7290faea7f77fe6cade35dfd4b0c1997b33ee8b7c1fe41cef` |

The baseline contains no ordinary host-to-device `0x101b` transaction, as
expected for a read-only baseline. The selected-send capture contains one
complete, parseable ordinary transaction.

## Selected-send result

| property | value |
| --- | --- |
| native transaction offset | `0x239d17` |
| declared length | `0x207e38` |
| native payload records | 524 |
| range lengths | `0x100, 0x40, 0xfec0, 0, 0x40, 0, 0, 0x1f7df8` |
| staging | `N=0`, `M=0x1f7e38` |
| decoded range-5 + range-8 length | 2,063,928 bytes |
| decoded range-5 + range-8 SHA-256 | `c86f5523565da644995c5a2c47ca7255fe18f70b374ad1c105c44a330e26940f` |

The decoded model blob is structurally valid: 366 metadata records and 309
reachable paths. It adds exactly one path to the previous read-back blob:

```text
root\\IC_TEST_01.txt
```

The new record is an ordinary unread `txt` file at metadata offset `0x01c0`,
with the native 32-byte prefix and a 41-byte CRLF payload:

```text
InfoCarry disposable test 01
Do not keep
```

Its payload SHA-256 is
`85c8e82f3547ace5c72f3f2c1c3817788cd134e4e6bbf4dca9032d4ca11e4c08`. All
previous reachable paths retain the same file contents and record shape as the
previous post-send read-back.

The transaction has been preserved as the offline-only artifact:

```text
analysis/phase-8-candidate-2/
```

Its manifest explicitly records `usb_transmission_performed: false`.

## Fixture observation

`fixtures-3/Backup/VICDATA.bin` is byte-identical to the earlier manager
source fixture (`72142be...b728`) and therefore does not contain `IC_TEST_01`.
The copied `VICMEM.bin` differs from earlier fixture copies, while `VICLV.bin`
and `order.vnw` are unchanged. These files are useful manager-side evidence,
but they are not a post-send device backup for this test.

## Fresh macOS read-back

After USB ownership was handed back to macOS, the toolkit created this new
read-only archive:

```text
analysis/phase-8-live-after-4/
```

Its dynamic `0x8004` blob is 2,063,928 bytes with SHA-256
`c86f5523565da644995c5a2c47ca7255fe18f70b374ad1c105c44a330e26940f`, exactly
matching the decoded range-5 plus range-8 blob from the selected-send capture.
The complete-backup freshness, device-identity, object-length, object-hash,
and structural gates all pass. Comparing this blob with the previous
post-send read-back finds one added reachable path—`root\\IC_TEST_01.txt`—and
zero shared content or record-shape changes.

This closes the capture/read-back evidence loop for the disposable manager
operation. The corresponding offline candidate remains at
`analysis/phase-8-candidate-2/`; its `usb_transmission_performed` flag is still
false because the modern sender has not been invoked.

## Fresh-state candidate normalization

The captured manager transaction's range 1 contains three stale bytes in the
fourth 64-byte state block: it carries `value_04=0x0001` and
`value_06=0x6e69`, while the fresh device response carries zero for both values
with the same count and record offset. Range 2 and the decoded model blob are
identical.

To avoid replaying that stale selection/mark metadata, the offline composer
rebuilt the candidate using the fresh `0x001b`--`0x001f` response state and the
accepted decoded `0x8004` blob. The normalized artifact is:

```text
analysis/phase-8-candidate-3/
```

Its concatenated transaction SHA-256 is
`d733869aa08e1aafdb790047a0b89413f0538b05eb13a5b64c4b66400f3f2491`. The
normalized candidate preserves the exact accepted blob, changes only those
three range-1 state bytes, and passes the fresh-backup write gate in offline
authorization tests. No USB transmission occurred.

## Safety decision and next handoff

This is the first capture that represents one genuinely disposable record, and
the fresh macOS read-back confirms it end-to-end. The normalized candidate is
the only candidate suitable for a future modern replay. It is still not
authorized for that device-changing operation: the existing write gate must be
explicitly approved at the final checkpoint. Until that approval is provided,
no modern write command is sent.
