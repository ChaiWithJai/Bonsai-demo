from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from workspace_store import WorkspaceStore,RevisionConflict


class WorkspaceStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=WorkspaceStore(self.temp.name)
        self.workspace=self.store.create('Existing explorer',{'App.svelte':'<h1>Explorer</h1>\n<p>Keep zero: 0, missing: null</p>','package.json':'{}'},{'revision':'frozen-fixture'})

    def patch(self,*args,**kwargs):
        return self.store.patch(*args,author='test',**kwargs)

    def test_second_turn_edits_the_prior_revision_and_old_source_remains(self):
        first=self.patch(self.workspace['id'],self.workspace['head'],[{'path':'App.svelte','old_text':'Explorer','new_text':'Runtime explorer'}])
        restored=WorkspaceStore(self.temp.name)
        self.assertEqual(restored.get(first['id'])['files'],first['files'])
        second=self.patch(first['id'],first['head'],[{'path':'App.svelte','old_text':'Runtime explorer','new_text':'Reviewed runtime explorer'}])
        self.assertEqual(second['parent_revision'],first['head'])
        self.assertIn('Keep zero: 0, missing: null',second['files']['App.svelte'])
        self.assertEqual(restored.get(first['id'],self.workspace['head'])['files'],self.workspace['files'])
        with self.assertRaises(RevisionConflict):self.patch(first['id'],self.workspace['head'],[{'path':'App.svelte','old_text':'Explorer','new_text':'stale'}])

    def test_failed_multi_edit_is_atomic(self):
        with self.assertRaises(RevisionConflict):
            self.patch(self.workspace['id'],self.workspace['head'],[{'path':'App.svelte','old_text':'Explorer','new_text':'new'},{'path':'App.svelte','old_text':'missing text','new_text':'bad'}])
        self.assertEqual(self.store.get(self.workspace['id'])['head'],self.workspace['head'])

    def test_paths_dependencies_and_ambiguous_matches_are_rejected(self):
        for path in ['../escape','/tmp/escape','src/../../escape','.env','package.json']:
            with self.assertRaises(ValueError):
                self.patch(self.workspace['id'],self.workspace['head'],[{'path':path,'old_text':'{}','new_text':'bad'}])
        with self.assertRaises(RevisionConflict):
            self.patch(self.workspace['id'],self.workspace['head'],[{'path':'App.svelte','old_text':'<','new_text':'bad'}])

    def test_event_resume_and_terminal_state_survive_reload(self):
        aid=self.store.start_attempt(self.workspace['id'],self.workspace['head'],'Add a filter')
        with self.assertRaises(RevisionConflict):self.store.start_attempt(self.workspace['id'],self.workspace['head'],'Duplicate')
        self.store.event(aid,'tool.started',{'name':'build'})
        self.store.event(aid,'attempt.cancelled',{'reason':'test cancellation'})
        restored=WorkspaceStore(self.temp.name)
        self.assertEqual([event['sequence'] for event in restored.events(aid,after=1)],[2,3])
        self.assertEqual(restored.get(self.workspace['id'])['attempts'][0]['status'],'cancelled')
        with self.assertRaises(RevisionConflict):restored.event(aid,'model.delta',{'text':'late output'})

    def test_model_patch_and_event_commit_together_and_cancellation_blocks_late_patch(self):
        key,base=self.workspace['id'],self.workspace['head']
        edits=[{'path':'App.svelte','old_text':'Explorer','new_text':'Runtime explorer'}]
        with self.assertRaises(ValueError):self.store.patch(key,base,edits)
        aid=self.store.start_attempt(key,base,'Runtime drilldown')
        with self.assertRaises(RevisionConflict):self.patch(key,base,edits)
        result=self.store.patch(key,base,edits,attempt=aid)
        event=self.store.events(aid)[-1]
        self.assertEqual(event['kind'],'patch.applied')
        self.assertEqual(event['payload']['revision'],result['head'])
        self.assertEqual(event['payload']['base_revision'],base)
        self.store.event(aid,'attempt.cancelled',{})
        with self.assertRaises(RevisionConflict):
            self.store.patch(key,result['head'],[{'path':'App.svelte','old_text':'Runtime explorer','new_text':'late'}],attempt=aid)
        self.assertEqual(self.store.get(key)['head'],result['head'])

    def test_patch_cannot_be_attributed_to_another_workspace(self):
        other=self.store.create('Other',{'App.svelte':'other'},{})
        aid=self.store.start_attempt(other['id'],other['head'],'Change other')
        with self.assertRaises(RevisionConflict):
            self.store.patch(self.workspace['id'],self.workspace['head'],[{'path':'App.svelte','old_text':'Explorer','new_text':'wrong'}],attempt=aid)
        with self.assertRaises(ValueError):self.store.event(aid,'patch.applied',{'revision':'forged'})

    def test_restart_preserves_edits_and_closes_interrupted_attempt_once(self):
        aid=self.store.start_attempt(self.workspace['id'],self.workspace['head'],'Add a filter')
        restored=WorkspaceStore(self.temp.name)
        self.assertEqual(restored.recover_interrupted(),[aid])
        self.assertEqual(restored.recover_interrupted(),[])
        self.assertEqual(restored.events(aid)[-1]['kind'],'attempt.failed')
        self.assertTrue(restored.events(aid)[-1]['payload']['interrupted'])
        self.assertEqual(restored.get(self.workspace['id'])['head'],self.workspace['head'])


if __name__=='__main__':unittest.main()
