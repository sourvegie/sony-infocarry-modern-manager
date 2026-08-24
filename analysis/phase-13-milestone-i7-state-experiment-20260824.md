# Milestone I.7 — isolated display-history, mark, and bookmark state experiment

Date: 2026-08-24
Status: **Complete for the observed disposable-record state transitions; general timestamp and fresh-state construction remain blocked.**

This report summarizes the separately approved state experiment on the
legacy-created disposable record `root\\IC_I7_CLOCK_01.txt`. The raw backups
and derived JSON reports remain outside the sanitized source repository under
the local evidence store. No raw payload bytes are reproduced here.

Evidence session: `phase-13-i7-state-experiment-20260824-01`

## Sequence and integrity

| Stage | Complete backup | Dynamic blob SHA-256 | Records | Result |
| --- | --- | --- | ---: | --- |
| Stable baseline | `baseline-pre-state` | `7d64a9dccc3bede003ee732d50a4ee25c02d324fa3c1f9f4b455e034ec1c805f` | 374 | Target unread; all fixed state zero |
| After opening once | `after-display-history` | `5b081faf7cc733e9c63c13250d689d6e7beb52bcf10470503dd68684471ab61b` | 374 | Target read; display-history reference added |
| After Mark 1 | `after-mark-1` | `5b081faf7cc733e9c63c13250d689d6e7beb52bcf10470503dd68684471ab61b` | 374 | Mark-list 1 reference added |
| After Bookmark 1 at file beginning | `after-bookmark-1` | `5b081faf7cc733e9c63c13250d689d6e7beb52bcf10470503dd68684471ab61b` | 374 | Bookmark group 1 populated |

Every backup was complete, used the supported device identity `054c:001e`,
and was written to a new non-overwriting destination. The target remained at
record offset `0x380` with payload length 1,863 and payload SHA-256
`3aa626dc1e0dbd2fe13b59fbea7eddf43358a522b9f55ed15ac18556b2a69d4b`.

## Observed fixed-state transitions

The offset-list values below are metadata-relative. The observed `0x340`
value maps to absolute record offset `0x380` after adding the metadata start
`0x40`.

| Stage | `0x001b` display history | `0x001c` Mark 1 | `0x001d` Mark 2 | `0x001e` Mark 3 | `0x001f` Bookmark 1 group |
| --- | --- | --- | --- | --- | --- |
| Baseline | count 0 | count 0 | count 0 | count 0 | `(0, 0, 0, 0, 0)` |
| After opening | count 1, offset `0x340` | count 0 | count 0 | count 0 | `(0, 0, 0, 0, 0)` |
| After Mark 1 | count 1, offset `0x340` | count 1, offset `0x340` | count 0 | count 0 | `(0, 0, 0, 0, 0)` |
| After Bookmark 1 | count 1, offset `0x340` | count 1, offset `0x340` | count 0 | count 0 | `(0x340, 0, 0, 0x80000000, 0)` |

The second bookmark group remained all zero. Unused tails were preserved and
are not interpreted as active entries. The exact bookmark tuple is recorded
as an observation; the semantics of its second and third dwords remain
unresolved for this record and must not be generalized from this one case.

## Dynamic-record changes

Opening the previously unread record changed its file flag from `0xe0` to
`0x20`, consistent with the already verified unread/read representation. Its
32-byte native wrapper also changed, while the decoded payload remained
byte-identical. The display-history transition therefore affected the target
record state, target wrapper, and `0x001b`; it did not change payload bytes,
record count, model length, shared timestamps, or unrelated records.

Mark 1 and Bookmark 1 did not change the dynamic blob at all. Their changes
were isolated to `0x001c` and `0x001f`, respectively. This is independent
evidence that these two state families are carried in fixed response objects
for the observed operations rather than requiring dynamic-model growth.

## Evidence classification

- **Verified:** complete backups, device identity, target persistence and
  payload hash, record count, exact fixed-object bytes, active counts, and
  metadata-relative target reference.
- **Independently observed:** display history uses `0x001b`, Mark 1 uses
  `0x001c`, and Bookmark 1 uses the first `0x001f` group, consistently with
  earlier isolated state evidence.
- **Observed in this target:** the display-history wrapper transition and the
  Bookmark 1 tuple `(0x340, 0, 0x80000000, 0)`.
- **Unresolved:** the general timestamp-generation rule, general rebasing or
  removal of nonzero references, the complete semantics of bookmark dwords,
  and the operation-wide delete transformation.

## Gate result

The state experiment is a successful characterization of one disposable
legacy-created root TXT record. It does not close the general I.7 timestamp
or fixed-state rule, and it does not make H.2 deletion eligible. No deletion,
modern write, or normal GUI/CLI state action is authorized. The next work is
offline synthesis and regression coverage; any future deletion experiment
requires its own protocol and explicit approval.
