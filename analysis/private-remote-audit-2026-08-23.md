# Private Remote Readiness Audit — 2026-08-23

## Scope and checkpoint

This is a read-only repository and complete-history audit for a proposed
private GitHub source/history backup. No InfoCarry hardware or USB transport
was accessed. The audit was run at `b2eb8ab` on branch `main` with a clean
working tree before the policy changes in this commit.

The canonical suite passed **360 tests** with:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -q
```

`git diff --check` is required before committing this audit and policy slice.

## Results

- Tracked files before this slice: 242.
- No `origin` remote was configured.
- `gh auth status` could not run because GitHub CLI is not installed. No
  authentication or account identity was changed.
- No private-key, GitHub-token, AWS-key, or similar signature was found while
  scanning all reachable Git blobs.
- No Sony executable, DLL, driver, installer, ISO, or complete device-backup
  directory is tracked by name.
- The ignored local `.venv`, `build`, Python caches, and `tmp` directories are
  not tracked.

## Blocking history finding

The complete history contains this tracked native transaction fixture:

`analysis/phase-8-candidate-1/range-01.bin`

`analysis/phase-8-candidate-1/range-02.bin`

`analysis/phase-8-candidate-1/range-03.bin`

`analysis/phase-8-candidate-1/range-04.bin`

`analysis/phase-8-candidate-1/range-05.bin`

`analysis/phase-8-candidate-1/range-06.bin`

`analysis/phase-8-candidate-1/range-07.bin`

`analysis/phase-8-candidate-1/range-08.bin`

Its tracked manifest identifies the source as a native SnoopyPro capture and
the fixture was introduced by commit `85b78a9` (`Retain required offline
regression fixture`). `range-08.bin` is 2,063,724 bytes and the complete
fixture payload is a raw transaction-derived binary, not merely a compact
parser fixture. This is prohibited raw USB/live-operation evidence for the
proposed remote audit, even though the intended remote would be private.

The history also contains analysis-only references to local paths for
external captures, complete backups, preserved legacy binaries, and the
read-only conversion checkout. These references do not include the external
file contents, but they should be reviewed for path sanitization before any
future remote is considered.

## Decision and remediation

Remote creation and push are **blocked**. The `.gitignore` rules added in this
slice prevent common future evidence, capture, proprietary-binary, generated,
and credential paths from being added, but they do not remove already tracked
objects or rewrite history.

The owner must choose the remediation before a remote checkpoint can pass:

1. Keep the current canonical history local-only; or
2. explicitly approve a separately reviewed history rewrite that removes the
   raw transaction fixture and any other excluded material, followed by a
   fresh complete-history audit.

Do not delete or alter the preserved original evidence as remediation. Do not
rewrite published history. If a clean replacement history is approved, retain
the original repository and evidence separately and record the replacement
mapping and hashes before any GitHub repository is created.

GitHub CLI must also be installed and authenticated separately by the owner
before a later remote task can verify the intended account. The exact
read-only check is `gh auth status`; after it reports the intended owner, the
repository availability and private-creation gates must be rechecked.
