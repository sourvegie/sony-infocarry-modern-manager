#!/usr/bin/env python3
"""Offline disposable root-BMP fixture and Delete preparation. No write mode."""
from pathlib import Path
import argparse
import json
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from infocarry.delete_workflow import (
    ROOT_BMP_DELETE_FIXTURE_BYTES, ROOT_BMP_DELETE_FIXTURE_FILENAME,
    ROOT_BMP_DELETE_FIXTURE_SHA256, prepare_disposable_root_bmp_delete,
    require_external_bmp_output,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fixture = commands.add_parser("fixture", help="create only the disposable BMP on the host")
    fixture.add_argument("--output", type=Path, required=True, help="new directory outside Git")
    prepare = commands.add_parser("prepare", help="prepare from a complete backup containing the exact fixture")
    prepare.add_argument("--backup", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True, help="new private directory outside Git")
    prepare.add_argument("--post-backup", type=Path, help="optional complete post-delete backup for offline verification")
    prepare.add_argument("--completion", type=lambda s: int(s, 0), help="observed native result, required with --post-backup")
    args = parser.parse_args(argv)
    output = require_external_bmp_output(args.output)
    if output.is_relative_to(REPOSITORY_ROOT):
        parser.error("output must remain outside the source repository")
    if args.command == "fixture":
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        with (output / ROOT_BMP_DELETE_FIXTURE_FILENAME).open("xb") as stream:
            stream.write(ROOT_BMP_DELETE_FIXTURE_BYTES)
        result = {"status": "host_fixture_only", "file": str(output / ROOT_BMP_DELETE_FIXTURE_FILENAME),
                  "bytes": len(ROOT_BMP_DELETE_FIXTURE_BYTES), "sha256": ROOT_BMP_DELETE_FIXTURE_SHA256}
    else:
        if (args.post_backup is None) != (args.completion is None):
            parser.error("--post-backup and the actually observed --completion must be supplied together")
        if args.post_backup is not None and output.is_relative_to(args.post_backup.expanduser().resolve()):
            parser.error("output must not modify the post-delete backup")
        prepared = prepare_disposable_root_bmp_delete(args.backup, output)
        core = prepared.verify()
        result = {"status": "host_prepared_not_live_enabled", "report": str(output / "preparation.json"),
                  "candidate_sha256": core.candidate_blob_sha256, "transaction_sha256": core.transaction_sha256}
        if args.post_backup is not None:
            verification = prepared.verify_readback(args.post_backup, completion=args.completion).to_dict()
            with (output / "offline-readback.json").open("x", encoding="utf-8") as stream:
                json.dump(verification, stream, indent=2, sort_keys=True)
                stream.write("\n")
            result["offline_readback_verified"] = True
    result.update(execution_available=False, physical_operation_authorized=False, usb_operations=0)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as error:
        print(f"Stopped: {type(error).__name__}: {error}. No physical operation was performed.", file=sys.stderr)
        raise SystemExit(2)
