"""Handwritten expectations, coherent variants, scorer isolation and regression sensitivity."""
from copy import deepcopy
from decimal import Decimal
import json
import tempfile
from pathlib import Path
import unittest
from evaluation.robustness_suite import build_robustness_exercises
from evaluation.run_judge_suite import evaluate
from ryde_resolve.agents import build_judge_messages
from ryde_resolve.contracts import check_advocate,check_judge
from ryde_resolve.evidence import verify_snapshot
from ryde_resolve.mock_agents import OfflineJudge
from ryde_resolve.policy_v21 import application
from ryde_resolve.rule_engine import calculate_rules
from test_policy_v21 import completed


class RobustnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.exercises=build_robustness_exercises()

    def test_twenty_frozen_expectations_cover_four_decisions(self):
        self.assertEqual(len(self.exercises),20)
        self.assertEqual(len({x['exercise_id'] for x in self.exercises}),20)
        self.assertEqual({x['expected']['decision'] for x in self.exercises},{'escalate','uphold_charge','refund_full','refund_partial'})
        for x in self.exercises:
            with self.subTest(case=x['exercise_id']):
                app=application(x['snapshot']);expected=x['expected']
                self.assertEqual(app['permitted_decision'] or 'escalate',expected['decision'])
                amount=expected['refund_amount']
                self.assertEqual(app['refundable_amount_cents'],None if amount is None else int(Decimal(str(amount))*100))

    def test_all_snapshots_and_advocates_validate_without_labels_in_model_inputs(self):
        for x in self.exercises:
            s=x['snapshot'];verify_snapshot(s)
            for rnd in x['arguments'].values():
                for side,arg in rnd.items():self.assertFalse(check_advocate(s,arg,side)[0])
            payload=json.loads(build_judge_messages(s,x['arguments'],calculate_rules(s))[1]['content'])
            self.assertNotIn('expected',payload);self.assertNotIn('exercise_id',payload);self.assertNotIn('purpose',payload)
            self.assertNotIn(x['exercise_id'],json.dumps(payload))

    def test_policy_candidates_validate_and_wrong_amount_is_rejected(self):
        for x in self.exercises:
            s=x['snapshot'];args=x['arguments']
            output=OfflineJudge()(s,args,calculate_rules(s)) if x['expected']['decision']=='escalate' else completed(s,args)
            self.assertFalse(check_judge(s,output,args)[0],(x['exercise_id'],check_judge(s,output,args)[0]))
            if x['expected']['decision']=='refund_partial':
                changed=deepcopy(output);changed['refund_amount']=0.01
                self.assertTrue(check_judge(s,changed,args)[0])

    def test_order_pair_changes_order_not_fact_or_claim_multisets(self):
        a,b=[x for x in self.exercises if x['order_pair']]
        self.assertEqual(a['snapshot'],b['snapshot']);self.assertEqual(a['expected'],b['expected'])
        self.assertEqual(json.dumps(a['arguments'],sort_keys=True),json.dumps(b['arguments'],sort_keys=True))
        self.assertNotEqual(json.dumps(a['arguments']),json.dumps(b['arguments']))

    def test_export_keeps_scorer_answers_out_of_twenty_model_inputs(self):
        from evaluation.export_dataset import export_dataset
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(export_dataset(directory, 'robustness-v21'),20)
            root=Path(directory)
            manifest=json.loads((root/'manifest.json').read_text())
            labels=json.loads((root/'scorer-only-labels.json').read_text())
            self.assertEqual(manifest['total'],20)
            self.assertEqual(len(labels),20)
            for name in labels:
                payload=json.loads((root/name).read_text())
                data=json.loads(payload[1]['content'])
                self.assertNotIn('expected',data)
                self.assertNotIn(labels[name]['exercise_id'],json.dumps(data))

    def test_never_deciding_does_not_get_a_perfect_score(self):
        r=evaluate(OfflineJudge(),self.exercises)
        self.assertLess(sum(row['behaviour_match'] for row in r['results']),len(self.exercises))
        self.assertGreater(r['metrics']['false_escalations'],0)
        self.assertEqual(r['summary']['resolvable_cases']['matched'],0)
        self.assertFalse(r['model_quality_measured'])
