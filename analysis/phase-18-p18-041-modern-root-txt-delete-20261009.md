# P18-041 modern guarded exact root-TXT Delete — 2026-10-09

## Scope and implementation

Approved task changes direction from the unavailable legacy Manager gate to
one modern guarded VNW-V15 Delete. Base commit: `3addede2dcf389038fa053adfab6698da8300b02`.
The target is only `root\IC_P18_041G_CLOCK_01.txt`, exact 29-byte fixture,
SHA-256 `9541c1b9d09ee7d4ab91c704755c4bea8b2022c3bb8f50aa15c1a990bf80c35d`.
No real USB, `0x101b`, physical write, production claim, marker or lock mutation
was performed. Fake lifecycle state exists only in temporary test stores.

`delete_state.py` adds an opt-in survivor-preservation policy: counted verified
history and established bookmark pointers after the deleted metadata record
subtract 64, pointers before it remain exact, target references refuse.
Every rebase must resolve to the same ordinary file, identical metadata except
the payload pointer, and identical prefix/payload. Opaque bytes and empty Mark
state are preserved; active Marks and unresolved associations refuse.
`delete_generalized.py` retains its original default behavior.

`delete_workflow.py` adds the exact experimental admission/bundle/facade using
H2's frozen artifacts, reconnect-safe equivalence, established canonical owner,
coordinator, durable claims/markers/global lock and sender. Candidate authority
is reconstructed from verified immutable inputs. No transaction format,
transport, persistent schema or parallel live pipeline is introduced.
The adapter/report hook and root-operation confirmation are made operation
specific; existing ADD formats and guarded behavior remain unchanged.
The owner identity keeps its fingerprint internally and exposes one exact
Delete phrase. The script defaults offline; its explicit live flag obtains
its own fresh backup, rejects offline input adoption and asks once.
Normal GUI/CLI generalized Device Library Delete remains disabled.

## Exact changed files

- `src/infocarry/delete_state.py`
- `src/infocarry/delete_generalized.py`
- `src/infocarry/delete_workflow.py`
- `src/infocarry/experimental_library_transfer.py`
- `src/infocarry/library_transfer_execution.py`
- `src/infocarry/prepared_library_package_live_adapter.py`
- `src/infocarry/root_txt_placement.py`
- `scripts/experimental_root_txt_delete.py`
- `tests/test_experimental_root_txt_delete.py`
- `CURRENT_STATUS.md`, `CAPABILITY_MATRIX.md`, `README.md`
- This implementation record, the linked operator procedure and sanitized
  structural-validation JSON.

Development uses isolated branch `task/P18-041-modern-root-txt-delete` in
`/external/local-path`.
The reference/evidence checkouts and their existing work remain untouched.
No push or merge is authorized/performed.

## Structural evidence and risks

Reviewed P18-041F/G timestamp mismatch evidence, the completed fixture-placement
report (not its preparation placeholder), historic H2 modern root-TXT Delete
readback, and October 9 complete eight-object backup. The historic constrained
Delete corroborates preserved timestamps on its own state; it does not prove
this new implementation/current state physically safe. The independent prior
pre-placement archive is used only as validation, never candidate input.

[Sanitized structural validation](phase-18-p18-041-modern-root-txt-delete-validation-20261009.json):
455 -> 454 serialized records, 300 survivor payloads unchanged, 454 survivor
timestamps preserved, exact target-only removal and valid checksum.
2,210,560 -> 2,210,432 bytes; 128 bytes reclaimed. Eight protected pointers
rebase and all opaque fixed-state bytes remain exact. Candidate SHA-256
`6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`
and all five fixed-state blocks exactly match captured pre-placement state.
Transaction SHA-256
`e5831e0e363cab494c3f4aa859763808fa5a7676b01c6fd4ddb15edd4d58c452`;
existing eight ranges `[256,64,65216,0,64,0,0,2210368]`.
No legacy-native equality or new physical completion is claimed.

Raw archives/candidate/ranges remain outside Git. VNW-V10, arbitrary TXT,
directories/subtrees, generalized Delete, restore and recovery stay unsupported.
Target auxiliary references fail closed rather than silently clearing state.
Physical atomicity/interrupted-write recovery remains unresolved.

## Validation and independent review

Supported Python 3.12.14, `PYTHONDONTWRITEBYTECODE=1`, isolated checkout only:

- Focused suite: 130 tests pass (including 24 new exact-Delete tests).
- Full portable suite: 1,098 tests pass, three established intentional evidence
  skips (two unavailable stable Capture 04 tests and one local-only raw native
  transaction-range test). No new skip introduced.
- `git diff --check`: clean.
- Strong independent R3 source/evidence review: one P2 audit-binding finding
  corrected by binding audit SHA-256 in the envelope and comparing it with the
  independently reconstructed audit; tampering fails before claim/sender.
  Reviewer independently ran 87 relevant tests plus the three correction/
  pointer/script tests and reproduced the actual October 9 structural proof.
  Working-review findings after correction: P0/P1/P2 = 0/0/0.
  Final exact-head review is saved outside Git at
  `/external/local-path`; its recorded commit is the
  final review authority, not this executor summary.

Full test command (no USB):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /external/local-path -m unittest discover -s tests -v
```

Final validation logs remain outside Git:
`/external/local-path` and
`/external/local-path`.
Host checkpoint: `READY_FOR_HARDWARE_TEST`, conditional on clean final
exact-head R3 review. Physical correctness/current-state result requires the
separate owner-authorized experiment.
Tests cover target scope, timestamp/payload preservation, signed reference
rebasing and opaque tails, before-sender marker persistence, duplicate claims,
reconnect state equivalence, drift refusal before claim, terminal nonzero,
malformed completion, interrupted sender, failed post-backup and global locks.

[Exact operator procedure](phase-18-p18-041-modern-root-txt-delete-procedure-20261009.md)
requires separate owner approval and a new fresh backup before physical use.
