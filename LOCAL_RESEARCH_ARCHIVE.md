# Local Research Archive Boundary

This directory is a sanitized source-only migration checkpoint. Its new Git
history intentionally begins at the migration commit and does not contain the
canonical repository's earlier `.git` directory, refs, bundle, raw evidence,
or original research payloads.

The complete canonical history is preserved separately in the local research
archive. Original Sony software, USB/SnoopyPro captures, complete device
backups, raw responses, live-operation evidence, and transaction-range
binaries are intentionally absent from this candidate. Their absence here
does not mean that the research never existed; online agents must not infer
that conclusion.

Portable analysis notes retain only sanitized paths, hashes, sizes, structural
summaries, and conservative evidence classifications where those summaries do
not expose payload content. The original evidence remains under the local
evidence-preservation policy and is not a GitHub source backup.

## Test boundary

The normal source and synthetic-fixture tests are retained. Two capture-04
new-TXT tests skip when the external evidence root is unavailable. The
payload-builder regression that reproduces the native transaction ranges also
remains present but skips because those raw ranges are local-research-only.
No smaller or reconstructed payload fixture was created.

## Remote policy

Any later private GitHub repository is an additional source/history backup,
never the sole evidence backup. Before each verified push, inspect the commit
and complete candidate history, run focused and complete tests, run
`git diff --check`, confirm that excluded evidence is absent, and push normally
without force-pushing or changing visibility. A remote must not receive the
local research archive or any excluded evidence.
