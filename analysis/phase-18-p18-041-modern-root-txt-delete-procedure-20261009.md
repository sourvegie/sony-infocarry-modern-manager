# P18-041 exact modern root-TXT Delete operator procedure

Host-only preparation; physical use requires separate operation-specific owner
approval after independent R3 review. No physical operation is authorized by
this document. Use the reviewed branch/commit in the implementation record.

1. Close legacy Windows Manager and every other InfoCarry client. Keep the
   connected verified VNW-V15 available exclusively to this operation. Do not
   clear any existing canonical lock or unresolved sender marker. Confirm the
   intended disposable target is `root\IC_P18_041G_CLOCK_01.txt`.
2. Obtain separate owner approval for the one physical experiment and, when
   Codex runs it, narrowly scoped permission for this single command outside
   the sandbox with normal macOS permissions. Do not alter global settings.
   Work directory:
   `/external/local-path`.

   ```sh
   PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /external/local-path scripts/experimental_root_txt_delete.py --allow-write
   ```

3. The script uses the existing production runtime and canonical safety owner.
   It obtains native capacity and a new fresh complete eight-object backup.
   It requires the exact root TXT, 29-byte payload and SHA-256
   `9541c1b9d09ee7d4ab91c704755c4bea8b2022c3bb8f50aa15c1a990bf80c35d`.
   It derives and freezes one timestamp-preserving candidate/transaction,
   rejecting target references, active Marks and unsupported auxiliary state.
   Read the target and backup summary. On any refusal, stop; do not change
   the target, regenerate an approved candidate or use archived inputs.
4. Type exactly once:

   ```text
   DELETE IC_P18_041G_CLOCK_01.txt ONCE
   ```

   The internal fingerprint binds model, complete baseline state, capacity,
   exact target, candidate, transaction and verification/no-retry policy.
   Immediately before claim/sender, the existing read-only equivalence check
   captures current complete state and capacity. A reconnect is allowed only
   if that state is identical; no hardware serial number is required.
5. The existing guarded coordinator consumes one durable claim and persists
   its sender marker before exposing the sender. It permits one logical
   transaction/one `0x101b`, zero retries. Only explicit integer native
   `0x0000` plus a complete post-write backup and independent byte-exact
   candidate/fixed-state verification can produce verified success. All
   surviving payloads and serialized timestamp fields must be preserved.
6. Preserve the printed evidence directory, transaction ranges, canonical
   claim/marker records, completion and full post-backup outside Git. On
   interruption, missing/malformed result, disconnect, timeout or failed
   readback, stop and retain the global lock/unresolved marker as required.
   Never rerun automatically or treat an exception as proof of no write.
   Explicit nonzero terminal completion is failure, never success. Diagnose
   only with read-only evidence; no restore/recovery is authorized here.
7. Independently ingest and verify the actual terminal report and complete
   post-backup before declaring the experiment complete. A successful host
   simulation or structural match does not establish physical success.

The October 9 archive supports offline review only and is not reused as the
live baseline. No legacy-native candidate or transaction equality is claimed.
Backup preservation does not prove interrupted-write recovery or atomicity.
