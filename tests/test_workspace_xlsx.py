"""Minimal OOXML test inputs exercise extraction, not workbook authoring."""
import io
import json
import tempfile
import unittest
import zipfile
from workspace_data.intake import extract, ingest
from workspace_data.xlsx import extract_xlsx


def workbook(sheet_xml=None):
    sheet_xml = sheet_xml or '''<row r="1"><c r="A1" t="inlineStr"><is><t>Model</t></is></c><c r="B1" t="inlineStr"><is><t>Count</t></is></c></row>
    <row r="2"><c r="A2" t="inlineStr"><is><t>A</t></is></c><c r="B2"><v>0</v></c><c r="C2" t="b"><v>0</v></c></row>
    <row r="3"><c r="A3"><f>SUM(B2,12)</f><v>12</v></c><c r="B3"><f>1+1</f></c><c r="C3" t="e"><v>#DIV/0!</v></c></row>'''
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('[Content_Types].xml','''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>''')
        z.writestr('xl/workbook.xml','''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Observations" sheetId="1" r:id="rId1"/><sheet name="Notes" sheetId="2" state="hidden" r:id="rId2"/></sheets></workbook>''')
        z.writestr('xl/_rels/workbook.xml.rels','''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/></Relationships>''')
        z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+sheet_xml+'</sheetData></worksheet>')
        z.writestr('xl/worksheets/sheet2.xml','''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Development fixture, not release evidence</t></is></c></row></sheetData></worksheet>''')
        z.writestr('xl/media/image1.png',b'unread fixture')
    return out.getvalue()


class WorkbookIntakeTest(unittest.TestCase):
    def test_preserves_values_formula_caches_and_hidden_sheet_provenance(self):
        result=extract('data.xlsx',workbook())
        cells={r['locator']['sheet']+'!'+r['locator']['cell']:r for r in result['records']}
        self.assertEqual(cells['Observations!B2']['data']['value'],0)
        self.assertIs(cells['Observations!C2']['data']['value'],False)
        self.assertEqual(cells['Observations!A3']['data']['formula'],'=SUM(B2,12)')
        self.assertEqual(cells['Observations!A3']['data']['value'],12)
        self.assertEqual(cells['Observations!A3']['data']['value_origin'],'cached_formula_result_unverified')
        self.assertIsNone(cells['Observations!B3']['data']['value'])
        self.assertEqual(cells['Observations!B3']['data']['value_origin'],'formula_result_unavailable')
        self.assertEqual(cells['Observations!C3']['data']['value'],'#DIV/0!')
        self.assertEqual(cells['Notes!A1']['locator']['sheet_state'],'hidden')
        self.assertEqual(result['workbook_coverage']['formulas_without_cached_value'],1)
        self.assertEqual(result['workbook_coverage']['embedded_media_not_read'],1)
        self.assertTrue(result['requires_structuring'])
        json.dumps(result,allow_nan=False)

    def test_original_and_cell_identity_survive_reupload(self):
        with tempfile.TemporaryDirectory() as root:
            raw=workbook();a=ingest(root,'data.xlsx',raw);b=ingest(root,'renamed.xlsx',raw)
            self.assertEqual(a,b)
            self.assertEqual(a['records'][0]['locator']['cell'],'A1')
            self.assertTrue(a['records'][0]['id'].startswith(a['source_id']))

    def test_cell_limit_and_malformed_archive_fail(self):
        with self.assertRaises(ValueError):extract_xlsx(workbook(),2)
        with self.assertRaises(ValueError):extract('bad.xlsx',b'not a workbook')

    def test_large_sparse_grid_is_bounded(self):
        raw=workbook(''.join(f'<row r="{i}"><c r="XFD{i}"><v>1</v></c></row>' for i in range(1,21)))
        with self.assertRaisesRegex(ValueError,'scanned cell'):extract('wide.xlsx',raw)

    def test_iso_dates_and_invalid_sheet_xml(self):
        result=extract('date.xlsx',workbook('<row r="1"><c r="A1" t="d"><v>2026-09-21T00:00:00</v></c></row>'))
        self.assertEqual(result['records'][0]['data']['value'],'2026-09-21T00:00:00')
        self.assertEqual(result['records'][0]['data']['cell_type'],'d')
        with self.assertRaises(ValueError):extract('broken.xlsx',workbook('<not-closed>'))

    def test_excel_serial_dates_respect_the_workbook_epoch(self):
        original=workbook('<row r="1"><c r="A1" s="1"><v>1</v></c></row>')
        out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original)) as src, zipfile.ZipFile(out,'w') as dest:
            for item in src.infolist():
                raw=src.read(item)
                if item.filename=='xl/workbook.xml':raw=raw.replace(b'<sheets>',b'<workbookPr date1904="1"/><sheets>')
                dest.writestr(item,raw)
            dest.writestr('xl/styles.xml','''<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font/></fonts><fills count="1"><fill><patternFill/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf/><xf numFmtId="14"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>''')
        result=extract('dates.xlsx',out.getvalue())
        self.assertEqual(result['records'][0]['data']['value'],'1904-01-02T00:00:00')
        self.assertEqual(result['workbook_coverage']['date_system'],'1904-01-01')

    def test_boolean_evidence_accepts_json_notation_but_not_the_opposite(self):
        from workspace_data.proposal import structured_manifest
        manifest={'source_id':'source','records':[{'id':'source:0','locator':{'cell':'C2'},'data':{'value':False}}]}
        for quote in ('false','False',' false '):
            structure={'rationale':'Preserve the boolean cell','records':[{'values':{'value':False},'evidence':[{'record_id':'r1','field':'value','quote':quote}]}]}
            self.assertIs(structured_manifest(manifest,structure,{'r1':'source:0'})['records'][0]['data']['value'],False)
        for quote in ('true','True','alse'):
            structure['records'][0]['evidence'][0]['quote']=quote
            with self.assertRaises(ValueError):structured_manifest(manifest,structure,{'r1':'source:0'})
