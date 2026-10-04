#!/usr/bin/env python3
"""Offline-only P18-041H preparation and evidence tooling.

Every command operates on caller-selected local files.  This script has no
USB discovery, Manager automation, sender, claim, marker, or device-write
path.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from infocarry.p18_041h_experiment import (  # noqa: E402
    EVENTS,
    P18041HError,
    build_owner_authorization_identity,
    create_session,
    experiment_manifest,
    inspect_native_capture,
    operation_binding,
    record_time_observation,
    seal_evidence,
    validate_fixture_source,
    verify_delete_evidence,
    write_json,
    write_manifest,
    write_event_mapping,
)


def _path(value: str) -> Path:
    return Path(value).expanduser()


def _json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise P18041HError(f"could not read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise P18041HError(f"JSON value is not an object: {path}")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline-only P18-041H preparation and evidence verification."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    manifest = commands.add_parser("manifest", help="print the immutable preparation manifest")
    manifest.add_argument("--output", type=_path)

    session = commands.add_parser("session", help="create a fresh evidence-session skeleton")
    session.add_argument("--destination", required=True, type=_path)

    fixture = commands.add_parser("validate-fixture", help="validate an exact local source copy")
    fixture.add_argument("source", type=_path)

    binding = commands.add_parser("operation-binding", help="write the exact one-delete operation binding")
    binding.add_argument("--output", required=True, type=_path)

    clock = commands.add_parser("observe-time", help="record one host/file-clock observation")
    clock.add_argument("--destination", required=True, type=_path)
    clock.add_argument("--event", required=True, choices=EVENTS)
    clock.add_argument("--fixture-source", type=_path)
    clock.add_argument("--device-clock-observation", type=_path)

    event_map = commands.add_parser("event-map", help="bind the four observations separately")
    event_map.add_argument("--destination", required=True, type=_path)
    for event in EVENTS:
        event_map.add_argument(f"--{event.replace('_', '-')}", required=True, type=_path)

    capture = commands.add_parser("capture-report", help="inspect one saved native 0x101b capture")
    capture.add_argument("capture", type=_path)
    capture.add_argument("--operation-binding", required=True, type=_path)
    capture.add_argument("--output", required=True, type=_path)
    capture.add_argument("--artifact-destination", type=_path)
    capture.add_argument(
        "--capture-phase",
        choices=("pre-execution", "post-execution-evidence"),
        default="post-execution-evidence",
    )

    verify = commands.add_parser("verify-delete", help="verify saved before/after evidence offline")
    verify.add_argument("--before", required=True, type=_path)
    verify.add_argument("--after", required=True, type=_path)
    verify.add_argument("--output", required=True, type=_path)
    verify.add_argument("--candidate-artifact", required=True, type=_path)
    verify.add_argument("--fixture-prestage-report", required=True, type=_path)
    verify.add_argument("--event-map", required=True, type=_path)
    verify.add_argument("--native-transaction-report", required=True, type=_path)
    verify.add_argument("--terminal-result", required=True, type=_path)

    seal = commands.add_parser("seal", help="seal independently verified evidence before recovery")
    seal.add_argument("--session-root", required=True, type=_path)
    seal.add_argument("--verification-report", required=True, type=_path)
    seal.add_argument("--destination", required=True, type=_path)

    identity = commands.add_parser(
        "owner-identity",
        help="freeze the exact owner-approval identity; rejects post-execution evidence",
    )
    identity.add_argument("--pre-delete-backup", required=True, type=_path)
    identity.add_argument("--capture-plan", required=True, type=_path)
    identity.add_argument("--recovery-plan", required=True, type=_path)
    identity.add_argument("--candidate-report", required=True, type=_path)
    identity.add_argument("--fixture-prestage-report", required=True, type=_path)
    identity.add_argument("--fixture-source", required=True, type=_path)
    identity.add_argument("--device-boundary", required=True, type=_path)
    identity.add_argument("--output", required=True, type=_path)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "manifest":
        value = experiment_manifest()
        if args.output is None:
            print(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            print(write_manifest(args.output))
        return 0
    if args.command == "session":
        print(create_session(args.destination))
        return 0
    if args.command == "validate-fixture":
        print(json.dumps(validate_fixture_source(args.source), ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    if args.command == "operation-binding":
        print(write_json(args.output, operation_binding()))
        return 0
    if args.command == "observe-time":
        print(record_time_observation(
            args.destination,
            args.event,
            fixture_source=args.fixture_source,
            device_clock_observation=args.device_clock_observation,
        ))
        return 0
    if args.command == "event-map":
        paths = {
            event: getattr(args, event.replace("-", "_"))
            for event in EVENTS
        }
        print(write_event_mapping(args.destination, paths))
        return 0
    if args.command == "capture-report":
        report = inspect_native_capture(
            args.capture,
            artifact_destination=args.artifact_destination,
            capture_phase=args.capture_phase,
            operation_binding_metadata=_json(args.operation_binding),
        )
        write_json(args.output, report)
        print(args.output)
        return 0
    if args.command == "verify-delete":
        report = verify_delete_evidence(
            args.before,
            args.after,
            candidate_artifact=args.candidate_artifact,
            fixture_prestage_report=args.fixture_prestage_report,
            time_event_map=args.event_map,
            native_transaction_report=args.native_transaction_report,
            terminal_result_path=args.terminal_result,
        )
        write_json(args.output, report)
        print(args.output)
        return 0
    if args.command == "seal":
        print(seal_evidence(
            args.session_root,
            verification_report=args.verification_report,
            destination=args.destination,
        ))
        return 0
    if args.command == "owner-identity":
        report = build_owner_authorization_identity(
            pre_delete_backup=args.pre_delete_backup,
            capture_plan=args.capture_plan,
            recovery_plan=args.recovery_plan,
            candidate_report=args.candidate_report,
            fixture_prestage_report=args.fixture_prestage_report,
            fixture_source=args.fixture_source,
            device_boundary=args.device_boundary,
        )
        write_json(args.output, report)
        print(args.output)
        return 0
    raise AssertionError(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except P18041HError as exc:
        print(f"P18-041H offline tooling refused: {exc}", file=sys.stderr)
        raise SystemExit(2)
