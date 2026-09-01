# P17-015 — Immutable Library-package operation bundle

Date: 2026-09-01
Risk: R3 — production live entrypoint, candidate binding, and one-shot write gate
Status: **READY_FOR_HARDWARE_TEST — host-only**

## Scope and historical trigger

P17-015 is an offline correction on PR #21. It preserves the P17-010
premature freshness-clock failure, the P17-012 sealed-report schema failure,
and the P17-014 safe wrong-baseline failure as historical records. P17-014
paired a valid sealed report with the older P17-012 baseline and stopped before
device access. No P17-015 hardware, USB, real sender, approval phrase, or
`0x101b` activity is permitted.

The correction removes manual cross-generation artifact pairing from the
production live call site. The live entrypoint now accepts one immutable
`infocarry-p17-015-library-package-operation-bundle-v1` object. Runtime
callbacks remain injected so host tests can exercise the real entrypoint with
fake hardware boundaries without importing or opening USB.

## Bundle contract

The framework-independent bundle is frozen and recursively immutable. Its
hash-only manifest binds:

- the sealed P17-013 report and exact report SHA-256;
- the report-selected baseline backup directory and exact manifest-byte
  SHA-256;
- the Library catalog, package manifest, reviewed template bytes, and native
  `0x0019` response bytes, each with path, length, and SHA-256;
- the selected Library item, exact Sony `054c:001e` identity, destination,
  explicit timestamp policy/value, confirmation policy/phrases, and OUT
  endpoint;
- the complete ordered package-child records, including source/prepared
  paths, kinds, names, sizes, and hashes;
- raw-state identity, parsed capacity response, candidate audit, candidate
  blob, prospective transaction, Library binding, core-seal, outer-seal,
  authorization, and expected-post-state hashes; and
- the three distinct non-overwriting fresh-before, post-operation, and
  result-manifest destinations.

The bundle manifest includes a self-hash and a fixed safety projection:
automatic retry is false, the maximum sender count is one, the only
transaction request is `0x101b`, and the only accepted completion is
`0x0000`. Candidate and transaction bytes are not stored in the bundle or
Git. The bundle loader rejects duplicate JSON keys, missing/unexpected
fields, malformed hashes, non-canonical paths, output collisions, and changed
artifact bytes.

Before any runtime callback, the P17-005 adapter resolves the bundle and:

1. verifies every bound artifact and the exact sealed-report/baseline path
   relationship;
2. re-verifies the complete baseline backup and raw-state identity;
3. parses the reviewed template and capacity response and reloads the
   catalog;
4. invokes the strict P17-013 sealed-report loader with those exact artifacts;
5. compares every copied package, Library, authorization, candidate,
   transaction, capacity, state, timestamp, and seal binding; and
6. rejects existing output destinations before device callbacks.

The runner then retains the established ordered detection/capacity/backup,
freshness, target-absence, candidate-reconstruction, authorization,
cancellation, one-shot, completion, post-backup, independent read-back, and
evidence-manifest controls. No fallback top-level transaction alias or
manually supplied catalog/report/backup/template/transaction is accepted at
the live call site.

## Host rehearsals and failure coverage

The actual exported production entrypoint was exercised through injected fake
boundaries:

1. nominal rehearsal A: one fake send, explicit integer `0x0000`, complete
   post-operation backup, independent read-back, and one sender call;
2. nominal rehearsal B: the same result with a separate fresh bundle and
   evidence destinations; and
3. preflight-only rehearsal: fresh revalidation reached the sender boundary
   with no backend, zero sender calls, and no send.

The focused matrix mutates or substitutes each artifact, scalar, package-child,
expected-post-state, output, and safety-policy member. It specifically
reproduces the P17-014 report/P17-012 baseline substitution against a separate
temporary baseline and proves rejection before detection, capacity, capture,
sender construction, approval consumption, or transmission. Existing tests
retain cancellation-before-start, timeout/disconnect, malformed/missing/
nonzero completion, post-backup/read-back mismatch, and second-send refusal.

Final host validation passed with 29 focused adapter tests, 51 focused
P17-003/P17-005/state/read-back regression tests, and 618 complete portable
tests with 3 intentional evidence-dependent skips. Compilation without
bytecode writes, `git diff --check`, the excluded-evidence/history audit, and
normal CLI/GUI import isolation also passed.

## Evidence classifications

- **Verified:** strict bundle self-hash and artifact verification; exact
  report/baseline pairing; complete baseline integrity and raw-state identity;
  catalog/package/template/capacity reconstruction; exact candidate,
  transaction, authorization, timestamp, fixed-state, display-history,
  target, and seal bindings; two nominal fake entrypoint runs with successful
  fake read-back; sender-boundary zero-send rehearsal; mutation/substitution
  rejection; one-shot/no-retry behavior; and GUI/CLI import isolation.
- **Observed:** the test fake backend recorded the expected one-send or
  zero-send call counts and the test archives were created at their fresh
  temporary destinations.
- **Inferred:** a later real operation can use the same single-bundle call
  boundary if it first performs a new fresh device/capacity/complete-backup
  preflight and obtains new exact owner approval.
- **Unresolved:** physical compatibility of the P17 Library source content,
  native numeric completion semantics beyond prior constrained evidence,
  interrupted-write recovery/atomicity, and any package shape outside the
  exact flat TXT/BMP/TXT profile.

## Disposition

P17-015 is **READY_FOR_HARDWARE_TEST** only for the exact reviewed Library
package profile, after independent R3 review, complete host validation, CI,
and exclusion audits. The next live task must create a new non-overwriting
fresh read-only preflight and request new operation-specific approval. This
record does not authorize hardware access or a device-changing transaction.
