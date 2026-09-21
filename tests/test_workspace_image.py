import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from workspace_data.image import extract_image
from workspace_sources import WorkspaceSources
from test_workspace_pdf import PDFClient

class ImageTest(unittest.TestCase):
    def test_image_regions_preserve_text_and_location(self):
        lines=[{'text':'Runtime: 27B','confidence':.92,'bbox_normalized_bottom_left':[.1,.2,.5,.1]}]
        with tempfile.TemporaryDirectory() as root,patch('workspace_data.image.command',return_value=json.dumps(lines).encode()):
            result=extract_image(b'image bytes',root)
            self.assertEqual(result['records'][0]['locator']['bbox_normalized_bottom_left'],lines[0]['bbox_normalized_bottom_left'])
            self.assertEqual(result['records'][0]['data']['text'],'Runtime: 27B')
            self.assertTrue(result['requires_structuring'])
            self.assertEqual(json.loads((Path(root)/'ocr-regions.json').read_text()),lines)

    def test_empty_or_malformed_ocr_cannot_succeed(self):
        with tempfile.TemporaryDirectory() as root:
            for lines in ([],[{'text':'invalid','confidence':.5,'bbox_normalized_bottom_left':[5,0,0,0]}]):
                with patch('workspace_data.image.command',return_value=json.dumps(lines).encode()),self.assertRaises(ValueError):extract_image(b'original',root)

    def test_image_upload_retains_original_on_failure_and_can_retry(self):
        with tempfile.TemporaryDirectory() as root:
            sources=WorkspaceSources(root,PDFClient(),'http://localhost:5210')
            with patch('workspace_data.image.extract_image',side_effect=ValueError('No readable text')):
                result=sources.upload('photo.png',b'original bytes')
            self.assertEqual(result['status'],'extraction_failed');self.assertEqual(sources.download(result['source_id'])[0],b'original bytes')
            with patch('workspace_data.image.extract_image',return_value={'kind':'image','status':'extracted','requires_structuring':True,'records':[{'locator':{'region':1},'data':{'text':'Recovered'}}]}):
                result=sources.extract_media(result['source_id'])
            self.assertEqual(result['records'][0]['id'],result['source_id']+':region:1');self.assertNotIn('extraction_error',result)
            other=sources.upload('other.json',b'[{"value":1}]')
            self.assertTrue(sources.collection([result['source_id'],other['source_id']])['requires_structuring'])
