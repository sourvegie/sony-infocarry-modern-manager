from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from infocarry.app_paths import application_paths
from infocarry.execution_claim_store import (
    ExecutionClaimAlreadyConsumedError,
    ExecutionClaimStoreError,
)
from infocarry.indeterminate_write_lock import (
    DiagnosticBackupEvidence,
    IndeterminateWriteLockError,
)
from infocarry.write_safety_boundary import (
    WriteSafetyBoundaryError,
    create_default_application_write_safety_owner,
)


_DIGEST = "a" * 64
_BINDINGS = {
    "preflight_seal_sha256": "1" * 64,
    "core_preflight_seal_sha256": "2" * 64,
    "candidate_blob_sha256": "3" * 64,
    "transaction_sha256": "4" * 64,
    "authorization_sha256": "5" * 64,
    "baseline_state_identity_sha256": "6" * 64,
    "capacity_response_sha256": "7" * 64,
}


class ApplicationSafetyPathsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name) / "profile"
        self.paths = application_paths(
            home=self.home,
            environ={},
            platform="darwin",
            os_name="posix",
        )

    def test_fresh_owner_creates_only_historical_claim_path_and_is_restart_stable(self):
        self.assertFalse(self.paths.safety_root.exists())
        first = create_default_application_write_safety_owner(paths=self.paths)
        self.assertEqual(first.execution_claim_store.path, self.paths.execution_claims_database)
        self.assertEqual(first.indeterminate_write_lock.path, self.paths.indeterminate_write_lock)
        self.assertTrue(self.paths.execution_claims_database.is_file())
        self.assertFalse(self.paths.indeterminate_write_lock.exists())
        first.assert_execution_boundary_available()

        claim = first.consume_execution_claim(_BINDINGS)
        restarted_paths = application_paths(
            home=self.home,
            environ={},
            platform="darwin",
            os_name="posix",
        )
        second = create_default_application_write_safety_owner(paths=restarted_paths)
        self.assertEqual(second.execution_claim_store.path, first.execution_claim_store.path)
        self.assertEqual(second.indeterminate_write_lock.path, first.indeterminate_write_lock.path)
        with self.assertRaises(ExecutionClaimAlreadyConsumedError):
            second.consume_execution_claim(_BINDINGS)
        self.assertEqual(claim.preflight_seal_sha256, _BINDINGS["preflight_seal_sha256"])

    def test_existing_cleared_lock_remains_at_legacy_path_and_does_not_block_owner(self):
        owner = create_default_application_write_safety_owner(paths=self.paths)
        key = owner.device_model_profile.lock_key
        owner.indeterminate_write_lock.record_indeterminate(
            reason="fixture incident",
            evidence_root="fixture-evidence",
            model_key=key,
            incident_id="incident-1",
            attempt_id="attempt-1",
        )
        owner.indeterminate_write_lock.clear_after_diagnostic(
            diagnostic_backup=DiagnosticBackupEvidence(
                model_key=key,
                incident_id="incident-1",
                attempt_id="attempt-1",
                backup_sha256=_DIGEST,
                object_count=1,
            ),
            recovery_decision="fixture recovery decision",
            decision_record_sha256="b" * 64,
            evidence_root="fixture-recovery-evidence",
            model_key=key,
        )

        restarted = create_default_application_write_safety_owner(paths=self.paths)
        restarted.assert_execution_boundary_available()
        clear_record = restarted.indeterminate_write_lock.read(key)
        self.assertIsNotNone(clear_record)
        self.assertFalse(clear_record.locked)
        self.assertTrue(self.paths.indeterminate_write_lock.is_file())
        self.assertEqual(restarted.execution_claim_store.path, self.paths.execution_claims_database)

    def test_existing_active_global_lock_blocks_boundary_after_restart(self):
        owner = create_default_application_write_safety_owner(paths=self.paths)
        owner.indeterminate_write_lock.record_indeterminate(
            reason="fixture unresolved outcome",
            evidence_root="fixture-evidence",
            model_key=owner.device_model_profile.lock_key,
            incident_id="incident-active",
            attempt_id="attempt-active",
        )

        restarted = create_default_application_write_safety_owner(paths=self.paths)
        with self.assertRaisesRegex(IndeterminateWriteLockError, "globally locked"):
            restarted.assert_execution_boundary_available()

    def test_abandoned_sender_marker_is_promoted_to_the_legacy_lock_path(self):
        owner = create_default_application_write_safety_owner(paths=self.paths)
        claim = owner.consume_execution_claim(_BINDINGS)
        owner.mark_sender_start(
            claim,
            attempt_id="attempt-abandoned",
            evidence_root="fixture-evidence",
            operation_label="fixture-operation",
        )

        restarted = create_default_application_write_safety_owner(paths=self.paths)
        with self.assertRaisesRegex(IndeterminateWriteLockError, "abandoned sender-start boundary"):
            restarted.assert_execution_boundary_available()

        lock = restarted.indeterminate_write_lock.read(restarted.device_model_profile.lock_key)
        marker = restarted.execution_claim_store.read_sender_in_flight()
        self.assertIsNotNone(lock)
        self.assertTrue(lock.locked)
        self.assertEqual(lock.attempt_id, "attempt-abandoned")
        self.assertIsNotNone(marker)
        self.assertEqual(marker.state, "lock_recorded")
        self.assertEqual(marker.attempt_id, "attempt-abandoned")
        self.assertEqual(restarted.indeterminate_write_lock.path, self.paths.indeterminate_write_lock)

    def test_startup_inspection_does_not_promote_abandoned_marker(self):
        owner = create_default_application_write_safety_owner(paths=self.paths)
        claim = owner.consume_execution_claim(_BINDINGS)
        owner.mark_sender_start(
            claim,
            attempt_id="attempt-startup-inspection",
            evidence_root="fixture-evidence",
            operation_label="fixture-operation",
        )

        restarted = create_default_application_write_safety_owner(paths=self.paths)
        marker_before = restarted.execution_claim_store.read_sender_in_flight()
        self.assertIsNotNone(marker_before)
        self.assertFalse(self.paths.indeterminate_write_lock.exists())

        with self.assertRaisesRegex(
            IndeterminateWriteLockError, "unresolved sender-start marker"
        ):
            restarted.inspect_execution_boundary()

        marker_after = restarted.execution_claim_store.read_sender_in_flight()
        self.assertEqual(marker_after, marker_before)
        self.assertFalse(self.paths.indeterminate_write_lock.exists())

    def test_existing_legacy_root_without_claim_database_fails_closed_without_creating_db(self):
        self.paths.safety_root.mkdir(parents=True)

        with self.assertRaisesRegex(WriteSafetyBoundaryError, "database is missing"):
            create_default_application_write_safety_owner(paths=self.paths)

        self.assertTrue(self.paths.safety_root.is_dir())
        self.assertFalse(self.paths.execution_claims_database.exists())

    def test_inaccessible_persistent_state_fails_closed_before_owner_creation(self):
        with patch(
            "infocarry.write_safety_boundary._path_exists_without_hiding_access_errors",
            side_effect=WriteSafetyBoundaryError("cannot inspect persistent state: permission denied"),
        ):
            with self.assertRaisesRegex(WriteSafetyBoundaryError, "permission denied"):
                create_default_application_write_safety_owner(paths=self.paths)
        self.assertFalse(self.paths.safety_root.exists())

    def test_corrupt_historical_claim_database_is_not_replaced(self):
        self.paths.safety_root.mkdir(parents=True)
        original = b"not a sqlite database; preserve this state"
        self.paths.execution_claims_database.write_bytes(original)

        with self.assertRaises(ExecutionClaimStoreError):
            create_default_application_write_safety_owner(paths=self.paths)

        self.assertEqual(self.paths.execution_claims_database.read_bytes(), original)

    def test_conflicting_state_in_each_proposed_alternate_root_blocks_selection(self):
        for index, alternate_root in enumerate(self.paths.alternate_safety_roots):
            with self.subTest(alternate_root=alternate_root):
                alternate_root.mkdir(parents=True, exist_ok=True)
                existing_state = alternate_root / "execution-claims.sqlite3"
                existing_state.write_bytes(f"alternate-state-{index}".encode())

                with self.assertRaisesRegex(WriteSafetyBoundaryError, "proposed alternate"):
                    create_default_application_write_safety_owner(paths=self.paths)

                self.assertFalse(self.paths.safety_root.exists())
                self.assertEqual(existing_state.read_bytes(), f"alternate-state-{index}".encode())
                existing_state.unlink()
                alternate_root.rmdir()

    def test_corrupt_historical_lock_fails_closed_and_is_preserved(self):
        owner = create_default_application_write_safety_owner(paths=self.paths)
        original = b"{invalid lock json"
        self.paths.indeterminate_write_lock.write_bytes(original)

        restarted = create_default_application_write_safety_owner(paths=self.paths)
        with self.assertRaisesRegex(IndeterminateWriteLockError, "unreadable"):
            restarted.assert_execution_boundary_available()

        self.assertEqual(self.paths.indeterminate_write_lock.read_bytes(), original)
        self.assertEqual(restarted.execution_claim_store.path, owner.execution_claim_store.path)

    def test_sender_marker_stays_in_historical_sqlite_database(self):
        owner = create_default_application_write_safety_owner(paths=self.paths)
        claim = owner.consume_execution_claim(_BINDINGS)
        owner.mark_sender_start(
            claim,
            attempt_id="attempt-marker",
            evidence_root="fixture-evidence",
            operation_label="fixture-operation",
        )

        self.assertTrue(self.paths.execution_claims_database.is_file())
        self.assertFalse((self.paths.safety_root / "sender-in-flight.json").exists())
        reopened = create_default_application_write_safety_owner(paths=self.paths)
        marker = reopened.execution_claim_store.read_sender_in_flight()
        self.assertIsNotNone(marker)
        self.assertEqual(marker.attempt_id, "attempt-marker")


if __name__ == "__main__":
    unittest.main()
