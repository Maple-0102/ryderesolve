"""A captured-material inventory is not an event fact or completeness certificate."""
from copy import deepcopy
from pathlib import Path
import json
import unittest
from ryde_resolve.claim_support import captured_materials,claim_support_guide

ROOT=Path(__file__).resolve().parents[1]


class MaterialInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_run=json.loads((ROOT/'outputs/latest-flow-2026-10-16/final-live-official/fresh-pipeline.json').read_text())['results'][0]['run']

    def test_inventory_matches_all_captured_sections_and_real_communication_pointers(self):
        s=deepcopy(self.saved_run['snapshot']);before=deepcopy(s)
        inventory=captured_materials(s)
        self.assertEqual(len(inventory['raw_sections']),len(s['raw']))
        for row in inventory['raw_sections']:
            key=row['source_ref'][1:].replace('~1','/').replace('~0','~')
            self.assertIn(key,s['raw'])
            if 'entry_count' in row:self.assertEqual(row['entry_count'],len(s['raw'][key]))
        for row in inventory['communication_records']:
            record=s['source_index']['evidence'][row['evidence_id']]
            self.assertEqual(record['kind'],'communication_record')
            self.assertEqual(row['source_refs'],record['source_refs'])
        self.assertEqual(s,before)
        self.assertIn('not certification',inventory['boundary'])
        self.assertNotIn('audio_never_existed',inventory)

    def test_null_empty_and_escaped_section_names_are_retained_without_inferred_absence(self):
        s=deepcopy(self.saved_run['snapshot'])
        s['raw'].update({'audio_recording':None,'call_records':[],'x/y~z':{'flag':False}})
        entries={row['source_ref']:row for row in captured_materials(s)['raw_sections']}
        self.assertEqual(entries['/audio_recording']['json_type'],'null')
        self.assertEqual(entries['/call_records']['entry_count'],0)
        self.assertEqual(entries['/x~1y~0z']['json_type'],'object')
        self.assertNotIn('recording_absent',entries['/audio_recording'])
        guide=claim_support_guide(s,self.saved_run['arguments'])
        self.assertEqual(set(guide['reading_tasks']),{'attributed_report','recorded_communication','incident_assertion','material_gap'})
        self.assertIn('not new assessment_scope',guide['reading_tasks']['material_gap'])
        self.assertTrue(all('assessment' not in row for row in guide['arguments']))
