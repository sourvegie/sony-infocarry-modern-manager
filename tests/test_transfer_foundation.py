import inspect
import json
import unittest
from pathlib import Path

from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.device_model_profile import (
    CapacityObservation,
    VNW_V10_PROFILE,
    VNW_V15_PROFILE,
)
from infocarry.device_info import RawInfoResponse
from infocarry.transfer_foundation import (
    Authorization,
    CandidateLibrary,
    PreparedItem,
    TransferFoundation,
    TransferFoundationError,
)


def _children():
    return (
        {
            "order": 0,
            "kind": "txt",
            "name": "01-introduction.txt",
            "path": "root\\Book\\01-introduction.txt",
            "source_sha256": "1" * 64,
            "prepared_payload_sha256": "2" * 64,
            "source_bytes": 12,
            "prepared_payload_bytes": 14,
        },
        {
            "order": 1,
            "kind": "bmp",
            "name": "02-page-01.bmp",
            "path": "root\\Book\\02-page-01.bmp",
            "source_sha256": "3" * 64,
            "prepared_payload_sha256": "4" * 64,
            "source_bytes": 10302,
            "prepared_payload_bytes": 10302,
        },
        {
            "order": 2,
            "kind": "txt",
            "name": "03-ending.txt",
            "path": "root\\Book\\03-ending.txt",
            "source_sha256": "5" * 64,
            "prepared_payload_sha256": "6" * 64,
            "source_bytes": 8,
            "prepared_payload_bytes": 10,
        },
    )


def _prepared_item():
    return PreparedItem("library-item-1", "a" * 64, "Book", _children())


def _capacity():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "infocarry_info_responses.json").read_text(
            encoding="utf-8"
        )
    )
    raw_response = bytes.fromhex(fixture["hardware"]["response_hex"])
    native_response = NativeCapacityResponse.from_hardware_response(
        RawInfoResponse(0x0019, "hardware", raw_response),
        device_identity=(0x054C, 0x001E),
    )
    native_evidence = native_response.bind_model_lengths(700, 800)
    return CapacityObservation(
        native_evidence=native_evidence,
        model_profile_id=VNW_V15_PROFILE.profile_id,
        capacity_response_sha256=native_evidence.raw_response_sha256,
        total_model_bytes=3_145_728,
        baseline_model_bytes=700,
        candidate_model_bytes=800,
        candidate_growth_bytes=100,
        remaining_growth_bytes=3_145_028,
        remaining_after_transfer_bytes=3_144_928,
    )


def _foundation():
    return TransferFoundation.from_prepared_items(
        (_prepared_item(),), device_model_profile=VNW_V15_PROFILE
    )


class TransferFoundationTests(unittest.TestCase):
    def test_facade_progression_is_hash_only_and_disabled(self):
        foundation = _foundation()
        report = foundation.to_dict()

        self.assertEqual(report["format"], "infocarry-transfer-foundation-v1")
        self.assertEqual(report["plan"]["selected_package_count"], 1)
        self.assertFalse(report["execute_once"]["enabled"])
        self.assertEqual(
            report["execute_once"]["disabled_reason"],
            "initial capability profile is defined but not live-enabled",
        )
        self.assertFalse(report["usb_accessed"])
        self.assertFalse(report["candidate"])
        self.assertFalse(report["authorization"])
        self.assertNotIn("candidate_bytes", inspect.getsource(TransferFoundation))

    def test_queue_item_is_explicitly_grouped_and_revalidated(self):
        item = PreparedItem.from_queue_item(
            {
                "item_id": "library-item-1",
                "prepared_artifact": {
                    "manifest_sha256": "a" * 64,
                    "contract": "infocarry-prepared-typed-media-package-v1",
                    "child_order": [child["name"] for child in _children()],
                    "ordered_children": list(_children()),
                },
                "destination": {
                    "paths": list(_prepared_item().destination_paths),
                    "folder_path": _prepared_item().destination_paths[0],
                    "child_path": _prepared_item().destination_paths[1],
                },
                "operation_type": "prepared_flat_typed_package",
            }
        )
        self.assertEqual(item.library_item_id, "library-item-1")
        self.assertEqual(item.destination_paths[-1], "root\\Book\\03-ending.txt")

    def test_candidate_and_authorization_must_match_plan(self):
        foundation = _foundation().attach_capacity(_capacity())
        candidate = CandidateLibrary(
            candidate_sha256="b" * 64,
            transaction_sha256="c" * 64,
            baseline_state_sha256="d" * 64,
            expected_post_paths=_prepared_item().destination_paths,
        )
        bound = foundation.attach_candidate(candidate)
        capacity = _capacity()
        authorization = Authorization(
            "b" * 64,
            "c" * 64,
            capacity.capacity_response_sha256,
            capacity,
        )
        bound = bound.attach_authorization(authorization)

        self.assertEqual(bound.candidate, candidate)
        self.assertEqual(bound.authorization, authorization)
        report = bound.to_dict()
        self.assertEqual(report["device_model_profile_id"], VNW_V15_PROFILE.profile_id)
        self.assertEqual(report["plan"]["capacity"]["total_model_bytes"], 3_145_728)
        self.assertEqual(
            report["authorization"]["capacity"]["remaining_growth_bytes"],
            3_145_028,
        )
        self.assertEqual(
            report["authorization"]["capacity"]["remaining_after_transfer_bytes"],
            3_144_928,
        )

        with self.assertRaises(TransferFoundationError):
            foundation.attach_authorization(authorization)
        with self.assertRaises(TransferFoundationError):
            bound.attach_authorization(
                Authorization(
                    "e" * 64,
                    "c" * 64,
                    capacity.capacity_response_sha256,
                    capacity,
                )
            )
        with self.assertRaises(TransferFoundationError):
            bound.attach_candidate(
                CandidateLibrary("b" * 64, "c" * 64, "d" * 64, ("root\\other",))
            )
        with self.assertRaises(TransferFoundationError):
            bound.attach_candidate(candidate)

    def test_authorization_cannot_omit_or_substitute_session_capacity(self):
        candidate = CandidateLibrary(
            candidate_sha256="b" * 64,
            transaction_sha256="c" * 64,
            baseline_state_sha256="d" * 64,
            expected_post_paths=_prepared_item().destination_paths,
        )
        no_capacity = _foundation().attach_candidate(candidate)
        with self.assertRaises(TransferFoundationError):
            no_capacity.attach_authorization(
                Authorization("b" * 64, "c" * 64, "e" * 64, _capacity())
            )

        with self.assertRaises(TransferFoundationError):
            _foundation().attach_capacity(_capacity()).attach_candidate(candidate).attach_authorization(
                Authorization("b" * 64, "c" * 64, "f" * 64, _capacity())
            )

    def test_multiple_packages_and_live_execution_are_rejected(self):
        item = _prepared_item()
        with self.assertRaises(TransferFoundationError):
            TransferFoundation.from_prepared_items(
                (item, item), device_model_profile=VNW_V15_PROFILE
            )
        with self.assertRaises(TransferFoundationError):
            TransferFoundation.from_prepared_items(
                (item,),
                profile=type("LiveProfile", (), {"live_enabled": True})(),
                device_model_profile=VNW_V15_PROFILE,
            )

        with self.assertRaises(TransferFoundationError):
            TransferFoundation.from_prepared_items(
                (item,), device_model_profile=VNW_V10_PROFILE
            )

    def test_explicit_model_profile_and_session_capacity_are_required(self):
        item = _prepared_item()
        with self.assertRaises(TransferFoundationError):
            TransferFoundation.from_prepared_items((item,))
        foundation = _foundation()
        with self.assertRaises(TransferFoundationError):
            foundation.attach_capacity(
                object()
            )

    def test_queue_item_requires_real_library_identity(self):
        item = {
            "operation_type": "prepared_flat_typed_package",
            "prepared_artifact": {
                "manifest_sha256": "a" * 64,
                "contract": "infocarry-prepared-typed-media-package-v1",
                "child_order": [child["name"] for child in _children()],
                "ordered_children": list(_children()),
            },
            "destination": {
                "paths": list(_prepared_item().destination_paths),
                "folder_path": _prepared_item().destination_paths[0],
                "child_path": _prepared_item().destination_paths[1],
            },
        }

        with self.assertRaises(TransferFoundationError):
            PreparedItem.from_queue_item(item)

    def test_prepared_children_are_immutable_after_revalidation(self):
        item = _prepared_item()

        with self.assertRaises(TypeError):
            item.children[0]["name"] = "changed.txt"

    def test_transfer_plan_cannot_disable_required_safety_gates(self):
        from infocarry.transfer_foundation import TransferPlan

        with self.assertRaises(TransferFoundationError):
            TransferPlan(
                profile_id="experimental-flat-root-folder-txt-bmp-v1",
                prepared_items=(_prepared_item(),),
                destination_paths=_prepared_item().destination_paths,
                fresh_backup_required=False,
            )

    def test_queue_item_destination_binding_is_exact(self):
        item = {
            "item_id": "library-item-1",
            "operation_type": "prepared_flat_typed_package",
            "prepared_artifact": {
                "manifest_sha256": "a" * 64,
                "contract": "infocarry-prepared-typed-media-package-v1",
                "child_order": [child["name"] for child in _children()],
                "ordered_children": list(_children()),
            },
            "destination": {
                "paths": list(_prepared_item().destination_paths[:-1])
                + ["root\\Book\\other.txt"],
                "folder_path": "root\\Book",
                "child_path": "root\\Book\\other.txt",
            },
        }

        with self.assertRaises(TransferFoundationError):
            PreparedItem.from_queue_item(item)

    def test_candidate_paths_must_be_immutable(self):
        with self.assertRaises(TransferFoundationError):
            CandidateLibrary(
                candidate_sha256="b" * 64,
                transaction_sha256="c" * 64,
                baseline_state_sha256="d" * 64,
                expected_post_paths=["root\\Book"],
            )


if __name__ == "__main__":
    unittest.main()
