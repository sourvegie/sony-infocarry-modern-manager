# P18-043 archived root-TXT candidate census — 2026-10-10

**TESTED OFFLINE. General root-TXT execution remains unvalidated.** An
independent bounded evidence specialist inspected twelve preserved complete
VNW-V15 archives using the existing P18-042 one-TXT structural model and
protected-state policy. This is host corroboration, not evidence that a new
file class has physically completed. No USB or production safety store was
accessed. No transaction, authorization or raw candidate was saved.

## Evidence and selection

The [sanitized corpus inventory](phase-18-p18-043-root-txt-corpus-20261010.json)
records external archive references, manifest SHA-256, all eight object hashes
and sizes, and hashed target identities/payloads. Private names and payloads
are absent. Every manifest and object was read-only hash-verified before
analysis and rehashed afterward; all twelve archives remained unchanged.
The four P18-041/H2 before/post manifest and dynamic hashes also match
their existing canonical physical-closeout records. The corpus contains nine
distinct dynamic blobs. Historical states sharing
one dynamic blob remain separate because their auxiliary associations differ.

Selection was bounded to sources directly cited by the
[P18-041 physical closeout](phase-18-p18-041-physical-delete-closeout-20261010.md),
[H2 modern Delete record](phase-13-milestone-h2-modern-delete-smoke-20260827.md),
[P18-041F calibration](phase-18-p18-041f-root-leaf-calibration-20261004.md),
and the existing I7 state/NewTXT archive families. The
[two-case marker matrix](phase-13-milestone-h2-parent-marker-two-case-matrix-20260826.md)
and P18-042 existing model/state source were inspected before comparison.
No unrelated evidence or whole analysis-directory content was scanned.

| Archive state | Root TXT models pass | Protected-state pass | Refusal |
| --- | ---: | ---: | --- |
| P18-041 actual before | 5 | 5 | None |
| P18-041 actual after | 4 | 4 | None |
| H2 modern Delete before | 5 | 5 | None |
| H2 modern Delete after | 4 | 4 | None |
| I7 legacy Delete before | 6 | 0 | 6 active Mark states |
| I7 legacy Delete after | 5 | 5 | None |
| I7 after display history | 6 | 5 | 1 protected target |
| I7 after bookmark | 6 | 0 | 6 active Mark states |
| NewTXT first add after | 2 | 0 | 2 active Mark states |
| NewTXT repeat 1 after | 3 | 0 | 3 active Mark states |
| NewTXT repeat 2 after | 4 | 0 | 4 active Mark states |
| NewTXT repeat 3 after | 5 | 0 | 5 active Mark states |
| **Total** | **55** | **28** | **26 active Marks; 1 protected target** |

All 55 candidates passed separate raw checks. The 27 auxiliary refusals are
expected exclusions, not candidate successes or skipped verification.
No ambiguous/structurally unsupported root TXT occurred in this real corpus;
synthetic tests must establish those refusal paths.

## Independent comparisons

For each actual target, the existing model creates one isolated candidate
from its archive; operations are never chained. A second implementation,
without calling the model's survivor-check helpers, independently compares:

- Exactly one reachable target path removed, with no added or extra removed path.
- Exactly one 64-byte metadata record removed; every survivor's serialized
  bytes equal the source except the permitted metadata/content pointer changes,
  exact parent-table shortening and established relation-based marker change.
- Every serialized survivor timestamp remains exact.
- Every surviving file's native prefix and payload remains exact.
- The entire content region equals the original with only the target's
  aligned prefix/payload segment excised; all other gaps/unknown content bytes
  remain exact.
- Exact expected length reduction and valid recomputed checksum.

For all 28 admitted protected-state cases, a separate direct derivation
rebases only established counted history/bookmark references after the target
by 64 bytes; each resolves to the same survivor. Every other fixed-state byte
remains exact. Active Mark states refuse through the existing policy. The
history-associated target in the display-only archive refuses rather than
clearing its association. Assertion failures terminate the reproduction;
they are never relabeled as an expected unsupported-file refusal.

## Observed structural envelope

The corpus has eight distinct combinations of hashed path, payload, flag and
native selector. All 55 root names are ASCII, 10–21 native CP932 bytes with
NUL termination and exact CP932 decode/encode roundtrip. All native prefixes
are 32 bytes, selector `0x00000200`, with zero high bits. There are 52 unread
flags (`0xe0`) and three read flags (`0x20`). Target payloads range 29–1,863
bytes; lengths modulo four are 1 and 3. Root TXT first/middle/last ordinal
positions occur, with metadata offsets `0x1c0`–`0x680`.

**Inferred smallest useful preparation profile:** one unique ordinary
root-level TXT file; known read/unread flag; 32-byte prefix and the evidenced
selector; exactly bound native identity and candidate; no active Marks or
unsupported auxiliary blocks; no target history/bookmark reference;
independently proven sole removal and complete survivor preservation.
Native names should have a 1–39-byte CP932 basename with native NUL terminator,
exact raw-name roundtrip, and no separators, control characters, root/marker
syntax or ambiguous dotted basename. These syntax exclusions avoid admitting
names the existing single-file path/UI contract cannot identify clearly.
They do not infer host filesystem behavior for the device.

No payload-size ceiling can be inferred from this census. Use the actual
validated content geometry, complete backup, candidate and existing bounded
transaction/capacity checks. Deletion should not inherit an add-file limit
merely because the payload builder for creation has one.

## Evidence gaps and physical boundary

There are no real root-TXT samples here with non-ASCII names, 16-byte prefixes,
nonzero selector high bits, empty payloads, much larger payloads, or every
possible alignment remainder. Their synthetic correctness is host-only;
there is no new physical proof. Three read-state occurrences are all the
same archived target in related states. Active Marks and referenced targets
are deliberately excluded; the corpus does not justify clearing them.

The prior modern hardware evidence remains two individually bounded
root-TXT operations: H2's exact all-zero-state case and P18-041's exact
29-byte fixture with unrelated protected associations preserved. Neither
provides general class standing authorization. The P18-041 closure records no
independent USB bus trace; none is inferred here.

General root-TXT preparation may use the existing guarded architecture, but
routine execution admission must remain gated until separate owner-authorized
bounded physical validation with disposable content. BMP, nested-file,
directory/subtree and VNW-V10 operations remain outside this census.

Reproduction script remains outside Git at
`/external/local-path`. Run with the supported Python 3.12:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /external/local-path -u /external/local-path
```

Only sanitized aggregate progress is printed. The script reads original
archives, saves no raw candidates and writes the sanitized JSON inventory.
USB requests, physical writes, production safety access/mutations and
transaction/authorization construction: **0**.
