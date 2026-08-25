import hashlib
import struct
import unittest

from infocarry.delete_state import (
    FIXED_STATE_COMMANDS,
    DeleteStateError,
    derive_supported_delete_state,
)


def _offset_list(*offsets, value_04=0, value_06=0, tail=b""):
    data = bytearray(64)
    struct.pack_into(">IHH", data, 0, len(offsets), value_04, value_06)
    for index, offset in enumerate(offsets):
        struct.pack_into(">I", data, 8 + index * 4, offset)
    if tail:
        data[8 + len(offsets) * 4 :] = tail
    return bytes(data)


def _bookmark(groups):
    data = bytearray(64)
    for group_index, group in enumerate(groups):
        for value_index, value in enumerate(group):
            struct.pack_into(">I", data, (group_index * 5 + value_index) * 4, value)
    return bytes(data)


class DeleteStateTests(unittest.TestCase):
    def setUp(self):
        self.metadata_start = 0x40
        self.record_size = 0x40
        self.target_offset = 0x380
        self.target_ref = self.target_offset - self.metadata_start
        self.zero = bytes(64)

    def _state(self, overrides=None):
        state = {command: self.zero for command in FIXED_STATE_COMMANDS}
        state.update(overrides or {})
        return state

    def test_all_zero_state_is_preserved_exactly(self):
        result = derive_supported_delete_state(
            self._state(),
            target_record_offset=self.target_offset,
            metadata_start=self.metadata_start,
            record_size=self.record_size,
        )
        self.assertEqual(result.before, result.after)
        self.assertEqual(result.changed_commands, ())
        self.assertEqual(result.range1, bytes(0x100))
        self.assertEqual(result.grouped_values, self.zero)
        self.assertEqual(result.audit["policy"], "exact_target_reference_clear_only")

    def test_exact_target_references_are_cleared(self):
        bookmark = _bookmark(((self.target_ref, 0, 0x80000000, 0, 0), (0, 0, 0, 0, 0)))
        result = derive_supported_delete_state(
            self._state({
                    0x001B: _offset_list(self.target_ref),
                    0x001C: _offset_list(self.target_ref),
                    0x001D: _offset_list(self.target_ref),
                    0x001E: _offset_list(self.target_ref),
                    0x001F: bookmark,
                }),
            target_record_offset=self.target_offset,
            metadata_start=self.metadata_start,
            record_size=self.record_size,
        )
        self.assertEqual(result.after, (self.zero,) * 5)
        self.assertEqual(result.changed_commands, FIXED_STATE_COMMANDS)
        self.assertEqual(result.audit["target_metadata_reference_hex"], "0x00000340")

    def test_bookmark_tuple_matches_authoritative_byte_order(self):
        raw = _bookmark(((self.target_ref, 0, 0x80000000, 0, 0), (0, 0, 0, 0, 0)))
        self.assertEqual(raw[:20].hex(), "0000034000000000800000000000000000000000")
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "4f25288fce201441c85256cde9e9ab4649946a73b6ef07e348224fe5de8f7273",
        )
        result = derive_supported_delete_state(
            self._state({0x001F: raw}),
            target_record_offset=self.target_offset,
            metadata_start=self.metadata_start,
            record_size=self.record_size,
        )
        self.assertEqual(result.after[4], self.zero)

    def test_unrelated_reference_is_rejected(self):
        with self.assertRaisesRegex(DeleteStateError, "unsupported reference"):
            derive_supported_delete_state(
                self._state({0x001B: _offset_list(self.target_ref + self.record_size)}),
                target_record_offset=self.target_offset,
                metadata_start=self.metadata_start,
                record_size=self.record_size,
            )

    def test_multiple_or_unknown_state_is_rejected(self):
        for command, raw in (
            (0x001C, _offset_list(self.target_ref, self.target_ref)),
            (0x001D, _offset_list(self.target_ref, tail=b"\x01")),
            (0x001E, _offset_list(self.target_ref, value_04=1)),
            (
                0x001F,
                _bookmark(((self.target_ref, 0, 0x80000000, 0, 0), (1, 0, 0, 0, 0))),
            ),
        ):
            with self.subTest(command=command), self.assertRaises(DeleteStateError):
                derive_supported_delete_state(
                    self._state({command: raw}),
                    target_record_offset=self.target_offset,
                    metadata_start=self.metadata_start,
                    record_size=self.record_size,
                )

    def test_missing_wrong_length_and_unaligned_target_are_rejected(self):
        with self.assertRaises(DeleteStateError):
            derive_supported_delete_state(
                {command: self.zero for command in FIXED_STATE_COMMANDS[:-1]},
                target_record_offset=self.target_offset,
                metadata_start=self.metadata_start,
                record_size=self.record_size,
            )
        with self.assertRaises(DeleteStateError):
            derive_supported_delete_state(
                self._state({0x001B: b"short"}),
                target_record_offset=self.target_offset,
                metadata_start=self.metadata_start,
                record_size=self.record_size,
            )
        with self.assertRaises(DeleteStateError):
            derive_supported_delete_state(
                self._state(),
                target_record_offset=self.target_offset + 1,
                metadata_start=self.metadata_start,
                record_size=self.record_size,
            )


if __name__ == "__main__":
    unittest.main()
