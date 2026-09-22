from pathlib import Path
import re
import tempfile
import unittest
from build_prism_ui import stage_workspace_components

class WorkspacePackagingTest(unittest.TestCase):
    def test_fresh_stage_resolves_all_workspace_component_imports(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            stage=Path(folder);stage_workspace_components(root,stage)
            route=stage/'src/routes/workspace/+page.svelte'
            self.assertEqual(route.read_bytes(),(root/'scripts/prism-ui/Workspace.svelte').read_bytes())
            self.assertFalse((stage/'src/lib/Workspace.svelte').exists())
            self.assertTrue((stage/'src/lib/workspace-data-types.ts').is_file())
            components=list((stage/'src/lib').glob('Workspace*.svelte'))
            self.assertGreater(len(components),6)
            for file in [route,*components]:
                for dependency in re.findall(r'\$lib/(Workspace[^\'\"]+\.svelte)',file.read_text()):
                    self.assertTrue((stage/'src/lib'/dependency).is_file(),f'{file.name}: missing {dependency}')
