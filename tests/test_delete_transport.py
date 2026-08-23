from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import tempfile
import time
import unittest

from infocarry.backup_format import calculate_backup_checksum, parse_backup_blob
from infocarry.backup_repack import repack_existing_records, delete_existing_file
from infocarry.delete_gate import (
    DELETE_ONE_CONFIRMATION_PHRASE,
    DeleteGateError,
    authorize_delete,
    bind_delete_sender,
    build_delete_candidate,
    verify_post_delete_backup,
)
from infocarry.protocol import (
    DeviceStatusError,
    TransferCancelledError,
    TransferTimeoutError,
)
from infocarry.write_protocol import (
    AuthorizedWriteSender,
    REQUEST_COMPLETION,
    REQUEST_TRANSFER_STATE,
    WritePolicy,
    WriteProtocolError,
    WriteTransferLengthError,
    assess_write_failure,
)

try:
    from test_backup_format import make_record
    from test_new_txt import _make_root_blob, _write_archive
except ModuleNotFoundError:
    from tests.test_backup_format import make_record
    from tests.test_new_txt import _make_root_blob, _write_archive


def _make_two_root_blob(source=b"source\r\n", other=b"other\r\n"):
    """Make a compact root fixture with two unrelated TXT leaves."""

    records = b"".join(
        (
            make_record(0xD0, "", 0x40, 0xC0, "root"),
            make_record(0xD0, "", 0x00, 0x40, ".."),
            make_record(0xE0, "txt", 0x00, len(source), "source", 0x200),
            make_record(
                0xE0,
                "txt",
                (0x20 + len(source) + 3) & ~3,
                len(other),
                "other",
                0x200,
            ),
        )
    )
    content = b"\xff" * 0x20 + source
    content += b"\xff" * (-(0x20 + len(source)) % 4)
    content += b"\xff" * 0x20 + other
    content += b"\x00" * (-(0x140 + len(content)) % 4)
    content_start = 0x40 + len(records)
    total_length = content_start + len(content) + 4
    header = bytearray(64)
    header[:14] = b"infoCarry 2.00"
    header[14:16] = b"\x01\x00"
    header[16:18] = (64).to_bytes(2, "big")
    header[0x14:0x18] = (0x20).to_bytes(4, "big")
    header[0x18:0x1C] = (total_length - 1).to_bytes(4, "big")
    header[0x28:0x2C] = (0x40).to_bytes(4, "big")
    header[0x2C:0x30] = len(records).to_bytes(4, "big")
    header[0x30:0x34] = content_start.to_bytes(4, "big")
    header[0x34:0x38] = len(content).to_bytes(4, "big")
    header[0x38:0x3C] = total_length.to_bytes(4, "big")
    header[0x3C:0x40] = b"\xff" * 4
    blob = bytearray(bytes(header) + records + content + b"\xff" * 4)
    blob[0x1C:0x20] = calculate_backup_checksum(blob).to_bytes(4, "big")
    return bytes(blob)


class DeleteScenarioBackend:
    def __init__(
        self,
        *,
        completion=(0,),
        completion_bytes=None,
        state_default=0,
        fail_control_out=False,
        fail_bulk_at=None,
        bulk_error=None,
        partial=False,
    ):
        self.calls = []
        self.completion = list(completion)
        self.completion_bytes = completion_bytes
        self.state_default = state_default
        self.fail_control_out = fail_control_out
        self.fail_bulk_at = fail_bulk_at
        self.bulk_error = bulk_error or OSError("simulated fake disconnect")
        self.partial = partial

    def control_out(self, request_type, request, value, index, data, timeout_ms):
        self.calls.append(("control_out", request, bytes(data)))
        if self.fail_control_out:
            raise OSError("simulated header disconnect")
        return len(data)

    def control_in(self, request_type, request, value, index, length, timeout_ms):
        self.calls.append(("control_in", request))
        if request == REQUEST_TRANSFER_STATE:
            return self.state_default.to_bytes(2, "little")
        if request == REQUEST_COMPLETION:
            if self.completion_bytes is not None:
                return self.completion_bytes
            value = self.completion.pop(0) if self.completion else 0
            return value.to_bytes(2, "little")
        raise AssertionError(request)

    def bulk_write(self, endpoint, data, timeout_ms):
        self.calls.append(("bulk_write", bytes(data)))
        count = sum(call[0] == "bulk_write" for call in self.calls)
        if self.fail_bulk_at is not None and count == self.fail_bulk_at:
            raise self.bulk_error
        if self.partial:
            return max(1, len(data) // 2)
        return len(data)


class DeleteTransportIntegrationTests(unittest.TestCase):
    def _candidate(self, *, two_files=False):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        now = datetime(2026, 8, 22, tzinfo=timezone.utc)
        blob = _make_two_root_blob() if two_files else _make_root_blob(b"source\r\n")
        backup = _write_archive(root / "before", blob, now)
        parsed = parse_backup_blob((backup / "object-08.bin").read_bytes())
        timestamps = {
            record.offset: 0x65000000 + index
            for index, record in enumerate(parsed.records)
            if record.offset != 0xC0
        }
        candidate = build_delete_candidate(
            backup,
            "root\\source.txt",
            0xC0,
            timestamps,
            now=now,
            max_age_seconds=None,
        )
        authorization = authorize_delete(
            candidate,
            confirmation=DELETE_ONE_CONFIRMATION_PHRASE,
        )
        sender_binding = bind_delete_sender(
            authorization,
            candidate,
            now=now,
            max_age_seconds=None,
        )
        return temporary, root, backup, parsed, candidate, authorization, sender_binding, now

    @staticmethod
    def _calls(backend, name):
        return [call for call in backend.calls if call[0] == name]

    @staticmethod
    def _send(backend, sender_binding, candidate, **kwargs):
        return AuthorizedWriteSender(
            backend,
            0x01,
            policy=kwargs.pop("policy", WritePolicy()),
            clock=kwargs.pop("clock", time.monotonic),
            sleep=kwargs.pop("sleep", time.sleep),
        ).send(candidate.transaction, sender_binding, **kwargs)

    @staticmethod
    def _post(root, candidate, now, *, blob=None, name="after"):
        fixed_state = {
            0x001B: candidate.transaction.ranges[0][0x00:0x40],
            0x001C: candidate.transaction.ranges[0][0x40:0x80],
            0x001D: b"\x00" * 64,
            0x001E: candidate.transaction.ranges[0][0xC0:0x100],
            0x001F: candidate.transaction.ranges[1],
        }
        return _write_archive(
            root / name,
            candidate.candidate_blob if blob is None else blob,
            now,
            fixed_state=fixed_state,
        )

    @staticmethod
    def _candidate_for_readback_blob(candidate, blob):
        audit = dict(candidate.audit)
        candidate_audit = dict(audit["candidate"])
        candidate_audit["blob_sha256"] = hashlib.sha256(blob).hexdigest()
        audit["candidate"] = candidate_audit
        return replace(candidate, audit=audit)

    def test_partial_transfer_completes_and_readback_is_verified(self):
        temporary, root, _backup, _parsed, candidate, _authorization, binding, now = self._candidate()
        self.addCleanup(temporary.cleanup)
        backend = DeleteScenarioBackend(partial=True)
        self.assertEqual(
            self._send(
                backend,
                binding,
                candidate,
                policy=WritePolicy(max_bulk_chunk=0x40),
            ),
            0,
        )
        verification = verify_post_delete_backup(
            candidate,
            self._post(root, candidate, now),
            completion=0,
            now=now,
            max_age_seconds=None,
        )
        self.assertTrue(verification.dynamic_blob_matches)
        self.assertGreater(len(self._calls(backend, "bulk_write")), 5)
        self.assertEqual(len(self._calls(backend, "control_out")), 1)

    def test_disconnect_at_header_is_safe_and_disconnect_after_start_is_indeterminate(self):
        temporary, _root, _backup, _parsed, candidate, _authorization, binding, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        before = DeleteScenarioBackend(fail_control_out=True)
        with self.assertRaises(OSError) as raised:
            self._send(before, binding, candidate)
        self.assertFalse(assess_write_failure(raised.exception).write_started)
        self.assertEqual(len(self._calls(before, "control_out")), 1)
        after = DeleteScenarioBackend(fail_bulk_at=2)
        with self.assertRaises(WriteProtocolError) as raised:
            self._send(after, binding, candidate)
        assessment = assess_write_failure(raised.exception)
        self.assertTrue(assessment.write_started)
        self.assertEqual(assessment.device_outcome, "indeterminate")
        self.assertFalse(assessment.automatic_retry_allowed)
        self.assertEqual(len(self._calls(after, "control_out")), 1)
        self.assertEqual(len(self._calls(after, "bulk_write")), 2)

    def test_timeout_before_and_during_payload_is_terminal_without_retry(self):
        temporary, _root, _backup, _parsed, candidate, _authorization, binding, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        clock = [0.0]
        busy = DeleteScenarioBackend(state_default=3)
        with self.assertRaises(TransferTimeoutError) as raised:
            self._send(
                busy,
                binding,
                candidate,
                policy=WritePolicy(busy_timeout_seconds=0.25, busy_poll_interval_seconds=0.1),
                clock=lambda: clock[0],
                sleep=lambda value: clock.__setitem__(0, clock[0] + value),
            )
        self.assertTrue(assess_write_failure(raised.exception).write_started)
        self.assertEqual(len(self._calls(busy, "bulk_write")), 0)
        during = DeleteScenarioBackend(
            fail_bulk_at=2,
            bulk_error=TransferTimeoutError("simulated payload timeout"),
        )
        with self.assertRaises(TransferTimeoutError) as raised:
            self._send(during, binding, candidate)
        assessment = assess_write_failure(raised.exception)
        self.assertTrue(assessment.write_started)
        self.assertEqual(assessment.device_outcome, "indeterminate")
        self.assertEqual(len(self._calls(during, "bulk_write")), 2)
        self.assertEqual(len(self._calls(during, "control_out")), 1)

    def test_cancellation_before_header_is_safe_and_after_start_is_indeterminate(self):
        temporary, _root, _backup, _parsed, candidate, _authorization, binding, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        before = DeleteScenarioBackend()
        with self.assertRaises(TransferCancelledError) as raised:
            self._send(before, binding, candidate, cancelled=lambda: True)
        self.assertFalse(assess_write_failure(raised.exception).write_started)
        self.assertEqual(before.calls, [])
        after = DeleteScenarioBackend()
        checks = iter((False, False, False, True))
        with self.assertRaises(TransferCancelledError) as raised:
            self._send(after, binding, candidate, cancelled=lambda: next(checks, True))
        assessment = assess_write_failure(raised.exception)
        self.assertTrue(assessment.write_started)
        self.assertEqual(assessment.device_outcome, "indeterminate")
        self.assertFalse(assessment.automatic_retry_allowed)
        self.assertEqual(len(self._calls(after, "control_out")), 1)
        self.assertEqual(len(self._calls(after, "bulk_write")), 1)

    def test_nonzero_and_malformed_completion_are_terminal_without_retry(self):
        temporary, _root, _backup, _parsed, candidate, _authorization, binding, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        nonzero = DeleteScenarioBackend(completion=(1, 0))
        with self.assertRaises(DeviceStatusError) as raised:
            self._send(nonzero, binding, candidate)
        self.assertEqual(assess_write_failure(raised.exception).device_outcome, "completed_with_error")
        self.assertEqual(len(self._calls(nonzero, "control_out")), 1)
        self.assertEqual(len(self._calls(nonzero, "bulk_write")), 5)
        for malformed in (b"", b"\x00", b"\x00\x00\x01\x00"):
            with self.subTest(malformed=malformed):
                backend = DeleteScenarioBackend(completion_bytes=malformed)
                with self.assertRaises(WriteTransferLengthError):
                    self._send(backend, binding, candidate)
                self.assertEqual(len(self._calls(backend, "control_out")), 1)
                self.assertEqual(len(self._calls(backend, "bulk_write")), 5)

    def test_authorization_binds_every_delete_identity_and_hash(self):
        temporary, _root, _backup, _parsed, candidate, authorization, _binding, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        mutations = (
            ("device", {"device_identity": ("0x054c", "0x001f")}),
            ("manifest", {"baseline_manifest_sha256": "1" * 64}),
            ("blob", {"baseline_blob_sha256": "2" * 64}),
            ("path", {"target_path": "root\\other.txt"}),
            ("offset", {"target_record_offset": 0x100}),
            ("payload", {"target_payload_sha256": "3" * 64}),
            ("candidate", {"candidate_blob_sha256": "4" * 64}),
            ("transaction", {"candidate_transaction_sha256": "5" * 64}),
        )
        for label, changes in mutations:
            with self.subTest(label=label):
                try:
                    altered = replace(authorization, **changes)
                except DeleteGateError:
                    continue
                with self.assertRaises(DeleteGateError):
                    altered.require_same_candidate(candidate)

    def test_malformed_or_mismatched_readback_is_terminal_and_not_retried(self):
        temporary, root, backup, _parsed, candidate, _authorization, binding, now = self._candidate()
        self.addCleanup(temporary.cleanup)
        backend = DeleteScenarioBackend()
        self.assertEqual(self._send(backend, binding, candidate), 0)
        malformed = _write_archive(
            root / "malformed",
            candidate.candidate_blob[:-1],
            now,
        )
        with self.assertRaisesRegex(DeleteGateError, "indeterminate"):
            verify_post_delete_backup(
                candidate, malformed, completion=0, now=now, max_age_seconds=None
            )
        mismatch = _write_archive(root / "mismatch", _make_root_blob(), now)
        with self.assertRaisesRegex(DeleteGateError, "does not match"):
            verify_post_delete_backup(
                candidate, mismatch, completion=0, now=now, max_age_seconds=None
            )
        self.assertEqual(len(self._calls(backend, "control_out")), 1)
        self.assertEqual(backup.name, "before")

    def test_target_still_present_extra_delete_and_unrelated_payload_change_fail(self):
        temporary, root, _backup, parsed, candidate, _authorization, binding, now = self._candidate(two_files=True)
        self.addCleanup(temporary.cleanup)
        backend = DeleteScenarioBackend()
        self.assertEqual(self._send(backend, binding, candidate), 0)
        target_blob = _make_two_root_blob()
        target_candidate = self._candidate_for_readback_blob(candidate, target_blob)
        target_still_present = self._post(root, candidate, now, blob=target_blob, name="target-present")
        with self.assertRaisesRegex(DeleteGateError, "path delta"):
            verify_post_delete_backup(
                target_candidate, target_still_present, completion=0, now=now, max_age_seconds=None
            )
        candidate_parsed = parse_backup_blob(candidate.candidate_blob)
        other_offset = next(
            record.offset for record in candidate_parsed.records if record.name == "other"
        )
        extra_deleted = delete_existing_file(candidate_parsed, other_offset)
        extra_candidate = self._candidate_for_readback_blob(candidate, extra_deleted)
        with self.assertRaisesRegex(DeleteGateError, "path delta"):
            verify_post_delete_backup(
                extra_candidate,
                self._post(root, candidate, now, blob=extra_deleted, name="extra-deleted"),
                completion=0,
                now=now,
                max_age_seconds=None,
            )
        changed = repack_existing_records(candidate_parsed, {other_offset: b"changed"})
        changed_candidate = self._candidate_for_readback_blob(candidate, changed)
        with self.assertRaisesRegex(DeleteGateError, "unrelated payload"):
            verify_post_delete_backup(
                changed_candidate,
                self._post(root, candidate, now, blob=changed, name="changed-payload"),
                completion=0,
                now=now,
                max_age_seconds=None,
            )
        self.assertEqual(len(self._calls(backend, "control_out")), 1)
        self.assertEqual(parsed.paths[0xC0], ("root", "source"))

    def test_missing_post_backup_and_nonzero_completion_are_terminal_without_resend(self):
        temporary, root, _backup, _parsed, candidate, _authorization, binding, now = self._candidate()
        self.addCleanup(temporary.cleanup)
        backend = DeleteScenarioBackend()
        self.assertEqual(self._send(backend, binding, candidate), 0)
        with self.assertRaisesRegex(DeleteGateError, "indeterminate"):
            verify_post_delete_backup(
                candidate,
                root / "missing-post",
                completion=0,
                now=now,
                max_age_seconds=None,
            )
        self.assertEqual(len(self._calls(backend, "control_out")), 1)


if __name__ == "__main__":
    unittest.main()
