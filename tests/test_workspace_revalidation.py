import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from workspace_source_jobs import SourceJobs
from workspace_sources import WorkspaceSources
from workspace_store import WorkspaceStore
from test_workspace_source_jobs import Client,BadPlanner

class RevalidationTest(unittest.TestCase):
    def test_saved_response_recovery_is_frozen_separate_and_never_calls_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);client=Client();provider=BadPlanner()
            worker=SimpleNamespace(store=WorkspaceStore(root/'workspace'),provider=provider,client=client,guard=threading.Lock(),tracking_uri='http://localhost:5210')
            sources=WorkspaceSources(root/'sources',client,worker.tracking_uri);jobs=SourceJobs(worker,sources)
            sid='source';jid='a'*32;folder=jobs.root/jid;folder.mkdir()
            fields={f'value_{i}':i for i in range(8)}
            manifest={'source_id':sid,'sha256':'hash','kind':'table','filename':'measurements.json','status':'extracted','records':[{'id':'source:1','source_id':sid,'locator':{},'data':fields}]}
            proposal={'interpretation':{'findings':[{'text':'Values are present','record_ids':['r1']}],'rationale':'Inspect values','uncertainties':[],'questions':['Use this view?']},'structure':None,'plan':{'title':'Measurements','summary':'Compare measurements','fields':[{'name':key,'type':'number'} for key in fields],'view':{'component':'RecordTable','columns':list(fields)}}}
            status={'id':jid,'status':'failed','source_id':sid,'filename':'measurements.json','request':'Compare measurements','run_id':'old-run'}
            for name,value in {'status.json':status,'source-manifest.json':manifest,'source-packet.json':{'record_id_map':{'r1':'source:1'},'records':[{'id':'r1','locator':{},'data':fields}],'records_shown':1,'records_total':1},'profile.json':{},'model-info.json':{'frozen_model':'test'},'model-0.json':{'message':{'content':json.dumps(proposal)}}}.items():jobs.save(folder,name,value)
            before={p.name:p.read_bytes() for p in folder.iterdir()}
            recovered=jobs.revalidate(jid)
            self.assertEqual(recovered['status'],'awaiting_confirmation')
            self.assertEqual(recovered['model_calls'],0)
            self.assertEqual(provider.calls,0)
            self.assertNotEqual(recovered['id'],jid)
            self.assertEqual(recovered['parent_job_id'],jid)
            self.assertEqual({p.name:p.read_bytes() for p in folder.iterdir()},before)
            target=jobs.root/recovered['id']
            self.assertFalse((target/'confirmation.json').exists())
            self.assertEqual(json.loads((target/'compiled.json').read_text())['rows'][0]['data'],fields)
            self.assertEqual((target/'source-manifest.json').read_bytes(),before['source-manifest.json'])
            self.assertEqual(worker.store.list(),[])
            # Invalid references remain invalid; revalidation never repairs the output itself.
            proposal['plan']['view']['columns']=['invented']
            jobs.save(folder,'model-0.json',{'message':{'content':json.dumps(proposal)}})
            failed=jobs.revalidate(jid)
            self.assertEqual(failed['status'],'failed')
            self.assertIn('overview columns',failed['error'])
            self.assertNotIn('proposal',failed)
            self.assertEqual(provider.calls,0)
