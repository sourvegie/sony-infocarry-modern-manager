"""Verified size formulas recovered from the legacy model builder.

These helpers intentionally calculate lengths only.  The legacy builder also
creates headers, paths, checksums, and model records whose semantics are not
fully recovered, so no function here emits a device payload.
"""


class ModelLayoutError(ValueError):
    """Raised when a recovered model-length formula receives an unsafe value."""


def _require_nonnegative_int(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ModelLayoutError(f"{label} must be a non-negative integer")


def round_up_4(length: int) -> int:
    """Return the legacy builder's ordinary 4-byte alignment of ``length``."""

    _require_nonnegative_int(length, "length")
    return ((length + 3) // 4) * 4


def model_node_contribution(node_length: int) -> int:
    """Return the observed size contribution for one admitted model node.

    Static control flow at ``VicTwo.dll`` ``0x10004925``–``0x10004959`` adds
    ``0x24`` to the node length, rounds that value up to four bytes, then adds
    a fixed ``0x40`` overhead.  This is an allocation-size formula, not a
    semantic description of the resulting bytes.
    """

    _require_nonnegative_int(node_length, "node length")
    return round_up_4(node_length + 0x24) + 0x40


def range8_payload_length(field_34: int) -> int:
    """Return the distinct range-8 length formula observed in the worker.

    At ``VicTwo.dll`` ``0x10005238`` the worker computes
    ``4 * floor(field(+0x34) / 4) + 4``.  Unlike ordinary alignment, this
    intentionally adds four bytes even when ``field_34`` is already aligned.
    """

    _require_nonnegative_int(field_34, "field(+0x34)")
    return (field_34 // 4) * 4 + 4


__all__ = [
    "ModelLayoutError",
    "model_node_contribution",
    "range8_payload_length",
    "round_up_4",
]
