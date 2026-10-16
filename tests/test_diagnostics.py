"""Explain retained source failures without changing a ruling or executing recovery."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from ryde_resolve.diagnostics import explain_checks
from ryde_resolve.ui import render_html


class DiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(__file__).resolve().parents[1]/'outputs/latest-flow-2026-10-16/fresh-v1/fresh-pipeline.json'
        cls.rows=json.loads(path.read_text())['results']

    def test_failed_argument_explains_exact_original_claim_and_links_it(self):
        run=deepcopy(self.rows[2]['run']);before=deepcopy(run)
        rows=explain_checks(run)
        row=next(r for r in rows if r['argument_ref']=='/opening/rider/claims/0')
        self.assertEqual(row['claim'],run['arguments']['opening']['rider']['claims'][0]['claim'])
        self.assertEqual(row['phase'],'final')
        with tempfile.TemporaryDirectory() as directory:
            text=render_html(run,Path(directory)/'report.html').read_text()
        self.assertIn('检查原因与下一步',text)
        self.assertIn('href="#case-0-argument-opening-rider-claims-0"',text)
        self.assertEqual(run,before)

    def test_policy_referral_is_not_explained_as_model_failure(self):
        run=deepcopy(self.rows[0]['run'])
        rows=explain_checks(run)
        self.assertTrue(any(r['phase']=='policy' and r['code']=='policy_gate' for r in rows))
        self.assertTrue(all(r['phase']!='final' for r in rows))

    def test_source_text_is_escaped_and_unknown_errors_stay_visible(self):
        run=deepcopy(self.rows[2]['run'])
        run['arguments']['opening']['rider']['claims'][0]['claim']='<script>unsafe()</script>'
        run['validation_errors'].append('NEW_CHECK_ERROR: unrecognized')
        run['validation_errors'].append('CANNOT_SELF_RESOLVE_POLICY_OR_DATA: ROUTE_DISTANCE_REQUIRES_HUMAN_REVIEW')
        self.assertTrue(any('人工处理' in row['message'] for row in explain_checks(run) if row['code']=='CANNOT_SELF_RESOLVE_POLICY_OR_DATA'))
        self.assertTrue(any(r['code']=='NEW_CHECK_ERROR' for r in explain_checks(run)))
        with tempfile.TemporaryDirectory() as directory:
            text=render_html(run,Path(directory)/'report.html').read_text()
        self.assertIn('&lt;script&gt;unsafe()&lt;/script&gt;',text)
        self.assertNotIn('<script>unsafe()</script>',text)
