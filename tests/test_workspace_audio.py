from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from workspace_sources import WorkspaceSources
from test_workspace_pdf import PDFClient
from workspace_data.audio import extract_audio

class AudioTest(unittest.TestCase):
    def test_missing_runtime_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as root,patch.dict('os.environ',{},clear=True):
            with self.assertRaisesRegex(ValueError,'not configured'):extract_audio(b'audio',root)

    def test_upload_preserves_source_and_timestamp_identity(self):
        with tempfile.TemporaryDirectory() as root:
            sources=WorkspaceSources(root,PDFClient(),'http://localhost:5210')
            result={'kind':'audio','status':'extracted','requires_structuring':True,'records':[{'locator':{'segment':1,'start_seconds':2,'end_seconds':3},'data':{'text':'A source phrase','start_seconds':2,'end_seconds':3}}]}
            with patch('workspace_data.audio.extract_audio',return_value=result):source=sources.upload('notes.wav',b'original')
            self.assertEqual(source['records'][0]['id'],source['source_id']+':segment:1')
            self.assertEqual(source['records'][0]['locator']['start_seconds'],2)
            self.assertEqual(sources.download(source['source_id']),(b'original','audio/wav'))
            self.assertTrue(source['requires_structuring'])

    def test_transcription_failure_keeps_original_available(self):
        with tempfile.TemporaryDirectory() as root:
            sources=WorkspaceSources(root,PDFClient(),'http://localhost:5210')
            with patch('workspace_data.audio.extract_audio',side_effect=ValueError('No speech transcribed')):source=sources.upload('silent.mp3',b'original')
            self.assertEqual(source['status'],'extraction_failed');self.assertEqual(source['record_count'],0)
            self.assertIn('No speech',source['extraction_error']);self.assertEqual(sources.download(source['source_id'])[0],b'original')
