import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import threading
import unittest
from test_workspace_source_jobs import Client, BadPlanner
from workspace_store import WorkspaceStore, RevisionConflict
from workspace_source_jobs import SourceJobs
from workspace_sources import WorkspaceSources
from workspace_intake_chat import start, context

class IntakeChatTest(unittest.TestCase):
    def test_conversation_is_persisted_reserved_and_carried_into_source_job(self):
        class Provider(BadPlanner):
            def generate(self,messages,*args):
                self.entered.set();self.release.wait(5)
                return {'message':{'role':'assistant','content':'Which dates should the timeline use?'}}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);client=Client();provider=Provider()
            w=SimpleNamespace(store=WorkspaceStore(root/'workspace'),client=client,provider=provider,guard=threading.Lock(),running={},source_jobs=set(),tracking_uri='http://localhost:5210',model_info={})
            sources=WorkspaceSources(root/'sources',client,w.tracking_uri);jobs=SourceJobs(w,sources)
            job=start(jobs,'Data analyst','Explore model releases over time')
            self.assertTrue(provider.entered.wait(5));thread=jobs.active[job['id']][1]
            with self.assertRaises(RevisionConflict):start(jobs,'Data analyst','Another question')
            provider.release.set();thread.join(10)
            self.assertFalse(w.source_jobs)
            self.assertEqual(context(jobs,job['id'])[-1]['content'],'Which dates should the timeline use?')
            with self.assertRaises(ValueError):context(jobs,job['id'],'Evidence reviewer')
            source=sources.upload('observations.json',b'[{"value":0}]')
            result=jobs.start(source['source_id'],'Use explicit release dates',intake_job_id=job['id'])
            with w.guard: thread=jobs.active.get(result['id'],(None,None))[1]
            if thread:thread.join(10)
            saved=json.loads((jobs.root/result['id']/'intake-context.json').read_text())
            self.assertEqual(saved,context(jobs,job['id']))
            request=json.loads((jobs.root/job['id']/'request.json').read_text())
            self.assertIn('No files are attached',request[0]['content'])
            self.assertEqual(w.store.list(),[])

    def test_unfinished_reply_is_not_valid_context(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);root.joinpath('a').mkdir()
            fake=SimpleNamespace(get=lambda _: {'kind':'intake_conversation','status':'failed'},root=root)
            with self.assertRaisesRegex(ValueError,'completed'):context(fake,'a')

if __name__=='__main__':unittest.main()

class WorkstreamDiscoveryTest(unittest.TestCase):
    def test_discussion_and_source_revisions_are_one_recoverable_workstream(self):
        from workspace_intake_chat import workstreams
        first={'id':'a','kind':'intake_conversation','role':'Data analyst','request':'Compare releases','created_at':1,'status':'completed','stage':'Ready'}
        second={**first,'id':'b','parent_job_id':'a','request':'One product','created_at':2}
        source={'id':'c','intake_job_id':'b','source_id':'csv','created_at':3,'status':'awaiting_confirmation','stage':'Review'}
        revised={**source,'id':'d','parent_job_id':'c','created_at':4,'status':'completed','stage':'Built','workspace_id':'project'}
        row=workstreams([revised,second,first,source])[0]
        self.assertEqual(row['id'],'a');self.assertEqual(row['latest_intake_id'],'b')
        self.assertEqual(row['title'],'Compare releases');self.assertEqual(row['source_ids'],['csv'])
        self.assertEqual(row['workspace_id'],'project');self.assertEqual(row['turn_count'],2)
        self.assertEqual(row['status'],'completed')

    def test_failed_followup_stays_discoverable_and_cycles_do_not_hang(self):
        from workspace_intake_chat import workstreams
        first={'id':'a','kind':'intake_conversation','role':'Research analyst','request':'Find evidence','created_at':1,'status':'completed','stage':'Ready'}
        failed={**first,'id':'b','parent_job_id':'a','status':'failed','stage':'Reply stopped','created_at':2}
        self.assertEqual(workstreams([first,failed])[0]['status'],'failed')
        self.assertEqual(workstreams([{**first,'parent_job_id':'a'}]),[])
