import unittest
from pathlib import Path
from types import SimpleNamespace

from infocarry.payload_builder import (
    PayloadBuilderError,
    build_from_decoded_vicdata,
    build_ordinary_from_decoded_vicdata,
    build_from_observed_capture,
    build_from_replacements,
    build_offline_payload,
)
from infocarry.model_range import ExplicitModelNode
from infocarry.backup_format import parse_backup_blob
from infocarry.range5_model import serialize_range5_model
from infocarry.usblog import Usblog101bCapture
try:
    from test_backup_format import make_text_blob
except ModuleNotFoundError:
    from tests.test_backup_format import make_text_blob


def _offset_states():
    return tuple(
        SimpleNamespace(
            count=1,
            value_04_be16=index,
            value_06_be16=index + 1,
            record_offsets=(0x100 + index,),
        )
        for index in range(4)
    )


def _grouped_state():
    return SimpleNamespace(groups=((1, 2, 3, 4, 5), (6, 7, 8, 9, 10)))


class PayloadBuilderTests(unittest.TestCase):
    def test_composes_verified_and_explicit_opaque_ranges(self):
        range4 = b"generated"  # Explicit unresolved range input.
        range6 = b"six"
        range7 = b""
        range8 = b"model-records"
        source = bytes(range(0x40))

        transaction = build_offline_payload(
            _offset_states(),
            _grouped_state(),
            range4=range4,
            range5_source=source,
            range6=range6,
            range7=range7,
            range8=range8,
        )

        self.assertEqual(transaction.variable_n, len(range4))
        self.assertEqual(transaction.ranges[0][0:8], bytes.fromhex("0000000100000001"))
        self.assertEqual(transaction.ranges[1][0:8], bytes.fromhex("0000000100000002"))
        self.assertEqual(transaction.ranges[3], range4)
        self.assertEqual(transaction.ranges[4], serialize_range5_model(source))
        self.assertEqual(transaction.ranges[5:], (range6, range7, range8))
        self.assertEqual(transaction.payload_length, 0x10000 + transaction.variable_m + len(range4))

    def test_recomposes_an_observed_capture_exactly(self):
        source = bytes(range(0x40))
        range5 = serialize_range5_model(source)
        ranges = (
            build_offline_payload(
                _offset_states(),
                _grouped_state(),
                range5_source=source,
                range8=b"opaque",
            ).ranges
        )
        capture = Usblog101bCapture(
            record_offset=0,
            command_offset=6,
            declared_length=sum(len(item) for item in ranges),
            records=(),
            ranges=ranges,
        )

        rebuilt = build_from_observed_capture(capture)
        self.assertEqual(rebuilt.ranges, ranges)
        self.assertEqual(rebuilt.ranges[4], range5)

    def test_rejects_invalid_fixed_state_or_range5_input(self):
        with self.assertRaises(PayloadBuilderError):
            build_offline_payload(
                _offset_states()[:-1],
                _grouped_state(),
                range5_source=b"short",
                range8=b"opaque",
            )
        with self.assertRaises(PayloadBuilderError):
            build_offline_payload(
                _offset_states(),
                _grouped_state(),
                range5_source=b"short",
                range8=b"opaque",
            )

    def test_composes_explicit_model_nodes_without_usb(self):
        internal = bytearray(0x51)
        internal[0x19] = 1
        internal[0x50] = 0
        node = ExplicitModelNode(bytes(internal), variable_data=b"node")
        transaction = build_offline_payload(
            _offset_states(),
            _grouped_state(),
            range5_source=bytes(0x40),
            model_nodes=(node,),
        )
        self.assertEqual(transaction.ranges[7][0x10:0x14], b"node")
        self.assertEqual(transaction.ranges[7][0x14:], b"")

    def test_composes_decoded_vicdata_as_header_plus_body(self):
        decoded = make_text_blob(b"payload\r\n")

        transaction = build_from_decoded_vicdata(
            decoded,
            _offset_states(),
            _grouped_state(),
        )

        self.assertEqual(transaction.ranges[4], decoded[:0x40])
        self.assertEqual(transaction.ranges[7], decoded[0x40:])
        self.assertEqual(transaction.ranges[4] + transaction.ranges[7], decoded)
        self.assertEqual(transaction.ranges[3], b"")
        self.assertEqual(transaction.ranges[5], b"")
        self.assertEqual(transaction.ranges[6], b"")
        self.assertEqual(transaction.variable_n, 0)
        self.assertEqual(transaction.variable_m, len(decoded))

        ordinary = build_ordinary_from_decoded_vicdata(
            decoded, _offset_states(), _grouped_state()
        )
        self.assertEqual(ordinary.ranges, transaction.ranges)

    def test_decoded_vicdata_composer_rejects_malformed_blob(self):
        with self.assertRaises(PayloadBuilderError):
            build_from_decoded_vicdata(
                b"not a VICDATA blob",
                _offset_states(),
                _grouped_state(),
            )

    def test_builds_toolkit_authored_existing_record_replacement(self):
        original = make_text_blob(b"old text\r\n")
        transaction = build_from_replacements(
            original,
            {0xC0: b"new text\r\n"},
            _offset_states(),
            _grouped_state(),
        )
        rebuilt = transaction.ranges[4] + transaction.ranges[7]
        parsed = parse_backup_blob(rebuilt)
        _, payload = parsed.payload_parts(parsed.record_at(0xC0))
        self.assertEqual(payload, b"new text\r\n")
        self.assertNotEqual(rebuilt, original)

    def test_replacement_builder_requires_a_change(self):
        with self.assertRaises(PayloadBuilderError):
            build_from_replacements(
                make_text_blob(), {}, _offset_states(), _grouped_state()
            )

    def test_decoded_vicdata_composer_reproduces_preserved_candidate(self):
        project_root = Path(__file__).resolve().parents[1]
        artifact_root = project_root / "analysis/phase-8-candidate-1"
        if not (artifact_root / "range-01.bin").is_file():
            self.skipTest(
                "raw native transaction ranges are local-research-only evidence"
            )
        ranges = tuple(
            (artifact_root / f"range-{index:02d}.bin").read_bytes()
            for index in range(1, 9)
        )
        states = []
        for index in range(4):
            data = ranges[0][index * 0x40 : (index + 1) * 0x40]
            count = int.from_bytes(data[0:4], "big")
            states.append(
                SimpleNamespace(
                    count=count,
                    value_04_be16=int.from_bytes(data[4:6], "big"),
                    value_06_be16=int.from_bytes(data[6:8], "big"),
                    record_offsets=tuple(
                        int.from_bytes(data[offset : offset + 4], "big")
                        for offset in range(8, 8 + 4 * count, 4)
                    ),
                )
            )
        grouped_data = ranges[1]
        grouped = SimpleNamespace(
            groups=(
                tuple(
                    int.from_bytes(grouped_data[offset : offset + 4], "big")
                    for offset in range(0, 20, 4)
                ),
                tuple(
                    int.from_bytes(grouped_data[offset : offset + 4], "big")
                    for offset in range(20, 40, 4)
                ),
            )
        )

        rebuilt = build_from_decoded_vicdata(
            ranges[4] + ranges[7], states, grouped
        )
        self.assertEqual(rebuilt.ranges, ranges)


if __name__ == "__main__":
    unittest.main()
