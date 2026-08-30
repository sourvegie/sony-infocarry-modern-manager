from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from infocarry.backup_format import calculate_backup_checksum, parse_backup_blob
from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.device_info import RawInfoResponse
from infocarry.prepared_media_package import build_prepared_media_package
from infocarry.prepared_mixed_package_live_smoke import (
    P16_002_MODERN_MIXED_CONFIRMATION,
    P16_002_MODERN_MIXED_OWNER_APPROVAL,
    P16_002_NATIVE_TEMPLATE_FOLDER_PATH,
    P16_002_NATIVE_TEMPLATE_ITEM_PATHS,
    P16_002_TARGET_FOLDER,
    P16MixedPackageLiveSender,
    P16MixedPackageLiveSmokeError,
    execute_p16_mixed_package_live_smoke,
    prepare_p16_mixed_package_live_smoke,
)
from infocarry.protocol import REQUEST_COMPLETION, TransferTimeoutError
from infocarry.write_protocol import WritePolicy

try:
    from test_new_txt import _write_archive
    from test_prepared_package_multi_candidate import _template_blobs
    from test_prepared_package_workflow import PackageWorkflowBackend
    import test_prepared_package_multi_candidate as _fixture
except ModuleNotFoundError:
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_package_multi_candidate import _template_blobs
    from tests.test_prepared_package_workflow import PackageWorkflowBackend
    import tests.test_prepared_package_multi_candidate as _fixture


FIXTURE = Path(__file__).parents[1] / "samples/generated/P16-002-modern-mixed-txt-bmp"
SOURCE = FIXTURE / "source/IC_P16_MIXED_20260830_02"


def _native_named_template_blob():
    _baseline, template_blob = _template_blobs()
    blob = bytearray(template_blob)
    names = {
        0x100: "IC_P16_MIXED_20260830_01",
        0x180: "01-introduction",
        0x1C0: "02-page-01",
    }
    for offset, name in names.items():
        encoded = name.encode("cp932")
        blob[offset + 0x18 : offset + 0x40] = encoded.ljust(0x28, b"\x00")
    blob[0x1C:0x20] = b"\x00" * 4
    blob[0x1C:0x20] = calculate_backup_checksum(bytes(blob)).to_bytes(4, "big")
    return bytes(blob)


class MalformedCompletionBackend(PackageWorkflowBackend):
    def control_in(self, request_type, request, value, index, length, timeout_ms):
        if request == REQUEST_COMPLETION:
            return b"\x00"
        return super().control_in(request_type, request, value, index, length, timeout_ms)


class MissingCompletionBackend(PackageWorkflowBackend):
    def control_in(self, request_type, request, value, index, length, timeout_ms):
        if request == REQUEST_COMPLETION:
            raise OSError("simulated missing completion")
        return super().control_in(request_type, request, value, index, length, timeout_ms)


class P16MixedPackageLiveSmokeTests(unittest.TestCase):
    now = datetime(2026, 8, 30, tzinfo=timezone.utc)

    def test_sanitized_fixture_manifest_and_hashes_are_exact(self):
        manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["root_folder"], P16_002_TARGET_FOLDER)
        self.assertEqual([item["kind"] for item in manifest["ordered_children"]], ["txt", "bmp", "txt"])
        for item in manifest["ordered_children"]:
            source = FIXTURE / item["source_path"]
            data = source.read_bytes()
            self.assertEqual(len(data), item["bytes"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])

    def _setup(self, *, backend=None, after_blob=None, capture_error=False):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        baseline_blob, _template_blob = _template_blobs()
        template_blob = _native_named_template_blob()
        fixed_state = {
            command: b"\x00" * 64
            for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)
        }
        sources = []
        for name in ("01-introduction.txt", "02-page-01.bmp", "03-ending.txt"):
            target = root / name
            target.write_bytes((SOURCE / name).read_bytes())
            sources.append((target, name))
        package = build_prepared_media_package(sources, P16_002_TARGET_FOLDER)
        template = parse_backup_blob(template_blob)
        response = _fixture.PreparedMultiCandidateTests()._response()
        current = {"candidate": None}
        captures = []

        def capture(destination, **_kwargs):
            captures.append(Path(destination))
            if capture_error and len(captures) >= 2:
                raise OSError("simulated backup failure")
            blob = baseline_blob if len(captures) == 1 else (
                current["candidate"].candidate_blob
                if after_blob is None
                else after_blob
            )
            _write_archive(destination, blob, self.now, fixed_state=fixed_state)

        previewed = []

        def preview_callback(candidate):
            previewed.append(candidate.audit_dict())
            current["candidate"] = candidate

        sender = P16MixedPackageLiveSender(
            backend or PackageWorkflowBackend(),
            0x01,
            policy=WritePolicy(
                busy_timeout_seconds=0.25,
                busy_poll_interval_seconds=0.01,
            ),
        )
        common = {
            "backup_destination": root / "fresh-before",
            "package": package,
            "template": template,
            "template_folder_path": P16_002_NATIVE_TEMPLATE_FOLDER_PATH,
            "template_item_paths": P16_002_NATIVE_TEMPLATE_ITEM_PATHS,
            "new_record_timestamp_be32": 0x6A942500,
            "expected_folder_name": P16_002_TARGET_FOLDER,
            "detect_device": lambda: (0x054C, 0x001E),
            "query_capacity": lambda: response,
            "capture": capture,
            "preview_callback": preview_callback,
            "now": self.now,
            "max_age_seconds": None,
        }
        preflight = prepare_p16_mixed_package_live_smoke(**common)
        current["candidate"] = preflight.candidate
        return {
            "temporary": temporary,
            "root": root,
            "package": package,
            "preflight": preflight,
            "response": response,
            "capture": capture,
            "previewed": previewed,
            "backend": sender._sender._backend,
            "sender": sender,
            "common": common,
            "current": current,
            "captures": captures,
            "fixed_state": fixed_state,
        }

    def _execute(self, setup, **overrides):
        arguments = {
            "post_operation_destination": setup["root"] / "after",
            "owner_approval": P16_002_MODERN_MIXED_OWNER_APPROVAL,
            "confirmation": P16_002_MODERN_MIXED_CONFIRMATION,
            "detect_device": setup["common"]["detect_device"],
            "query_capacity": setup["common"]["query_capacity"],
            "capture": setup["capture"],
            "sender": setup["sender"],
            "now": self.now,
            "max_age_seconds": None,
        }
        arguments.update(overrides)
        return execute_p16_mixed_package_live_smoke(setup["preflight"], **arguments)

    def test_exact_fixture_shape_and_read_only_preflight_are_sealed(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        preflight = setup["preflight"]
        self.assertTrue(preflight.audit["read_only"])
        self.assertTrue(preflight.audit["target_absent_from_fresh_backup"])
        self.assertEqual([item.kind for item in preflight.candidate.package.items], ["txt", "bmp", "txt"])
        self.assertEqual(preflight.candidate.audit["package"]["paths"][0], "root\\IC_P16_MIXED_20260830_02")
        offsets = preflight.candidate.audit["package"]["record_offsets"]
        self.assertEqual(len(offsets), 4)
        self.assertTrue(all(int(value, 16) % 0x40 == 0 for value in offsets))
        self.assertEqual(len(setup["captures"]), 1)
        self.assertEqual(setup["sender"].calls, 0)
        preflight.verify_seal()

    def test_seal_ignores_only_reverification_observation_time(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        changed = replace(
            setup["preflight"].before_backup,
            verified_at_utc="2026-08-30T15:00:00+00:00",
        )
        replace(setup["preflight"], before_backup=changed).verify_seal()

    def test_approval_seal_source_change_and_target_conflict_fail_before_send(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaisesRegex(P16MixedPackageLiveSmokeError, "owner approval"):
            self._execute(setup, owner_approval="APPROVE SOMETHING ELSE")
        self.assertEqual(setup["sender"].calls, 0)

        source = setup["package"].items[0].source_path
        source.write_bytes(source.read_bytes() + b"changed")
        with self.assertRaises(P16MixedPackageLiveSmokeError):
            self._execute(setup)
        self.assertEqual(setup["sender"].calls, 0)

        conflict = self._setup()
        self.addCleanup(conflict["temporary"].cleanup)
        # A package already present in the preflight baseline is rejected by
        # the candidate builder before a preview or sender can be reached.
        common = dict(conflict["common"])
        common["capture"] = lambda destination, **_kwargs: _write_archive(
            destination,
            conflict["preflight"].candidate.candidate_blob,
            self.now,
            fixed_state=conflict["fixed_state"],
        )
        with self.assertRaises(P16MixedPackageLiveSmokeError):
            common["backup_destination"] = conflict["root"] / "conflict"
            prepare_p16_mixed_package_live_smoke(**common)
        self.assertEqual(conflict["sender"].calls, 0)

    def test_preflight_rejects_unreviewed_template_identity(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        common = dict(setup["common"])
        common["backup_destination"] = setup["root"] / "unreviewed-template"
        common["template_folder_path"] = ("root", "Template")
        with self.assertRaisesRegex(P16MixedPackageLiveSmokeError, "reviewed native"):
            prepare_p16_mixed_package_live_smoke(**common)
        self.assertEqual(setup["sender"].calls, 0)

    def test_seal_identity_capacity_and_fixed_state_drift_are_terminal(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        setup["preflight"].candidate.audit["candidate"]["blob_sha256"] = "0" * 64
        with self.assertRaisesRegex(P16MixedPackageLiveSmokeError, "sealed"):
            self._execute(setup)
        self.assertEqual(setup["sender"].calls, 0)

        identity = self._setup()
        self.addCleanup(identity["temporary"].cleanup)
        with self.assertRaises(P16MixedPackageLiveSmokeError):
            self._execute(identity, detect_device=lambda: (0x1234, 0x001E))
        self.assertEqual(identity["sender"].calls, 0)

        capacity = self._setup()
        self.addCleanup(capacity["temporary"].cleanup)
        changed_raw = bytearray(capacity["response"].raw_response)
        changed_raw[0x10] ^= 1
        changed_response = NativeCapacityResponse.from_hardware_response(
            RawInfoResponse(0x0019, "changed", bytes(changed_raw)),
            device_identity=(0x054C, 0x001E),
        )
        with self.assertRaises(P16MixedPackageLiveSmokeError):
            self._execute(capacity, query_capacity=lambda: changed_response)
        self.assertEqual(capacity["sender"].calls, 0)

        fixed = self._setup()
        self.addCleanup(fixed["temporary"].cleanup)
        fixed_path = fixed["preflight"].before_backup.object_filename("0x001b:response-001b")
        (fixed["preflight"].before_backup.directory / fixed_path).write_bytes(b"x" * 64)
        with self.assertRaises(P16MixedPackageLiveSmokeError):
            self._execute(fixed)
        self.assertEqual(fixed["sender"].calls, 0)

    def test_success_is_one_shot_and_independently_read_back(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        result = self._execute(setup)
        self.assertEqual(result.completion, 0)
        self.assertTrue(result.verification.success)
        self.assertEqual(setup["sender"].calls, 1)
        self.assertEqual(len(setup["captures"]), 2)
        self.assertEqual(result.audit["workflow"]["operation_sequence"][-1], "independent_readback_verification")
        self.assertFalse(result.audit["workflow"]["automatic_retry_allowed"])
        with self.assertRaisesRegex(P16MixedPackageLiveSmokeError, "second transaction"):
            setup["sender"].send(
                result.candidate.transaction,
                result.candidate,
                result.authorization,
                now=self.now,
                max_age_seconds=None,
                cancelled=None,
                progress=None,
            )

    def test_cancellation_after_header_is_indeterminate_and_one_shot(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        backend = setup["backend"]

        def cancelled_after_transmission_start():
            return any(call[0] == "control_out" for call in backend.calls)

        with self.assertRaises(P16MixedPackageLiveSmokeError) as raised:
            self._execute(setup, cancelled=cancelled_after_transmission_start)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertTrue(raised.exception.write_started)
        self.assertEqual(setup["sender"].calls, 1)
        self.assertFalse(raised.exception.audit["automatic_retry_allowed"])

    def test_cancellation_timeout_disconnect_and_completion_failures_never_retry(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaisesRegex(P16MixedPackageLiveSmokeError, "cancelled") as raised:
            self._execute(setup, cancelled=lambda: True)
        self.assertEqual(raised.exception.state, "cancelled_before_transaction")
        self.assertEqual(setup["sender"].calls, 0)

        for backend_error in (TransferTimeoutError("timeout"), OSError("disconnect")):
            failed = self._setup(backend=PackageWorkflowBackend(bulk_error=backend_error))
            self.addCleanup(failed["temporary"].cleanup)
            with self.assertRaises(P16MixedPackageLiveSmokeError) as raised:
                self._execute(failed)
            self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
            self.assertEqual(failed["sender"].calls, 1)
            self.assertFalse(raised.exception.audit["automatic_retry_allowed"])

        for backend in (
            PackageWorkflowBackend(completions=(1, 0)),
            MalformedCompletionBackend(),
            MissingCompletionBackend(),
        ):
            failed = self._setup(backend=backend)
            self.addCleanup(failed["temporary"].cleanup)
            with self.assertRaises(P16MixedPackageLiveSmokeError):
                self._execute(failed)
            self.assertEqual(failed["sender"].calls, 1)

    def test_post_backup_failure_and_readback_mismatch_are_indeterminate(self):
        failed_backup = self._setup(capture_error=True)
        self.addCleanup(failed_backup["temporary"].cleanup)
        with self.assertRaises(P16MixedPackageLiveSmokeError) as raised:
            self._execute(failed_backup)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertEqual(failed_backup["sender"].calls, 1)

        mismatch = self._setup()
        self.addCleanup(mismatch["temporary"].cleanup)
        bad_blob = bytearray(mismatch["preflight"].candidate.candidate_blob)
        bad_blob[-1] ^= 1
        with self.assertRaises(P16MixedPackageLiveSmokeError) as raised:
            self._execute(
                mismatch,
                capture=lambda destination, **_kwargs: _write_archive(
                    destination,
                    bytes(bad_blob),
                    self.now,
                    fixed_state=mismatch["fixed_state"],
                ),
            )
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertEqual(mismatch["sender"].calls, 1)


if __name__ == "__main__":
    unittest.main()
