"""Command-line entry point. Only standard read-only USB operations exist."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional, Sequence

from .backup import BackupClient, RawBackupArchive
from .backup_format import (
    BackupExporter,
    BackupFormatError,
    load_complete_backup,
    load_complete_backup_bytes,
)
from .constants import INFOCARRY_PRODUCT_ID, SONY_VENDOR_ID
from .capture import CaptureError, RawInfoCapture
from .capture_artifact import CaptureArtifactError, preserve_capture_artifact
from .descriptors import DescriptorError, DescriptorSet, parse_descriptor_set
from .device_info import DeviceInfoClient, decode_info_response
from .desktop import DesktopWorkflowError, launch_desktop
from .runtime import DesktopRuntimeError
from .fixture_report import FixtureReportError, write_fixture_report
from .protocol import ProtocolError
from .usb_access import (
    DeviceAccessError,
    describe_device,
    find_devices,
    find_one_device,
    read_active_alternate_setting,
    read_raw_descriptors,
)
from .transport import InfoCarrySession
from .text_authoring import TextAuthoringError, preview_decoded_text_replacement
from .workflow import WorkflowError, build_backup_inventory, save_json_report


def _descriptor_payload(descriptors: DescriptorSet, raw_device: bytes, raw_config: bytes) -> Dict[str, Any]:
    payload = descriptors.to_dict()
    payload["raw_device_descriptor_hex"] = raw_device.hex(" ")
    payload["raw_configuration_descriptor_hex"] = raw_config.hex(" ")
    return payload


def _print_human(descriptors: DescriptorSet) -> None:
    device = descriptors.device
    configuration = descriptors.configuration
    print(f"Sony InfoCarry {device.vendor_id:04x}:{device.product_id:04x}")
    print(
        f"USB {device.usb_version_bcd >> 8}.{device.usb_version_bcd & 0xff:02x}, "
        f"EP0 {device.endpoint_zero_max_packet_size} bytes, "
        f"{device.configuration_count} configuration"
    )
    print(
        f"Configuration {configuration.configuration_value}: "
        f"{configuration.max_power_ma} mA, attributes 0x{configuration.attributes:02x}"
    )
    if descriptors.active_alternate_setting is not None:
        print(f"Active alternate setting: {descriptors.active_alternate_setting}")
    else:
        print("Active alternate setting: unavailable")
    for interface in configuration.interfaces:
        marker = " (active)" if interface.alternate_setting == descriptors.active_alternate_setting else ""
        print(
            f"Interface {interface.number}, alternate {interface.alternate_setting}{marker}: "
            f"class 0x{interface.interface_class:02x}, "
            f"subclass 0x{interface.interface_subclass:02x}, "
            f"protocol 0x{interface.interface_protocol:02x}"
        )
        for endpoint in interface.endpoints:
            print(
                f"  0x{endpoint.address:02x} {endpoint.direction.upper()} "
                f"{endpoint.transfer_type_name}, max packet {endpoint.max_packet_size} bytes"
            )


def command_detect(json_output: bool) -> int:
    devices = [describe_device(device) for device in find_devices()]
    if json_output:
        print(json.dumps([device.__dict__ for device in devices], indent=2, sort_keys=True))
    elif not devices:
        print(f"No Sony InfoCarry {SONY_VENDOR_ID:04x}:{INFOCARRY_PRODUCT_ID:04x} detected")
    else:
        for device in devices:
            print(
                f"Sony InfoCarry {device.vendor_id:04x}:{device.product_id:04x} "
                f"on bus {device.bus}, address {device.address}"
            )
    return 0 if devices else 1


def command_descriptors(json_output: bool) -> int:
    device = find_one_device()
    raw_device, raw_configuration = read_raw_descriptors(device)
    active_alt = read_active_alternate_setting(device)
    descriptors = parse_descriptor_set(raw_device, raw_configuration, active_alt)
    if json_output:
        print(
            json.dumps(
                _descriptor_payload(descriptors, raw_device, raw_configuration),
                indent=2,
                sort_keys=True,
            )
        )
    else:
        _print_human(descriptors)
    return 0


def command_open_check(json_output: bool, cycles: int) -> int:
    """Claim and release the verified interface without an application command."""

    results = []
    for cycle in range(1, cycles + 1):
        with InfoCarrySession.open() as session:
            results.append(
                {
                    "cycle": cycle,
                    "interface": 0,
                    "alternate_setting": 0,
                    "bulk_in": session.endpoints.bulk_in,
                    "bulk_out": session.endpoints.bulk_out,
                    "max_packet_size": session.endpoints.max_packet_size,
                }
            )
    if json_output:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        for result in results:
            print(
                f"Open/close cycle {result['cycle']} succeeded: interface 0 alt 0, "
                f"bulk OUT 0x{result['bulk_out']:02x}, "
                f"bulk IN 0x{result['bulk_in']:02x}"
            )
    return 0


def command_info(json_output: bool, query: str, save_raw: Path) -> int:
    """Run only the verified information queries and preserve bytes immediately."""

    capture = RawInfoCapture.create(save_raw)
    entries = []
    with InfoCarrySession.open() as session:
        client = DeviceInfoClient(session)
        if query in ("configuration", "all"):
            response = client.read_configuration()
            entry = capture.save(response)
            entry["decoded"] = decode_info_response(response)
            entries.append(entry)
        if query in ("hardware", "all"):
            response = client.read_hardware()
            entry = capture.save(response)
            entry["decoded"] = decode_info_response(response)
            entries.append(entry)
    capture.finalize()
    payload = {
        "capture_directory": str(capture.directory),
        "responses": entries,
    }
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Raw responses preserved in {capture.directory}")
        for entry in entries:
            print(
                f"  {entry['command']} {entry['kind']}: {entry['length']} bytes, "
                f"SHA-256 {entry['sha256']}"
            )
            if entry["kind"] == "hardware":
                decoded = entry["decoded"]
                print(
                    f"    display: {decoded['display_width_pixels']} x "
                    f"{decoded['display_height_pixels']} pixels"
                )
    return 0


def command_backup(json_output: bool, destination: Path) -> int:
    """Create a lossless archive using only the recovered receive commands."""

    archive = RawBackupArchive.create(destination)
    try:
        with InfoCarrySession.open() as session:
            objects = BackupClient(session).backup(archive)
    except (Exception, KeyboardInterrupt) as exc:
        try:
            archive.mark_incomplete(exc)
        except CaptureError:
            pass
        raise
    payload = {
        "backup_directory": str(archive.directory),
        "state": "complete",
        "objects": list(objects),
    }
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Raw backup preserved in {archive.directory}")
        for entry in objects:
            print(
                f"  {entry['sequence']:02d} {entry['command']} {entry['kind']}: "
                f"{entry['received_length']} bytes, SHA-256 {entry['sha256']}"
            )
    return 0


def command_export(
    json_output: bool, backup_directory: Path, destination: Path
) -> int:
    """Parse and export a complete backup without accessing USB hardware."""

    parsed, source_digest = load_complete_backup(backup_directory)
    manifest = BackupExporter(parsed, source_digest).export(destination)
    payload = {
        "export_directory": str(destination.expanduser().resolve()),
        "source_blob_sha256": source_digest,
        "summary": manifest["summary"],
    }
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        summary = manifest["summary"]
        print(f"Export preserved in {payload['export_directory']}")
        print(
            f"  {summary['directories']} directories, {summary['files']} files, "
            f"{summary['orphan_records']} orphan records"
        )
        print(f"  source blob SHA-256 {source_digest}")
    return 0


def _parse_record_offset(value: str) -> int:
    try:
        offset = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "record offset must be an integer such as 0xc0"
        ) from exc
    if offset < 0:
        raise argparse.ArgumentTypeError("record offset must be non-negative")
    return offset


def command_inventory(
    json_output: bool, backup_directory: Path, report_destination: Optional[Path]
) -> int:
    """List reachable backup records without accessing USB hardware."""

    parsed, source_digest = load_complete_backup(backup_directory)
    report = build_backup_inventory(parsed, source_digest)
    saved = None
    if report_destination is not None:
        saved = save_json_report(report_destination, report)
    if json_output:
        payload = dict(report)
        if saved is not None:
            payload["report_path"] = str(saved)
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        summary = report["summary"]
        print(
            f"Backup inventory: {summary['files']} files, "
            f"{summary['directories']} directories, "
            f"{summary['unresolved']} unresolved records"
        )
        for record in report["records"]:
            suffix = ""
            if record["kind"] == "file":
                suffix = f" ({record['payload_bytes']} bytes, {record['read_state']})"
            print(f"{record['record_offset']} {record['path']}{suffix}")
        if saved is not None:
            print(f"Inventory report preserved in {saved}")
    return 0


def command_preview_text(
    json_output: bool,
    backup_directory: Path,
    record_offset: int,
    text_path: Path,
    max_payload_bytes: Optional[int],
    report_destination: Optional[Path],
) -> int:
    """Preview one CP932 text replacement entirely offline."""

    raw, source_digest = load_complete_backup_bytes(backup_directory)
    try:
        text = text_path.expanduser().read_text(encoding="utf-8")
    except OSError as exc:
        raise TextAuthoringError(f"could not read UTF-8 text input: {exc}") from exc
    report = preview_decoded_text_replacement(
        raw,
        record_offset,
        text,
        max_payload_bytes=max_payload_bytes,
    )
    report["workflow"] = {
        "source_backup_blob_sha256": source_digest,
        "input_path": str(text_path.expanduser().resolve()),
        "device_accessed": False,
        "candidate_bytes_included": False,
    }
    saved = None
    if report_destination is not None:
        saved = save_json_report(report_destination, report)
    if json_output:
        payload = dict(report)
        if saved is not None:
            payload["report_path"] = str(saved)
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        target = report["target"]
        authoring = report["authoring"]
        print(f"Text preview for {target.get('path') or target['record_offset']}")
        print(
            f"  encoded payload: {authoring['encoded_payload_bytes']} bytes "
            f"({authoring['encoding']}, {authoring['newline_policy'].upper()})"
        )
        print("  candidate bytes included: no; device accessed: no")
        if saved is not None:
            print(f"Preview report preserved in {saved}")
    return 0


def command_desktop() -> int:
    """Launch the optional no-write desktop workflow shell."""

    launch_desktop()
    return 0


def command_fixture_report(
    json_output: bool, fixture_root: Path, destination: Path
) -> int:
    """Verify and summarize a preserved manager fixture without USB access."""

    manifest = write_fixture_report(fixture_root, destination)
    payload = {
        "report_directory": str(destination.expanduser().resolve()),
        "format": manifest["format"],
        "fixture_root": manifest["fixture_root"],
        "files": manifest["files"],
        "backup_summary": manifest["vicdata"]["summary"],
        "correlation_counts": {
            name: len(entries)
            for name, entries in manifest["correlations"].items()
        },
    }
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        summary = manifest["vicdata"]["summary"]
        print(f"Fixture report preserved in {payload['report_directory']}")
        print(
            f"  {summary['records']} backup records, {summary['files']} files, "
            f"{summary['directories']} directories"
        )
        print(
            "  correlations: "
            + ", ".join(
                f"{name} {count}"
                for name, count in payload["correlation_counts"].items()
            )
        )
    return 0


def command_capture_artifact(
    json_output: bool,
    capture_path: Path,
    destination: Path,
    transaction_index: int,
) -> int:
    """Preserve one parsed native 0x101b capture as an offline artifact."""

    artifact = preserve_capture_artifact(
        capture_path, destination, transaction_index=transaction_index
    )
    payload = {
        "artifact_directory": str(artifact),
        "capture": str(capture_path.expanduser().resolve()),
        "transaction_index": transaction_index,
        "usb_transmission_performed": False,
    }
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Offline prospective artifact preserved in {artifact}")
        print("  USB transmission performed: no")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="infocarry",
        description="Read-only discovery tools for the Sony InfoCarry VNW-V15",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("detect", "descriptors"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    open_check = subparsers.add_parser(
        "open-check",
        help="claim and release interface 0 without sending an InfoCarry command",
    )
    open_check.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    open_check.add_argument(
        "--cycles",
        type=int,
        default=1,
        choices=range(1, 11),
        metavar="1..10",
        help="number of open/close cycles (default: 1)",
    )
    info = subparsers.add_parser(
        "info",
        help="query verified read-only device information and preserve raw bytes",
    )
    info.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    info.add_argument(
        "--query",
        choices=("configuration", "hardware", "all"),
        default="all",
        help="information response to request (default: all)",
    )
    info.add_argument(
        "--save-raw",
        type=Path,
        required=True,
        metavar="NEW_DIRECTORY",
        help="new directory in which raw responses and hashes will be preserved",
    )
    backup = subparsers.add_parser(
        "backup",
        help="create a complete lossless read-only backup in a new directory",
    )
    backup.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    backup.add_argument(
        "destination",
        type=Path,
        metavar="NEW_DIRECTORY",
        help="new directory in which raw objects and hashes will be preserved",
    )
    export = subparsers.add_parser(
        "export",
        help="export files from a complete raw backup without accessing the device",
    )
    export.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    export.add_argument(
        "backup_directory",
        type=Path,
        metavar="BACKUP_DIRECTORY",
        help="complete raw backup archive created by the backup command",
    )
    export.add_argument(
        "destination",
        type=Path,
        metavar="NEW_DIRECTORY",
        help="new directory for exact native files and decoded text views",
    )
    inventory = subparsers.add_parser(
        "inventory",
        help="list reachable records from a complete backup without USB access",
    )
    inventory.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    inventory.add_argument(
        "--save-report",
        type=Path,
        metavar="NEW_DIRECTORY",
        help="also preserve the inventory JSON in a new directory",
    )
    inventory.add_argument(
        "backup_directory",
        type=Path,
        metavar="BACKUP_DIRECTORY",
        help="complete raw backup archive",
    )
    preview_text = subparsers.add_parser(
        "preview-text",
        help="preview a CP932/CRLF text replacement without USB access",
    )
    preview_text.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    preview_text.add_argument(
        "--max-bytes",
        type=int,
        metavar="N",
        help="optional caller-supplied encoded payload limit",
    )
    preview_text.add_argument(
        "--save-report",
        type=Path,
        metavar="NEW_DIRECTORY",
        help="also preserve the preview JSON in a new directory",
    )
    preview_text.add_argument(
        "backup_directory",
        type=Path,
        metavar="BACKUP_DIRECTORY",
        help="complete raw backup archive",
    )
    preview_text.add_argument(
        "record_offset",
        type=_parse_record_offset,
        metavar="RECORD_OFFSET",
        help="file record offset, for example 0xc0",
    )
    preview_text.add_argument(
        "text_file",
        type=Path,
        metavar="UTF8_TEXT_FILE",
        help="UTF-8 source text; line endings are normalized to CRLF",
    )
    subparsers.add_parser(
        "desktop",
        help="open the offline backup browsing and text-preview window",
    )
    fixture_report = subparsers.add_parser(
        "fixture-report",
        help="verify a preserved manager fixture and write an offline JSON report",
    )
    fixture_report.add_argument(
        "--json", action="store_true", help="emit a machine-readable summary"
    )
    fixture_report.add_argument(
        "fixture_root",
        type=Path,
        metavar="FIXTURE_DIRECTORY",
        help="directory containing Backup/, Memo/, and ICM/order.vnw",
    )
    fixture_report.add_argument(
        "destination",
        type=Path,
        metavar="NEW_DIRECTORY",
        help="new directory in which the JSON report will be preserved",
    )
    capture_artifact = subparsers.add_parser(
        "capture-artifact",
        help="extract one native 0x101b transaction into an offline artifact",
    )
    capture_artifact.add_argument(
        "--json", action="store_true", help="emit a machine-readable summary"
    )
    capture_artifact.add_argument(
        "--transaction-index",
        type=int,
        default=0,
        metavar="N",
        help="zero-based 0x101b transaction to extract (default: 0)",
    )
    capture_artifact.add_argument(
        "capture_path",
        type=Path,
        metavar="USBLOG_FILE",
        help="native SnoopyPro capture; it is never modified",
    )
    capture_artifact.add_argument(
        "destination",
        type=Path,
        metavar="NEW_DIRECTORY",
        help="new directory for the offline prospective artifact",
    )
    return parser


def main(argv: Sequence[str] = ()) -> int:
    args = build_parser().parse_args(list(argv) if argv else None)
    try:
        if args.command == "detect":
            return command_detect(args.json)
        if args.command == "descriptors":
            return command_descriptors(args.json)
        if args.command == "open-check":
            return command_open_check(args.json, args.cycles)
        if args.command == "info":
            return command_info(args.json, args.query, args.save_raw)
        if args.command == "backup":
            return command_backup(args.json, args.destination)
        if args.command == "export":
            return command_export(
                args.json, args.backup_directory, args.destination
            )
        if args.command == "inventory":
            return command_inventory(
                args.json, args.backup_directory, args.save_report
            )
        if args.command == "preview-text":
            return command_preview_text(
                args.json,
                args.backup_directory,
                args.record_offset,
                args.text_file,
                args.max_bytes,
                args.save_report,
            )
        if args.command == "desktop":
            return command_desktop()
        if args.command == "fixture-report":
            return command_fixture_report(
                args.json, args.fixture_root, args.destination
            )
        if args.command == "capture-artifact":
            return command_capture_artifact(
                args.json,
                args.capture_path,
                args.destination,
                args.transaction_index,
            )
        raise AssertionError(f"unhandled command {args.command}")
    except KeyboardInterrupt:
        print("error: operation interrupted; any preserved backup remains on disk", file=sys.stderr)
        return 130
    except (
        BackupFormatError,
        CaptureError,
        DescriptorError,
        DeviceAccessError,
        FixtureReportError,
        ProtocolError,
        CaptureArtifactError,
        TextAuthoringError,
        WorkflowError,
        DesktopWorkflowError,
        DesktopRuntimeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
