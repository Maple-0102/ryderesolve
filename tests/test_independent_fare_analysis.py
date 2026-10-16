"""A malformed advocacy ledger cannot create an otherwise unsupported fare ruling."""
from copy import deepcopy
from pathlib import Path
import json
import unittest
from ryde_resolve.statement_gate import reconcile_independent_fare_analysis
from ryde_resolve.contracts import check_judge
from ryde_resolve.orchestrator import RydeOrchestrator
from evaluation.run_statement_regressions import CapturedEvidence,CapturedAdvocates

ROOT=Path(__file__).resolve().parents[1]


class FareAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=json.loads((ROOT/'outputs/latest-flow-2026-10-16/judge-v2/judge-regressions.json').read_text())['results']
    def fare(self,index=2):
        run=deepcopy(self.rows[index]['run'])
        return run['snapshot'],run['arguments'],run['judge_initial_proposal']
    def test_downgrade_only_with_independent_main_evidence_and_unchanged_money(self):
        s,args,raw=self.fare();before=deepcopy((s,args,raw))
        self.assertTrue(check_judge(s,raw,args)[0])
        candidate,changes=reconcile_independent_fare_analysis(s,raw,args)
        self.assertTrue(changes)
        self.assertFalse(check_judge(s,candidate,args)[0])
        for key in ('decision','refund_amount','findings','confidence','currency','amount_unit','uncertainties'):
            self.assertEqual(raw[key],candidate[key])
        self.assertEqual(raw['case_analysis']['decision_conditions'],candidate['case_analysis']['decision_conditions'])
        for change in changes:
            if change['rule']=='independent_fare_argument_downgrade':
                self.assertEqual(change['adjusted']['assessment'],'insufficient_evidence')
                self.assertEqual(change['adjusted']['supporting_evidence_refs'],[])
        self.assertEqual((s,args,raw),before)
    def test_side_summary_is_reconciled_without_regrading_any_argument(self):
        s,args,raw=self.fare(3)
        candidate,changes=reconcile_independent_fare_analysis(s,raw,args)
        self.assertTrue(changes)
        self.assertTrue(all(c['rule']=='independent_fare_side_summary' for c in changes))
        self.assertEqual(candidate['case_analysis']['argument_assessments'],raw['case_analysis']['argument_assessments'])
        self.assertEqual(candidate['case_analysis']['sides']['driver']['assessment'],'partly_supported')
        self.assertEqual(candidate['case_analysis']['sides']['rider'],raw['case_analysis']['sides']['rider'])
        self.assertFalse(check_judge(s,candidate,args)[0])
    def test_wrong_amount_or_decision_or_unknown_condition_cannot_be_reconciled(self):
        for field,value in [('refund_amount',5),('decision','uphold_charge')]:
            s,args,raw=self.fare();raw[field]=value
            self.assertEqual(reconcile_independent_fare_analysis(s,raw,args),(raw,[]))
        unknown=self.rows[4]['run']['snapshot'];s,args,raw=self.fare()
        self.assertEqual(reconcile_independent_fare_analysis(unknown,raw,args),(raw,[]))
    def test_material_statement_dependency_or_opposing_sources_blocks_correction(self):
        for mode in ('finding','condition','opposition','unknown_ref'):
            s,args,raw=self.fare()
            bad=raw['case_analysis']['argument_assessments'][0]
            ref=bad['supporting_evidence_refs'][0]
            if mode=='finding':raw['findings'][0]['evidence_refs'].append(ref)
            if mode=='condition':raw['case_analysis']['decision_conditions'][0]['evidence_refs'].append(ref)
            if mode=='opposition':bad['opposing_evidence_refs']=['E-001']
            if mode=='unknown_ref':bad['supporting_evidence_refs']=['E-NOT-REAL']
            self.assertEqual(reconcile_independent_fare_analysis(s,raw,args),(raw,[]),mode)
    def test_route_and_noshow_are_never_given_a_decisive_correction(self):
        for row in self.rows[:2]:
            run=row['run'];s=run['snapshot'];args=run['arguments'];raw=deepcopy(run['judge_initial_proposal'])
            raw.update(decision='uphold_charge',refund_amount=0,escalate_to_human=False)
            self.assertEqual(reconcile_independent_fare_analysis(s,raw,args),(raw,[]))
    def test_real_orchestrator_adopts_audited_candidate_and_keeps_original_failure(self):
        s,args,raw=self.fare()
        class Judge:
            mode='teammate_json'
            def __call__(self,*_):return deepcopy(raw)
        run=RydeOrchestrator(CapturedEvidence(s),CapturedAdvocates(s,args),Judge()).run(s['case_id'])
        self.assertFalse(run['validation_errors'])
        self.assertEqual(run['ruling']['refund_amount'],4.5)
        self.assertEqual(run['judge_initial_proposal'],raw)
        self.assertTrue(run['judge_raw_validation_errors'])
        self.assertTrue(run['judge_adjustments'])
        self.assertFalse(run['first_pass_valid'])
