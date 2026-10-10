"""Bounded A/B placement fakes; never use USB or production safety state."""
from dataclasses import replace
import json
from pathlib import Path
import unittest

from infocarry.delete_workflow import ROOT_TXT_DELETE_VALIDATION_FILES
from infocarry.root_txt_placement import (
    DISPOSABLE_ROOT_TXT_PLACEMENT_PROFILE, _json,
)
from infocarry.write_protocol import REQUEST_BEGIN_TRANSMIT
try:
    import test_root_txt_placement as placement_tests
except ModuleNotFoundError:
    from tests import test_root_txt_placement as placement_tests


class DisposablePlacementTests(unittest.TestCase):
    def setup_case(self, target=None, **kwargs):
        helper = placement_tests.RootPlacementTests()
        case = helper.setup_case(**kwargs)
        self.addCleanup(helper.doCleanups)
        target = target or next(iter(ROOT_TXT_DELETE_VALIDATION_FILES))
        source = case[0] / target.split('\\')[-1]
        source.write_bytes(ROOT_TXT_DELETE_VALIDATION_FILES[target])
        return (case[0], source, *case[2:]), target

    def prepare(self, case, target):
        bundle = case[4].prepare(case[1], target_path=target, validation_placement=True)
        case[2]['bundle'] = bundle
        return bundle

    def approve(self, case):
        identity = case[4].owner_authorization_identity
        case[4].authorize_prepared_operation(identity.approval_phrase)
        return identity

    def execute(self, case, bundle):
        return case[4].execute_once(confirmation_interaction=lambda _: bundle.authorization.core.confirmation_phrase)

    def no_write(self, case, bundle=None):
        self.assertEqual(case[3].calls, [])
        if bundle is not None:
            self.assertIsNone(case[5].read_claim(bundle.seal_sha256))
        self.assertIsNone(case[5].read_sender_in_flight())
        self.assertFalse(case[6].path.exists())

    def test_both_exact_disposable_sources_prepare_and_reconstruct_without_write(self):
        for target in ROOT_TXT_DELETE_VALIDATION_FILES:
            with self.subTest(target=target):
                case, _ = self.setup_case(target)
                bundle = self.prepare(case, target)
                self.assertTrue(bundle.validation_placement)
                self.assertEqual(bundle.operation_profile, DISPOSABLE_ROOT_TXT_PLACEMENT_PROFILE)
                self.assertEqual(bundle.expected_folder_name, case[1].name)
                self.assertEqual(bundle.authorization.core.confirmation_phrase, f'ADD {case[1].name} ONCE')
                self.assertEqual(bundle.candidate.core.audit['target']['path'], target)
                bundle.verify_seal()
                self.assertEqual(case[2]['timestamp_calls'], 1)
                self.no_write(case, bundle)

    def test_opt_in_name_payload_model_and_old_fixture_are_fail_closed(self):
        for variant in ('no_optin', 'false', 'truthy', 'wrongtarget', 'nested', 'payload', 'model', 'legacy'):
            with self.subTest(variant=variant):
                case, target = self.setup_case()
                kwargs = dict(target_path=target, validation_placement=True)
                if variant == 'no_optin': kwargs.pop('validation_placement')
                elif variant == 'false': kwargs['validation_placement'] = False
                elif variant == 'truthy': kwargs['validation_placement'] = 1
                elif variant == 'wrongtarget': kwargs['target_path'] = 'root\\Other.txt'
                elif variant == 'nested': kwargs['target_path'] = 'root\\nested\\' + case[1].name
                elif variant == 'payload': case[1].write_bytes(b'changed')
                elif variant == 'model': kwargs['device_model'] = 'VNW-V10'
                else:
                    from infocarry.root_txt_placement import FIXTURE_PATH
                    kwargs['target_path'] = FIXTURE_PATH
                with self.assertRaises(ValueError): case[4].prepare(case[1], **kwargs)
                self.assertEqual(case[2]['captures'], [])
                self.no_write(case)

    def test_existing_target_and_case_native_stem_collision_are_rejected(self):
        case, target = self.setup_case()
        bundle = self.prepare(case, target)
        for lower in (False, True):
            other, _ = self.setup_case(target)
            blob = bundle.candidate.candidate_blob
            if lower:
                from infocarry.backup_format import parse_backup_blob
                from infocarry.backup_format import calculate_backup_checksum
                parsed = parse_backup_blob(blob)
                record = next(parsed.record_at(offset) for offset, path in parsed.paths.items() if path[-1] == case[1].stem)
                changed = bytearray(blob)
                name = case[1].stem.lower().encode('cp932')
                # Native name occupies record offset 0x18 onward.
                changed[record.offset+0x18:record.offset+0x18+len(name)] = name
                changed[0x1C:0x20] = calculate_backup_checksum(changed).to_bytes(4, "big")
                blob = bytes(changed)
            other[2]['blob'] = blob
            with self.assertRaisesRegex(ValueError, 'absent|ambiguity|duplicate'):
                self.prepare(other, target)
            self.no_write(other)

    def test_unsupported_template_and_global_lock_stop_before_sender(self):
        from infocarry.backup_format import calculate_backup_checksum
        for variant in ('prefix', 'lock'):
            case, target = self.setup_case()
            if variant == 'prefix':
                blob = bytearray(case[2]['blob'])
                blob[0xC0+0x14:0xC0+0x18] = (0x100).to_bytes(4, 'big')
                blob[0x1C:0x20] = calculate_backup_checksum(blob).to_bytes(4, 'big')
                case[2]['blob'] = bytes(blob)
            else:
                # Established owner fails closed on malformed persistent lock.
                case[6].path.write_text('{}')
            with self.assertRaises(Exception): self.prepare(case, target)
            self.assertEqual(case[3].calls, [])
            self.assertIsNone(case[5].read_sender_in_flight())

    def test_disposable_cannot_generate_legacy_prestage_report(self):
        case, target = self.setup_case()
        bundle = self.prepare(case, target)
        with self.assertRaisesRegex(ValueError, 'cannot produce'):
            bundle.write_placement_report(case[0], {}, bundle.before_backup)
        self.no_write(case, bundle)

    def test_reconstruction_detects_individually_valid_transaction_rebinding(self):
        from infocarry.write_artifact import ProspectiveWriteTransaction
        case, target = self.setup_case()
        bundle = self.prepare(case, target)
        ranges = list(bundle.candidate.transaction.ranges)
        changed = bytearray(ranges[0]); changed[63] ^= 1; ranges[0] = bytes(changed)
        transaction = ProspectiveWriteTransaction(tuple(ranges), bundle.candidate.transaction.variable_n, bundle.candidate.transaction.variable_m)
        rebound = replace(bundle, candidate=replace(bundle.candidate, transaction=transaction))
        # Direct check reaches independent reconstruction even before envelope checks.
        with self.assertRaisesRegex(ValueError, 'independent reconstruction'):
            rebound._reconstruct_disposable_candidate(bundle.before_backup)
        self.no_write(case, bundle)

    def test_one_shot_reconnect_readback_report_claim_marker_and_clear_lock(self):
        for target in ROOT_TXT_DELETE_VALIDATION_FILES:
            case, _ = self.setup_case(target, reconnect=True)
            bundle = self.prepare(case, target)
            self.approve(case)
            case[2]['session'] = 'new-equivalent-session'
            result = self.execute(case, bundle)
            self.assertEqual(result.completion, 0)
            self.assertEqual(result.audit['workflow']['sender_calls'], 1)
            self.assertEqual(sum(c[0]=='control_out' and c[1]==REQUEST_BEGIN_TRANSMIT for c in case[3].calls), 1)
            self.assertEqual(case[2]['timestamp_calls'], 1)
            self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
            self.assertIsNone(case[5].read_sender_in_flight())
            self.assertFalse(case[6].path.exists())
            evidence = Path(result.audit['evidence_outputs']['root'])
            report = json.loads((evidence/'disposable-placement-report.json').read_bytes())
            self.assertEqual(report['experiment_id'], 'P18-044')
            self.assertEqual(report['fixture']['path'], target)
            self.assertEqual(report['native_completion'], '0x0000')
            self.assertTrue(report['verification']['exact_path_and_payload_verification']['surviving_timestamps_unchanged'])
            self.assertEqual(list(evidence.rglob('placement-readback-or-backup-report.json')), [])
            with self.assertRaises(Exception): self.execute(case, bundle)
            self.assertEqual(sum(c[0]=='control_out' for c in case[3].calls), 1)

    def test_source_candidate_audit_profile_optin_and_authorization_rebinding_rejected(self):
        for mutation in ('source', 'candidate', 'audit', 'target', 'optin', 'profile', 'approval'):
            case, target = self.setup_case()
            bundle = self.prepare(case, target)
            self.approve(case)
            if mutation == 'source': bundle.source_path.write_bytes(b'x')
            elif mutation == 'candidate': Path(bundle.candidate_artifact.path).write_bytes(b'x')
            elif mutation == 'audit':
                audit = bundle.candidate.audit_dict()
                audit['disposable_placement']['record_timestamp_be32'] += 1
                case[4]._prepared_operation = replace(bundle, candidate=replace(bundle.candidate, audit_json=_json(audit)))
            elif mutation == 'target': case[4]._prepared_operation = replace(bundle, placement_target_path=list(ROOT_TXT_DELETE_VALIDATION_FILES)[1])
            elif mutation == 'optin': case[4]._prepared_operation = replace(bundle, validation_placement=False)
            elif mutation == 'profile': case[4]._prepared_operation = replace(bundle, authorization=replace(bundle.authorization, core=replace(bundle.authorization.core, profile_id='wrong')))
            else: case[4]._owner_authorized_identity = replace(case[4]._owner_authorized_identity, candidate_blob_sha256='a'*64)
            with self.assertRaises(Exception): self.execute(case, bundle)
            self.no_write(case, bundle)

    def test_stale_state_and_cancel_before_start_do_not_consume_claim(self):
        for variant in ('state', 'cancel'):
            case, target = self.setup_case()
            bundle = self.prepare(case, target)
            self.approve(case)
            if variant == 'state':
                try: from test_new_txt import _make_root_blob
                except ModuleNotFoundError: from tests.test_new_txt import _make_root_blob
                case[2]['blob'] = _make_root_blob(b'drift\r\n')
                execute = lambda: self.execute(case, bundle)
            else: execute = lambda: case[4].execute_once(confirmation_interaction=lambda _: 'cancel')
            with self.assertRaises(Exception): execute()
            self.no_write(case, bundle)

    def test_native_rejection_and_indeterminate_failures_keep_existing_lifecycle_no_retry(self):
        for variant in ('nonzero', 'disconnect', 'readback'):
            options = {'completion': (2,)} if variant == 'nonzero' else {'fail_bulk_at':1} if variant == 'disconnect' else {}
            case, target = self.setup_case(backend_options=options)
            bundle = self.prepare(case, target)
            self.approve(case)
            if variant == 'readback': case[2]['after_bad'] = True
            with self.assertRaises(Exception) as raised: self.execute(case, bundle)
            self.assertIn(raised.exception.state, ('failed', 'indeterminate_after_transaction_start'))
            self.assertEqual(sum(c[0]=='control_out' for c in case[3].calls), 1)
            self.assertIsNotNone(case[5].read_claim(bundle.seal_sha256))
            if variant == 'nonzero':
                # Existing runner terminally resolves a definite native rejection.
                self.assertIsNone(case[5].read_sender_in_flight())
                self.assertFalse(case[6].path.exists())
            else:
                self.assertIsNotNone(case[5].read_sender_in_flight())
                self.assertTrue(case[6].path.exists())
            self.assertEqual(list(case[0].rglob('disposable-placement-report.json')), [])


if __name__ == '__main__': unittest.main()
