import unittest

from infocarry.model_range import (
    ExplicitModelNode,
    ModelRangeError,
    infer_prefix_length,
    serialize_explicit_model_node,
    serialize_explicit_model_range,
)
from infocarry.view_wrapper import calculate_text_view_checksum


def internal(*, prefix_nibble=0, flag=0):
    value = bytearray(0x51)
    value[0x04] = flag
    value[0x19] = prefix_nibble
    value[0x50] = 0
    value[0x44] = 0x12
    value[0x46:0x48] = (0x3456).to_bytes(2, "little")
    value[0x48:0x4C] = (0x789ABCDE).to_bytes(4, "little")
    value[0x4C:0x50] = (0x10203040).to_bytes(4, "little")
    return bytes(value)


class ExplicitModelRangeTests(unittest.TestCase):
    def test_prefix_variable_data_alignment_and_child_order(self):
        child = ExplicitModelNode(internal_object=internal(), variable_data=b"C")
        root = ExplicitModelNode(
            internal_object=internal(prefix_nibble=2),
            variable_data=b"ROOT!",
            children=(child,),
        )
        result = serialize_explicit_model_node(root)
        self.assertEqual(len(result), 0x20 + 5 + 3 + 0x10 + 1 + 3)
        self.assertEqual(result[0x20:0x25], b"ROOT!")
        self.assertEqual(result[0x25:0x28], b"\xff" * 3)
        self.assertEqual(result[0x38:0x3C], b"C" + b"\xff" * 3)
        self.assertEqual(
            int.from_bytes(result[0:4], "big"),
            calculate_text_view_checksum(result[:0x20]),
        )

    def test_inferred_zero_selector_uses_empty_prefix(self):
        self.assertEqual(infer_prefix_length(internal()), 0x10)
        result = serialize_explicit_model_node(
            ExplicitModelNode(internal_object=internal(), variable_data=b"")
        )
        self.assertEqual(len(result), 0x10)

    def test_flagged_node_is_skipped_without_guessing_descendants(self):
        node = ExplicitModelNode(
            internal_object=internal(flag=0x10),
            variable_data=b"must-not-appear",
            children=(ExplicitModelNode(internal_object=internal(), variable_data=b"child"),),
        )
        self.assertEqual(serialize_explicit_model_node(node), b"")

    def test_expected_length_and_shape_are_checked(self):
        node = ExplicitModelNode(internal_object=internal(), variable_data=b"x")
        self.assertEqual(len(serialize_explicit_model_range([node])), 0x14)
        self.assertEqual(
            len(serialize_explicit_model_range([node], expected_length=0x14)), 0x14
        )
        with self.assertRaises(ModelRangeError):
            serialize_explicit_model_range([node], expected_length=0x10)
        with self.assertRaises(ModelRangeError):
            ExplicitModelNode(internal_object=b"short")


if __name__ == "__main__":
    unittest.main()
