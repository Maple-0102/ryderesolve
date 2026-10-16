"""Changing runtime prompts or schemas must invalidate resumable outputs."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ryde_resolve.execution import implementation_digest


class RuntimeAssetTests(unittest.TestCase):
    def test_vendor_prompt_and_contract_changes_invalidate_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            package=root/'vendor/ryderesolve-advocate-system/ryderesolve_advocate'
            (package/'prompts').mkdir(parents=True)
            (package/'contracts').mkdir()
            code=package/'agents.py';code.write_text('# identical Python code\n')
            prompt=package/'prompts/common.txt';prompt.write_text('original prompt')
            schema=package/'contracts/advocate.schema.json';schema.write_text('{"title":"v0.2"}')
            with patch('ryde_resolve.execution.ROOT',root):
                original=implementation_digest()
                prompt.write_text('new source-attribution instructions')
                changed_prompt=implementation_digest()
                self.assertNotEqual(original,changed_prompt)
                schema.write_text('{"title":"v0.3"}')
                self.assertNotEqual(changed_prompt,implementation_digest())

    def test_non_runtime_outputs_do_not_invalidate_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            package=root/'vendor/ryderesolve-advocate-system/ryderesolve_advocate'
            package.mkdir(parents=True)
            (package/'agents.py').write_text('# runtime')
            with patch('ryde_resolve.execution.ROOT',root):
                original=implementation_digest()
                (root/'outputs').mkdir();(root/'outputs/result.json').write_text('{"result":1}')
                self.assertEqual(original,implementation_digest())
