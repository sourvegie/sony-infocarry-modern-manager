# P18-019 — Fresh Capacity Propagation Closure

Status: **COMPLETE** (host-side product gating correction)

Canonical base: `c3fd0c93f72730650c52a7e8475e0d8a651646b2`

Branch: `task/P18-019-fresh-capacity-propagation`

## Scope

P18-018 obtained valid fresh read-only VNW-V15 capacity and backup evidence,
but the normal ttk/facade path retained its earlier offline queue plan. That
plan had no `available_capacity_bytes`, so it remained `queue_ready = false`
with a stale capacity blocker. P18-019 closes that host-side propagation gap.

The correction does not authorize or perform a device operation. It does not
change the native sender, transaction protocol, operation identity, claim
store, indeterminate-write lock, or terminal verifier.

## Implementation

The canonical `build_library_transfer_queue_plan` now accepts the typed
`NativeCapacityResponse` used by the reviewed live preflight. It derives the
available value from that response, requires a verified backup with the same
VNW-V15 identity, rejects conflicting scalar values, and records the native
`0x0019` source, evidence version, response hash, and device identity in the
queue plan. Offline capacity inputs remain explicitly labeled as offline and
cannot create a live operation.

After the existing read-only preflight completes, the product facade rebuilds
the same canonical queue plan from the preflight's verified backup and typed
capacity response. Readiness and the Experimental review are then recomputed
from that fresh plan. The prepared operation stores the fresh plan and hashes
it for final execution-time consistency checks. The ttk handler adopts that
fresh plan/readiness state, so the displayed review and any later action refer
to the same capacity-cleared plan rather than the stale offline plan.

Insufficient, missing, malformed, mismatched, or stale evidence remains
blocked before claim consumption or sender reachability. No historical
P18-015/P18-018 scalar or operation identity is accepted as fresh evidence.
The exact boundary remains one explicitly selected VNW-V15 root package with
TXT → BMP → TXT children, one target, no overwrite/delete/nesting/merge, and
no retry. VNW-V10 remains **UNCHARACTERIZED / READ-ONLY DISCOVERY REQUIRED**.

## Validation

New and retained host-only coverage proves:

- offline review without fresh capacity remains blocked;
- typed fresh capacity propagates into the normal queue/readiness/review;
- queue readiness is recomputed and the fresh native source/hash is recorded;
- insufficient, missing, malformed, mismatched, stale, and changed-plan
  inputs fail closed;
- exact package, historical-identity, ttk reachability, claim, marker, and
  sender protections remain intact.

Focused capacity/readiness/facade/UI suites passed. The complete portable
Python 3.12 suite, compilation, `git diff --check`, final-head macOS CI, and
final-head Windows CI are required at the reviewed commit and are recorded in
the task report/PR.

No physical device was connected or used by this task. Real counters remain:

```text
device-changing operations = 0
real sender calls          = 0
real 0x101b                = 0
real claims consumed       = 0
real marker mutations      = 0
real lock mutations        = 0
```

P18-018 remains the historical safe pre-write stop. This task does not reuse
its approval or authorize another physical validation. After P18-019, stop
for PM disposition; any later physical attempt requires its own authorization
and procedure.
