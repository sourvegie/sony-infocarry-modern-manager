import tempfile
import unittest
from pathlib import Path

from infocarry.indeterminate_write_lock import (
    DeviceModelLockKey,
    DiagnosticBackupEvidence,
    IndeterminateWriteLockError,
    PersistentIndeterminateWriteLock,
)


V15 = DeviceModelLockKey("sony-vnw-v15")
V10 = DeviceModelLockKey("sony-vnw-v10")


class IndeterminateWriteLockTests(unittest.TestCase):
    def test_global_lock_persists_across_sessions_and_never_auto_clears(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state" / "indeterminate-lock.json"
            first = PersistentIndeterminateWriteLock(path)
            self.assertIsNone(first.read())
            record = first.record_indeterminate(
                reason="completion was ambiguous",
                evidence_root="/external/attempt-1",
                model_key=V15,
                incident_id="incident-1",
                attempt_id="attempt-1",
            )
            self.assertTrue(record.locked)

            second = PersistentIndeterminateWriteLock(path)
            self.assertTrue(second.read(V10).locked)
            with self.assertRaises(IndeterminateWriteLockError):
                second.assert_unlocked(V10)  # A fresh V10 session sees the global lock.
            self.assertTrue(second.record_indeterminate(
                reason="a different reason",
                evidence_root="/external/attempt-2",
                model_key=V10,
                incident_id="incident-2",
                attempt_id="attempt-2",
            ).locked)

    def test_clear_requires_original_incident_and_documented_decision(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PersistentIndeterminateWriteLock(Path(temporary) / "lock.json")
            store.record_indeterminate(
                reason="disconnect after transmission",
                evidence_root="/external/attempt",
                model_key=V15,
                incident_id="incident-1",
                attempt_id="attempt-1",
            )
            with self.assertRaises(IndeterminateWriteLockError):
                store.clear_after_diagnostic(
                    diagnostic_backup=DiagnosticBackupEvidence(
                        model_key=V15,
                        incident_id="incident-1",
                        attempt_id="attempt-1",
                        backup_sha256="a" * 64,
                        object_count=8,
                    ),
                    recovery_decision="Project Lead reviewed read-only diagnosis",
                    decision_record_sha256="also-not-a-hash",
                    evidence_root="/external/diagnosis",
                    model_key=V15,
                )

            with self.assertRaises(IndeterminateWriteLockError):
                store.clear_after_diagnostic(
                    diagnostic_backup=DiagnosticBackupEvidence(
                        model_key=V15,
                        incident_id="incident-1",
                        attempt_id="attempt-1",
                        backup_sha256="a" * 64,
                        object_count=8,
                    ),
                    recovery_decision="",
                    decision_record_sha256="b" * 64,
                    evidence_root="/external/diagnosis",
                    model_key=V15,
                )

            with self.assertRaises(IndeterminateWriteLockError):
                store.clear_after_diagnostic(
                    diagnostic_backup=DiagnosticBackupEvidence(
                        model_key=V15,
                        incident_id="incident-1",
                        attempt_id="different-attempt",
                        backup_sha256="a" * 64,
                        object_count=8,
                    ),
                    recovery_decision="Project Lead reviewed read-only diagnosis",
                    decision_record_sha256="b" * 64,
                    evidence_root="/external/diagnosis",
                    model_key=V15,
                )
            cleared = store.clear_after_diagnostic(
                diagnostic_backup=DiagnosticBackupEvidence(
                    model_key=V15,
                    incident_id="incident-1",
                    attempt_id="attempt-1",
                    backup_sha256="a" * 64,
                    object_count=8,
                    complete=True,
                    read_only=True,
                    integrity_verified=True,
                ),
                recovery_decision="Project Lead reviewed read-only diagnosis",
                decision_record_sha256="b" * 64,
                evidence_root="/external/diagnosis",
                model_key=V15,
            )
            self.assertFalse(cleared.locked)
            store.assert_unlocked()

    def test_diagnostic_evidence_requires_exact_true_verification_flags(self):
        base = {
            "model_key": V15,
            "incident_id": "incident-1",
            "attempt_id": "attempt-1",
            "backup_sha256": "a" * 64,
            "object_count": 8,
        }

        accepted = DiagnosticBackupEvidence(
            **base,
            complete=True,
            read_only=True,
            integrity_verified=True,
        )
        self.assertTrue(accepted.complete)
        self.assertTrue(accepted.read_only)
        self.assertTrue(accepted.integrity_verified)

        for field in ("complete", "read_only", "integrity_verified"):
            for value in (False, "false", "true", 1):
                with self.subTest(field=field, value=value):
                    values = {
                        "complete": True,
                        "read_only": True,
                        "integrity_verified": True,
                        field: value,
                    }
                    with self.assertRaises(IndeterminateWriteLockError):
                        DiagnosticBackupEvidence(**base, **values)

    def test_unknown_or_vid_pid_keys_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PersistentIndeterminateWriteLock(Path(temporary) / "lock.json")
            with self.assertRaises(ValueError):
                DeviceModelLockKey("sony-vnw-unknown")
            with self.assertRaises(IndeterminateWriteLockError):
                store.record_indeterminate(
                    reason="bad identity",
                    evidence_root="/external/attempt",
                    model_key=("0x054c", "0x001e"),
                    incident_id="incident-1",
                    attempt_id="attempt-1",
                )
            with self.assertRaises(IndeterminateWriteLockError):
                store.read(("0x054c", "0x001e"))

    def test_lock_clear_rejects_unverified_or_unrelated_diagnostic(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PersistentIndeterminateWriteLock(Path(temporary) / "lock.json")
            store.record_indeterminate(
                reason="timeout",
                evidence_root="/external/attempt",
                model_key=V15,
                incident_id="incident-1",
                attempt_id="attempt-1",
            )

            with self.assertRaises(IndeterminateWriteLockError):
                store.clear_after_diagnostic(
                    diagnostic_backup=DiagnosticBackupEvidence(
                        model_key=V15,
                        incident_id="incident-1",
                        attempt_id="attempt-1",
                        backup_sha256="a" * 64,
                        object_count=8,
                        integrity_verified=False,
                    ),
                    recovery_decision="Project Lead reviewed read-only diagnosis",
                    decision_record_sha256="b" * 64,
                    evidence_root="/external/diagnosis",
                    model_key=V15,
                )

            with self.assertRaises(IndeterminateWriteLockError):
                store.clear_after_diagnostic(
                    diagnostic_backup=DiagnosticBackupEvidence(
                        model_key=V10,
                        incident_id="incident-1",
                        attempt_id="attempt-1",
                        backup_sha256="a" * 64,
                        object_count=8,
                    ),
                    recovery_decision="Project Lead reviewed read-only diagnosis",
                    decision_record_sha256="b" * 64,
                    evidence_root="/external/diagnosis",
                    model_key=V10,
                )

            with self.assertRaises(IndeterminateWriteLockError):
                store.clear_after_diagnostic(
                    diagnostic_backup=DiagnosticBackupEvidence(
                        model_key=V15,
                        incident_id="different-incident",
                        attempt_id="attempt-1",
                        backup_sha256="a" * 64,
                        object_count=8,
                    ),
                    recovery_decision="Project Lead reviewed read-only diagnosis",
                    decision_record_sha256="b" * 64,
                    evidence_root="/external/diagnosis",
                    model_key=V15,
                )

            class DuckTypedBackup:
                model_key = V15
                incident_id = "incident-1"
                attempt_id = "attempt-1"
                backup_sha256 = "a" * 64

            with self.assertRaises(IndeterminateWriteLockError):
                store.clear_after_diagnostic(
                    diagnostic_backup=DuckTypedBackup(),
                    recovery_decision="Project Lead reviewed read-only diagnosis",
                    decision_record_sha256="b" * 64,
                    evidence_root="/external/diagnosis",
                    model_key=V15,
                )


if __name__ == "__main__":
    unittest.main()
