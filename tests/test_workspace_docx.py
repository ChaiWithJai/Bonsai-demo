import io
import zipfile
import unittest
from workspace_data.intake import extract


def document(body):
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body + '</w:body></w:document>')
        archive.writestr('word/media/image1.png', b'not interpreted')
    return out.getvalue()

class WordIntakeTest(unittest.TestCase):
    def test_paragraphs_tables_and_locations_preserve_values(self):
        result = extract('data.docx', document('<w:p><w:r><w:t>A &amp; B</w:t><w:tab/><w:t>0</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>0</w:t></w:r></w:p></w:tc><w:tc><w:p/></w:tc></w:tr></w:tbl>'))
        self.assertEqual(result['records'][0]['data']['text'], 'A & B\t0')
        self.assertEqual(result['records'][1]['data']['cells'], ['0', ''])
        self.assertEqual(result['records'][1]['locator']['table_row'], 1)
        self.assertEqual(result['document_coverage']['embedded_media_not_read'], 1)
        self.assertTrue(result['requires_structuring'])

    def test_unreadable_and_image_only_files_fail_explicitly(self):
        for raw in (b'not a zip', document('<w:p><w:drawing/></w:p>')):
            with self.assertRaises(ValueError): extract('data.docx', raw)

    def test_text_boxes_are_not_mixed_into_body_text(self):
        result = extract('data.docx', document('<w:p><w:r><w:t>Body</w:t><w:drawing><w:txbxContent><w:p><w:r><w:t>Box</w:t></w:r></w:p></w:txbxContent></w:drawing></w:r></w:p>'))
        self.assertEqual(result['records'][0]['data']['text'], 'Body')
