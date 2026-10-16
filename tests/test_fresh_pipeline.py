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
        self.assertEqual(tuple(r['exercise_id'] for r in selected_exercises(official_only=True)),SELECTED[:3])
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
            from evaluation.run_statement_regressions import run_regressions
            rejudge=run_regressions(Path(directory,'fresh-pipeline.json'),Path(directory,'rejudge'),OfflineJudge)
            self.assertEqual(len(rejudge['results']),5)
            self.assertEqual(rejudge['summary']['provider_calls'],0)
            self.assertEqual([r['exercise_id'] for r in rejudge['results']],list(SELECTED))
            from evaluation.revalidate_saved_pipeline import revalidate
            replay=revalidate(Path(directory,'rejudge/judge-regressions.json'),Path(directory,'offline-replay'))
            self.assertEqual(len(replay['results']),5)
            self.assertEqual(replay['summary']['provider_calls'],0)
            self.assertIn('离线复验报告',Path(directory,'offline-replay/ryde-evaluation.html').read_text())
            from evaluation.build_demo_package import build
            package=build([Path(directory,'fresh-pipeline.json')],Path(directory,'recording'))
            self.assertEqual(package['opening_provider_calls'],0)
            self.assertEqual(len(package['entries']),5)
            self.assertFalse(any(r['replayed'] for r in package['entries']))
            page=Path(directory,'recording/r21-fare-original.html').read_text()
            self.assertIn('真实模型调用的保存记录',page)
            self.assertNotIn('<script src=',page)
            with self.assertRaisesRegex(ValueError,'new output'):
                build([Path(directory,'fresh-pipeline.json')],Path(directory,'recording'))
            replay_package=build([Path(directory,'offline-replay/revalidation.json')],Path(directory,'recording-replay'))
            self.assertTrue(all(r['replayed'] for r in replay_package['entries']))
            self.assertIn('离线复验',Path(directory,'recording-replay/r21-fare-original.html').read_text())
            saved=Path(directory,'fresh-pipeline.json').read_bytes()
            with self.assertRaisesRegex(ValueError,'new output'):run_fresh(directory,advocate,OfflineJudge)
            self.assertEqual(Path(directory,'fresh-pipeline.json').read_bytes(),saved)
