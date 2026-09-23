import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from workspace_bond_interpret import interpret, validate


class BondInterpretTest(unittest.TestCase):
    def proposal(self):
        return {'inputs': {'face': 1000, 'coupon_rate': .05, 'annual_yield': None,
                           'periods': 20, 'frequency': 2},
                'explanation': 'Semiannual payments for ten years.', 'unresolved': ['Yield is not stated.']}

    def test_missing_values_remain_missing(self):
        self.assertIsNone(validate(self.proposal())['inputs']['annual_yield'])
        for invalid in [True, float('nan'), '5%']:
            value = self.proposal();value['inputs']['coupon_rate'] = invalid
            with self.assertRaises(ValueError):
                validate(value)

    @patch('workspace_bond_interpret.LocalProvider')
    def test_local_proposal_is_saved_and_lane_released(self, provider):
        worker = SimpleNamespace(guard=threading.Lock(), running={}, source_jobs=set(),
                                 provider=SimpleNamespace(host='127.0.0.1', port=5257,
                                                          model='bonsai', profile='legacy-greedy', seed=42))
        provider.return_value.generate.return_value = {'message': {'content': json.dumps(self.proposal())},
                                                       'finish_reason': 'stop', 'proxy_trace_id': 'test'}
        with tempfile.TemporaryDirectory() as root:
            result = interpret(worker, None, {'working': '1000 face, 5% coupon, ten years, semiannual'}, Path(root))
            self.assertTrue(result['review_required'])
            self.assertIsNone(result['inputs']['annual_yield'])
            self.assertTrue((Path(root)/'model-response.json').exists())
        self.assertEqual(worker.source_jobs, set())
        provider.return_value.generate.side_effect = RuntimeError('model failed')
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(RuntimeError):
                interpret(worker, None, {'working': 'x'}, Path(root))
        self.assertEqual(worker.source_jobs, set())
