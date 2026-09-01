"""Shared, framework-independent safety vocabulary for Experimental transfer.

The P17 runner remains the enforcement point.  This module gives the Library
review and tests one stable inventory of terminal boundaries so product copy
cannot accidentally omit a failure class or imply retry/recovery behavior.
It does not perform device access or replace any runner gate.
"""

from __future__ import annotations

from typing import Any


EXPERIMENTAL_FAILURE_BOUNDARIES = (
    "stale_or_future_backup",
    "wrong_device",
    "target_conflict",
    "capacity_failure_or_unknown",
    "package_or_catalog_drift",
    "candidate_or_transaction_mismatch",
    "authorization_or_seal_mismatch",
    "pre_transfer_cancellation",
    "timeout_disconnect_or_missing_completion",
    "malformed_or_nonzero_completion",
    "multiple_logical_sends",
    "failed_post_backup",
    "semantic_readback_mismatch",
    "wrapper_verification_failure",
    "automatic_retry",
)


def experimental_safety_contract() -> dict[str, Any]:
    """Return the reviewed contract inventory for hash-only reports."""

    return {
        "fresh_complete_backup": "required before every live attempt",
        "immediate_revalidation": "required before sender construction",
        "maximum_logical_sender_calls": 1,
        "accepted_completion": "0x0000",
        "automatic_retry_allowed": False,
        "post_operation_backup": "complete and independently verified",
        "read_back": "independent candidate-core reconciliation required",
        "indeterminate_outcome": "stop and diagnose read-only; never retry",
        "terminal_failure_boundaries": list(EXPERIMENTAL_FAILURE_BOUNDARIES),
    }


__all__ = ["EXPERIMENTAL_FAILURE_BOUNDARIES", "experimental_safety_contract"]
