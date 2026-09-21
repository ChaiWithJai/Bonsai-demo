import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from workspace_store import WorkspaceStore,RevisionConflict
from workspace_sources import WorkspaceSources
from workspace_source_jobs import SourceJobs
from workspace_data.intake import ingest
from test_workspace_source_jobs import Client,BadPlanner

class VisionTest(unittest.TestCase):
    def test_visual_extraction_is_reserved_persisted_and_unreviewed(self):
        class Provider(BadPlanner):
            def generate(self,*args):
                self.entered.set();self.release.wait(5)
                return {'message':{'content':json.dumps({'rows':[{'label':'Visible value','count':'0'}]})}}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);client=Client();sources=WorkspaceSources(root/'sources',client,'http://localhost:5210')
            original=ingest(sources.root,'table.png',b'isolated unit fixture')
            provider=Provider();worker=SimpleNamespace(store=WorkspaceStore(root/'workspace'),client=client,provider=provider,guard=threading.Lock(),running={},source_jobs=set(),tracking_uri='http://localhost:5210',model_info={'checkpoint_release':{'runtime':{'mmproj_sha256':'test'}}})
            jobs=SourceJobs(worker,sources);job=jobs.start_vision(original['source_id'])
            self.assertTrue(provider.entered.wait(5));thread=jobs.active[job['id']][1]
            with self.assertRaises(RevisionConflict):jobs.start_vision(original['source_id'])
            provider.release.set();thread.join(10);self.assertFalse(thread.is_alive())
            self.assertEqual(jobs.get(job['id'])['status'],'completed');self.assertFalse(worker.source_jobs)
            updated=sources.get(original['source_id']);self.assertEqual(updated['records'][0]['data']['count'],'0')
            self.assertEqual(updated['records'][0]['evidence_status'],'model_extracted_unreviewed')
            self.assertEqual(sources.download(original['source_id'])[0],b'isolated unit fixture')
            self.assertTrue((sources.root/original['source_id']/'extractions'/job['id']/'previous-manifest.json').exists())
            self.assertEqual(worker.store.list(),[])

    def test_unverified_vision_runtime_cannot_start_job(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);client=Client();sources=WorkspaceSources(root/'sources',client,'http://localhost:5210')
            worker=SimpleNamespace(store=WorkspaceStore(root/'workspace'),provider=BadPlanner(),model_info={})
            jobs=SourceJobs(worker,sources)
            with self.assertRaisesRegex(ValueError,'no verified vision'):jobs.start_vision('x')
