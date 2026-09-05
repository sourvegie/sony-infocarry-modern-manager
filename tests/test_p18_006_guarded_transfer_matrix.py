"""P18-006 offline adversarial matrix for the guarded Library boundary.

These tests deliberately use the reviewed P17 fixture builders and fake write
backend.  They assert lifecycle reachability and safety disposition, not just
error text: an input that is rejected before transmission must not reach the
sender, while an ambiguous result after a sender attempt must leave the
installation-wide lock active.
"""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch
import unittest

from infocarry.backup_format import calculate_backup_checksum, parse_backup_blob
from infocarry.capacity import CapacitySemanticsError, assess_total_capacity
from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.device_info import RawInfoResponse
from infocarry.device_model_profile import (
    DeviceModelProfileError,
    VNW_V15_CAPABILITY_PROFILE_ID,
    VNW_V10_PROFILE,
    VNW_V15_PROFILE,
    reviewed_device_model_profile,
    validate_actionable_session,
)
from infocarry.experimental_library_transfer import (
    GuardedLibraryExecutionCoordinator,
    GuardedLibraryExecutionError,
)
from infocarry.experimental_library_transfer_review import (
    EXPERIMENTAL_TARGET_FOLDER,
    build_experimental_library_transfer_review,
)
from infocarry.indeterminate_write_lock import (
    DiagnosticBackupEvidence,
    IndeterminateWriteLockError,
    PersistentIndeterminateWriteLock,
)
from infocarry.library import LibraryCatalog
from infocarry.prepared_library_package_live_adapter import (
    P17_005_CONFIRMATION,
    P17_005_OWNER_APPROVAL,
    P17_005_TARGET_FOLDER,
    PreparedLibraryPackageLiveAdapterError,
    execute_prepared_library_package_live,
    prepare_prepared_library_package_live_preflight,
    reconcile_prepared_library_package_live_result,
)
from infocarry.prepared_library_package_operation_bundle import (
    OperationArtifact,
    PreparedLibraryPackageOperationBundle,
)
from infocarry.prepared_package_multi_verify import (
    PreparedMultiVerificationError,
    verify_prepared_multi_package_readback,
)
from infocarry.prepared_media_package import (
    build_prepared_media_package,
    export_prepared_media_package,
)
from infocarry.protocol import REQUEST_COMPLETION, TransferTimeoutError
from infocarry.write_protocol import REQUEST_BEGIN_TRANSMIT
from infocarry.write_gate import WriteGateError, verify_fresh_backup

try:
    from test_new_txt import _write_archive
    from test_prepared_library_package_live_adapter import _named_template_blob, _response
    from test_prepared_package_multi_candidate import _template_blobs, make_profile_bmp
    from test_prepared_package_workflow import PackageWorkflowBackend
except ModuleNotFoundError:
    from tests.test_new_txt import _write_archive
    from tests.test_prepared_library_package_live_adapter import _named_template_blob, _response
    from tests.test_prepared_package_multi_candidate import _template_blobs, make_profile_bmp
    from tests.test_prepared_package_workflow import PackageWorkflowBackend

import infocarry.prepared_library_package_bridge as bridge_module
import infocarry.prepared_package_multi_candidate as candidate_module
import infocarry.write_protocol as write_protocol_module
from infocarry.prepared_library_package_bridge import PreparedLibraryPackageBridgeError
from infocarry.prepared_multi_package_gate import PreparedMultiPackageGateError


NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


class _HeaderFailureBackend(PackageWorkflowBackend):
    def control_out(self, request_type, request, value, index, data, timeout_ms):
        self.calls.append(("control_out", request, bytes(data)))
        raise OSError("simulated header failure")


class _MissingCompletionBackend(PackageWorkflowBackend):
    def control_in(self, request_type, request, value, index, length, timeout_ms):
        if request == REQUEST_COMPLETION:
            raise OSError("simulated missing completion")
        return super().control_in(request_type, request, value, index, length, timeout_ms)


def _paths():
    return [
        f"root\\{EXPERIMENTAL_TARGET_FOLDER}",
        f"root\\{EXPERIMENTAL_TARGET_FOLDER}\\01-introduction.txt",
        f"root\\{EXPERIMENTAL_TARGET_FOLDER}\\02-page-01.bmp",
        f"root\\{EXPERIMENTAL_TARGET_FOLDER}\\03-ending.txt",
    ]


def _sender_calls(backend) -> int:
    return sum(
        1
        for call in backend.calls
        if call[0] == "control_out" and call[1] == REQUEST_BEGIN_TRANSMIT
    )


def _rewrite_checksum(value: bytes) -> bytes:
    result = bytearray(value)
    result[0x1C:0x20] = b"\x00" * 4
    result[0x1C:0x20] = calculate_backup_checksum(bytes(result)).to_bytes(4, "big")
    return bytes(result)


def _record_for_path(parsed, path):
    offsets = [offset for offset, value in parsed.paths.items() if value == path]
    if len(offsets) != 1:
        raise AssertionError(f"expected one record for {path!r}, got {offsets!r}")
    return parsed.record_at(offsets[0])


def _mutate_candidate_blob(value: bytes, case: str) -> bytes:
    parsed = parse_backup_blob(value)
    result = bytearray(value)
    folder = _record_for_path(parsed, ("root", EXPERIMENTAL_TARGET_FOLDER))
    children = [
        _record_for_path(parsed, ("root", EXPERIMENTAL_TARGET_FOLDER, name))
        for name in ("01-introduction", "02-page-01", "03-ending")
    ]

    if case in {"missing_new_root", "wrong_root_name"}:
        offset = folder.offset + 0x18
        result[offset : offset + 0x28] = b"wrong-root\x00".ljust(0x28, b"\x00")
    elif case == "wrong_child_count":
        offset = folder.offset + 0x08
        result[offset : offset + 4] = (folder.field_08_be32 + 0x40).to_bytes(4, "big")
    elif case == "wrong_child_order":
        first = result[children[0].offset : children[0].offset + 0x40]
        second = result[children[1].offset : children[1].offset + 0x40]
        result[children[0].offset : children[0].offset + 0x40] = second
        result[children[1].offset : children[1].offset + 0x40] = first
    elif case == "wrong_child_type":
        result[children[0].offset + 1 : children[0].offset + 4] = b"bmp"
    elif case in {"txt_payload_mismatch", "bmp_payload_mismatch"}:
        index = 0 if case.startswith("txt") else 1
        _prefix, payload = parsed.payload_parts(children[index])
        payload_offset = parsed.header.content_start + children[index].field_04_be32 + len(_prefix)
        result[payload_offset] ^= 1
    elif case == "extra_unexpected_child":
        offset = children[2].offset + 0x18
        result[offset : offset + 0x28] = b"04-extra\x00".ljust(0x28, b"\x00")
    elif case == "required_metadata_mismatch":
        offset = children[0].offset + 0x0C
        result[offset : offset + 4] = (children[0].timestamp_be32 + 1).to_bytes(4, "big")
    elif case == "unrelated_content_change":
        baseline_files = [
            record
            for path, record in (
                (path, parsed.record_at(offset)) for offset, path in parsed.paths.items()
            )
            if record.kind == "file" and path in {
                candidate_path
                for candidate_path in parsed.paths.values()
                if candidate_path not in {
                    ("root", EXPERIMENTAL_TARGET_FOLDER, "01-introduction"),
                    ("root", EXPERIMENTAL_TARGET_FOLDER, "02-page-01"),
                    ("root", EXPERIMENTAL_TARGET_FOLDER, "03-ending"),
                }
            }
        ]
        if not baseline_files:
            raise AssertionError("fixture has no unrelated file to mutate")
        record = baseline_files[0]
        _prefix, payload = parsed.payload_parts(record)
        payload_offset = parsed.header.content_start + record.field_04_be32 + len(_prefix)
        result[payload_offset] ^= 1
    else:
        raise AssertionError(f"unknown candidate mutation {case}")
    return _rewrite_checksum(bytes(result))


def _mutate_unrelated_blob(value: bytes) -> bytes:
    """Change one pre-existing file while preserving a parseable checksum."""

    parsed = parse_backup_blob(value)
    record = next(
        record
        for offset, path in parsed.paths.items()
        for record in (parsed.record_at(offset),)
        if record.kind == "file"
    )
    prefix, _payload = parsed.payload_parts(record)
    result = bytearray(value)
    payload_offset = parsed.header.content_start + record.field_04_be32 + len(prefix)
    result[payload_offset] ^= 1
    return _rewrite_checksum(bytes(result))


def _plan_from_fixture(fixture):
    candidate = fixture.preflight.candidate.audit_dict()
    binding = candidate["library_binding"]
    candidate_items = candidate["package"]["ordered_items"]
    children = []
    for binding_child, candidate_child in zip(binding["ordered_children"], candidate_items):
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
        "selection": {"mode": "selected", "selected_item_ids": [fixture.bundle.selected_item_id]},
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
                "item_id": fixture.bundle.selected_item_id,
                "operation_type": "prepared_flat_typed_package",
                "execution_eligible": False,
                "prepared_artifact": {
                    "contract": "infocarry-prepared-typed-media-package-v1",
                    "manifest_sha256": candidate["package"]["prepared_manifest_sha256"],
                    "source_bytes": sum(child["source_bytes"] for child in children),
                    "prepared_payload_bytes": sum(child["prepared_payload_bytes"] for child in children),
                    "ordered_children": children,
                },
                "destination": {"paths": candidate["package"]["paths"]},
                "conflicts": [],
                "queue_ready": True,
            }
        ],
    }


class _P18006Fixture:
    """One real P17 bundle with an injected fake-only transport boundary."""

    def __init__(self, *, backend=None, after_mode=None, prewrite_mode=None, content_suffix=""):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.evidence_namespace = self.root / "evidence-namespace"
        self.evidence_namespace.mkdir()
        baseline_blob, _template_blob = _template_blobs()
        self.baseline_blob = baseline_blob
        self.changed_unrelated_blob = _mutate_unrelated_blob(baseline_blob)
        self.fixed_state = {command: b"\x00" * 64 for command in (0x001B, 0x001C, 0x001D, 0x001E, 0x001F)}
        intro = self.root / "intro.txt"
        image = self.root / "page.bmp"
        ending = self.root / "ending.txt"
        intro.write_text("Introduction\n" + content_suffix, encoding="utf-8")
        image.write_bytes(make_profile_bmp())
        ending.write_text("The End\n" + content_suffix, encoding="utf-8")
        package = build_prepared_media_package(
            ((intro, "01-introduction.txt"), (image, "02-page-01.bmp"), (ending, "03-ending.txt")),
            P17_005_TARGET_FOLDER,
        )
        package_root = export_prepared_media_package(package, self.root / "package")
        self.catalog = LibraryCatalog(self.root / "catalog/library.json")
        self.item = self.catalog.import_prepared_package(package_root)
        self.template = parse_backup_blob(_named_template_blob())
        self.candidate_holder = {"candidate": None}
        self.captures = []
        self.after_mode = after_mode
        self.prewrite_mode = prewrite_mode

        def capture(destination, **_kwargs):
            destination = Path(destination)
            self.captures.append(destination)
            if destination.name == "backup-after-0001":
                if self.after_mode == "no_backup":
                    raise OSError("simulated missing post-operation backup")
                blob = self.candidate_holder["candidate"].candidate_blob
                if self.after_mode == "stale_preoperation":
                    blob = self.baseline_blob
                _write_archive(destination, blob, NOW, fixed_state=self.fixed_state)
                if self.after_mode == "incomplete":
                    manifest_path = destination / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["state"] = "incomplete"
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                elif self.after_mode == "integrity_invalid":
                    (destination / "object-08.bin").write_bytes(b"tampered")
                elif self.after_mode == "wrong_session":
                    manifest_path = destination / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["device"] = {"vendor_id": "0x0000", "product_id": "0x0000"}
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                elif self.after_mode == "parser_failure":
                    blob_path = destination / "object-08.bin"
                    blob_path.write_bytes(b"not-a-backup")
                    manifest_path = destination / "manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    for entry in manifest["objects"]:
                        if entry["filename"] == blob_path.name:
                            entry["sha256"] = hashlib.sha256(b"not-a-backup").hexdigest()
                            entry["received_length"] = len(b"not-a-backup")
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                return
            blob = self.baseline_blob
            if self.prewrite_mode == "changed_baseline" and destination.name == "backup-before-0001":
                blob = self.candidate_holder["candidate"].candidate_blob
            elif self.prewrite_mode == "changed_unrelated" and destination.name == "backup-before-0001":
                blob = self.changed_unrelated_blob
            _write_archive(destination, blob, NOW, fixed_state=self.fixed_state)
            if self.prewrite_mode == "incomplete" and destination.name == "backup-before-0001":
                manifest_path = destination / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["state"] = "incomplete"
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            elif self.prewrite_mode == "integrity_invalid" and destination.name == "backup-before-0001":
                (destination / "object-08.bin").write_bytes(b"tampered")
            elif self.prewrite_mode == "wrong_session" and destination.name == "backup-before-0001":
                manifest_path = destination / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["device"] = {"vendor_id": "0x0000", "product_id": "0x0000"}
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        self.capture = capture
        self.previewed = []
        patchers = [
            patch.object(bridge_module, "P17_003_REVIEWED_TEMPLATE_BLOB_SHA256", hashlib.sha256(self.template.data).hexdigest()),
            patch.object(candidate_module, "REVIEWED_TEMPLATE_SUBSET_POLICY_SHA256", hashlib.sha256(self.template.data).hexdigest()),
        ]
        for patcher in patchers:
            patcher.start()
        self._patchers = patchers
        common = {
            "catalog": self.catalog,
            "selected_item_id": self.item.item_id,
            "backup_destination": self.root / "before",
            "template": self.template,
            "new_record_timestamp_be32": 0x6A958595,
            "detect_device": lambda: (0x054C, 0x001E),
            "query_capacity": _response,
            "capture": self.capture,
            "preview_callback": self.previewed.append,
            "now": NOW,
            "max_age_seconds": None,
        }
        self.preflight = prepare_prepared_library_package_live_preflight(**common)
        self.candidate_holder["candidate"] = self.preflight.candidate
        self.report_path = self.root / "sealed-preflight.json"
        self.report_path.write_text(json.dumps(self.preflight.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.template_path = self.root / "reviewed-template.bin"
        self.template_path.write_bytes(self.template.data)
        self.capacity_path = self.root / "capacity-response.bin"
        self.capacity_path.write_bytes(_response().raw_response)
        self.bundle = PreparedLibraryPackageOperationBundle.from_sealed_report(
            self.report_path,
            template_path=self.template_path,
            capacity_response_path=self.capacity_path,
        )
        self.backend = backend or PackageWorkflowBackend()
        self.lock = PersistentIndeterminateWriteLock(self.root / "lock.json")
        self.plan = _plan_from_fixture(self)

    def execute(self, *, coordinator=False, **overrides):
        arguments = {
            "owner_approval": P17_005_OWNER_APPROVAL,
            "confirmation": P17_005_CONFIRMATION,
            "detect_device": lambda: (0x054C, 0x001E),
            "query_capacity": _response,
            "backend": self.backend,
            "capture": self.capture,
            "evidence_namespace": self.evidence_namespace,
            "now": NOW,
            "max_age_seconds": None,
        }
        arguments.update(overrides)
        if coordinator:
            arguments.pop("owner_approval", None)
            arguments.pop("confirmation", None)
            return GuardedLibraryExecutionCoordinator(indeterminate_write_lock=self.lock).execute(
                self.bundle,
                plan_report=self.plan,
                confirmation_interaction=lambda _review: P17_005_CONFIRMATION,
                **arguments,
            )
        return execute_prepared_library_package_live(self.bundle, **arguments)

    def close(self):
        for patcher in getattr(self, "_patchers", ()):
            patcher.stop()
        self.temporary.cleanup()


class P18006GuardedTransferMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        template = parse_backup_blob(_named_template_blob())
        digest = hashlib.sha256(template.data).hexdigest()
        cls._bridge_template_patch = patch.object(bridge_module, "P17_003_REVIEWED_TEMPLATE_BLOB_SHA256", digest)
        cls._candidate_template_patch = patch.object(candidate_module, "REVIEWED_TEMPLATE_SUBSET_POLICY_SHA256", digest)
        cls._bridge_template_patch.start()
        cls._candidate_template_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls._candidate_template_patch.stop()
        cls._bridge_template_patch.stop()

    def fixture(self, **kwargs):
        fixture = _P18006Fixture(**kwargs)
        self.addCleanup(fixture.close)
        return fixture

    def assert_rejected_before_sender(self, fixture, *, plan=None, stage="eligibility"):
        confirmations = []
        with self.assertRaises(GuardedLibraryExecutionError) as raised:
            GuardedLibraryExecutionCoordinator(indeterminate_write_lock=fixture.lock).execute(
                fixture.bundle,
                plan_report=fixture.plan if plan is None else plan,
                confirmation_interaction=lambda review: confirmations.append(review) or P17_005_CONFIRMATION,
                detect_device=lambda: self.fail("device detection must not be reached"),
                query_capacity=lambda: self.fail("capacity must not be reached"),
                backend=fixture.backend,
                capture=lambda *_args, **_kwargs: self.fail("backup must not be reached"),
                evidence_namespace=fixture.evidence_namespace,
            )
        self.assertEqual(raised.exception.stage, stage)
        self.assertEqual(confirmations, [])
        self.assertEqual(_sender_calls(fixture.backend), 0)
        self.assertIsNone(fixture.lock.read())
        self.assertFalse(raised.exception.automatic_retry_allowed)
        return raised.exception

    def test_declared_matrix_has_all_required_adversarial_categories(self):
        categories = set("ABCDEFGHIJKLMNO")
        documented = {
            "A": "capability/package shape",
            "B": "model/profile isolation",
            "C": "prepared content/manifest drift",
            "D": "plan/review/bundle binding",
            "E": "fresh backup evidence",
            "F": "capacity evidence",
            "G": "conflict/baseline drift",
            "H": "confirmation/authorization replay",
            "I": "persistent indeterminate lock",
            "J": "transport/completion outcomes",
            "K": "execute-once/retry resistance",
            "L": "post-write backup failures",
            "M": "independent semantic read-back",
            "N": "auxiliary-state boundary",
            "O": "GUI/CLI isolation",
        }
        self.assertEqual(set(documented), categories)
        self.assertEqual(len(documented), 15)

    def test_A_shape_matrix_is_preview_only_and_cannot_reach_confirmation(self):
        fixture = self.fixture()
        base = fixture.plan
        base_children = base["items"][0]["prepared_artifact"]["ordered_children"]

        def child_case(kind, index, value):
            def mutate(plan):
                plan["items"][0]["prepared_artifact"]["ordered_children"][index][kind] = value
            return mutate

        cases = [
            ("zero children", lambda plan: plan["items"][0]["prepared_artifact"].update(ordered_children=[])),
            ("one child", lambda plan: plan["items"][0]["prepared_artifact"].update(ordered_children=deepcopy(base_children[:1]))),
            ("two children", lambda plan: plan["items"][0]["prepared_artifact"].update(ordered_children=deepcopy(base_children[:2]))),
            ("four children", lambda plan: plan["items"][0]["prepared_artifact"].update(ordered_children=deepcopy(base_children + [base_children[-1]]))),
            ("TXT TXT BMP", lambda plan: (plan["items"][0]["prepared_artifact"]["ordered_children"].__setitem__(1, deepcopy(base_children[2])), plan["items"][0]["prepared_artifact"]["ordered_children"].__setitem__(2, deepcopy(base_children[1])))),
            ("BMP TXT TXT", lambda plan: (plan["items"][0]["prepared_artifact"].__setitem__(0, deepcopy(base_children[1])), plan["items"][0]["prepared_artifact"]["ordered_children"].__setitem__(1, deepcopy(base_children[0])))),
            ("TXT BMP BMP", child_case("kind", 2, "bmp")),
            ("unsupported type", child_case("kind", 1, "epub")),
            ("nested child", child_case("path", 0, f"root\\{EXPERIMENTAL_TARGET_FOLDER}\\nested\\01-introduction.txt")),
            ("nested subfolder", child_case("path", 1, f"root\\{EXPERIMENTAL_TARGET_FOLDER}\\sub\\page\\02-page-01.bmp")),
            ("destination present", lambda plan: plan["items"][0].update(conflicts=[{"path": _paths()[0]}])),
            ("overwrite", lambda plan: plan["items"][0].update(operation_type="overwrite_existing")),
            ("merge", lambda plan: plan["grouping"].update(overlap_status="merge")),
            ("delete semantics", lambda plan: plan["items"][0].update(operation_type="delete")),
            ("batch semantics", lambda plan: plan["selection"].update(selected_item_ids=[fixture.bundle.selected_item_id, "second"])),
            ("multiple root packages", lambda plan: plan.update(items=[deepcopy(plan["items"][0]), deepcopy(plan["items"][0])])),
            ("automatic grouping", lambda plan: plan["grouping"].update(automatic_grouping=True)),
            ("broader flat profile", lambda plan: plan["items"][0]["prepared_artifact"]["ordered_children"].__setitem__(1, {**base_children[1], "name": "other.bmp", "path": f"root\\{EXPERIMENTAL_TARGET_FOLDER}\\other.bmp"})),
            ("hierarchical preview", lambda plan: (plan["items"][0].update(operation_type="hierarchical_preview_package"), plan["items"][0]["prepared_artifact"]["ordered_children"].__setitem__(0, {**base_children[0], "path": f"root\\Folder\\01-introduction.txt"}))),
        ]
        for name, mutate in cases:
            with self.subTest(name=name):
                plan = deepcopy(base)
                mutate(plan)
                self.assert_rejected_before_sender(fixture, plan=plan)

    def test_B_model_and_capability_matrix_is_fail_closed(self):
        fixture = self.fixture()
        for name, kwargs in (
            ("V10", {"device_model_profile": VNW_V10_PROFILE}),
            ("unknown capability", {"capability_profile_id": "unknown-profile"}),
        ):
            with self.subTest(name=name):
                with self.assertRaises(GuardedLibraryExecutionError) as raised:
                    GuardedLibraryExecutionCoordinator(indeterminate_write_lock=fixture.lock, **kwargs)
                self.assertIn(raised.exception.stage, {"model_profile", "capability_profile"})
                self.assertEqual(_sender_calls(fixture.backend), 0)
        with self.assertRaises(DeviceModelProfileError):
            reviewed_device_model_profile("unknown-model")
        with self.assertRaises(DeviceModelProfileError):
            validate_actionable_session([VNW_V10_PROFILE])
        self.assertIs(validate_actionable_session([VNW_V15_PROFILE]), VNW_V15_PROFILE)
        tampered_profile = replace(
            VNW_V15_PROFILE,
            transfer_capability_profile_id="tampered-capability-profile",
        )
        with self.assertRaises(GuardedLibraryExecutionError) as raised:
            GuardedLibraryExecutionCoordinator(
                indeterminate_write_lock=fixture.lock,
                device_model_profile=tampered_profile,
            )
        self.assertEqual(raised.exception.stage, "model_profile")
        self.assertEqual(VNW_V15_PROFILE.transfer_capability_profile_id, VNW_V15_CAPABILITY_PROFILE_ID)

    def test_C_prepared_source_and_manifest_drift_stops_before_sender(self):
        for name, mutate in (
            ("TXT bytes", lambda fixture: (fixture.root / "package" / "prepared" / P17_005_TARGET_FOLDER / "01-introduction.txt").write_bytes(b"mutated")),
            ("BMP bytes", lambda fixture: (fixture.root / "package" / "prepared" / P17_005_TARGET_FOLDER / "02-page-01.bmp").write_bytes(b"mutated")),
            ("package manifest", lambda fixture: Path(fixture.item.package.manifest_path).write_text("{}", encoding="utf-8")),
        ):
            with self.subTest(name=name):
                fixture = self.fixture()
                mutate(fixture)
                with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as raised:
                    fixture.execute(coordinator=True)
                self.assertIn(raised.exception.stage, {"preflight_load", "operation_bundle", "candidate_revalidation"})
                self.assertEqual(_sender_calls(fixture.backend), 0)
                self.assertIsNone(fixture.lock.read())
        for name, mutate in (
            ("source hash", lambda plan: plan["items"][0]["prepared_artifact"]["ordered_children"][0].update(source_sha256="0" * 64)),
            ("prepared hash", lambda plan: plan["items"][0]["prepared_artifact"]["ordered_children"][1].update(prepared_payload_sha256="0" * 64)),
            ("child order", lambda plan: plan["items"][0]["prepared_artifact"]["ordered_children"][1].update(order=9)),
            ("child name", lambda plan: plan["items"][0]["prepared_artifact"]["ordered_children"][0].update(name="renamed.txt")),
            ("child path", lambda plan: plan["items"][0]["prepared_artifact"]["ordered_children"][0].update(path="root\\other\\01-introduction.txt")),
            ("type declaration", lambda plan: plan["items"][0]["prepared_artifact"]["ordered_children"][1].update(kind="txt")),
            ("prepared size", lambda plan: plan["items"][0]["prepared_artifact"]["ordered_children"][1].update(prepared_payload_bytes=1)),
            ("logical manifest", lambda plan: plan["items"][0]["prepared_artifact"].update(manifest_sha256="0" * 64)),
            ("destination", lambda plan: plan["items"][0]["destination"].update(paths=["root\\other"])),
        ):
            with self.subTest(name=name):
                fixture = self.fixture()
                plan = deepcopy(fixture.plan)
                mutate(plan)
                self.assert_rejected_before_sender(fixture, plan=plan)

        unknown = self.fixture()
        sealed = json.loads(unknown.report_path.read_text(encoding="utf-8"))
        sealed["unexpected"] = True
        unknown.report_path.write_text(json.dumps(sealed), encoding="utf-8")
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as raised:
            unknown.execute(coordinator=True)
        self.assertEqual(raised.exception.stage, "operation_bundle")
        self.assertEqual(_sender_calls(unknown.backend), 0)

    def test_D_individually_valid_objects_do_not_cross_bind(self):
        first = self.fixture(content_suffix=" A")
        second = self.fixture(content_suffix=" B")
        review = build_experimental_library_transfer_review(
            first.plan,
            preflight_report=second.preflight.to_dict(),
            bundle_report=second.bundle.to_dict(),
        ).to_dict()
        self.assertEqual(review["eligibility"]["state"], "preview_only")
        with self.assertRaises((PreparedLibraryPackageBridgeError, PreparedMultiPackageGateError)):
            first.preflight.authorization.require_same_candidate(second.preflight.candidate)
        with self.assertRaises(GuardedLibraryExecutionError) as raised:
            GuardedLibraryExecutionCoordinator(indeterminate_write_lock=first.lock).execute(
                second.bundle,
                plan_report=first.plan,
                confirmation_interaction=lambda _review: P17_005_CONFIRMATION,
                detect_device=lambda: (0x054C, 0x001E),
                query_capacity=_response,
                backend=first.backend,
                capture=first.capture,
                evidence_namespace=first.evidence_namespace,
            )
        self.assertEqual(raised.exception.stage, "eligibility")
        self.assertEqual(_sender_calls(first.backend), 0)

    def test_E_backup_evidence_matrix_never_authorizes_without_fresh_verified_state(self):
        for name, mode in (
            ("incomplete", "incomplete"),
            ("integrity invalid", "integrity_invalid"),
            ("wrong session", "wrong_session"),
        ):
            with self.subTest(name=name):
                fixture = self.fixture(prewrite_mode=mode)
                with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
                    fixture.execute(coordinator=True)
                self.assertEqual(_sender_calls(fixture.backend), 0)
                self.assertIsNone(fixture.lock.read())
        stale = self.fixture()
        stale_manifest_path = Path(stale.bundle.baseline_backup.path) / "manifest.json"
        stale_manifest = json.loads(stale_manifest_path.read_text(encoding="utf-8"))
        stale_manifest["updated_at_utc"] = "2020-01-01T00:00:00+00:00"
        stale_manifest_path.write_text(json.dumps(stale_manifest), encoding="utf-8")
        with self.assertRaises(WriteGateError):
            verify_fresh_backup(Path(stale.bundle.baseline_backup.path), now=NOW, max_age_seconds=60)
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
            stale.execute(coordinator=True)
        self.assertEqual(_sender_calls(stale.backend), 0)

        substituted = self.fixture()
        object_path = Path(substituted.bundle.baseline_backup.path) / "object-08.bin"
        object_path.write_bytes(b"substituted-backup-object")
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
            substituted.execute(coordinator=True)
        self.assertEqual(_sender_calls(substituted.backend), 0)
        missing = self.fixture()
        missing.bundle = replace(
            missing.bundle,
            baseline_backup=OperationArtifact(
                str(missing.root / "missing-baseline"),
                missing.bundle.baseline_backup.sha256,
                "backup_manifest_bytes",
                missing.bundle.baseline_backup.size_bytes,
            ),
        )
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
            missing.execute(coordinator=True)
        self.assertEqual(_sender_calls(missing.backend), 0)

        for field in ("complete", "read_only", "integrity_verified"):
            with self.subTest(non_boolean_field=field):
                values = {
                    "model_key": VNW_V15_PROFILE.lock_key,
                    "incident_id": "incident",
                    "attempt_id": "attempt",
                    "backup_sha256": "a" * 64,
                    "object_count": 1,
                }
                values[field] = 1
                with self.assertRaises(IndeterminateWriteLockError):
                    DiagnosticBackupEvidence(**values)

    def test_F_capacity_matrix_preserves_exact_existing_boundary_semantics(self):
        fixture = self.fixture()
        allocation = fixture.preflight.candidate.audit_dict()["allocation"]
        exact = assess_total_capacity(
            allocation["candidate_model_bytes"],
            allocation["baseline_model_bytes"],
            allocation["candidate_model_bytes"],
            source="p18-006-boundary",
        )
        self.assertEqual(exact.remaining_after_transfer_bytes if hasattr(exact, "remaining_after_transfer_bytes") else exact.capacity_limit_bytes - exact.candidate_model_bytes, 0)
        with self.assertRaises(CapacitySemanticsError):
            assess_total_capacity(
                allocation["candidate_model_bytes"] - 1,
                allocation["baseline_model_bytes"],
                allocation["candidate_model_bytes"],
                source="p18-006-beyond-boundary",
            )
        altered_raw = bytearray(_response().raw_response)
        altered_raw[0x08:0x0C] = (int.from_bytes(altered_raw[0x08:0x0C], "big") - 1).to_bytes(4, "big")
        altered_response = NativeCapacityResponse.from_hardware_response(
            RawInfoResponse(0x0019, "altered", bytes(altered_raw)),
            device_identity=(0x054C, 0x001E),
        )
        for name, response in (
            ("missing", None),
            ("wrong type", object()),
            ("stale or altered response", altered_response),
        ):
            with self.subTest(name=name):
                failed = self.fixture()
                with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
                    failed.execute(coordinator=True, query_capacity=lambda response=response: response)
                self.assertEqual(_sender_calls(failed.backend), 0)

    def test_G_drift_after_confirmation_is_revalidated_before_sender(self):
        fixture = self.fixture()
        confirmed = []

        def capture(destination, **kwargs):
            fixture.capture(destination, **kwargs)
            if Path(destination).name == "backup-before-0001":
                fixture.plan["items"][0]["conflicts"] = [{"path": _paths()[0]}]

        with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as raised:
            GuardedLibraryExecutionCoordinator(indeterminate_write_lock=fixture.lock).execute(
                fixture.bundle,
                plan_report=fixture.plan,
                confirmation_interaction=lambda review: confirmed.append(review) or P17_005_CONFIRMATION,
                detect_device=lambda: (0x054C, 0x001E),
                query_capacity=_response,
                backend=fixture.backend,
                capture=capture,
                evidence_namespace=fixture.evidence_namespace,
            )
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(raised.exception.stage, "preflight_revalidation")
        self.assertEqual(_sender_calls(fixture.backend), 0)
        self.assertIsNone(fixture.lock.read())

        for name, fixture_kwargs, execute_kwargs in (
            ("baseline logical contents changed", {"prewrite_mode": "changed_baseline"}, {}),
            ("unrelated baseline content changed", {"prewrite_mode": "changed_unrelated"}, {}),
            ("device identity changed", {}, {"detect_device": lambda: (0x054C, 0x001F)}),
        ):
            with self.subTest(name=name):
                drifted = self.fixture(**fixture_kwargs)
                with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as drift:
                    drifted.execute(coordinator=True, **execute_kwargs)
                self.assertEqual(drift.exception.stage, "preflight_revalidation")
                self.assertEqual(_sender_calls(drifted.backend), 0)
                self.assertIsNone(drifted.lock.read())

    def test_H_confirmation_decline_replay_and_double_call_cannot_send_twice(self):
        fixture = self.fixture()
        with self.assertRaises(GuardedLibraryExecutionError) as declined:
            GuardedLibraryExecutionCoordinator(indeterminate_write_lock=fixture.lock).execute(
                fixture.bundle,
                plan_report=fixture.plan,
                confirmation_interaction=lambda _review: "",
                detect_device=lambda: self.fail("no device callback after decline"),
                query_capacity=_response,
                backend=fixture.backend,
                capture=fixture.capture,
                evidence_namespace=fixture.evidence_namespace,
            )
        self.assertEqual(declined.exception.stage, "confirmation")
        self.assertEqual(_sender_calls(fixture.backend), 0)
        result = fixture.execute(coordinator=True)
        self.assertEqual(result.completion, 0)
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
            fixture.execute(coordinator=True)
        self.assertEqual(_sender_calls(fixture.backend), 1)

        for name, response in (
            ("integer", 0),
            ("mapping", {"confirmation": P17_005_CONFIRMATION}),
            ("none", None),
        ):
            with self.subTest(malformed_confirmation=name):
                malformed = self.fixture()
                with self.assertRaises(GuardedLibraryExecutionError) as raised:
                    GuardedLibraryExecutionCoordinator(
                        indeterminate_write_lock=malformed.lock
                    ).execute(
                        malformed.bundle,
                        plan_report=malformed.plan,
                        confirmation_interaction=lambda _review, value=response: value,
                        detect_device=lambda: self.fail("device detection must not be reached"),
                        query_capacity=_response,
                        backend=malformed.backend,
                        capture=malformed.capture,
                        evidence_namespace=malformed.evidence_namespace,
                    )
                self.assertEqual(raised.exception.stage, "confirmation")
                self.assertEqual(_sender_calls(malformed.backend), 0)

        changed = self.fixture()

        def change_after_review(_review):
            changed.plan["safety"]["automatic_retry"] = True
            return P17_005_CONFIRMATION

        with self.assertRaises(GuardedLibraryExecutionError) as raised:
            GuardedLibraryExecutionCoordinator(
                indeterminate_write_lock=changed.lock
            ).execute(
                changed.bundle,
                plan_report=changed.plan,
                confirmation_interaction=change_after_review,
                detect_device=lambda: self.fail("device detection must not be reached"),
                query_capacity=_response,
                backend=changed.backend,
                capture=changed.capture,
                evidence_namespace=changed.evidence_namespace,
            )
        self.assertEqual(raised.exception.stage, "confirmation_revalidation")
        self.assertEqual(_sender_calls(changed.backend), 0)

        premature = self.fixture()
        with self.assertRaises(GuardedLibraryExecutionError) as raised:
            GuardedLibraryExecutionCoordinator(
                indeterminate_write_lock=premature.lock
            ).execute(
                premature.bundle,
                plan_report=premature.plan,
                confirmation_interaction=lambda _review: P17_005_CONFIRMATION,
                owner_approval=P17_005_OWNER_APPROVAL,
                confirmation=P17_005_CONFIRMATION,
                detect_device=lambda: self.fail("device detection must not be reached"),
                query_capacity=_response,
                backend=premature.backend,
                capture=premature.capture,
                evidence_namespace=premature.evidence_namespace,
            )
        self.assertEqual(raised.exception.stage, "confirmation")
        self.assertEqual(_sender_calls(premature.backend), 0)

    def test_I_global_lock_survives_reopen_reconnect_and_model_change(self):
        fixture = self.fixture(backend=PackageWorkflowBackend(bulk_error=OSError("disconnect")))
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
            fixture.execute(coordinator=True)
        self.assertIsNotNone(fixture.lock.read())
        reopened = PersistentIndeterminateWriteLock(fixture.lock.path)
        with self.assertRaises(IndeterminateWriteLockError):
            reopened.assert_unlocked(VNW_V15_PROFILE.lock_key)
        with self.assertRaises(IndeterminateWriteLockError):
            reopened.assert_unlocked(VNW_V10_PROFILE.lock_key)
        with self.assertRaises(IndeterminateWriteLockError):
            GuardedLibraryExecutionCoordinator(indeterminate_write_lock=reopened).execute(
                fixture.bundle,
                plan_report=fixture.plan,
                confirmation_interaction=lambda _review: P17_005_CONFIRMATION,
            )
        record = reopened.read()
        self.assertEqual(record.model_key, VNW_V15_PROFILE.lock_key)
        self.assertEqual(record.state, "locked")
        self.assertIsNotNone(record.incident_id)
        with self.assertRaises(IndeterminateWriteLockError):
            reopened.clear_after_diagnostic(
                diagnostic_backup=object(),
                recovery_decision="clear",
                decision_record_sha256="b" * 64,
                evidence_root=str(fixture.evidence_namespace),
                model_key=VNW_V15_PROFILE.lock_key,
            )
        wrong_binding = DiagnosticBackupEvidence(
            model_key=VNW_V15_PROFILE.lock_key,
            incident_id="wrong-incident",
            attempt_id=record.attempt_id,
            backup_sha256="a" * 64,
            object_count=1,
        )
        with self.assertRaises(IndeterminateWriteLockError):
            reopened.clear_after_diagnostic(
                diagnostic_backup=wrong_binding,
                recovery_decision="clear",
                decision_record_sha256="b" * 64,
                evidence_root=str(fixture.evidence_namespace),
                model_key=VNW_V15_PROFILE.lock_key,
            )
        self.assertEqual(reopened.read().state, "locked")

    def test_J_completion_matrix_distinguishes_nonzero_from_ambiguous_values(self):
        for name, completion, expected_lock in (
            ("nonzero integer", 1, False),
            ("None", None, True),
            ("bool", False, True),
            ("string", "0x0000", True),
            ("unexpected object", object(), True),
        ):
            with self.subTest(name=name):
                fixture = self.fixture()
                with patch.object(write_protocol_module.AuthorizedWriteSender, "send", return_value=completion) as send:
                    with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
                        fixture.execute(coordinator=True)
                self.assertEqual(send.call_count, 1)
                self.assertEqual(_sender_calls(fixture.backend), 0)
                self.assertEqual(fixture.lock.read() is not None, expected_lock)

    def test_K_transport_failures_are_one_shot_and_never_implicitly_retried(self):
        cases = (
            ("header exception", _HeaderFailureBackend(), False),
            ("nonzero completion", PackageWorkflowBackend(completions=(1,)), False),
            ("bulk timeout", PackageWorkflowBackend(bulk_error=TransferTimeoutError("timeout")), True),
            ("disconnect", PackageWorkflowBackend(bulk_error=OSError("disconnect")), True),
            ("missing completion", _MissingCompletionBackend(), True),
        )
        for name, backend, locked in cases:
            with self.subTest(name=name):
                fixture = self.fixture(backend=backend)
                with self.assertRaises(PreparedLibraryPackageLiveAdapterError):
                    fixture.execute(coordinator=True)
                self.assertEqual(_sender_calls(backend), 1)
                if locked:
                    self.assertIsNotNone(fixture.lock.read())
                with self.assertRaises((PreparedLibraryPackageLiveAdapterError, IndeterminateWriteLockError)):
                    fixture.execute(coordinator=True)
                self.assertEqual(_sender_calls(backend), 1)

        before = self.fixture()
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as raised:
            before.execute(coordinator=True, cancelled=lambda: True)
        self.assertEqual(raised.exception.state, "cancelled_before_transaction")
        self.assertEqual(_sender_calls(before.backend), 0)
        self.assertIsNone(before.lock.read())

        after_backend = PackageWorkflowBackend()
        after = self.fixture(backend=after_backend)
        with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as raised:
            after.execute(coordinator=True, cancelled=lambda: bool(after_backend.calls))
        self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
        self.assertEqual(_sender_calls(after_backend), 1)
        self.assertIsNotNone(after.lock.read())

        repeated = self.fixture()
        repeated.execute(coordinator=True)
        with self.assertRaises((PreparedLibraryPackageLiveAdapterError, IndeterminateWriteLockError)):
            repeated.execute(
                coordinator=True,
                evidence_namespace=repeated.root / "second-evidence-namespace",
            )
        self.assertEqual(_sender_calls(repeated.backend), 1)

        parallel = self.fixture()
        barrier = threading.Barrier(2)
        outcomes = []

        def invoke_parallel():
            barrier.wait()
            try:
                outcomes.append(("success", parallel.execute(coordinator=True)))
            except BaseException as exc:
                outcomes.append(("error", exc))

        workers = [threading.Thread(target=invoke_parallel) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(sum(kind == "success" for kind, _value in outcomes), 1)
        self.assertEqual(sum(kind == "error" for kind, _value in outcomes), 1)
        self.assertEqual(_sender_calls(parallel.backend), 1)

    def test_L_post_write_backup_failures_are_indeterminate_after_exactly_one_send(self):
        for name in ("no_backup", "incomplete", "integrity_invalid", "wrong_session", "parser_failure", "stale_preoperation"):
            with self.subTest(name=name):
                fixture = self.fixture(after_mode=name)
                with self.assertRaises(PreparedLibraryPackageLiveAdapterError) as raised:
                    fixture.execute(coordinator=True)
                self.assertEqual(raised.exception.state, "indeterminate_after_transaction_start")
                self.assertEqual(_sender_calls(fixture.backend), 1)
                self.assertIsNotNone(fixture.lock.read())

    def test_M_independent_readback_rejects_each_semantic_tamper(self):
        cases = (
            "missing_new_root", "wrong_root_name", "wrong_child_count", "wrong_child_order",
            "wrong_child_type", "txt_payload_mismatch", "bmp_payload_mismatch",
            "extra_unexpected_child", "unrelated_content_change", "required_metadata_mismatch",
        )
        for case in cases:
            with self.subTest(case=case):
                fixture = self.fixture()
                bad_blob = _mutate_candidate_blob(fixture.preflight.candidate.candidate_blob, case)
                after = fixture.root / f"after-{case}"
                _write_archive(after, bad_blob, NOW, fixed_state=fixture.fixed_state)
                with self.assertRaises(PreparedMultiVerificationError):
                    verify_prepared_multi_package_readback(
                        fixture.preflight.candidate.core,
                        after,
                        completion=0,
                        now=NOW,
                        max_age_seconds=None,
                    )

        altered = self.fixture()
        bad_blob = _mutate_candidate_blob(altered.preflight.candidate.candidate_blob, "wrong_root_name")
        bad_after = altered.root / "after-altered-expectation"
        _write_archive(bad_after, bad_blob, NOW, fixed_state=altered.fixed_state)
        altered_core = replace(
            altered.preflight.candidate.core,
            candidate=parse_backup_blob(bad_blob),
            candidate_blob=bad_blob,
        )
        with self.assertRaises(PreparedMultiVerificationError):
            verify_prepared_multi_package_readback(
                altered_core,
                bad_after,
                completion=0,
                now=NOW,
                max_age_seconds=None,
            )
        valid_after = altered.root / "after-valid-for-claim-check"
        _write_archive(valid_after, altered.preflight.candidate.candidate_blob, NOW, fixed_state=altered.fixed_state)
        with self.assertRaises(PreparedMultiVerificationError):
            verify_prepared_multi_package_readback(
                altered.preflight.candidate.core,
                valid_after,
                completion="0x0000",
                now=NOW,
                max_age_seconds=None,
            )

    def test_N_auxiliary_state_policy_is_bounded_and_tamper_is_not_reclassified(self):
        fixture = self.fixture()
        audit = fixture.preflight.candidate.audit_dict()
        self.assertEqual(audit["policy"]["manager_sidecars"], "not part of device transaction")
        self.assertIn("display_history_validation", audit)
        after = fixture.root / "after-fixed-state"
        _write_archive(after, fixture.preflight.candidate.candidate_blob, NOW, fixed_state={**fixture.fixed_state, 0x001B: b"changed" * 16})
        with self.assertRaises(PreparedMultiVerificationError):
            verify_prepared_multi_package_readback(
                fixture.preflight.candidate,
                after,
                completion=0,
                now=NOW,
                max_age_seconds=None,
            )

    def test_O_normal_surfaces_remain_review_only_and_imports_are_usb_free(self):
        root = Path(__file__).resolve().parents[1]
        cli = (root / "src/infocarry/cli.py").read_text(encoding="utf-8")
        desktop = (root / "src/infocarry/desktop_ttk.py").read_text(encoding="utf-8")
        for source in (cli, desktop):
            self.assertNotIn("run_experimental_library_transfer", source)
            self.assertNotIn("from .experimental_library_transfer import", source)
        self.assertNotIn("debug", cli.lower())
        self.assertNotIn("test_transport", desktop)
        self.assertFalse(hasattr(__import__("infocarry.experimental_library_transfer", fromlist=["*"]), "AuthorizedWriteSender"))

    def test_positive_control_is_one_exact_fake_transaction_with_independent_success(self):
        fixture = self.fixture()
        result = fixture.execute(coordinator=True)
        self.assertEqual(result.completion, 0)
        self.assertTrue(result.verification.success)
        self.assertEqual(_sender_calls(fixture.backend), 1)
        self.assertEqual(len(fixture.captures), 3)
        self.assertIsNone(fixture.lock.read())
        self.assertEqual(result.audit["accounting"]["logical_sender_calls"], 1)
        self.assertTrue(result.audit["post_backup_verified"])
        self.assertTrue(result.audit["independent_readback_verified"])
        with self.assertRaises((PreparedLibraryPackageLiveAdapterError, IndeterminateWriteLockError)):
            fixture.execute(coordinator=True)
        self.assertEqual(_sender_calls(fixture.backend), 1)


if __name__ == "__main__":
    unittest.main()
