import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import struct
import unittest

from infocarry.backup_format import calculate_backup_checksum, parse_backup_blob
from infocarry.backup_repack import delete_existing_file
from infocarry.payload_builder import build_from_decoded_vicdata, build_offline_payload
from infocarry.write_artifact import ProspectiveWriteTransaction, build_staging_range
from infocarry.p18_041h_experiment import (
    EVENTS,
    FIXTURE_BYTES,
    FIXTURE_FILENAME,
    FIXTURE_LENGTH,
    FIXTURE_PATH,
    FIXTURE_SHA256,
    IdentityNotFrozenError,
    inspect_native_capture,
    P18041HError,
    build_owner_authorization_identity,
    create_session,
    experiment_manifest,
    operation_binding,
    recovery_plan_contract,
    record_time_observation,
    seal_evidence,
    write_json,
    validate_fixture_source,
    verify_delete_evidence,
    write_event_mapping,
)

try:
    from test_backup_format import make_text_blob
    from test_capture_artifact import _capture_bytes
except ModuleNotFoundError:
    from tests.test_backup_format import make_text_blob
    from tests.test_capture_artifact import _capture_bytes


def _write_complete_backup(root: Path, blob: bytes) -> None:
    root.mkdir(exist_ok=True)
    objects = []
    raw_objects = [
        (0x0024, "response-0024", b"A" * 64),
        (0x001B, "response-001b", b"B" * 64),
        (0x001C, "response-001c", b"C" * 64),
        (0x001D, "response-001d", b"D" * 64),
        (0x001E, "response-001e", b"E" * 64),
        (0x001F, "response-001f", b"F" * 64),
        (0x8004, "backup-blob-probe", b"G" * 64),
        (0x8004, "backup-blob", blob),
    ]
    for ordinal, (command, kind, data) in enumerate(raw_objects, start=1):
        filename = f"object-{ordinal:02d}.bin"
        (root / filename).write_bytes(data)
        objects.append(
            {
                "sequence": ordinal,
                "command": f"0x{command:04x}",
                "kind": kind,
                "filename": filename,
                "received_length": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    timestamp = datetime.now(timezone.utc).isoformat()
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "format": "infocarry-raw-backup-v1",
                "state": "complete",
                "created_at_utc": timestamp,
                "updated_at_utc": timestamp,
                "device": {"vendor_id": "0x054c", "product_id": "0x001e"},
                "objects": objects,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _fixture_blob() -> bytes:
    raw = bytearray(make_text_blob(FIXTURE_BYTES))
    name_start = 0xC0 + 0x18
    name_end = 0xC0 + 0x40
    encoded = Path(FIXTURE_FILENAME).stem.encode("cp932")
    raw[name_start:name_end] = encoded + b"\x00" + raw[name_start + len(encoded) + 1 : name_end]
    raw[0x1C:0x20] = b"\x00" * 4
    raw[0x1C:0x20] = calculate_backup_checksum(bytes(raw)).to_bytes(4, "big")
    return bytes(raw)


def _write_prestage_report(path: Path) -> Path:
    write_json(
        path,
        {
            "format": "infocarry-p18-041h-separate-fixture-placement-v1",
            "experiment_id": "P18-041H",
            "status": "completed_and_independently_verified",
            "operation": "separate_fixture_placement",
            "completed_before_delete": True,
            "placement_readback_verified": True,
            "owner_authorization_status": "separate_owner_authorized",
            "physical_operation_count": 1,
            "add_count": 1,
            "delete_count": 0,
            "subtree_operation": False,
            "retry_count": 0,
            "sender_invocations": 1,
            "fixture": {
                "filename": FIXTURE_FILENAME,
                "device_path": FIXTURE_PATH,
                "kind": "ordinary_root_level_txt",
                "content_encoding": "ASCII subset / CP932-compatible",
                "line_ending": "CRLF",
                "content_length": FIXTURE_LENGTH,
                "sha256": FIXTURE_SHA256,
            },
            "post_placement_backup": {
                "manifest_sha256": "a" * 64,
                "blob_sha256": "b" * 64,
            },
        },
    )
    return path


def _candidate_and_terminal(root: Path, after_blob: bytes) -> tuple[Path, Path, Path]:
    states = tuple(
        type("State", (), {
            "count": 1,
            "value_04_be16": index,
            "value_06_be16": index + 1,
            "record_offsets": (0x100 + index,),
        })()
        for index in range(4)
    )
    grouped = type("Grouped", (), {"groups": ((1, 2, 3, 4, 5), (6, 7, 8, 9, 10))})()
    transaction = build_from_decoded_vicdata(
        after_blob,
        states,
        grouped,
    )
    artifact = transaction.preserve(root / "candidate", source="synthetic P18-041H test candidate")
    binding = operation_binding()
    write_json(artifact / "operation-binding.json", binding)
    native_log = root / "raw-delete.usblog"
    native_log.write_bytes(_capture_from_transaction(transaction))
    native_log_hash = hashlib.sha256(native_log.read_bytes()).hexdigest()
    report = inspect_native_capture(
        native_log,
        capture_phase="post-execution-evidence",
        operation_binding_metadata=binding,
    )
    report["candidate_artifact"] = {
        "directory": str(artifact),
        "manifest_sha256": hashlib.sha256((artifact / "manifest.json").read_bytes()).hexdigest(),
        "operation_binding_sha256": hashlib.sha256((artifact / "operation-binding.json").read_bytes()).hexdigest(),
    }
    transaction_report_path = root / "native-transaction-report.json"
    write_json(transaction_report_path, report)
    terminal = {
        "format": "infocarry-p18-041h-native-terminal-result-v1",
        "experiment_id": "P18-041H",
        "status": "normal_terminal_success",
        "normal_return": True,
        "native_completion": "0x0000",
        "sender_invocations": 1,
        "retry_count": 0,
        "physical_operation_count": 1,
        "add_count": 0,
        "subtree_operation": False,
        "target_path": FIXTURE_PATH,
        "native_log_sha256": native_log_hash,
        "candidate_blob_sha256": report["candidate_blob_sha256"],
        "transaction_sha256": report["transaction_sha256"],
    }
    terminal_path = root / "native-terminal-result.json"
    terminal["transaction_report_sha256"] = hashlib.sha256(transaction_report_path.read_bytes()).hexdigest()
    write_json(terminal_path, terminal)
    return artifact, transaction_report_path, terminal_path


def _capture_from_transaction(transaction: ProspectiveWriteTransaction) -> bytes:
    def native_payload(payload: bytes) -> bytes:
        record = bytearray(0x1A)
        record[:4] = b"\x48\x00\x09\x00"
        struct.pack_into("<H", record, 0x14, len(payload))
        struct.pack_into("<H", record, 0x18, 1)
        record.extend(payload)
        completion = bytearray(0x1A)
        completion[:4] = b"\x48\x00\x09\x00"
        struct.pack_into("<H", completion, 0x14, 2)
        struct.pack_into("<H", completion, 0x18, len(payload))
        return bytes(record + completion)

    payloads = [transaction.ranges[0], transaction.ranges[1]]
    payloads.extend(
        transaction.ranges[2][offset : offset + 0x1000]
        for offset in range(0, len(transaction.ranges[2]), 0x1000)
    )
    payloads.extend((transaction.ranges[4], transaction.ranges[7]))
    header = b"\x06\x00\x00\x00\x01\x00" + struct.pack("<HI", 0x101B, transaction.payload_length)
    return header + b"".join(native_payload(payload) for payload in payloads)


class P18041HExperimentTests(unittest.TestCase):
    def test_fixture_identity_and_source_are_exact(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / FIXTURE_FILENAME
            source.write_bytes(FIXTURE_BYTES)
            report = validate_fixture_source(source)
            self.assertEqual(report["device_path"], FIXTURE_PATH)
            self.assertEqual(report["observed_length"], 29)
            self.assertEqual(report["observed_sha256"], FIXTURE_SHA256)
            source.write_bytes(b"changed")
            with self.assertRaises(P18041HError):
                validate_fixture_source(source)

    def test_session_is_offline_and_non_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            session = create_session(Path(temporary) / "session")
            manifest = json.loads((session / "session-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["experiment_id"], "P18-041H")
            self.assertEqual(manifest["state"], "blocked_offline_fixture_and_stable_identity_required")
            self.assertFalse(manifest["usb_operation_performed"])
            self.assertEqual(manifest["safety_counters"]["hardware_writes"], 0)
            with self.assertRaises(P18041HError):
                create_session(session)

    def test_checked_in_manifest_matches_the_host_contract(self):
        manifest_path = Path(__file__).resolve().parents[1] / "analysis" / "phase-18-p18-041h-experiment-manifest-20261004.json"
        self.assertEqual(
            json.loads(manifest_path.read_text(encoding="utf-8")),
            experiment_manifest(),
        )
        recovery_path = Path(__file__).resolve().parents[1] / "analysis" / "phase-18-p18-041h-recovery-plan-20261004.json"
        self.assertEqual(
            json.loads(recovery_path.read_text(encoding="utf-8")),
            recovery_plan_contract(),
        )

    def test_four_time_observations_and_separate_map_are_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / FIXTURE_FILENAME
            source.write_bytes(FIXTURE_BYTES)
            paths = {}
            for event in EVENTS:
                path = root / f"{event}.json"
                record_time_observation(path, event, fixture_source=source)
                paths[event] = path
            event_map = write_event_mapping(root / "event-map.json", paths)
            report = json.loads(event_map.read_text(encoding="utf-8"))
            self.assertTrue(report["raw_observations_are_separate"])
            self.assertEqual(set(report["events"]), set(EVENTS))

    def test_owner_identity_requires_pre_execution_candidate_and_binds_phrase(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture_source = root / FIXTURE_FILENAME
            fixture_source.write_bytes(FIXTURE_BYTES)
            before_blob = _fixture_blob()
            before = root / "before"
            _write_complete_backup(before, before_blob)
            capture_plan = root / "capture-plan.json"
            write_json(capture_plan, experiment_manifest())
            recovery_plan = root / "recovery-plan.json"
            write_json(recovery_plan, recovery_plan_contract())
            prestage_dir = root / "01-fixture-prestage"
            prestage_dir.mkdir()
            prestage_report = _write_prestage_report(prestage_dir / "placement-readback-or-backup-report.json")
            boundary = root / "device-boundary.json"
            stable_identity = root / "stable-device-identity.json"
            write_json(
                stable_identity,
                {
                    "format": "infocarry-p18-041h-stable-device-identity-v1",
                    "status": "read_only_observed",
                    "model": "VNW-V15",
                    "vendor_id": "0x054c",
                    "product_id": "0x001e",
                    "stable_unit_identity": "unit-serial-01",
                    "source": "native Manager read-only device identity page",
                    "observed_at_utc": "2026-10-04T07:00:00+00:00",
                },
            )
            write_json(
                boundary,
                {
                    "format": "infocarry-p18-041h-device-boundary-v1",
                    "model": "VNW-V15",
                    "vendor_id": "0x054c",
                    "product_id": "0x001e",
                    "observation_mode": "read_only",
                    "identity_source": "native Manager read-only device identity page",
                    "stable_identity_artifact": {
                        "path": str(stable_identity),
                        "sha256": hashlib.sha256(stable_identity.read_bytes()).hexdigest(),
                    },
                },
            )
            before_parsed = parse_backup_blob(before_blob)
            target = next(record for record in before_parsed.records if _record_path(before_parsed, record) == FIXTURE_PATH)
            after_blob = delete_existing_file(before_parsed, target.offset)
            native_stage = root / "05-native-delete-capture"
            native_stage.mkdir()
            candidate_artifact, _transaction_report, _terminal = _candidate_and_terminal(native_stage, after_blob)
            candidate_report = json.loads((_transaction_report).read_text(encoding="utf-8"))
            candidate_report["capture_phase"] = "post-execution-evidence"
            post_candidate = root / "post-candidate.json"
            write_json(post_candidate, candidate_report)
            with self.assertRaises(IdentityNotFrozenError):
                build_owner_authorization_identity(
                    pre_delete_backup=before,
                    capture_plan=capture_plan,
                    recovery_plan=recovery_plan,
                    candidate_report=post_candidate,
                    fixture_prestage_report=prestage_report,
                    fixture_source=fixture_source,
                    device_boundary=boundary,
                )
            candidate_report["capture_phase"] = "pre-execution"
            candidate_report["candidate_artifact"]= {
                "directory": str(candidate_artifact),
                "manifest_sha256": hashlib.sha256((candidate_artifact / "manifest.json").read_bytes()).hexdigest(),
                "operation_binding_sha256": hashlib.sha256((candidate_artifact / "operation-binding.json").read_bytes()).hexdigest(),
            }
            candidate_report_path = root / "candidate.json"
            write_json(candidate_report_path, candidate_report)
            identity = build_owner_authorization_identity(
                pre_delete_backup=before,
                capture_plan=capture_plan,
                recovery_plan=recovery_plan,
                candidate_report=candidate_report_path,
                fixture_prestage_report=prestage_report,
                fixture_source=fixture_source,
                device_boundary=boundary,
            )
        self.assertTrue(identity["approval_is_not_granted"])
        self.assertTrue(identity["exact_owner_approval_phrase"].endswith(identity["fingerprint_sha256"]))

    def test_native_capture_report_requires_one_transaction_and_preserves_hashes(self):
        from infocarry.p18_041h_experiment import inspect_native_capture

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capture = root / "delete.usblog"
            capture.write_bytes(_capture_bytes())
            report = inspect_native_capture(
                capture,
                capture_phase="pre-execution",
                operation_binding_metadata=operation_binding(),
            )
            self.assertEqual(report["ordinary_0x101b_transaction_count"], 1)
            self.assertEqual(report["command"], "0x101b")
            self.assertEqual(len(report["range_sha256"]), 8)
            self.assertEqual(report["safety_counters"]["real_0x101b"], 0)
            wrong_binding = operation_binding()
            wrong_binding["target_path"] = r"root\other.txt"
            with self.assertRaises(P18041HError):
                inspect_native_capture(
                    capture,
                    capture_phase="pre-execution",
                    operation_binding_metadata=wrong_binding,
                )
            capture.write_bytes(capture.read_bytes() + capture.read_bytes())
            with self.assertRaises(P18041HError):
                inspect_native_capture(capture, operation_binding_metadata=operation_binding())

    def test_post_delete_verifier_reports_all_surviving_records_and_times(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before_blob = _fixture_blob()
            before_parsed = parse_backup_blob(before_blob)
            target = next(record for record in before_parsed.records if _record_path(before_parsed, record) == FIXTURE_PATH)
            after_blob = delete_existing_file(before_parsed, target.offset)
            before = root / "before"
            after = root / "after"
            _write_complete_backup(before, before_blob)
            _write_complete_backup(after, after_blob)
            paths = {}
            for event in EVENTS:
                path = root / f"{event}.json"
                record_time_observation(path, event)
                paths[event] = path
            event_map = write_event_mapping(root / "event-map.json", paths)
            prestage_dir = root / "01-fixture-prestage"
            prestage_dir.mkdir()
            prestage_report = _write_prestage_report(prestage_dir / "placement-readback-or-backup-report.json")
            native_stage = root / "05-native-delete-capture"
            native_stage.mkdir()
            candidate_artifact, transaction_report, terminal_path = _candidate_and_terminal(native_stage, after_blob)
            report = verify_delete_evidence(
                before,
                after,
                candidate_artifact=candidate_artifact,
                fixture_prestage_report=prestage_report,
                time_event_map=event_map,
                native_transaction_report=transaction_report,
                terminal_result_path=terminal_path,
            )
            self.assertTrue(report["verification"]["offline_evidence_valid"], report)
            self.assertEqual(report["path_delta"]["removed"], [FIXTURE_PATH])
            self.assertEqual(report["path_delta"]["added"], [])
            self.assertEqual(report["timestamp_summary"]["surviving_record_count"], 2)
            self.assertTrue(report["payloads"]["unrelated_payloads_byte_identical"])
            self.assertEqual(report["fixed_state"]["status"], "unchanged")

    def test_post_delete_verifier_does_not_accept_unexplained_fixed_state_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before_blob = _fixture_blob()
            before_parsed = parse_backup_blob(before_blob)
            target = next(record for record in before_parsed.records if _record_path(before_parsed, record) == FIXTURE_PATH)
            after_blob = delete_existing_file(before_parsed, target.offset)
            before = root / "before"
            after = root / "after"
            _write_complete_backup(before, before_blob)
            _write_complete_backup(after, after_blob)
            fixed_path = after / "object-02.bin"
            fixed_path.write_bytes(b"changed" + b"B" * 57)
            manifest_path = after / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["objects"][1]["sha256"] = hashlib.sha256(fixed_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            paths = {}
            for event in EVENTS:
                path = root / f"{event}.json"
                record_time_observation(path, event)
                paths[event] = path
            event_map = write_event_mapping(root / "event-map.json", paths)
            prestage_dir = root / "01-fixture-prestage"
            prestage_dir.mkdir()
            prestage_report = _write_prestage_report(prestage_dir / "placement-readback-or-backup-report.json")
            native_stage = root / "05-native-delete-capture"
            native_stage.mkdir()
            candidate_artifact, transaction_report, terminal_path = _candidate_and_terminal(native_stage, after_blob)
            report = verify_delete_evidence(
                before,
                after,
                candidate_artifact=candidate_artifact,
                fixture_prestage_report=prestage_report,
                time_event_map=event_map,
                native_transaction_report=transaction_report,
                terminal_result_path=terminal_path,
            )
            self.assertFalse(report["verification"]["offline_evidence_valid"])
            self.assertEqual(report["fixed_state"]["status"], "changed_requires_native_demonstration")

    def test_post_delete_verifier_rejects_unexplained_serialized_record_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before_blob = _fixture_blob()
            before_parsed = parse_backup_blob(before_blob)
            target = next(record for record in before_parsed.records if _record_path(before_parsed, record) == FIXTURE_PATH)
            after_blob = delete_existing_file(before_parsed, target.offset)
            after_parsed = parse_backup_blob(after_blob)
            mutated = bytearray(after_blob)
            mutated[after_parsed.records[0].offset + 0x18] ^= 0x01
            mutated[0x1C:0x20] = b"\x00" * 4
            mutated[0x1C:0x20] = calculate_backup_checksum(bytes(mutated)).to_bytes(4, "big")
            before = root / "before"
            after = root / "after"
            _write_complete_backup(before, before_blob)
            _write_complete_backup(after, bytes(mutated))
            paths = {}
            for event in EVENTS:
                path = root / f"{event}.json"
                record_time_observation(path, event)
                paths[event] = path
            event_map = write_event_mapping(root / "event-map.json", paths)
            prestage_dir = root / "01-fixture-prestage"
            prestage_dir.mkdir()
            prestage_report = _write_prestage_report(prestage_dir / "placement-readback-or-backup-report.json")
            native_stage = root / "05-native-delete-capture"
            native_stage.mkdir()
            candidate_artifact, transaction_report, terminal_path = _candidate_and_terminal(native_stage, after_blob)
            with self.assertRaises(P18041HError):
                verify_delete_evidence(
                    before,
                    after,
                    candidate_artifact=candidate_artifact,
                    fixture_prestage_report=prestage_report,
                    time_event_map=event_map,
                    native_transaction_report=transaction_report,
                    terminal_result_path=terminal_path,
                )

    def test_evidence_seal_is_exclusive_and_requires_valid_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            session = create_session(Path(temporary) / "session")
            before_blob = _fixture_blob()
            before_parsed = parse_backup_blob(before_blob)
            target = next(record for record in before_parsed.records if _record_path(before_parsed, record) == FIXTURE_PATH)
            after_blob = delete_existing_file(before_parsed, target.offset)
            _write_complete_backup(session / "02-pre-delete-backup", before_blob)
            _write_complete_backup(session / "07-post-delete-backup", after_blob)
            prestage_report = _write_prestage_report(
                session / "01-fixture-prestage" / "placement-readback-or-backup-report.json"
            )
            write_json(session / "03-manager-before" / "snapshot-manifest.json", {"state": "before"})
            write_json(session / "06-manager-after" / "snapshot-manifest.json", {"state": "after"})
            for event in EVENTS:
                record_time_observation(session / "04-time-observations" / f"{event}.json", event)
            write_event_mapping(
                session / "04-time-observations" / "event-map.json",
                {event: session / "04-time-observations" / f"{event}.json" for event in EVENTS},
            )
            _candidate, _transaction_report, _terminal = _candidate_and_terminal(
                session / "05-native-delete-capture", after_blob
            )
            verification = session / "10-analysis" / "delete-evidence-verification.json"
            computed = verify_delete_evidence(
                session / "02-pre-delete-backup",
                session / "07-post-delete-backup",
                candidate_artifact=session / "05-native-delete-capture" / "candidate",
                fixture_prestage_report=prestage_report,
                time_event_map=session / "04-time-observations" / "event-map.json",
                native_transaction_report=session / "05-native-delete-capture" / "native-transaction-report.json",
                terminal_result_path=session / "05-native-delete-capture" / "native-terminal-result.json",
            )
            write_json(verification, computed)
            destination = session / "08-sealed-evidence" / "evidence-seal.json"
            self.assertEqual(seal_evidence(session, verification_report=verification, destination=destination), destination.resolve())
            self.assertEqual(json.loads(destination.read_text(encoding="utf-8"))["state"], "sealed_before_recovery")
            with self.assertRaises(P18041HError):
                seal_evidence(session, verification_report=verification, destination=destination)


def _record_path(parsed, record):
    parts = parsed.paths.get(record.offset)
    if parts is None:
        return None
    return "\\".join(parts) + (f".{record.extension}" if record.extension else "")


if __name__ == "__main__":
    unittest.main()
