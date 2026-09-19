from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

from infocarry.backup_format import parse_backup_blob
from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.capability_profile import (
    FOUR_LEAF_VALIDATION_PROFILE_ID,
    four_leaf_validation_profile,
)
from infocarry.device_info import RawInfoResponse
from infocarry.four_leaf_validation import (
    FOUR_LEAF_CHILD_KINDS,
    FOUR_LEAF_CHILD_NAMES,
    FOUR_LEAF_VALIDATION_TARGET,
    FourLeafValidationReadback,
)
from infocarry.library import LibraryCatalog
from infocarry.library_transfer_execution import (
    FRESH_AUXILIARY_STATE_POLICY,
    LibraryTransferOperationBinding,
)
from infocarry.prepared_library_package_bridge import (
    PreparedLibraryPackageBridgeError,
    authorize_prepared_library_package,
    build_prepared_library_package_candidate,
    run_prepared_library_package_fake_workflow,
)
from infocarry.prepared_library_package_live_adapter import (
    PreparedLibraryPackageLiveAdapterError,
    load_prepared_library_package_live_preflight,
    prepare_prepared_library_package_live_preflight,
)
from infocarry.experimental_library_transfer import (
    GuardedLibraryExecutionCoordinator,
    GuardedLibraryExecutionError,
)
from infocarry.prepared_library_package_operation_bundle import (
    PreparedLibraryPackageOperationBundle,
)
from infocarry.prepared_multi_package_workflow import PreparedMultiFakeTransport
from infocarry.prepared_media_package import (
    build_prepared_media_package,
    export_prepared_media_package,
)
from infocarry.indeterminate_write_lock import PersistentIndeterminateWriteLock
from infocarry.execution_claim_store import PersistentExecutionClaimStore
from infocarry.write_protocol import REQUEST_BEGIN_TRANSMIT, REQUEST_COMPLETION

import infocarry.prepared_library_package_bridge as bridge_module
import infocarry.prepared_package_multi_candidate as candidate_module

try:
    from test_new_txt import _write_archive
    from test_prepared_package_multi_candidate import _template_blobs, make_profile_bmp
    from test_prepared_library_package_live_adapter import _named_template_blob, _response
    from test_prepared_package_workflow import PackageWorkflowBackend
except ModuleNotFoundError:
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_package_multi_candidate import _template_blobs, make_profile_bmp
    from tests.test_prepared_library_package_live_adapter import _named_template_blob, _response
    from tests.test_prepared_package_workflow import PackageWorkflowBackend


OWNER_APPROVAL = "APPROVE P18-031 V15 FOUR-LEAF PHYSICAL VALIDATION 01"
CONFIRMATION = f"ADD {FOUR_LEAF_VALIDATION_TARGET} ONCE"


def _plan_for_setup(setup):
    candidate = setup["preflight"].candidate.audit_dict()
    binding = candidate["library_binding"]
    children = []
    for binding_child, candidate_child in zip(
        binding["ordered_children"], candidate["package"]["ordered_items"]
    ):
        children.append(
            {
                "order": candidate_child["order"],
                "kind": candidate_child["kind"],
                "name": binding_child["name"],
                "path": candidate_child["path"],
                "source_sha256": candidate_child["source_sha256"],
                "source_bytes": binding_child["source_bytes"],
                "prepared_payload_sha256": candidate_child["payload_sha256"],
                "prepared_payload_bytes": candidate_child["payload_length"],
            }
        )
    return {
        "format": "infocarry-library-transfer-plan-v1",
        "state": "previewed_offline",
        "usb_accessed": False,
        "device_change": "none",
        "selection": {
            "mode": "selected",
            "selected_item_ids": [setup["bundle"].selected_item_id],
        },
        "grouping": {"automatic_grouping": False, "overlap_status": "none"},
        "eligibility": {
            "offline_review_ready": True,
            "queue_ready": True,
            "device_candidate_eligible": False,
            "transfer_enabled": False,
        },
        "safety": {
            "source_mutated": False,
            "catalog_mutated": False,
            "candidate_constructed": False,
            "authorization_created": False,
            "transaction_constructed": False,
            "sender_called": False,
            "automatic_retry": False,
        },
        "items": [
            {
                "item_id": setup["bundle"].selected_item_id,
                "operation_type": "prepared_flat_typed_package",
                "execution_eligible": False,
                "prepared_artifact": {
                    "contract": "infocarry-prepared-typed-media-package-v1",
                    "manifest_sha256": candidate["package"]["prepared_manifest_sha256"],
                    "source_bytes": sum(child["source_bytes"] for child in children),
                    "prepared_payload_bytes": sum(
                        child["prepared_payload_bytes"] for child in children
                    ),
                    "ordered_children": children,
                },
                "destination": {"paths": candidate["package"]["paths"]},
                "conflicts": [],
                "queue_ready": True,
            }
        ],
    }


class P18031FourLeafExecutionTests(unittest.TestCase):
    now = datetime(2026, 9, 19, tzinfo=timezone.utc)

    def _setup(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        baseline_blob, _template_blob = _template_blobs()
        fixed_state = {
            command: b"\x00" * 64
            for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)
        }
        display_history = bytearray(64)
        display_history[0:4] = (1).to_bytes(4, "big")
        display_history[8:12] = (0x80).to_bytes(4, "big")
        display_history[60:] = b"HIST"
        fixed_state[0x001B] = bytes(display_history)
        bookmark = bytearray(64)
        bookmark_values = (0x80, 0xC00, 0, 0x14, 0xFFF101C5)
        bookmark[:20] = b"".join(
            value.to_bytes(4, "big") for value in bookmark_values
        )
        bookmark[40:] = b"B" * 24
        fixed_state[0x001F] = bytes(bookmark)
        files = []
        for filename, content in (
            ("01-introduction.txt", "Introduction\n"),
            ("03-ending.txt", "The End\n"),
            ("04-extra.txt", "Extra\n"),
        ):
            path = root / filename
            path.write_text(content, encoding="utf-8")
            files.append((path, filename))
        image = root / "02-page-01.bmp"
        image.write_bytes(make_profile_bmp())
        files.insert(1, (image, image.name))
        package = build_prepared_media_package(
            tuple(files), FOUR_LEAF_VALIDATION_TARGET
        )
        package_root = export_prepared_media_package(package, root / "package")
        catalog = LibraryCatalog(root / "catalog/library.json")
        item = catalog.import_prepared_package(package_root)
        template = parse_backup_blob(_named_template_blob())
        current = {"candidate": None}

        def capture(destination, **_kwargs):
            blob = (
                current["candidate"].candidate_blob
                if "after" in Path(destination).name
                else baseline_blob
            )
            _write_archive(destination, blob, self.now, fixed_state=fixed_state)

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

        binding = LibraryTransferOperationBinding(
            target_folder_name=FOUR_LEAF_VALIDATION_TARGET,
            owner_approval_phrase=OWNER_APPROVAL,
            confirmation_phrase=CONFIRMATION,
            profile_id=FOUR_LEAF_VALIDATION_PROFILE_ID,
        )
        preflight = prepare_prepared_library_package_live_preflight(
            catalog=catalog,
            selected_item_id=item.item_id,
            backup_destination=root / "before",
            template=template,
            new_record_timestamp_be32=0x6A958595,
            operation_binding=binding,
            detect_device=lambda: (0x054C, 0x001E),
            query_capacity=_response,
            capture=capture,
            preview_callback=lambda _audit: None,
            now=self.now,
            max_age_seconds=None,
        )
        current["candidate"] = preflight.candidate
        report_path = root / "sealed-preflight.json"
        report_path.write_text(
            json.dumps(preflight.to_dict(), ensure_ascii=True, sort_keys=True) + "\n",
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
            operation_id=binding.operation_id,
        )
        evidence_namespace = root / "evidence"
        evidence_namespace.mkdir()
        return {
            "temporary": temporary,
            "root": root,
            "catalog": catalog,
            "item": item,
            "template": template,
            "preflight": preflight,
            "bundle": bundle,
            "current": current,
            "capture": capture,
            "binding": binding,
            "evidence": evidence_namespace,
            "report_path": report_path,
            "claims": PersistentExecutionClaimStore(
                root / "installation-state/execution-claims.sqlite3"
            ),
            "lock": PersistentIndeterminateWriteLock(
                root / "installation-state/indeterminate-write-lock.json"
            ),
        }

    def test_exact_four_leaf_uses_shared_one_shot_runner_and_verifier(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        result = GuardedLibraryExecutionCoordinator(
            operation_binding=setup["binding"],
            indeterminate_write_lock=setup["lock"],
            execution_claim_store=setup["claims"],
        ).execute(
            setup["bundle"],
            plan_report=_plan_for_setup(setup),
            confirmation_interaction=lambda _review: CONFIRMATION,
            detect_device=lambda: (0x054C, 0x001E),
            query_capacity=_response,
            backend=PackageWorkflowBackend(),
            capture=setup["capture"],
            evidence_namespace=setup["evidence"],
            now=self.now,
            max_age_seconds=None,
        )
        self.assertEqual(result.audit["state"], "readback_verified")
        self.assertEqual(
            result.runner_result.audit["profile"], FOUR_LEAF_VALIDATION_PROFILE_ID
        )
        self.assertIsInstance(result.verification, FourLeafValidationReadback)
        self.assertEqual(result.verification.to_dict()["validation_profile_id"], FOUR_LEAF_VALIDATION_PROFILE_ID)
        self.assertEqual(result.runner_result.audit["workflow"]["sender_calls"], 1)
        self.assertEqual(
            result.runner_result.audit["workflow"]["operation_sequence"].count(
                "single_0x101b_transaction"
            ),
            1,
        )

    def test_four_leaf_reload_requires_typed_operation_binding(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as raised:
            load_prepared_library_package_live_preflight(
                setup["report_path"],
                catalog=setup["catalog"],
                selected_item_id=setup["item"].item_id,
                backup=setup["preflight"].before_backup,
                template=setup["template"],
                capacity_response=setup["preflight"].capacity_response,
            )
        self.assertEqual(raised.exception.stage, "preflight_load")
        self.assertIn("typed operation binding", str(raised.exception))

    def test_four_leaf_fake_workflow_preserves_profile_builder_and_readback(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        result = run_prepared_library_package_fake_workflow(
            setup["preflight"].core,
            catalog=setup["catalog"],
            selected_item_id=setup["item"].item_id,
            backup_destination=setup["root"] / "fake-before",
            post_operation_destination=setup["root"] / "fake-after",
            capture=setup["capture"],
            transport=PreparedMultiFakeTransport(lambda *_args, **_kwargs: 0),
            detect_device=lambda: (0x054C, 0x001E),
            query_capacity=_response,
            now=self.now,
            max_age_seconds=None,
        )
        self.assertIsInstance(result.verification, FourLeafValidationReadback)
        self.assertEqual(
            result.verification.to_dict()["validation_profile_id"],
            FOUR_LEAF_VALIDATION_PROFILE_ID,
        )
        self.assertEqual(
            result.authorization.to_dict()["validation_profile"]["profile_id"],
            FOUR_LEAF_VALIDATION_PROFILE_ID,
        )

    def test_guarded_four_leaf_plan_mutation_stops_before_confirmation_or_sender(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        plan = _plan_for_setup(setup)
        plan["items"][0]["destination"]["paths"][-1] = (
            "root\\other\\04-extra.txt"
        )
        confirmations = []
        backend = PackageWorkflowBackend()
        with self.assertRaises(GuardedLibraryExecutionError) as raised:
            GuardedLibraryExecutionCoordinator(
                operation_binding=setup["binding"],
                indeterminate_write_lock=setup["lock"],
                execution_claim_store=setup["claims"],
            ).execute(
                setup["bundle"],
                plan_report=plan,
                confirmation_interaction=lambda review: confirmations.append(review)
                or CONFIRMATION,
                detect_device=lambda: self.fail("device detection must not be reached"),
                query_capacity=lambda: self.fail("capacity must not be reached"),
                backend=backend,
                capture=lambda *_args, **_kwargs: self.fail(
                    "backup must not be reached"
                ),
                evidence_namespace=setup["evidence"],
            )
        self.assertEqual(raised.exception.stage, "eligibility")
        self.assertEqual(confirmations, [])
        self.assertEqual(
            sum(
                1
                for call in backend.calls
                if call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
            ),
            0,
        )

    def test_four_leaf_ambiguous_completion_is_terminal_and_not_retried(self):
        class MissingCompletionBackend(PackageWorkflowBackend):
            def control_in(self, request_type, request, value, index, length, timeout_ms):
                if request == REQUEST_COMPLETION:
                    raise OSError("simulated missing completion")
                return super().control_in(
                    request_type, request, value, index, length, timeout_ms
                )

        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        backend = MissingCompletionBackend()
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as raised:
            GuardedLibraryExecutionCoordinator(
                operation_binding=setup["binding"],
                indeterminate_write_lock=setup["lock"],
                execution_claim_store=setup["claims"],
            ).execute(
                setup["bundle"],
                plan_report=_plan_for_setup(setup),
                confirmation_interaction=lambda _review: CONFIRMATION,
                detect_device=lambda: (0x054C, 0x001E),
                query_capacity=_response,
                backend=backend,
                capture=setup["capture"],
                evidence_namespace=setup["evidence"],
                now=self.now,
                max_age_seconds=None,
            )
        self.assertEqual(
            raised.exception.state, "indeterminate_after_transaction_start"
        )
        self.assertFalse(raised.exception.automatic_retry_allowed)
        self.assertEqual(
            sum(
                1
                for call in backend.calls
                if call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
            ),
            1,
        )

    def test_guarded_four_leaf_operation_id_mutation_fails_before_callbacks(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        tampered_bundle = replace(
            setup["bundle"], operation_id="vnw-v15-library-operation-tampered"
        )
        with self.assertRaises(GuardedLibraryExecutionError) as raised:
            GuardedLibraryExecutionCoordinator(
                operation_binding=setup["binding"],
                indeterminate_write_lock=setup["lock"],
                execution_claim_store=setup["claims"],
            ).execute(
                tampered_bundle,
                plan_report=_plan_for_setup(setup),
                confirmation_interaction=lambda _review: CONFIRMATION,
                detect_device=lambda: self.fail("device detection must not be reached"),
                query_capacity=lambda: self.fail("capacity must not be reached"),
                backend=PackageWorkflowBackend(),
                capture=lambda *_args, **_kwargs: self.fail(
                    "backup must not be reached"
                ),
                evidence_namespace=setup["evidence"],
            )
        self.assertEqual(raised.exception.stage, "operation_identity")

    def test_four_leaf_binding_and_authorization_bind_profile_hash_and_artifact(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        candidate = setup["preflight"].candidate
        self.assertEqual(tuple(candidate.core.package.items[i].kind for i in range(4)), FOUR_LEAF_CHILD_KINDS)
        self.assertEqual(tuple(item.name for item in candidate.core.package.items), FOUR_LEAF_CHILD_NAMES)
        self.assertEqual(
            candidate.library_binding["profile_sha256"],
            four_leaf_validation_profile().sha256,
        )
        authorization = authorize_prepared_library_package(
            candidate,
            confirmation=CONFIRMATION,
            confirmation_policy=setup["binding"].confirmation_policy,
        )
        self.assertEqual(authorization.profile_id, FOUR_LEAF_VALIDATION_PROFILE_ID)
        self.assertEqual(
            authorization.profile_sha256, four_leaf_validation_profile().sha256
        )

    def test_four_leaf_reuses_canonical_auxiliary_state_policy(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        self.assertEqual(
            setup["binding"].fixed_state_policy,
            FRESH_AUXILIARY_STATE_POLICY,
        )
        self.assertEqual(
            setup["preflight"].candidate.core.audit_dict()["policy"]["fixed_state"],
            FRESH_AUXILIARY_STATE_POLICY,
        )
        with self.assertRaisesRegex(ValueError, "auxiliary-state policy"):
            LibraryTransferOperationBinding(
                target_folder_name=FOUR_LEAF_VALIDATION_TARGET,
                owner_approval_phrase=OWNER_APPROVAL,
                confirmation_phrase=CONFIRMATION,
                profile_id=FOUR_LEAF_VALIDATION_PROFILE_ID,
                fixed_state_policy="capture7_exact_all_zero_fixed_state",
            )

    def test_capture7_policy_stale_bundle_stops_before_any_callback(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        stale_bundle = replace(
            setup["bundle"],
            fixed_state_policy="capture7_exact_all_zero_fixed_state",
        )
        with self.assertRaises(GuardedLibraryExecutionError) as raised:
            GuardedLibraryExecutionCoordinator(
                operation_binding=setup["binding"],
                indeterminate_write_lock=setup["lock"],
                execution_claim_store=setup["claims"],
            ).execute(
                stale_bundle,
                plan_report=_plan_for_setup(setup),
                confirmation_interaction=lambda _review: self.fail(
                    "stale policy must stop before confirmation"
                ),
                detect_device=lambda: self.fail("stale policy must stop before device access"),
                query_capacity=lambda: self.fail("stale policy must stop before capacity"),
                backend=PackageWorkflowBackend(),
                capture=lambda *_args, **_kwargs: self.fail(
                    "stale policy must stop before backup"
                ),
                evidence_namespace=setup["evidence"],
            )
        self.assertEqual(raised.exception.stage, "operation_identity")

    def test_wrong_profile_hash_and_non_exact_shapes_fail_closed(self):
        setup = self._setup()
        self.addCleanup(setup["temporary"].cleanup)
        candidate = setup["preflight"].candidate
        tampered_binding = dict(candidate.library_binding)
        tampered_binding["profile_sha256"] = "0" * 64
        with self.assertRaises(PreparedLibraryPackageBridgeError):
            authorize_prepared_library_package(
                type(candidate)(candidate.core, tampered_binding),
                confirmation=CONFIRMATION,
                confirmation_policy=setup["binding"].confirmation_policy,
            )

        extra5 = setup["root"] / "05-extra.txt"
        extra5.write_text("Fifth\n", encoding="utf-8")
        five = build_prepared_media_package(
            (
                (setup["root"] / "01-introduction.txt", "01-introduction.txt"),
                (setup["root"] / "02-page-01.bmp", "02-page-01.bmp"),
                (setup["root"] / "03-ending.txt", "03-ending.txt"),
                (setup["root"] / "04-extra.txt", "04-extra.txt"),
                (extra5, "05-extra.txt"),
            ),
            FOUR_LEAF_VALIDATION_TARGET,
        )
        five_root = export_prepared_media_package(five, setup["root"] / "five-package")
        five_catalog = LibraryCatalog(setup["root"] / "five-catalog/library.json")
        five_item = five_catalog.import_prepared_package(five_root)
        with self.assertRaises(PreparedLibraryPackageBridgeError):
            build_prepared_library_package_candidate(
                five_catalog,
                five_item.item_id,
                setup["preflight"].before_backup,
                setup["template"],
                new_record_timestamp_be32=0x6A958595,
                native_capacity_response=_response(),
                profile_id=FOUR_LEAF_VALIDATION_PROFILE_ID,
            )


if __name__ == "__main__":
    unittest.main()
