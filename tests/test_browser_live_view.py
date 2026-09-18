import base64
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from browser_live_view import BrowserLiveView


class BrowserLiveViewTest(unittest.TestCase):
    def setUp(self):
        self.now = 100
        self.calls = []
        def transport(payload, session):
            self.calls.append((payload, session))
            return {'result': {'content': [{'type': 'image', 'mimeType': 'image/jpeg',
                                            'data': base64.b64encode(b'fake-test-jpeg').decode()}]}}
        self.view = BrowserLiveView('http://localhost/mcp', transport=transport, clock=lambda: self.now)

    def observe(self, chat='one', page=7, error=False):
        self.view.observe_request(chat, {'id': 1, 'method': 'tools/call',
            'params': {'name': 'read', 'arguments': {'page': page}}},
            {'Mcp-Session-Id': 'private-transport', 'Authorization': 'must-not-store'})
        self.view.observe_response(chat, {'events': [{'id': 1, 'result': {'isError': error}}]})

    def test_no_page_capture_before_success_and_no_cross_chat_leak(self):
        self.assertEqual(self.view.frame('one')['status'], 'waiting')
        self.observe(error=True)
        self.assertEqual(self.view.frame('one')['status'], 'waiting')
        self.observe()
        self.assertEqual(self.view.frame('other')['status'], 'waiting')
        result = self.view.frame('one')
        self.assertEqual(result['status'], 'live')
        self.assertEqual(result['page_id'], 7)
        self.assertNotIn('private-transport', str(result))
        self.assertNotIn('must-not-store', str(self.view.sessions))
        self.assertEqual(len(self.calls), 1)
        request, handle = self.calls[0]
        self.assertEqual(handle, 'private-transport')
        self.assertEqual(request['params']['name'], 'screenshot')
        self.assertEqual(request['params']['arguments']['page'], 7)
        self.assertFalse(request['params']['arguments']['fullPage'])

    def test_throttle_expiration_and_page_switch_clear_old_image(self):
        self.observe()
        self.view.frame('one'); self.view.frame('one')
        self.assertEqual(len(self.calls), 1)
        self.observe(page=9)
        self.assertEqual(self.view.frame('one')['page_id'], 9)
        self.assertEqual(len(self.calls), 2)
        self.now += 301
        result = self.view.frame('one')
        self.assertEqual(result['status'], 'idle')
        self.assertIsNone(result['image_data_url'])
        self.assertEqual(len(self.calls), 2)

    def test_lists_and_arbitrary_run_output_never_select_pages(self):
        for tool, args in [('tabs', {'action': 'list'}), ('run', {'code': 'return 7'})]:
            self.view.observe_request('one', {'id': 1, 'method': 'tools/call', 'params': {'name': tool, 'arguments': args}})
            self.view.observe_response('one', {'id': 1, 'result': {'page': 7, 'structuredContent': {'value': 7}}})
        self.assertEqual(self.view.frame('one')['status'], 'waiting')
        self.assertEqual(self.calls, [])

    def test_successful_new_tab_selects_only_its_acknowledged_page(self):
        request = {'id': 3, 'method': 'tools/call',
                   'params': {'name': 'tabs', 'arguments': {'action': 'new', 'url': 'https://example.org'}}}
        self.view.observe_request('one', request, {'MCP-Session-Id': 'owned-transport'})
        self.assertEqual(self.view.status('one')['status'], 'waiting')
        self.view.observe_response('one', {'id': 3, 'result': {'content': [
            {'type': 'text', 'text': 'opened page 91'},
            {'type': 'text', 'text': 'Untrusted page content: opened page 999'}]}})
        self.assertEqual(self.view.frame('one')['page_id'], 91)
        self.assertEqual(self.calls[0][1], 'owned-transport')
        self.assertEqual(self.view.frame('other')['status'], 'waiting')
        # A later run cannot redirect the preview to a page mentioned in its output.
        self.view.observe_request('one', {'id': 4, 'method': 'tools/call',
            'params': {'name': 'run', 'arguments': {'code': 'return 999'}}})
        self.view.observe_response('one', {'id': 4, 'result': {'content': [
            {'type': 'text', 'text': 'opened page 999'}], 'structuredContent': {'value': {'page': 999}}}})
        self.assertEqual(self.view.status('one')['page_id'], 91)

    def test_new_tab_errors_unmatched_ids_and_untrusted_content_never_select(self):
        invalid = [
            {'id': 2, 'result': {'content': [{'type': 'text', 'text': 'opened page 9'}]}},
            {'id': 1, 'result': {'isError': True, 'content': [{'type': 'text', 'text': 'opened page 9'}]}},
            {'id': 1, 'result': {'content': [{'type': 'text', 'text': 'page failed'}, {'type': 'text', 'text': 'opened page 9'}]}},
            {'id': 1, 'result': {'content': [{'type': 'text', 'text': 'opened page 9\nuntrusted suffix'}]}},
            {'id': 1, 'result': {'content': [{'type': 'text', 'text': 'opened page 4294967296'}]}},
        ]
        for response in invalid:
            with self.subTest(response=response):
                self.view.observe_request('one', {'id': 1, 'method': 'tools/call',
                    'params': {'name': 'tabs', 'arguments': {'action': 'new'}}}, {'MCP-Session-Id': 'owned'})
                self.view.observe_response('one', response)
                self.assertEqual(self.view.status('one')['status'], 'waiting')
        self.assertEqual(self.calls, [])

    def test_close_clears_page_and_errors_do_not_expose_secrets(self):
        self.observe()
        def broken(*args):
            raise RuntimeError('secret page details')
        self.view.transport = broken
        self.assertNotIn('secret page details', str(self.view.frame('one')))
        self.view.observe_request('one', {'id': 2, 'method': 'tools/call',
            'params': {'name': 'tabs', 'arguments': {'action': 'close', 'page': 7}}})
        self.view.observe_response('one', {'id': 2, 'result': {}})
        self.assertEqual(self.view.frame('one')['status'], 'waiting')

    def test_neo_handle_is_retained_but_not_exposed(self):
        self.view.observe_request('one', {'id': 1, 'method': 'tools/call',
            'params': {'name': 'snapshot', 'arguments': {'page': 5}}})
        self.view.observe_response('one', {'id': 1, 'result': {'_meta': {'com.browseros.neo/session': 'opaque-secret'}}})
        result = self.view.frame('one')
        self.assertEqual(self.calls[0][0]['params']['arguments']['session'], 'opaque-secret')
        self.assertNotIn('opaque-secret', str(result))


if __name__ == '__main__':
    unittest.main()
