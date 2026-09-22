import json
from pathlib import Path
import tempfile
import unittest
from workspace_store import WorkspaceStore
from workspace_review_inventory import inventory

class ReviewInventoryTests(unittest.TestCase):
    def test_current_review_eligibility_and_private_content_omission(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=WorkspaceStore(root);(root/'source-jobs').mkdir()
            projects=[]
            for kind in ('test','human'):
                p=store.create(title='Private project title',files={'App.svelte':'<p>first</p>'},fixture={'private':'private fixture'})
                store.review_interface(p['id'],{'revision':p['head'],'author':'Private name','reviewer_kind':kind,'action':'accept','note':'Private review note','previous_event_id':None})
                projects.append(p)
            report=inventory(root)
            self.assertEqual(report['summary']['interface_candidates'],1)
            self.assertNotIn('Private',json.dumps(report))
            self.assertNotIn('private fixture',json.dumps(report))
            p=projects[1]
            store.patch(p['id'],p['head'],[{'path':'App.svelte','old_text':'first','new_text':'second'}],author='test')
            self.assertEqual(inventory(root)['summary']['interface_candidates'],0)
            bad=root/'source-jobs'/'bad';bad.mkdir();(bad/'status.json').write_text('{broken')
            self.assertEqual(inventory(root)['summary']['unreadable'],1)

    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaisesRegex(ValueError,'Existing'):inventory(root)
            self.assertEqual(list(root.iterdir()),[])
