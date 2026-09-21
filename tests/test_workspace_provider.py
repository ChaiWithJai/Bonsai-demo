import json
from pathlib import Path
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from workspace_provider import LocalProvider, ProviderError, GenerationCancelled


def chunk(delta=None, finish=None):
    return 'data: ' + json.dumps({'choices': [{'index': 0, 'delta': delta or {}, 'finish_reason': finish}]}) + '\r\n\r\n'


class Endpoint(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        self.server.requests.append((self.path, dict(self.headers), json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('X-Bonsai-Trace-ID', 'fixture-proxy-trace')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.flush()
        self.server.entered.set()
        if self.server.pause:
            self.server.release.wait(3)
        try:
            self.wfile.write(self.server.stream.encode())
        except (BrokenPipeError, ConnectionResetError):
            pass


class ProviderTest(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Endpoint)
        self.server.requests = []
        self.server.pause = False
        self.server.entered = threading.Event()
        self.server.release = threading.Event()
        self.server.stream = chunk({'content': 'hello'}, 'stop') + 'data: [DONE]\r\n\r\n'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.provider = LocalProvider(f'http://127.0.0.1:{self.server.server_port}', 'test-model', timeout=2)
        self.cancel = threading.Event()
        self.deltas = []
        self.tools = [{'type': 'function', 'function': {'name': 'read_file', 'parameters': {'type': 'object'}}}]

    def tearDown(self):
        self.server.release.set()
        self.server.shutdown()
        self.server.server_close()

    def generate(self):
        return self.provider.generate([{'role': 'user', 'content': 'edit existing'}], self.tools,
                                      'workspace-test', self.cancel, self.deltas.append, 512)

    def test_streams_native_tools_and_keeps_proxy_lineage(self):
        self.server.stream = (
            ': heartbeat\r\n\r\n' + chunk({'reasoning_content': 'Generated reasoning'})
            + chunk({'tool_calls': [{'index': 0, 'id': 'call1', 'function': {'name': 'read_', 'arguments': '{"path":'}}]})
            + chunk({'tool_calls': [{'index': 0, 'function': {'name': 'file', 'arguments': '"App.svelte"}'}}]}, 'tool_calls')
            + 'data: [DONE]\r\n\r\n')
        result = self.generate()
        self.assertEqual(result['message']['tool_calls'][0]['function'], {'name': 'read_file', 'arguments': '{"path":"App.svelte"}'})
        self.assertEqual(result['proxy_trace_id'], 'fixture-proxy-trace')
        self.assertEqual(self.server.requests[0][1]['X-Bonsai-Conversation'], 'workspace-test')
        self.assertEqual(self.server.requests[0][2]['model'], 'test-model')
        self.assertEqual(self.deltas[0]['field'], 'reasoning_content')

    def test_rejects_partial_and_truncated_completions_without_retry(self):
        for stream in [chunk({'content': 'partial'}, 'stop'),
                       chunk({'content': 'cut off'}, 'length') + 'data: [DONE]\n\n',
                       'data: {bad json}\n\n',
                       chunk({'tool_calls': [{'index': 0, 'id': 'x', 'function': {'name': 'shell', 'arguments': '{}'}}]}, 'tool_calls') + 'data: [DONE]\n\n']:
            self.server.stream = stream
            before = len(self.server.requests)
            with self.assertRaises(ProviderError):
                self.generate()
            self.assertEqual(len(self.server.requests), before + 1)

    def test_cancellation_interrupts_a_silent_stream(self):
        self.server.pause = True
        def cancel_when_connected():
            self.server.entered.wait(2)
            self.cancel.set()
        thread = threading.Thread(target=cancel_when_connected)
        thread.start()
        start = time.monotonic()
        with self.assertRaises(GenerationCancelled):
            self.generate()
        thread.join()
        self.assertLess(time.monotonic() - start, 1)

    def test_wall_clock_budget_interrupts_a_silent_stream(self):
        self.server.pause = True
        self.provider.timeout = 0.15
        start = time.monotonic()
        with self.assertRaises(ProviderError):
            self.generate()
        self.assertLess(time.monotonic() - start, 1)

    def test_cancel_before_start_does_not_send_request(self):
        self.cancel.set()
        with self.assertRaises(GenerationCancelled):
            self.generate()
        self.assertEqual(self.server.requests, [])

    def test_response_and_destination_limits(self):
        for endpoint in ['https://example.com', 'http://127.0.0.1:80/other', 'http://name:pass@localhost', 'http://localhost/?key=x']:
            with self.assertRaises(ValueError):
                LocalProvider(endpoint, 'model')
        self.provider.max_bytes = 1024
        self.server.stream = chunk({'content': 'a' * 1200}, 'stop') + 'data: [DONE]\n\n'
        with self.assertRaises(ProviderError):
            self.generate()


if __name__ == '__main__':
    unittest.main()
