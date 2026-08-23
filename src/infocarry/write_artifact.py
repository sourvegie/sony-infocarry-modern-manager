"""Offline-only validation and preservation for prospective write payloads.

This module has no USB dependency, transport protocol, bulk-write method, or
device entry point. It records candidate bytes for comparison with legacy
fixtures before any hardware write implementation is considered.
"""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple

from .protocol import build_command_header


WRITE_COMMAND = 0x101B
FIXED_PREFIX_LENGTH = 0x10000
RANGE_LENGTHS = (0x100, 0x40, 0xFEC0)


class WriteArtifactError(RuntimeError):
    """Raised when prospective bytes are inconsistent or cannot be preserved."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_staging_range(variable_n: int, variable_m: int) -> bytes:
    """Build the verified fixed staging range for an offline candidate.

    Static analysis establishes only this range's framing: big-endian ``N``
    and ``M`` in its first eight bytes, followed by ``0xff`` through the end.
    The helper intentionally does not infer either variable payload or any
    model semantics.
    """

    for value, label in ((variable_n, "N"), (variable_m, "M")):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value <= 0xFFFFFFFF
        ):
            raise WriteArtifactError(
                f"{label} must fit an unsigned 32-bit integer"
            )
    return (
        variable_n.to_bytes(4, "big")
        + variable_m.to_bytes(4, "big")
        + b"\xff" * (RANGE_LENGTHS[2] - 8)
    )


@dataclass(frozen=True)
class ProspectiveWriteTransaction:
    """The eight statically verified ranges of an offline command-0x101b payload."""

    ranges: Tuple[bytes, ...]
    variable_n: int
    variable_m: int

    def __post_init__(self) -> None:
        if len(self.ranges) != 8:
            raise WriteArtifactError(
                f"command 0x101b requires exactly 8 ranges, got {len(self.ranges)}"
            )
        if not 0 <= self.variable_n <= 0xFFFFFFFF:
            raise WriteArtifactError("N must fit an unsigned 32-bit integer")
        if not 0 <= self.variable_m <= 0xFFFFFFFF:
            raise WriteArtifactError("M must fit an unsigned 32-bit integer")

        for index, expected in enumerate(RANGE_LENGTHS):
            actual = len(self.ranges[index])
            if actual != expected:
                raise WriteArtifactError(
                    f"range {index + 1} is {actual} bytes; expected {expected}"
                )

        if len(self.ranges[3]) != self.variable_n:
            raise WriteArtifactError(
                f"range 4 is {len(self.ranges[3])} bytes; N declares {self.variable_n}"
            )

        model_total = sum(len(data) for data in self.ranges[4:])
        if model_total != self.variable_m:
            raise WriteArtifactError(
                f"ranges 5-8 total {model_total} bytes; M declares {self.variable_m}"
            )

        expected_prefix = self.variable_n.to_bytes(4, "big") + self.variable_m.to_bytes(
            4, "big"
        )
        if self.ranges[2][:8] != expected_prefix:
            raise WriteArtifactError(
                "range 3 does not begin with the verified big-endian N/M fields"
            )
        if self.ranges[2][8:] != b"\xff" * (RANGE_LENGTHS[2] - 8):
            raise WriteArtifactError(
                "range 3 bytes after the N/M fields are not the verified 0xff fill"
            )

        declared = FIXED_PREFIX_LENGTH + self.variable_n + self.variable_m
        actual = sum(len(data) for data in self.ranges)
        if declared != actual:
            raise WriteArtifactError(
                f"declared payload is {declared} bytes but ranges total {actual}"
            )
        if declared > 0xFFFFFFFF:
            raise WriteArtifactError("declared payload does not fit the command header")

    @property
    def payload_length(self) -> int:
        return sum(len(data) for data in self.ranges)

    @property
    def command_header(self) -> bytes:
        return build_command_header(WRITE_COMMAND, self.payload_length)

    @property
    def concatenated_sha256(self) -> str:
        digest = hashlib.sha256()
        for data in self.ranges:
            digest.update(data)
        return digest.hexdigest()

    def manifest(self, source: str) -> Dict[str, Any]:
        entries = []
        for sequence, data in enumerate(self.ranges, start=1):
            entries.append(
                {
                    "sequence": sequence,
                    "filename": f"range-{sequence:02d}.bin",
                    "length": len(data),
                    "sha256": _sha256(data),
                }
            )
        return {
            "format": "infocarry-prospective-write-v1",
            "state": "offline_only",
            "usb_transmission_performed": False,
            "source": source,
            "command": f"0x{WRITE_COMMAND:04x}",
            "command_header_hex": self.command_header.hex(),
            "payload_length": self.payload_length,
            "variable_n": self.variable_n,
            "variable_m": self.variable_m,
            "concatenated_sha256": self.concatenated_sha256,
            "ranges": entries,
        }

    def preserve(self, directory: Path, source: str) -> Path:
        """Write a new offline artifact directory without replacing any path."""

        if not source:
            raise WriteArtifactError("source provenance must not be empty")
        destination = directory.expanduser().resolve()
        try:
            destination.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise WriteArtifactError(
                f"refusing to overwrite existing artifact path: {destination}"
            ) from exc
        except OSError as exc:
            raise WriteArtifactError(
                f"could not create artifact directory {destination}: {exc}"
            ) from exc

        try:
            for sequence, data in enumerate(self.ranges, start=1):
                path = destination / f"range-{sequence:02d}.bin"
                with path.open("xb") as output:
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
            manifest_path = destination / "manifest.json"
            with manifest_path.open("x", encoding="utf-8") as output:
                json.dump(self.manifest(source), output, indent=2, sort_keys=True)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
        except OSError as exc:
            raise WriteArtifactError(
                f"could not preserve prospective artifact in {destination}: {exc}"
            ) from exc
        return destination


def load_preserved_artifact(directory: Path) -> ProspectiveWriteTransaction:
    """Load and re-verify one offline prospective transaction artifact.

    The loader accepts only the manifest format emitted by
    :meth:`ProspectiveWriteTransaction.preserve`. It verifies every range
    filename, length, SHA-256, staging field, and aggregate hash before
    returning bytes to a future explicitly authorized sender. It performs no
    USB operation.
    """

    root = directory.expanduser().resolve()
    manifest_path = root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WriteArtifactError(
            f"could not read prospective artifact manifest: {exc}"
        ) from exc
    if manifest.get("format") != "infocarry-prospective-write-v1":
        raise WriteArtifactError(
            "source is not an InfoCarry prospective-write artifact"
        )
    if manifest.get("state") != "offline_only":
        raise WriteArtifactError("prospective artifact is not marked offline_only")
    if manifest.get("usb_transmission_performed") is not False:
        raise WriteArtifactError(
            "prospective artifact does not prove zero USB transmission"
        )
    entries = manifest.get("ranges")
    if not isinstance(entries, list) or len(entries) != 8:
        raise WriteArtifactError("prospective artifact must contain eight ranges")

    ranges = []
    for expected_sequence, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or entry.get("sequence") != expected_sequence:
            raise WriteArtifactError("prospective artifact range sequence is invalid")
        filename = entry.get("filename")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise WriteArtifactError("prospective artifact filename is not simple")
        path = root / filename
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise WriteArtifactError(
                f"could not read prospective range {path}: {exc}"
            ) from exc
        if len(data) != entry.get("length"):
            raise WriteArtifactError(
                f"prospective range {path} length does not match manifest"
            )
        if _sha256(data) != entry.get("sha256"):
            raise WriteArtifactError(
                f"prospective range {path} SHA-256 does not match manifest"
            )
        ranges.append(data)

    try:
        transaction = ProspectiveWriteTransaction(
            ranges=tuple(ranges),
            variable_n=manifest["variable_n"],
            variable_m=manifest["variable_m"],
        )
    except (KeyError, TypeError, WriteArtifactError) as exc:
        raise WriteArtifactError(
            f"prospective artifact failed structural validation: {exc}"
        ) from exc
    if transaction.concatenated_sha256 != manifest.get("concatenated_sha256"):
        raise WriteArtifactError(
            "prospective artifact aggregate SHA-256 does not match manifest"
        )
    if transaction.payload_length != manifest.get("payload_length"):
        raise WriteArtifactError(
            "prospective artifact payload length does not match manifest"
        )
    return transaction


__all__ = [
    "ProspectiveWriteTransaction",
    "WriteArtifactError",
    "build_staging_range",
    "load_preserved_artifact",
]
