# Phase 7 — Controlled Bookmark-State Experiment

Date: 2026-08-21

## Safety and procedure

The user disconnected the InfoCarry, opened
`簡易マニュアル/各部の名前とはたらき`, returned to the beginning of the
file, selected the ordinary device menu item `しおり１をはさむ`, and
reconnected the device. The host then made two complete backups using only the
verified read-only workflow. No host write, restore, unknown command, or
control request was sent.

Evidence directories:

- `tests/output/phase-7-bookmark-1-after-1`
- `tests/output/phase-7-bookmark-1-after-2`

All eight corresponding raw objects are byte-identical across the two
captures. The dynamic blob SHA-256 remained
`f30153cf3c3a6dbc7c540b600bb2038f9b8b0344a16dbb3cf17eb1ddf0fa771b`.
Command `0x001b` display history, all three mark responses, command `0x0024`,
the size probe, and the main blob were unchanged. Only command `0x001f`
changed.

## Command `0x001f`

Before the action, its two groups of five big-endian dwords were both zero.
After setting Bookmark 1 they were:

1. `(0x000001c0, 0x00000140, 0, 0, 0)`
2. `(0, 0, 0, 0, 0)`

This **verifies the first group as Bookmark 1**. Later cross-file evidence
establishes the first value as a metadata-relative selected-file record offset;
`0x01c0 + 0x40` maps to absolute file record `0x0200`. The precise role of the
second value `0x0140`, and the three zero position/state values, remained
unresolved at this checkpoint.

## Isolated Bookmark 2 one page lower

The user then disconnected the device, reopened the same file, returned to its
beginning, scrolled down exactly one full page, selected `しおり２をはさむ`,
and reconnected it. Two further complete read-only backups were captured:

- `tests/output/phase-7-bookmark-2-after-1`
- `tests/output/phase-7-bookmark-2-after-2`

All eight corresponding raw objects are byte-identical across these captures.
The main blob remained unchanged at SHA-256
`f30153cf3c3a6dbc7c540b600bb2038f9b8b0344a16dbb3cf17eb1ddf0fa771b`.
Only command `0x001f` changed from the Bookmark-1-only state. Its groups are:

1. Bookmark 1: `(0x000001c0, 0x00000140, 0, 0, 0)`
2. Bookmark 2: `(0x000001c0, 0x00000140, 0, 20, 0xfff101be)`

This **verifies the second group as Bookmark 2**. The first group remained
unchanged, confirming that the two bookmark slots are independent. Both groups
share their first three values in this same-file experiment. Moving Bookmark 2
one page lower changed only its fourth and fifth values relative to Bookmark 1,
making those two dwords verified components of the saved line/page or render
position state. Their precise encoding remains unresolved; another controlled
position is required to establish the relationship.

## Bookmark 2 two pages lower

The user repeated the Bookmark 2 action after returning to the beginning and
scrolling down exactly two full pages. Two complete read-only backups were
captured:

- `tests/output/phase-7-bookmark-2-page-2-after-1`
- `tests/output/phase-7-bookmark-2-page-2-after-2`

All corresponding raw objects are byte-identical. Again, only command
`0x001f` changed and the main blob retained SHA-256
`f30153cf3c3a6dbc7c540b600bb2038f9b8b0344a16dbb3cf17eb1ddf0fa771b`.
Bookmark 1 remained unchanged. Bookmark 2 became:

`(0x000001c0, 0x00000140, 0, 40, 0xfff10448)`

The controlled positions therefore compare as:

| Position | Dword 4 | Dword 5 | Low 16 bits of dword 5 |
| --- | ---: | ---: | ---: |
| beginning | 0 | 0 | 0 |
| one page | 20 | `0xfff101be` | `0x01be` (446) |
| two pages | 40 | `0xfff10448` | `0x0448` (1096) |

Dword 4 advances by exactly 20 per full page. Both low-16-bit positions land
on valid CP932 character boundaries in the exact native text. At each offset,
the bytes begin the first visible wrapped line for the corresponding 20-line
or 40-line position. This is strong controlled evidence that dword 4 is the
rendered-line index and the low 16 bits of dword 5 are the source-byte offset
of that displayed line. The upper `0xfff1` tag is constant at both nonzero
positions but its meaning remains unknown. The beginning uses an all-zero
position sentinel rather than `0xfff10000`.

## Bookmark 2 in the adjacent file

The user then opened adjacent file `画面の名前とはたらき`, returned to its
beginning, and overwrote Bookmark 2 without changing Bookmark 1. Two complete
read-only backups were captured:

- `tests/output/phase-7-bookmark-2-file-2-after-1`
- `tests/output/phase-7-bookmark-2-file-2-after-2`

All corresponding objects are byte-identical. The main blob remained unchanged
at SHA-256
`f30153cf3c3a6dbc7c540b600bb2038f9b8b0344a16dbb3cf17eb1ddf0fa771b`.
Bookmark 1 remained `(0x01c0, 0x0140, 0, 0, 0)`, while Bookmark 2 became:

`(0x00000200, 0x00000140, 0, 0, 0)`

The first and second selected files have absolute exported record offsets
`0x0200` and `0x0240`. Subtracting metadata start `0x40` produces exactly the
bookmark dword-1 values `0x01c0` and `0x0200`. This **verifies dword 1 as the
metadata-relative selected-file record offset**. Display history changed from
leading values `(0x01c0, 0x0200)` to `(0x0200, 0x01c0)` and therefore uses the
same coordinate system. Dwords 4 and 5 returned to their zero beginning-of-file
sentinel. Dword 2 remained `0x0140` and dword 3 remained zero, so their roles
are not file identity or the tested vertical position.

## Static consumer confirmation

The preserved `VicTwo.dll` consumer at `0x10005a20` iterates exactly twice. It
matches group dword 1 against the current metadata-relative file record, then
copies group dwords 3 and 4 into the bookmark entry's two coordinate outputs.
It does not use dwords 2 or 5 in this reconstruction path.

Combined with the controlled text captures, this strongly identifies dword 3
as the horizontal coordinate (zero in every vertical text-scroll experiment)
and verifies dword 4 as the vertical rendered-line index. Dword 5 independently
preserves the tagged source-byte position used by the device. Dword 2 remains
constant `0x0140` in all tested text states and its role is unresolved, but it
is not needed by the legacy manager's bookmark-entry reconstruction path.
