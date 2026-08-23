import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from infocarry.capture import CaptureError, RawInfoCapture
from infocarry.device_info import RawInfoResponse


class CaptureTests(unittest.TestCase):
    def test_raw_response_is_preserved_with_hash_before_finalize(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "new-capture"
            capture = RawInfoCapture.create(destination)
            payload = bytes(range(64))
            entry = capture.save(
                RawInfoResponse(0x18, "configuration", payload)
            )
            raw_path = destination / "command-0018-configuration.bin"
            self.assertEqual(raw_path.read_bytes(), payload)
            self.assertEqual(entry["length"], 64)
            self.assertEqual(entry["sha256"], hashlib.sha256(payload).hexdigest())
            in_progress = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(in_progress["state"], "in_progress")
            self.assertEqual(in_progress["responses"], [entry])

            capture.finalize()
            complete = json.loads((destination / "manifest.json").read_text())
            self.assertEqual(complete["state"], "complete")

    def test_existing_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "existing"
            destination.mkdir()
            sentinel = destination / "keep.txt"
            sentinel.write_text("preserve me")
            with self.assertRaises(CaptureError):
                RawInfoCapture.create(destination)
            self.assertEqual(sentinel.read_text(), "preserve me")


if __name__ == "__main__":
    unittest.main()
