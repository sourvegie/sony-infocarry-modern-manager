from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from infocarry.new_txt import build_new_root_txt_add
from infocarry.new_txt_gate import (
    NEW_ROOT_TXT_CONFIRMATION_PHRASE,
    NewTxtGateError,
    authorize_new_txt_add,
)
from infocarry.write_protocol import (
    AuthorizedWriteSender,
    REQUEST_COMPLETION,
    REQUEST_TRANSFER_STATE,
)

try:
    from test_new_txt import _make_root_blob, _write_archive
except ModuleNotFoundError:
    from tests.test_new_txt import _make_root_blob, _write_archive


class NewTxtGateTests(unittest.TestCase):
    def _candidate(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        backup = _write_archive(root / "backup", _make_root_blob(), now)
        source = root / "source.txt"
        source.write_bytes(b"new\r\n")
        result = build_new_root_txt_add(
            backup, source, "new.txt", source_template_offset=0xC0,
            available_capacity_bytes=10000, now=now, max_age_seconds=None,
        )
        return temporary, backup, source, result, now

    def test_binds_identity_hashes_path_and_candidate_after_phrase(self):
        temporary, backup, source, result, now = self._candidate()
        self.addCleanup(temporary.cleanup)
        authorization = authorize_new_txt_add(
            result, confirmation=NEW_ROOT_TXT_CONFIRMATION_PHRASE
        )
        encoded = authorization.to_dict()
        self.assertEqual(encoded["operation"], "add_one_root_txt")
        self.assertFalse(encoded["usb_transmission_performed"])
        self.assertEqual(encoded["target_path"], "root\\new.txt")
        authorization.revalidate(result, backup, source, now=now, max_age_seconds=None)

    def test_requires_operation_specific_phrase(self):
        temporary, _backup, _source, result, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(NewTxtGateError, "phrase"):
            authorize_new_txt_add(result, confirmation="WRITE INFOCARRY")

    def test_rejects_changed_source_and_candidate(self):
        temporary, backup, source, result, now = self._candidate()
        self.addCleanup(temporary.cleanup)
        authorization = authorize_new_txt_add(
            result, confirmation=NEW_ROOT_TXT_CONFIRMATION_PHRASE
        )
        source.write_bytes(b"changed\r\n")
        with self.assertRaisesRegex(NewTxtGateError, "source bytes"):
            authorization.revalidate(result, backup, source, now=now, max_age_seconds=None)

        altered_audit = dict(result.audit)
        altered_candidate = dict(altered_audit["candidate"])
        altered_candidate["blob_sha256"] = "0" * 64
        altered_audit["candidate"] = altered_candidate
        altered = type(result)(result.candidate_blob, result.transaction, altered_audit)
        with self.assertRaisesRegex(NewTxtGateError, "candidate blob"):
            authorization.require_same_candidate(altered)

    def test_generated_transaction_exercises_only_an_injected_fake_transport(self):
        temporary, _backup, _source, result, _now = self._candidate()
        self.addCleanup(temporary.cleanup)
        binding = authorize_new_txt_add(
            result, confirmation=NEW_ROOT_TXT_CONFIRMATION_PHRASE
        )

        class FakeBackend:
            def __init__(self):
                self.calls = []

            def control_out(self, request_type, request, value, index, data, timeout_ms):
                self.calls.append(("control_out", request, bytes(data)))
                return len(data)

            def control_in(self, request_type, request, value, index, length, timeout_ms):
                self.calls.append(("control_in", request))
                if request in (REQUEST_TRANSFER_STATE, REQUEST_COMPLETION):
                    return b"\x00\x00"
                raise AssertionError(request)

            def bulk_write(self, endpoint, data, timeout_ms):
                self.calls.append(("bulk_write", bytes(data)))
                return len(data)

        class FakeAuthorization:
            def revalidate(self, candidate):
                self.candidate = candidate
                binding.require_same_candidate(result)

        backend = FakeBackend()
        fake_authorization = FakeAuthorization()
        completion = AuthorizedWriteSender(backend, 0x01).send(
            result.transaction, fake_authorization
        )
        self.assertEqual(completion, 0)
        self.assertIs(fake_authorization.candidate, result.transaction)
        self.assertEqual(backend.calls[0][1], 0x02)
        self.assertGreaterEqual(sum(call[0] == "bulk_write" for call in backend.calls), 1)

    def test_full_readback_verification_is_independent_and_terminal_on_mismatch(self):
        temporary, backup, source, result, now = self._candidate()
        self.addCleanup(temporary.cleanup)
        authorization = authorize_new_txt_add(
            result, confirmation=NEW_ROOT_TXT_CONFIRMATION_PHRASE
        )
        post = _write_archive(
            Path(temporary.name) / "post",
            result.candidate_blob,
            now,
            fixed_state={
                0x001B: result.transaction.ranges[0][0x00:0x40],
                0x001C: result.transaction.ranges[0][0x40:0x80],
                0x001D: result.transaction.ranges[0][0x80:0xC0],
                0x001E: result.transaction.ranges[0][0xC0:0x100],
                0x001F: result.transaction.ranges[1],
            },
        )
        verification = authorization.verify_post_add_backup(
            result, backup, source, post, now=now, max_age_seconds=None
        )
        self.assertTrue(verification.dynamic_blob_matches)
        self.assertTrue(verification.fixed_state_matches)
        self.assertTrue(verification.unrelated_objects_unchanged)

        bad_post = _write_archive(
            Path(temporary.name) / "bad-post",
            result.candidate_blob[:-4] + b"BAD!",
            now,
            fixed_state={
                0x001B: result.transaction.ranges[0][0x00:0x40],
                0x001C: result.transaction.ranges[0][0x40:0x80],
                0x001D: result.transaction.ranges[0][0x80:0xC0],
                0x001E: result.transaction.ranges[0][0xC0:0x100],
                0x001F: result.transaction.ranges[1],
            },
        )
        with self.assertRaisesRegex(NewTxtGateError, "no retry attempted"):
            authorization.verify_post_add_backup(
                result, backup, source, bad_post, now=now, max_age_seconds=None
            )


if __name__ == "__main__":
    unittest.main()
