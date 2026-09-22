import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from workspace_proposal_preview import preview

class ProposalPreviewTest(unittest.TestCase):
    def test_preview_is_cached_and_does_not_confirm_or_rewrite_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'job';folder.mkdir()
            compiled={'rows':[{'id':'a'},{'id':'b'}],'excluded_record_ids':[],
                      'chart':{'component':'Scatterplot','props':{'data':[{'record_id':'a'},{'record_id':'b'}]}}}
            (folder/'compiled.json').write_text(json.dumps(compiled));frozen=(folder/'compiled.json').read_bytes();calls=[]
            def save(target,name,value):(target/name).write_text(json.dumps(value))
            def command(argv,directory,cancel,timeout):
                calls.append(argv);self.assertEqual(timeout,30)
                (directory/'chart.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
                save(directory,'render-evidence.json',{'interaction':{'points':[{'record_id':'a'},{'record_id':'b'}]}})
                return {'ok':True}
            jobs=SimpleNamespace(root=root,get=lambda jid:{'proposal':{'saved':True},'task_record_ids':['a','b']},save=save,preview_guard=threading.Lock(),worker=SimpleNamespace(tools=SimpleNamespace(node='node',command=command)))
            self.assertTrue(preview(jobs,'job').startswith(b'<svg'))
            preview(jobs,'job');self.assertEqual(len(calls),1)
            self.assertEqual((folder/'compiled.json').read_bytes(),frozen)
            self.assertFalse((folder/'confirmation.json').exists())
            compiled['chart']['props']['title']='New title';(folder/'compiled.json').write_text(json.dumps(compiled))
            preview(jobs,'job');self.assertEqual(len(calls),2)
            evidence=list((folder/'proposal-preview').glob('*/preview-evidence.json'))
            self.assertEqual(len(evidence),2)
            for path in evidence:self.assertEqual(json.loads(path.read_text())['model_calls'],0)

    def test_unavailable_proposals_are_rejected_before_rendering(self):
        jobs=SimpleNamespace(get=lambda jid:{})
        with self.assertRaisesRegex(ValueError,'saved proposal'):preview(jobs,'job')

    def test_empty_render_is_not_cached_and_can_be_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'job';folder.mkdir()
            (folder/'compiled.json').write_text(json.dumps({'rows':[], 'chart':{'component':'Scatterplot','props':{'data':[]}}}))
            calls=[]
            def save(target,name,value):(target/name).write_text(json.dumps(value))
            def command(argv,directory,cancel,timeout):
                calls.append(argv)
                (directory/'chart.svg').write_text('' if len(calls)==1 else '<svg/>')
                save(directory,'render-evidence.json',{})
                return {'ok':True}
            jobs=SimpleNamespace(root=root,get=lambda jid:{'proposal':{'saved':True}},save=save,preview_guard=threading.Lock(),worker=SimpleNamespace(tools=SimpleNamespace(node='node',command=command)))
            with self.assertRaisesRegex(ValueError,'empty'):preview(jobs,'job')
            self.assertEqual(list((folder/'proposal-preview').glob('*/preview-evidence.json')),[])
            self.assertEqual(preview(jobs,'job'),b'<svg/>')
            self.assertEqual(len(calls),2)
