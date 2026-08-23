"""Explicit offline construction of the recovered model-range grammar.

Static analysis recovered the *boundary* of the manager's recursive model
builder, but not the code that turns a VICDATA tree into its internal nodes.
This module therefore accepts those internal node bytes and the already
prepared variable data explicitly.  It serializes only rules that are
verified: the fixed legacy prefix, child/sibling order, and ``0xff``
four-byte alignment.  It never reads a device, parses a manager file, or
pretends to infer unresolved source fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from .model_layout import round_up_4
from .view_wrapper import (
    LEGACY_INTERNAL_REQUIRED_SIZE,
    ViewWrapperError,
    serialize_legacy_prefix,
)


MODEL_NODE_FLAG_OFFSET = 0x04
MODEL_NODE_PREFIX_NIBBLE_OFFSET = 0x19
MODEL_NODE_TEXT_OFFSET = 0x51
MODEL_NODE_EMPTY_PREFIX_LENGTH = 0x10
MODEL_NODE_ALIGNMENT_BYTE = 0xFF


class ModelRangeError(ValueError):
    """Raised when an explicit model node cannot be serialized safely."""


def _bytes(value: bytes | bytearray | memoryview, label: str) -> bytes:
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise ModelRangeError(f"{label} must be bytes-like")
    return bytes(value)


@dataclass(frozen=True)
class ExplicitModelNode:
    """One caller-supplied node for the recovered append grammar.

    ``internal_object`` is the legacy in-memory object prefix.  Its source
    construction remains unresolved, so callers must provide it rather than
    passing a user-facing record and expecting conversion here.  Likewise,
    ``variable_data`` is the exact byte sequence selected by the caller after
    applying any manager-specific length/path rules.

    Children are emitted depth-first before ``sibling``.  A node whose legacy
    flag has bit ``0x10`` set is skipped, matching the helper's verified gate;
    its descendants are not silently serialized because their traversal
    relationship is an unresolved manager semantic.
    """

    internal_object: bytes
    variable_data: bytes = b""
    prefix_length: Optional[int] = None
    children: Tuple["ExplicitModelNode", ...] = ()
    sibling: Optional["ExplicitModelNode"] = None

    def __post_init__(self) -> None:
        internal = _bytes(self.internal_object, "internal_object")
        variable = _bytes(self.variable_data, "variable_data")
        if len(internal) < LEGACY_INTERNAL_REQUIRED_SIZE:
            raise ModelRangeError(
                f"internal_object must contain at least {LEGACY_INTERNAL_REQUIRED_SIZE:#x} bytes"
            )
        if self.prefix_length is not None:
            _validate_prefix_length(self.prefix_length)
        if not isinstance(self.children, tuple):
            raise ModelRangeError("children must be a tuple of ExplicitModelNode values")
        if any(not isinstance(child, ExplicitModelNode) for child in self.children):
            raise ModelRangeError("children must contain ExplicitModelNode values")
        if self.sibling is not None and not isinstance(
            self.sibling, ExplicitModelNode
        ):
            raise ModelRangeError("sibling must be an ExplicitModelNode or None")
        object.__setattr__(self, "internal_object", internal)
        object.__setattr__(self, "variable_data", variable)


def _validate_prefix_length(prefix_length: int) -> None:
    if (
        isinstance(prefix_length, bool)
        or not isinstance(prefix_length, int)
        or prefix_length < MODEL_NODE_EMPTY_PREFIX_LENGTH
        or prefix_length % 4
    ):
        raise ModelRangeError(
            "prefix_length must be a multiple of four of at least 0x10"
        )


def infer_prefix_length(internal_object: bytes | bytearray | memoryview) -> int:
    """Apply the observed prefix selector without naming its semantic field."""

    source = _bytes(internal_object, "internal_object")
    if len(source) < MODEL_NODE_PREFIX_NIBBLE_OFFSET + 1:
        raise ModelRangeError("internal_object is too short for the prefix selector")
    selected = (source[MODEL_NODE_PREFIX_NIBBLE_OFFSET] & 0x0F) << 4
    return selected or MODEL_NODE_EMPTY_PREFIX_LENGTH


def serialize_explicit_model_node(node: ExplicitModelNode) -> bytes:
    """Serialize one node and its descendants using the verified grammar."""

    if not isinstance(node, ExplicitModelNode):
        raise ModelRangeError("node must be an ExplicitModelNode")
    if node.internal_object[MODEL_NODE_FLAG_OFFSET] & 0x10:
        return b""

    prefix_length = (
        infer_prefix_length(node.internal_object)
        if node.prefix_length is None
        else node.prefix_length
    )
    try:
        prefix = serialize_legacy_prefix(node.internal_object, prefix_length)
    except ViewWrapperError as exc:
        raise ModelRangeError(str(exc)) from exc

    result = bytearray(prefix)
    result.extend(node.variable_data)
    aligned_length = round_up_4(len(result))
    result.extend(bytes([MODEL_NODE_ALIGNMENT_BYTE]) * (aligned_length - len(result)))
    for child in node.children:
        result.extend(serialize_explicit_model_node(child))
    if node.sibling is not None:
        result.extend(serialize_explicit_model_node(node.sibling))
    return bytes(result)


def serialize_explicit_model_range(
    roots: Sequence[ExplicitModelNode], *, expected_length: Optional[int] = None
) -> bytes:
    """Serialize an explicit forest for use as candidate range 8 bytes.

    ``expected_length`` is an optional comparison guard.  It is useful when a
    caller is checking a candidate against a captured allocation formula; it
    does not make the candidate device-compatible by itself.
    """

    if not isinstance(roots, (tuple, list)):
        raise ModelRangeError("roots must be a tuple or list of ExplicitModelNode values")
    if any(not isinstance(root, ExplicitModelNode) for root in roots):
        raise ModelRangeError("roots must contain ExplicitModelNode values")
    result = b"".join(serialize_explicit_model_node(root) for root in roots)
    if expected_length is not None:
        if (
            isinstance(expected_length, bool)
            or not isinstance(expected_length, int)
            or expected_length < 0
        ):
            raise ModelRangeError("expected_length must be a non-negative integer")
        if len(result) != expected_length:
            raise ModelRangeError(
                f"serialized model range is {len(result)} bytes; expected {expected_length}"
            )
    return result


__all__ = [
    "ExplicitModelNode",
    "MODEL_NODE_ALIGNMENT_BYTE",
    "MODEL_NODE_EMPTY_PREFIX_LENGTH",
    "MODEL_NODE_FLAG_OFFSET",
    "MODEL_NODE_PREFIX_NIBBLE_OFFSET",
    "MODEL_NODE_TEXT_OFFSET",
    "ModelRangeError",
    "infer_prefix_length",
    "serialize_explicit_model_node",
    "serialize_explicit_model_range",
]
