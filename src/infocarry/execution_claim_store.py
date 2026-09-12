"""Durable, installation-scoped one-shot execution claims.

The live execution boundary consumes a sealed preflight identity before it
calls any device callback.  This module is intentionally small and has no
USB or workflow imports.  SQLite supplies the cross-process uniqueness and
the fully committed tombstone; a single sender marker closes the crash
window between entering the sender and recording the existing global
indeterminate-write lock.

The caller must inject a path in installation-owned state.  This component
never chooses a repository, evidence, session, process, or temporary path on
its own, and it never resets a consumed claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from typing import Any, Mapping
from uuid import uuid4

from .indeterminate_write_lock import IndeterminateWriteLockRecord

PERSISTENT_EXECUTION_CLAIM_STORE_FORMAT = (
    "infocarry-persistent-execution-claim-store-v1"
)
PERSISTENT_EXECUTION_CLAIM_PERSISTENCE_MODE = (
    "sqlite3-primary-key-synchronous-full"
)
EXECUTION_CLAIM_SCHEMA_VERSION = 1
SQLITE_BUSY_TIMEOUT_SECONDS = 5.0
_METADATA_KEY = "format"
_SENDER_MARKER_ID = 1
_SENDER_MARKER_STATES = frozenset({"in_flight", "lock_recorded"})
_TERMINAL_SENDER_RESOLUTIONS = frozenset(
    {
        "determinate_no_start",
        "determinate_completion_failure",
        "verified_terminal_success",
    }
)

_CLAIM_METADATA_DDL = """
CREATE TABLE claim_metadata (
    key TEXT PRIMARY KEY NOT NULL,
    value TEXT NOT NULL
)
"""
_EXECUTION_CLAIMS_DDL = """
CREATE TABLE execution_claims (
    preflight_seal_sha256 TEXT PRIMARY KEY NOT NULL,
    core_preflight_seal_sha256 TEXT NOT NULL,
    candidate_blob_sha256 TEXT NOT NULL,
    transaction_sha256 TEXT NOT NULL,
    authorization_sha256 TEXT NOT NULL,
    baseline_state_identity_sha256 TEXT NOT NULL,
    capacity_response_sha256 TEXT NOT NULL,
    claim_id TEXT NOT NULL UNIQUE,
    claimed_at_utc TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state = 'consumed')
)
"""
_SENDER_IN_FLIGHT_DDL = """
CREATE TABLE sender_in_flight (
    marker_id INTEGER PRIMARY KEY CHECK (marker_id = 1),
    preflight_seal_sha256 TEXT NOT NULL,
    core_preflight_seal_sha256 TEXT NOT NULL,
    candidate_blob_sha256 TEXT NOT NULL,
    transaction_sha256 TEXT NOT NULL,
    authorization_sha256 TEXT NOT NULL,
    baseline_state_identity_sha256 TEXT NOT NULL,
    capacity_response_sha256 TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    attempt_id TEXT NOT NULL,
    incident_id TEXT NOT NULL,
    started_at_utc TEXT NOT NULL,
    evidence_root TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('in_flight', 'lock_recorded')),
    FOREIGN KEY (preflight_seal_sha256)
        REFERENCES execution_claims(preflight_seal_sha256)
)
"""


class ExecutionClaimStoreError(RuntimeError):
    """Raised when claim persistence cannot safely make a decision."""


class ExecutionClaimAlreadyConsumedError(ExecutionClaimStoreError):
    """Raised when a sealed operation already has a durable tombstone."""


class SenderInFlightError(ExecutionClaimStoreError):
    """Raised when another or an abandoned sender boundary is still active."""


def _digest(value: Any, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ExecutionClaimStoreError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _required_text(value: Any, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ExecutionClaimStoreError(f"{label} is required")
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _identity_tuple(
    *,
    preflight_seal_sha256: Any,
    core_preflight_seal_sha256: Any,
    candidate_blob_sha256: Any,
    transaction_sha256: Any,
    authorization_sha256: Any,
    baseline_state_identity_sha256: Any,
    capacity_response_sha256: Any,
) -> tuple[str, ...]:
    return (
        _digest(preflight_seal_sha256, "preflight_seal_sha256"),
        _digest(core_preflight_seal_sha256, "core_preflight_seal_sha256"),
        _digest(candidate_blob_sha256, "candidate_blob_sha256"),
        _digest(transaction_sha256, "transaction_sha256"),
        _digest(authorization_sha256, "authorization_sha256"),
        _digest(
            baseline_state_identity_sha256,
            "baseline_state_identity_sha256",
        ),
        _digest(capacity_response_sha256, "capacity_response_sha256"),
    )


@dataclass(frozen=True)
class ExecutionClaimRecord:
    """Hash-only record for one consumed sealed operation."""

    preflight_seal_sha256: str
    core_preflight_seal_sha256: str
    candidate_blob_sha256: str
    transaction_sha256: str
    authorization_sha256: str
    baseline_state_identity_sha256: str
    capacity_response_sha256: str
    claim_id: str
    claimed_at_utc: str
    state: str = "consumed"
    committed: bool = True

    def __post_init__(self) -> None:
        _identity_tuple(
            preflight_seal_sha256=self.preflight_seal_sha256,
            core_preflight_seal_sha256=self.core_preflight_seal_sha256,
            candidate_blob_sha256=self.candidate_blob_sha256,
            transaction_sha256=self.transaction_sha256,
            authorization_sha256=self.authorization_sha256,
            baseline_state_identity_sha256=self.baseline_state_identity_sha256,
            capacity_response_sha256=self.capacity_response_sha256,
        )
        _required_text(self.claim_id, "claim_id")
        _required_text(self.claimed_at_utc, "claimed_at_utc")
        if self.state != "consumed" or self.committed is not True:
            raise ExecutionClaimStoreError("execution claim is not a committed tombstone")

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": PERSISTENT_EXECUTION_CLAIM_STORE_FORMAT,
            "store_format": PERSISTENT_EXECUTION_CLAIM_STORE_FORMAT,
            "persistence_mode": PERSISTENT_EXECUTION_CLAIM_PERSISTENCE_MODE,
            "state": self.state,
            "committed": self.committed,
            "preflight_seal_sha256": self.preflight_seal_sha256,
            "core_preflight_seal_sha256": self.core_preflight_seal_sha256,
            "candidate_blob_sha256": self.candidate_blob_sha256,
            "transaction_sha256": self.transaction_sha256,
            "authorization_sha256": self.authorization_sha256,
            "baseline_state_identity_sha256": self.baseline_state_identity_sha256,
            "capacity_response_sha256": self.capacity_response_sha256,
            "claim_id": self.claim_id,
            "claimed_at_utc": self.claimed_at_utc,
        }


@dataclass(frozen=True)
class SenderInFlightRecord:
    """Hash-only durable marker for a sender-start crash boundary."""

    preflight_seal_sha256: str
    core_preflight_seal_sha256: str
    candidate_blob_sha256: str
    transaction_sha256: str
    authorization_sha256: str
    baseline_state_identity_sha256: str
    capacity_response_sha256: str
    claim_id: str
    attempt_id: str
    incident_id: str
    started_at_utc: str
    evidence_root: str
    state: str = "in_flight"

    def __post_init__(self) -> None:
        _identity_tuple(
            preflight_seal_sha256=self.preflight_seal_sha256,
            core_preflight_seal_sha256=self.core_preflight_seal_sha256,
            candidate_blob_sha256=self.candidate_blob_sha256,
            transaction_sha256=self.transaction_sha256,
            authorization_sha256=self.authorization_sha256,
            baseline_state_identity_sha256=self.baseline_state_identity_sha256,
            capacity_response_sha256=self.capacity_response_sha256,
        )
        _required_text(self.claim_id, "sender marker claim_id")
        _required_text(self.attempt_id, "sender marker attempt_id")
        _required_text(self.incident_id, "sender marker incident_id")
        _required_text(self.started_at_utc, "sender marker started_at_utc")
        _required_text(self.evidence_root, "sender marker evidence_root")
        if self.state not in _SENDER_MARKER_STATES:
            raise ExecutionClaimStoreError("sender marker state is unsupported")

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": PERSISTENT_EXECUTION_CLAIM_STORE_FORMAT,
            "persistence_mode": PERSISTENT_EXECUTION_CLAIM_PERSISTENCE_MODE,
            "state": self.state,
            "preflight_seal_sha256": self.preflight_seal_sha256,
            "core_preflight_seal_sha256": self.core_preflight_seal_sha256,
            "candidate_blob_sha256": self.candidate_blob_sha256,
            "transaction_sha256": self.transaction_sha256,
            "authorization_sha256": self.authorization_sha256,
            "baseline_state_identity_sha256": self.baseline_state_identity_sha256,
            "capacity_response_sha256": self.capacity_response_sha256,
            "claim_id": self.claim_id,
            "attempt_id": self.attempt_id,
            "incident_id": self.incident_id,
            "started_at_utc": self.started_at_utc,
            "evidence_root": self.evidence_root,
        }


class SenderInFlightHandle:
    """Non-persisted proof held by the process that entered the sender path."""

    __slots__ = ("record", "_terminal_token")

    def __init__(self) -> None:
        raise TypeError("sender handles are issued by PersistentExecutionClaimStore")

    @classmethod
    def _create(
        cls,
        record: SenderInFlightRecord,
        terminal_token: object,
    ) -> "SenderInFlightHandle":
        handle = object.__new__(cls)
        handle.record = record
        handle._terminal_token = terminal_token
        return handle

    def to_dict(self) -> dict[str, Any]:
        return self.record.to_dict()


class PersistentExecutionClaimStore:
    """Installation-stable SQLite claim and sender-marker store.

    Every public operation opens a short-lived connection.  This is deliberate:
    independent coordinator objects and independent processes all contend on
    the same database primary key and marker row.  ``INSERT`` is the authority
    for the one-shot decision; no preceding existence check grants eligibility.
    """

    _CLAIM_COLUMNS = (
        "preflight_seal_sha256",
        "core_preflight_seal_sha256",
        "candidate_blob_sha256",
        "transaction_sha256",
        "authorization_sha256",
        "baseline_state_identity_sha256",
        "capacity_response_sha256",
        "claim_id",
        "claimed_at_utc",
        "state",
    )
    _MARKER_COLUMNS = (
        "marker_id",
        "preflight_seal_sha256",
        "core_preflight_seal_sha256",
        "candidate_blob_sha256",
        "transaction_sha256",
        "authorization_sha256",
        "baseline_state_identity_sha256",
        "capacity_response_sha256",
        "claim_id",
        "attempt_id",
        "incident_id",
        "started_at_utc",
        "evidence_root",
        "state",
    )

    def __init__(self, path: os.PathLike[str] | str):
        try:
            resolved = Path(path).expanduser().resolve()
        except (TypeError, ValueError, OSError) as exc:
            raise ExecutionClaimStoreError("execution claim store path is invalid") from exc
        if resolved.exists() and resolved.is_dir():
            raise ExecutionClaimStoreError("execution claim store path must be a file")
        if resolved.parent.exists() and not resolved.parent.is_dir():
            raise ExecutionClaimStoreError(
                "execution claim store parent is not a directory"
            )
        self.path = resolved
        self._path_existed_at_open = resolved.exists()
        self._terminal_resolution_token = object()
        connection = self._open_connection()
        try:
            self._ensure_schema(connection)
        finally:
            connection.close()

    def _open_connection(self) -> sqlite3.Connection:
        connection: sqlite3.Connection | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(
                str(self.path),
                timeout=SQLITE_BUSY_TIMEOUT_SECONDS,
            )
            connection.execute(
                f"PRAGMA busy_timeout={int(SQLITE_BUSY_TIMEOUT_SECONDS * 1000)}"
            )
            connection.execute("PRAGMA foreign_keys=ON")
            # DELETE journaling is supported by the standard SQLite builds on
            # both macOS and Windows and, with FULL synchronous mode, keeps the
            # committed tombstone durable without leaving a per-install WAL.
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("PRAGMA synchronous=FULL")
            return connection
        except (OSError, sqlite3.Error) as exc:
            if connection is not None:
                try:
                    connection.close()
                except sqlite3.Error:
                    pass
            raise ExecutionClaimStoreError(
                f"execution claim store could not be opened: {exc}"
            ) from exc

    @staticmethod
    def _commit(connection: sqlite3.Connection) -> None:
        connection.commit()

    @staticmethod
    def _rollback(connection: sqlite3.Connection) -> None:
        try:
            connection.rollback()
        except sqlite3.Error:
            pass

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        try:
            connection.execute("BEGIN IMMEDIATE")
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity != ("ok",):
                raise ExecutionClaimStoreError("execution claim store integrity check failed")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            expected_tables = {"claim_metadata", "execution_claims", "sender_in_flight"}
            if version == 0 and not tables:
                if self._path_existed_at_open:
                    raise ExecutionClaimStoreError(
                        "existing execution claim store has no supported schema"
                    )
                self._create_schema(connection)
            else:
                self._validate_schema(connection, version, tables, expected_tables)
            self._commit(connection)
        except ExecutionClaimStoreError:
            self._rollback(connection)
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            self._rollback(connection)
            raise ExecutionClaimStoreError(
                f"execution claim store schema could not be validated: {exc}"
            ) from exc

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        for ddl in (
            _CLAIM_METADATA_DDL,
            _EXECUTION_CLAIMS_DDL,
            _SENDER_IN_FLIGHT_DDL,
        ):
            connection.execute(ddl)
        connection.execute(
            "INSERT INTO claim_metadata(key, value) VALUES (?, ?)",
            (_METADATA_KEY, PERSISTENT_EXECUTION_CLAIM_STORE_FORMAT),
        )
        connection.execute(f"PRAGMA user_version={EXECUTION_CLAIM_SCHEMA_VERSION}")

    def validate_integrity(self) -> None:
        """Revalidate the persistent schema before a write boundary decision."""

        connection = self._open_connection()
        try:
            self._ensure_schema(connection)
        finally:
            connection.close()

    @staticmethod
    def _table_columns(
        connection: sqlite3.Connection,
        table: str,
    ) -> tuple[str, ...]:
        return tuple(
            row[1]
            for row in connection.execute(f"PRAGMA table_info({table})")
        )

    def _validate_schema(
        self,
        connection: sqlite3.Connection,
        version: int,
        tables: set[str],
        expected_tables: set[str],
    ) -> None:
        if version != EXECUTION_CLAIM_SCHEMA_VERSION:
            raise ExecutionClaimStoreError(
                f"execution claim store schema version {version} is unsupported"
            )
        if tables != expected_tables:
            raise ExecutionClaimStoreError(
                f"execution claim store tables differ: {sorted(tables)}"
            )
        objects = connection.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        expected_sql = {
            "claim_metadata": _CLAIM_METADATA_DDL,
            "execution_claims": _EXECUTION_CLAIMS_DDL,
            "sender_in_flight": _SENDER_IN_FLIGHT_DDL,
        }
        if len(objects) != len(expected_sql) or any(
            object_type != "table"
            or name not in expected_sql
            or sql is None
            or " ".join(sql.split()).lower()
            != " ".join(expected_sql[name].split()).lower()
            for object_type, name, sql in objects
        ):
            raise ExecutionClaimStoreError("execution claim store definitions differ")
        metadata = connection.execute(
            "SELECT key, value FROM claim_metadata"
        ).fetchall()
        if metadata != [(_METADATA_KEY, PERSISTENT_EXECUTION_CLAIM_STORE_FORMAT)]:
            raise ExecutionClaimStoreError("execution claim store metadata differs")
        if self._table_columns(connection, "claim_metadata") != ("key", "value"):
            raise ExecutionClaimStoreError("claim metadata schema differs")
        if self._table_columns(connection, "execution_claims") != self._CLAIM_COLUMNS:
            raise ExecutionClaimStoreError("execution claim schema differs")
        if self._table_columns(connection, "sender_in_flight") != self._MARKER_COLUMNS:
            raise ExecutionClaimStoreError("sender marker schema differs")
        primary_key = connection.execute(
            "PRAGMA table_info(execution_claims)"
        ).fetchall()
        if not primary_key or primary_key[0][1] != "preflight_seal_sha256" or primary_key[0][5] != 1:
            raise ExecutionClaimStoreError("execution claim primary key differs")
        unique_indexes = {
            row[1]
            for row in connection.execute("PRAGMA index_list(execution_claims)")
            if row[2]
        }
        claim_id_unique = False
        for index_name in unique_indexes:
            columns = tuple(
                row[2]
                for row in connection.execute(f"PRAGMA index_info({index_name})")
            )
            if columns == ("claim_id",):
                claim_id_unique = True
        if not claim_id_unique:
            raise ExecutionClaimStoreError("execution claim identifier is not unique")

    @staticmethod
    def _claim_from_row(row: tuple[Any, ...]) -> ExecutionClaimRecord:
        return ExecutionClaimRecord(
            preflight_seal_sha256=row[0],
            core_preflight_seal_sha256=row[1],
            candidate_blob_sha256=row[2],
            transaction_sha256=row[3],
            authorization_sha256=row[4],
            baseline_state_identity_sha256=row[5],
            capacity_response_sha256=row[6],
            claim_id=row[7],
            claimed_at_utc=row[8],
            state=row[9],
        )

    @staticmethod
    def _marker_from_row(row: tuple[Any, ...]) -> SenderInFlightRecord:
        return SenderInFlightRecord(
            preflight_seal_sha256=row[1],
            core_preflight_seal_sha256=row[2],
            candidate_blob_sha256=row[3],
            transaction_sha256=row[4],
            authorization_sha256=row[5],
            baseline_state_identity_sha256=row[6],
            capacity_response_sha256=row[7],
            claim_id=row[8],
            attempt_id=row[9],
            incident_id=row[10],
            started_at_utc=row[11],
            evidence_root=row[12],
            state=row[13],
        )

    @staticmethod
    def _claim_select_sql() -> str:
        return "SELECT " + ", ".join(PersistentExecutionClaimStore._CLAIM_COLUMNS)

    @staticmethod
    def _marker_select_sql() -> str:
        return "SELECT " + ", ".join(PersistentExecutionClaimStore._MARKER_COLUMNS)

    @staticmethod
    def _claim_bindings_match(
        record: ExecutionClaimRecord,
        identities: tuple[str, ...],
    ) -> bool:
        return (
            record.preflight_seal_sha256,
            record.core_preflight_seal_sha256,
            record.candidate_blob_sha256,
            record.transaction_sha256,
            record.authorization_sha256,
            record.baseline_state_identity_sha256,
            record.capacity_response_sha256,
        ) == identities

    def _assert_marker_claim_binding(
        self,
        connection: sqlite3.Connection,
        marker: SenderInFlightRecord,
    ) -> None:
        claim_row = connection.execute(
            self._claim_select_sql()
            + " FROM execution_claims WHERE preflight_seal_sha256 = ?",
            (marker.preflight_seal_sha256,),
        ).fetchone()
        if claim_row is None:
            raise ExecutionClaimStoreError(
                "sender marker does not reference a committed tombstone"
            )
        claim = self._claim_from_row(claim_row)
        if (
            not self._claim_bindings_match(
                claim,
                (
                    marker.preflight_seal_sha256,
                    marker.core_preflight_seal_sha256,
                    marker.candidate_blob_sha256,
                    marker.transaction_sha256,
                    marker.authorization_sha256,
                    marker.baseline_state_identity_sha256,
                    marker.capacity_response_sha256,
                ),
            )
            or claim.claim_id != marker.claim_id
        ):
            raise ExecutionClaimStoreError(
                "sender marker bindings differ from the committed tombstone"
            )

    def _read_current_marker(
        self,
        connection: sqlite3.Connection,
    ) -> SenderInFlightRecord:
        row = connection.execute(
            self._marker_select_sql()
            + " FROM sender_in_flight WHERE marker_id = ?",
            (_SENDER_MARKER_ID,),
        ).fetchone()
        if row is None:
            raise ExecutionClaimStoreError("sender marker is no longer active")
        return self._marker_from_row(row)

    def _delete_marker(
        self,
        connection: sqlite3.Connection,
        marker: SenderInFlightRecord,
        *,
        allowed_states: frozenset[str],
    ) -> None:
        current = self._read_current_marker(connection)
        if current != marker:
            raise ExecutionClaimStoreError("sender marker changed before resolution")
        if current.state not in allowed_states:
            raise ExecutionClaimStoreError(
                f"sender marker state {current.state!r} cannot be resolved here"
            )
        self._assert_marker_claim_binding(connection, current)
        connection.execute(
            "DELETE FROM sender_in_flight WHERE marker_id = ?",
            (_SENDER_MARKER_ID,),
        )

    def consume(
        self,
        *,
        preflight_seal_sha256: str,
        core_preflight_seal_sha256: str,
        candidate_blob_sha256: str,
        transaction_sha256: str,
        authorization_sha256: str,
        baseline_state_identity_sha256: str,
        capacity_response_sha256: str,
    ) -> ExecutionClaimRecord:
        """Atomically insert and commit one tombstone.

        The unique primary key is intentionally attempted directly.  A
        duplicate is rejected after the transaction rolls back, and any
        storage/commit error is propagated as a fail-closed store error.
        """

        identities = _identity_tuple(
            preflight_seal_sha256=preflight_seal_sha256,
            core_preflight_seal_sha256=core_preflight_seal_sha256,
            candidate_blob_sha256=candidate_blob_sha256,
            transaction_sha256=transaction_sha256,
            authorization_sha256=authorization_sha256,
            baseline_state_identity_sha256=baseline_state_identity_sha256,
            capacity_response_sha256=capacity_response_sha256,
        )
        record = ExecutionClaimRecord(
            preflight_seal_sha256=identities[0],
            core_preflight_seal_sha256=identities[1],
            candidate_blob_sha256=identities[2],
            transaction_sha256=identities[3],
            authorization_sha256=identities[4],
            baseline_state_identity_sha256=identities[5],
            capacity_response_sha256=identities[6],
            claim_id=uuid4().hex,
            claimed_at_utc=_utc_now(),
        )
        connection = self._open_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT INTO execution_claims(
                        preflight_seal_sha256,
                        core_preflight_seal_sha256,
                        candidate_blob_sha256,
                        transaction_sha256,
                        authorization_sha256,
                        baseline_state_identity_sha256,
                        capacity_response_sha256,
                        claim_id,
                        claimed_at_utc,
                        state
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'consumed')
                    """,
                    (
                        record.preflight_seal_sha256,
                        record.core_preflight_seal_sha256,
                        record.candidate_blob_sha256,
                        record.transaction_sha256,
                        record.authorization_sha256,
                        record.baseline_state_identity_sha256,
                        record.capacity_response_sha256,
                        record.claim_id,
                        record.claimed_at_utc,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                self._rollback(connection)
                existing_connection = self._open_connection()
                try:
                    row = existing_connection.execute(
                        self._claim_select_sql()
                        + " FROM execution_claims WHERE preflight_seal_sha256 = ?",
                        (record.preflight_seal_sha256,),
                    ).fetchone()
                finally:
                    existing_connection.close()
                if row is None:
                    raise ExecutionClaimStoreError(
                        "claim uniqueness failure did not leave a readable tombstone"
                    ) from exc
                existing = self._claim_from_row(row)
                if not self._claim_bindings_match(existing, identities):
                    raise ExecutionClaimStoreError(
                        "same sealed operation has inconsistent bound identities"
                    ) from exc
                raise ExecutionClaimAlreadyConsumedError(
                    "sealed operation already has a committed execution claim"
                ) from exc
            self._commit(connection)
            return record
        except (ExecutionClaimStoreError, ExecutionClaimAlreadyConsumedError):
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            self._rollback(connection)
            raise ExecutionClaimStoreError(
                f"execution claim could not be committed: {exc}"
            ) from exc
        finally:
            connection.close()

    def read_sender_in_flight(self) -> SenderInFlightRecord | None:
        connection = self._open_connection()
        try:
            row = connection.execute(
                self._marker_select_sql()
                + " FROM sender_in_flight WHERE marker_id = ?",
                (_SENDER_MARKER_ID,),
            ).fetchone()
            if row is None:
                return None
            marker = self._marker_from_row(row)
            self._assert_marker_claim_binding(connection, marker)
            return marker
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            raise ExecutionClaimStoreError(
                f"sender marker could not be read: {exc}"
            ) from exc
        finally:
            connection.close()

    def assert_no_sender_in_flight(self) -> None:
        marker = self.read_sender_in_flight()
        if marker is not None:
            raise SenderInFlightError(
                "a sender-start marker is active; read-only diagnosis and recovery are required"
            )

    def mark_sender_in_flight(
        self,
        claim: ExecutionClaimRecord,
        *,
        attempt_id: str,
        incident_id: str,
        evidence_root: str,
    ) -> SenderInFlightHandle:
        if not isinstance(claim, ExecutionClaimRecord):
            raise ExecutionClaimStoreError("sender marker requires a durable execution claim")
        _required_text(attempt_id, "attempt_id")
        _required_text(incident_id, "incident_id")
        _required_text(evidence_root, "evidence_root")
        marker = SenderInFlightRecord(
            preflight_seal_sha256=claim.preflight_seal_sha256,
            core_preflight_seal_sha256=claim.core_preflight_seal_sha256,
            candidate_blob_sha256=claim.candidate_blob_sha256,
            transaction_sha256=claim.transaction_sha256,
            authorization_sha256=claim.authorization_sha256,
            baseline_state_identity_sha256=claim.baseline_state_identity_sha256,
            capacity_response_sha256=claim.capacity_response_sha256,
            claim_id=claim.claim_id,
            attempt_id=attempt_id,
            incident_id=incident_id,
            started_at_utc=_utc_now(),
            evidence_root=evidence_root,
        )
        connection = self._open_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            claim_row = connection.execute(
                self._claim_select_sql()
                + " FROM execution_claims WHERE preflight_seal_sha256 = ?",
                (claim.preflight_seal_sha256,),
            ).fetchone()
            if claim_row is None or self._claim_from_row(claim_row) != claim:
                raise ExecutionClaimStoreError(
                    "sender marker claim does not match the committed tombstone"
                )
            try:
                connection.execute(
                    """
                    INSERT INTO sender_in_flight(
                        marker_id,
                        preflight_seal_sha256,
                        core_preflight_seal_sha256,
                        candidate_blob_sha256,
                        transaction_sha256,
                        authorization_sha256,
                        baseline_state_identity_sha256,
                        capacity_response_sha256,
                        claim_id,
                        attempt_id,
                        incident_id,
                        started_at_utc,
                        evidence_root,
                        state
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'in_flight')
                    """,
                    (
                        _SENDER_MARKER_ID,
                        marker.preflight_seal_sha256,
                        marker.core_preflight_seal_sha256,
                        marker.candidate_blob_sha256,
                        marker.transaction_sha256,
                        marker.authorization_sha256,
                        marker.baseline_state_identity_sha256,
                        marker.capacity_response_sha256,
                        marker.claim_id,
                        marker.attempt_id,
                        marker.incident_id,
                        marker.started_at_utc,
                        marker.evidence_root,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise SenderInFlightError(
                    "another sender-start marker is already active"
                ) from exc
            self._commit(connection)
            return SenderInFlightHandle._create(
                marker,
                self._terminal_resolution_token,
            )
        except (ExecutionClaimStoreError, SenderInFlightError):
            self._rollback(connection)
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            self._rollback(connection)
            raise ExecutionClaimStoreError(
                f"sender-start marker could not be committed: {exc}"
            ) from exc
        finally:
            connection.close()

    def mark_sender_lock_recorded(self, marker: SenderInFlightRecord) -> SenderInFlightRecord:
        if not isinstance(marker, SenderInFlightRecord):
            raise ExecutionClaimStoreError("lock transition requires a sender marker")
        connection = self._open_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = self._read_current_marker(connection)
            if current != marker:
                raise ExecutionClaimStoreError("sender marker changed before lock transition")
            self._assert_marker_claim_binding(connection, current)
            connection.execute(
                "UPDATE sender_in_flight SET state = 'lock_recorded' WHERE marker_id = ?",
                (_SENDER_MARKER_ID,),
            )
            self._commit(connection)
            return SenderInFlightRecord(**{**marker.__dict__, "state": "lock_recorded"})
        except ExecutionClaimStoreError:
            self._rollback(connection)
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            self._rollback(connection)
            raise ExecutionClaimStoreError(
                f"sender marker lock transition could not be committed: {exc}"
            ) from exc
        finally:
            connection.close()

    def resolve_sender_terminal(
        self,
        handle: SenderInFlightHandle,
        *,
        resolution: str,
    ) -> None:
        if (
            not isinstance(handle, SenderInFlightHandle)
            or handle._terminal_token is not self._terminal_resolution_token
        ):
            raise ExecutionClaimStoreError(
                "sender terminal resolution requires the live-process sender handle"
            )
        if resolution not in _TERMINAL_SENDER_RESOLUTIONS:
            raise ExecutionClaimStoreError("sender terminal resolution is unsupported")
        connection = self._open_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._delete_marker(
                connection,
                handle.record,
                allowed_states=frozenset({"in_flight"}),
            )
            self._commit(connection)
        except ExecutionClaimStoreError:
            self._rollback(connection)
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            self._rollback(connection)
            raise ExecutionClaimStoreError(
                f"sender marker resolution could not be committed: {exc}"
            ) from exc
        finally:
            connection.close()

    def resolve_sender_after_diagnostic(
        self,
        marker: SenderInFlightRecord,
        *,
        lock_record: IndeterminateWriteLockRecord,
    ) -> None:
        """Resolve only after the existing global lock was explicitly cleared."""

        if not isinstance(marker, SenderInFlightRecord):
            raise ExecutionClaimStoreError(
                "diagnostic sender resolution requires a persisted sender marker"
            )
        if not isinstance(lock_record, IndeterminateWriteLockRecord):
            raise ExecutionClaimStoreError(
                "diagnostic sender resolution requires a typed lock record"
            )
        if (
            lock_record.state != "cleared"
            or lock_record.incident_id != marker.incident_id
            or lock_record.attempt_id != marker.attempt_id
        ):
            raise ExecutionClaimStoreError(
                "cleared lock does not bind the original sender incident and attempt"
            )
        connection = self._open_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._delete_marker(
                connection,
                marker,
                allowed_states=frozenset({"in_flight", "lock_recorded"}),
            )
            self._commit(connection)
        except ExecutionClaimStoreError:
            self._rollback(connection)
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            self._rollback(connection)
            raise ExecutionClaimStoreError(
                f"diagnostic sender resolution could not be committed: {exc}"
            ) from exc
        finally:
            connection.close()


__all__ = [
    "EXECUTION_CLAIM_SCHEMA_VERSION",
    "ExecutionClaimAlreadyConsumedError",
    "ExecutionClaimRecord",
    "ExecutionClaimStoreError",
    "PERSISTENT_EXECUTION_CLAIM_PERSISTENCE_MODE",
    "PERSISTENT_EXECUTION_CLAIM_STORE_FORMAT",
    "PersistentExecutionClaimStore",
    "SenderInFlightHandle",
    "SenderInFlightError",
    "SenderInFlightRecord",
]
