import inspect
import unittest

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


class TransferFoundationTests(unittest.TestCase):
    def test_facade_progression_is_hash_only_and_disabled(self):
        foundation = TransferFoundation.from_prepared_items((_prepared_item(),))
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
        foundation = TransferFoundation.from_prepared_items((_prepared_item(),))
        candidate = CandidateLibrary(
            candidate_sha256="b" * 64,
            transaction_sha256="c" * 64,
            baseline_state_sha256="d" * 64,
            expected_post_paths=_prepared_item().destination_paths,
        )
        bound = foundation.attach_candidate(candidate)
        authorization = Authorization("b" * 64, "c" * 64)
        bound = bound.attach_authorization(authorization)

        self.assertEqual(bound.candidate, candidate)
        self.assertEqual(bound.authorization, authorization)

        with self.assertRaises(TransferFoundationError):
            foundation.attach_authorization(authorization)
        with self.assertRaises(TransferFoundationError):
            bound.attach_authorization(Authorization("e" * 64, "c" * 64))
        with self.assertRaises(TransferFoundationError):
            bound.attach_candidate(
                CandidateLibrary("b" * 64, "c" * 64, "d" * 64, ("root\\other",))
            )
        with self.assertRaises(TransferFoundationError):
            bound.attach_candidate(candidate)

    def test_multiple_packages_and_live_execution_are_rejected(self):
        item = _prepared_item()
        with self.assertRaises(TransferFoundationError):
            TransferFoundation.from_prepared_items((item, item))
        with self.assertRaises(TransferFoundationError):
            TransferFoundation.from_prepared_items(
                (item,), profile=type("LiveProfile", (), {"live_enabled": True})()
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
