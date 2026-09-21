import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from workspace_source_jobs import SourceJobs
from workspace_sources import WorkspaceSources
from workspace_store import WorkspaceStore, RevisionConflict
from workspace_data.desktop_plan import compile_plan

class Client:
    def get_experiment_by_name(self,name):return SimpleNamespace(experiment_id='test')
    def create_run(self,*args,**kwargs):return SimpleNamespace(info=SimpleNamespace(run_id='test'))
    def start_trace(self,*args,**kwargs):return SimpleNamespace(trace_id='trace',span_id='root')
    def start_span(self,*args,**kwargs):return SimpleNamespace(span_id='span')
    def end_span(self,*args,**kwargs):pass
    def end_trace(self,*args,**kwargs):pass
    def log_artifacts(self,*args,**kwargs):pass
    def log_metric(self,*args,**kwargs):pass
    def set_terminated(self,*args,**kwargs):pass

class BadPlanner:
    model='fake-test';profile='legacy-greedy';seed=42
    def __init__(self):self.calls=0;self.entered=threading.Event();self.release=threading.Event()
    def preflight(self,*args):return {'fits':True}
    def generate(self,*args):
        self.calls+=1;self.entered.set();self.release.wait(5)
        return {'message':{'role':'assistant','content':'{"bad":"plan"}'}}

class SourceJobsTest(unittest.TestCase):
    def test_invalid_plan_is_bounded_persisted_and_releases_model_lane(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=WorkspaceStore(root/'workspace');client=Client();provider=BadPlanner()
            worker=SimpleNamespace(store=store,client=client,provider=provider,guard=threading.Lock(),running={},source_jobs=set(),tracking_uri='http://localhost:5210',model_info={})
            sources=WorkspaceSources(root/'sources',client,worker.tracking_uri)
            source=sources.upload('data.json',b'[{"value":0}]');jobs=SourceJobs(worker,sources)
            result=jobs.start(source['source_id'],'Show a grouping of the data')
            self.assertTrue(provider.entered.wait(5))
            with self.assertRaises(RevisionConflict):jobs.start(source['source_id'],'Another plot of this data')
            provider.release.set()
            thread=jobs.active[result['id']][1];thread.join(10)
            self.assertFalse(thread.is_alive());saved=jobs.get(result['id'])
            self.assertEqual(saved['status'],'failed');self.assertEqual(provider.calls,2)
            self.assertFalse(worker.source_jobs);self.assertIn('two-call budget',saved['error'])
            self.assertTrue((jobs.root/result['id']/'model-0.json').exists())
            self.assertTrue((jobs.root/result['id']/'validation-1.json').exists())
            self.assertEqual(store.list(),[])

    def test_collection_job_archives_each_original_before_planning(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=WorkspaceStore(root/'workspace');client=Client();provider=BadPlanner()
            worker=SimpleNamespace(store=store,client=client,provider=provider,guard=threading.Lock(),running={},source_jobs=set(),tracking_uri='http://localhost:5210',model_info={})
            sources=WorkspaceSources(root/'sources',client,worker.tracking_uri)
            originals=[('first.json',b'[{"value":0}]'),('second.json',b'[{"value":2}]')]
            members=[sources.upload(name,raw) for name,raw in originals]
            source=sources.collection([m['source_id'] for m in members]);jobs=SourceJobs(worker,sources)
            result=jobs.start(source['source_id'],'Compare values across these files')
            self.assertTrue(provider.entered.wait(5));thread=jobs.active[result['id']][1]
            provider.release.set();thread.join(10);self.assertFalse(thread.is_alive())
            for member,(_,raw) in zip(members,originals):
                archived=jobs.root/result['id']/'originals'/member['source_id']
                self.assertEqual((archived/'source.bin').read_bytes(),raw)
                self.assertEqual(json.loads((archived/'provenance.json').read_text())['sha256'],member['sha256'])
            self.assertEqual(jobs.get(result['id'])['source_ids'],[m['source_id'] for m in members])
            self.assertEqual(store.list(),[])

    def test_compiler_preserves_zero_null_ids_and_rejects_invented_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            sources=WorkspaceSources(folder,Client(),'http://localhost:5210')
            source=sources.upload('data.json',b'[{"group":"A","x":0,"y":0},{"group":"B","x":1,"y":null}]')
            manifest=sources.manifest(source['source_id'])
            plan={'title':'Measured values','summary':'Missing coordinates excluded, zero preserved','fields':[{'name':'group','type':'text'},{'name':'x','type':'number'},{'name':'y','type':'number'}],'view':{'component':'Scatterplot','x':'x','y':'y','color':'group'}}
            compiled=compile_plan(manifest,plan)
            self.assertEqual(compiled['chart']['props']['data'][0]['y'],0)
            self.assertEqual(compiled['excluded_record_ids'],[manifest['records'][1]['id']])
            self.assertEqual(compiled['rows'][0]['id'],manifest['records'][0]['id'])
            plan['fields'].append({'name':'invented','type':'number'})
            with self.assertRaises(ValueError):compile_plan(manifest,plan)

    def test_proposal_cannot_build_until_its_exact_version_is_confirmed(self):
        class Planner(BadPlanner):
            def generate(self,messages,*args):
                self.calls+=1;self.entered.set();self.release.wait(5)
                packet=json.loads(messages[-1]['content'])['source_evidence']
                proposal={'structure':None,'interpretation':{'findings':[{'text':'One zero-valued observation','record_ids':[packet['records'][0]['id']]}],'rationale':'Inspect the supplied values','uncertainties':['Only one observation'],'questions':['Is grouping by value useful?']},'plan':{'title':'Observed values','summary':'A supplied value group','fields':[{'name':'value','type':'number'}],'view':{'component':'ForceDirectedGraph','groupBy':['value']}}}
                return {'message':{'role':'assistant','content':json.dumps(proposal)}}
        class Tools:
            node='node'
            def __init__(self):self.renders=0
            def command(self,argv,folder,cancel):
                self.renders+=1;folder.mkdir(parents=True,exist_ok=True)
                (folder/'render-evidence.json').write_text('{}');(folder/'chart.svg').write_text('<svg/>')
                return {'ok':True}
            def build(self,*args):return {'ok':True}
            def preview(self,project,*args):return {'url':'http://test/','revision':project['head']}
            def check_browser(self,*args):return {'ok':True}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=WorkspaceStore(root/'workspace');client=Client();provider=Planner();tools=Tools()
            worker=SimpleNamespace(store=store,client=client,provider=provider,tools=tools,latest={},guard=threading.Lock(),running={},source_jobs=set(),tracking_uri='http://localhost:5210',model_info={})
            sources=WorkspaceSources(root/'sources',client,worker.tracking_uri)
            source=sources.upload('data.json',b'[{"value":0}]');jobs=SourceJobs(worker,sources)
            result=jobs.start(source['source_id'],'Explore these source records')
            self.assertTrue(provider.entered.wait(5));thread=jobs.active[result['id']][1];provider.release.set();thread.join(10)
            proposal=jobs.get(result['id']);self.assertEqual(proposal['status'],'awaiting_confirmation')
            self.assertEqual(store.list(),[]);self.assertEqual(tools.renders,0)
            with self.assertRaises(RevisionConflict):jobs.confirm(result['id'],'stale-or-forged-version')
            jobs.confirm(result['id'],proposal['proposal_sha256'],'test')
            active=jobs.active.get(result['id'])
            if active:active[1].join(10)
            complete=jobs.get(result['id']);self.assertEqual(complete['status'],'completed')
            self.assertEqual(provider.calls,1);self.assertEqual(tools.renders,1);self.assertEqual(len(store.list()),1)
            confirmation=json.loads((jobs.root/result['id']/'confirmation.json').read_text())
            self.assertEqual(confirmation['actor'],'test')
            self.assertEqual(confirmation['proposal_sha256'],proposal['proposal_sha256'])

    def test_revision_preserves_exact_parent_proposal_and_source_snapshot(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            jobs = SourceJobs.__new__(SourceJobs)
            jobs.root = Path(folder)
            jid = 'a'*32
            parent = jobs.root/jid
            parent.mkdir()
            raw = b'{"records": [{"value": 0}]}'
            (parent/'source-manifest.json').write_bytes(raw)
            proposal = {'plan': {'title': 'Prior interpretation'}}
            jobs.save(parent, 'status.json', {'status':'awaiting_confirmation',
                'source_id':'source', 'request':'Explore the evidence', 'apply_reviews':False,
                'proposal':proposal, 'proposal_sha256':'exact-proposal-sha', 'run_id':'parent-run'})
            jobs.start = Mock(return_value={'id':'new-job'})
            self.assertEqual(jobs.revise(jid, ' Keep missing values ', 'test'), {'id':'new-job'})
            revision = jobs.start.call_args.args[3]
            self.assertEqual(revision['parent_proposal_sha256'], 'exact-proposal-sha')
            self.assertEqual(revision['parent_planning_run_id'], 'parent-run')
            self.assertEqual(revision['parent_source_snapshot_sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(revision['previous_proposal'], proposal)
            self.assertEqual(revision['feedback'], 'Keep missing values')
            self.assertIn('not a training label', revision['identity_basis'])
            self.assertFalse((parent/'confirmation.json').exists())

    def test_structured_entities_require_real_source_quotes_and_preserve_lineage(self):
        from workspace_data.proposal import structured_manifest
        manifest={'kind':'document','source_id':'source','records':[{'id':'original:page:2','locator':{'page':2},'data':{'text':'Bottleneck: metrics computation. Fix: vectorization.'}}]}
        structure={'rationale':'One bottleneck and its fix','records':[{'values':{'bottleneck':'metrics computation','fix':'vectorization'},'evidence':[{'record_id':'r1','field':'text','quote':'Bottleneck: metrics computation. Fix: vectorization.'}]}]}
        result=structured_manifest(manifest,structure,{'r1':'original:page:2'})
        self.assertEqual(result['records'][0]['data']['fix'],'vectorization')
        self.assertEqual(result['records'][0]['locator']['source_evidence'][0]['record_id'],'original:page:2')
        self.assertEqual(result['records'][0]['evidence_status'],'model_structured_unreviewed')
        self.assertNotEqual(result['records'][0]['id'],manifest['records'][0]['id'])
        structure['records'][0]['evidence'][0]['quote']='Invented speedup 100x'
        with self.assertRaisesRegex(ValueError,'not present'):structured_manifest(manifest,structure,{'r1':'original:page:2'})
        with self.assertRaisesRegex(ValueError,'explicit source-grounded'):structured_manifest(manifest,None,{'r1':'original:page:2'})
