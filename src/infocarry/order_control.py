"""Lossless reader for the legacy ``order.vnw`` control sidecar.

The preserved manager reads this file as an ANSI byte stream.  It skips lines
whose first byte is ``;`` and treats the first ``:``, carriage return, or line
feed as the end of an entry.  The parser mirrors those verified rules while
retaining the original bytes for forensic round-trips.  It performs no device
I/O and does not synthesize transfer names.
"""

from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple


ORDER_CONTROL_PREAMBLE = b";v1.0\n"
ORDER_CONTROL_READ_CHUNK_SIZE = 0x200
ORDER_CONTROL_SPECIAL_EXTENSION = "ecd"


class OrderControlFormatError(ValueError):
    """Raised when an ``order.vnw`` input cannot be represented safely."""


def generated_transfer_basename(
    record_name: str,
    extension: str,
    counter: int,
    *,
    state_byte: int = 0,
) -> str:
    """Render the legacy manager's verified generated basename.

    Static analysis shows a one-based counter and a low-bit gate on the
    in-memory state byte.  When ``state_byte & 0x07`` is zero, the raw
    three-byte extension is used; otherwise the manager substitutes ``ecd``.
    This is a pure naming helper: it does not create files, resolve paths, or
    guess ordering or collision behavior.
    """

    if not isinstance(record_name, str) or not isinstance(extension, str):
        raise OrderControlFormatError("generated-name fields must be strings")
    if "\x00" in record_name or "\x00" in extension:
        raise OrderControlFormatError("generated-name fields cannot contain NUL")
    if not isinstance(counter, int) or isinstance(counter, bool) or counter < 1:
        raise OrderControlFormatError("generated-name counter must be one-based")
    if not isinstance(state_byte, int) or isinstance(state_byte, bool) or not 0 <= state_byte <= 0xFF:
        raise OrderControlFormatError("generated-name state byte must fit one byte")
    selected_extension = (
        extension if (state_byte & 0x07) == 0 else ORDER_CONTROL_SPECIAL_EXTENSION
    )
    return f"{record_name}-{counter}.{selected_extension}"


def select_legacy_transfer_basename(
    record_name: str,
    extension: str,
    candidate_opens_for_read: Callable[[str], bool],
    *,
    state_byte: int = 0,
    maximum_counter: int = 1_000_000,
) -> str:
    """Select the first generated basename rejected by a read-open probe.

    The manager starts at suffix 1, tries each candidate with mode ``"r"``,
    closes successful probes, and uses the first candidate whose probe fails.
    It then opens that path with ``"wb"``.  The callback keeps this helper
    offline and lets a caller model Windows path equivalence explicitly.

    ``maximum_counter`` is a modern safety bound; the recovered legacy loop
    has no comparable bound.  A failed read probe is not proof that a path is
    absent (for example, it could be unreadable), so this function must not be
    treated as an atomic or generally safe file-creation primitive.
    """

    if not callable(candidate_opens_for_read):
        raise OrderControlFormatError("candidate read probe must be callable")
    if (
        not isinstance(maximum_counter, int)
        or isinstance(maximum_counter, bool)
        or maximum_counter < 1
    ):
        raise OrderControlFormatError("maximum counter must be a positive integer")
    for counter in range(1, maximum_counter + 1):
        candidate = generated_transfer_basename(
            record_name,
            extension,
            counter,
            state_byte=state_byte,
        )
        if not candidate_opens_for_read(candidate):
            return candidate
    raise OrderControlFormatError(
        f"no available generated basename within {maximum_counter} candidates"
    )


def _legacy_line_chunks(data: bytes) -> Tuple[bytes, ...]:
    """Split bytes like the DLL's 0x200-byte LF/EOF line reader.

    The old helper returns as soon as it sees LF, reaches 0x200 bytes, or hits
    EOF.  A line longer than 0x200 bytes therefore becomes multiple chunks;
    preserving that quirk is useful when comparing malformed fixtures.
    """

    chunks = []
    offset = 0
    while offset < len(data):
        limit = min(len(data), offset + ORDER_CONTROL_READ_CHUNK_SIZE)
        newline = data.find(b"\n", offset, limit)
        if newline >= 0:
            end = newline + 1
        else:
            end = limit
        chunks.append(data[offset:end])
        offset = end
    return tuple(chunks)


def _legacy_entry(chunk: bytes) -> Optional[bytes]:
    if chunk.startswith(b";"):
        return None
    end = len(chunk)
    for marker in (b":", b"\r", b"\n"):
        position = chunk.find(marker)
        if position >= 0:
            end = min(end, position)
    return chunk[:end]


@dataclass(frozen=True)
class OrderControlFile:
    """A raw ``order.vnw`` image and entries recognized by the legacy reader."""

    raw: bytes
    entries: Sequence[bytes]

    def __post_init__(self) -> None:
        if not isinstance(self.raw, bytes):
            raise OrderControlFormatError("order.vnw raw data must be bytes")
        entries = tuple(self.entries)
        for entry in entries:
            if not isinstance(entry, bytes):
                raise OrderControlFormatError("order.vnw entries must be bytes")
        object.__setattr__(self, "entries", entries)

    def to_bytes(self) -> bytes:
        """Return the exact original bytes, including comments and endings."""

        return self.raw

    def decode_entries(self, encoding: str = "cp932", errors: str = "strict") -> Tuple[str, ...]:
        """Decode recognized entries without changing the preserved raw file."""

        return tuple(entry.decode(encoding, errors) for entry in self.entries)


def parse_order_control(data: bytes) -> OrderControlFile:
    """Parse ``order.vnw`` using the verified legacy line rules."""

    if not isinstance(data, bytes):
        raise OrderControlFormatError("order.vnw input must be bytes")
    entries = tuple(
        entry
        for chunk in _legacy_line_chunks(data)
        for entry in (_legacy_entry(chunk),)
        if entry is not None
    )
    return OrderControlFile(raw=data, entries=entries)
