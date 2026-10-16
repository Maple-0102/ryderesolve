"""Recording fidelity must include failures and distinguish replay from fresh calls."""
from pathlib import Path
import json
import tempfile
import unittest
from evaluation.build_demo_package import build
from evaluation.verify_demo_package import verify

ROOT=Path(__file__).resolve().parents[1]


class RecordingIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'fresh.json'
        original=ROOT/'outputs/latest-flow-2026-10-16/final-live-official/fresh-pipeline.json'
        self.source.write_bytes(original.read_bytes())
        self.package=self.root/'recording'
        build([self.source],self.package)

    def test_verifies_actual_source_and_original_failure_without_model_calls(self):
        result=verify(self.package)
        self.assertEqual(result['verification_provider_calls'],0)
        self.assertEqual(result['source_recorded_provider_calls'],15)
        self.assertEqual(result['final_formal_acceptance'],2)
        self.assertEqual(result['raw_first_pass_acceptance'],0)
        self.assertEqual(result['runs_with_program_adjustments'],2)
        self.assertEqual(result['retained_failures'],1)

    def test_modified_page_or_source_is_detected(self):
        page=self.package/'r21-fare-original.html';saved=page.read_bytes()
        page.write_bytes(saved+b'changed')
        with self.assertRaisesRegex(ValueError,'file hash mismatch'):verify(self.package)
        page.write_bytes(saved)
        self.source.write_bytes(self.source.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'Source report hash mismatch'):verify(self.package)

    def test_dropping_failure_relabeling_replay_or_swapping_run_is_detected(self):
        manifest_path=self.package/'manifest.json';original=manifest_path.read_text()
        manifest=json.loads(original)
        manifest['entries']=[e for e in manifest['entries'] if not e['validation_errors']]
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'coverage mismatch'):verify(self.package)
        manifest=json.loads(original);manifest['entries'][0]['replayed']=True
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'result differs'):verify(self.package)
        manifest=json.loads(original)
        entry=manifest['entries'][0];path=self.package/entry['run_json']
        value=json.loads(path.read_text());value['ruling']['refund_amount']=100
        path.write_text(json.dumps(value))
        from hashlib import sha256
        manifest['files'][entry['run_json']]=sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'Copied run differs'):verify(self.package)
