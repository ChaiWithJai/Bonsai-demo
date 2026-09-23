import subprocess
import unittest
from unittest.mock import patch

from workspace_gateway import GatewayError, gateway_request


class GatewayBridgeTest(unittest.TestCase):
    @patch('workspace_gateway.subprocess.run')
    def test_serializes_without_shell_and_decodes_result(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, '{"review_required":true}', '')
        result = gateway_request({'operation': 'evaluate_evidence', 'claim': '$(no shell)', 'evidence': 'Source'})
        self.assertTrue(result['review_required'])
        args, kwargs = run.call_args
        self.assertEqual(args[0][0], 'node')
        self.assertNotIn('shell', kwargs)
        self.assertIn('$(no shell)', kwargs['input'])

    @patch('workspace_gateway.subprocess.run')
    def test_provider_error_does_not_expose_stderr(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, '', 'SECRET provider error')
        with self.assertRaises(GatewayError) as error:
            gateway_request({'operation': 'evaluate_evidence'})
        self.assertNotIn('SECRET', str(error.exception))

    @patch('workspace_gateway.subprocess.run')
    def test_timeout_stays_a_failure(self, run):
        run.side_effect = subprocess.TimeoutExpired('node', 130)
        with self.assertRaisesRegex(GatewayError, 'timed out'):
            gateway_request({'operation': 'evaluate_evidence'})
