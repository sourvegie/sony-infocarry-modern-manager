import unittest

from infocarry.offline_conversion import monochrome_bmp_bytes
from infocarry.prepared_content import EMPTY_SHA256, PreparedContentArtifact, PreparedContentChild
from infocarry.transfer_shape import (
    EXACT_VERIFIED_LIVE_PROFILE,
    PLAUSIBLE_FUTURE_DIRECT_LEAF_V15,
    UNMAPPABLE_UNSUPPORTED_SHAPE,
    assess_transfer_shape,
)


def _artifact(kinds):
    children = []
    for order, kind in enumerate(kinds):
        payload = b"text" if kind == "txt" else monochrome_bmp_bytes(
            [[False] * 237 for _ in range(320)], width=237, height=320
        )
        import hashlib

        children.append(
            PreparedContentChild(
                order=order,
                kind=kind,
                name=f"child-{order}.{kind}",
                path=f"root\\Book\\child-{order}.{kind}",
                payload_sha256=hashlib.sha256(payload).hexdigest(),
                payload_bytes=len(payload),
                payload_path=f"prepared/Book/child-{order}.{kind}",
            )
        )
    return PreparedContentArtifact("Book", tuple(children))


class TransferShapeTests(unittest.TestCase):
    def test_exact_shape_matches_only_current_reviewed_profile(self):
        result = assess_transfer_shape(_artifact(("txt", "bmp", "txt")))
        self.assertEqual(result.classification, EXACT_VERIFIED_LIVE_PROFILE)
        self.assertFalse(result.requires_capability_validation)

    def test_other_flat_leaf_shapes_are_future_only(self):
        result = assess_transfer_shape(_artifact(("txt", "bmp", "txt", "txt")))
        self.assertEqual(result.classification, PLAUSIBLE_FUTURE_DIRECT_LEAF_V15)
        self.assertTrue(result.requires_capability_validation)

    def test_nested_shapes_are_unmappable(self):
        folder = PreparedContentChild(
            order=0,
            kind="folder",
            name="Nested",
            path="root\\Book\\Nested",
            payload_sha256=EMPTY_SHA256,
            payload_bytes=0,
        )
        child = PreparedContentChild(
            order=1,
            kind="txt",
            name="nested.txt",
            path="root\\Book\\Nested\\nested.txt",
            payload_sha256="0" * 64,
            payload_bytes=0,
            payload_path="prepared/Book/nested.txt",
        )
        result = assess_transfer_shape(PreparedContentArtifact("Book", (folder, child)))
        self.assertEqual(result.classification, UNMAPPABLE_UNSUPPORTED_SHAPE)
        self.assertTrue(result.unmappable)


if __name__ == "__main__":
    unittest.main()
