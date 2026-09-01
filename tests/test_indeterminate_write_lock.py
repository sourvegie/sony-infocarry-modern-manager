import tempfile
import unittest
from pathlib import Path

from infocarry.indeterminate_write_lock import (
    DiagnosticBackupEvidence,
    IndeterminateWriteLockError,
    PersistentIndeterminateWriteLock,
)


class IndeterminateWriteLockTests(unittest.TestCase):
    def test_lock_persists_across_store_instances_and_never_auto_clears(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state" / "indeterminate-lock.json"
            first = PersistentIndeterminateWriteLock(path)
            self.assertIsNone(first.read())
            record = first.record_indeterminate(
                reason="completion was ambiguous",
                evidence_root="/external/attempt-1",
            )
            self.assertTrue(record.locked)

            second = PersistentIndeterminateWriteLock(path)
            self.assertTrue(second.read().locked)
            with self.assertRaises(IndeterminateWriteLockError):
                second.assert_unlocked()
            self.assertTrue(second.record_indeterminate(
                reason="a different reason", evidence_root="/external/attempt-2"
            ).locked)

    def test_clear_requires_diagnostic_backup_and_documented_decision(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PersistentIndeterminateWriteLock(Path(temporary) / "lock.json")
            store.record_indeterminate(
                reason="disconnect after transmission", evidence_root="/external/attempt"
            )
            with self.assertRaises(IndeterminateWriteLockError):
                store.clear_after_diagnostic(
                    diagnostic_backup=DiagnosticBackupEvidence(
                        device_identity=("0x054c", "0x001e"),
                        backup_sha256="not-a-hash",
                        object_count=8,
                    ),
                    recovery_decision="",
                    decision_record_sha256="also-not-a-hash",
                    evidence_root="/external/diagnosis",
                )
            cleared = store.clear_after_diagnostic(
                diagnostic_backup=DiagnosticBackupEvidence(
                    device_identity=("0x054c", "0x001e"),
                    backup_sha256="a" * 64,
                    object_count=8,
                    complete=True,
                    read_only=True,
                    integrity_verified=True,
                ),
                recovery_decision="Project Lead reviewed read-only diagnosis",
                decision_record_sha256="b" * 64,
                evidence_root="/external/diagnosis",
            )
            self.assertFalse(cleared.locked)
            store.assert_unlocked()

    def test_diagnostic_evidence_requires_exact_true_verification_flags(self):
        base = {
            "device_identity": ("0x054c", "0x001e"),
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
    def test_unsupported_device_cannot_create_or_clear_a_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PersistentIndeterminateWriteLock(Path(temporary) / "lock.json")
            with self.assertRaises(IndeterminateWriteLockError):
                store.record_indeterminate(
                    reason="bad identity",
                    evidence_root="/external/attempt",
                    device_identity=("0x1234", "0x5678"),
                )

    def test_lock_clear_rejects_unverified_or_wrong_device_diagnostic(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PersistentIndeterminateWriteLock(Path(temporary) / "lock.json")
            store.record_indeterminate(reason="timeout", evidence_root="/external/attempt")

            with self.assertRaises(IndeterminateWriteLockError):
                store.clear_after_diagnostic(
                    diagnostic_backup=DiagnosticBackupEvidence(
                        device_identity=("0x054c", "0x001e"),
                        backup_sha256="a" * 64,
                        object_count=8,
                        integrity_verified=False,
                    ),
                    recovery_decision="Project Lead reviewed read-only diagnosis",
                    decision_record_sha256="b" * 64,
                    evidence_root="/external/diagnosis",
                )

            with self.assertRaises(IndeterminateWriteLockError):
                store.clear_after_diagnostic(
                    diagnostic_backup=DiagnosticBackupEvidence(
                        device_identity=("0x054c", "0x001e"),
                        backup_sha256="a" * 64,
                        object_count=8,
                    ),
                    recovery_decision="Project Lead reviewed read-only diagnosis",
                    decision_record_sha256="b" * 64,
                    evidence_root="/external/diagnosis",
                    device_identity=("0x054c", "0x0099"),
                )

            class DuckTypedBackup:
                device_identity = ("0x054c", "0x001e")
                backup_sha256 = "a" * 64

            with self.assertRaises(IndeterminateWriteLockError):
                store.clear_after_diagnostic(
                    diagnostic_backup=DuckTypedBackup(),
                    recovery_decision="Project Lead reviewed read-only diagnosis",
                    decision_record_sha256="b" * 64,
                    evidence_root="/external/diagnosis",
                )


if __name__ == "__main__":
    unittest.main()
