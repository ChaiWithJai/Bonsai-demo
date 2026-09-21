import tempfile
import unittest
from pathlib import Path
from workspace_data.intake import ingest


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
                with self.subTest(content=content), self.assertRaises(ValueError):
                    ingest(root, name, content)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_jsonl_retains_original_line_numbers(self):
        with tempfile.TemporaryDirectory() as root:
            result = ingest(root, 'a.jsonl', b'\n{"a":1}\n\n{"a":2}\n')
            self.assertEqual([r['locator']['line'] for r in result['records']], [2, 4])
