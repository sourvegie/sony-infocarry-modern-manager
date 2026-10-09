# P18-042 continuation — independent root-BMP model review

Date: 2026-10-10 Asia/Tokyo.
**PASS — unresolved P0=0 / P1=0 / P2=0.**
Exact reviewed commit: `ba0d36c20385678a08f9c9854ef9e85097a7a72d`.
Extension base: `67d029bcd3820feac34b5c350f06d36da4992162`.
Review is independent and read-only. No repository edits or commits were made.

## Independently inspected scope

Reviewed the full six-file exact diff against extension base, inherited actual AGENTS/WORKFLOW/product/capability/risk requirements and owner-approved host-only follow-on boundary, current source and new tests, shared TXT/BMP model, parser/payload prefix/read-state classification, existing repacker/marker relationship logic and strict canonical monochrome BMP validator. Inspected current generalized TXT candidate imports and Device Library admission to verify that the BMP helper has no live path. Source references to the new helper occur only at its definition/export; no final transaction, authorization, facade, UI admission, sender, claim/marker/global-lock schema or lifecycle change is introduced.

The private one-file refactor retains the TXT wrapper's fixed `txt` admission. Its former ordinary-TXT error strings, candidate bytes, audit operation and other audit content remain equivalent. BMP fixes admission to an ordinary root file, supported read/unread flags, validated 16/32-byte native prefixes and exact 237×320 uncompressed 1-bit BMP payload profile. Exact path/offset and ambiguity refusal precede construction. Existing survivor pointer/raw-record/timestamp/payload checks, sole removal and checksum-valid parse remain in force. BMP audit explicitly records host-only capability, no transaction/authorization/execution and no physical proof. Protected references are handled by the separate existing state derivation; the pure structural helper does not claim to validate full fixed state.

No material P0/P1/P2 defect found. No widening of live TXT/BMP capability is justified by this work.

## Independent validation and preservation comparisons

- Ran `PYTHONPATH=src:tests .venv/bin/python -m unittest test_root_bmp_delete_model test_delete_model test_delete_hardening test_backup_repack test_delete_state test_delete_generalized test_experimental_root_txt_delete test_device_library_delete_execution test_device_library_delete_ui -v`: **107 tests passed**, no skips, 8.057s; log `/external/local-path`.
- These independently rerun cases cover first/middle/last target, both prefix lengths and read states, sole root file, top-down/bottom-up BMP, malformed headers/dimensions/compression/depth, nested/root/directory/wrong identity, unsupported prefix/state, overlap/ambiguity, protected surviving-reference rebases and target-reference refusal, deterministic output, unchanged source and continued rejection by TXT transaction and Device Library gates.
- Loaded the original `67d029b` TXT function independently from Git into an isolated module and compared it to the current wrapper for **all 137 reachable TXT files in actual saved pre-delete archive and all 136 in actual post-delete archive**. All **273 candidate-byte and complete audit comparisons are exact**; the run completed successfully, none are interrupted/skipped results.
- Independently rebuilt P18-041's original exact actual pre-delete candidate: SHA-256 `6d50eb4c5276d194069be92b4b352fe2cb625ed2b1972de27ea9af8a410b46b8`. Transaction SHA-256 remains `e5831e0e363cab494c3f4aa859763808fa5a7676b01c6fd4ddb15edd4d58c452`. Both match canonical closeout. Original actual saved post-delete independent verifier remains `readback_verified`.
- Independently inspected `/external/local-path`: **1,142 run / 1,139 passed / 3 established skips**, 119.630s, terminal `OK (skipped=3)`. The same two absent stable capture-04 cases and local-only raw transaction ranges are skipped. No failure/hung/interrupted test is presented as passed.
- Exact extension `git diff --check` passes; reviewed HEAD is clean.

## Capability and final disposition

**IMPLEMENTED / TESTED OFFLINE:** one pure root-BMP structural model only. It is suitable for continued host preparation and review. **NOT LIVE-ENABLED / NOT PHYSICALLY DEMONSTRATED:** root BMP deletion. It is not a complete runnable BMP operation and has no full fixed-state transaction/authorization or success decision. Original UI/guarded TXT scope remains only the exact reviewed VNW-V15 fixture. General TXT/BMP, nested/directory/subtree execution and VNW-V10 remain unavailable; original physical proof is unchanged and no independent USB trace exists.

Future live BMP extension still needs scoped complete-backup/candidate/protected-state binding, exact independent success checks, review and separate operation-specific owner authorization for physical validation. This review does not require or authorize any present hardware action. Reviewer USB requests, physical writes and production safety-state accesses/mutations: **0**. No push/merge authority implied.
