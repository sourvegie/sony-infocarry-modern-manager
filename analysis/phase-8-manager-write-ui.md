# Phase 8 — Manager write-producing UI evidence

Date: 2026-08-21

This note corrects the earlier assumption that the legacy manager requires a
built-in memo editor. Static inspection of the preserved resource DLL shows
that the manager is a transfer-area browser with explicit send commands. No
UI action was executed while preparing this note.

Evidence files:

- `icmres.dll` SHA-256 `94c6e123514d67d88ed17907c9a8f60e45d787180147d9018f067c1f0ad6ee15`
- `infoCarryManager.exe` SHA-256 `a195c898de9f619a9978ba9bb8bc71c18692bf28cfca915ea0b747edc4ee4d76`

## Verified resource strings

The preserved `icmres.dll` contains the following menu/context labels:

| Japanese label | Conservative meaning | Safety relevance |
| --- | --- | --- |
| `転送` | Transfer | Parent menu |
| `送信` | Send | Device-changing branch |
| `一括送信` | Send all | Warning text says it erases all device data before sending all carrying-area data; avoid for capture |
| `選択送信` | Send selected | Candidate for a single-item write capture |
| `受信` | Receive | Host-side receive branch |
| `一括受信` | Receive all | Host-side destructive replacement of the carrying area; not needed |
| `選択受信` | Receive selected | Safe read/receive candidate |
| `infoCarry端末へ送信` | Send to InfoCarry terminal | Context-menu send label |
| `転送元フォルダ` | Transfer-source folder | Folder-selection workflow |
| `簡易メモ` | Simple memo | One of the manager's content categories |

The same resource contains status and warning text for “sending data to the
terminal,” successful/failed send, and a prompt to select the transfer-source
folder. The manager executable imports `VICSendData`, matching the static
write path already documented in `phase-8-write-transaction.md`.

## Revised capture plan

The test item does not need to be authored in a memo editor. When a write
capture is explicitly approved, the safer candidate is:

1. Use the manager's existing carrying-area/transfer-source view.
2. Select exactly one already-present, non-sensitive small item, preferably a
   `簡易メモ` item.
3. Use `転送 → 選択送信` or the equivalent `infoCarry端末へ送信` context action.
4. Capture that one operation and wait for the manager's success message.

Do **not** use `一括送信`; its embedded warning explicitly describes erasing
all InfoCarry data before repopulating it. Do not create or rename files in the
transfer-source directory until the manager's accepted input format is
confirmed.

The labels prove that a write-producing UI exists in the shipped manager, but
they do not prove which screen exposes it in the user's current layout. A
screenshot is only needed if `転送 → 選択送信` and the terminal context action
are absent or disabled after a normal receive session.
