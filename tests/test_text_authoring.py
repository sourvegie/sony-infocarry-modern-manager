import json
import unittest

from infocarry.text_authoring import (
    TEXT_AUTHORING_FORMAT,
    TextAuthoringError,
    encode_cp932_text,
    preview_decoded_text_replacement,
    preview_text_replacement,
)
from infocarry.vicdata import xor_vicdata

try:
    from test_backup_format import make_text_blob
except ModuleNotFoundError:
    from tests.test_backup_format import make_text_blob


class TextAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.encoded = xor_vicdata(make_text_blob(b"old\r\ntext"))

    def test_strict_cp932_encoding_normalizes_newlines(self):
        result = encode_cp932_text("日本語\nnext\rfinal\r\nend")
        self.assertEqual(result.normalized_text, "日本語\r\nnext\r\nfinal\r\nend")
        self.assertEqual(result.payload, result.normalized_text.encode("cp932"))

    def test_rejects_unsupported_characters_and_nul(self):
        with self.assertRaisesRegex(TextAuthoringError, r"U\+1F600"):
            encode_cp932_text("unsupported 😀")
        with self.assertRaises(TextAuthoringError):
            encode_cp932_text("has\x00nul")

    def test_preview_is_json_safe_and_preserves_wrapper(self):
        report = preview_text_replacement(
            self.encoded, 0xC0, "日本語\nreplacement", max_payload_bytes=128
        )
        json.dumps(report, sort_keys=True)
        self.assertEqual(report["format"], TEXT_AUTHORING_FORMAT)
        self.assertEqual(report["authoring"]["encoding"], "cp932")
        self.assertEqual(report["authoring"]["newline_policy"], "crlf")
        self.assertEqual(
            report["authoring"]["input_utf8_bytes"],
            len("日本語\nreplacement".encode("utf-8")),
        )
        self.assertTrue(report["authoring"]["unsupported_characters_replaced"] is False)
        self.assertTrue(report["capacity"]["encoded_payload_within_limit"])
        self.assertEqual(report["target"]["native_prefix"]["length_bytes"], 32)
        self.assertTrue(report["target"]["native_prefix"]["preserved_exactly"])
        self.assertTrue(report["invariants"]["target_payload_verified"])
        self.assertFalse(report["safety"]["candidate_bytes_included"])

    def test_capacity_rejection_and_non_text_target_rejection(self):
        with self.assertRaises(TextAuthoringError):
            preview_text_replacement(self.encoded, 0xC0, "too long", max_payload_bytes=2)
        with self.assertRaises(TextAuthoringError):
            preview_text_replacement(self.encoded, 0x40, "text")

    def test_decoded_backup_preview_applies_xor_only_in_memory(self):
        decoded = xor_vicdata(self.encoded)
        report = preview_decoded_text_replacement(decoded, 0xC0, "decoded\ntext")
        self.assertEqual(report["target"]["path"], "root\\memo")
        self.assertFalse(report["safety"]["candidate_bytes_included"])


if __name__ == "__main__":
    unittest.main()
