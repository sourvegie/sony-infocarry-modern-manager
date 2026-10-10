#!/usr/bin/env python3
"""Separately approved placement of one exact disposable Delete fixture.

No USB or safety-state setup occurs without --allow-write. Preparation is
read-only; the one readable owner answer binds the same frozen bundle before
the existing guarded coordinator, sender and independent readback execute.
"""
from pathlib import Path
import argparse
import json
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from infocarry.delete_workflow import ROOT_TXT_DELETE_VALIDATION_FILES
from infocarry.root_txt_placement import RootTxtPlacementFacade, _write_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--target", choices=tuple(ROOT_TXT_DELETE_VALIDATION_FILES), required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, required=True,
                        help="new external JSON file for the frozen operation review")
    args = parser.parse_args(argv)
    if not args.allow_write:
        parser.error("physical mode requires --allow-write and separate owner authorization")
    source = args.source.expanduser().resolve()
    filename = args.target.split("\\")[-1]
    payload = ROOT_TXT_DELETE_VALIDATION_FILES[args.target]
    if source.name != filename or not source.is_file() or source.read_bytes() != payload:
        parser.error("source must be the exact named disposable fixture and payload")
    review_output = args.review_output.expanduser().resolve()
    if review_output.is_relative_to(REPOSITORY_ROOT) or review_output.exists():
        parser.error("review output must be a new file outside the repository")

    from infocarry.write_safety_boundary import create_default_application_write_safety_owner
    from infocarry.library_transfer_runtime_provider import ProductionLibraryTransferRuntimeProvider
    owner = create_default_application_write_safety_owner()
    owner.inspect_execution_boundary()
    runtime = ProductionLibraryTransferRuntimeProvider.for_current_application().create_root_txt_runtime(
        write_safety_owner=owner)
    facade = RootTxtPlacementFacade(runtime)
    try:
        bundle = facade.prepare(source, target_path=args.target, validation_placement=True)
        review = bundle.review_dict()
        identity = facade.owner_authorization_identity
        if identity is None or identity.to_dict() != review["owner_identity"]:
            raise ValueError("frozen placement lacks its exact owner identity")
        review_output.parent.mkdir(parents=True, exist_ok=True)
        _write_json(review_output, review)
        print(json.dumps({"state": "awaiting_owner_confirmation", "operation": "Add disposable TXT",
                          "target": args.target, "bytes": len(payload), "model": "VNW-V15",
                          "review": str(review_output), "prepared_root": str(bundle.source_path.parent),
                          "sender_calls": 0, "automatic_retry_allowed": False}), flush=True)
        phrase = bundle.authorization.core.confirmation_phrase
        entered = input(f"Add {filename} ({len(payload)} bytes) to Sony InfoCarry VNW-V15 once?\n"
                        "Device storage will change. The fresh complete backup and exact candidate are verified.\n"
                        "Existing content must remain preserved; no automatic retry.\n"
                        f"Enter {phrase} to approve this frozen operation, or anything else to cancel.\n> ")
        if entered != phrase:
            print("Cancelled before sender start; no device storage change.", flush=True)
            return 0
        if bundle.review_dict() != review or facade.owner_authorization_identity != identity:
            raise ValueError("frozen placement changed after owner confirmation")
        # The readable answer above supplies the sole human decision; the
        # framework still binds its complete internal operation identity.
        facade.authorize_prepared_operation(identity.approval_phrase)

        def confirmation(current_review):
            if current_review != review:
                raise ValueError("placement review changed at the guarded confirmation boundary")
            return entered

        result = facade.execute_once(confirmation_interaction=confirmation)
        if (type(result.completion) is not int or result.completion != 0
                or result.audit.get("state") != "readback_verified"
                or result.audit.get("workflow", {}).get("sender_calls") != 1):
            raise ValueError("placement lacks verified one-shot native success")
        print(json.dumps({"state": "readback_verified", "target": args.target,
                          "completion": "0x0000", "sender_calls": 1,
                          "automatic_retry_allowed": False,
                          "evidence_root": result.audit["evidence_outputs"]["root"]}), flush=True)
        return 0
    finally:
        facade.discard_prepared_operation()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as error:
        print(f"Stopped: {type(error).__name__}: {error}. No automatic retry.", file=sys.stderr)
        raise SystemExit(2)
