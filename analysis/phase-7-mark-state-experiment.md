# Phase 7 — Controlled Mark-State Experiment

Date: 2026-08-21

## Safety and exact procedure

The user used only the normal InfoCarry interface on the already opened file
`簡易マニュアル/各部の名前とはたらき`. The user later clarified that the
choices were selected in this exact order:

1. first mark choice;
2. second mark choice;
3. third mark choice;
4. first mark choice again.

The device was then connected and the host made two complete backups using the
verified read-only workflow. No host write, restore, unknown command, or
control request was sent.

Evidence directories:

- `tests/output/phase-7-mark-1-after-1`
- `tests/output/phase-7-mark-1-after-2`

All eight corresponding raw objects in the two backups are byte-identical.
The dynamic blob SHA-256 remained
`f30153cf3c3a6dbc7c540b600bb2038f9b8b0344a16dbb3cf17eb1ddf0fa771b`,
the same as the stable post-read-state baseline. The repeated read caused no
further state change.

## Final mark response state

Compared with `tests/output/phase-7-read-state-after-2`:

| Command | Count | Metadata-relative offsets | Interpretation |
| --- | ---: | --- | --- |
| `0x001c` | 1 | `0x01c0` | verified first mark list |
| `0x001d` | 0 | none | semantic order not yet verified |
| `0x001e` | 0 | none | semantic order not yet verified |

The main blob, command `0x001b` display history, command `0x001f`, command
`0x0024`, and size probe were unchanged. Mark state is therefore carried in
the fixed responses rather than in the main content blob for this action.

The `0x01c0` response offset is relative to metadata start `0x40` and maps to
absolute record `0x0200`, the marked file. This coordinate system was verified
by the later cross-file Bookmark 2 experiment.

The `0x001d` and `0x001e` responses each contain `0x01c0` at raw offset `0x08`
despite declaring count zero. Those bytes lie in the unused tail and are not
entries. Their presence after the multi-choice sequence is consistent with a
shared response buffer retaining the last offset processed. This validates the
parser rule that only the first `count` offset slots are meaningful.

Because the user selected all three choices before returning to the first, this
first capture proves only the final first-mark state.

## Isolated second-mark state

The user then disconnected the device, opened the same file, selected only the
second mark choice once, and reconnected it. Two further complete read-only
backups were captured:

- `tests/output/phase-7-mark-2-after-1`
- `tests/output/phase-7-mark-2-after-2`

All eight corresponding objects are byte-identical across these two backups.
The main blob remained unchanged at SHA-256
`f30153cf3c3a6dbc7c540b600bb2038f9b8b0344a16dbb3cf17eb1ddf0fa771b`.
The final mark responses were:

| Command | Count | Metadata-relative offsets | Interpretation |
| --- | ---: | --- | --- |
| `0x001c` | 0 | none | mark 1 no longer active |
| `0x001d` | 1 | `0x01c0` | verified second mark list |
| `0x001e` | 0 | none | semantic order not yet verified |

This **verifies command `0x001d` as mark list 2**. It also verifies that
selecting mark 2 for this file replaced its previous mark 1 rather than adding
a second simultaneous mark.

## Isolated third-mark state

The user repeated the procedure on the same file, selecting only the third
mark choice once before reconnecting. Two further complete read-only backups
were captured:

- `tests/output/phase-7-mark-3-after-1`
- `tests/output/phase-7-mark-3-after-2`

All eight corresponding objects are byte-identical across these two backups.
The main blob again remained unchanged at SHA-256
`f30153cf3c3a6dbc7c540b600bb2038f9b8b0344a16dbb3cf17eb1ddf0fa771b`.
The final mark responses were:

| Command | Count | Metadata-relative offsets | Interpretation |
| --- | ---: | --- | --- |
| `0x001c` | 0 | none | mark 1 inactive |
| `0x001d` | 0 | none | mark 2 no longer active |
| `0x001e` | 1 | `0x01c0` | verified third mark list |

This **verifies command `0x001e` as mark list 3**. Together, the experiments
verify the complete command ordering:

- `0x001c`: mark 1;
- `0x001d`: mark 2;
- `0x001e`: mark 3.

They also verify that, for the tested file, selecting a different mark replaces
the previous mark rather than creating simultaneous memberships. Across every
state, the main content blob and display history remained unchanged; only the
three fixed mark-list responses changed.
