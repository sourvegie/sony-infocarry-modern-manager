# Phase 14 — fake-only ordered package workflow

Date: 2026-08-28
Status: **Offline/fake workflow complete; no package device operation is authorized.**

`infocarry.prepared_multi_package_workflow` adds an explicit
`PreparedMultiFakeTransport` capability and a one-shot guarded workflow for
the existing ordered TXT or TXT/BMP package candidate. The workflow requires a
displayed candidate, detects the supported device identity, obtains parsed
native `0x0019` capacity evidence, captures a fresh complete backup, rebuilds
and compares the candidate, binds the ordered package authorization, sends at
most one simulated `0x101b` transaction, accepts only `0x0000`, and verifies a
complete independent fake post-operation backup.

The authorization binds ordered source hashes, all target paths and record
identities, package manifest, frozen timestamp, fixed-state hashes, native
capacity response and derived lengths, candidate hash, and transaction hash.
The transport has no USB import or live adapter. The explicit transport type
is a defense against accidental integration, not a security boundary; no live
adapter exists in this checkout.

Focused synthetic coverage includes successful independent read-back, missing
fake assertion, unmarked transport rejection, changed capacity response,
wrong device, pre-transaction timeout and cancellation, post-entry timeout and
cancellation, nonzero/missing/malformed completion, post-operation backup
failure, candidate/read-back mismatch, and zero automatic retry. A finite
cooperative deadline is checked at workflow boundaries and passed to the fake
sender; it cannot forcibly interrupt an arbitrary callback that hangs forever.

This slice does not claim multi-child legacy or live compatibility. Nested
folders, arbitrary record types, normal CLI/GUI actions, and any live package
operation remain prohibited. The portable suite is **507 passing tests with
three intentional evidence-dependent skips**.
