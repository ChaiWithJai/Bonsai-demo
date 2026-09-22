import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from workspace_data.pdf import extract_pdf
from workspace_sources import WorkspaceSources
from test_workspace_sources import Client

class PDFClient(Client):
    def log_artifacts(self,*args):pass

class PDFTest(unittest.TestCase):
    def test_mixed_pdf_retains_pages_and_uses_ocr_for_image_only_page(self):
        calls=[]
        def command(argv,timeout=60):
            calls.append(argv)
            if argv[0]=='pdfinfo':return b'Pages: 2\n'
            if argv[0]=='pdftotext':return (('Native text '*30)+'\f\f').encode()
            if argv[0]=='pdftoppm' or argv[0]=='swiftc':return b''
            return json.dumps([{'text':'Scanned page text','confidence':0.9}]).encode()
        with tempfile.TemporaryDirectory() as root, patch('workspace_data.pdf.command',side_effect=command),patch('workspace_data.pdf.shutil.which',return_value='/test/bin'):
            result=extract_pdf(b'%PDF-test',Path(root))
            self.assertEqual([r['locator']['page'] for r in result['records']],[1,2])
            self.assertEqual(result['records'][1]['data']['text'],'Scanned page text')
            self.assertEqual(result['extraction_coverage']['ocr_pages'],[2])
            self.assertEqual(result['extraction_coverage']['pages_with_text'],2)
            self.assertEqual(len([c for c in calls if c[0]=='pdftoppm']),1)

    def test_upload_runs_pdf_extraction_and_failure_is_explicit_with_original_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            sources=WorkspaceSources(root,PDFClient(),'http://localhost:5210')
            with patch('workspace_data.pdf.extract_pdf',side_effect=ValueError('Encrypted PDF cannot be read')):
                result=sources.upload('locked.pdf',b'%PDF-preserved')
            self.assertEqual(result['status'],'extraction_failed')
            self.assertIn('Encrypted PDF',result['extraction_error'])
            self.assertEqual(sources.download(result['source_id'])[0],b'%PDF-preserved')
            with patch('workspace_data.pdf.extract_pdf',return_value={'kind':'document','status':'extracted','extractor':'test','records':[{'locator':{'page':1},'data':{'text':'Recovered'}}],'extraction_coverage':{'page_count':1,'pages_with_text':1,'unresolved_pages':[]}}):
                fixed=sources.extract_pdf(result['source_id'])
            self.assertEqual(fixed['record_count'],1)
            self.assertEqual(fixed['records'][0]['id'],result['source_id']+':page:1')
            self.assertNotIn('extraction_error',fixed)
            self.assertEqual(len(list((Path(root)/result['source_id']/'extractions').iterdir())),2)

    def test_page_count_mismatch_cannot_be_reported_as_success(self):
        with tempfile.TemporaryDirectory() as root,patch('workspace_data.pdf.shutil.which',return_value='/test/bin'),patch('workspace_data.pdf.command',side_effect=[b'Pages: 2\n',b'Only one page\f']):
            with self.assertRaisesRegex(ValueError,'coverage mismatch'):extract_pdf(b'%PDF-test',Path(root))

    def test_sparse_embedded_header_is_supplemented_with_ocr(self):
        def command(argv,timeout=60):
            if argv[0]=='pdfinfo':return b'Pages: 1\n'
            if argv[0]=='pdftotext':return b'Page 1\f'
            if argv[0] in ('pdftoppm','swiftc'):return b''
            return json.dumps([{'text':'Page 1'},{'text':'Owner: Maya'},{'text':'Open issues: 3'}]).encode()
        with tempfile.TemporaryDirectory() as root,patch('workspace_data.pdf.command',side_effect=command),patch('workspace_data.pdf.shutil.which',return_value='/test/bin'):
            result=extract_pdf(b'%PDF-test',root)
            self.assertEqual(result['records'][0]['data']['text'],'Page 1\nOwner: Maya\nOpen issues: 3')
            self.assertEqual(result['extraction_coverage']['pages'][0]['ocr_trigger'],'sparse_embedded_text')
            self.assertEqual(result['extraction_coverage']['ocr_pages'],[1])

    def test_sparse_page_ocr_failure_retains_embedded_text_and_reports_gap(self):
        def command(argv,timeout=60):
            if argv[0]=='pdfinfo':return b'Pages: 1\n'
            if argv[0]=='pdftotext':return b'Page 1\f'
            raise ValueError('OCR unavailable')
        with tempfile.TemporaryDirectory() as root,patch('workspace_data.pdf.command',side_effect=command),patch('workspace_data.pdf.shutil.which',return_value='/test/bin'):
            result=extract_pdf(b'%PDF-test',root)
            self.assertEqual(result['records'][0]['data']['text'],'Page 1')
            self.assertEqual(result['records'][0]['data']['extraction_status'],'needs_review')
            self.assertEqual(result['extraction_coverage']['unresolved_pages'],[1])

    def test_explicit_refresh_replaces_cached_pdf_and_failure_preserves_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            sources=WorkspaceSources(root,PDFClient(),'http://localhost:5210')
            def result(text):
                return {'kind':'document','status':'extracted','extractor':'test','records':[{'locator':{'page':1},'data':{'text':text}}],'extraction_coverage':{'page_count':1,'pages_with_text':1,'unresolved_pages':[]}}
            with patch('workspace_data.pdf.extract_pdf',return_value=result('Header')):
                first=sources.upload('scan.pdf',b'%PDF-original')
            sid=first['source_id']
            with patch('workspace_data.pdf.extract_pdf',return_value=result('Header and recovered content')) as extract:
                sources.extract_media(sid)
                extract.assert_not_called()
                recovered=sources.extract_media(sid,refresh_pdf=True)
                self.assertEqual(recovered['records'][0]['data']['text'],'Header and recovered content')
            with patch('workspace_data.pdf.extract_pdf',side_effect=ValueError('OCR unavailable')):
                failed=sources.extract_media(sid,refresh_pdf=True)
            self.assertEqual(failed['status'],'extracted')
            self.assertEqual(failed['records'],recovered['records'])
            self.assertEqual(failed['extraction_run_id'],recovered['extraction_run_id'])
            self.assertIn('OCR unavailable',failed['refresh_error'])
            self.assertEqual(sources.download(sid)[0],b'%PDF-original')
            history=[json.loads(p.read_text()) for p in (Path(root)/sid/'extractions').glob('*/previous-manifest.json')]
            self.assertTrue(any(m.get('records') and m['records'][0]['data']['text']=='Header' for m in history))
            self.assertTrue(any(m.get('records') and m['records'][0]['data']['text']=='Header and recovered content' for m in history))
