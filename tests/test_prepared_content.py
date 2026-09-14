import copy
import unittest

from infocarry.capability_profile import HIERARCHICAL_OFFLINE_PROFILE_ID, hierarchical_offline_capability_profile
from infocarry.library_transfer_readiness import build_library_transfer_readiness
from infocarry.prepared_content import (
    EMPTY_SHA256,
    PREPARED_CONTENT_ARTIFACT_FORMAT,
    PreparedContentArtifact,
    PreparedContentChild,
    PreparedContentError,
)


def _child(order, kind, name, payload, *, root="Book", parent=None):
    parent_path = f"root\\{root}" if parent is None else f"root\\{root}\\{parent}"
    return PreparedContentChild(
        order=order,
        kind=kind,
        name=name,
        path=f"{parent_path}\\{name}",
        payload_sha256=payload,
        payload_bytes=0 if kind == "folder" else 10 + order,
        payload_path=None if kind == "folder" else f"prepared/{root}/{name}",
        source_sha256=EMPTY_SHA256 if kind == "folder" else payload,
        source_bytes=0 if kind == "folder" else 10 + order,
    )


def _exact_children():
    return (
        _child(0, "txt", "01-introduction.txt", "a" * 64),
        _child(1, "bmp", "02-page-01.bmp", "b" * 64),
        _child(2, "txt", "03-ending.txt", "c" * 64),
    )


def _readiness_plan(artifact, *, destination_paths=None):
    children = artifact.to_legacy_children()
    paths = destination_paths or [artifact.root_path, *(child["path"] for child in children)]
    return {
        "format": "infocarry-library-transfer-plan-v1",
        "state": "previewed_offline",
        "usb_accessed": False,
        "device_change": "none",
        "selection": {"mode": "selected", "selected_item_ids": ["item-1"]},
        "baseline": {"available": False},
        "grouping": {"automatic_grouping": False, "overlap_status": "none", "overlap_paths": []},
        "items": [{
            "item_id": "item-1",
            "operation_type": "prepared_flat_typed_package",
            "execution_eligible": False,
            "prepared_artifact": {
                "contract": "infocarry-prepared-typed-media-package-v1",
                "manifest_sha256": "d" * 64,
                "source_bytes": sum(child.source_bytes for child in artifact.children),
                "prepared_payload_bytes": artifact.aggregate_size,
                "canonical": artifact.to_dict(),
                "artifact_identity": artifact.artifact_identity,
                "root_name": artifact.root_name,
                "aggregate_size": artifact.aggregate_size,
                "ordered_children": children,
            },
            "destination": {"paths": paths},
            "conflicts": [],
            "capacity": {
                "status": "not_evaluated_without_verified_backup",
                "baseline_model_bytes": None,
                "available_bytes": None,
                "lower_bound_bytes": 100,
                "exact_growth_known": False,
            },
            "queue_ready": False,
            "reasons": ["verified device backup is required for destination and capacity review"],
        }],
        "eligibility": {
            "offline_review_ready": True,
            "queue_ready": False,
            "device_candidate_eligible": False,
            "transfer_enabled": False,
            "reasons": ["verified device backup is required for destination and capacity review"],
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
    }


class PreparedContentArtifactTests(unittest.TestCase):
    def test_identity_is_deterministic_and_child_order_is_preserved(self):
        artifact = PreparedContentArtifact("Book", _exact_children(), profile_id="typed-media")
        repeat = PreparedContentArtifact("Book", _exact_children(), profile_id="typed-media")

        self.assertEqual(artifact.artifact_identity, repeat.artifact_identity)
        self.assertEqual(
            [child.name for child in artifact.children],
            ["01-introduction.txt", "02-page-01.bmp", "03-ending.txt"],
        )
        self.assertEqual(artifact.aggregate_size, 33)
        self.assertEqual(artifact.to_dict()["format"], PREPARED_CONTENT_ARTIFACT_FORMAT)
        self.assertEqual(
            PreparedContentArtifact.from_dict(artifact.to_dict()).artifact_identity,
            artifact.artifact_identity,
        )

    def test_payload_and_root_mutations_change_identity(self):
        artifact = PreparedContentArtifact("Book", _exact_children(), profile_id="typed-media")
        changed_payload = list(_exact_children())
        changed_payload[1] = PreparedContentChild(
            **{**changed_payload[1].__dict__, "payload_sha256": "e" * 64}
        )
        self.assertNotEqual(
            artifact.artifact_identity,
            PreparedContentArtifact("Book", tuple(changed_payload), profile_id="typed-media").artifact_identity,
        )
        self.assertNotEqual(
            artifact.artifact_identity,
            PreparedContentArtifact(
                "Renamed Book",
                tuple(
                    PreparedContentChild(
                        **{
                            **child.__dict__,
                            "path": child.path.replace("root\\Book", "root\\Renamed Book"),
                        }
                    )
                    for child in _exact_children()
                ),
                profile_id="typed-media",
            ).artifact_identity,
        )

    def test_duplicate_owner_visible_siblings_fail_closed(self):
        first = _child(0, "txt", "chapter.txt", "a" * 64)
        duplicate = _child(1, "txt", "Chapter.txt", "b" * 64)
        with self.assertRaisesRegex(PreparedContentError, "duplicate owner-visible sibling"):
            PreparedContentArtifact("Book", (first, duplicate))

    def test_valid_hierarchical_preparation_is_not_live_eligible(self):
        hierarchy = PreparedContentArtifact(
            "Book",
            (
                _child(0, "folder", "Section", EMPTY_SHA256),
                _child(1, "txt", "chapter.txt", "a" * 64, parent="Section"),
            ),
            profile_id=HIERARCHICAL_OFFLINE_PROFILE_ID,
            profile_sha256=hierarchical_offline_capability_profile().sha256,
        )
        self.assertTrue(hierarchy.valid_preparation)
        readiness = build_library_transfer_readiness(_readiness_plan(hierarchy))
        self.assertTrue(readiness.prepared_content_valid)
        self.assertFalse(readiness.live_transfer_eligible)
        self.assertTrue(readiness.blocked)

    def test_exact_reviewed_shape_is_host_live_eligible_but_not_enabled(self):
        artifact = PreparedContentArtifact("Book", _exact_children(), profile_id="typed-media")
        readiness = build_library_transfer_readiness(_readiness_plan(artifact))
        self.assertTrue(readiness.prepared_content_valid)
        self.assertTrue(readiness.live_transfer_eligible)
        self.assertTrue(readiness.host_profile_eligible)
        self.assertFalse(readiness.transfer_enabled)
        self.assertEqual(
            readiness.to_dict()["package"]["prepared_artifact_identity"],
            artifact.artifact_identity,
        )

    def test_broader_shape_is_prepared_but_live_ineligible(self):
        broader = PreparedContentArtifact(
            "Book",
            (
                _child(0, "txt", "one.txt", "a" * 64),
                _child(1, "txt", "two.txt", "b" * 64),
            ),
            profile_id="typed-media",
        )
        readiness = build_library_transfer_readiness(_readiness_plan(broader))
        self.assertTrue(readiness.prepared_content_valid)
        self.assertFalse(readiness.live_transfer_eligible)
        self.assertTrue(readiness.blocked)

    def test_stale_canonical_identity_and_target_are_rejected(self):
        artifact = PreparedContentArtifact("Book", _exact_children(), profile_id="typed-media")
        stale = _readiness_plan(artifact)
        changed = copy.deepcopy(stale)
        changed["items"][0]["prepared_artifact"]["canonical"]["children"][1]["payload_sha256"] = "e" * 64
        self.assertTrue(build_library_transfer_readiness(changed).blocked)

        target_changed = _readiness_plan(artifact, destination_paths=["root\\Other", *[child["path"] for child in artifact.to_legacy_children()]])
        self.assertTrue(build_library_transfer_readiness(target_changed).blocked)

    def test_legacy_projection_adapter_is_deterministic(self):
        children = _exact_children()
        legacy = PreparedContentArtifact("Book", children, profile_id="typed-media").to_legacy_children()
        first = PreparedContentArtifact.from_legacy_children(root_name="Book", children=legacy)
        second = PreparedContentArtifact.from_legacy_children(root_name="Book", children=legacy)
        self.assertEqual(first.artifact_identity, second.artifact_identity)
        self.assertEqual(first.to_legacy_children(), legacy)


if __name__ == "__main__":
    unittest.main()
