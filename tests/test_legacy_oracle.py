import json
from pathlib import Path
import unittest

from infocarry.legacy_oracle import (
    CORPUS_FORMAT,
    DifferentialClassification,
    DifferentialError,
    DifferenceAnnotation,
    backup_inventory,
    canonical_json,
    compare_backup_structure,
    compare_bytes,
    compare_transactions,
    validate_corpus_metadata,
)

try:
    from test_backup_duplicate import make_nested_blob
    from infocarry.backup_format import parse_backup_blob
except ModuleNotFoundError:
    from tests.test_backup_duplicate import make_nested_blob
    from infocarry.backup_format import parse_backup_blob


class LegacyOracleDifferentialTests(unittest.TestCase):
    def test_exact_equality(self):
        result = compare_bytes(b"oracle", b"oracle")
        self.assertEqual(result.classification, DifferentialClassification.EXACT_MATCH)
        self.assertEqual(result.raw_differences, ())
        self.assertEqual(result.normalized_differences, ())

    def test_single_byte_difference(self):
        result = compare_bytes(b"abc", b"axc")
        self.assertEqual(result.classification, DifferentialClassification.UNEXPLAINED)
        self.assertEqual(result.raw_differences[0].to_dict(), {
            "start": 1,
            "end": 2,
            "length": 1,
            "differing_bytes": 1,
            "classification": "UNEXPLAINED",
            "annotations": [],
        })

    def test_multiple_contiguous_difference_ranges(self):
        result = compare_bytes(b"abcdefgh", b"abXYefgh")
        self.assertEqual(len(result.raw_differences), 1)
        self.assertEqual(result.raw_differences[0].raw.to_dict()["length"], 2)

    def test_separated_difference_ranges(self):
        result = compare_bytes(b"abcdefgh", b"aXcdeYgh")
        self.assertEqual(
            [(item.raw.start, item.raw.end) for item in result.raw_differences],
            [(1, 2), (5, 6)],
        )

    def test_length_mismatch_is_retained(self):
        result = compare_bytes(b"abc", b"abcXYZ")
        self.assertEqual(result.classification, DifferentialClassification.UNEXPLAINED)
        self.assertEqual(result.left_length, 3)
        self.assertEqual(result.right_length, 6)
        self.assertEqual(result.raw_differences[0].raw.to_dict()["start"], 3)

    def test_known_volatile_range_is_annotated_but_raw_difference_remains(self):
        annotation = DifferenceAnnotation(
            2,
            6,
            DifferentialClassification.EXPLAINED_VOLATILE_FIELD,
            "record timestamps",
            "independently observed operation-wide legacy timestamp rewrite",
        )
        result = compare_bytes(b"aa1234zz", b"aaxyzwzz", annotations=(annotation,))
        self.assertEqual(result.classification, DifferentialClassification.EXPLAINED_VOLATILE_FIELD)
        self.assertEqual(len(result.raw_differences), 1)
        self.assertEqual(len(result.normalized_differences), 0)
        self.assertEqual(result.to_dict()["raw"]["difference_count"], 1)
        self.assertEqual(result.to_dict()["normalized"]["difference_count"], 0)
        self.assertEqual(result.to_dict()["annotations"][0]["evidence"], annotation.evidence)

    def test_unexplained_difference_cannot_be_silently_equal(self):
        result = compare_bytes(b"left", b"right")
        self.assertNotEqual(result.classification, DifferentialClassification.EXACT_MATCH)
        self.assertNotEqual(result.to_dict()["raw"]["difference_count"], 0)

    def test_malformed_corpus_metadata_is_rejected(self):
        with self.assertRaisesRegex(DifferentialError, "missing 'provenance'"):
            validate_corpus_metadata({"format": CORPUS_FORMAT, "fixture_id": "bad"})

    def test_fixture_hash_mismatch_is_rejected(self):
        metadata = self._metadata()
        with self.assertRaisesRegex(DifferentialError, "fixture/hash mismatch"):
            validate_corpus_metadata(metadata, {"legacy_candidate": b"wrong"})

    def test_corpus_metadata_and_reports_are_deterministic(self):
        metadata = self._metadata()
        first = validate_corpus_metadata(metadata)
        second = validate_corpus_metadata(json.loads(canonical_json(metadata)))
        self.assertEqual(first, second)
        self.assertEqual(canonical_json(first), canonical_json(second))
        json.dumps(first, sort_keys=True)

    def test_invalid_summary_classification_is_rejected(self):
        metadata = self._metadata()
        metadata["raw_differential_summary"]["candidate"]["classification"] = "EQUIVALENT"
        with self.assertRaisesRegex(DifferentialError, "invalid classification"):
            validate_corpus_metadata(metadata)

    def test_not_comparable_requires_reason_and_status(self):
        metadata = self._metadata()
        metadata["raw_differential_summary"]["candidate"] = {
            "classification": "NOT_COMPARABLE",
        }
        with self.assertRaisesRegex(DifferentialError, "requires a non-empty reason"):
            validate_corpus_metadata(metadata)
        metadata["raw_differential_summary"]["candidate"]["reason"] = "different baselines"
        with self.assertRaisesRegex(DifferentialError, "interpretation_status"):
            validate_corpus_metadata(metadata)
        metadata["interpretation_status"] = "NOT_COMPARABLE_TEST_FIXTURE"
        self.assertEqual(validate_corpus_metadata(metadata)["fixture_id"], "test-fixture")

    def test_sanitized_p18_corpus_metadata_is_valid(self):
        corpus_path = (
            Path(__file__).parents[1]
            / "samples"
            / "generated"
            / "P18-007-legacy-oracle-differential"
            / "corpus.json"
        )
        document = json.loads(corpus_path.read_text(encoding="utf-8"))
        self.assertEqual(document["format"], CORPUS_FORMAT)
        for row in document["corpus"]:
            validated = validate_corpus_metadata(row)
            self.assertEqual(validated["fixture_id"], row["fixture_id"])

    def test_parsed_structure_and_inventory_are_deterministic(self):
        parsed = parse_backup_blob(make_nested_blob(b"text\r\n"))
        self.assertEqual(compare_backup_structure(parsed, parsed)["classification"], "EXACT_MATCH")
        inventory = backup_inventory(parsed)
        self.assertEqual(inventory["record_count"], len(parsed.records))
        self.assertEqual(inventory["blob_length"], len(parsed.data))
        self.assertEqual(backup_inventory(parsed), inventory)

    def test_transaction_wrapper_is_compared_separately_from_candidate_bytes(self):
        result = compare_transactions((b"fixed", b"candidate"), (b"fixed", b"candidate"))
        self.assertEqual(result["classification"], "EXACT_MATCH")
        self.assertEqual(result["left"]["range_count"], 2)
        changed = compare_transactions((b"fixed", b"legacy"), (b"fixed", b"modern"))
        self.assertEqual(changed["classification"], "UNEXPLAINED")
        self.assertEqual(changed["ranges"][1]["raw"]["difference_count"], 1)

    def test_transaction_range_count_mismatch_cannot_be_exact(self):
        result = compare_transactions((b"fixed",), (b"fixed", b""))
        self.assertEqual(result["range_count_difference"], -1)
        self.assertEqual(result["classification"], "UNEXPLAINED")

    def test_transaction_range_annotation_keeps_raw_difference(self):
        annotation = DifferenceAnnotation(
            2,
            4,
            DifferentialClassification.EXPLAINED_VOLATILE_FIELD,
            "range-local timestamp",
            "synthetic test annotation",
        )
        result = compare_transactions(
            (b"fixed", b"ab12"),
            (b"fixed", b"ab34"),
            range_annotations={1: (annotation,)},
        )
        self.assertEqual(result["classification"], "EXPLAINED_VOLATILE_FIELD")
        self.assertEqual(result["ranges"][1]["raw"]["difference_count"], 1)
        self.assertEqual(result["ranges"][1]["normalized"]["difference_count"], 0)

    def test_transaction_aggregate_preserves_explained_classification(self):
        annotation = DifferenceAnnotation(
            0,
            1,
            DifferentialClassification.EXPLAINED_DETERMINISTIC_DIFFERENCE,
            "derived byte",
            "synthetic test annotation",
        )
        result = compare_transactions(
            (b"fixed", b"ab"),
            (b"fixed", b"cb"),
            range_annotations={1: (annotation,)},
        )
        self.assertEqual(
            result["classification"],
            "EXPLAINED_DETERMINISTIC_DIFFERENCE",
        )

    @staticmethod
    def _metadata():
        values = {
            "legacy_candidate": b"legacy",
            "legacy_transaction": b"transaction",
            "modern_candidate": b"modern",
            "modern_transaction": b"modern-transaction",
        }
        import hashlib

        return {
            "format": CORPUS_FORMAT,
            "fixture_id": "test-fixture",
            "provenance": {"source": "synthetic", "raw_external": False},
            "logical_input_shape": {"ordered_children": ["txt"]},
            "representations": [
                {
                    "id": identifier,
                    "availability": "available",
                    "length": len(value),
                    "sha256": hashlib.sha256(value).hexdigest(),
                }
                for identifier, value in values.items()
            ],
            "expected_volatile_fields": [],
            "raw_differential_summary": {
                "candidate": {"classification": "EXACT_MATCH", "raw_range_count": 0},
                "transaction": {"classification": "EXACT_MATCH", "raw_range_count": 0},
            },
            "interpretation_status": "test-only",
        }


if __name__ == "__main__":
    unittest.main()
