"""Evaluation separation checks using the real adapters with local transport only."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import json
import tempfile
import unittest
from evaluation.run_fresh_pipeline import run_fresh, selected_exercises, SELECTED
from ryde_resolve.teammate_advocate import TeammateAdvocate
from ryde_resolve.mock_agents import OfflineJudge
from test_teammate_advocate import FakeClient


class FreshPipelineTests(unittest.TestCase):
    def test_five_inputs_keep_expected_labels_and_fixture_arguments_out_of_agents(self):
        rows=selected_exercises()
        self.assertEqual(tuple(r['exercise_id'] for r in rows),SELECTED)
        self.assertEqual([r['snapshot']['audit']['data_origin'] for r in rows],['organizer_sample']*3+['synthetic']*2)
        class RecordingClient(FakeClient):
            def generate(self,*args,**kwargs):
                result=super().generate(*args,**kwargs)
                for row in result['claims']:
                    row.update(claim_type='advocacy_inference',evidence_status='unverified')
                return result
        clients=[]
        def advocate():
            client=RecordingClient();clients.append(client);return TeammateAdvocate(client)
        with tempfile.TemporaryDirectory() as directory,redirect_stdout(StringIO()):
            report=run_fresh(directory,advocate,OfflineJudge)
            self.assertEqual(len(report['results']),5)
            self.assertEqual(report['summary']['provider_calls'],20)  # Local fake transport invocations.
            self.assertEqual(report['summary']['recorded_tokens'],0)
            self.assertEqual([len(c.inputs) for c in clients],[4]*5)
            for client in clients:
                for _,context,_ in client.inputs:
                    self.assertNotIn('expected',context)
                    self.assertNotIn('exercise_id',context)
                    self.assertNotIn('arguments',context)
                    self.assertNotIn('Assess the recorded case facts',json.dumps(context))
            saved=Path(directory,'fresh-pipeline.json').read_bytes()
            with self.assertRaisesRegex(ValueError,'new output'):run_fresh(directory,advocate,OfflineJudge)
            self.assertEqual(Path(directory,'fresh-pipeline.json').read_bytes(),saved)
