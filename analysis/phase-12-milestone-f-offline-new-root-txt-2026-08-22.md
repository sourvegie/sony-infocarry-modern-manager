# Milestone F — offline new root-level TXT candidate

Date: 2026-08-22
Status: **Milestone F complete; no device operation or normal CLI/GUI control
is enabled.**

The implementation is committed in `20fb6ee` (`Build offline root TXT add
candidates`). The canonical suite passes **238 tests**. The focused slice
passes 25 tests across the existing duplicate, bundle, state, and new-TXT
tests.

## Scope

`src/infocarry/new_txt.py` provides `build_new_root_txt_add()` and
`compare_new_txt_candidate()`. The builder:

- validates a complete fresh backup through the existing write-gate verifier;
- requires all eight observed backup objects, including the dynamic blob and
  fixed `0x001b`–`0x001f` state responses;
- reads the host source without changing it, preserves its original hash, and
  applies the established strict CP932/CRLF authoring rules;
- accepts only one trimmed CP932 basename with a literal `.txt` extension at
  the device root, rejects duplicate names, paths, ambiguous names, NULs, and
  unsupported CP932;
- reuses `add_file_from_template()` for the captured TXT record shape;
- preserves existing reachable records and file payloads, inserts one metadata
  record, preserves the native prefix class, recomputes content offsets,
  alignment, length, and checksum, and validates the result again;
- rebases only established metadata-relative references in the four counted
  state lists and the first dword of each bookmark group. Unknown fields,
  unused tails, categories, marks, bookmarks, selection, and Manager-local
  sidecar membership are not invented;
- requires an explicit non-negative safe capacity budget and fails closed when
  it is absent, malformed, or smaller than the complete candidate growth;
- builds the eight USB-neutral candidate ranges in memory and records source,
  target, baseline, candidate, allocation, state-rebase, preservation, and
  assumption details in a deterministic audit. It never authorizes or sends
  the candidate.

## Capture 04 golden comparison

The primary golden case is the preserved clean capture at:

```text
${EVIDENCE_ROOT}/phase-12-new-txt-repeat-20260822-152959/
```

Starting from its complete pre-add backup, the preserved source
`IC_E_ADD_20260822_04.txt`, source template record `0x0280`, an explicit
152-byte offline capacity budget, and the observed timestamp map, the builder
produces the exact post-add dynamic blob:

```text
153f446520f556cb0d0c93061e14230664833d1320c25c9f86acf5c0ff7bc8dd
```

That equals the complete post-add backup and the native SnoopyPro range-5 plus
range-8 reconstruction. The existing template rewriter required one shared
offline correction: parent-marker pointers whose child-table start moved with
the root insertion now rebase as well. Without timestamp overrides, the
candidate is normalized-equivalent to the actual blob; every permitted
difference is an observed per-record timestamp difference plus its checksum
consequence. No other difference is permitted.

## Explicit safety boundary

The candidate is a decoded dynamic blob and USB-neutral `ProspectiveWriteTransaction`
only. `new_txt.py` is not imported by the normal CLI or desktop write path. It
does not alter `VICMEM.bin`, `VICLV.bin`, or `order.vnw`; capture 04 established
those Manager-local files as unchanged around Send Selected. It does not add a
new category, mark, bookmark, or selection entry. Completion value `0x0000`
remains a checked new-add protocol assumption, and the supplied capacity
budget is not a claim about the device's unresolved capacity field.

## Operation binding slice

Commit `80f6e48` (`Bind offline new TXT operations safely`) adds the
framework-independent `NewTxtAddAuthorization` boundary. It requires the
operation-specific phrase `ADD INFOCARRY TXT` and binds the exact device
identity, baseline manifest and blob hashes, original source hash, target path,
candidate blob hash, and candidate transaction hash. Revalidation rereads the
complete baseline and source and refuses changed identity, backup, source, or
candidate metadata. The authorization remains explicitly
`authorized_for_future_writer_only` with `usb_transmission_performed: false`.

The generated transaction is exercised only through an injected fake transport
in the focused tests. Commit `fef7339` (`Add bound new TXT readback
verification`) binds the candidate to the existing USB-neutral full read-back
verifier. The verifier checks fixed state, dynamic blob, and unrelated backup
objects and reports a mismatch as terminal with no retry. The existing bounded
sender and read-back tests cover partial writes, progress, cancellation,
disconnect, timeout, nonzero completion, and no automatic retry. The complete
canonical suite passed **243 tests** before the Milestone F closure slice.

## Milestone F closure — fake transport and R15 boundary

Commit `8a6166f` (`Close Milestone F fake transport boundary`) adds 11
new-TXT-specific integration tests using the bound sender adapter and an
injected fake backend. The focused cases cover partial writes, disconnect,
busy timeout, cancellation before the request and after the first payload
chunk, nonzero completion, malformed/missing completion, changed-source
rejection before USB access, malformed read-back, candidate/read-back
mismatch, terminal reporting, and zero automatic retry. The complete suite at
the combined offline checkpoint passes **263 tests**.

The sender now checks cancellation before request `0x02`. That is an ordinary
safe cancellation with no USB calls. Once the request header is accepted,
disconnect, timeout, cancellation, or missing completion carries an explicit
`indeterminate` assessment with the primary error preserved, read-only
diagnosis/backup permitted later, and automatic retry forbidden. A nonzero
completion is recorded as a terminal `completed_with_error` result, also with
no retry. These are host-side fake-transport classifications only; they do not
prove physical device atomicity, rollback, or recovery.

The exact binding still includes the supported device identity, baseline
manifest/blob hashes, source hash, root target path, candidate blob hash,
prospective transaction hash, and `ADD INFOCARRY TXT`. The candidate and
transaction remain USB-neutral, and all normal GUI/CLI new-file controls remain
disabled. Milestone F closure is documented in `ROADMAP.md`, the parity matrix,
and `RISK_REGISTER.md`.

A live modern write, delete, restore, GUI/CLI control, or additional hardware
capture remains outside this milestone.

## Milestone G initial offline guarded workflow

Commit `1aa4ccb` (`Add offline guarded new TXT workflow`) adds the
framework-independent `GuardedNewTxtWorkflow` and nine focused tests. It
accepts one local UTF-8 TXT source and one explicit root-level `.txt` name,
produces a hash-only preview with CP932/CRLF sizes, complete growth and
capacity, offsets, state rebasing, preserved-object checks, assumptions, and
an unmistakable no-device-change notice. It then obtains a fresh complete
backup through an injected provider, revalidates the exact identity/backup,
source, target, candidate, and transaction binding, requires
`ADD INFOCARRY TXT`, executes once through an explicitly asserted fake
transport, reports bounded progress, and performs the independent complete
read-back.

The returned or terminal-error audit distinguishes `previewed`, `authorized`,
`simulated_transfer_completed`, `readback_verified`, `failed`, and
`indeterminate_after_transaction_start` states. The workflow never imports a
live transport and is not connected to the normal CLI or ttk handlers. The
combined canonical offline suite remains at **263 tests**. This is an initial
offline/fake-only G slice, not live new-file compatibility proof.
