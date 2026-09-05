# P18-008 — Durable cross-process one-shot execution claims

Date: 2026-09-06  
Base: canonical `main` at `9cf01f49404e354c3704fbc6508afa8f7d20c509` (merged P18-007 / PR #33)  
Branch: `task/P18-008-durable-one-shot-claims`  
Disposition: **READY_FOR_HARDWARE_TEST — HOST-ONLY; NO HARDWARE PERFORMED**

## Scope and safety boundary

P18-008 closes the P18-006 process-local one-shot claim gap. It does not
change candidate construction, the Oracle boundary, the exact reviewed
TXT/BMP/TXT capability shape, normal GUI/CLI reachability, or any physical
device behavior. No USB or device-changing operation occurred.

The property closed here is **at-most-one host execution claim per sealed
operation**, including after restart, abrupt process exit, and concurrent
independent processes. It is not a claim that the physical device transaction
occurs exactly once; physical interruption and atomicity remain separate.

## Durable claim architecture

`infocarry.execution_claim_store.PersistentExecutionClaimStore` is an
installation-stable injected dependency backed by Python standard-library
`sqlite3`. Its `execution_claims` table uses the exact
`preflight_seal_sha256` as the primary key. A direct transactional `INSERT`
followed by an explicit commit is authoritative; there is no check-then-insert
eligibility decision and no in-memory production fallback.

The store uses an explicit schema version and metadata format, validates an
existing database instead of rebuilding it, enables a bounded five-second
busy timeout, and sets `synchronous=FULL` with cross-platform DELETE
journaling. Commit, lock, path, corruption, schema, and binding failures fail
closed before any device callback.

Only hash and operational metadata are persisted: outer/core seals, candidate
and transaction hashes, authorization/baseline/capacity hashes, claim time,
claim ID, and sender attempt/incident metadata. Candidate and transaction
bytes are not stored.

The canonical live adapter requires both the injected durable claim store and
the existing persistent installation-wide indeterminate-write lock. The
guarded coordinator requires and passes the same store to the adapter.
`preflight_only=True` remains explicitly claim-free because it cannot reach a
sender.

## Sender-start crash boundary

The existing global lock was recorded only after an indeterminate exception,
which left a crash window around sender entry. The store therefore also holds
one singleton `sender_in_flight` marker. It is durably committed immediately
before entering the sender and carries the consumed claim, attempt ID,
incident ID, and evidence root.

| Crash/failure point | Durable disposition after restart |
| --- | --- |
| Immediately after claim commit | Claim tombstone remains; same sealed operation cannot claim again. No sender marker exists because sender was not entered. |
| During device detection | Claim remains consumed; no physical-write marker is needed. |
| During capacity query | Claim remains consumed; no physical-write marker is needed. |
| During fresh pre-write backup | Claim remains consumed; no physical-write marker is needed. |
| After candidate revalidation | Claim remains consumed; no physical-write marker is needed. |
| Immediately before sender entry | In-flight marker remains and the next guarded write promotes it to the existing global indeterminate lock. |
| During sender/USB transmission | In-flight marker remains; the next guarded write promotes it to the existing global lock. |
| After sender return before completion handling | In-flight marker remains; restart fails closed through the existing global lock. |
| During post-write backup | In-flight marker remains; restart fails closed through the existing global lock. |
| During read-back verification | In-flight marker remains; restart fails closed through the existing global lock. |

Normal verified terminal success and determinate sender outcomes resolve only
the sender marker; they never delete or reset the claim tombstone. An
abandoned marker is never cleared by PID, time, reconnect, VID/PID, bus, or a
new session. Normal marker resolution requires a store-issued live-process
sender handle. After a process crash, marker resolution is available only
after the existing reviewed diagnostic/clear binding has produced a typed
cleared lock record matching both incident ID and attempt ID; otherwise the
coordinator records the existing global lock and stops. Marker reads, state
transitions, and deletion validate every marker binding against its durable
tombstone.

## Host evidence

`tests/test_execution_claim_store.py` uses actual subprocess boundaries for:

- restart persistence;
- abrupt `os._exit` persistence; and
- a two-process same-seal race, requiring exactly one winner and one rejection.

Adapter and coordinator tests cover pre-callback claim ordering, storage
commit failure, cancellation, pre-send and candidate failures, missing
backend, determinate and indeterminate completion, marker resolution,
abandoned-marker promotion, post-backup/read-back failure, reconstructed
bundle replay, global-lock persistence, and the unchanged exact positive
control.

Local validation passes 90 focused claim/adapter/coordinator tests and the full
portable suite passes 746 tests with 3 intentional evidence-dependent skips.
`compileall` and `git diff --check` pass. The P18-008 PR has passing macOS and
Windows Python 3.12 offline checks in [workflow run 33976813020](https://github.com/sourvegie/sony-infocarry-modern-manager/actions/runs/33976813020).
Independent R3 re-review of `b41eccd` is PASS with no remaining P0/P1/P2
findings. The only correction round addressed
Windows SQLite/file-handle cleanup and prevented unproven generic marker
resolution by splitting terminal-handle and typed-diagnostic APIs.

## Capability and hardware boundary

The exact reviewed TXT → BMP → TXT shape remains the only relevant
physical-test candidate. The broader flat profile remains non-live,
hierarchical packages remain preview-only, VNW-V10 remains non-write-capable,
and normal GUI/CLI Send remains absent. No USB, `0x101b`, live transfer,
intentional interruption, or hardware test was performed. This record is
READY_FOR_HARDWARE_TEST for the exact reviewed TXT/BMP/TXT shape only; it is
not a claim that the physical transaction is atomic or recoverable.
