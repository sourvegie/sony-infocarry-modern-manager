# P18-043 bounded disposable root-TXT Delete validation

**PREPARATION ONLY — no physical operation is authorized by this document.**
Final independent R3 and GUI visual checks are still outstanding; do not run
this procedure until they complete. Use the final reviewed code head from the
P18-043 delivery record. Stop if the
installation-wide lock or sender marker is active; do not clear it manually.
Never use personal files, interrupt a write, restore, or automatically retry.

1. Obtain separate owner authorization for fixture placement. Before placement,
   capture and verify a complete eight-object VNW-V15 backup and confirm that
   both reserved fixture paths are absent. Place only the two ASCII TXT files
   defined by the [fixture manifest](phase-18-p18-043-disposable-delete-fixtures-20261010.json),
   using an already reviewed native/placement procedure. This task adds no
   fixture-placement writer. Verify exact payloads and unaffected content after
   placement. Close the legacy Manager before opening the modern Manager.
2. Obtain a new operation-specific owner authorization for **A once**. The
   explicit validation launcher is below; command-specific out-of-sandbox
   permission must cover its VNW-V15 read/write access. This grants no other
   device action. Ordinary transfer has no configured runtime in this mode.
3. In Device Library, use **Back Up** to obtain the fresh displayed complete
   baseline. Select `IC_P18_043_DELETE_A.txt`, click **Delete**, then review one
   **Delete / Cancel** dialog. Preparation obtains another complete backup and
   native capacity, admits only the exact selected row/path/payload, rejects
   references, active Marks and unsupported structure, and freezes the operation.
   Stop on any refusal; do not alter/clear protected state merely to proceed.
4. Confirm **Delete** once. Keep the device connected and the window open.
   Execution revalidates complete state/capacity without rebinding, consumes one
   durable claim and records the sender marker before its single guarded send.
   There is no cancellation or automatic retry after confirmation starts the
   guarded operation. Require native integer `0x0000`, complete independent
   post-backup, sole path removal, unchanged survivor prefixes/payloads/timestamps,
   protected state and checksum, durable terminal resolution, and refreshed
   Device Library before declaring success.
5. Preserve the complete evidence directory and immutable result/terminal
   records outside Git. Independently rehash archives/artifacts and verify the
   actual readback, claim consumed, marker resolved and lock state. No independent
   USB trace should be claimed unless separately captured. A nonzero, missing,
   ambiguous, interrupted or failed verification outcome stops the experiment
   with no retry; preserve evidence and use read-only diagnosis under existing
   safety rules. Backup is not undo.
6. Only if A verified successfully and the owner separately authorizes **B once**,
   repeat steps 2–5 with B and its exact launcher target. At most **two deletes**
   total. A has a 32-byte payload; B has 51 bytes and exercises a different
   four-byte content alignment. Both require the evidenced 32-byte native TXT
   prefix and known read/unread flags. This bounded proof does not automatically
   enable arbitrary TXT, BMP, nested files, folders, VNW-V10 or recovery.

After separate approval, A's launcher is:

```sh
PYTHONPATH=src .venv/bin/python scripts/experimental_root_txt_delete.py --allow-write --manager-validation-target 'root\IC_P18_043_DELETE_A.txt'
```

For B, substitute only `root\IC_P18_043_DELETE_B.txt` after its separate approval.
No hash or approval phrase is typed in the Manager: **select → Delete → confirm**.
The launcher and sealed bundle permit only the named disposable and exact
manifest payload; other files, including the old experimental fixture, stay
unavailable in validation mode. General root-TXT execution remains disabled
until a later reviewed, owner-accepted capability promotion incorporates the
actual results. Do not infer success or widen admission from a fake transport.
