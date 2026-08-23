from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import calculate_backup_checksum
from infocarry.write_artifact import ProspectiveWriteTransaction, build_staging_range
from infocarry.write_gate import (
    DEFAULT_CONFIRMATION_PHRASE,
    TEXT_REPLACEMENT_CONFIRMATION_PHRASE,
    WriteGateError,
    WriteTarget,
    authorize_existing_text_replacement,
    authorize_write_session,
    capture_and_verify_fresh_backup,
    interactive_confirmation,
    verify_fresh_backup,
    verify_post_write_backup,
)


def _make_record(flag, extension, field04, field08, name, field14=0):
    raw = bytearray(64)
    raw[0] = flag
    raw[1:4] = extension.encode("ascii").ljust(3, b"\x00")
    raw[4:8] = field04.to_bytes(4, "big")
    raw[8:12] = field08.to_bytes(4, "big")
    raw[12:16] = (1_787_207_892).to_bytes(4, "big")
    raw[16:20] = (0xFFFFFFFF).to_bytes(4, "big")
    raw[20:24] = field14.to_bytes(4, "big")
    raw[24 : 24 + len(name)] = name.encode("cp932")
    return bytes(raw)


def _make_blob(payload=b"hello\r\n"):
    metadata = (
        _make_record(0xD0, "", 0x40, 0x80, "root")
        + _make_record(0xD0, "", 0x40, 0x80, "..")
        + _make_record(0xE0, "txt", 0, len(payload), "memo", 0x200)
    )
    content_start = 0x40 + len(metadata)
    content = b"\xff" * 32 + payload
    content += b"\x00" * (-(content_start + len(content)) % 4)
    total_length = content_start + len(content) + 4
    header = bytearray(64)
    header[:14] = b"infoCarry 2.00"
    header[14:16] = b"\x01\x00"
    header[16:18] = (64).to_bytes(2, "big")
    header[0x14:0x18] = (0x20).to_bytes(4, "big")
    header[0x18:0x1C] = (total_length - 1).to_bytes(4, "big")
    header[0x28:0x2C] = (0x40).to_bytes(4, "big")
    header[0x2C:0x30] = len(metadata).to_bytes(4, "big")
    header[0x30:0x34] = content_start.to_bytes(4, "big")
    header[0x34:0x38] = len(content).to_bytes(4, "big")
    header[0x38:0x3C] = total_length.to_bytes(4, "big")
    header[0x3C:0x40] = b"\xff" * 4
    blob = bytearray(bytes(header) + metadata + content + b"\xff" * 4)
    blob[0x1C:0x20] = calculate_backup_checksum(blob).to_bytes(4, "big")
    return bytes(blob)


def _transaction():
    range5 = b"m" * 0x40
    range8 = b"model"
    variable_m = len(range5) + len(range8)
    return ProspectiveWriteTransaction(
        ranges=(
            b"a" * 0x100,
            b"b" * 0x40,
            build_staging_range(0, variable_m),
            b"",
            range5,
            b"",
            b"",
            range8,
        ),
        variable_n=0,
        variable_m=variable_m,
    )


def _transaction_for_blob(blob: bytes):
    return ProspectiveWriteTransaction(
        ranges=(
            b"a" * 0x100,
            b"b" * 0x40,
            build_staging_range(0, len(blob)),
            b"",
            blob[:0x40],
            b"",
            b"",
            blob[0x40:],
        ),
        variable_n=0,
        variable_m=len(blob),
    )


def _write_archive(
    root: Path,
    blob: bytes,
    timestamp: datetime,
    *,
    fixed_ranges=None,
):
    objects = []
    if fixed_ranges is not None:
        range1, range2 = fixed_ranges
        for sequence, (command, data) in enumerate(
            zip((0x001B, 0x001C, 0x001D, 0x001E), (range1[:0x40], range1[0x40:0x80], range1[0x80:0xC0], range1[0xC0:]))
        ):
            filename = f"object-{sequence + 1:02d}-command-{command:04x}.bin"
            (root / filename).write_bytes(data)
            objects.append((sequence + 1, command, f"response-{command:04x}", filename, data))
        filename = "object-05-command-001f.bin"
        (root / filename).write_bytes(range2)
        objects.append((5, 0x001F, "response-001f", filename, range2))
    sequence = len(objects) + 1
    filename = f"object-{sequence:02d}-command-8004.bin"
    object_path = root / filename
    object_path.write_bytes(blob)
    objects.append((sequence, 0x8004, "backup-blob", filename, blob))
    manifest = {
        "format": "infocarry-raw-backup-v1",
        "state": "complete",
        "created_at_utc": timestamp.isoformat(),
        "updated_at_utc": timestamp.isoformat(),
        "device": {"vendor_id": "0x054c", "product_id": "0x001e"},
        "objects": [
            {
                "sequence": sequence,
                "command": f"0x{command:04x}",
                "kind": kind,
                "filename": name,
                "requested_length": len(data),
                "received_length": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            for sequence, command, kind, name, data in objects
        ],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class WriteGateTests(unittest.TestCase):
    def test_capture_and_verify_fresh_backup_uses_one_injected_capture(self):
        now = datetime(2026, 8, 21, tzinfo=timezone.utc)
        calls = []

        def fake_capture(destination):
            calls.append(destination)
            destination.mkdir()
            _write_archive(destination, _make_blob(), now)

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "fresh"
            verified = capture_and_verify_fresh_backup(
                destination, fake_capture, now=now
            )
            self.assertEqual(calls, [destination.resolve()])
            self.assertEqual(verified.directory, destination.resolve())
            self.assertEqual(verified.object_count, 1)

    def test_fresh_backup_verification_uses_post_capture_clock_when_now_is_none(self):
        invocation_started = datetime.now(timezone.utc) - timedelta(seconds=2)
        capture_times = []

        def fake_capture(destination):
            destination.mkdir()
            captured_at = datetime.now(timezone.utc)
            capture_times.append(captured_at)
            _write_archive(destination, _make_blob(), captured_at)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stale_reference = root / "stale-reference"
            with self.assertRaisesRegex(WriteGateError, "timestamp is in the future"):
                capture_and_verify_fresh_backup(
                    stale_reference,
                    fake_capture,
                    now=invocation_started,
                    max_age_seconds=30,
                )
            self.assertTrue((stale_reference / "manifest.json").is_file())

            accepted = capture_and_verify_fresh_backup(
                root / "post-capture-reference",
                fake_capture,
                now=None,
                max_age_seconds=30,
            )

            self.assertGreater(capture_times[0], invocation_started)
            self.assertGreaterEqual(
                datetime.fromisoformat(accepted.verified_at_utc), capture_times[1]
            )
            self.assertEqual(accepted.object_count, 1)

    def test_genuinely_future_dated_manifest_is_still_rejected(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_archive(root, _make_blob(), future)
            with self.assertRaisesRegex(WriteGateError, "timestamp is in the future"):
                verify_fresh_backup(root, now=datetime.now(timezone.utc), max_age_seconds=None)

    def test_capture_and_verify_rejects_existing_path_and_never_retries(self):
        with tempfile.TemporaryDirectory() as temporary:
            existing = Path(temporary) / "existing"
            existing.mkdir()
            calls = []

            def should_not_run(destination):
                calls.append(destination)

            with self.assertRaisesRegex(WriteGateError, "existing backup path"):
                capture_and_verify_fresh_backup(existing, should_not_run)
            self.assertEqual(calls, [])

            failed = Path(temporary) / "failed"

            def fail_once(destination):
                calls.append(destination)
                destination.mkdir()
                raise RuntimeError("simulated capture disconnect")

            with self.assertRaisesRegex(WriteGateError, "preserve any partial archive"):
                capture_and_verify_fresh_backup(failed, fail_once)
            self.assertEqual(calls, [failed.resolve()])
            self.assertTrue(failed.is_dir())

    def test_verifies_complete_fresh_backup_and_all_object_hashes(self):
        now = datetime(2026, 8, 21, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_archive(root, _make_blob(), now)
            verified = verify_fresh_backup(root, now=now)
            self.assertEqual(verified.object_count, 1)
            self.assertEqual(verified.blob_sha256, hashlib.sha256(_make_blob()).hexdigest())

    def test_authorization_binds_device_backup_target_and_candidate_hashes(self):
        now = datetime(2026, 8, 21, tzinfo=timezone.utc)
        before_blob = _make_blob(b"before\r\n")
        candidate_blob = _make_blob(b"candidate\r\n")
        transaction = _transaction_for_blob(candidate_blob)
        target = WriteTarget(
            record_offset=0xC0,
            path="root\\memo.txt",
            candidate_payload_sha256=hashlib.sha256(b"candidate\r\n").hexdigest(),
            before_payload_sha256=hashlib.sha256(b"before\r\n").hexdigest(),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_archive(root, before_blob, now, fixed_ranges=transaction.ranges[:2])
            authorization = authorize_write_session(
                root,
                transaction,
                cli_write_flag=True,
                confirmation=DEFAULT_CONFIRMATION_PHRASE,
                target=target,
                now=now,
            )
            self.assertEqual(authorization.backup.device_identity, ("0x054c", "0x001e"))
            self.assertEqual(authorization.target, target)
            encoded = authorization.to_dict()
            self.assertEqual(encoded["backup"]["device"]["vendor_id"], "0x054c")
            self.assertEqual(encoded["target"]["record_offset_hex"], "0x000000c0")
            self.assertEqual(
                encoded["target"]["candidate_payload_sha256"],
                target.candidate_payload_sha256,
            )
            authorization.revalidate(transaction, now=now)

            with self.assertRaisesRegex(WriteGateError, "transaction bytes differ"):
                authorization.revalidate(
                    _transaction_for_blob(_make_blob(b"other\r\n")), now=now
                )
            bad_target = WriteTarget(
                record_offset=target.record_offset,
                path="root\\wrong.txt",
                candidate_payload_sha256=target.candidate_payload_sha256,
                before_payload_sha256=target.before_payload_sha256,
            )
            with self.assertRaisesRegex(WriteGateError, "candidate transaction target path"):
                authorize_write_session(
                    root,
                    transaction,
                    cli_write_flag=True,
                    confirmation=DEFAULT_CONFIRMATION_PHRASE,
                    target=bad_target,
                    now=now,
                )

    def test_target_scope_can_only_be_created_from_a_no_device_preview(self):
        report = {
            "workflow": {
                "target_record_offset": "0x000000c0",
                "target_path": "root\\memo.txt",
                "device_accessed": False,
            },
            "target": {
                "after_payload_sha256": "a" * 64,
                "before_payload_sha256": "b" * 64,
            },
            "safety": {"candidate_bytes_included": False},
        }
        target = WriteTarget.from_preview_report(report)
        self.assertEqual(target.record_offset, 0xC0)
        self.assertEqual(target.path, "root\\memo.txt")
        with self.assertRaisesRegex(WriteGateError, "no-candidate audit"):
            WriteTarget.from_preview_report(
                {**report, "safety": {"candidate_bytes_included": True}}
            )

    def test_existing_text_authorization_requires_operation_specific_phrase(self):
        now = datetime(2026, 8, 21, tzinfo=timezone.utc)
        before_blob = _make_blob(b"before\r\n")
        candidate_blob = _make_blob(b"candidate\r\n")
        transaction = _transaction_for_blob(candidate_blob)
        preview = {
            "workflow": {
                "device_accessed": False,
                "source_backup_blob_sha256": hashlib.sha256(before_blob).hexdigest(),
                "target_record_offset": "0x000000c0",
                "target_path": "root\\memo.txt",
            },
            "target": {
                "before_payload_sha256": hashlib.sha256(b"before\r\n").hexdigest(),
                "after_payload_sha256": hashlib.sha256(b"candidate\r\n").hexdigest(),
            },
            "candidate": {
                "decoded_sha256": hashlib.sha256(candidate_blob).hexdigest(),
            },
            "safety": {"candidate_bytes_included": False},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_archive(root, before_blob, now, fixed_ranges=transaction.ranges[:2])
            authorization = authorize_existing_text_replacement(
                root,
                transaction,
                preview,
                cli_write_flag=True,
                confirmation=TEXT_REPLACEMENT_CONFIRMATION_PHRASE,
                now=now,
            )
            self.assertEqual(
                authorization.confirmation_phrase,
                TEXT_REPLACEMENT_CONFIRMATION_PHRASE,
            )
            self.assertFalse(authorization.to_dict()["usb_transmission_performed"])
            with self.assertRaisesRegex(WriteGateError, "confirmation phrase"):
                authorize_existing_text_replacement(
                    root,
                    transaction,
                    preview,
                    cli_write_flag=True,
                    confirmation=DEFAULT_CONFIRMATION_PHRASE,
                    now=now,
                )

            prompt = []
            self.assertTrue(
                interactive_confirmation(
                    phrase=TEXT_REPLACEMENT_CONFIRMATION_PHRASE,
                    input_fn=lambda value: (
                        prompt.append(value) or TEXT_REPLACEMENT_CONFIRMATION_PHRASE
                    ),
                    output_fn=lambda value: prompt.append(value),
                )
            )
            self.assertIn(TEXT_REPLACEMENT_CONFIRMATION_PHRASE, prompt[0])

    def test_existing_text_authorization_rejects_candidate_hash_not_in_preview(self):
        now = datetime(2026, 8, 21, tzinfo=timezone.utc)
        before_blob = _make_blob(b"before\r\n")
        candidate_blob = _make_blob(b"candidate\r\n")
        transaction = _transaction_for_blob(candidate_blob)
        preview = {
            "workflow": {
                "device_accessed": False,
                "source_backup_blob_sha256": hashlib.sha256(before_blob).hexdigest(),
                "target_record_offset": "0x000000c0",
                "target_path": "root\\memo.txt",
            },
            "target": {
                "before_payload_sha256": hashlib.sha256(b"before\r\n").hexdigest(),
                "after_payload_sha256": hashlib.sha256(b"candidate\r\n").hexdigest(),
            },
            "candidate": {"decoded_sha256": "f" * 64},
            "safety": {"candidate_bytes_included": False},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_archive(root, before_blob, now, fixed_ranges=transaction.ranges[:2])
            with self.assertRaisesRegex(WriteGateError, "candidate transaction blob"):
                authorize_existing_text_replacement(
                    root,
                    transaction,
                    preview,
                    cli_write_flag=True,
                    confirmation=TEXT_REPLACEMENT_CONFIRMATION_PHRASE,
                    now=now,
                )

    def test_requires_explicit_flag_and_exact_confirmation(self):
        now = datetime(2026, 8, 21, tzinfo=timezone.utc)
        transaction = _transaction()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_archive(root, _make_blob(), now, fixed_ranges=transaction.ranges[:2])
            with self.assertRaises(WriteGateError):
                authorize_write_session(
                    root,
                    transaction,
                    cli_write_flag=False,
                    confirmation=DEFAULT_CONFIRMATION_PHRASE,
                    now=now,
                )
            with self.assertRaises(WriteGateError):
                authorize_write_session(
                    root,
                    transaction,
                    cli_write_flag=True,
                    confirmation="yes",
                    now=now,
                )
            authorization = authorize_write_session(
                root,
                transaction,
                cli_write_flag=True,
                confirmation=DEFAULT_CONFIRMATION_PHRASE,
                now=now,
            )
            self.assertFalse(authorization.to_dict()["usb_transmission_performed"])
            authorization.revalidate(transaction, now=now)

    def test_freshness_and_post_authorization_change_are_rejected(self):
        now = datetime(2026, 8, 21, tzinfo=timezone.utc)
        transaction = _transaction()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_archive(root, _make_blob(), now - timedelta(seconds=10))
            with self.assertRaises(WriteGateError):
                verify_fresh_backup(root, now=now, max_age_seconds=5)
            _write_archive(root, _make_blob(), now, fixed_ranges=transaction.ranges[:2])
            authorization = authorize_write_session(
                root,
                transaction,
                cli_write_flag=True,
                confirmation=DEFAULT_CONFIRMATION_PHRASE,
                now=now,
            )
            blob_path = root / "object-06-command-8004.bin"
            blob_path.write_bytes(blob_path.read_bytes() + b"x")
            with self.assertRaises(WriteGateError):
                authorization.revalidate(transaction, now=now)

    def test_authorization_rejects_fixed_state_mismatch(self):
        now = datetime(2026, 8, 21, tzinfo=timezone.utc)
        transaction = _transaction()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wrong_state = bytes([0xFF]) * 0x100
            _write_archive(root, _make_blob(), now, fixed_ranges=(wrong_state, transaction.ranges[1]))
            with self.assertRaises(WriteGateError):
                authorize_write_session(
                    root,
                    transaction,
                    cli_write_flag=True,
                    confirmation=DEFAULT_CONFIRMATION_PHRASE,
                    now=now,
                )

    def test_post_write_verification_matches_fixed_state_and_blob(self):
        now = datetime(2026, 8, 21, tzinfo=timezone.utc)
        blob = _make_blob()
        transaction = _transaction_for_blob(blob)
        with tempfile.TemporaryDirectory() as temporary:
            before_root = Path(temporary) / "before"
            after_root = Path(temporary) / "after"
            before_root.mkdir()
            after_root.mkdir()
            _write_archive(before_root, blob, now, fixed_ranges=transaction.ranges[:2])
            _write_archive(after_root, blob, now, fixed_ranges=transaction.ranges[:2])
            before = verify_fresh_backup(before_root, now=now)
            verification = verify_post_write_backup(
                before, after_root, transaction, now=now
            )
            self.assertTrue(verification.fixed_state_matches)
            self.assertTrue(verification.dynamic_blob_matches)
            self.assertTrue(verification.unrelated_objects_unchanged)

    def test_interactive_confirmation_requires_exact_phrase(self):
        prompts = []
        self.assertTrue(
            interactive_confirmation(
                input_fn=lambda prompt: (prompts.append(prompt) or DEFAULT_CONFIRMATION_PHRASE),
                output_fn=lambda message: prompts.append(message),
            )
        )
        self.assertFalse(
            interactive_confirmation(
                input_fn=lambda prompt: "write infocarry",
                output_fn=lambda message: None,
            )
        )
        self.assertEqual(prompts[0], "This is a device-changing operation. Type 'WRITE INFOCARRY' to continue:")


if __name__ == "__main__":
    unittest.main()
