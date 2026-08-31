# P17-003 — guarded single prepared-package candidate and preflight bridge

Date: 2026-08-31
Status: **READY_FOR_HARDWARE_TEST — host-only preparation; stop before hardware**
Risk: **R3 — device/safety critical**

## Boundary

P17-003 bridges exactly one explicitly imported, fully revalidated P17-002
Library package into the existing ordered multi-child candidate, authorization,
independent read-back, and fake-host workflow. It does not detect a device,
open USB, capture a backup, query capacity, authorize a live operation, or send
`0x101b`. The normal CLI and ttk application do not import this bridge and no
transfer control was added.

The only supported content profile is one root-level folder with exactly these
three direct children in manifest order:

```text
root\<manifest folder>\01-introduction.txt
root\<manifest folder>\02-page-01.bmp
root\<manifest folder>\03-ending.txt
```

The TXT children use the existing strict UTF-8/CP932/CRLF authoring boundary.
The BMP child uses the validated 237 x 320, 1-bit, uncompressed Windows BMP
profile and the native 16-byte wrapper template established by P16-001. This
is experimental host readiness for the exact profile, not generalized package
compatibility.

## Implementation

`src/infocarry/prepared_library_package_bridge.py` provides the isolated
bridge. Its builder accepts one `LibraryCatalog` and one item ID, rejects plain
source-file items, and re-loads the selected package through the authoritative
P17-002 importer before candidate construction. It requires the exact
TXT/BMP/TXT names and order, checks the catalog's package reference against the
fresh manifest, and uses the existing
`build_prepared_multi_package_candidate()` rather than duplicating native
record construction. Before construction, the bridge also requires the exact
reviewed P16-001 native template blob SHA-256
`6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b`; the
generic builder remains reusable for its own offline fixtures, but an
unreviewed template cannot enter this R3 bridge.

The candidate audit and authorization bind:

- Library format/version, catalog path and full catalog hash, selected item ID
  and item-record hash;
- package contract, non-owning package root/manifest paths, manifest hash, and
  the full ordered child table with source/prepared paths, kinds, sizes, and
  source/prepared payload hashes;
- the Library item's canonical package source path/name/hash/size, observed
  manifest hash/size, and latest source observation;
- the existing device identity, verified backup/model hashes, exact native
  TXT/BMP template blob/path/prefix hashes, destination paths/record offsets,
  fixed-state hashes and policy, parsed native `0x0019` capacity evidence,
  timestamp policy, candidate/transaction hashes, and expected additive
  post-state; and
- the established exact multi-child confirmation phrase and no-retry policy.

The imported package now retains its signed manifest hash as a separate
verification binding because its reconstruction objects use archive-local
source paths. This does not rewrite or reserialize the manifest and preserves
the existing builder behavior for newly prepared packages.

`GuardedPreparedMultiPackageWorkflow` gained only optional explicit template
paths and an isolated candidate-enrichment hook. P17-003 uses those options to
rebuild the Library-enriched candidate through the existing fake transport
workflow. It still requires `fake_transport=True`, permits one injected send,
accepts only integer completion `0x0000`, performs independent post-backup
read-back, and reports cancellation before start separately from terminal
indeterminate failure after transaction start. No live adapter was added.

## Evidence classification

### Verified offline

- The selected item must be one P17-002 `prepared_package` record in current
  ready/present/prepared state; a plain TXT Library record cannot enter this
  bridge.
- The importer revalidates the signed manifest, source archive, prepared
  children, path containment, source/prepared hashes and sizes, strict TXT
  rules, BMP profile, and explicit order before candidate construction.
- The bridge requires exactly the reviewed TXT/BMP/TXT profile and reuses the
  exact reviewed P16 native template bytes and existing candidate/state
  construction.
- The candidate rejects an existing destination, malformed or unsupported
  backup/fixed state, missing or mismatched parsed native capacity evidence,
  template drift, source drift, and any unexplained shared-record difference.
- Existing records, payloads, timestamps, unknown record bytes, supported read
  state, and fixed-state semantics are protected by the existing candidate and
  independent verifier. The additive folder and ordered child delta is checked
  offline.
- The sealed report is hash-only with respect to candidate/payload bytes. It
  carries hashes, paths, sizes, profile, policy, and expected post-state, not
  raw candidate or source payload bytes.
- Candidate and authorization tampering, manifest drift, catalog
  source/manifest drift, plain-item selection, profile/order mismatch,
  reviewed-template-byte drift, destination conflict, cancellation before
  send, immutable sealed-report behavior, and successful one-shot fake-host
  read-back are covered by focused tests.
- The existing ordered-package fake workflow coverage remains in force for
  timeout, disconnect, missing/malformed/nonzero completion, post-backup and
  read-back failure, and second-send refusal; P17-003 invokes that workflow
  only through an injected fake boundary.

### Observed or human evidence

None for P17-003. No hardware, USB, legacy Manager, external evidence, or
`InfoCarry-Toolkit` checkout was accessed or modified.

### Inferred

The P17-002 non-owning package directory is a suitable source boundary for
this exact host candidate because the importer revalidates all package files
and the bridge binds both the catalog record and signed manifest. The existing
P16 package/state model is reusable for this exact profile.

### Unresolved and deliberately disabled

- physical compatibility of a Library-selected package under a future live
  operation;
- fresh live device detection, complete backup, native capacity response, and
  target absence for a future operation;
- native numeric completion decoding, interrupted-write recovery, arbitrary
  display-history/package behavior, nesting, batching, and synchronization;
- any profile other than exactly TXT/BMP/TXT with the named children; and
- normal GUI/CLI transfer exposure or a live sender in this bridge.

## Validation and disposition

The focused P17-003 bridge tests cover deterministic Library/catalog and
manifest bindings, hash-only sealing, exact profile/order/template and
destination checks, manifest drift, authorization tampering, source drift,
safe pre-send cancellation, and one-shot fake-host success with independent
read-back. The existing ordered-package tests continue to cover the remaining
post-start terminal/no-retry classes.

Final test, hygiene, excluded-content/history audit, and independent R3 review
results are recorded in
`analysis/phase-13-p17-003-r3-review-20260831.md` at the commit boundary.

P17-003 is **READY_FOR_HARDWARE_TEST** only for this host-prepared bridge. A
later separately briefed task must obtain a new fresh read-only device
preflight and operation-specific owner approval before any device-changing
operation. This task performed no hardware access and does not solicit or
consume live approval.
