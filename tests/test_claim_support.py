"""Scope regression checks; no real model calls and no weakened production gates."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from ryde_resolve.claim_support import claim_support_guide
from ryde_resolve.evidence import EvidenceGateway
from ryde_resolve.agents import build_judge_messages
from ryde_resolve.contracts import check_judge
from ryde_resolve.rule_engine import calculate_rules
from ryde_resolve.policy_v21 import application,communication_refs
from ryde_resolve.reasoning_checks import argument_paths
from evaluation.run_statement_regressions import DEFAULT_SOURCE,run_regressions


class ClaimSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.report=json.loads(DEFAULT_SOURCE.read_text())
    def setUp(self):
        self.row=self.report['results'][1]
        self.run=self.row['variants']['debate_judge']['run'];self.s=self.run['snapshot'];self.a=self.run['arguments']
    def test_ticket_and_repeated_chat_do_not_become_incident_corroboration(self):
        guide=claim_support_guide(self.s,self.a);groups=guide['reference_groups']
        self.assertIn('E-002',groups['attributed_party_statements'])
        self.assertNotIn('E-002',groups['communication_records'])
        self.assertNotIn('E-002',groups['candidate_incident_records'])
        self.assertIn('E-012',groups['communication_records'])
        self.assertNotIn('E-012',groups['candidate_incident_records'])
        self.assertIn('E-024',groups['candidate_incident_records'])
        row=next(r for r in guide['arguments'] if r['argument_ref']=='/opening/rider/claims/1')
        self.assertEqual(row['cited_party_statements'],['E-002'])
        self.assertEqual(row['cited_communication_records'],['E-012'])
        self.assertEqual(row['cited_candidate_incident_records'],[])
        self.assertFalse(communication_refs(self.s,['E-002','E-012']))
    def test_all_original_paths_text_and_source_refs_are_preserved(self):
        before=deepcopy((self.s,self.a));guide=claim_support_guide(self.s,self.a)
        expected=set().union(*(argument_paths(self.a,side) for side in ('rider','driver')))
        self.assertEqual({r['argument_ref'] for r in guide['arguments']},expected)
        for row in guide['arguments']:
            _,rnd,side,field,i=row['argument_ref'].split('/')
            self.assertEqual(row['original_text'],self.a[rnd][side][field][int(i)]['claim'])
        self.assertEqual((self.s,self.a),before)
        self.assertTrue(all(set(refs)<=set(self.s['source_index']['evidence']) for refs in guide['reference_groups'].values()))
    def test_guide_has_no_assessment_or_scorer_answer_and_preserves_unknown_policy(self):
        row=self.report['results'][2];run=row['variants']['debate_judge']['run'];s=run['snapshot'];a=run['arguments'];before=application(s)
        payload=json.loads(build_judge_messages(s,a,calculate_rules(s))[1]['content'])
        guide=payload['claim_support_guide']
        self.assertTrue(guide['arguments'])
        self.assertNotIn('expected',payload);self.assertNotIn('exercise_id',payload)
        self.assertTrue(all('assessment' not in r and 'decision' not in r for r in guide['arguments']))
        self.assertEqual(application(s),before)
        self.assertEqual(next(c for c in before['conditions'] if c['condition_id']=='surge_notice')['status'],'unknown')
    def test_advocate_labels_cannot_promote_a_statement_to_incident_record(self):
        args=deepcopy(self.a)
        claim=args['opening']['rider']['claims'][1]
        claim.update(claim_type='system_record',evidence_status='recorded',evidence_refs=['E-002'])
        guide=claim_support_guide(self.s,args)
        row=next(r for r in guide['arguments'] if r['argument_ref']=='/opening/rider/claims/1')
        self.assertEqual(row['advocate_provenance_labels']['claim_type'],'system_record')
        self.assertEqual(row['cited_party_statements'],['E-002'])
        self.assertEqual(row['cited_candidate_incident_records'],[])
        self.assertTrue(row['incident_support_absent_from_own_citations'])
        self.assertIn('Untrusted',row['advocate_provenance_labels']['boundary'])

    def test_old_mislabeled_candidates_remain_rejected(self):
        for row in self.report['results'][1:]:
            run=row['variants']['debate_judge']['run'];candidate=deepcopy(run['judge_initial_proposal'])
            claim_support_guide(run['snapshot'],run['arguments'])
            errors=check_judge(run['snapshot'],candidate,run['arguments'])[0]
            self.assertTrue(any(e.startswith('ARGUMENT_ASSESSMENT_WITHOUT_RECORD_SUPPORT') for e in errors),errors)
            self.assertEqual(candidate,run['judge_initial_proposal'])
    def test_saved_transcript_runner_preserves_rejections_and_never_spends_offline(self):
        report=deepcopy(self.report);before=DEFAULT_SOURCE.read_bytes()
        outputs={row['snapshot_id']:row['variants']['debate_judge']['run']['judge_initial_proposal'] for row in report['results']}
        class CapturedJudge:
            mode='offline_review'
            def __call__(self,s,a,c):return deepcopy(outputs[s['snapshot_id']])
        with tempfile.TemporaryDirectory() as d:
            r=run_regressions(DEFAULT_SOURCE,d,CapturedJudge)
            self.assertEqual(r['summary']['provider_calls'],0)
            self.assertEqual(r['summary']['valid_expected_results'],1)
            self.assertEqual(len(r['results']),3)
            self.assertTrue(all(x['run']['execution_usage']['provider_calls']==0 for x in r['results']))
            with self.assertRaisesRegex(ValueError,'new output'):run_regressions(DEFAULT_SOURCE,d,CapturedJudge)
        self.assertEqual(DEFAULT_SOURCE.read_bytes(),before)
