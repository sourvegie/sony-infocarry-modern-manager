# Milestone G — controlled live new root-level TXT smoke

Date: 2026-08-22
Status: **One narrow live smoke completed with full read-back verification;
normal GUI/CLI new-file controls remain disabled.**

This is controlled live evidence for the supported Sony InfoCarry identity
`0x054c:0x001e`, one root-level TXT target, and one complete pre/post backup
pair. It is not a general compatibility claim, a recovery proof, or a release
authorization for arbitrary new-file creation.

## Authorization and candidate binding

The operation used the exact operation-specific phrase `ADD INFOCARRY TXT`.
The candidate was rebuilt from the fresh pre-add archive immediately before
the sender binding and was bound to:

- device identity `0x054c:0x001e`;
- pre-add manifest SHA-256
  `96b02019797210ee196ea5d231046890c413dde26f965147e795f5f8193d5958`;
- pre-add dynamic-blob SHA-256
  `153f446520f556cb0d0c93061e14230664833d1320c25c9f86acf5c0ff7bc8dd`;
- source `tmp/live-new-txt-smoke-20260822-01/source/IC_G_LIVE_20260822_01.txt`,
  51 original bytes, SHA-256
  `50f537b765bce618a7ff54b4b741a2594832ca8e4adc1a764a37b882fde2f4b0`;
- exact target `root\\IC_G_LIVE_20260822_01.txt`;
- candidate blob SHA-256
  `aec90438c1323400b2f4d4210541c599600f4e9493596edc710bd676dee8adf6`;
- prospective transaction SHA-256
  `304832b5b8eba28f462843b0f3a138b7e1eda9ddd66f96e7c7f30017b0204119`.

The source was authored as strict CP932 with CRLF normalization. The encoded
payload is 53 bytes with SHA-256
`67955517043d1da9c78f2fe06fa911a045ce5e6b64043e99226d864fdc26c15f`.

## Live transaction

The sender performed exactly one device-changing `0x101b` transaction. Its
range lengths were `[256, 64, 65216, 0, 64, 0, 0, 2050936]`, for a bounded
payload total of 2,116,536 bytes. Progress reached the complete total and the
native completion value was `0x0000`. No retry and no delete were performed;
the sender did not use the separate `0x101d` unlock path.

The original ignored smoke workspace is:

```text
${PROJECT_ROOT}/tmp/live-new-txt-smoke-20260822-01/
```

It contains the source, complete pre-add archive, complete post-add archive,
and generated audit. These raw artifacts are intentionally not committed to
the Git repository. The generated audit is
`${PROJECT_ROOT}/tmp/live-new-txt-smoke-20260822-01/live-smoke-audit.json`.

On 2026-08-22 it was copied without modifying the original into the stable
evidence root:

```text
${EVIDENCE_ROOT}/phase-12-milestone-g-live-new-txt-20260822-01/
```

`diff -rq` verified the initial copy byte-for-byte. Every preserved file then
passed `SHA256SUMS.txt`; that manifest's SHA-256 is
`85c4d00a540804d417c0fcd6f04233d1f7b89b95e1ab750166a6587307bf1296`.

## Independent post-add verification

The post-add archive is complete with eight objects. Its manifest SHA-256 is
`7b43e0db14408eae8e92d4f22fb1fbae589bb35aedcebe5e8ba739b67876b19d`, and its
dynamic blob SHA-256 is exactly the candidate blob hash above. The existing
USB-neutral verifier reports:

- fixed state matches: **true**;
- dynamic blob matches: **true**;
- unrelated backup objects unchanged: **true**.

Independent path parsing finds 310 reachable pre-add records and 311
post-add records: exactly one added path, the target above, and no removed
path. The new record is at metadata offset `0x00000300`; its payload starts at
`0x00005e0c`, is 53 bytes, and has the expected payload hash. The payload
bytes are:

```text
Live Milestone G smoke\r\nThis file is disposable.123\r\n
```

The result is therefore **read-back verified** for this exact device, source,
target, candidate, and transaction. No Manager-local sidecar claim is made:
this smoke intentionally verifies the device-resident result through complete
post-add backup rather than attempting to infer `VICMEM.bin`, `VICLV.bin`, or
`order.vnw` behavior.

## Evidence labels and boundary

- **Verified live:** one successful bounded send, completion `0x0000`, complete
  post-add backup, exact candidate blob equivalence, fixed-state equivalence,
  unrelated-object preservation, one added root TXT path, and no removal.
- **Observed:** the supported device identity and the sender's completion
  response for this operation.
- **Inferred/checked only:** that the existing `0x101b` completion handling is
  suitable for this narrow new-add operation beyond this successful result.
- **Unresolved:** interrupted-write atomicity, rollback, physical recovery,
  general capacity semantics, sidecar mutation for other Manager workflows,
  other record types, nested placement, and other device models.

R15 remains open. Any interruption after `0x101b` begins remains an
indeterminate outcome requiring read-only assessment; this successful smoke
does not prove physical atomicity or recovery. Selective deletion remains a
separate Milestone H gate. The normal GUI/CLI does not expose this writer.

The complete canonical suite remains at **263 passing tests**. No original
evidence, source backup, or separate `InfoCarry-Toolkit` checkout was modified.

Documentation commit: `3dcf5e7` (`Record approved live new TXT smoke`).
