from datetime import datetime, timezone
from dataclasses import replace
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
from infocarry.prepared_library_package_bridge import (
    P17_003_CONFIRMATION_PHRASE,
    P17_003_REVIEWED_TEMPLATE_BLOB_SHA256,
    P17_003_TEMPLATE_FOLDER_PATH,
    P17_003_TEMPLATE_ITEM_PATHS,
    PreparedLibraryPackageAuthorization,
    PreparedLibraryPackageBridgeError,
    PreparedLibraryPackageCandidate,
    authorize_prepared_library_package,
    build_prepared_library_package_candidate,
    prepare_prepared_library_package_preflight,
    run_prepared_library_package_fake_workflow,
)
import infocarry.prepared_library_package_bridge as bridge_module
import infocarry.prepared_package_multi_candidate as candidate_module
from infocarry.prepared_media_package import (
    build_prepared_media_package,
    export_prepared_media_package,
)
from infocarry.prepared_multi_package_workflow import (
    PreparedMultiFakeTransport,
    PreparedMultiPackageWorkflowError,
)
from infocarry.write_gate import verify_fresh_backup

try:
    from test_new_txt import _write_archive
    from test_prepared_package_multi_candidate import _template_blobs, make_profile_bmp
except ModuleNotFoundError:
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_package_multi_candidate import _template_blobs, make_profile_bmp


def _native_named_template_blob() -> bytes:
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


class PreparedLibraryPackageBridgeTests(unittest.TestCase):
    now = datetime(2026, 8, 31, tzinfo=timezone.utc)

    def _setup(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        intro = root / "intro.txt"
        image = root / "page.bmp"
        ending = root / "ending.txt"
        intro.write_text("Introduction\n日本語\n", encoding="utf-8")
        image.write_bytes(make_profile_bmp())
        ending.write_text("The End\n", encoding="utf-8")
        package = build_prepared_media_package(
            (
                (intro, "01-introduction.txt"),
                (image, "02-page-01.bmp"),
                (ending, "03-ending.txt"),
            ),
            "IC_P17_LIBRARY_20260831_01",
        )
        package_root = export_prepared_media_package(package, root / "package")
        catalog = LibraryCatalog(root / "catalog/library.json")
        item = catalog.import_prepared_package(package_root)

        baseline_blob, _template_blob = _template_blobs()
        fixed_state = {
            command: b"\x00" * 64
            for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)
        }
        before_path = _write_archive(
            root / "before",
            baseline_blob,
            self.now,
            fixed_state=fixed_state,
        )
        backup = verify_fresh_backup(before_path, now=self.now, max_age_seconds=None)
        template = parse_backup_blob(_native_named_template_blob())
        # The repository test uses a compact synthetic native fixture.  Bind
        # that fixture as the reviewed-template stand-in for this test process;
        # production callers must match the committed P16-001 native hash.
        template_patcher = patch.object(
            bridge_module,
            "P17_003_REVIEWED_TEMPLATE_BLOB_SHA256",
            hashlib.sha256(template.data).hexdigest(),
        )
        template_patcher.start()
        self.addCleanup(template_patcher.stop)
        subset_policy_patcher = patch.object(
            candidate_module,
            "REVIEWED_TEMPLATE_SUBSET_POLICY_SHA256",
            hashlib.sha256(template.data).hexdigest(),
        )
        subset_policy_patcher.start()
        self.addCleanup(subset_policy_patcher.stop)
        candidate = build_prepared_library_package_candidate(
            catalog,
            item.item_id,
            backup,
            template,
            new_record_timestamp_be32=0x6A942500,
            native_capacity_response=_response(),
        )
        preflight = prepare_prepared_library_package_preflight(
            catalog,
            item.item_id,
            backup,
            template,
            new_record_timestamp_be32=0x6A942500,
            native_capacity_response=_response(),
        )
        return {
            "temporary": temporary,
            "root": root,
            "catalog": catalog,
            "item": item,
            "package_root": package_root,
            "backup": backup,
            "template": template,
            "candidate": candidate,
            "preflight": preflight,
            "baseline_blob": baseline_blob,
            "fixed_state": fixed_state,
        }

    def test_selected_package_is_one_exact_hash_bound_candidate(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        candidate = setup["candidate"]
        self.assertIsInstance(candidate, PreparedLibraryPackageCandidate)
        self.assertEqual(
            [child["kind"] for child in candidate.library_binding["ordered_children"]],
            ["txt", "bmp", "txt"],
        )
        self.assertEqual(
            [child["order"] for child in candidate.library_binding["ordered_children"]],
            [0, 1, 2],
        )
        self.assertEqual(
            candidate.library_binding["manifest_sha256"],
            setup["item"].package.manifest_sha256,
        )
        self.assertEqual(
            candidate.library_binding["catalog_sha256"],
            hashlib.sha256(
                json.dumps(
                    setup["catalog"].to_dict(),
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        )
        self.assertEqual(
            candidate.audit_dict()["candidate"]["blob_sha256"],
            candidate.candidate_blob_sha256,
        )
        self.assertFalse(candidate.audit_dict()["bridge"]["hardware_accessed"])
        authorization = authorize_prepared_library_package(
            candidate,
            confirmation=P17_003_CONFIRMATION_PHRASE,
        )
        authorization.require_same_candidate(candidate)
        self.assertEqual(
            authorization.library_binding_sha256,
            hashlib.sha256(
                json.dumps(
                    candidate.library_binding,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
        )

    def test_preflight_is_hash_only_sealed_and_offline(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        preflight = setup["preflight"]
        preflight.verify_seal()
        report = preflight.to_dict()
        self.assertEqual(report["state"], "ready_for_hardware_test_host_only")
        self.assertFalse(report["read_only_hardware_accessed"])
        self.assertFalse(report["hardware_write_performed"])
        self.assertFalse(report["hardware_transaction_performed"])
        self.assertFalse(report["normal_gui_cli_transfer_exposed"])
        serialized = json.dumps(report)
        self.assertNotIn('"candidate_blob":', serialized)
        self.assertNotIn('"candidate_bytes":', serialized)
        self.assertEqual(set(preflight.candidate.library_binding["ordered_children"][0]), {
            "order",
            "kind",
            "name",
            "target_path",
            "source_path",
            "source_archive_path",
            "prepared_archive_path",
            "source_sha256",
            "source_bytes",
            "prepared_payload_sha256",
            "prepared_payload_bytes",
            "package_root",
        })

    def test_plain_library_item_and_manifest_drift_fail_closed(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        plain = setup["root"] / "plain.txt"
        plain.write_text("plain\n", encoding="utf-8")
        plain_item = setup["catalog"].import_file(plain)
        with self.assertRaisesRegex(PreparedLibraryPackageBridgeError, "explicitly imported"):
            build_prepared_library_package_candidate(
                setup["catalog"],
                plain_item.item_id,
                setup["backup"],
                setup["template"],
                new_record_timestamp_be32=0x6A942500,
                native_capacity_response=_response(),
            )

        manifest = json.loads(
            (setup["package_root"] / "manifest.json").read_text(encoding="utf-8")
        )
        manifest["notice"] = "changed"
        (setup["package_root"] / "manifest.json").write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(PreparedLibraryPackageBridgeError, "manifest revalidation"):
            build_prepared_library_package_candidate(
                setup["catalog"],
                setup["item"].item_id,
                setup["backup"],
                setup["template"],
                new_record_timestamp_be32=0x6A942500,
                native_capacity_response=_response(),
            )

    def test_authorization_rejects_library_binding_tampering(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        candidate = setup["candidate"]
        altered = dict(candidate.library_binding)
        altered["catalog_item_id"] = "different"
        altered_candidate = replace_candidate_binding(candidate, altered)
        authorization = authorize_prepared_library_package(
            candidate,
            confirmation=P17_003_CONFIRMATION_PHRASE,
        )
        with self.assertRaisesRegex(PreparedLibraryPackageBridgeError, "Library .*binding"):
            authorization.require_same_candidate(altered_candidate)
        with self.assertRaises(PreparedLibraryPackageBridgeError):
            PreparedLibraryPackageAuthorization(
                authorization.core,
                authorization.library_binding,
                "0" * 64,
            )

        altered_top_level = dict(candidate.library_binding)
        altered_top_level["catalog_item_id"] = "different-top-level-only"
        altered_top_level_candidate = PreparedLibraryPackageCandidate(
            candidate.core,
            altered_top_level,
        )
        with self.assertRaisesRegex(
            PreparedLibraryPackageBridgeError,
            "top-level binding",
        ):
            authorization.require_same_candidate(altered_top_level_candidate)

        split_binding = dict(candidate.library_binding)
        split_binding["catalog_item_id"] = "inconsistent-before-authorization"
        with self.assertRaisesRegex(
            PreparedLibraryPackageBridgeError,
            "bindings are inconsistent",
        ):
            authorize_prepared_library_package(
                PreparedLibraryPackageCandidate(candidate.core, split_binding),
                confirmation=P17_003_CONFIRMATION_PHRASE,
            )

    def test_catalog_source_binding_must_match_verified_manifest(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        altered_item = replace(setup["item"], source_sha256="0" * 64)
        setup["catalog"]._items[altered_item.item_id] = altered_item
        with self.assertRaisesRegex(
            PreparedLibraryPackageBridgeError,
            "source/manifest binding",
        ):
            build_prepared_library_package_candidate(
                setup["catalog"],
                altered_item.item_id,
                setup["backup"],
                setup["template"],
                new_record_timestamp_be32=0x6A942500,
                native_capacity_response=_response(),
            )

    def test_reviewed_template_bytes_are_required(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        altered = bytearray(setup["template"].data)
        bmp_offset = next(
            offset
            for offset, path in setup["template"].paths.items()
            if path == P17_003_TEMPLATE_ITEM_PATHS["bmp"]
        )
        record = setup["template"].record_at(bmp_offset)
        prefix_offset = setup["template"].header.content_start + record.field_04_be32
        altered[prefix_offset] ^= 0x01
        altered[0x1C:0x20] = b"\x00" * 4
        altered[0x1C:0x20] = calculate_backup_checksum(bytes(altered)).to_bytes(4, "big")
        altered_template = parse_backup_blob(bytes(altered))
        with self.assertRaisesRegex(
            PreparedLibraryPackageBridgeError,
            "template bytes",
        ):
            build_prepared_library_package_candidate(
                setup["catalog"],
                setup["item"].item_id,
                setup["backup"],
                altered_template,
                new_record_timestamp_be32=0x6A942500,
                native_capacity_response=_response(),
            )

    def test_preflight_report_is_immutable_and_seal_remains_authoritative(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaises(TypeError):
            setup["preflight"].audit["state"] = "tampered"
        setup["preflight"].verify_seal()
        report = setup["preflight"].to_dict()
        report["state"] = "tampered-detached-view"
        self.assertEqual(
            setup["preflight"].to_dict()["state"],
            "ready_for_hardware_test_host_only",
        )
        forged = replace(setup["preflight"], audit={"state": "forged-review-report"})
        with self.assertRaisesRegex(PreparedLibraryPackageBridgeError, "report seal"):
            forged.verify_seal()

    def test_reviewed_template_digest_is_pinned_without_fixture_override(self):
        self.assertEqual(
            P17_003_REVIEWED_TEMPLATE_BLOB_SHA256,
            "6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b",
        )

    def test_profile_order_template_and_destination_conflicts_fail_closed(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        conflict_path = _write_archive(
            setup["root"] / "conflict",
            setup["candidate"].candidate_blob,
            self.now,
            fixed_state=setup["fixed_state"],
        )
        conflict_backup = verify_fresh_backup(
            conflict_path,
            now=self.now,
            max_age_seconds=None,
        )
        with self.assertRaisesRegex(PreparedLibraryPackageBridgeError, "destination path"):
            build_prepared_library_package_candidate(
                setup["catalog"],
                setup["item"].item_id,
                conflict_backup,
                setup["template"],
                new_record_timestamp_be32=0x6A942500,
                native_capacity_response=_response(),
            )

        bad_manifest = json.loads(
            (setup["package_root"] / "manifest.json").read_text(encoding="utf-8")
        )
        bad_manifest["items"][1]["order"] = 0
        unsigned = dict(bad_manifest)
        unsigned.pop("prepared_manifest_sha256")
        bad_manifest["prepared_manifest_sha256"] = hashlib.sha256(
            json.dumps(
                unsigned,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        (setup["package_root"] / "manifest.json").write_text(
            json.dumps(bad_manifest),
            encoding="utf-8",
        )
        with self.assertRaises(PreparedLibraryPackageBridgeError):
            build_prepared_library_package_candidate(
                setup["catalog"],
                setup["item"].item_id,
                setup["backup"],
                setup["template"],
                new_record_timestamp_be32=0x6A942500,
                native_capacity_response=_response(),
            )

    def test_fake_workflow_revalidates_library_and_completes_once(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        current = {"blob": setup["baseline_blob"], "fixed": setup["fixed_state"]}

        def capture(destination, **_kwargs):
            _write_archive(
                destination,
                current["blob"],
                self.now,
                fixed_state=current["fixed"],
            )

        def send(transaction, _authorization, **_kwargs):
            current["blob"] = transaction.ranges[4] + transaction.ranges[7]
            current["fixed"] = {
                0x001B: transaction.ranges[0][0x00:0x40],
                0x001C: transaction.ranges[0][0x40:0x80],
                0x001D: transaction.ranges[0][0x80:0xC0],
                0x001E: transaction.ranges[0][0xC0:0x100],
                0x001F: transaction.ranges[1],
            }
            return 0

        result = run_prepared_library_package_fake_workflow(
            setup["preflight"],
            catalog=setup["catalog"],
            selected_item_id=setup["item"].item_id,
            backup_destination=setup["root"] / "fake-before",
            post_operation_destination=setup["root"] / "fake-after",
            capture=capture,
            transport=PreparedMultiFakeTransport(send),
            detect_device=lambda: (0x054C, 0x001E),
            query_capacity=_response,
            now=self.now,
            max_age_seconds=None,
        )
        self.assertEqual(result.completion, 0)
        self.assertTrue(result.verification.success)
        self.assertEqual(result.audit["bridge"]["format"], "infocarry-p17-003-library-package-bridge-v1")
        self.assertEqual(result.candidate.library_binding, setup["candidate"].library_binding)

    def test_fake_workflow_cancellation_is_before_send_and_drift_is_terminal(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        calls = []
        transport = PreparedMultiFakeTransport(
            lambda *_args, **_kwargs: calls.append(True) or 0
        )

        def capture(destination, **_kwargs):
            _write_archive(
                destination,
                setup["baseline_blob"],
                self.now,
                fixed_state=setup["fixed_state"],
            )

        with self.assertRaisesRegex(PreparedMultiPackageWorkflowError, "cancelled"):
            run_prepared_library_package_fake_workflow(
                setup["preflight"],
                catalog=setup["catalog"],
                selected_item_id=setup["item"].item_id,
                backup_destination=setup["root"] / "cancel-before",
                post_operation_destination=setup["root"] / "cancel-after",
                capture=capture,
                transport=transport,
                detect_device=lambda: (0x054C, 0x001E),
                query_capacity=_response,
                cancelled=lambda: True,
                now=self.now,
                max_age_seconds=None,
            )
        self.assertEqual(calls, [])

        source = setup["package_root"] / "source/0001_intro.txt"
        source.write_bytes(source.read_bytes() + b"drift")
        with self.assertRaisesRegex(PreparedLibraryPackageBridgeError, "manifest revalidation"):
            run_prepared_library_package_fake_workflow(
                setup["preflight"],
                catalog=setup["catalog"],
                selected_item_id=setup["item"].item_id,
                backup_destination=setup["root"] / "drift-before",
                post_operation_destination=setup["root"] / "drift-after",
                capture=capture,
                transport=PreparedMultiFakeTransport(lambda *_args, **_kwargs: 0),
                detect_device=lambda: (0x054C, 0x001E),
                query_capacity=_response,
                now=self.now,
                max_age_seconds=None,
            )

    def test_bridge_is_not_in_normal_gui_or_cli_import_graph(self):
        source_root = Path(__file__).parents[1] / "src/infocarry"
        for filename in ("cli.py", "desktop.py", "desktop_ttk.py"):
            self.assertNotIn(
                "prepared_library_package_bridge",
                (source_root / filename).read_text(encoding="utf-8"),
            )


def replace_candidate_binding(candidate, binding):
    altered_audit = dict(candidate.core.audit_dict())
    altered_audit["library_binding"] = binding
    return PreparedLibraryPackageCandidate(
        replace(candidate.core, audit=altered_audit),
        binding,
    )


if __name__ == "__main__":
    unittest.main()
