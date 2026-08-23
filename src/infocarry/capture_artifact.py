"""Offline conversion of a native SnoopyPro transaction into an artifact."""

from __future__ import annotations

from pathlib import Path

from .payload_builder import PayloadBuilderError, build_from_observed_capture
from .usblog import UsblogParseError, extract_101b, find_101b_headers
from .write_artifact import WriteArtifactError


class CaptureArtifactError(ValueError):
    """Raised when a native capture cannot produce a verified artifact."""


def preserve_capture_artifact(
    capture_path: Path,
    destination: Path,
    *,
    transaction_index: int = 0,
) -> Path:
    """Extract one ordinary ``0x101b`` transaction and preserve its bytes.

    This operation is entirely offline. The native capture remains untouched;
    the destination must be a new directory and receives the normal
    ``ProspectiveWriteTransaction`` manifest/range files.
    """

    source = capture_path.expanduser().resolve()
    try:
        data = source.read_bytes()
    except OSError as exc:
        raise CaptureArtifactError(f"could not read capture {source}: {exc}") from exc
    try:
        offsets = find_101b_headers(data)
    except (TypeError, UsblogParseError) as exc:
        raise CaptureArtifactError(f"could not inspect capture {source}: {exc}") from exc
    if (
        isinstance(transaction_index, bool)
        or not isinstance(transaction_index, int)
        or transaction_index < 0
        or transaction_index >= len(offsets)
    ):
        raise CaptureArtifactError(
            f"transaction index {transaction_index!r} is outside the {len(offsets)} captured transactions"
        )
    try:
        capture = extract_101b(data, offsets[transaction_index])
        transaction = build_from_observed_capture(capture)
        return transaction.preserve(
            destination,
            source=f"native SnoopyPro capture {source} transaction {transaction_index}",
        )
    except (UsblogParseError, PayloadBuilderError, WriteArtifactError) as exc:
        raise CaptureArtifactError(
            f"capture transaction {transaction_index} is not a verified ordinary candidate: {exc}"
        ) from exc


__all__ = ["CaptureArtifactError", "preserve_capture_artifact"]
