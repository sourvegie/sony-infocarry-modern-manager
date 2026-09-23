# P18-037 operation-owned staging correction — 2026-09-23

## Scope

This record covers the owner-authorized continuation of PR #65 from the
exact pre-change head `ff1f0593dd7fbcc1c71d3dc76bd53cfdd515dbc6`. It is a
host-only correction for ordinary Local Library folder reachability. No USB
device was opened, no native write was attempted, and no physical result is
claimed.

The preserved `-07` validation attempt remains permanently stopped and was
not edited, retried, or relabeled. Its disposable source, evidence, package,
and negative-test artifacts remain outside this repository. The source
workspace `/Users/stardust/Projects/InfoCarry-Toolkit` was not modified.

## Exact host reproduction

The valid ordinary folder was revalidated as the exact direct shape
`TXT → BMP → TXT`, with the reviewed 237×320, 1-bit, uncompressed Windows BMP
fixture and unchanged source/catalog inputs. Host-only live preflight reached
the existing reviewed VNW-V15 path and produced fresh read-only evidence.

The stopped route failed only when the transient adapter workspace was
cleaned before a later sealed operation reload. The sealed bundle retained a
manifest path inside that temporary directory, so canonical bundle resolution
failed closed with `bound artifact is unavailable`. The failure occurred
before claim consumption and sender entry; it was not evidence of a device
failure.

## Correction

The ordinary-folder adapter now copies the complete validated prepared package
into the unique operation evidence directory before preflight sealing. It
also writes an operation-owned catalog snapshot because the in-memory overlay
must remain reloadable while the user catalog stays unchanged. The operation
binding records the operation id, preflight seal, stable package paths, file
hashes, prepared-manifest identity, and semantic prepared-artifact identity.
The sealed operation bundle binds this metadata as an additional optional
artifact; legacy bundles without it remain loadable. The canonical live
resolver verifies the metadata, stable paths, hashes, operation identity, and
sealed-report identity before any runtime callback.

Temporary preparation cleanup removes only the pre-seal workspace. The
operation-owned package/catalog/binding remain available through authorization,
execution, post-write backup, and independent read-back, including restart or
reload. Missing, changed, stale, escaped, or mismatched artifacts continue to
fail closed.

Pre-send failures now receive a durable concise diagnostic with a stable
reason code, exception class/message, operation and artifact bindings, and
sender-start, authorization, claim, and marker status. The normal UI maps
staging-verification failures to “Transfer preparation could not be verified.
No device change occurred.” No traceback is shown and no failed sealed
operation is recycled. A fresh exact-head review also required the ordinary
folder adapter to reject non-root folder nodes, and required claim/marker read
failures, missing safety stores, and diagnostic-write failures to remain
explicitly unknown/unavailable rather than being represented as safe absence.
The portable path assertion was made separator-neutral for Windows.

## Host validation

Focused ordinary-folder tests cover three- and four-leaf package survival
after temporary cleanup, stable catalog reload, source/catalog immutability,
root-level-only admission, canonical fake execution after reload, and missing
staged-artifact/diagnostic failures before any claim or sender call. The
complete portable Python 3.12 suite passed 1,004 tests with 3 documented
skips. The external test-only PyUSB stub was used to ensure the suite could
not discover or open hardware. Compilation and `git diff --check` passed.

This checkpoint remains host-only and requires fresh independent exact-head
review plus final macOS/Windows CI and packaging checks before the disposition
`READY_FOR_HARDWARE_TEST`. It does not authorize or perform physical
validation and does not merge PR #65.
