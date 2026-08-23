"""Deterministic, read-only reports for parsed SnoopyPro transactions.

This module compares already-parsed byte ranges.  It deliberately does not
load files, open USB, or assign semantic names to unresolved InfoCarry fields;
callers decide how preserved bytes are obtained and where a JSON report goes.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from .usblog import Usblog101bCapture


def _common_prefix_length(left: bytes, right: bytes) -> int:
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[index] == right[index]:
        index += 1
    return index


def _common_suffix_length(left: bytes, right: bytes) -> int:
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[-1 - index] == right[-1 - index]:
        index += 1
    return index


def compare_bytes(reference: bytes, candidate: bytes) -> Mapping[str, Any]:
    """Return a JSON-safe byte comparison without retaining either input."""

    if not isinstance(reference, bytes) or not isinstance(candidate, bytes):
        raise TypeError("reference and candidate must be bytes")

    differing = sum(
        left != right for left, right in zip(reference, candidate)
    ) + abs(len(reference) - len(candidate))
    first_difference = None
    for index, (left, right) in enumerate(zip(reference, candidate)):
        if left != right:
            first_difference = index
            break
    if first_difference is None and len(reference) != len(candidate):
        first_difference = min(len(reference), len(candidate))

    last_difference = None
    for index in range(1, min(len(reference), len(candidate)) + 1):
        if reference[-index] != candidate[-index]:
            last_difference = max(len(reference), len(candidate)) - index
            break
    if last_difference is None and len(reference) != len(candidate):
        last_difference = max(len(reference), len(candidate)) - 1

    return {
        "equal": reference == candidate,
        "reference_length": len(reference),
        "candidate_length": len(candidate),
        "length_delta": len(candidate) - len(reference),
        "reference_sha256": sha256(reference).hexdigest(),
        "candidate_sha256": sha256(candidate).hexdigest(),
        "differing_byte_count": differing,
        "first_difference": first_difference,
        "last_difference": last_difference,
        "common_prefix_length": _common_prefix_length(reference, candidate),
        "common_suffix_length": _common_suffix_length(reference, candidate),
    }


def summarize_capture(capture: Usblog101bCapture) -> Mapping[str, Any]:
    """Return offsets, lengths, staging fields, and hashes for one capture."""

    if not isinstance(capture, Usblog101bCapture):
        raise TypeError("capture must be a Usblog101bCapture")
    return {
        "record_offset": capture.record_offset,
        "command_offset": capture.command_offset,
        "declared_length": capture.declared_length,
        "record_count": len(capture.records),
        "range3_n": capture.range3_n,
        "range3_m": capture.range3_m,
        "range_lengths": list(capture.range_lengths),
        "range_sha256": [sha256(data).hexdigest() for data in capture.ranges],
    }


def compare_captures(
    reference: Usblog101bCapture, candidate: Usblog101bCapture
) -> Mapping[str, Any]:
    """Compare two parsed ordinary-send transactions range by range."""

    if not isinstance(reference, Usblog101bCapture) or not isinstance(
        candidate, Usblog101bCapture
    ):
        raise TypeError("reference and candidate must be Usblog101bCapture values")
    return {
        "reference": summarize_capture(reference),
        "candidate": summarize_capture(candidate),
        "declared_length_delta": candidate.declared_length - reference.declared_length,
        "changed_ranges": [
            index + 1
            for index, (left, right) in enumerate(zip(reference.ranges, candidate.ranges))
            if left != right
        ],
        "ranges": [
            compare_bytes(left, right)
            for left, right in zip(reference.ranges, candidate.ranges)
        ],
    }


__all__ = ["compare_bytes", "compare_captures", "summarize_capture"]
