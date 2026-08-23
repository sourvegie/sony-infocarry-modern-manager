"""Byte-exact helpers for the recovered VicTwo model-object boundary.

Static inspection of ``VicTwo.dll`` recovers two useful initializers even
though the higher-level source-node construction is still model-dependent:
the 0x40-byte source object initializer at ``0x10003330`` and the 0x16c-byte
node initializer at ``0x100033a0``.  These helpers expose those bytes for
offline comparison and tests.  They do not construct a transfer payload or
open a device.
"""

from __future__ import annotations


MODEL_SOURCE_SIZE = 0x40
MODEL_NODE_SIZE = 0x16C
MODEL_NODE_SOURCE_OFFSET = 0x04
MODEL_NODE_FLAG_OFFSET = 0x50
MODEL_NODE_TEXT_OFFSET = 0x51
MODEL_NODE_TEXT_SIZE = 0x104
MODEL_NODE_LINK_SENTINEL_OFFSETS = (0x154, 0x158, 0x15C)


class ModelTreeStaticError(ValueError):
    """Raised when a recovered model-object boundary receives bad input."""


def initialize_model_source() -> bytes:
    """Return the exact zero-state source object from ``VicTwo.dll``.

    The overlapping stores intentionally remain in the same order as the
    native routine.  They copy bytes from the embedded ``infoCarry`` and
    version literals plus neutral numeric fields; no semantic names are
    assigned to those fields here.
    """

    source = bytearray(MODEL_SOURCE_SIZE)
    source[0:4] = b"\x00\x00\x00\x00"  # dword at data+0x152f8
    source[4:8] = b"info"  # dword at data+0x152fc
    source[8:10] = b"y\x00"  # word at data+0x15300
    source[9:13] = b" 2.0"  # dword at data+0x152f0
    source[0x0D:0x0F] = b"00"  # word at data+0x152f4
    source[0x10:0x12] = (0x40).to_bytes(2, "little")
    source[0x0E:0x10] = (0x100).to_bytes(2, "little")
    source[0x12:0x14] = (0xFFFF).to_bytes(2, "little")
    source[0x3C:0x40] = (0xFFFFFFFF).to_bytes(4, "little")
    return bytes(source)


def initialize_model_node(source: bytes | bytearray | memoryview) -> bytes:
    """Return one exact zero-state 0x16c-byte node object.

    The caller-supplied source is copied at node offset ``+0x04``.  The
    native initializer then sets the flag byte, clears its 0x104-byte path
    buffer, and writes three unresolved link/count sentinels.  Pointer links
    are intentionally left as zero because the native allocator fills them
    later; this function is a static-layout helper, not a tree builder.
    """

    if not isinstance(source, (bytes, bytearray, memoryview)):
        raise ModelTreeStaticError("model source must be bytes-like")
    raw = bytes(source)
    if len(raw) != MODEL_SOURCE_SIZE:
        raise ModelTreeStaticError(
            f"model source must be exactly {MODEL_SOURCE_SIZE:#x} bytes"
        )
    node = bytearray(MODEL_NODE_SIZE)
    node[MODEL_NODE_SOURCE_OFFSET : MODEL_NODE_SOURCE_OFFSET + MODEL_SOURCE_SIZE] = raw
    node[MODEL_NODE_FLAG_OFFSET] = 0xFF
    # The zero-filled path buffer is explicit for readability and future
    # assertions, even though the bytearray already provides those bytes.
    node[MODEL_NODE_TEXT_OFFSET : MODEL_NODE_TEXT_OFFSET + MODEL_NODE_TEXT_SIZE] = bytes(
        MODEL_NODE_TEXT_SIZE
    )
    for offset in MODEL_NODE_LINK_SENTINEL_OFFSETS:
        node[offset : offset + 4] = (0xFFFFFFFF).to_bytes(4, "little")
    return bytes(node)


__all__ = [
    "MODEL_NODE_FLAG_OFFSET",
    "MODEL_NODE_LINK_SENTINEL_OFFSETS",
    "MODEL_NODE_SIZE",
    "MODEL_NODE_SOURCE_OFFSET",
    "MODEL_NODE_TEXT_OFFSET",
    "MODEL_NODE_TEXT_SIZE",
    "MODEL_SOURCE_SIZE",
    "ModelTreeStaticError",
    "initialize_model_node",
    "initialize_model_source",
]
