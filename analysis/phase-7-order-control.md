# Phase 7 — `order.vnw` static reconstruction

This note is based only on preserved `VicTwo.dll` code and data. No legacy
file was edited and no device operation was performed.

## Filename selection

The DLL stores these ANSI strings:

| Address | Value |
| --- | --- |
| `0x10015308` | `Software\\Sony Corporation\\infoCarry` |
| `0x1001531c` | `OrderControlFile` |
| `0x10015330` | `order.vnw` |

The helper at `0x10002d80` queries the registry path/value pair and falls back
to `order.vnw`. The call sites pass the resulting filename through the normal
memo-directory path builder, so this file is a manager-side control sidecar,
not a device protocol command.

## Writer evidence

The transfer/package writer around `0x10005e80` creates the selected file in
text mode (`"w"`) and writes the literal first line:

```text
;v1.0
```

The same routine uses `wsprintfA` with the formats `%s-%d.%s` and `%s\n`.
The `%s-%d.%s` call receives a base string, a one-based counter (the loop
increments its counter before formatting), and an extension string. The
result is used as a generated memo filename. The `%s\n` call receives a
pointer to the substring after the final backslash in the selected memo path,
so each control-file record is a basename, not the full path. The line writer
appends each name as a newline-terminated ANSI byte string. The manager
also opens generated memo files in read mode while constructing the transfer
set, so the control file is an ordering/name manifest rather than the memo
payload itself.

## Ordering and collision policy

The complete metadata image is parsed sequentially at `0x10006484`--
`0x100064ac`: the source advances by one 64-byte record and the destination by
one `0x16c`-byte in-memory object. The transfer loop starts its index at zero
at `0x100064fc` and increments it at `0x10006ca4`, returning to
`0x10006514` until the metadata-record count is reached. Selected manifest
entries are therefore appended in metadata-record order; there is no
alphabetical sort in this path.

The generated-file collision loop is also explicit:

1. Clear the suffix counter at `0x10006b3c`.
2. Increment it before formatting at `0x10006b66`.
3. Format `%s-%d.%s` at `0x10006b71`.
4. Open the candidate with mode `"r"` at `0x10006b80`.
5. When the open succeeds, close it and repeat at `0x10006b3e`.
6. When it fails, open the same candidate with mode `"wb"` at
   `0x10006b96`.
7. Strip the directory, format `%s\n` at `0x10006c7f`, and append the
   generated basename to the already-open `order.vnw` stream at
   `0x10006c93`.

Thus the manager chooses the first positive numeric suffix whose full path
cannot be opened for reading. This is not an atomic existence check: a path
that exists but is unreadable can be treated as available and subsequently
opened with truncating `"wb"`. The modern compatibility helper models the
verified selection loop through a caller-supplied read-probe callback and adds
a finite counter bound; it is not exposed as a safe filesystem writer.

## Current confidence and limits

The following are verified from static code:

- default filename and registry override;
- text mode creation;
- literal `;v1.0\n` preamble;
- newline-terminated name records;
- ANSI/CP932-compatible byte-string APIs (`wsprintfA` and `CreateFileA`
  wrappers);
- generated-name argument order and one-based counter;
- manifest lines use the basename after the final `\\`.

The reader at `0x10001b80` is also recovered. It opens the selected file with
the legacy text mode, reads at most `0x200` bytes per line (stopping at LF or
EOF), skips a line only when its first byte is `;`, and truncates every other
line at the first `:`, CR, or LF. It does not validate the `;v1.0` version
line. Empty non-comment lines therefore become empty entries, and an input
longer than `0x200` bytes without LF is processed as multiple chunks. These
rules are implemented in `src/infocarry/order_control.py`; the raw source is
always retained for exact forensic round-trips.

## Origin of generated names

The originating fields are now statically traced through both transfer-loop
copies (`0x10005fdb`–`0x100061c6` and `0x10006aa2`–`0x10006b77`). The legacy
64-byte record parser at `0x10001ab0` copies the record's name field at raw
offset `0x18` into the in-memory memo object at offset `+0x1c` (the object
stores the parsed record beginning at `+0x04`). It copies the three-byte ASCII
extension at raw offset `0x01` into object offset `+0x05`.

The later transfer loop performs these steps:

1. Copy the parent memo-directory path from the parent object path buffer at
   `+0x51` and append `\\`.
2. Use bounded concatenation helper `0x10009b20` to append the current memo
   name from object `+0x1c` (maximum 40 bytes, matching the record name field).
3. Test object byte `+0x1a` mask `0x07`. For an ordinary record (mask zero),
   copy exactly three bytes from object `+0x05` and NUL-terminate the local
   extension buffer. For a record with any of those low state bits set, append
   the constant extension `ecd` instead; the DLL obtains it through pointer
   `0x100151f8`, which targets the string at `0x100152ec`.
4. Call imported `wsprintfA` with `"%s-%d.%s"`, the constructed base path,
   a counter incremented before use (therefore one-based), and that extension.

Thus the generated path has the verified form
`<parent-directory>\\<record-name>-<one-based-index>.<extension>`, where
`<extension>` is the record's raw three-byte field when `(+0x1a & 0x07) == 0`
and the literal `ecd` otherwise. The exact `%s-%d.%s` call at
`0x10006b71` is reached after the zero-mask gate; the sibling path builder at
`0x100069d8` contains the explicit `ecd` override.
The subsequent `"r"` and `"wb"` opens operate on this generated path. The
separate `"%s\\n"` call still strips the final component before writing an
`order.vnw` manifest line, so the manifest contains the basename rather than
the full generated path.

This resolves the source-field question without requiring a device capture.
Metadata-order traversal and first-failed-read-probe collision handling are
now verified statically. The pure helpers `generated_transfer_basename()` and
`select_legacy_transfer_basename()` mirror those recovered rules without
opening or creating files. Full lossless `VICDATA` repacking remains
unverified; raw control text and every unresolved field must still be
preserved.
