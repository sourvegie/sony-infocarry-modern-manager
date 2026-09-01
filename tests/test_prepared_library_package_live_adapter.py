from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from infocarry.backup_format import calculate_backup_checksum, parse_backup_blob
from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.device_info import RawInfoResponse
from infocarry.library import LibraryCatalog
from infocarry.prepared_library_package_live_adapter import (
    P17_005_CONFIRMATION,
    P17_005_OWNER_APPROVAL,
    P17_005_TARGET_FOLDER,
    P17_009_CONFIRMATION,
    P17_009_CONFIRMATION_POLICY,
    P17_009_OWNER_APPROVAL,
    PreparedLibraryPackageLiveAdapterError,
    execute_prepared_library_package_live,
    load_prepared_library_package_live_preflight,
    prepare_prepared_library_package_live_preflight,
    write_prepared_library_package_evidence_manifest,
)
import infocarry.prepared_library_package_bridge as bridge_module
import infocarry.prepared_library_package_live_adapter as adapter_module
import infocarry.prepared_package_multi_candidate as candidate_module
from infocarry.prepared_media_package import (
    build_prepared_media_package,
    export_prepared_media_package,
)
from infocarry.protocol import REQUEST_COMPLETION, TransferTimeoutError
from infocarry.write_protocol import REQUEST_BEGIN_TRANSMIT, WritePolicy

try:
    from test_new_txt import _write_archive
    from test_prepared_package_multi_candidate import _template_blobs, make_profile_bmp
    from test_prepared_package_workflow import PackageWorkflowBackend
except ModuleNotFoundError:
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_package_multi_candidate import _template_blobs, make_profile_bmp
    from tests.test_prepared_package_workflow import PackageWorkflowBackend


def _named_template_blob() -> bytes:
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


def _response() -> NativeCapacityResponse:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "infocarry_info_responses.json").read_text()
    )
    return NativeCapacityResponse.from_hardware_response(
        RawInfoResponse(
            0x0019,
            "test",
            bytes.fromhex(fixture["hardware"]["response_hex"]),
        ),
        device_identity=(0x054C, 0x001E),
    )


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


class PreparedLibraryPackageLiveAdapterTests(unittest.TestCase):
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)

    def _setup(
        self,
        *,
        backend=None,
        capture_error=False,
        after_blob=None,
        explicit=False,
    ):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        baseline_blob, _template_blob = _template_blobs()
        fixed_state = {
            command: b"\x00" * 64
            for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)
        }
        intro = root / "intro.txt"
        image = root / "page.bmp"
        ending = root / "ending.txt"
        intro.write_text("Introduction\n", encoding="utf-8")
        image.write_bytes(make_profile_bmp())
        ending.write_text("The End\n", encoding="utf-8")
        package = build_prepared_media_package(
            (
                (intro, "01-introduction.txt"),
                (image, "02-page-01.bmp"),
                (ending, "03-ending.txt"),
            ),
            P17_005_TARGET_FOLDER,
        )
        package_root = export_prepared_media_package(package, root / "package")
        catalog = LibraryCatalog(root / "catalog/library.json")
        item = catalog.import_prepared_package(package_root)
        template = parse_backup_blob(_named_template_blob())
        current = {"candidate": None}
        captures = []

        def capture(destination, **_kwargs):
            captures.append(Path(destination))
            if capture_error and len(captures) >= 3:
                raise OSError("simulated post-operation backup failure")
            blob = baseline_blob if len(captures) <= 2 else (
                current["candidate"].candidate_blob
                if after_blob is None
                else after_blob
            )
            _write_archive(destination, blob, self.now, fixed_state=fixed_state)

        previewed = []

        def preview_callback(report):
            previewed.append(dict(report))

        patchers = [
            patch.object(
                bridge_module,
                "P17_003_REVIEWED_TEMPLATE_BLOB_SHA256",
                hashlib.sha256(template.data).hexdigest(),
            ),
            patch.object(
                candidate_module,
                "REVIEWED_TEMPLATE_SUBSET_POLICY_SHA256",
                hashlib.sha256(template.data).hexdigest(),
            ),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

        common = {
            "catalog": catalog,
            "selected_item_id": item.item_id,
            "backup_destination": root / "before",
            "template": template,
            "new_record_timestamp_be32": 0x6A958595,
            "detect_device": lambda: (0x054C, 0x001E),
            "query_capacity": _response,
            "capture": capture,
            "preview_callback": preview_callback,
            "now": self.now,
            "max_age_seconds": None,
        }
        if explicit:
            common.update(
                {
                    "owner_approval_phrase": "APPROVE P17-011 MODERN LIBRARY PACKAGE PREFLIGHT 01",
                    "confirmation_phrase": "CONFIRM P17-011 ONE INFOCARRY MULTI-CHILD PACKAGE",
                    "confirmation_policy": P17_009_CONFIRMATION_POLICY,
                }
            )
        preflight = prepare_prepared_library_package_live_preflight(**common)
        current["candidate"] = preflight.candidate
        backend = backend or PackageWorkflowBackend()
        return {
            "temporary": temporary,
            "root": root,
            "catalog": catalog,
            "item": item,
            "template": template,
            "preflight": preflight,
            "current": current,
            "capture": capture,
            "captures": captures,
            "previewed": previewed,
            "backend": backend,
            "fixed_state": fixed_state,
            "common": common,
        }

    def _write_loader_report(self, setup, mutate=None, raw=None):
        report_path = setup["root"] / "sealed-preflight.json"
        if raw is None:
            report = setup["preflight"].to_dict()
            if mutate is not None:
                mutate(report)
            raw = json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
        report_path.write_text(raw, encoding="utf-8")
        return report_path

    def _load_report(self, setup, path):
        return load_prepared_library_package_live_preflight(
            path,
            catalog=setup["catalog"],
            selected_item_id=setup["item"].item_id,
            backup=setup["preflight"].before_backup,
            template=setup["template"],
            capacity_response=setup["preflight"].capacity_response,
        )

    def _execute(self, setup, **overrides):
        arguments = {
            "catalog": setup["catalog"],
            "selected_item_id": setup["item"].item_id,
            "backup_destination": setup["root"] / "execution-before",
            "post_operation_destination": setup["root"] / "after",
            "evidence_manifest_destination": setup["root"] / "evidence/result-manifest.json",
            "owner_approval": P17_005_OWNER_APPROVAL,
            "confirmation": P17_005_CONFIRMATION,
            "detect_device": setup["common"]["detect_device"],
            "query_capacity": setup["common"]["query_capacity"],
            "backend": setup["backend"],
            "bulk_out_endpoint": 0x01,
            "policy": WritePolicy(
                busy_timeout_seconds=0.25,
                busy_poll_interval_seconds=0.01,
            ),
            "capture": setup["capture"],
            "now": self.now,
            "max_age_seconds": None,
        }
        arguments.update(overrides)
        return execute_prepared_library_package_live(setup["preflight"], **arguments)

    @staticmethod
    def _sender_calls(setup):
        return sum(
            1
            for call in setup["backend"].calls
            if call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
        )

    def test_preflight_is_exact_hash_only_and_sender_is_not_reached(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        preflight = setup["preflight"]
        preflight.verify_seal()
        report = preflight.to_dict()
        self.assertEqual(report["state"], "ready_for_hardware_test_host_only")
        self.assertEqual(report["device_identity"], ["0x054c", "0x001e"])
        self.assertTrue(report["target_absent_from_fresh_backup"])
        self.assertFalse(report["usb_transmission_performed"])
        self.assertEqual(report["send_count"], 0)
        self.assertEqual(
            [item.kind for item in preflight.candidate.package.items],
            ["txt", "bmp", "txt"],
        )
        self.assertEqual(len(setup["captures"]), 1)
        self.assertEqual(self._sender_calls(setup), 0)
        serialized = json.dumps(report)
        self.assertNotIn('"candidate_blob":', serialized)
        self.assertNotIn('"candidate_bytes":', serialized)

    def test_loader_accepts_exact_p17_012_nested_transaction_binding(self):
        setup = self._setup(explicit=True)
        self.addCleanup(setup["temporary"].cleanup)
        path = self._write_loader_report(setup)
        loaded = self._load_report(setup, path)
        self.assertEqual(loaded.seal_sha256, setup["preflight"].seal_sha256)
        self.assertEqual(
            loaded.authorization.to_dict()["candidate_transaction_sha256"],
            loaded.candidate.transaction_sha256,
        )
        self.assertEqual(
            [path.resolve() for path in setup["captures"]],
            [(setup["root"] / "before").resolve()],
        )

    def test_loader_rejects_missing_nested_transaction_binding_before_hardware(self):
        setup = self._setup(explicit=True)
        self.addCleanup(setup["temporary"].cleanup)

        def remove_nested(report):
            report["authorization"].pop("candidate_transaction_sha256")

        path = self._write_loader_report(setup, remove_nested)
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "candidate_transaction_sha256",
        ):
            self._load_report(setup, path)
        self.assertEqual(
            [path.resolve() for path in setup["captures"]],
            [(setup["root"] / "before").resolve()],
        )
        self.assertEqual(self._sender_calls(setup), 0)

    def test_loader_rejects_stale_top_level_only_transaction_alias(self):
        setup = self._setup(explicit=True)
        self.addCleanup(setup["temporary"].cleanup)

        def replace_with_alias(report):
            report["authorization"].pop("candidate_transaction_sha256")
            report["transaction_sha256"] = setup["preflight"].candidate.transaction_sha256

        path = self._write_loader_report(setup, replace_with_alias)
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "schema fields differ",
        ):
            self._load_report(setup, path)
        self.assertEqual(
            [path.resolve() for path in setup["captures"]],
            [(setup["root"] / "before").resolve()],
        )
        self.assertEqual(self._sender_calls(setup), 0)

    def test_loader_rejects_contradictory_top_level_transaction_alias(self):
        setup = self._setup(explicit=True)
        self.addCleanup(setup["temporary"].cleanup)

        def add_contradictory_alias(report):
            report["transaction_sha256"] = "0" * 64

        path = self._write_loader_report(setup, add_contradictory_alias)
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "schema fields differ",
        ):
            self._load_report(setup, path)
        self.assertEqual(
            [path.resolve() for path in setup["captures"]],
            [(setup["root"] / "before").resolve()],
        )
        self.assertEqual(self._sender_calls(setup), 0)

    def test_loader_rejects_malformed_nested_transaction_hash(self):
        setup = self._setup(explicit=True)
        self.addCleanup(setup["temporary"].cleanup)

        def replace_hash(report):
            report["authorization"]["candidate_transaction_sha256"] = "not-a-hash"

        path = self._write_loader_report(setup, replace_hash)
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "lowercase SHA-256 digest",
        ):
            self._load_report(setup, path)
        self.assertEqual(
            [path.resolve() for path in setup["captures"]],
            [(setup["root"] / "before").resolve()],
        )
        self.assertEqual(self._sender_calls(setup), 0)

    def test_loader_rejects_nested_transaction_mismatch_before_hardware(self):
        setup = self._setup(explicit=True)
        self.addCleanup(setup["temporary"].cleanup)

        def replace_hash(report):
            report["authorization"]["candidate_transaction_sha256"] = "0" * 64

        path = self._write_loader_report(setup, replace_hash)
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "does not match the independently reconstructed transaction",
        ):
            self._load_report(setup, path)
        self.assertEqual(
            [path.resolve() for path in setup["captures"]],
            [(setup["root"] / "before").resolve()],
        )
        self.assertEqual(self._sender_calls(setup), 0)

    def test_loader_rejects_duplicate_json_keys_before_hardware(self):
        setup = self._setup(explicit=True)
        self.addCleanup(setup["temporary"].cleanup)
        path = self._write_loader_report(
            setup,
            raw=(
                '{"format": "infocarry-p17-005-library-package-live-adapter-v1", '
                '"format": "infocarry-p17-005-library-package-live-adapter-v1"}'
            ),
        )
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "duplicate JSON key",
        ):
            self._load_report(setup, path)
        self.assertEqual(
            [path.resolve() for path in setup["captures"]],
            [(setup["root"] / "before").resolve()],
        )
        self.assertEqual(self._sender_calls(setup), 0)

    def test_p17_009_phrases_are_new_and_sealed_into_authorization(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        common = dict(setup["common"])
        common.update(
            {
                "backup_destination": setup["root"] / "p17-009-before",
                "owner_approval_phrase": P17_009_OWNER_APPROVAL,
                "confirmation_phrase": P17_009_CONFIRMATION,
                "confirmation_policy": P17_009_CONFIRMATION_POLICY,
            }
        )
        preflight = prepare_prepared_library_package_live_preflight(**common)
        preflight.verify_seal()
        report = preflight.to_dict()
        self.assertEqual(report["owner_approval_phrase"], P17_009_OWNER_APPROVAL)
        self.assertEqual(report["confirmation_phrase"], P17_009_CONFIRMATION)
        self.assertEqual(report["confirmation_policy"], P17_009_CONFIRMATION_POLICY)
        self.assertEqual(
            preflight.authorization.core.confirmation_phrase, P17_009_CONFIRMATION
        )
        self.assertNotEqual(P17_009_OWNER_APPROVAL, P17_005_OWNER_APPROVAL)
        self.assertNotEqual(P17_009_CONFIRMATION, P17_005_CONFIRMATION)

    def test_explicit_policy_rejects_expired_p17_007_phrases(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        for field in ("owner_approval_phrase", "confirmation_phrase"):
            with self.subTest(field=field):
                common = dict(setup["common"])
                common.update(
                    {
                        "backup_destination": setup["root"] / f"p17-009-expired-{field}",
                        "owner_approval_phrase": (
                            P17_005_OWNER_APPROVAL
                            if field == "owner_approval_phrase"
                            else P17_009_OWNER_APPROVAL
                        ),
                        "confirmation_phrase": (
                            P17_005_CONFIRMATION
                            if field == "confirmation_phrase"
                            else P17_009_CONFIRMATION
                        ),
                        "confirmation_policy": P17_009_CONFIRMATION_POLICY,
                    }
                )
                with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as context:
                    prepare_prepared_library_package_live_preflight(**common)
                self.assertEqual(context.exception.stage, "approval")
                self.assertIn("expired P17-007", str(context.exception))

    def test_adapter_is_unreachable_from_normal_cli_and_gui(self):
        cli = (Path(__file__).parents[1] / "src/infocarry/cli.py").read_text()
        desktop = (Path(__file__).parents[1] / "src/infocarry/desktop_ttk.py").read_text()
        self.assertNotIn("prepared_library_package_live_adapter", cli)
        self.assertNotIn("prepared_library_package_live_adapter", desktop)
        self.assertFalse(hasattr(adapter_module, "AuthorizedWriteSender"))

    def test_preflight_rejects_wrong_identity_and_target_conflict(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        common = dict(setup["common"])
        common["backup_destination"] = setup["root"] / "wrong-device"
        common["detect_device"] = lambda: (0x054C, 0x001F)
        with self.assertRaisesRegex(PreparedLibraryPackageLiveAdapterError, "not Sony"):
            prepare_prepared_library_package_live_preflight(**common)
        self.assertEqual(self._sender_calls(setup), 0)

        conflict = self._setup()
        self.addCleanup(conflict["temporary"].cleanup)
        common = dict(conflict["common"])
        common["backup_destination"] = conflict["root"] / "conflict"
        common["capture"] = lambda destination, **_kwargs: _write_archive(
            destination,
            conflict["preflight"].candidate.candidate_blob,
            self.now,
            fixed_state=conflict["fixed_state"],
        )
        with self.assertRaisesRegex(PreparedLibraryPackageLiveAdapterError, "candidate"):
            prepare_prepared_library_package_live_preflight(**common)

        insufficient = self._setup()
        self.addCleanup(insufficient["temporary"].cleanup)
        raw = bytearray(_response().raw_response)
        raw[0x08:0x0C] = (1).to_bytes(4, "big")
        low_capacity = NativeCapacityResponse.from_hardware_response(
            RawInfoResponse(0x0019, "low-capacity", bytes(raw)),
            device_identity=(0x054C, 0x001E),
        )
        common = dict(insufficient["common"])
        common["backup_destination"] = insufficient["root"] / "insufficient"
        common["query_capacity"] = lambda: low_capacity
        with self.assertRaisesRegex(PreparedLibraryPackageLiveAdapterError, "candidate"):
            prepare_prepared_library_package_live_preflight(**common)

    def test_tampered_seal_source_backup_and_capacity_stop_before_sender(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        forged = replace(setup["preflight"], audit={"state": "forged"})
        with self.assertRaisesRegex(PreparedLibraryPackageLiveAdapterError, "report bindings"):
            self._execute({**setup, "preflight": forged})
        self.assertEqual(self._sender_calls(setup), 0)

        for key, value in (
            ("device_identity", ["0x0000", "0x0000"]),
            ("normal_gui_cli_transfer_exposed", True),
        ):
            tampered = setup["preflight"].to_dict()
            tampered[key] = value
            with self.assertRaisesRegex(
                PreparedLibraryPackageLiveAdapterError,
                "report bindings|seal was modified",
            ):
                self._execute({**setup, "preflight": replace(setup["preflight"], audit=tampered)})
        self.assertEqual(self._sender_calls(setup), 0)

        source = setup["preflight"].candidate.package.items[0].source_path
        source.write_bytes(source.read_bytes() + b"drift")
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
            self._execute(setup)
        self.assertEqual(self._sender_calls(setup), 0)

        backup_file = setup["preflight"].before_backup.object_filename("0x8004:backup-blob")
        (setup["preflight"].before_backup.directory / backup_file).write_bytes(b"tampered")
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
            self._execute(setup)
        self.assertEqual(self._sender_calls(setup), 0)

        fixed = self._setup()
        self.addCleanup(fixed["temporary"].cleanup)
        fixed_file = fixed["preflight"].before_backup.object_filename(
            "0x001b:response-001b"
        )
        (fixed["preflight"].before_backup.directory / fixed_file).write_bytes(
            b"changed" * 10 + b"x" * 4
        )
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
            self._execute(fixed)
        self.assertEqual(self._sender_calls(fixed), 0)

        capacity = self._setup()
        self.addCleanup(capacity["temporary"].cleanup)
        changed = bytearray(_response().raw_response)
        changed[0x10] ^= 1
        changed_response = NativeCapacityResponse.from_hardware_response(
            RawInfoResponse(0x0019, "changed", bytes(changed)),
            device_identity=(0x054C, 0x001E),
        )
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
            self._execute(capacity, query_capacity=lambda: changed_response)
        self.assertEqual(self._sender_calls(capacity), 0)

    def test_cancel_before_start_and_success_are_one_shot(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaisesRegex(PreparedLibraryPackageLiveAdapterError, "cancelled"):
            self._execute(setup, cancelled=lambda: True)
        self.assertEqual(self._sender_calls(setup), 0)

        result = self._execute(setup)
        self.assertEqual(result.completion, 0)
        self.assertTrue(result.verification.success)
        self.assertEqual(
            result.before_backup.directory,
            (setup["root"] / "execution-before").resolve(),
        )
        self.assertEqual(self._sender_calls(setup), 1)

    def test_pre_send_failure_does_not_consume_approval_or_one_shot_claim(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)

        with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as raised:
            self._execute(setup, detect_device=lambda: (0x054C, 0x001F))
        self.assertEqual(raised.exception.stage, "preflight_revalidation")
        self.assertFalse(raised.exception.write_started)
        self.assertEqual(self._sender_calls(setup), 0)

        # A pre-send gate failure does not consume the sealed one-shot claim;
        # the same exact preflight may still be attempted after revalidation.
        result = self._execute(setup)
        self.assertEqual(result.completion, 0)
        self.assertEqual(self._sender_calls(setup), 1)
        self.assertEqual(len(setup["captures"]), 3)
        manifest = json.loads(
            (setup["root"] / "evidence/result-manifest.json").read_text(encoding="utf-8")
        )
        self.assertIsNotNone(manifest["before_backup"])
        self.assertIsNotNone(manifest["after_backup"])
        self.assertTrue(manifest["backup_state_comparison"]["raw_state_equal"])
        self.assertIn(
            "archive_directory",
            {
                entry["field"]
                for entry in manifest["backup_state_comparison"][
                    "provenance_differences"
                ]
            },
        )
        self.assertEqual(manifest["result_audit"]["state"], "readback_verified")

        setup["captures"].clear()
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "already attempted its one transaction",
        ):
            self._execute(
                setup,
                backup_destination=setup["root"] / "execution-before-second",
                post_operation_destination=setup["root"] / "after-second",
                evidence_manifest_destination=setup["root"] / "evidence/second.json",
            )
        self.assertEqual(self._sender_calls(setup), 1)

    def test_independent_same_state_backup_provenance_does_not_block_execution(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        captures = setup["captures"]

        def recaptured_with_new_provenance(destination, **kwargs):
            captures.append(Path(destination))
            blob = setup["current"]["candidate"].candidate_blob if len(captures) >= 3 else setup["preflight"].candidate.core.baseline.data
            _write_archive(
                destination,
                blob,
                self.now - timedelta(seconds=len(captures)),
                fixed_state=setup["fixed_state"],
            )

        setup["capture"] = recaptured_with_new_provenance
        result = self._execute(setup)
        self.assertEqual(result.completion, 0)
        self.assertEqual(self._sender_calls(setup), 1)
        self.assertTrue(result.audit["backup_state_comparison"]["raw_state_equal"])
        self.assertTrue(result.audit["backup_state_comparison"]["provenance_differences"])
        self.assertIn(
            "manifest_sha256",
            {
                entry["field"]
                for entry in result.audit["backup_state_comparison"][
                    "provenance_differences"
                ]
            },
        )
    def test_execute_requires_injected_backend_at_approved_boundary(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaisesRegex(PreparedLibraryPackageLiveAdapterError, "write backend"):
            self._execute(setup, backend=None)
        self.assertEqual(self._sender_calls(setup), 0)

    def test_after_start_cancel_timeout_disconnect_and_completion_failures_are_terminal(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)

        def cancelled_after_start():
            return any(call[0] == "control_out" for call in setup["backend"].calls)

        with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as raised:
            self._execute(setup, cancelled=cancelled_after_start)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertTrue(raised.exception.write_started)
        self.assertEqual(self._sender_calls(setup), 1)

        for backend_error in (TransferTimeoutError("timeout"), OSError("disconnect")):
            failed = self._setup(backend=PackageWorkflowBackend(bulk_error=backend_error))
            self.addCleanup(failed["temporary"].cleanup)
            with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as raised:
                self._execute(failed)
            self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
            self.assertEqual(self._sender_calls(failed), 1)

        for backend in (
            PackageWorkflowBackend(completions=(1, 0)),
            MalformedCompletionBackend(),
            MissingCompletionBackend(),
        ):
            failed = self._setup(backend=backend)
            self.addCleanup(failed["temporary"].cleanup)
            with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
                self._execute(failed)
            self.assertEqual(self._sender_calls(failed), 1)

    def test_post_backup_and_readback_failures_are_indeterminate_without_retry(self):
        failed_backup = self._setup(capture_error=True)
        self.addCleanup(failed_backup["temporary"].cleanup)
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as raised:
            self._execute(failed_backup)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertEqual(self._sender_calls(failed_backup), 1)

        mismatch = self._setup()
        self.addCleanup(mismatch["temporary"].cleanup)
        bad_blob = bytearray(mismatch["preflight"].candidate.candidate_blob)
        bad_blob[-1] ^= 1
        original_capture = mismatch["capture"]
        post_capture_calls = 0

        def mismatched_post_capture(destination, **kwargs):
            nonlocal post_capture_calls
            post_capture_calls += 1
            if post_capture_calls == 1:
                return original_capture(destination, **kwargs)
            return _write_archive(
                destination,
                bytes(bad_blob),
                self.now,
                fixed_state=mismatch["fixed_state"],
            )

        mismatch["capture"] = mismatched_post_capture
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as raised:
            self._execute(mismatch)
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertEqual(self._sender_calls(mismatch), 1)

    def test_external_manifest_is_hash_only_and_non_overwriting(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        result = self._execute(setup)
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "missing required fields",
        ):
            write_prepared_library_package_evidence_manifest(
                setup["root"] / "evidence/rejected.json",
                preflight=setup["preflight"],
                before_backup=result.before_backup,
                after_backup=result.after_backup,
                result_audit={"state": "host-test"},
                now=self.now,
                max_age_seconds=None,
            )
        for field in ("candidate_bytes_hex", "transaction_bytes_hex"):
            forged = dict(result.audit)
            forged[field] = "00"
            with self.assertRaisesRegex(
                PreparedLibraryPackageLiveAdapterError,
                "unexpected fields",
            ):
                write_prepared_library_package_evidence_manifest(
                    setup["root"] / f"evidence/{field}.json",
                    preflight=setup["preflight"],
                    before_backup=result.before_backup,
                    after_backup=result.after_backup,
                    result_audit=forged,
                    now=self.now,
                    max_age_seconds=None,
                )
        forged_sequence = json.loads(json.dumps(result.audit))
        forged_sequence["workflow"]["operation_sequence"][0] = (
            "candidate_bytes_hex=00"
        )
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "one-shot no-retry result",
        ):
            write_prepared_library_package_evidence_manifest(
                setup["root"] / "evidence/sequence-payload.json",
                preflight=setup["preflight"],
                before_backup=result.before_backup,
                after_backup=result.after_backup,
                result_audit=forged_sequence,
                now=self.now,
                max_age_seconds=None,
            )
        forged_manifest_binding = json.loads(json.dumps(result.audit))
        forged_manifest_binding["evidence_manifest"] = {
            "path": "candidate_bytes_hex=00",
            "sha256": "0" * 64,
        }
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "unexpected fields",
        ):
            write_prepared_library_package_evidence_manifest(
                setup["root"] / "evidence/manifest-binding-payload.json",
                preflight=setup["preflight"],
                before_backup=result.before_backup,
                after_backup=result.after_backup,
                result_audit=forged_manifest_binding,
                now=self.now,
                max_age_seconds=None,
            )
        path = write_prepared_library_package_evidence_manifest(
            setup["root"] / "evidence/preservation-manifest-v1.json",
            preflight=setup["preflight"],
            before_backup=result.before_backup,
            after_backup=result.after_backup,
            result_audit=result.audit,
            now=self.now,
            max_age_seconds=None,
        )
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 1)
        self.assertTrue(payload["raw_candidate_bytes_included"] is False)
        with self.assertRaisesRegex(PreparedLibraryPackageLiveAdapterError, "existing"):
            write_prepared_library_package_evidence_manifest(
                path,
                preflight=setup["preflight"],
                before_backup=result.before_backup,
                after_backup=result.after_backup,
                result_audit=result.audit,
                now=self.now,
                max_age_seconds=None,
            )


if __name__ == "__main__":
    unittest.main()
