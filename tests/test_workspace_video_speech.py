from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from workspace_sources import WorkspaceSources
from workspace_data.intake import save_manifest
from workspace_data.desktop_plan import profile
from test_workspace_pdf import PDFClient

class VideoSpeechTest(unittest.TestCase):
    def fixture(self,root):
        sources=WorkspaceSources(root,PDFClient(),'http://localhost:5210')
        m=sources.upload('meeting.mp4',b'video bytes')
        row={'id':m['source_id']+':frame','source_id':m['source_id'],'locator':{'time_seconds':0},'data':{'count':0}}
        manifest=sources.manifest(m['source_id']);manifest.update(records=[row],status='extracted',vision_coverage={'samples':1,'records':1,'limitation':'Sampled frames only'})
        save_manifest(Path(root)/m['source_id'],manifest)
        return sources,manifest,row

    def test_speech_appends_to_visual_evidence_and_retries_are_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            sources,m,frame=self.fixture(root)
            result={'records':[{'locator':{'start_seconds':1,'end_seconds':2},'data':{'text':'Keep the zero value'}}], 'audio_coverage':{'segments':1,'limitation':'Test speech'},'extractor':'test-whisper'}
            with patch('workspace_data.video.extract_audio',return_value=result) as extract:
                actual=sources.extract_media(m['source_id']);again=sources.extract_media(m['source_id'])
            self.assertEqual(extract.call_count,1)
            self.assertEqual(actual['records'][0],frame)
            self.assertEqual(actual['records'],again['records'])
            self.assertEqual(actual['kind'],'video')
            self.assertEqual(actual['records'][1]['locator']['evidence_channel'],'speech')
            coverage=profile(sources.manifest(m['source_id']))['media_coverage']
            self.assertIsNotNone(coverage['visual']);self.assertIsNotNone(coverage['speech'])
            self.assertEqual(sources.download(m['source_id'])[0],b'video bytes')

    def test_speech_failure_does_not_destroy_visual_success(self):
        with tempfile.TemporaryDirectory() as root:
            sources,m,frame=self.fixture(root)
            with patch('workspace_data.video.extract_audio',side_effect=ValueError('No audio stream found')):
                actual=sources.extract_media(m['source_id'])
            self.assertEqual(actual['status'],'extracted');self.assertEqual(actual['records'],[frame])
            self.assertIn('No audio stream',actual['speech_extraction_error'])

    def test_visual_pass_preserves_preexisting_speech(self):
        import threading
        from types import SimpleNamespace
        from test_workspace_source_jobs import Client, BadPlanner
        from workspace_source_jobs import SourceJobs
        from workspace_store import WorkspaceStore
        class Provider(BadPlanner):
            def generate(self,*args):
                self.entered.set();self.release.wait(5)
                return {'message':{'content':'{"rows":[{"visible_count":0}]}'}}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);client=Client();sources=WorkspaceSources(root/'sources',client,'http://localhost:5210')
            source=sources.upload('meeting.mp4',b'original video');m=sources.manifest(source['source_id'])
            speech={'id':m['source_id']+':speech:1','source_id':m['source_id'],'locator':{'start_seconds':1,'end_seconds':2,'evidence_channel':'speech'},'data':{'text':'Keep the zero value'}}
            m.update(records=[speech],status='extracted',audio_coverage={'segments':1},visual_extraction_pending=True)
            save_manifest(sources.root/m['source_id'],m)
            provider=Provider();w=SimpleNamespace(store=WorkspaceStore(root/'workspace'),client=client,provider=provider,guard=threading.Lock(),running={},source_jobs=set(),tracking_uri='http://localhost:5210',model_info={'checkpoint_release':{'runtime':{'mmproj_sha256':'test'}}})
            jobs=SourceJobs(w,sources);frame=root/'frame.png';frame.write_bytes(b'test image')
            with patch('workspace_vision_jobs.image_units',return_value=[{'path':str(frame),'mime':'image/png','locator':{'time_seconds':0}}]):
                job=jobs.start_vision(m['source_id']);self.assertTrue(provider.entered.wait(5));thread=jobs.active[job['id']][1];provider.release.set();thread.join(10)
            result=sources.get(m['source_id']);self.assertEqual(result['records'][0],speech)
            self.assertEqual(result['records'][1]['locator']['evidence_channel'],'visual')
            self.assertEqual(result['audio_coverage'],{'segments':1});self.assertNotIn('visual_extraction_pending',result)
