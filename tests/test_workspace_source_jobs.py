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
    def test_attempt_profile_is_frozen_used_and_does_not_mutate_default(self):
        from unittest.mock import patch
        from workspace_provider import LocalProvider
        seen=[]
        def generate(provider,*args):
            seen.append(provider.payload([],[],4096))
            return {'message':{'role':'assistant','content':'{"bad":"plan"}'}}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);client=Client();provider=LocalProvider('http://127.0.0.1:1','test-model')
            worker=SimpleNamespace(store=WorkspaceStore(root/'workspace'),client=client,provider=provider,guard=threading.Lock(),running={},source_jobs=set(),tracking_uri='http://localhost:5210',model_info={})
            sources=WorkspaceSources(root/'sources',client,worker.tracking_uri);source=sources.upload('data.json',b'[{"value":0}]');jobs=SourceJobs(worker,sources)
            config={'profile':'bonsai2-instruct','seed':73}
            with patch.object(LocalProvider,'preflight',return_value={'fits':True}),patch.object(LocalProvider,'generate',generate):
                job=jobs.start(source['source_id'],'Compare the measurements',generation_config=config)
                config['seed']=99
                jobs.active[job['id']][1].join(10)
            self.assertEqual(len(seen),2)
            self.assertTrue(all(payload['seed']==73 and payload['temperature']==0.7 for payload in seen))
            self.assertTrue(all(payload['response_format']['type']=='json_schema' for payload in seen))
            self.assertEqual(provider.profile,'legacy-greedy');self.assertEqual(provider.seed,42)
            self.assertEqual(jobs.get(job['id'])['generation_config'],{'profile':'bonsai2-instruct','seed':73})
            self.assertEqual(json.loads((jobs.root/job['id']/'generation-config.json').read_text()),{'profile':'bonsai2-instruct','seed':73})
            before=set(jobs.root.iterdir())
            with self.assertRaises(ValueError):jobs.start(source['source_id'],'Compare the measurements',generation_config={'profile':'unknown','seed':42})
            self.assertEqual(set(jobs.root.iterdir()),before)

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

    def test_revision_feedback_reaches_source_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=WorkspaceStore(root/'workspace');client=Client();provider=BadPlanner()
            provider.release.set()
            worker=SimpleNamespace(store=store,client=client,provider=provider,guard=threading.Lock(),running={},source_jobs=set(),tracking_uri='http://localhost:5210',model_info={})
            sources=WorkspaceSources(root/'sources',client,worker.tracking_uri)
            source=sources.upload('data.json',b'[{"value":0}]');jobs=SourceJobs(worker,sources)
            parent=jobs.start(source['source_id'],'Inspect values')
            jobs.active[parent['id']][1].join(10)
            path=jobs.root/parent['id']
            status=json.loads((path/'status.json').read_text())
            proposal={'interpretation':{'findings':[]},'structure':None,'plan':{}}
            jobs.save(path,'proposal.json',proposal)
            status.update(status='awaiting_confirmation',proposal_contract='source-proposal-v2-structured',proposal_sha256='test-sha',proposal=proposal)
            jobs.save(path,'status.json',status)
            child=jobs.revise(parent['id'],'Inspect pages 10-12', 'test')
            jobs.active[child['id']][1].join(10)
            packet=json.loads((jobs.root/child['id']/'source-packet.json').read_text())
            self.assertEqual(packet['requested_page_coverage']['requested'],[10,11,12])
            self.assertEqual(packet['requested_page_coverage']['not_found'],[10,11,12])
            self.assertEqual(json.loads((path/'status.json').read_text()),status)

    def test_context_packing_reduces_evidence_before_any_model_call(self):
        class TightPlanner(BadPlanner):
            def __init__(self):super().__init__();self.preflights=0;self.release.set()
            def preflight(self,*args):
                self.preflights+=1
                if self.preflights<=2:
                    assert self.calls==0
                    assert args[2]==8448
                return {'fits':self.preflights>1}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);store=WorkspaceStore(root/'workspace');client=Client();provider=TightPlanner()
            worker=SimpleNamespace(store=store,client=client,provider=provider,guard=threading.Lock(),running={},source_jobs=set(),tracking_uri='http://localhost:5210',model_info={})
            sources=WorkspaceSources(root/'sources',client,worker.tracking_uri)
            source=sources.upload('large.json',json.dumps([{'text':'source '*100} for _ in range(70)]).encode());jobs=SourceJobs(worker,sources)
            result=jobs.start(source['source_id'],'Inspect the source records')
            jobs.active[result['id']][1].join(10)
            path=jobs.root/result['id']
            first=json.loads((path/'packing-64000.json').read_text())
            second=json.loads((path/'packing-48000.json').read_text())
            self.assertGreater(first['records_shown'],second['records_shown'])
            self.assertFalse(first['preflight']['fits']);self.assertTrue(second['preflight']['fits'])
            self.assertEqual(provider.calls,2)
            packet=json.loads((path/'source-packet.json').read_text())
            self.assertIn('partial',packet['coverage'])

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
            built=store.get(complete['workspace_id'])
            self.assertEqual(built['fixture']['compiled']['planning_coverage'],proposal['source_coverage'])
            confirmation=json.loads((jobs.root/result['id']/'confirmation.json').read_text())
            self.assertEqual(confirmation['actor'],'test')
            self.assertEqual(confirmation['proposal_sha256'],proposal['proposal_sha256'])

    def test_revision_correction_is_last_and_prior_citations_use_current_aliases(self):
        from workspace_data.proposal import revision_messages
        proposal={'interpretation':{'findings':[{'record_ids':['original:2']}]},
                  'structure':{'records':[{'evidence':[{'record_id':'original:2','field':'text','quote':'fact'}]}]}}
        revision={'previous_proposal':proposal,'feedback':'Use the title Requested title.'}
        messages=revision_messages(revision,{'r1':'original:2'})
        self.assertEqual([m['role'] for m in messages],['assistant','user'])
        prior=json.loads(messages[0]['content'])
        self.assertEqual(prior['interpretation']['findings'][0]['record_ids'],['r1'])
        self.assertEqual(prior['structure']['records'][0]['evidence'][0]['record_id'],'r1')
        self.assertEqual(json.loads(messages[-1]['content'])['correction'],revision['feedback'])
        self.assertEqual(proposal['interpretation']['findings'][0]['record_ids'],['original:2'])

    def test_valid_revision_supersedes_parent_but_failed_planning_does_not(self):
        with tempfile.TemporaryDirectory() as folder:
            jobs = SourceJobs.__new__(SourceJobs)
            jobs.root = Path(folder)
            jobs.worker = SimpleNamespace(guard=threading.Lock(),running={},source_jobs=set())
            parent_id, child_id = 'a'*32, 'b'*32
            parent, child = jobs.root/parent_id, jobs.root/child_id
            parent.mkdir(); child.mkdir()
            original = {'id':parent_id,'status':'awaiting_confirmation',
                        'proposal_contract':'source-proposal-v2-structured',
                        'proposal_sha256':'old-sha','proposal':{'plan':{}}}
            jobs.save(parent,'status.json',original)
            failed = {'id':child_id,'parent_job_id':parent_id,'status':'failed'}
            jobs.save(child,'status.json',failed)
            self.assertEqual(jobs.get(parent_id)['status'],'awaiting_confirmation')
            jobs.save(child,'status.json',{**failed,'status':'awaiting_confirmation',
                'proposal_contract':'source-proposal-v2-structured',
                'proposal_sha256':'new-sha','proposal':{'plan':{}}})
            self.assertEqual(jobs.get(parent_id)['status'],'superseded')
            self.assertEqual(jobs.get(parent_id)['superseded_by'],child_id)
            with self.assertRaises(RevisionConflict):jobs.confirm(parent_id,'old-sha')
            with self.assertRaises(RevisionConflict):jobs.revise(parent_id,'Another change')
            self.assertEqual(json.loads((parent/'status.json').read_text()),original)
            self.assertFalse((parent/'confirmation.json').exists())

    def test_preview_includes_structure_only_citations_without_uncited_records(self):
        packet = {'records':[{'id':'r1','data':{'value':0}},
                             {'id':'r2','data':{'value':False}},
                             {'id':'r3','data':{'value':'uncited'}}],
                  'record_id_map':{'r1':'original:1','r2':'original:2','r3':'original:3'}}
        proposal = {'interpretation':{'findings':[{'record_ids':['original:1']}]},
                    'structure':{'records':[{'evidence':[{'record_id':'original:2'},
                                                        {'record_id':'original:1'}]}]}}
        examples = SourceJobs.proposal_examples(proposal, packet)
        self.assertEqual([row['id'] for row in examples], ['original:1','original:2'])
        self.assertIs(examples[1]['data']['value'], False)
        self.assertEqual(packet['records'][1]['id'], 'r2')
        proposal['structure'] = None
        self.assertEqual(len(SourceJobs.proposal_examples(proposal, packet)), 1)

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
        item=structure['records'][0]['evidence'][0]
        item['field']='page'; item['quote']='2'
        with self.assertRaisesRegex(ValueError,'Use one of: text'):
            structured_manifest(manifest,structure,{'r1':'original:page:2'})
        item['field']='text'
        structure['records'][0]['evidence'][0]['quote']='Invented speedup 100x'
        with self.assertRaisesRegex(ValueError,'not present'):structured_manifest(manifest,structure,{'r1':'original:page:2'})
        with self.assertRaisesRegex(ValueError,'explicit source-grounded'):structured_manifest(manifest,None,{'r1':'original:page:2'})

    def test_retry_keeps_confirmation_and_failure_archive_without_inference(self):
        class Tools:
            node='node'
            def command(self,argv,folder,cancel):
                folder.mkdir(parents=True,exist_ok=True)
                spec=json.loads(Path(argv[2]).read_text());assert spec['props']['edges']
                (folder/'render-evidence.json').write_text('{}');(folder/'chart.svg').write_text('<svg/>');return {'ok':True}
            build_calls=0
            def build(self,*args):
                self.build_calls+=1
                return {'ok':self.build_calls>1,'stderr':'Development first build failure'}
            def preview(self,project,*args):return {'url':'http://test/','revision':project['head']}
            def check_browser(self,*args):return {'ok':True}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);provider=BadPlanner();client=Client()
            worker=SimpleNamespace(store=WorkspaceStore(root/'workspace'),provider=provider,client=client,tools=Tools(),latest={},guard=threading.Lock(),running={},source_jobs=set(),tracking_uri='http://localhost:5210',model_info={})
            sources=WorkspaceSources(root/'sources',client,worker.tracking_uri);source=sources.upload('data.json',b'[{"value":0}]');jobs=SourceJobs(worker,sources)
            jid='a'*32;folder=jobs.root/jid;folder.mkdir()
            from workspace_data.desktop_plan import profile
            manifest=sources.manifest(source['source_id']);plan={'title':'Groups','summary':'Source groups','fields':[{'name':'value','type':'number'}],'view':{'component':'ForceDirectedGraph','groupBy':['value']}}
            compiled=compile_plan(manifest,plan)
            # Simulate an older compiled artifact with disconnected groups.
            compiled['chart']['props']['nodes']=compiled['chart']['props']['nodes'][1:];compiled['chart']['props']['edges']=[];compiled['node_membership'].pop('all-records')
            status={'id':jid,'source_id':source['source_id'],'filename':'data.json','request':'Group source values','status':'failed','stage':'Stopped','planning_run_id':'plan','run_id':'failed-build','proposal_sha256':'exact','error':'No edges'}
            for name,value in [('status.json',status),('confirmation.json',{'proposal_sha256':'exact','actor':'test-original'}),('source-manifest.json',manifest),('profile.json',profile(manifest)),('compiled.json',compiled)]:jobs.save(folder,name,value)
            with self.assertRaises(RevisionConflict):jobs.retry_build(jid,'wrong')
            jobs.retry_build(jid,'exact','test-retry');active=jobs.active.get(jid)
            if active:active[1].join(10)
            self.assertEqual(jobs.get(jid)['status'],'failed')
            saved_project=worker.store.get(jobs.get(jid)['workspace_id'])
            jobs.retry_build(jid,'exact','test-retry-saved-project');active=jobs.active.get(jid)
            if active:active[1].join(10)
            self.assertEqual(jobs.get(jid)['status'],'completed');self.assertEqual(provider.calls,0)
            self.assertEqual(jobs.get(jid)['workspace_id'],saved_project['id'])
            self.assertEqual(worker.store.get(saved_project['id'])['head'],saved_project['head'])
            self.assertEqual(len(worker.store.list()),1)
            self.assertEqual(json.loads((folder/'confirmation.json').read_text())['actor'],'test-original')
            archives=list((folder/'build-retries').glob('*/status.json'));self.assertEqual(len(archives),2)
            self.assertIn(status,[json.loads(path.read_text()) for path in archives])
            self.assertEqual(jobs.get(jid)['retry_of_run_id'],'test')
            with self.assertRaises(RevisionConflict):jobs.retry_build(jid,'exact')

class ScopedPlanningTest(unittest.TestCase):
    def test_scoped_job_omits_other_page_examples_from_model_messages(self):
        import hashlib
        class Capture(BadPlanner):
            def generate(self,messages,*args):
                self.messages=messages
                return {'message':{'role':'assistant','content':'{}'}}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);client=Client();provider=Capture()
            worker=SimpleNamespace(store=WorkspaceStore(root/'workspace'),provider=provider,client=client,guard=threading.Lock(),running={},source_jobs=set(),tracking_uri='http://localhost:5210',model_info={})
            sources=WorkspaceSources(root/'sources',client,worker.tracking_uri);jobs=SourceJobs(worker,sources)
            raw=b'%PDF-frozen';sid=hashlib.sha256(raw).hexdigest();folder=sources.root/sid;folder.mkdir();(folder/'source.bin').write_bytes(raw)
            manifest={'source_id':sid,'sha256':sid,'filename':'source.pdf','kind':'document','status':'extracted','records':[{'id':sid+':1','source_id':sid,'locator':{'page':1},'data':{'text':'EXCLUDED_PAGE_CONTENT'}},{'id':sid+':2','source_id':sid,'locator':{'page':2},'data':{'text':'SELECTED_PAGE_CONTENT'}}]}
            (folder/'manifest.json').write_text(json.dumps(manifest))
            job=jobs.start(sid,'Inspect selected page',source_scope={'pages':[2]})
            active=jobs.active.get(job['id'])
            if active:active[1].join(10)
            messages=json.dumps(provider.messages)
            self.assertIn('SELECTED_PAGE_CONTENT',messages)
            self.assertNotIn('EXCLUDED_PAGE_CONTENT',messages)
            self.assertEqual(jobs.get(job['id'])['source_scope'],{'pages':[2]})
            saved=json.loads((jobs.root/job['id']/'source-manifest.json').read_text())
            self.assertEqual(saved,manifest)
            from unittest.mock import patch
            pending={**jobs.get(job['id']),'status':'awaiting_confirmation','proposal':{},'proposal_sha256':'test-version','generation_config':{'profile':'bonsai2-medium','seed':81}}
            with patch.object(jobs,'get',return_value=pending),patch.object(jobs,'start',return_value={'id':'new'}) as start:
                jobs.revise(job['id'],'Inspect labels too')
                self.assertEqual(start.call_args.kwargs['source_scope'],{'pages':[2]})
                self.assertEqual(start.call_args.kwargs['generation_config'],pending['generation_config'])
