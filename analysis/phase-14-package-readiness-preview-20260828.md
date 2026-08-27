# Phase 14 — read-only package readiness preview

Date: 2026-08-28
Status: **Read-only product preview complete; package transfer remains disabled.**

`infocarry.prepared_package_readiness` provides a JSON-safe presentation model
for an ordered TXT or TXT/BMP package. It reports the root folder, exact
ordered paths and types, source and encoded/payload sizes, aligned content
sizes, package manifest hash, conflicts against an optional verified backup,
and the candidate, transaction, and parsed-native-capacity hashes when an
offline candidate is supplied.

The preview distinguishes a logical package with no native candidate from a
candidate-backed offline preview. Both states explicitly report
`usb_accessed=false`, `device_change=none`, `sender_called=false`, and
`automatic_retry=false`. A candidate-backed preview still reports live
transfer as blocked because no native multi-child capture supports that
scope. Case-fold path conflicts and unsupported package input fail closed.

`desktop_ttk.format_prepared_package_readiness_preview` renders the same
summary for a future Library/Prepare detail surface. It does not add a
package transfer control, import the isolated sender, or invoke USB. The
portable suite is **507 passing tests with three intentional
evidence-dependent skips**.
