import unittest

from infocarry.model_tree import (
    MODEL_NODE_FLAG_OFFSET,
    MODEL_NODE_LINK_SENTINEL_OFFSETS,
    MODEL_NODE_SIZE,
    MODEL_NODE_SOURCE_OFFSET,
    MODEL_NODE_TEXT_OFFSET,
    MODEL_NODE_TEXT_SIZE,
    MODEL_SOURCE_SIZE,
    ModelTreeStaticError,
    initialize_model_node,
    initialize_model_source,
)


class ModelTreeStaticTests(unittest.TestCase):
    def test_source_initializer_matches_recovered_marker_and_fields(self):
        source = initialize_model_source()
        self.assertEqual(len(source), MODEL_SOURCE_SIZE)
        self.assertEqual(source[4:8], b"info")
        self.assertEqual(source[8:10], b"y ")
        self.assertEqual(source[9:13], b" 2.0")
        self.assertEqual(source[13:14], b"0")
        self.assertEqual(source[0x0E:0x10], b"\x00\x01")
        self.assertEqual(source[0x10:0x12], b"@\x00")
        self.assertEqual(source[0x12:0x14], b"\xff\xff")
        self.assertEqual(source[0x3C:0x40], b"\xff\xff\xff\xff")

    def test_node_initializer_copies_source_and_sets_sentinels(self):
        source = initialize_model_source()
        node = initialize_model_node(source)
        self.assertEqual(len(node), MODEL_NODE_SIZE)
        self.assertEqual(
            node[MODEL_NODE_SOURCE_OFFSET : MODEL_NODE_SOURCE_OFFSET + MODEL_SOURCE_SIZE],
            source,
        )
        self.assertEqual(node[MODEL_NODE_FLAG_OFFSET], 0xFF)
        text = node[MODEL_NODE_TEXT_OFFSET : MODEL_NODE_TEXT_OFFSET + MODEL_NODE_TEXT_SIZE]
        self.assertEqual(text[:-1], bytes(MODEL_NODE_TEXT_SIZE - 1))
        self.assertEqual(text[-1:], b"\xff")
        for offset in MODEL_NODE_LINK_SENTINEL_OFFSETS:
            self.assertEqual(node[offset : offset + 4], b"\xff\xff\xff\xff")

    def test_node_initializer_rejects_wrong_source_shape(self):
        with self.assertRaises(ModelTreeStaticError):
            initialize_model_node(b"short")


if __name__ == "__main__":
    unittest.main()
