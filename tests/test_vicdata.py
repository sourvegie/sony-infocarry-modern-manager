import unittest

from infocarry.backup_format import parse_backup_blob
from infocarry.vicdata import (
    OBSERVED_VICDATA_XOR_KEY,
    VicDataError,
    add_file_from_template_vicdata,
    decode_vicdata,
    delete_existing_vicdata,
    encode_vicdata,
    rename_existing_vicdata,
    repack_existing_vicdata,
    xor_vicdata,
)

try:
    from test_backup_format import make_text_blob
except ModuleNotFoundError:
    from tests.test_backup_format import make_text_blob


class VicDataTests(unittest.TestCase):
    def setUp(self):
        self.blob = make_text_blob(b"original")
        self.encoded = xor_vicdata(self.blob)
        self.file_offset = 0xC0

    def test_xor_is_symmetric_and_validates_inputs(self):
        self.assertEqual(xor_vicdata(self.encoded), self.blob)
        self.assertEqual(OBSERVED_VICDATA_XOR_KEY, 0xAA)
        for bad_key in (-1, 256, True, "aa"):
            with self.subTest(key=bad_key), self.assertRaises(VicDataError):
                xor_vicdata(b"data", key=bad_key)
        with self.assertRaises(VicDataError):
            xor_vicdata("not bytes")

    def test_decode_and_encode_are_exact(self):
        parsed = decode_vicdata(self.encoded)
        self.assertEqual(parsed.data, self.blob)
        self.assertEqual(encode_vicdata(parsed.data), self.encoded)

    def test_empty_repack_is_byte_identical(self):
        self.assertEqual(repack_existing_vicdata(self.encoded, {}), self.encoded)

    def test_replaces_existing_payload_through_encoded_layer(self):
        rebuilt = repack_existing_vicdata(
            self.encoded, {self.file_offset: b"a longer replacement"}
        )
        parsed = decode_vicdata(rebuilt)
        record = parsed.record_at(self.file_offset)
        _, payload = parsed.payload_parts(record)
        self.assertEqual(payload, b"a longer replacement")
        self.assertEqual(parsed.paths, parse_backup_blob(self.blob).paths)
        self.assertNotEqual(rebuilt, self.encoded)

    def test_renames_existing_record_through_encoded_layer(self):
        rebuilt = rename_existing_vicdata(self.encoded, self.file_offset, "renamed")
        parsed = decode_vicdata(rebuilt)
        self.assertEqual(parsed.paths[self.file_offset], ("root", "renamed"))
        _, payload = parsed.payload_parts(parsed.record_at(self.file_offset))
        self.assertEqual(payload, b"original")
        self.assertNotEqual(rebuilt, self.encoded)

    def test_rejects_malformed_encoded_or_decoded_data(self):
        with self.assertRaises(VicDataError):
            decode_vicdata(b"not a backup")
        with self.assertRaises(VicDataError):
            encode_vicdata(b"not a backup")

    def test_deletes_existing_file_through_encoded_layer(self):
        rebuilt = delete_existing_vicdata(self.encoded, self.file_offset)
        parsed = decode_vicdata(rebuilt)
        self.assertNotIn(("root", "file.txt"), parsed.paths.values())
        self.assertEqual(len(parsed.records), len(self.parsed_records()) - 1)

    def test_adds_template_file_with_arbitrary_payload_through_encoded_layer(self):
        try:
            from test_backup_duplicate import make_nested_blob
        except ModuleNotFoundError:
            from tests.test_backup_duplicate import make_nested_blob
        encoded = xor_vicdata(make_nested_blob(b"source\r\n"))
        rebuilt = add_file_from_template_vicdata(
            encoded,
            0xC0,
            0x140,
            "new.txt",
            b"new content",
        )
        parsed = decode_vicdata(rebuilt)
        target = next(
            record
            for record in parsed.records
            if parsed.paths.get(record.offset) == ("root", "folder", "new.txt")
        )
        _, payload = parsed.payload_parts(target)
        self.assertEqual(payload, b"new content")

    def parsed_records(self):
        return parse_backup_blob(self.blob).records


if __name__ == "__main__":
    unittest.main()
