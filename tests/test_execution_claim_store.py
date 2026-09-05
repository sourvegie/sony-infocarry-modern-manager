import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from infocarry.device_model_profile import DeviceModelLockKey
from infocarry.execution_claim_store import (
    ExecutionClaimAlreadyConsumedError,
    ExecutionClaimStoreError,
    PersistentExecutionClaimStore,
)
from infocarry.indeterminate_write_lock import IndeterminateWriteLockRecord


IDENTITIES = {
    "preflight_seal_sha256": "a" * 64,
    "core_preflight_seal_sha256": "b" * 64,
    "candidate_blob_sha256": "c" * 64,
    "transaction_sha256": "d" * 64,
    "authorization_sha256": "e" * 64,
    "baseline_state_identity_sha256": "f" * 64,
    "capacity_response_sha256": "0" * 64,
}


class PersistentExecutionClaimStoreTests(unittest.TestCase):
    def test_claim_persists_and_rejects_reopened_store(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "installation" / "execution-claims.sqlite3"
            first = PersistentExecutionClaimStore(path)
            record = first.consume(**IDENTITIES)
            self.assertTrue(record.committed)
            self.assertEqual(record.state, "consumed")
            self.assertEqual(record.to_dict()["store_format"], record.to_dict()["format"])

            with self.assertRaises(ExecutionClaimAlreadyConsumedError):
                first.consume(**IDENTITIES)
            with self.assertRaises(ExecutionClaimAlreadyConsumedError):
                PersistentExecutionClaimStore(path).consume(**IDENTITIES)

            different = dict(IDENTITIES)
            different["preflight_seal_sha256"] = "1" * 64
            self.assertEqual(
                PersistentExecutionClaimStore(path).consume(**different).preflight_seal_sha256,
                "1" * 64,
            )

    def test_bindings_are_hash_only_and_inconsistent_reuse_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "claims.sqlite3"
            store = PersistentExecutionClaimStore(path)
            record = store.consume(**IDENTITIES)
            self.assertEqual(record.candidate_blob_sha256, "c" * 64)
            altered = dict(IDENTITIES)
            altered["transaction_sha256"] = "1" * 64
            with self.assertRaises(ExecutionClaimStoreError) as raised:
                store.consume(**altered)
            self.assertNotIsInstance(raised.exception, ExecutionClaimAlreadyConsumedError)
            raw = path.read_bytes()
            self.assertNotIn(b"candidate_bytes", raw)
            self.assertNotIn(b"transaction_bytes", raw)
            self.assertNotIn(b"private candidate payload", raw)
            connection = sqlite3.connect(path)
            try:
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(execution_claims)"
                    )
                }
            finally:
                connection.close()
            self.assertNotIn("candidate_bytes", columns)
            self.assertNotIn("transaction_bytes", columns)

    def test_malformed_digest_is_rejected_before_insert(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PersistentExecutionClaimStore(Path(temporary) / "claims.sqlite3")
            altered = dict(IDENTITIES)
            altered["preflight_seal_sha256"] = "not-a-digest"
            with self.assertRaises(ExecutionClaimStoreError):
                store.consume(**altered)

    def test_corrupt_and_unsupported_stores_are_not_recreated(self):
        with tempfile.TemporaryDirectory() as temporary:
            corrupt = Path(temporary) / "corrupt.sqlite3"
            corrupt.write_bytes(b"this is not sqlite")
            with self.assertRaises(ExecutionClaimStoreError):
                PersistentExecutionClaimStore(corrupt)
            self.assertEqual(corrupt.read_bytes(), b"this is not sqlite")

            unsupported = Path(temporary) / "unsupported.sqlite3"
            connection = sqlite3.connect(unsupported)
            connection.execute("PRAGMA user_version=99")
            connection.commit()
            connection.close()
            with self.assertRaises(ExecutionClaimStoreError):
                PersistentExecutionClaimStore(unsupported)

            empty = Path(temporary) / "empty.sqlite3"
            empty.touch()
            with self.assertRaises(ExecutionClaimStoreError):
                PersistentExecutionClaimStore(empty)

    def test_invalid_path_and_commit_failure_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ExecutionClaimStoreError):
                PersistentExecutionClaimStore(root)
            parent_file = root / "parent-file"
            parent_file.write_text("not a directory", encoding="utf-8")
            with self.assertRaises(ExecutionClaimStoreError):
                PersistentExecutionClaimStore(parent_file / "claims.sqlite3")

            store = PersistentExecutionClaimStore(root / "commit.sqlite3")
            with patch.object(
                store,
                "_commit",
                side_effect=sqlite3.OperationalError("simulated commit failure"),
            ):
                with self.assertRaises(ExecutionClaimStoreError):
                    store.consume(**IDENTITIES)
            # The failed transaction cannot authorize a second caller.  A
            # subsequent real claim is allowed only because the insert was
            # rolled back and no sender callback has been reached.
            self.assertEqual(store.consume(**IDENTITIES).state, "consumed")

    def test_sender_marker_is_singleton_and_resolves_without_resetting_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = PersistentExecutionClaimStore(Path(temporary) / "claims.sqlite3")
            claim = store.consume(**IDENTITIES)
            marker = store.mark_sender_in_flight(
                claim,
                attempt_id="attempt-1",
                incident_id="incident-1",
                evidence_root="/external/attempt-1",
            )
            self.assertEqual(store.read_sender_in_flight(), marker.record)
            with self.assertRaises(ExecutionClaimStoreError):
                store.mark_sender_in_flight(
                    claim,
                    attempt_id="attempt-2",
                    incident_id="incident-2",
                    evidence_root="/external/attempt-2",
                )
            store.resolve_sender_terminal(
                marker,
                resolution="verified_terminal_success",
            )
            self.assertIsNone(store.read_sender_in_flight())
            with self.assertRaises(ExecutionClaimAlreadyConsumedError):
                store.consume(**IDENTITIES)

            different = dict(IDENTITIES)
            different["preflight_seal_sha256"] = "1" * 64
            second_claim = store.consume(**different)
            second_marker = store.mark_sender_in_flight(
                second_claim,
                attempt_id="attempt-2",
                incident_id="incident-2",
                evidence_root="/external/attempt-2",
            )
            recorded = store.mark_sender_lock_recorded(second_marker.record)
            self.assertEqual(recorded.state, "lock_recorded")
            with self.assertRaises(ExecutionClaimStoreError):
                store.resolve_sender_terminal(
                    recorded,
                    resolution="determinate_no_start",
                )
            cleared_lock = IndeterminateWriteLockRecord(
                model_key=DeviceModelLockKey("sony-vnw-v15"),
                incident_id="incident-2",
                attempt_id="attempt-2",
                state="cleared",
                reason="abandoned sender marker",
                evidence_root="/external/diagnostic",
                recorded_at_utc="2026-09-06T00:00:00+00:00",
                diagnostic_backup_sha256="2" * 64,
                recovery_decision="clear",
                decision_record_sha256="3" * 64,
            )
            store.resolve_sender_after_diagnostic(
                recorded,
                lock_record=cleared_lock,
            )
            self.assertIsNone(store.read_sender_in_flight())

    def test_marker_logical_binding_corruption_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "claims.sqlite3"
            store = PersistentExecutionClaimStore(path)
            claim = store.consume(**IDENTITIES)
            marker = store.mark_sender_in_flight(
                claim,
                attempt_id="attempt-corrupt",
                incident_id="incident-corrupt",
                evidence_root="/external/corrupt",
            )
            connection = sqlite3.connect(path)
            try:
                connection.execute(
                    "UPDATE sender_in_flight SET transaction_sha256 = ? WHERE marker_id = 1",
                    ("1" * 64,),
                )
                connection.commit()
            finally:
                connection.close()
            with self.assertRaises(ExecutionClaimStoreError):
                store.read_sender_in_flight()
            # The in-process terminal handle cannot bypass the persisted
            # binding check after the row has been tampered with.
            with self.assertRaises(ExecutionClaimStoreError):
                store.resolve_sender_terminal(
                    marker,
                    resolution="verified_terminal_success",
                )

    def test_restart_and_abrupt_crash_are_real_subprocess_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "claims.sqlite3"
            first = self._run_worker(database, mode="claim")
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout.strip(), "claimed")
            second = self._run_worker(database, mode="claim")
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(second.stdout.strip(), "rejected")

            crash_database = Path(temporary) / "crash.sqlite3"
            crashed = self._run_worker(crash_database, mode="crash")
            self.assertNotEqual(crashed.returncode, 0)
            after_crash = self._run_worker(crash_database, mode="claim")
            self.assertEqual(after_crash.returncode, 0, after_crash.stderr)
            self.assertEqual(after_crash.stdout.strip(), "rejected")

            marker_database = Path(temporary) / "marker-crash.sqlite3"
            marker_crash = self._run_worker(marker_database, mode="marker_crash")
            self.assertNotEqual(marker_crash.returncode, 0)
            marker = PersistentExecutionClaimStore(marker_database).read_sender_in_flight()
            self.assertIsNotNone(marker)
            self.assertEqual(marker.state, "in_flight")

    def test_two_independent_processes_racing_for_one_seal_have_one_winner(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "race.sqlite3"
            ready_a = root / "ready-a"
            ready_b = root / "ready-b"
            processes = [
                self._start_worker(database, "race", ready_a, ready_b),
                self._start_worker(database, "race", ready_b, ready_a),
            ]
            results = [process.communicate(timeout=30) for process in processes]
            for output, error in results:
                self.assertEqual(error, "", error)
                self.assertEqual(output.strip() in {"claimed", "rejected"}, True, output)
            self.assertEqual(
                sorted(output.strip() for output, _error in results),
                ["claimed", "rejected"],
            )

    def test_existing_store_is_rejected_when_unwritable_on_posix(self):
        if os.name == "nt":
            self.skipTest("portable chmod denial is not reliable on Windows")
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root can bypass POSIX mode-bit write denial")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "claims.sqlite3"
            store = PersistentExecutionClaimStore(path)
            path.chmod(0o400)
            try:
                if os.access(path, os.W_OK):
                    self.skipTest("test process can write chmod-readonly files")
                with self.assertRaises(ExecutionClaimStoreError):
                    store.consume(**IDENTITIES)
            finally:
                path.chmod(0o600)

    @staticmethod
    def _subprocess_environment() -> dict[str, str]:
        root = Path(__file__).resolve().parents[1]
        environment = dict(os.environ)
        source = str(root / "src")
        environment["PYTHONPATH"] = source + os.pathsep + environment.get("PYTHONPATH", "")
        return environment

    def _run_worker(self, database: Path, *, mode: str) -> subprocess.CompletedProcess[str]:
        script = textwrap.dedent(
            """
            import os
            import sys
            from infocarry.execution_claim_store import (
                ExecutionClaimStoreError,
                PersistentExecutionClaimStore,
            )

            values = {
                "preflight_seal_sha256": "a" * 64,
                "core_preflight_seal_sha256": "b" * 64,
                "candidate_blob_sha256": "c" * 64,
                "transaction_sha256": "d" * 64,
                "authorization_sha256": "e" * 64,
                "baseline_state_identity_sha256": "f" * 64,
                "capacity_response_sha256": "0" * 64,
            }
            try:
                store = PersistentExecutionClaimStore(sys.argv[1])
                claim = store.consume(**values)
                print("claimed", flush=True)
                if sys.argv[2] == "crash":
                    os._exit(7)
                if sys.argv[2] == "marker_crash":
                    store.mark_sender_in_flight(
                        claim,
                        attempt_id="attempt-crashed",
                        incident_id="incident-crashed",
                        evidence_root="/external/crashed",
                    )
                    os._exit(7)
            except ExecutionClaimStoreError:
                print("rejected", flush=True)
            """
        )
        return subprocess.run(
            [sys.executable, "-c", script, str(database), mode],
            env=self._subprocess_environment(),
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _start_worker(
        self,
        database: Path,
        mode: str,
        ready: Path,
        other_ready: Path,
    ) -> subprocess.Popen[str]:
        script = textwrap.dedent(
            """
            import sys
            import time
            from infocarry.execution_claim_store import (
                ExecutionClaimStoreError,
                PersistentExecutionClaimStore,
            )

            values = {
                "preflight_seal_sha256": "a" * 64,
                "core_preflight_seal_sha256": "b" * 64,
                "candidate_blob_sha256": "c" * 64,
                "transaction_sha256": "d" * 64,
                "authorization_sha256": "e" * 64,
                "baseline_state_identity_sha256": "f" * 64,
                "capacity_response_sha256": "0" * 64,
            }
            ready = __import__("pathlib").Path(sys.argv[2])
            other_ready = __import__("pathlib").Path(sys.argv[3])
            ready.write_text("ready", encoding="utf-8")
            deadline = time.monotonic() + 20
            while not other_ready.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            try:
                PersistentExecutionClaimStore(sys.argv[1]).consume(**values)
                print("claimed", flush=True)
            except ExecutionClaimStoreError:
                print("rejected", flush=True)
            """
        )
        return subprocess.Popen(
            [sys.executable, "-c", script, str(database), str(ready), str(other_ready)],
            env=self._subprocess_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
