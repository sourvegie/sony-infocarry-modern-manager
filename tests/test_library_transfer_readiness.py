import copy
import inspect
import unittest

from infocarry.desktop_ttk import format_library_transfer_readiness, launch_ttk_desktop
from infocarry.device_model_profile import VNW_V10_PROFILE, VNW_V15_PROFILE
from infocarry.library_transfer_readiness import (
    EXPERIMENTAL_CHILD_KINDS,
    LIBRARY_TRANSFER_READINESS_STATUS,
    LibraryTransferReadinessError,
    build_library_transfer_readiness,
    validate_library_transfer_readiness,
)


def _paths(folder="Book", names=None):
    names = names or (
        "01-introduction.txt",
        "02-page-01.bmp",
        "03-ending.txt",
    )
    root = f"root\\{folder}"
    return [root, *(f"{root}\\{name}" for name in names)]


def _children(folder="Book", kinds=None, names=None):
    kinds = kinds or EXPERIMENTAL_CHILD_KINDS
    names = names or (
        "01-introduction.txt",
        "02-page-01.bmp",
        "03-ending.txt",
    )
    paths = _paths(folder, names)
    return [
        {
            "order": order,
            "kind": kind,
            "name": name,
            "path": paths[order + 1],
            "source_sha256": f"{order + 1:x}" * 64,
            "source_bytes": 12 if kind == "txt" else 9662,
            "prepared_payload_sha256": f"{order + 4:x}" * 64,
            "prepared_payload_bytes": 12 if kind == "txt" else 9662,
        }
        for order, (kind, name) in enumerate(zip(kinds, names))
    ]


def _plan(
    *,
    selected_ids=None,
    children=None,
    paths=None,
    baseline=False,
    item_reasons=None,
    item_queue_ready=None,
):
    selected_ids = ["item-1"] if selected_ids is None else selected_ids
    children = _children() if children is None else children
    paths = _paths() if paths is None else paths
    if item_queue_ready is None:
        item_queue_ready = baseline
    if item_reasons is None:
        item_reasons = [] if baseline else [
            "verified device backup is required for destination and capacity review"
        ]
    capacity = (
        {
            "status": "sufficient_for_lower_bound_only",
            "baseline_model_bytes": 2_075_256,
            "available_bytes": 1_000_000,
            "lower_bound_bytes": 16_036,
            "exact_growth_known": False,
        }
        if baseline
        else {
            "status": "not_evaluated_without_verified_backup",
            "baseline_model_bytes": None,
            "available_bytes": None,
            "lower_bound_bytes": 16_036,
            "exact_growth_known": False,
        }
    )
    item = {
        "item_id": "item-1",
        "operation_type": "prepared_flat_typed_package",
        "execution_eligible": False,
        "prepared_artifact": {
            "contract": "infocarry-prepared-typed-media-package-v1",
            "manifest_sha256": "f" * 64,
            "source_bytes": sum(child["source_bytes"] for child in children),
            "prepared_payload_bytes": sum(
                child["prepared_payload_bytes"] for child in children
            ),
            "ordered_children": children,
        },
        "destination": {"paths": paths},
        "conflicts": [],
        "capacity": capacity,
        "queue_ready": item_queue_ready,
        "reasons": item_reasons,
    }
    return {
        "format": "infocarry-library-transfer-plan-v1",
        "state": "previewed_offline",
        "usb_accessed": False,
        "device_change": "none",
        "selection": {
            "mode": "selected",
            "selected_item_ids": selected_ids,
        },
        "baseline": (
            {
                "available": True,
                "device_identity": {"vendor_id": "0x054c", "product_id": "0x001e"},
                "blob_sha256": "a" * 64,
            }
            if baseline
            else {"available": False, "reason": "verified offline backup not supplied"}
        ),
        "grouping": {
            "automatic_grouping": False,
            "overlap_status": "none",
            "overlap_paths": [],
        },
        "eligibility": {
            "offline_review_ready": True,
            "queue_ready": item_queue_ready,
            "device_candidate_eligible": False,
            "transfer_enabled": False,
            "reasons": [] if baseline else ["destination conflicts require a verified offline backup"],
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
        "items": [item],
    }


class LibraryTransferReadinessTests(unittest.TestCase):
    def test_exact_package_is_reusable_host_eligible_but_needs_fresh_evidence(self):
        readiness = build_library_transfer_readiness(_plan()).to_dict()

        self.assertTrue(readiness["eligibility"]["host_profile_eligible"])
        self.assertTrue(readiness["eligibility"]["needs_fresh_live_evidence"])
        self.assertFalse(readiness["eligibility"]["blocked"])
        self.assertEqual(readiness["eligibility"]["status_text"], LIBRARY_TRANSFER_READINESS_STATUS)
        self.assertEqual(
            [child["kind"] for child in readiness["package"]["ordered_children"]],
            ["txt", "bmp", "txt"],
        )
        self.assertFalse(readiness["transfer_boundary"]["transfer_enabled"])
        self.assertEqual(readiness["transfer_boundary"]["device_changing_operations"], 0)

    def test_verified_baseline_contributes_conflict_and_lower_bound_capacity_facts(self):
        readiness = build_library_transfer_readiness(_plan(baseline=True)).to_dict()

        self.assertTrue(readiness["eligibility"]["host_profile_eligible"])
        self.assertTrue(readiness["evidence"]["verified_baseline_available"])
        self.assertEqual(readiness["destination"]["baseline_status"], "verified baseline supplied; destination paths checked")
        self.assertEqual(readiness["capacity"]["baseline_model_bytes"], 2_075_256)
        self.assertEqual(readiness["capacity"]["lower_bound_bytes"], 16_036)
        self.assertFalse(readiness["capacity"]["exact_growth_known"])

    def test_selection_and_package_shape_fail_closed(self):
        cases = (
            ("zero selection", _plan(selected_ids=[]), "select exactly one"),
            ("multiple selection", _plan(selected_ids=["item-1", "item-2"]), "never merged"),
            (
                "non-package",
                dict(_plan(), **{}),
                "placeholder",
            ),
            (
                "wrong count",
                _plan(children=_children()[:2]),
                "exactly three direct children",
            ),
            (
                "wrong order",
                _plan(children=[_children()[1], _children()[0], _children()[2]]),
                "TXT → BMP → TXT",
            ),
            (
                "wrong kind",
                _plan(children=_children(kinds=("txt", "txt", "txt"))),
                "TXT → BMP → TXT",
            ),
            (
                "nested",
                _plan(
                    children=[
                        *_children()[:1],
                        {**_children()[1], "path": "root\\Book\\nested\\02-page-01.bmp"},
                        _children()[2],
                    ]
                ),
                "nested",
            ),
            (
                "extra destination",
                _plan(paths=[*_paths(), "root\\Book\\extra.txt"]),
                "exactly the root folder",
            ),
        )
        for name, plan, expected in cases:
            with self.subTest(name=name):
                if name == "non-package":
                    plan["items"][0]["operation_type"] = "prepared_root_txt_package"
                    expected = "explicitly imported prepared Library package"
                readiness = build_library_transfer_readiness(plan)
                self.assertTrue(readiness.blocked)
                self.assertFalse(readiness.host_profile_eligible)
                self.assertIn(expected, " ".join(readiness.to_dict()["eligibility"]["reasons"]))

    def test_manifest_filename_path_and_payload_limits_fail_closed(self):
        cases = (
            ("malformed manifest", {"contract": "wrong"}, "manifest contract"),
            (
                "bad filename",
                {"children": _children(names=("nested.name.txt", "02-page-01.bmp", "03-ending.txt"))},
                "destination must contain exactly",
            ),
            (
                "bad cp932 folder",
                {
                    "paths": _paths(folder="😀"),
                    "children": _children(folder="😀"),
                },
                "canonical preparation/profile validation",
            ),
            (
                "payload limit",
                {"children": [{**child, "prepared_payload_bytes": 1_048_577} for child in _children()]},
                "canonical preparation/profile validation",
            ),
        )
        for name, mutation, expected in cases:
            with self.subTest(name=name):
                plan = _plan()
                if "children" in mutation:
                    plan["items"][0]["prepared_artifact"]["ordered_children"] = mutation["children"]
                if "paths" in mutation:
                    plan["items"][0]["destination"]["paths"] = mutation["paths"]
                plan["items"][0]["prepared_artifact"].update(
                    {key: value for key, value in mutation.items() if key not in {"children", "paths"}}
                )
                readiness = build_library_transfer_readiness(plan)
                self.assertTrue(readiness.blocked)
                self.assertIn(expected, " ".join(readiness.to_dict()["eligibility"]["reasons"]))

    def test_overlap_collision_and_model_substitution_block(self):
        collision = _plan(baseline=True)
        collision["items"][0]["conflicts"] = [{"path": "root\\Book", "reason": "exists"}]
        collision["items"][0]["queue_ready"] = False
        collision["items"][0]["reasons"] = ["one or more destination paths conflict with the verified backup"]
        readiness = build_library_transfer_readiness(collision)
        self.assertTrue(readiness.blocked)
        self.assertIn("already exists", " ".join(readiness.to_dict()["eligibility"]["reasons"]))

        overlap = _plan(baseline=True)
        overlap["grouping"]["automatic_grouping"] = True
        overlap["grouping"]["overlap_status"] = "conflict"
        self.assertTrue(build_library_transfer_readiness(overlap).blocked)

        self.assertTrue(
            build_library_transfer_readiness(_plan(baseline=True), model_profile=VNW_V10_PROFILE).blocked
        )
        self.assertIn(
            "uncharacterized",
            " ".join(
                build_library_transfer_readiness(
                    _plan(baseline=True), model_profile=VNW_V10_PROFILE
                ).to_dict()["eligibility"]["reasons"]
            ).lower(),
        )

    def test_historical_operation_identity_is_never_reused(self):
        plan = _plan(baseline=True)
        plan["operation_identity"] = {
            "target": "historical-one-shot",
            "owner_approval": "historical approval",
            "confirmation": "historical confirmation",
        }
        readiness = build_library_transfer_readiness(plan)
        report = readiness.to_dict()

        self.assertTrue(readiness.host_profile_eligible)
        self.assertFalse(report["evidence"]["historical_operation_identity_reused"])
        self.assertTrue(report["evidence"]["historical_operation_identity_supplied"])
        self.assertNotIn("authorization", report)
        self.assertNotIn("operation_identity", report)
        self.assertIn("ignored", " ".join(report["eligibility"]["fresh_evidence_reasons"]))

    def test_plan_and_review_tampering_fail_closed(self):
        plan = _plan(baseline=True)
        plan["safety"]["candidate_constructed"] = True
        readiness = build_library_transfer_readiness(plan)
        self.assertTrue(readiness.blocked)

        report = build_library_transfer_readiness(_plan(baseline=True)).to_dict()
        self.assertTrue(validate_library_transfer_readiness(report))
        tampered = copy.deepcopy(report)
        tampered["eligibility"]["blocked"] = True
        with self.assertRaisesRegex(LibraryTransferReadinessError, "modified"):
            validate_library_transfer_readiness(tampered)

    def test_product_formatter_explains_review_and_disabled_boundary(self):
        summary = format_library_transfer_readiness(
            build_library_transfer_readiness(_plan(baseline=True)).to_dict()
        )
        for text in (
            "Experimental profile eligible — live transfer not enabled in this build",
            "Root destination: root\\Book",
            "TXT 01-introduction.txt",
            "BMP 02-page-01.bmp",
            "TXT 03-ending.txt",
            "Transfer once — disabled",
            "Historical operation identity reused: no",
            "USB operation performed: no",
        ):
            self.assertIn(text, summary)
        self.assertNotIn("APPROVE", summary)
        self.assertNotIn("ADD IC_", summary)

    def test_normal_ttk_surface_has_no_live_sender_route(self):
        source = inspect.getsource(launch_ttk_desktop)

        self.assertIn('text="Transfer once"', source)
        self.assertIn('state="disabled"', source)
        self.assertIn("library_transfer_once_action", source)
        self.assertIn("library_execution_facade.execute_once", source)
        self.assertNotIn("from .experimental_library_transfer import", source)
        self.assertNotIn("prepared_library_package_live_adapter", source)


if __name__ == "__main__":
    unittest.main()
