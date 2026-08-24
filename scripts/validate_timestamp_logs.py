#!/usr/bin/env python3
"""Validate Windows 2000 timestamp logs without touching a device."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from infocarry.timestamp_validator import (  # noqa: E402
    TimestampValidationError,
    validate_timestamp_logs,
    write_validation_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only validation of Windows 2000 timestamp logs."
    )
    parser.add_argument("logs_directory", type=Path)
    parser.add_argument("--mapping", type=Path)
    parser.add_argument("--required-event", action="append", default=[])
    parser.add_argument("--max-gap-ms", type=int, default=None)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    kwargs = {
        "event_mapping": args.mapping,
        "required_events": tuple(args.required_event),
    }
    if args.max_gap_ms is not None:
        kwargs["max_gap_ms"] = args.max_gap_ms
    try:
        report = validate_timestamp_logs(args.logs_directory, **kwargs)
        output = write_validation_report(args.output, report)
    except (OSError, TimestampValidationError, ValueError) as exc:
        print(f"timestamp validation refused: {exc}", file=sys.stderr)
        return 2
    print(output)
    print("valid=" + str(report["valid"]).lower())
    return 0 if report["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
