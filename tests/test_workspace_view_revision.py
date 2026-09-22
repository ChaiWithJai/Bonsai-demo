import hashlib
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from workspace_source_jobs import SourceJobs
from workspace_sources import WorkspaceSources
from workspace_store import WorkspaceStore,RevisionConflict
from workspace_data.proposal import validate_proposal
from workspace_view_revision import revise_view
from test_workspace_source_jobs import Client,BadPlanner

class ViewRevisionTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name)
        self.provider=BadPlanner();self.worker=SimpleNamespace(store=WorkspaceStore(root/'workspace'),provider=self.provider,client=Client(),guard=threading.Lock(),tracking_uri='http://localhost:5210')
        self.jobs=SourceJobs(self.worker,WorkspaceSources(root/'sources',self.worker.client,self.worker.tracking_uri));self.jid='a'*32;self.folder=self.jobs.root/self.jid;self.folder.mkdir()
        manifest={'source_id':'source','sha256':'hash','kind':'table','filename':'data.json','status':'extracted','records':[{'id':'source:1','source_id':'source','locator':{'line':1},'data':{'date':'2026-09-18','count':0}},{'id':'source:2','source_id':'source','locator':{'line':2},'data':{'date':'2026-09-19','count':None}}]}
        self.proposal={'interpretation':{'findings':[{'text':'Values supplied','record_ids':['source:1']}],'rationale':'Inspect the table','uncertainties':[],'questions':['Use this view?']},'structure':None,'plan':{'title':'Observations','summary':'Inspect records','fields':[{'name':'date','type':'date'},{'name':'count','type':'number'}],'view':{'component':'RecordTable','columns':['date','count']}}}
        self.digest=hashlib.sha256(json.dumps(self.proposal,sort_keys=True).encode()).hexdigest();self.view={'component':'Scatterplot','x':'date','y':'count','color':None}
        status={'id':self.jid,'status':'awaiting_confirmation','source_id':'source','filename':'data.json','request':'Inspect observations','run_id':'parent-run','proposal_contract':'source-proposal-v2-structured','proposal':self.proposal,'proposal_sha256':self.digest,'task_record_ids':['source:1','source:2']}
        packet={'record_id_map':{'r1':'source:1','r2':'source:2'},'records':[{'id':'r1','data':manifest['records'][0]['data'],'locator':{}},{'id':'r2','data':manifest['records'][1]['data'],'locator':{}}]}
        compiled=validate_proposal(manifest,self.proposal,{'source:1':'source:1','source:2':'source:2'})
        for name,data in {'status.json':status,'source-manifest.json':manifest,'source-packet.json':packet,'profile.json':{},'model-info.json':{},'compiled.json':compiled}.items():self.jobs.save(self.folder,name,data)

    def test_new_view_keeps_frozen_rows_and_requires_new_confirmation(self):
        before={p.name:p.read_bytes() for p in self.folder.iterdir()};result=revise_view(self.jobs,self.jid,{'proposal_sha256':self.digest,'view':self.view},'test')
        self.assertEqual(result['status'],'awaiting_confirmation');self.assertEqual(result['model_calls'],0);self.assertEqual(self.provider.calls,0)
        target=self.jobs.root/result['id'];self.assertFalse((target/'confirmation.json').exists());self.assertEqual(self.worker.store.list(),[])
        self.assertEqual(json.loads((target/'compiled.json').read_text())['rows'],json.loads(before['compiled.json'])['rows'])
        self.assertEqual((target/'source-manifest.json').read_bytes(),before['source-manifest.json']);self.assertEqual({p.name:p.read_bytes() for p in self.folder.iterdir()},before)
        self.assertEqual(self.jobs.get(self.jid)['status'],'superseded');self.assertEqual(result['view_selection']['actor'],'test')
        with self.assertRaises(RevisionConflict):revise_view(self.jobs,self.jid,{'proposal_sha256':self.digest,'view':self.view})

    def test_structured_record_ids_survive_saved_full_citation_ids(self):
        manifest=json.loads((self.folder/'source-manifest.json').read_text())
        proposal=json.loads(json.dumps(self.proposal))
        proposal['interpretation']['findings'][0]['record_ids']=['r1']
        proposal['structure']={'rationale':'Dated observations','records':[{'values':row['data'],'evidence':[{'record_id':'r'+str(i+1),'field':'date','quote':row['data']['date']}]} for i,row in enumerate(manifest['records'])]}
        aliases={'r1':'source:1','r2':'source:2'}
        compiled=validate_proposal(manifest,proposal,aliases)
        proposal['interpretation']['findings'][0]['record_ids']=['source:1']
        for row in proposal['structure']['records']:
            row['evidence'][0]['record_id']=aliases[row['evidence'][0]['record_id']]
        status=json.loads((self.folder/'status.json').read_text());status['proposal']=proposal;status['proposal_sha256']=hashlib.sha256(json.dumps(proposal,sort_keys=True).encode()).hexdigest()
        self.jobs.save(self.folder,'status.json',status);self.jobs.save(self.folder,'compiled.json',compiled)
        result=revise_view(self.jobs,self.jid,{'proposal_sha256':status['proposal_sha256'],'view':self.view})
        saved=json.loads((self.jobs.root/result['id']/'compiled.json').read_text())
        self.assertEqual(saved['rows'],compiled['rows']);self.assertEqual(result['proposal']['structure'],proposal['structure'])

    def test_invalid_mapping_and_stale_selection_make_no_revision(self):
        for view in [{**self.view,'y':'invented'},{**self.view,'component':'LineChart'}]:
            with self.assertRaises(ValueError):revise_view(self.jobs,self.jid,{'proposal_sha256':self.digest,'view':view})
        with self.assertRaises(RevisionConflict):revise_view(self.jobs,self.jid,{'proposal_sha256':'old','view':self.view})
        self.assertEqual(len(list(self.jobs.root.iterdir())),1);self.assertEqual(self.jobs.get(self.jid)['status'],'awaiting_confirmation')

    def test_evidence_outage_keeps_local_revision(self):
        class Offline(Client):
            def create_run(self,*a,**k):raise ConnectionError('Evidence unavailable')
        self.worker.client=Offline();result=revise_view(self.jobs,self.jid,{'proposal_sha256':self.digest,'view':self.view})
        self.assertEqual(result['status'],'awaiting_confirmation');self.assertIn('unavailable',result['evidence_error']);self.assertEqual(self.provider.calls,0)
