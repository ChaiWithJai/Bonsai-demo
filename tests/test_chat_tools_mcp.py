import json
import unittest
from unittest.mock import Mock
from chat_tools_mcp import dispatch


class ChatToolsTest(unittest.TestCase):
    def setUp(self):
        self.service = Mock()
        self.service.create.return_value = {'id': 'saved-session'}

    def request(self, method, params=None):
        return dispatch(self.service, {'jsonrpc': '2.0', 'id': 4, 'method': method, 'params': params or {}})

    def test_discovery_and_notifications(self):
        value = self.request('initialize', {'protocolVersion': '2025-03-26'})
        self.assertEqual(value['result']['protocolVersion'], '2025-03-26')
        names = [x['name'] for x in self.request('tools/list')['result']['tools']]
        self.assertEqual(names, ['calculate_bond', 'treasury_yields', 'jev_evidence_check', 'mayor_exercise', 'grade_mayor_exercise', 'prepare_mayor_report'])
        self.assertIsNone(dispatch(self.service, {'jsonrpc': '2.0', 'method': 'notifications/initialized'}))

    def test_calculation_is_saved_and_not_a_human_label(self):
        self.service.act.return_value = {'status': 'completed', 'result': {'price': 1000, 'payments': [{'period': 1}]}}
        args = {'face': 1000, 'coupon_rate': .05, 'annual_yield': .05, 'periods': 20, 'frequency': 2}
        value = self.request('tools/call', {'name': 'calculate_bond', 'arguments': args})['result']
        self.assertFalse(value['isError'])
        output = json.loads(value['content'][0]['text'])
        self.assertEqual(output['result']['price'], 1000)
        payload = self.service.act.call_args.args[1]
        self.assertEqual(payload['actor'], 'native_chat_tool')
        self.assertIn('not a human review label', payload['confirmation_scope'])

    def test_failed_gateway_is_not_presented_as_an_answer(self):
        self.service.act.return_value = {'status': 'failed', 'error': 'Gateway unavailable'}
        result = self.request('tools/call', {'name': 'jev_evidence_check', 'arguments': {'claim': 'x', 'evidence': 'y'}})['result']
        self.assertTrue(result['isError'])
        self.assertIn('Gateway unavailable', result['content'][0]['text'])

    def test_unknown_arguments_do_not_execute(self):
        result = self.request('tools/call', {'name': 'treasury_yields', 'arguments': {'year': 2026, 'url': 'https://elsewhere'}})['result']
        self.assertTrue(result['isError'])
        self.service.act.assert_not_called()
