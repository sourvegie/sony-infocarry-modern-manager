import unittest

from infocarry.model_layout import (
    ModelLayoutError,
    model_node_contribution,
    range8_payload_length,
    round_up_4,
)


class ModelLayoutTests(unittest.TestCase):
    def test_ordinary_alignment_matches_builder_formula(self):
        self.assertEqual(round_up_4(0), 0)
        self.assertEqual(round_up_4(1), 4)
        self.assertEqual(round_up_4(4), 4)
        self.assertEqual(round_up_4(5), 8)

    def test_node_contribution_includes_header_and_fixed_overhead(self):
        self.assertEqual(model_node_contribution(0), 0x64)
        self.assertEqual(model_node_contribution(4), 0x68)
        self.assertEqual(model_node_contribution(5), 0x6C)

    def test_range8_formula_has_four_byte_minimum_padding(self):
        self.assertEqual(range8_payload_length(0), 4)
        self.assertEqual(range8_payload_length(1), 4)
        self.assertEqual(range8_payload_length(4), 8)
        self.assertEqual(range8_payload_length(7), 8)
        self.assertEqual(range8_payload_length(8), 12)

    def test_rejects_negative_non_integer_and_boolean_lengths(self):
        for function in (round_up_4, model_node_contribution, range8_payload_length):
            for value in (-1, True, "4"):
                with self.subTest(function=function.__name__, value=value):
                    with self.assertRaises(ModelLayoutError):
                        function(value)


if __name__ == "__main__":
    unittest.main()
