# Phase 8 manager test 3 — selected manual item

Date: 2026-08-21

This note records the latest manager test as read-only evidence. No USB write
was issued by the modern toolkit, and all source captures and fixture files
remain untouched.

## Operator-selected item

The supplied screenshot identifies the selected manager item as:

```text
簡易マニュアル\\画面の名前とはたらき.txt
```

The fixture report independently resolves that path in `VICMEM.bin` to the
backup record at metadata-relative offset `0x0e80`. Its native text payload is
1,410 bytes and its payload SHA-256 is
`e8a388b9a11b28bfdd7e845b1d1ddf7ceab5396a9a76532eb82bde96cef5ff21`.

## New capture

The preserved native capture is:

```text
${RESEARCH_ROOT}/usbsnifferlogs/02-manager-test/01-selected-send.usblog
```

SHA-256: `da0a0eb7b4be0f61c2ab971d293c2b66d41eb96476b34cfaf6c4fc5e9e953995`

It contains one verified ordinary `0x101b` transaction:

| property | value |
| --- | --- |
| declared length | `0x207dac` |
| native payload records | 524 |
| range lengths | `0x100, 0x40, 0xfec0, 0, 0x40, 0, 0, 0x1f7dac` |
| staging | `N=0`, `M=0x1f7dac` |
| range-5 + range-8 combined length | `0x1f7dac` |

The offline artifact derived from this transaction is preserved at:

```text
analysis/phase-8-candidate-1/
```

Its manifest records `usb_transmission_performed: false`.

## Fresh device read-back

After macOS detected Sony `054c:001e`, a new read-only backup was created at:

```text
analysis/phase-8-live-before-1/
```

The backup passed the full freshness/hash/device-identity gate. Its dynamic
`0x8004` object SHA-256 is:

```text
51fb612e78369170feb1851c644f498350ab387a23722977168f862988036f11
```

The concatenation of captured range 5 and range 8 has exactly the same length
and SHA-256. This is a strong end-to-end consistency result: the selected-send
capture's resulting model blob is the same blob now read from the device.

The offline composer now reproduces the preserved candidate's complete eight
ranges from the decoded `range5 + range8` blob and the candidate's fixed range-1
and range-2 state bytes. In particular, the first 64 decoded bytes become
range 5 and the exact remainder becomes range 8; no extra transformation is
applied at that boundary. This confirms the split on a real manager-produced
candidate in addition to the synthetic regression cases.

Parsing the fresh blob finds the original pair plus two new records:

```text
root\\簡易マニュアル\\画面の名前とはたらき.txt
root\\簡易マニュアル\\各部の名前とはたらき.txt
root\\簡易マニュアル\\Copy of 各部の名前とはたらき.txt
root\\簡易マニュアル\\Copy of 画面の名前とはたらき.txt
```

The two added records preserve the original payloads byte-for-byte: the
`各部...` copy is 3,135 bytes and the `画面...` copy is 1,410 bytes. This shows
that the manager operation copied both manual records even though the supplied
screenshot highlights the latter. Therefore the captured transaction is
evidence of a completed legacy-manager operation, not a safe disposable
transaction to replay.

## Decision

The candidate is preserved and fully cross-checked offline. It must not be
replayed: doing so could create another copy or otherwise alter the tree. The
next write milestone remains a separately authored minimal record, preceded by
an automatic fresh backup and the explicit final `WRITE INFOCARRY` checkpoint.
