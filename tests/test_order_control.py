import unittest

from infocarry.order_control import (
    ORDER_CONTROL_PREAMBLE,
    OrderControlFormatError,
    generated_transfer_basename,
    parse_order_control,
    select_legacy_transfer_basename,
)


class OrderControlTests(unittest.TestCase):
    def test_reader_skips_comments_and_strips_verified_delimiters(self):
        raw = (
            ORDER_CONTROL_PREAMBLE
            + b"first.txt\n"
            + b"second.txt\r\n"
            + b"metadata.txt:ignored\n"
            + b";comment\n"
            + b"\n"
        )
        parsed = parse_order_control(raw)
        self.assertEqual(
            parsed.entries,
            (b"first.txt", b"second.txt", b"metadata.txt", b""),
        )
        self.assertEqual(parsed.decode_entries(), ("first.txt", "second.txt", "metadata.txt", ""))
        self.assertEqual(parsed.to_bytes(), raw)

    def test_reader_accepts_eof_without_final_newline(self):
        raw = b";v1.0\nmanual\\chapter-1.txt"
        parsed = parse_order_control(raw)
        self.assertEqual(parsed.entries, (b"manual\\chapter-1.txt",))
        self.assertEqual(parsed.to_bytes(), raw)

    def test_reader_preserves_legacy_0x200_chunk_boundary(self):
        raw = b"A" * 0x200 + b"\nnext\n"
        parsed = parse_order_control(raw)
        self.assertEqual(parsed.entries, (b"A" * 0x200, b"", b"next"))

    def test_parser_rejects_non_bytes(self):
        with self.assertRaises(OrderControlFormatError):
            parse_order_control(";v1.0\n")

    def test_generated_basename_uses_raw_extension_for_zero_state_mask(self):
        self.assertEqual(
            generated_transfer_basename("memo", "txt", 1), "memo-1.txt"
        )
        self.assertEqual(
            generated_transfer_basename("memo", "bmp", 42, state_byte=0x08),
            "memo-42.bmp",
        )

    def test_generated_basename_uses_ecd_for_low_state_bits(self):
        self.assertEqual(
            generated_transfer_basename("memo", "txt", 3, state_byte=0x01),
            "memo-3.ecd",
        )
        self.assertEqual(
            generated_transfer_basename("memo", "txt", 3, state_byte=0x07),
            "memo-3.ecd",
        )

    def test_generated_basename_rejects_unsafe_scalar_inputs(self):
        for args in (("memo", "txt", 0), ("memo", "txt", -1), ("memo", "txt", True)):
            with self.subTest(args=args):
                with self.assertRaises(OrderControlFormatError):
                    generated_transfer_basename(*args)
        with self.assertRaises(OrderControlFormatError):
            generated_transfer_basename("memo\x00", "txt", 1)
        with self.assertRaises(OrderControlFormatError):
            generated_transfer_basename("memo", "txt", 1, state_byte=0x100)

    def test_collision_policy_selects_first_failed_read_probe(self):
        probed = []

        def opens_for_read(candidate):
            probed.append(candidate)
            return candidate in {"memo-1.txt", "memo-2.txt"}

        selected = select_legacy_transfer_basename(
            "memo", "txt", opens_for_read
        )
        self.assertEqual(selected, "memo-3.txt")
        self.assertEqual(
            probed,
            ["memo-1.txt", "memo-2.txt", "memo-3.txt"],
        )

    def test_collision_policy_applies_ecd_branch_and_safety_bound(self):
        selected = select_legacy_transfer_basename(
            "memo",
            "txt",
            lambda candidate: candidate == "memo-1.ecd",
            state_byte=0x01,
        )
        self.assertEqual(selected, "memo-2.ecd")
        with self.assertRaises(OrderControlFormatError):
            select_legacy_transfer_basename(
                "memo",
                "txt",
                lambda candidate: True,
                maximum_counter=2,
            )
        with self.assertRaises(OrderControlFormatError):
            select_legacy_transfer_basename(
                "memo", "txt", lambda candidate: False, maximum_counter=0
            )


if __name__ == "__main__":
    unittest.main()
