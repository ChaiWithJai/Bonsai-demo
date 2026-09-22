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

    def test_pdf_page_vision_keeps_ocr_and_other_pages_and_replaces_only_selected_visuals(self):
        import hashlib
        from unittest.mock import patch
        class Provider(BadPlanner):
            def generate(self,*args):
                return {'message':{'content':json.dumps({'rows':[{'Baseline_ms':402.1,'Vectorized_ms':389.1}]})}}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);client=Client();sources=WorkspaceSources(root/'sources',client,'http://localhost:5210')
            raw=b'%PDF-test';sid=hashlib.sha256(raw).hexdigest();directory=sources.root/sid;directory.mkdir()
            (directory/'source.bin').write_bytes(raw)
            ocr={'id':sid+':page:2','source_id':sid,'locator':{'page':2},'data':{'text':'Original OCR'}}
            other={'id':sid+':other','source_id':sid,'locator':{'page':1,'evidence_channel':'visual'},'data':{'text':'Other page'}}
            old={'id':sid+':old','source_id':sid,'locator':{'page':2,'evidence_channel':'visual'},'data':{'text':'Old observation'}}
            manifest={'source_id':sid,'sha256':sid,'filename':'source.pdf','kind':'document','status':'extracted','extractor':'OCR','records':[ocr,other,old]}
            (directory/'manifest.json').write_text(json.dumps(manifest));frame=root/'page.png';frame.write_bytes(b'png-fixture')
            provider=Provider();worker=SimpleNamespace(store=WorkspaceStore(root/'workspace'),client=client,provider=provider,guard=threading.Lock(),running={},source_jobs=set(),tracking_uri='http://localhost:5210',model_info={'checkpoint_release':{'runtime':{'mmproj_sha256':'test'}}})
            jobs=SourceJobs(worker,sources)
            for invalid in (None,0,251,True,'2'):
                with self.assertRaisesRegex(ValueError,'Select one PDF page'):jobs.start_vision(sid,invalid)
            with patch('workspace_vision_jobs.image_units',return_value=[{'path':str(frame),'mime':'image/png','locator':{'page':2}}]) as units:
                status=jobs.start_vision(sid,2);thread=jobs.active[status['id']][1];thread.join(10)
            self.assertEqual(jobs.get(status['id'])['status'],'completed')
            self.assertEqual(units.call_args.kwargs,{'page':2})
            updated=sources.manifest(sid)
            self.assertEqual(updated['records'][:2],[ocr,other])
            self.assertNotIn(old,updated['records'])
            self.assertEqual(updated['records'][-1]['locator']['page'],2)
            self.assertEqual(updated['records'][-1]['evidence_status'],'model_extracted_unreviewed')
            self.assertEqual(updated['vision_coverage']['pages'],[1,2])
            self.assertEqual((directory/'source.bin').read_bytes(),raw)
            # A rendering failure leaves the entire previous source snapshot intact.
            with patch('workspace_vision_jobs.image_units',side_effect=ValueError('Page unavailable')):
                failed=jobs.start_vision(sid,3);thread=jobs.active[failed['id']][1];thread.join(10)
            self.assertEqual(jobs.get(failed['id'])['status'],'failed')
            self.assertEqual(sources.manifest(sid),updated)
            self.assertFalse(worker.source_jobs)

    def test_packet_retains_unreviewed_model_provenance(self):
        from workspace_data.proposal import source_packet
        row={'id':'source:visual','locator':{'page':25,'evidence_channel':'visual'},'data':{'value':0},'evidence_status':'model_extracted_unreviewed','extraction_id':'run'}
        packet=source_packet({'records':[row]},request='page 25')
        self.assertEqual(packet['records'][0]['evidence_status'],'model_extracted_unreviewed')
        self.assertEqual(packet['records'][0]['extraction_id'],'run')
