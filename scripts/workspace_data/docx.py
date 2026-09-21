"""Extract DOCX body paragraphs and tables without executing embedded content."""
import io
import zipfile
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def extract_docx(content, max_rows):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            if len(infos) > 5000 or sum(i.file_size for i in infos) > 100 * 1024 * 1024:
                raise ValueError('Word document exceeds expanded-size limits')
            raw = archive.read('word/document.xml')
            if len(raw) > 20 * 1024 * 1024 or b'<!DOCTYPE' in raw or b'<!ENTITY' in raw:
                raise ValueError('Word document XML exceeds supported limits')
            document = ET.fromstring(raw)
            media = sum(i.filename.startswith('word/media/') for i in infos)
            extras = [i.filename for i in infos if i.filename.startswith(('word/header', 'word/footer', 'word/footnotes', 'word/endnotes', 'word/comments'))]
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ValueError('Could not read the Word document body') from exc
    body = document.find(W + 'body')
    if body is None:
        raise ValueError('Word document has no body')

    def text(node):
        parts = []
        def walk(el):
            if el.tag in (W + 'drawing', W + 'pict', W + 'txbxContent'):
                return
            if el.tag == W + 't': parts.append(el.text or '')
            elif el.tag == W + 'tab': parts.append('\t')
            elif el.tag in (W + 'br', W + 'cr'): parts.append('\n')
            for child in el: walk(child)
        walk(node)
        return ''.join(parts)

    records = []
    for ordinal, block in enumerate(body, 1):
        if block.tag == W + 'p':
            value = text(block)
            if value.strip():
                records.append({'locator': {'document_part': 'word/document.xml', 'body_block': ordinal, 'type': 'paragraph'}, 'data': {'text': value}})
        elif block.tag == W + 'tbl':
            for row_index, row in enumerate(block.findall(W + 'tr'), 1):
                cells = ['\n'.join(text(p) for p in cell.findall(W + 'p')) for cell in row.findall(W + 'tc')]
                if any(cell.strip() for cell in cells):
                    records.append({'locator': {'document_part': 'word/document.xml', 'body_block': ordinal, 'table_row': row_index},
                                    'data': {'cells': cells}})
        if len(records) > max_rows:
            raise ValueError('Word document exceeds record limits')
    if not records:
        raise ValueError('No readable body text in Word document; image-only content requires OCR')
    return {'kind': 'document', 'status': 'extracted', 'extractor': 'docx-body-xml-v1',
            'requires_structuring': True, 'records': records,
            'document_coverage': {'scope': 'Body paragraphs and table cells; no page-layout reconstruction',
                         'embedded_media_not_read': media, 'other_parts_not_read': extras,
                         'limitations': 'Images, charts, text boxes, headers, footers, notes, comments, and tracked-change interpretation are not extracted.'}}
