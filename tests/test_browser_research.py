import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from browser_research import BrowserResearch, public_url, sanitized_response, extract_search_evidence, research_messages


class BrowserResearchTest(unittest.TestCase):
    def test_search_results_survive_navigation_noise_without_invented_links(self):
        original = '[AI Mode](https://www.google.com/search?q=' + 'x'*5000 + ')\n# Search Results\nAI Overview text\n## Web results\n[Grant program](https://example.org/grants)\nObserved deadline unknown.'
        text, metadata = extract_search_evidence(original)
        self.assertTrue(text.startswith('## Web results'))
        self.assertIn('[Grant program](https://example.org/grants)', text[:3500])
        self.assertNotIn('AI Overview', text)
        self.assertFalse(metadata['claims_generated'])
        self.assertIn('Research date:', research_messages({'prompt':'x'})[0]['content'])
    def test_handle_redaction_preserves_source_text(self):
        raw = b'data: {"id":1,"result":{"_meta":{"com.browseros.neo/session":"secret-handle"},"content":[{"type":"text","text":"grant source"}]}}\n\n'
        stored = sanitized_response(raw, 'text/event-stream')
        self.assertNotIn(b'secret-handle', stored)
        self.assertIn(b'grant source', stored)
        self.assertIn(b'session handle redacted', stored)
    def test_owned_new_tabs_only_separate_clients_and_links_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = [[], []]
            browsers = []
            def make_transport(index):
                def transport(payload):
                    calls[index].append(payload)
                    method = payload['method']
                    if method == 'notifications/initialized':
                        return {}
                    result = {}
                    if method == 'tools/list':
                        result = {'tools': [{'name': 'tabs'}, {'name': 'read'}]}
                    if method == 'tools/call':
                        params = payload['params']; page = 100 + index
                        if params['name'] == 'tabs':
                            self.assertEqual(params['arguments']['action'], 'new')
                            result = {'content': [{'type': 'text', 'text': f'opened page {page}'}]}
                        else:
                            self.assertEqual(params['arguments']['page'], page)
                            self.assertEqual(params['arguments']['format'], 'markdown')
                            self.assertTrue(params['arguments']['includeLinks'])
                            result = {'content': [{'type': 'text', 'text': '[Official program](https://example.org/grant)'}]}
                    return {'id': payload.get('id'), 'result': result}
                return transport
            for i in range(2):
                browser = BrowserResearch(Path(folder)/str(i), transport=make_transport(i), validator=lambda url: url,
                                          client_name=f'model-{i}')
                browsers.append(browser)
                answer = browser.call('browser_search', {'query': 'community data center grants'})
                self.assertIn('https://example.org/grant', answer['content'])
                self.assertEqual(answer['source']['url_provenance'], 'requested_only')
            self.assertEqual(browsers[0].pages, {100})
            self.assertEqual(browsers[1].pages, {101})
            self.assertIsNot(browsers[0].pages, browsers[1].pages)
            self.assertEqual([p['method'] for p in calls[0]][:3], ['initialize', 'notifications/initialized', 'tools/list'])

    def test_private_and_account_urls_blocked_before_network_navigation(self):
        resolver = lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))]
        for url in ['http://example.org', 'file:///tmp/x', 'https://localhost/x', 'https://mail.google.com/x',
                    'https://drive.google.com/x', 'https://user:pass@example.org/x']:
            with self.assertRaises(ValueError):
                public_url(url, resolver)
        with self.assertRaises(ValueError):
            public_url('https://example.org', lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))])
        self.assertEqual(public_url('https://example.org/grants', resolver), 'https://example.org/grants')

    def test_browser_failure_is_not_returned_as_source(self):
        with tempfile.TemporaryDirectory() as folder:
            browser = BrowserResearch(Path(folder)/'browser', transport=lambda p: {'error': {'message': 'failed'}})
            with self.assertRaises(RuntimeError):
                browser.call('browser_search', {'query': 'grants'})
            self.assertEqual(browser.sources, [])


if __name__ == '__main__':
    unittest.main()
