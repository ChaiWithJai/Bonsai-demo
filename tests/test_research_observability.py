"""Live research capture must never be mislabeled as an instrumented replay."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from observability_api import Observability


class ResearchObservabilityTest(unittest.TestCase):
    def test_original_capture_provenance_and_vector_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            native = root / 'native-ui-records'
            native.mkdir()
            folder = root / 'research-records' / ('b' * 32)
            folder.mkdir(parents=True)
            request = b'{"messages":[{"role":"user","content":"pelican"}]}'
            (folder / 'request.json').write_bytes(request)
            identity = {'repo': 'official/model', 'revision': 'pinned-sha', 'dtype': 'bfloat16'}
            (folder / 'research.json').write_text(json.dumps({'model_identity': identity, 'status': 'completed',
                'started_at': 1, 'updated_at': 2, 'response': {'choices': [{'message': {'content': '<svg/>'}}]}}))
            raw = struct.pack('<2f', 1, -2)
            vector = folder / 'vector.f32'
            vector.write_bytes(raw)
            capture = {'kind': 'live_instrumented_inference', 'passed': True, 'model': identity,
                'source': {'research_id': folder.name, 'request_sha256': hashlib.sha256(request).hexdigest()},
                'samples': [{'step': 0, 'layer': 0, 'vector_file': str(vector), 'vector_length': 2,
                    'vector_sha256': hashlib.sha256(raw).hexdigest()}]}
            path = folder / 'activation-capture.json'
            path.write_text(json.dumps(capture))
            api = Observability(SimpleNamespace(directory=native), {})
            summary = api.sessions()['sessions'][0]
            self.assertEqual(summary['latest_output'], '<svg/>')
            self.assertEqual(summary['last_output'], '<svg/>')
            sid = summary['id']
            self.assertEqual(api.detail(sid)['session']['latest_output'], '<svg/>')
            result = {'identity': identity, 'source_request_sha256': hashlib.sha256(request).hexdigest(),
                      'generated_tokens': 12, 'seconds': 3, 'recorded_vectors': 39}
            result_path = folder / 'result.json'
            result_path.write_text(json.dumps(result))
            metrics = api.detail(sid)['nodes'][0]['research_metrics']
            self.assertEqual(metrics['output_tokens_per_total_second'], 4)
            self.assertEqual(metrics['recorded_vectors'], 39)
            self.assertIsNone(api.detail(sid)['nodes'][0]['elapsed_ms'])
            for key, wrong in [('identity', {'repo': 'different'}), ('source_request_sha256', 'wrong')]:
                result_path.write_text(json.dumps({**result, key: wrong}))
                self.assertNotIn('research_metrics', api.detail(sid)['nodes'][0])
            result_path.write_text(json.dumps(result))
            node = api.detail(sid)['nodes'][0]
            self.assertIn('activation_capture', node)
            self.assertNotIn('activation_replay', node)
            self.assertEqual(api.activation_vector(sid, node['id'], 0, 0)['values'], (1, -2))
            vector.write_bytes(struct.pack('<2f', 3, 4))
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                api.activation_vector(sid, node['id'], 0, 0)
            capture['model'] = {'repo': 'wrong/model'}
            path.write_text(json.dumps(capture))
            self.assertNotIn('activation_capture', api.detail(sid)['nodes'][0])
            capture['model'] = identity
            capture['source']['request_sha256'] = 'wrong'
            path.write_text(json.dumps(capture))
            self.assertNotIn('activation_capture', api.detail(sid)['nodes'][0])


if __name__ == '__main__':
    unittest.main()
