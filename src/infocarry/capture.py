"""Lossless, non-overwriting storage for raw InfoCarry information responses."""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from .device_info import RawInfoResponse


class CaptureError(RuntimeError):
    """Raised when a raw capture cannot be created without data loss."""


class RawInfoCapture:
    """Create a new capture directory and persist responses before parsing."""

    def __init__(self, directory: Path):
        self.directory = directory
        self._responses: List[Dict[str, Any]] = []
        self._created_at = datetime.now(timezone.utc).isoformat()
        self._complete = False

    @classmethod
    def create(cls, directory: Path) -> "RawInfoCapture":
        path = directory.expanduser().resolve()
        try:
            path.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise CaptureError(f"refusing to overwrite existing capture path: {path}") from exc
        except OSError as exc:
            raise CaptureError(f"could not create capture directory {path}: {exc}") from exc
        capture = cls(path)
        capture._write_manifest("in_progress")
        return capture

    def save(self, response: RawInfoResponse) -> Dict[str, Any]:
        if self._complete:
            raise CaptureError("capture has already been finalized")
        filename = f"command-{response.command:04x}-{response.kind}.bin"
        path = self.directory / filename
        try:
            with path.open("xb") as output:
                output.write(response.data)
                output.flush()
                os.fsync(output.fileno())
        except OSError as exc:
            raise CaptureError(f"could not preserve raw response {path}: {exc}") from exc
        entry = {
            "command": f"0x{response.command:04x}",
            "kind": response.kind,
            "filename": filename,
            "length": len(response.data),
            "sha256": hashlib.sha256(response.data).hexdigest(),
        }
        self._responses.append(entry)
        self._write_manifest("in_progress")
        return dict(entry)

    def finalize(self) -> None:
        if self._complete:
            return
        self._write_manifest("complete")
        self._complete = True

    def _write_manifest(self, state: str) -> None:
        manifest = {
            "format": "infocarry-raw-info-v1",
            "state": state,
            "created_at_utc": self._created_at,
            "device": {"vendor_id": "0x054c", "product_id": "0x001e"},
            "responses": self._responses,
        }
        temporary = self.directory / "manifest.json.tmp"
        destination = self.directory / "manifest.json"
        try:
            temporary.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.replace(destination)
        except OSError as exc:
            raise CaptureError(f"could not update capture manifest: {exc}") from exc
