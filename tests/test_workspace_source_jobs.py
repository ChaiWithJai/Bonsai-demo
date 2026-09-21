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
