#!/usr/bin/env python3
"""Offline-only preparation and evidence-ingestion support for I7.

This command never opens USB, invokes Windows software, parses a live device,
or sends a device-changing request.  It creates only caller-selected local
fixture/session/report files and refuses to overwrite them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from infocarry.i7_experiment import (  # noqa: E402
    I7ExperimentError,
    compare_i7_backups,
    create_i7_session,
    create_synthetic_fixture,
    hash_manager_snapshot,
    ingest_snoopy_log,
    create_i7_delete_session,
    preflight_i7_legacy_delete,
    record_host_clock,
    validate_complete_backup,
    validate_synthetic_fixture,
    write_report,
)


def _path(value: str) -> Path:
    return Path(value).expanduser()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline-only I.7 experiment preparation; no USB operation is available."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fixture = subparsers.add_parser("fixture", help="create or validate the synthetic source")
    fixture.add_argument("--destination", required=True, type=_path)
    fixture.add_argument("--validate", action="store_true")

    session = subparsers.add_parser("session", help="create a new empty evidence-session skeleton")
    session.add_argument("--destination", required=True, type=_path)
    session.add_argument("--source", type=_path)

    delete_session = subparsers.add_parser(
        "delete-session", help="create a new offline legacy-delete session skeleton"
    )
    delete_session.add_argument("--destination", required=True, type=_path)

    clock = subparsers.add_parser("clock", help="record a host clock, never the device clock")
    clock.add_argument("--destination", required=True, type=_path)
    clock.add_argument("--host-label", required=True)

    backup = subparsers.add_parser("backup-report", help="validate one complete backup offline")
    backup.add_argument("backup_directory", type=_path)
    backup.add_argument("--output", required=True, type=_path)

    manager = subparsers.add_parser("manager-report", help="hash one Manager snapshot offline")
    manager.add_argument("snapshot_directory", type=_path)
    manager.add_argument("--output", required=True, type=_path)

    snoopy = subparsers.add_parser("snoopy-report", help="ingest one saved native log offline")
    snoopy.add_argument("capture_path", type=_path)
    snoopy.add_argument("--output", required=True, type=_path)

    compare = subparsers.add_parser("compare-backups", help="compare two complete backups offline")
    compare.add_argument("before_directory", type=_path)
    compare.add_argument("after_directory", type=_path)
    compare.add_argument("--output", required=True, type=_path)
    compare.add_argument("--source-sha256")
    compare.add_argument("--target-path")

    delete_preflight = subparsers.add_parser(
        "delete-preflight", help="preflight one saved legacy-delete backup offline"
    )
    delete_preflight.add_argument("backup_directory", type=_path)
    delete_preflight.add_argument("--output", required=True, type=_path)
    delete_preflight.add_argument("--timestamp-directory", type=_path)
    delete_preflight.add_argument("--session-root", type=_path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "fixture":
        report = (
            validate_synthetic_fixture(args.destination)
            if args.validate
            else create_synthetic_fixture(args.destination)
        ).to_dict()
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    if args.command == "session":
        fixture = validate_synthetic_fixture(args.source) if args.source else None
        print(create_i7_session(args.destination, fixture=fixture))
        return 0
    if args.command == "delete-session":
        print(create_i7_delete_session(args.destination))
        return 0
    if args.command == "clock":
        print(record_host_clock(args.destination, args.host_label))
        return 0
    if args.command == "backup-report":
        report = validate_complete_backup(args.backup_directory)
        print(write_report(args.output, report))
        return 0
    if args.command == "manager-report":
        report = hash_manager_snapshot(args.snapshot_directory)
        print(write_report(args.output, report))
        return 0
    if args.command == "snoopy-report":
        report = ingest_snoopy_log(args.capture_path)
        print(write_report(args.output, report))
        return 0
    if args.command == "compare-backups":
        report = compare_i7_backups(
            args.before_directory,
            args.after_directory,
            expected_target_path=args.target_path or r"root\IC_I7_CLOCK_01.txt",
            source_sha256=args.source_sha256,
        )
        print(write_report(args.output, report))
        return 0
    if args.command == "delete-preflight":
        report = preflight_i7_legacy_delete(
            args.backup_directory,
            timestamp_directory=args.timestamp_directory,
            session_root=args.session_root,
        )
        print(write_report(args.output, report))
        return 0
    raise AssertionError(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except I7ExperimentError as exc:
        print(f"I7 offline support refused: {exc}", file=sys.stderr)
        raise SystemExit(2)
