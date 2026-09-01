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
from infocarry.prepared_library_package_operation_bundle import (
    OperationBundleError,
    PreparedLibraryPackageOperationBundle,
    load_operation_bundle,
)
import infocarry.prepared_library_package_bridge as bridge_module
import infocarry.prepared_library_package_live_adapter as adapter_module
import infocarry.prepared_package_multi_candidate as candidate_module
from infocarry.prepared_media_package import (
    build_prepared_media_package,
    export_prepared_media_package,
)
from infocarry.protocol import REQUEST_COMPLETION, TransferTimeoutError
from infocarry.write_protocol import REQUEST_BEGIN_TRANSMIT

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
        evidence_namespace = root / "evidence-namespace"
        evidence_namespace.mkdir()
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
            blob = baseline_blob if Path(destination).name != "backup-after-0001" else (
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
        report_path = root / "sealed-preflight.json"
        report_path.write_text(
            json.dumps(preflight.to_dict(), ensure_ascii=True, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        template_path = root / "reviewed-template.bin"
        template_path.write_bytes(template.data)
        capacity_path = root / "capacity-response.bin"
        capacity_path.write_bytes(_response().raw_response)
        bundle = PreparedLibraryPackageOperationBundle.from_sealed_report(
            report_path,
            template_path=template_path,
            capacity_response_path=capacity_path,
        )
        bundle_path = bundle.write(root / "operation-bundle.json")
        bundle = load_operation_bundle(bundle_path)
        backend = backend or PackageWorkflowBackend()
        return {
            "temporary": temporary,
            "root": root,
            "catalog": catalog,
            "item": item,
            "template": template,
            "preflight": preflight,
            "original_preflight": preflight,
            "bundle": bundle,
            "report_path": report_path,
            "template_path": template_path,
            "capacity_path": capacity_path,
            "current": current,
            "capture": capture,
            "captures": captures,
            "previewed": previewed,
            "backend": backend,
            "fixed_state": fixed_state,
            "evidence_namespace": evidence_namespace,
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
        preflight = setup["preflight"]
        bundle = setup["bundle"]
        if preflight is not setup["original_preflight"]:
            setup["report_path"].write_text(
                json.dumps(preflight.to_dict(), ensure_ascii=True, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
            try:
                bundle = PreparedLibraryPackageOperationBundle.from_sealed_report(
                    setup["report_path"],
                    template_path=setup["template_path"],
                    capacity_response_path=setup["capacity_path"],
                )
            except OperationBundleError as exc:
                raise PreparedLibraryPackageLiveAdapterError(
                    str(exc), stage="operation_bundle", state="failed"
                ) from exc
        evidence_namespace = overrides.pop(
            "evidence_namespace", setup["evidence_namespace"]
        )
        arguments = {
            "owner_approval": P17_005_OWNER_APPROVAL,
            "confirmation": P17_005_CONFIRMATION,
            "detect_device": setup["common"]["detect_device"],
            "query_capacity": setup["common"]["query_capacity"],
            "backend": setup["backend"],
            "capture": setup["capture"],
            "evidence_namespace": evidence_namespace,
            "now": self.now,
            "max_age_seconds": None,
        }
        arguments.update(overrides)
        return execute_prepared_library_package_live(bundle, **arguments)

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
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "report bindings|sealed report lacks canonical",
        ):
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
                "report bindings|seal was modified|operation bundle|reviewed value",
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
        self.assertEqual(result.before_backup.directory.name, "backup-before-0001")
        self.assertEqual(result.after_backup.directory.name, "backup-after-0001")
        self.assertEqual(self._sender_calls(setup), 1)

    def test_pre_send_failure_after_claim_expires_approval_without_retry(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)

        with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as raised:
            self._execute(setup, detect_device=lambda: (0x054C, 0x001F))
        self.assertEqual(raised.exception.stage, "preflight_revalidation")
        self.assertFalse(raised.exception.write_started)
        self.assertTrue(raised.exception.audit["approval_consumed"])
        self.assertEqual(self._sender_calls(setup), 0)

        setup["captures"].clear()
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "already attempted its one transaction",
        ):
            self._execute(
                setup,
                evidence_namespace=setup["evidence_namespace"],
            )
        self.assertEqual(self._sender_calls(setup), 0)
        self.assertEqual(setup["captures"], [])

    def test_p17_017_namespace_must_be_external_and_non_symlink(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        setup["captures"].clear()
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "outside the source repository",
        ):
            self._execute(setup, evidence_namespace=Path(__file__).resolve().parents[1])
        self.assertEqual(self._sender_calls(setup), 0)
        self.assertEqual(setup["captures"], [])

        link = setup["root"] / "evidence-link"
        link.symlink_to(setup["evidence_namespace"], target_is_directory=True)
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "must not be a symlink",
        ):
            self._execute(setup, evidence_namespace=link)
        self.assertEqual(self._sender_calls(setup), 0)
        self.assertEqual(setup["captures"], [])

    def test_independent_same_state_backup_provenance_does_not_block_execution(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        captures = setup["captures"]

        def recaptured_with_new_provenance(destination, **kwargs):
            captures.append(Path(destination))
            blob = (
                setup["current"]["candidate"].candidate_blob
                if Path(destination).name == "backup-after-0001"
                else setup["preflight"].candidate.core.baseline.data
            )
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
        with self.assertRaisesRegex(PreparedLibraryPackageLiveAdapterError, "write backend") as raised:
            self._execute(setup, backend=None)
        self.assertTrue(raised.exception.audit["approval_consumed"])
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
        path = setup["root"] / "manual-evidence/preservation-manifest-v1.json"
        manifest_audit = json.loads(json.dumps(result.audit))
        manifest_audit["evidence_outputs"] = {
            "root": str(path.parent),
            "before_backup": str(path.parent / "backup-before-0001"),
            "after_backup": str(path.parent / "backup-after-0001"),
            "manifest": str(path),
        }
        path = write_prepared_library_package_evidence_manifest(
            path,
            preflight=setup["preflight"],
            before_backup=result.before_backup,
            after_backup=result.after_backup,
            result_audit=manifest_audit,
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
                result_audit=manifest_audit,
                now=self.now,
                max_age_seconds=None,
            )

    @staticmethod
    def _bundle_json_with_mutation(setup, mutate, name):
        value = json.loads(json.dumps(setup["bundle"].to_dict()))
        mutate(value)
        unsigned = dict(value)
        unsigned.pop("bundle_sha256", None)
        value["bundle_sha256"] = hashlib.sha256(
            json.dumps(
                unsigned,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        path = setup["root"] / f"{name}.json"
        path.write_text(
            json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    def _assert_bundle_rejected_before_runtime(self, setup, mutate, name):
        path = self._bundle_json_with_mutation(setup, mutate, name)
        bundle = load_operation_bundle(path, verify_artifacts=False)
        events = []

        def detect():
            events.append("detect")
            return (0x054C, 0x001E)

        def capacity():
            events.append("capacity")
            return _response()

        def capture(*args, **kwargs):
            events.append("capture")
            return setup["capture"](*args, **kwargs)

        with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
            execute_prepared_library_package_live(
                bundle,
                owner_approval=P17_005_OWNER_APPROVAL,
                confirmation=P17_005_CONFIRMATION,
                detect_device=detect,
                query_capacity=capacity,
                backend=setup["backend"],
                capture=capture,
                evidence_namespace=setup["evidence_namespace"],
                now=self.now,
                max_age_seconds=None,
            )
        self.assertEqual(events, [])
        self.assertEqual(self._sender_calls(setup), 0)

    def test_production_entrypoint_has_two_nominal_fake_rehearsals(self):
        for name in ("nominal-a", "nominal-b"):
            with self.subTest(name=name):
                setup = self._setup()
                self.addCleanup(setup["temporary"].cleanup)
                result = self._execute(setup)
                self.assertEqual(result.completion, 0)
                self.assertTrue(result.verification.success)
                self.assertEqual(self._sender_calls(setup), 1)
                self.assertEqual(len(setup["captures"]), 3)
                self.assertEqual(
                    json.loads(
                        Path(
                            setup["captures"][-1].parent
                            / "result-manifest-0001.json"
                        ).read_text(
                            encoding="utf-8"
                        )
                    )["result_audit"]["completion"],
                    "0x0000",
                )

    def test_production_entrypoint_preflight_reaches_sender_boundary_without_send(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "preflight-only",
        ):
            self._execute(setup, backend=None, preflight_only=True)
        self.assertEqual(len(setup["captures"]), 2)
        self.assertEqual(self._sender_calls(setup), 0)

    def test_p17_016_preflight_output_does_not_deadlock_same_bundle_live_attempt(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)

        with self.assertRaisesRegex(
            PreparedLibraryPackageLiveAdapterError,
            "preflight-only",
        ) as preflight_error:
            self._execute(setup, backend=None, preflight_only=True)
        preflight_root = Path(
            preflight_error.exception.audit["evidence_outputs"]["root"]
        )
        self.assertTrue(preflight_root.is_dir())
        self.assertEqual(self._sender_calls(setup), 0)

        result = self._execute(setup)
        live_root = Path(result.audit["evidence_outputs"]["root"])
        self.assertTrue(result.verification.success)
        self.assertEqual(result.completion, 0)
        self.assertNotEqual(live_root, preflight_root)
        self.assertTrue((preflight_root / "backup-before-0001").is_dir())
        self.assertTrue((live_root / "backup-before-0001").is_dir())
        self.assertTrue((live_root / "backup-after-0001").is_dir())
        self.assertTrue((live_root / "result-manifest-0001.json").is_file())
        self.assertEqual(self._sender_calls(setup), 1)

    def test_p17_017_bundle_identity_excludes_attempt_output_paths(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        first = setup["bundle"]
        second = PreparedLibraryPackageOperationBundle.from_sealed_report(
            setup["report_path"],
            template_path=setup["template_path"],
            capacity_response_path=setup["capacity_path"],
        )
        self.assertEqual(first.bundle_sha256, second.bundle_sha256)
        serialized = first.to_dict()
        self.assertNotIn("outputs", serialized)
        self.assertIn("evidence_output_policy", serialized)

    def test_p17_017_output_root_collision_and_path_escape_stop_before_callbacks(self):
        for name, allocator in (
            (
                "collision",
                lambda namespace: namespace / "already-used",
            ),
            (
                "escape",
                lambda namespace: namespace.parent / "outside-namespace",
            ),
        ):
            with self.subTest(name=name):
                setup = self._setup()
                self.addCleanup(setup["temporary"].cleanup)
                collision = setup["evidence_namespace"] / "already-used"
                collision.mkdir()
                events = []

                def detect():
                    events.append("detect")
                    return (0x054C, 0x001E)

                with self.assertRaisesRegex(
                    PreparedLibraryPackageLiveAdapterError,
                    "evidence root",
                ):
                    self._execute(
                        setup,
                        evidence_root_allocator=allocator,
                        detect_device=detect,
                    )
                self.assertEqual(events, [])
                self.assertEqual(len(setup["captures"]), 1)
                self.assertEqual(self._sender_calls(setup), 0)

    def test_result_manifest_records_reserved_outputs_without_binding_them_to_bundle(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        result = self._execute(setup)
        outputs = result.audit["evidence_outputs"]
        manifest_path = Path(outputs["manifest"])
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["result_audit"]["evidence_outputs"], outputs)
        self.assertNotIn("evidence_outputs", setup["bundle"].to_dict())
        self.assertNotIn(outputs["root"], json.dumps(setup["bundle"].to_dict()))

    def test_operation_bundle_rejects_p17_014_report_with_p17_012_baseline_substitution(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        wrong_baseline = setup["root"] / "p17-012-baseline"
        _write_archive(
            wrong_baseline,
            setup["preflight"].before_backup.directory.joinpath(
                setup["preflight"].before_backup.object_filename("0x8004:backup-blob")
            ).read_bytes(),
            self.now,
            fixed_state=setup["fixed_state"],
        )

        def substitute_baseline(value):
            artifact = value["artifacts"]["baseline_backup"]
            manifest = wrong_baseline / "manifest.json"
            artifact["path"] = str(wrong_baseline.resolve())
            artifact["sha256"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
            artifact["size_bytes"] = manifest.stat().st_size

        self._assert_bundle_rejected_before_runtime(
            setup,
            substitute_baseline,
            "p17-014-report-p17-012-baseline",
        )

    def test_operation_bundle_mutations_fail_before_detection_or_sender(self):
        mutations = (
            ("sealed-report-hash", lambda value: value["artifacts"]["sealed_report"].update(sha256="0" * 64)),
            ("sealed-report-path", lambda value: value["artifacts"]["sealed_report"].update(path=value["artifacts"]["template"]["path"])),
            ("baseline-hash", lambda value: value["artifacts"]["baseline_backup"].update(sha256="0" * 64)),
            ("catalog-hash", lambda value: value["artifacts"]["catalog"].update(sha256="0" * 64)),
            ("catalog-path", lambda value: value["artifacts"]["catalog"].update(path=value["artifacts"]["template"]["path"])),
            ("template-hash", lambda value: value["artifacts"]["template"].update(sha256="0" * 64)),
            ("template-path", lambda value: value["artifacts"]["template"].update(path=value["artifacts"]["capacity_response"]["path"])),
            ("capacity-hash", lambda value: value["artifacts"]["capacity_response"].update(sha256="0" * 64)),
            ("capacity-path", lambda value: value["artifacts"]["capacity_response"].update(path=value["artifacts"]["template"]["path"])),
            ("package-manifest-hash", lambda value: value["artifacts"]["package_manifest"].update(sha256="0" * 64)),
            ("package-manifest-path", lambda value: value["artifacts"]["package_manifest"].update(path=value["artifacts"]["catalog"]["path"])),
            ("selected-item", lambda value: value.update(selected_item_id="wrong-item")),
            ("target", lambda value: value.update(expected_folder_name="wrong-target")),
            ("timestamp", lambda value: value.update(new_record_timestamp_be32=1)),
            ("owner-phrase", lambda value: value.update(owner_approval_phrase="wrong approval")),
            ("confirmation-phrase", lambda value: value.update(confirmation_phrase="wrong confirmation")),
            ("confirmation-policy", lambda value: value.update(confirmation_policy="wrong-policy")),
            ("raw-state", lambda value: value.update(baseline_state_identity_sha256="0" * 64)),
            ("capacity-binding", lambda value: value.update(capacity_response_sha256="0" * 64)),
            ("candidate-audit", lambda value: value.update(candidate_audit_sha256="0" * 64)),
            ("authorization", lambda value: value.update(authorization_sha256="0" * 64)),
            ("post-state", lambda value: value.update(expected_post_operation_sha256="0" * 64)),
            ("candidate", lambda value: value.update(candidate_blob_sha256="0" * 64)),
            ("transaction", lambda value: value.update(transaction_sha256="0" * 64)),
            ("core-seal", lambda value: value.update(core_preflight_seal_sha256="0" * 64)),
            ("outer-seal", lambda value: value.update(preflight_seal_sha256="0" * 64)),
            ("library-binding", lambda value: value.update(library_binding_sha256="0" * 64)),
            ("package-child", lambda value: value["package_children"][0].update(source_sha256="0" * 64)),
            ("expected-post-state", lambda value: value["expected_post_operation"].update(mutation=True)),
        )
        for name, mutate in mutations:
            with self.subTest(name=name):
                setup = self._setup()
                self.addCleanup(setup["temporary"].cleanup)
                self._assert_bundle_rejected_before_runtime(setup, mutate, name)

    def test_operation_bundle_rejects_every_safety_policy_mutation_at_load(self):
        for name, mutate in (
            ("retry", lambda value: value["safety"].update(automatic_retry_allowed=True)),
            ("sender-count", lambda value: value["safety"].update(max_sender_calls=2)),
            ("request", lambda value: value["safety"].update(transaction_request="0x0024")),
            ("completion", lambda value: value["safety"].update(accepted_completion="0x0001")),
        ):
            with self.subTest(name=name):
                setup = self._setup()
                self.addCleanup(setup["temporary"].cleanup)
                path = self._bundle_json_with_mutation(setup, mutate, f"safety-{name}")
                with self.assertRaises(OperationBundleError):
                    load_operation_bundle(path, verify_artifacts=False)

    def test_operation_bundle_rejects_fixed_identity_and_policy_mutations_at_load(self):
        for name, mutate in (
            ("device", lambda value: value.update(device_identity=["0x054c", "0x001f"])),
            ("timestamp-policy", lambda value: value.update(timestamp_policy="legacy_global_rewrite")),
            ("endpoint", lambda value: value.update(bulk_out_endpoint=2)),
            ("child-order", lambda value: value["package_children"][0].update(order=1)),
            ("evidence-output-policy", lambda value: value["evidence_output_policy"].update(manifest_name="changed.json")),
        ):
            with self.subTest(name=name):
                setup = self._setup()
                self.addCleanup(setup["temporary"].cleanup)
                path = self._bundle_json_with_mutation(setup, mutate, f"fixed-{name}")
                with self.assertRaises(OperationBundleError):
                    load_operation_bundle(path, verify_artifacts=False)

    def test_operation_bundle_rejects_each_ordered_child_binding_before_runtime(self):
        child_mutations = (
            ("kind", lambda child: child.update(kind="bmp")),
            ("name", lambda child: child.update(name="changed")),
            ("target-path", lambda child: child.update(target_path="root\\changed.txt")),
            ("source-path", lambda child: child.update(source_path="/tmp/changed.txt")),
            ("source-archive-path", lambda child: child.update(source_archive_path="changed")),
            ("prepared-archive-path", lambda child: child.update(prepared_archive_path="changed")),
            ("source-hash", lambda child: child.update(source_sha256="0" * 64)),
            ("source-size", lambda child: child.update(source_bytes=999)),
            ("prepared-hash", lambda child: child.update(prepared_payload_sha256="0" * 64)),
            ("prepared-size", lambda child: child.update(prepared_payload_bytes=999)),
            ("package-root", lambda child: child.update(package_root="/tmp/changed-package")),
        )
        for name, mutate_child in child_mutations:
            with self.subTest(name=name):
                setup = self._setup()
                self.addCleanup(setup["temporary"].cleanup)

                def mutate(value, mutate_child=mutate_child):
                    mutate_child(value["package_children"][0])

                self._assert_bundle_rejected_before_runtime(setup, mutate, f"child-{name}")

    def test_operation_bundle_is_recursively_immutable(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaises(TypeError):
            setup["bundle"].package_children[0]["name"] = "changed"
        with self.assertRaises(TypeError):
            setup["bundle"].expected_post_operation["changed"] = True

    def test_operation_bundle_live_signature_has_no_manual_artifact_pairing(self):
        import inspect

        names = set(inspect.signature(execute_prepared_library_package_live).parameters)
        self.assertEqual(
            names & {
                "catalog",
                "selected_item_id",
                "backup_destination",
                "execution_template",
                "post_operation_destination",
                "evidence_manifest_destination",
                "bulk_out_endpoint",
            },
            set(),
        )


if __name__ == "__main__":
    unittest.main()
