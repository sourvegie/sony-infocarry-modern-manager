# Phase 12 live evidence preservation

Date: 2026-08-22
Status: **Stable copies complete and hash-verified; originals retained.**

The Milestone G live-smoke workspace and Milestone H failed-delete package
were previously represented primarily by ignored `tmp` paths and an
owner-supplied Desktop directory. They were copied, never moved, into the
project's stable evidence tree before any further live experiment.

## Milestone G live new-TXT smoke

Source retained unchanged:

```text
${PROJECT_ROOT}/tmp/live-new-txt-smoke-20260822-01/
```

Stable copy:

```text
${EVIDENCE_ROOT}/phase-12-milestone-g-live-new-txt-20260822-01/
```

The source and destination were compared with `diff -rq` before adding the
manifest; no difference was reported. The stable copy contains the source TXT,
complete pre-add and post-add eight-object backups, the live audit, and the
owner-approved run helper. Every listed file passes `SHA256SUMS.txt`.

Manifest SHA-256:

```text
85c4d00a540804d417c0fcd6f04233d1f7b89b95e1ab750166a6587307bf1296
```

## Milestone H failed legacy delete attempt 01

Sources retained unchanged:

```text
${OWNER_DESKTOP}/capture5/
${PROJECT_ROOT}/tmp/milestone-h-delete-capture-20260822-01/
```

Stable copy:

```text
${EVIDENCE_ROOT}/phase-12-milestone-h-delete-attempt-20260822-01/
```

`owner-original/` contains the supplied native log and Manager before/after
snapshots. `derived-analysis/` contains the complete pre/post-attempt backups,
parsed eight-range artifact, reports, and copied failure screenshot. Each
source/destination pair was compared with `diff -rq` before adding the
manifest; no difference was reported. Every listed file passes
`SHA256SUMS.txt`.

Manifest SHA-256:

```text
adb60785a9c038c3f84f78b66d02a70808772a354f36c3084cabdf922443857e
```

## Boundary

These stable copies improve evidence durability but do not promote the failed
delete attempt to successful deletion proof. No source artifact, device state,
normal GUI/CLI control, or modern delete boundary was changed.
