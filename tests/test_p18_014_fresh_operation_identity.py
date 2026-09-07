from pathlib import Path
import sqlite3
import unittest

from infocarry.backup_format import parse_backup_blob
from infocarry.capacity_evidence import NativeCapacityResponse
from infocarry.device_info import RawInfoResponse
from infocarry.device_model_profile import DeviceModelLockKey
from infocarry.execution_claim_store import PersistentExecutionClaimStore
from infocarry.indeterminate_write_lock import PersistentIndeterminateWriteLock
from infocarry.prepared_media_package import build_prepared_media_package
from infocarry.prepared_package_multi_candidate import (
    build_prepared_multi_package_candidate,
)
from infocarry.write_gate import verify_fresh_backup


EVIDENCE_ROOT = Path(
    "/Users/stardust/Projects/InfoCarry-Evidence/"
    "phase-18-p18-012-readonly-diagnostic-20260907-01"
)
SOURCE_ROOT = Path(
    "/Users/stardust/Projects/InfoCarry-Evidence/"
    "phase-17-p17-004-fresh-library-package-20260831-02/00-package/source"
)
TEMPLATE_BLOB = Path(
    "/Users/stardust/Projects/InfoCarry-Evidence/"
    "phase-17-p17-012-library-package-live-preflight-20260901-01/"
    "00-inputs/template/object-08-command-8004.bin"
)
TARGET = "IC_P18_LIBRARY_20260907_01"
OLD_TARGET = "IC_P18_LIBRARY_20260906_01"
OLD_CANDIDATE_SHA = "6fd27699ca6c13a46f8d75467ba72860af8b865b7cf19046b7a91f63bf471e01"
OLD_TRANSACTION_SHA = "9373330cd78f58faaa0cfe61590e4cd0ce489ea5c8069c3112144e69aafe10f4"
P18_011_CLAIM_ID = "827bfde0b93d4b2da57ee646ff6aaa1d"
TEMPLATE_POLICY_SHA = "6c654fe4ec4cd87092b90980471fc32df797c84d7817398c9b81edefcedf796b"


@unittest.skipUnless(
    EVIDENCE_ROOT.is_dir() and SOURCE_ROOT.is_dir() and TEMPLATE_BLOB.is_file(),
    "preserved P18-012/P17 real-evidence inputs are external to CI",
)
class P18014FreshOperationIdentityTests(unittest.TestCase):
    def _candidate(self):
        backup = verify_fresh_backup(
            EVIDENCE_ROOT / "backup-current-0001", max_age_seconds=None
        )
        template = parse_backup_blob(TEMPLATE_BLOB.read_bytes())
        package = build_prepared_media_package(
            (
                (SOURCE_ROOT / "0001_intro-source.txt", "01-introduction.txt"),
                (SOURCE_ROOT / "0002_page-source.bmp", "02-page-01.bmp"),
                (SOURCE_ROOT / "0003_ending-source.txt", "03-ending.txt"),
            ),
            TARGET,
        )
        capacity = NativeCapacityResponse.from_hardware_response(
            RawInfoResponse(
                0x0019,
                "hardware-info",
                (EVIDENCE_ROOT / "command-0019-hardware.bin").read_bytes(),
            ),
            device_identity=(0x054C, 0x001E),
        )
        return build_prepared_multi_package_candidate(
            package,
            backup,
            template,
            new_record_timestamp_be32=0x6A9CAD00,
            native_capacity_response=capacity,
            template_folder_path=("root", "IC_P16_MIXED_20260830_01"),
            template_item_paths={
                "txt": ("root", "IC_P16_MIXED_20260830_01", "01-introduction"),
                "bmp": ("root", "IC_P16_MIXED_20260830_01", "02-page-01"),
            },
            template_subset_policy_sha256=TEMPLATE_POLICY_SHA,
            allow_verified_bookmarks=True,
        )

    def test_real_recovered_baseline_builds_one_new_operation_identity(self):
        candidate = self._candidate()
        before_paths = {"\\".join(path) for path in candidate.baseline.paths.values()}
        after_paths = {"\\".join(path) for path in candidate.candidate.paths.values()}
        target_paths = {
            f"root\\{TARGET}",
            f"root\\{TARGET}\\01-introduction",
            f"root\\{TARGET}\\02-page-01",
            f"root\\{TARGET}\\03-ending",
        }
        self.assertNotIn(f"root\\{TARGET}", before_paths)
        self.assertIn(f"root\\{OLD_TARGET}", before_paths)
        self.assertEqual(after_paths - before_paths, target_paths)
        self.assertEqual(candidate.candidate_blob_sha256, "2d21044987668c55d06aaa202fa678d760f9dbca99a96679eb4dff26e5e818ac")
        self.assertEqual(candidate.transaction_sha256, "82be7e81b213fbb07eba86894ee525970b8a48a1101da5b4324857b1003d2fc8")
        self.assertNotEqual(candidate.candidate_blob_sha256, OLD_CANDIDATE_SHA)
        self.assertNotEqual(candidate.transaction_sha256, OLD_TRANSACTION_SHA)
        self.assertEqual(candidate.candidate_model_bytes, 2123364)
        self.assertEqual(candidate.remaining_growth_bytes, 1038400)
        self.assertEqual(candidate.audit_dict()["allocation"]["metadata_growth_bytes"], 320)
        self.assertEqual(candidate.audit_dict()["display_history_validation"]["references_rebased"], 7)
        self.assertTrue(candidate.audit_dict()["display_history_validation"]["semantic_preserved"])
        self.assertTrue(candidate.audit_dict()["bookmark_validation"]["semantic_preserved"])
        self.assertTrue(candidate.audit_dict()["bookmark_validation"]["opaque_values_preserved_exactly"])
        self.assertEqual(candidate.audit_dict()["fixed_state"]["snapshot"]["blocks"]["0x001c"]["active_entries"], 0)
        self.assertEqual(candidate.audit_dict()["fixed_state"]["snapshot"]["blocks"]["0x001d"]["active_entries"], 0)
        self.assertEqual(candidate.audit_dict()["fixed_state"]["snapshot"]["blocks"]["0x001e"]["active_entries"], 0)

    def test_recovered_lock_is_read_only_clear_and_old_claim_remains_untouched(self):
        lock_path = Path(
            "/Users/stardust/Library/Application Support/"
            "SonyInfoCarryModernManager/indeterminate-write-lock.json"
        )
        db_path = Path(
            "/Users/stardust/Library/Application Support/"
            "SonyInfoCarryModernManager/execution-claims.sqlite3"
        )
        lock = PersistentIndeterminateWriteLock(lock_path).read(
            DeviceModelLockKey("sony-vnw-v15")
        )
        self.assertIsNotNone(lock)
        self.assertEqual(lock.state, "cleared")
        self.assertIsNone(PersistentExecutionClaimStore(db_path).read_sender_in_flight())
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))
            rows = connection.execute(
                "SELECT claim_id, state FROM execution_claims"
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(rows, [(P18_011_CLAIM_ID, "consumed")])


if __name__ == "__main__":
    unittest.main()
