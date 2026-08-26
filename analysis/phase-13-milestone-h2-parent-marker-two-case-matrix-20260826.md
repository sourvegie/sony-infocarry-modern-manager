# H.2 parent-marker relation matrix

Date: 2026-08-26

This is a sanitized derived matrix. It contains no raw capture, backup, USB
range, payload, or absolute external evidence path.

| Observation | Earlier legacy deletion case | I7 stateful deletion case | Classification |
| --- | --- | --- | --- |
| Deleted target metadata offset | `0x2c0` | `0x380` | Observed independently in two preserved deletions |
| Target parent | Root directory `0x40` | Root directory `0x40` | Verified from reachable paths |
| Direct child-table effect | The root child table lost one 64-byte record | The root child table lost one 64-byte record | Verified structural effect |
| Related marker pre-delete `field_04` | `0x40` | No affected marker used `0x40` for the twelve disputed records | Verified byte observations |
| Related marker `field_08` | `0x300` → `0x2c0` for four markers | No equivalent root-related shortening among the twelve disputed markers | Verified byte observations |
| Unrelated marker pre-delete `field_04` | Not needed for the related example | `0x3a00` → `0x39c0` as its metadata record moved | Verified byte observation; field meaning unresolved |
| Unrelated marker `field_08` | Not used to decide the related transformation | `0x380` remained `0x380`, although it equaled the deleted target offset | Verified byte observation |
| Rule supported by both cases | Shorten only for the exact parent-directory relation | Preserve coincidental values when the relation differs | Verified relation-based rule |
| Metadata reduction | One 64-byte record | One 64-byte record | Verified structural effect |
| Aligned content reduction | Native candidate removes the target's occupied aligned segment | 1,896 bytes observed for the target prefix/payload and alignment | Observed; general alignment rule remains scoped |
| Surviving payloads | Preserved in the preserved candidate/post comparison | 255 surviving payloads byte-identical | Verified for the preserved cases |
| Timestamp behavior | Legacy rewrites are operation-specific and not generalized here | All 373 surviving timestamps differ from the modern preserved-timestamp candidate | Observed; causal legacy rule unresolved |
| Fixed-state behavior | Narrow legacy state result from the earlier case | I7 display/mark/bookmark target references cleared | Verified narrow effects; arbitrary rebasing unresolved |
| Completion | Legacy request-4 interpretation unavailable or limited | Legacy request-4 value unavailable | Unresolved; future modern gate accepts only `0x0000` |

The two cases falsify a value-only transformation. In the earlier case,
`field_04=0x40` identifies the root directory whose direct child table lost the
record, so `field_08` shortens by one metadata record. In I7, the disputed
markers' `field_04=0x3a00` identifies a different metadata relationship, while
their `field_08=0x380` happens to equal the deleted target offset and remains
unchanged. The modern generalized rule therefore uses the pre-delete relation
and does not assign a broader semantic name to either unknown marker field.

The corrected full I7 comparison masks only surviving record timestamp bytes
`[0x0c:0x10]` and the header checksum derived from those differences. It has
zero remaining non-timestamp byte differences.
