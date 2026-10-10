#!/usr/bin/env python3
"""Offline candidate preparation or separately approved exact fixture Delete.

Default execution is offline. --allow-write uses the existing canonical
runtime, safety owner and sender, and prompts for one target-specific phrase.
Never run that mode as part of an offline development task.
"""
from pathlib import Path
import argparse
import json
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from infocarry.delete_workflow import (
    build_experimental_root_txt_delete, ExperimentalRootTxtDeleteFacade,
    ROOT_TXT_DELETE_CONFIRMATION, EXPERIMENTAL_ROOT_TXT_DELETE_PROFILE,
    build_root_txt_delete, ROOT_TXT_DELETE_HOST_PROFILE, ROOT_TXT_DELETE_VALIDATION_FILES,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, help="existing complete backup, offline mode only")
    parser.add_argument("--output", type=Path, help="new directory outside the repository, offline mode only")
    parser.add_argument("--allow-write", action="store_true", help="separately owner-authorized physical experiment")
    parser.add_argument("--target", help="ordinary root TXT path for offline preparation only")
    parser.add_argument("--manager-validation-target", choices=tuple(ROOT_TXT_DELETE_VALIDATION_FILES),
        help="separately authorized disposable validation through the normal Manager Delete UI")
    args = parser.parse_args(argv)
    if not args.allow_write:
        if args.manager_validation_target:
            parser.error("Manager validation requires explicit --allow-write and separate owner authorization")
        if args.backup is None or args.output is None:
            parser.error("offline mode requires --backup and --output")
        output = args.output.expanduser().resolve()
        if output.is_relative_to(REPOSITORY_ROOT):
            parser.error("raw candidate evidence must remain outside the repository")
        core = build_root_txt_delete(args.backup, args.target) if args.target else build_experimental_root_txt_delete(args.backup)
        profile = ROOT_TXT_DELETE_HOST_PROFILE if args.target else EXPERIMENTAL_ROOT_TXT_DELETE_PROFILE
        output.mkdir(parents=True, exist_ok=False)
        core.transaction.preserve(output / "transaction", source="offline-exact-root-txt-delete")
        with (output / "candidate.bin").open("xb") as file:
            file.write(core.candidate_blob)
        report = core.to_dict()
        report["experimental_profile"] = profile
        report["physical_operation_authorized"] = False
        with (output / "offline-report.json").open("x", encoding="utf-8") as file:
            json.dump(report, file, indent=2, sort_keys=True)
            file.write("\n")
        print(json.dumps({"profile": profile,
                          "candidate_sha256": core.candidate_blob_sha256,
                          "transaction_sha256": core.transaction_sha256,
                          "output": str(output), "usb_operations": 0}, indent=2))
        return 0
    if args.backup is not None or args.output is not None or args.target is not None:
        parser.error("write mode must obtain its own fresh backup; offline inputs cannot be adopted")
    # No USB or installation-state setup is reached without the explicit flag.
    from infocarry.write_safety_boundary import create_default_application_write_safety_owner
    from infocarry.library_transfer_runtime_provider import ProductionLibraryTransferRuntimeProvider
    owner = create_default_application_write_safety_owner()
    owner.inspect_execution_boundary()
    if args.manager_validation_target:
        from infocarry.desktop_ttk import launch_ttk_desktop
        from infocarry.device_library_delete_execution import DeviceLibraryDeleteService
        from infocarry.library_transfer_execution import LibraryTransferExecutionFacade
        provider = ProductionLibraryTransferRuntimeProvider.for_current_application()
        service = DeviceLibraryDeleteService(
            lambda: provider.create_root_txt_runtime(write_safety_owner=owner),
            validation_target=args.manager_validation_target)
        # Only the named disposable Delete is available in this explicit mode;
        # transfer has no configured runtime/provider. Startup opens no USB.
        launch_ttk_desktop(execution_facade=LibraryTransferExecutionFacade(), delete_service=service)
        return 0
    runtime = ProductionLibraryTransferRuntimeProvider.for_current_application().create_root_txt_runtime(
        write_safety_owner=owner)
    facade = ExperimentalRootTxtDeleteFacade(runtime)
    try:
        bundle = facade.prepare()  # fresh read-only capacity and complete backup
        review = bundle.review_dict()
        print("Sony VNW-V15 — experimental Delete")
        print("Target: " + review["target"])
        print("Exact 29-byte fixture verified; fresh complete backup verified.")
        print("Candidate prepared; protected survivor state verified.")
        print("One operation; no automatic retry. Complete post-write verification required.")
        entered = input(ROOT_TXT_DELETE_CONFIRMATION + "\n> ")
        facade.authorize_prepared_operation(entered)
        # Reuse the single actual owner answer at the canonical confirmation
        # boundary, while rejecting any intervening reviewed operation change.
        def confirmation(current_review):
            if current_review != review:
                raise ValueError("review changed after owner confirmation")
            return entered
        result = facade.execute_once(confirmation_interaction=confirmation)
        print("Delete complete — exact content and protected state verified.")
        print("Evidence: " + result.audit["evidence_outputs"]["root"])
        return 0
    finally:
        facade.discard_prepared_operation()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as error:
        print(f"Stopped: {type(error).__name__}: {error}. No automatic retry.", file=sys.stderr)
        raise SystemExit(2)
