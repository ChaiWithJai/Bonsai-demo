import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from workspace_learning import LearningWorkstreams


class LearningTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        client = Mock()
        client.get_experiment_by_name.return_value = SimpleNamespace(experiment_id='1')
        client.create_run.return_value = SimpleNamespace(info=SimpleNamespace(run_id='run'))
        self.worker = SimpleNamespace(store=SimpleNamespace(root=Path(self.temp.name)), client=client,
                                      tracking_uri='http://localhost:5210')
        self.service = LearningWorkstreams(self.worker)
        self.key = self.service.create('bond_math')['id']
        self.request = {'operation': 'calculate_bond', 'confirmed': True,
                        'inputs': {'face': 1000, 'coupon_rate': .05, 'annual_yield': .05,
                                   'periods': 20, 'frequency': 2}}

    def test_confirmed_result_survives_service_recreation(self):
        result = self.service.act(self.key, self.request)
        self.assertAlmostEqual(result['result']['price'], 1000)
        loaded = LearningWorkstreams(self.worker).get(self.key)['actions'][0]
        self.assertEqual(loaded['request'], self.request)
        self.assertEqual(loaded['status'], 'completed')
        self.worker.client.log_artifacts.assert_called_once()

    def test_unconfirmed_calculation_does_not_create_action(self):
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            self.service.act(self.key, {**self.request, 'confirmed': False})
        self.assertEqual(self.service.get(self.key)['actions'], [])

    @patch('workspace_learning.gateway_request')
    def test_cloud_is_explicit_and_failures_are_saved(self, gateway):
        request = {'operation': 'evaluate_evidence', 'claim': 'x', 'evidence': 'y'}
        with self.assertRaises(ValueError):
            self.service.act(self.key, request)
        gateway.assert_not_called()
        gateway.side_effect = RuntimeError('private provider error')
        result = self.service.act(self.key, {**request, 'cloud_evaluation_requested': True})
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('private', result['error'])
        self.assertEqual(self.service.get(self.key)['actions'][0]['status'], 'failed')

    def test_mlflow_outage_does_not_lose_calculation(self):
        self.worker.client.get_experiment_by_name.side_effect = RuntimeError('offline')
        result = self.service.act(self.key, self.request)
        self.assertEqual(result['status'], 'completed')
        self.assertIn('trace_error', result)
