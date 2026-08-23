# Phase 7 — 32-byte text-view wrapper fields

Date: 2026-08-21

This note combines the preserved backup captures with a static trace of
`VicTwo.dll`. It does not send a device command and does not modify any
legacy or captured file.

## Static serializer

The helper at `VicTwo.dll` VMA `0x100042f0` receives a destination buffer, a
prefix length, and an internal memo object. Its text call sites use a length
of `0x20`; the image path uses `0x10`. The helper first fills the requested
prefix with `0xff` and then exposes these internal object fields at fixed
prefix offsets:

| Prefix offset | Size | Source in internal memo object | Status |
| ---: | ---: | --- | --- |
| `0x00` | 4 | calculated complement | verified checksum word |
| `0x04` | 1 | `+0x50` | verified copied flag/state byte; semantic bits unresolved |
| `0x05` | 1 | `+0x44` | verified copied byte when the serializer's state gate allows it |
| `0x06` | 2 | `+0x46` | verified big-endian 16-bit copy when enabled |
| `0x08` | 4 | `+0x48` | verified big-endian 32-bit copy when enabled |
| `0x0c` | 4 | `+0x4c` | verified big-endian 32-bit copy when enabled |
| `0x10`–end | — | none | remains `0xff` in this helper |

The helper checks bit 0 of the internal `+0x50` byte before copying the four
optional fields. That gate is a property of this manager-side serializer;
the device firmware's captured wrappers can retain non-`ff` optional fields
while the copied flag byte is still `0xfd`. The modern parser therefore
reports raw field offsets but does not apply the manager's gate when decoding a
captured prefix.

The checksum is computed over big-endian 32-bit words beginning at prefix
offset `0x04`. For a 32-byte prefix, the first word is:

```text
(-sum(words[1:]) - 8) modulo 2^32
```

This makes the complete eight-word sum `0xfffffff8`. The same rule explains
the all-`ff` 16-byte image prefix: its first word also evaluates to
`0xffffffff`.

## Captured confirmation

The stable unread text prefix is:

```text
01ffffff fd ff ffff ffffffff ffffffff ffffffffffffffffffffffffffffffff
```

The two files displayed during the controlled action retained the same field
locations while changing the calculated checksum and view-state words. For
example, the first file's prefix parses as:

| Field | Value |
| --- | --- |
| checksum word | `0x018cff0d` |
| internal `+0x50` byte | `0xfd` |
| internal `+0x44` byte | `0xff` |
| internal `+0x46` word | `0x0000` |
| internal `+0x48` dword | `0x007400f0` |
| internal `+0x4c` dword | `0xffffffff` |

The adjacent file has the same fixed bytes except for checksum and
`+0x48 = 0x003100f0`. Both prefixes have a valid calculated checksum and the
same full-word sum as the unread default. The native text payloads are
unchanged, so these fields are per-file rendered/current-view state rather
than content bytes. An offline sweep of all 19 preserved complete-backup
captures found 97 text prefixes in each capture; every one satisfies the
recovered checksum rule.

## Modern handling

`src/infocarry/view_wrapper.py` parses the fixed offsets and validates the
checksum without assigning cursor or scroll names. `BackupExporter` includes
the raw field map in each text-file manifest entry while still preserving the
original prefix verbatim. No write path synthesizes this state yet; a future
writer must obtain an exact state transition or deliberately use the legacy
default rather than guessing individual values.
