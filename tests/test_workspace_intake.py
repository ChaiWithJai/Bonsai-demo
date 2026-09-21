import tempfile
import unittest
from pathlib import Path
from workspace_data.intake import ingest, extract_saved


class IntakeTest(unittest.TestCase):
    def test_csv_keeps_values_and_multiline_locator(self):
        with tempfile.TemporaryDirectory() as root:
            result = ingest(root, '../../observations.csv', b'name,value\n"two\nlines",0\nmissing,\n')
            self.assertEqual(result['filename'], 'observations.csv')
            self.assertEqual(result['records'][0]['data']['value'], '0')
            self.assertEqual(result['records'][1]['data']['value'], '')
            self.assertEqual(result['records'][0]['locator']['ending_line'], 3)
            self.assertTrue((Path(root) / result['source_id'] / 'source.bin').is_file())

    def test_same_source_has_stable_identity(self):
        with tempfile.TemporaryDirectory() as root:
            a = ingest(root, 'a.json', b'[{"value":null}]')
            b = ingest(root, 'renamed.json', b'[{"value":null}]')
            self.assertEqual(a['records'], b['records'])

    def test_media_is_pending_not_success(self):
        with tempfile.TemporaryDirectory() as root:
            result = ingest(root, 'clip.mp4', b'media fixture, not decoded')
            self.assertEqual(result['status'], 'needs_extractor')
            self.assertEqual(result['records'], [])

    def test_malformed_tables_and_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            for name, content in [('a.csv', b'x,x\n1,2'), ('a.csv', b'x,y\n1'),
                                  ('a.json', b'[{"x":NaN}]'), ('a.json', b'[1]')]:
                with self.subTest(content=content):
                    result=ingest(root, name, content)
                    self.assertEqual(result['status'],'extraction_failed')
                    self.assertEqual(result['records'],[])
                    self.assertTrue(result['extraction_error'])
                    self.assertEqual((Path(root)/result['source_id']/'source.bin').read_bytes(),content)
            self.assertEqual(len(list(Path(root).iterdir())),4)

    def test_jsonl_retains_original_line_numbers(self):
        with tempfile.TemporaryDirectory() as root:
            result = ingest(root, 'a.jsonl', b'\n{"a":1}\n\n{"a":2}\n')
            self.assertEqual([r['locator']['line'] for r in result['records']], [2, 4])

    def test_failed_extraction_can_retry_without_reupload_or_erasing_failure(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as root:
            raw=b'[{"value":0}]'
            with patch('workspace_data.intake.extract', side_effect=RuntimeError('Transient parser failure')):
                failed=ingest(root,'retry.json',raw)
            self.assertEqual(failed['status'],'extraction_failed')
            self.assertEqual(ingest(root,'renamed.json',raw),failed)
            fixed=extract_saved(root,failed)
            self.assertEqual(fixed['status'],'extracted')
            self.assertEqual(fixed['records'][0]['data']['value'],0)
            self.assertNotIn('extraction_error',fixed)
            self.assertNotEqual(fixed['extraction_attempt_id'],failed['extraction_attempt_id'])
            self.assertEqual(len(list((Path(root)/fixed['source_id']/'extractions').iterdir())),2)
            self.assertEqual((Path(root)/fixed['source_id']/'source.bin').read_bytes(),raw)

    def test_invalid_registration_and_corrupt_original_cannot_be_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            for name,raw in [('unknown.exe',b'bytes'),('empty.csv',b'')]:
                with self.assertRaises(ValueError):ingest(root,name,raw)
            self.assertEqual(list(Path(root).iterdir()),[])
            source=ingest(root,'a.csv',b'x,x\n1,2')
            (Path(root)/source['source_id']/'source.bin').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'integrity'):extract_saved(root,source)
