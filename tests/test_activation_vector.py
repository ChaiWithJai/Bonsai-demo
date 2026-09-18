import hashlib
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from observability_api import Observability

class VectorTest(unittest.TestCase):
    def test_verified_selected_vector_and_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); vector = root / 'v.f32'
            vector.write_bytes(struct.pack('<3f', -1, 0, 2))
            sample = {'step': 2, 'layer': 31, 'vector_file': str(vector), 'vector_length': 3,
                      'vector_sha256': hashlib.sha256(vector.read_bytes()).hexdigest()}
            obs = object.__new__(Observability)
            obs.recorder = SimpleNamespace(directory=root); obs.manifest = None
            obs.detail = lambda sid: {'nodes': [{'id': 'selected', 'activation_replay': {'samples': [sample]}}]}
            result = obs.activation_vector('session', 'selected', 2, 31)
            self.assertEqual(result['values'], (-1, 0, 2))
            with self.assertRaises(KeyError): obs.activation_vector('session', 'other', 2, 31)
            with self.assertRaises(KeyError): obs.activation_vector('session', 'selected', 3, 31)
            vector.write_bytes(struct.pack('<3f', 1, 0, 2))
            with self.assertRaises(ValueError): obs.activation_vector('session', 'selected', 2, 31)
            sample['vector_file'] = '/etc/passwd'
            with self.assertRaises(ValueError): obs.activation_vector('session', 'selected', 2, 31)

if __name__ == '__main__': unittest.main()
