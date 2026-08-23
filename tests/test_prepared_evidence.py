import json
from pathlib import Path
import unittest

from infocarry.backup_format import parse_backup_blob
from infocarry.prepared_evidence import canonical_inventory_sha256, inventory_records

try:
    from test_backup_duplicate import make_nested_blob
except ModuleNotFoundError:
    from tests.test_backup_duplicate import make_nested_blob


class PreparedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.parsed = parse_backup_blob(make_nested_blob(b"chapter\r\ntext"))

    def test_inventory_contains_tree_relationships_and_content_layout(self):
        inventory = inventory_records(self.parsed, root_names=("folder",))
        records = {item["path"]: item for item in inventory["records"]}
        folder = records["root\\folder"]
        source = records["root\\folder\\source"]
        self.assertEqual(folder["parent_offset"], 0x40)
        self.assertEqual(folder["parent_marker_offset"], 0x180)
        self.assertEqual(folder["child_offsets"], [0x140])
        self.assertEqual(source["parent_offset"], 0xC0)
        self.assertEqual(source["file"]["native_prefix_length"], 0x20)
        self.assertEqual(source["file"]["payload_length"], len(b"chapter\r\ntext"))
        self.assertEqual(source["file"]["alignment_padding_bytes"], 3)
        self.assertEqual(source["file"]["content_gap_after_bytes"], 0)

    def test_inventory_is_deterministic_and_json_safe(self):
        first = inventory_records(self.parsed, root_names=("folder",))
        second = inventory_records(self.parsed, root_names=("folder",))
        self.assertEqual(first, second)
        self.assertEqual(
            canonical_inventory_sha256(first), canonical_inventory_sha256(second)
        )
        json.dumps(first, ensure_ascii=False, sort_keys=True)

    def test_all_reachable_inventory_has_stable_summary(self):
        inventory = inventory_records(self.parsed)
        self.assertEqual(inventory["summary"]["records"], len(self.parsed.paths))
        self.assertEqual(inventory["summary"]["directories"], 2)
        self.assertEqual(inventory["summary"]["files"], 1)
        self.assertEqual(inventory["summary"]["extensions"], {"txt": 1})


if __name__ == "__main__":
    unittest.main()
