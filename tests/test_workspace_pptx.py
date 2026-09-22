import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from workspace_data.intake import extract, ingest
from workspace_data.pptx import extract_pptx

P='http://schemas.openxmlformats.org/presentationml/2006/main'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'

def deck(external=False, image_only=False, dtd=False):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('ppt/presentation.xml',f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst><p:sldId r:id="second"/><p:sldId r:id="first"/></p:sldIdLst></p:presentation>')
        mode=' TargetMode="External"' if external else ''
        z.writestr('ppt/_rels/presentation.xml.rels',f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="first" Type="{R}/slide" Target="slides/slide1.xml"/><Relationship Id="second" Type="{R}/slide" Target="slides/slide2.xml"{mode}/></Relationships>')
        z.writestr('ppt/slides/slide1.xml',f'<p:sld xmlns:p="{P}" show="0"><p:cSld><p:spTree/></p:cSld></p:sld>')
        body='' if image_only else '<p:sp><p:txBody><a:p><a:r><a:t>A &amp; B</a:t></a:r><a:br/><a:r><a:t>0</a:t></a:r></a:p></p:txBody></p:sp><p:graphicFrame><a:graphic><a:graphicData><a:tbl><a:tr><a:tc><a:txBody><a:p><a:r><a:t>0</a:t></a:r></a:p></a:txBody></a:tc><a:tc><a:txBody><a:p/></a:txBody></a:tc></a:tr></a:tbl></a:graphicData></a:graphic></p:graphicFrame>'
        prefix='<!DOCTYPE test>' if dtd else ''
        z.writestr('ppt/slides/slide2.xml',prefix+f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree>{body}</p:spTree></p:cSld></p:sld>')
        z.writestr('ppt/media/image1.png',b'not interpreted')
        z.writestr('ppt/notesSlides/notesSlide1.xml','not interpreted')
    return out.getvalue()

class PresentationIntakeTest(unittest.TestCase):
    def test_order_values_and_unread_coverage(self):
        result=extract('deck.pptx',deck())
        self.assertEqual([r['data'] for r in result['records']],[{'text':'A & B\n0'},{'cells':['0','']}])
        self.assertEqual(result['records'][0]['locator']['slide'],1)
        self.assertEqual(result['records'][0]['locator']['slide_part'],'ppt/slides/slide2.xml')
        self.assertEqual(result['records'][1]['locator']['table_row'],1)
        coverage=result['document_coverage']
        self.assertEqual(coverage['slides'][1],{'slide':2,'part':'ppt/slides/slide1.xml','hidden':True,'records':0})
        self.assertEqual(coverage['embedded_media_not_read'],1)
        self.assertEqual(coverage['other_parts_not_read'],['ppt/notesSlides/notesSlide1.xml'])
        self.assertTrue(result['requires_structuring'])

    def test_unsupported_and_unsafe_inputs_fail_explicitly(self):
        for raw in (b'not zip',deck(external=True),deck(image_only=True),deck(dtd=True)):
            with self.subTest(raw_length=len(raw)),self.assertRaises(ValueError):extract('deck.pptx',raw)
        with self.assertRaisesRegex(ValueError,'record limits'):extract_pptx(deck(),1)

    def test_failed_extraction_preserves_original(self):
        raw=deck(image_only=True)
        with tempfile.TemporaryDirectory() as root:
            result=ingest(root,'image-only.pptx',raw)
            self.assertEqual(result['status'],'extraction_failed')
            self.assertIn('visual extraction',result['extraction_error'])
            self.assertEqual((Path(root)/result['source_id']/'source.bin').read_bytes(),raw)
