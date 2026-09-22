import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from workspace_proposal_comparison import compare

class ProposalComparisonTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        record={'values':{'count':0,'missing':None},'evidence':[{'record_id':'source:0','field':'text','quote':'zero'}]}
        proposal={'structure':{'records':[record,copy.deepcopy(record)]},'interpretation':{'findings':[],'uncertainties':[]},'plan':{'view':{'component':'RecordTable','columns':['count']}}}
        self.states={name:{'id':name,'proposal':copy.deepcopy(proposal),'generation_config':{'profile':'legacy-greedy','seed':42},'run_id':name,'elapsed_seconds':2} for name in ('previous','current')}
        self.states['current']['parent_job_id']='previous';self.jobs=SimpleNamespace(root=self.root,get=lambda jid:copy.deepcopy(self.states[jid]))
        for name in self.states:
            (self.root/name).mkdir();(self.root/name/'source-manifest.json').write_text('{"source":"same"}')
        self.states['current']['parent_source_snapshot_sha256']=hashlib.sha256((self.root/'previous/source-manifest.json').read_bytes()).hexdigest()

    def test_duplicate_records_and_changed_citations_are_not_lost(self):
        self.states['current']['proposal']['structure']['records'][1]['evidence'][0]['quote']='different'
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result=compare(self.jobs,'current')
        self.assertEqual(result['records'],{'previous':2,'current':2,'unchanged':1,'previous_only':1,'current_only':1})
        self.assertTrue(result['matches']['source_snapshot']);self.assertTrue(result['matches']['recorded_parent_snapshot'])
        self.assertIsNone(result['matches']['generation_settings'])
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_zero_missing_and_configuration_differences_remain_distinct(self):
        self.states['current']['proposal']['structure']['records'][0]['values']['count']=None
        self.states['current']['proposal']['plan']['view']={'component':'Scatterplot','x':'date','y':'count','color':None}
        for name,seed in [('previous',0),('current',42)]:
            (self.root/name/'generation-settings.json').write_text(json.dumps({'seed':seed}))
        result=compare(self.jobs,'current')
        self.assertEqual(result['records']['unchanged'],1);self.assertTrue(result['view_changed']);self.assertFalse(result['matches']['generation_settings'])
        self.assertEqual(result['previous']['records'][0]['values']['count'],0)
        self.assertIsNone(result['current']['records'][0]['values']['count'])

    def test_missing_or_changed_parent_metadata_is_not_a_match(self):
        self.states['current'].pop('parent_source_snapshot_sha256');self.assertIsNone(compare(self.jobs,'current')['matches']['recorded_parent_snapshot'])
        self.states['current']['parent_source_snapshot_sha256']='wrong';self.assertFalse(compare(self.jobs,'current')['matches']['recorded_parent_snapshot'])
        with self.assertRaisesRegex(ValueError,'no previous'):compare(self.jobs,'previous')
        self.states['current'].pop('proposal')
        with self.assertRaisesRegex(ValueError,'Both versions'):compare(self.jobs,'current')

    def test_record_order_does_not_count_as_changed(self):
        rows=self.states['previous']['proposal']['structure']['records'];rows[0]['values']['count']=8
        self.states['current']['proposal']['structure']['records']=copy.deepcopy(rows[::-1])
        self.assertEqual(compare(self.jobs,'current')['records']['unchanged'],2)
