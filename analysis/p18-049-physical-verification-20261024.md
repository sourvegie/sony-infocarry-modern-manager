# P18-049 independent physical-evidence assessment — stopped after placement

**Outcome: STOPPED AFTER PLACEMENT. P0/P1/P2 = 0/1/0.** Actual placement bytes and protected-state preservation PASS. Immutable task-provenance consistency FAIL. The two-write experiment is incomplete: one audited sender invocation, zero Deletes, zero automatic retries. The disposable remains present; the original eight-object baseline has not been restored. No continuation PASS gate was created.

Reviewed implementation source: `2835e79599618376b2b28594809e9ed8e4673cae`; documentation checkpoint `c5b3af9ca033150eb73cb1d8c0c85d3446059665`. Owner approval bound the exact two-write envelope `eae6909886fbbfc10ab2e21d7e773c71ea9624ab1843f837960d7466648200a5`, with an explicit stop on inconsistency. This report preserves that boundary. It authorizes no retry, cleanup, recovery or further write.

## P1 — inconsistent frozen source-template provenance

The frozen task envelope records placement `template_offset=448` (`0x1c0`). The original sealed read-only placement preparation and actual placement candidate audit use `0x7180`. The preparation script enumerates eligible templates in `parsed.records` order; the facade enumerates `parsed.paths` order. The envelope/executor checks compared the resulting candidate/transaction hashes but omitted equality of the explicit template-offset field. The initial independent review also missed this pre-existing inconsistency.

This is not evidence of unexpected native bytes or live source-state drift. Independent reconstruction of the original frozen sealed candidate audit matches `0x7180`, not `0x1c0`. Both source records have identical native fields copied into the new record (flag/type and bytes 0x10–0x17) and an identical 32-byte prefix, SHA-256 `d0bcc6bc85dc36cdc1ad3882952c5d3d4414869c0bdd75b3b58ba28a32deb92a`. Their original timestamps differ, but the new record receives the same explicitly frozen timestamp 1792768350. Independent reconstruction with either source yields exactly the owner-approved candidate and transaction hashes.

Nevertheless, the immutable envelope explicitly named a source-template offset that conflicts with its sealed preparation. The discrepancy was found during independent actual-placement assessment, before step 2. The executor stopped under the owner's rule. No operation 2 directory exists, no Delete was sent, and no cleanup or automatic recovery was attempted. The earlier readiness PASS is superseded for continuation by this finding; it must not be cited as an unqualified completion assessment.

The host correction to consider in a later authorized engineering step is to use one existing template-selection rule for preparation/facade and compare every explicitly frozen provenance field, including source-template offset, before any operation authority gate. This report implements no correction and expands no authority.

## Actual native placement — independent byte verification PASS

Preserved actual before/after manifests each contain eight complete, hash-verified native objects. The fresh before-state matches all eight approved baseline objects and state identity. Actual post-write dynamic bytes equal the frozen candidate exactly; preserved sender transaction ranges equal the frozen transaction. Canonical terminal evidence reports native integer 0 / `0x0000`, one sender / one `single_0x101b_transaction`, zero retries and independently verified readback. These are execution-audit counts; there is no separate USB bus trace.

- Sole added path: `root\IC_P18_040_NESTED_20260930_01\Section-A\IC_P18_049_DELETE_A.txt`.
- Exact 34-byte payload, SHA-256 `aa1cecbacdeb3daa43c1b162aee68c7d3ad87f89f98874b61db0c02569984975`; unread 0xe0, opaque 0xffffffff, selector 0x200, captured 32-byte prefix; actual target 0x880.
- Existing Section-A parent 0x700 and both original siblings survive in original order, followed by the new leaf. No folder or subtree was created or removed.
- Dynamic image grows 132 bytes, from 2,210,432 to 2,210,564; record count 454→455. All 454 surviving timestamps and 300 surviving payload/prefix pairs were independently compared. All 79 marker records survive. The independent no-repacker inverse validator checks every surviving raw record, supported pointer/count/marker transformation, ordering, content/padding and opaque bytes against the original baseline.
- All five protected fixed-state objects match the exact frozen transaction. Offline construction of the same-leaf Delete verifies the target remains unreferenced and derives protected-state associations back to the original baseline. Unknown or unsupported state was not adopted.
- Payload-dependent auxiliary response/probe bytes changed during placement and were preserved in the actual eight-object backup. Their intermediate values were not falsely equated with the baseline-copied simulation. Final all-eight baseline restoration remains unperformed.

Actual placement candidate SHA-256:
`a0d28fbbd8ce6bd354df9f91ccf0088c045f84053178e9f4523c6de615933475`

Actual placement transaction SHA-256:
`cfb0950d09b19458d7a6dc1a8c9d7203e7db08f8097f1845d00088db6ac25560`

Actual placement sealed bundle SHA-256:
`f37d3d09dfe0de989a033d21f63be6f1adb0895ba41bda76ed0692250d91ba7f`

## One-shot safeguards — independent read-only check PASS

The placement consumed exactly one new claim, 24→25; every historical claim row remains unchanged. The new claim binds the actual operation seal, transaction and candidate and is durably `consumed`. Terminal evidence resolves its sender marker; the actual SQLite store was independently opened read-only after terminal completion and has zero active markers. The global lock remains clear and byte-identical to before placement. No production safety state was modified by the reviewer.

The independent reviewer inspected actual artifact bytes, reconstructed candidates and verified the production safety store read-only; the reviewer performed no USB/native operation. The pre-send executor source and post-result API block had also passed isolated fake-only checks, but those checks did not detect the missing template-offset comparison.

## Offline next-step observation — no execution authority

An offline exact Delete reconstruction from the actual post-placement backup produces the previously predicted transaction `e5831e0e363cab494c3f4aa859763808fa5a7676b01c6fd4ddb15edd4d58c452` and original dynamic baseline `6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`; its five derived fixed-state objects return to baseline. This is host evidence only. It neither proves physical nested Delete nor permits the stopped operation to continue.

## Sanitized evidence anchors

| Artifact | SHA-256 |
| --- | --- |
| Actual before-backup manifest | `fba838b45e84d5d19fe8761f3fc841ed9b2e61f4bb70b14a8aa2a331afc2085d` |
| Actual after-backup manifest | `2a3606f9b69e0fcccb032e5f8f4fe3a09d6acc44bb8d5253ce1900da5a1e9a5a` |
| Canonical native result manifest | `1687863f9111e33e9680b35c4e5e084205743a85af1f442ec099fce0e8a5d452` |
| Sender-marker resolution | `f2596b7ddfc8ed746b92b0e1589ba125b486c5003f41cd1466316fb5d2050c6a` |
| Disposable placement report | `4240decfc342a9600972444fc0237355ff9fe7255ec602ea289da867c1661326` |
| External operation 1 result summary | `be977c0ab9fd97dd49c43d414ce0a0fe0c72d96714080fb7a76aec27efab450b` |

Raw backups, private audit/template names, full safety rows, external executor and detailed independent JSON remain outside Git. The JSON separately anchors every actual post-backup object and safety snapshot.

**Final state:** exact disposable present; baseline not restored; sender 1 / Delete 0 / retry 0. Native placement preservation PASS; task continuation STOP with one P1 provenance-binding finding. Ordinary nested Delete remains disabled. No physical nested Delete proof, feature promotion, push or merge is claimed. No further physical operation is permitted in this stopped run.
