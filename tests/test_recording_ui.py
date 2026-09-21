import contextlib
import http.client
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

spec = importlib.util.spec_from_file_location("recording_ui", Path(__file__).resolve().parents[1] / "scripts/recording_ui.py")
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        raw = json.dumps({"ui_settings": {}, "cors_proxy_enabled": False}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.server.seen = (body, dict(self.headers), self.path)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        raw = b'data: {"choices":[{"delta":{"content":"real upstream text"}}]}\n\ndata: [DONE]\n\n'
        self.send_header("Content-Length", str(len(raw) + (9 if body == b"truncate" else 0)))
        self.end_headers()
        self.wfile.write(raw)


class Capture:
    @contextlib.contextmanager
    def exchange(self, kind, body, session, model_info):
        self.state = {"complete": False, "trace_id": "test-only"}
        self.output = io.BytesIO()
        self.body, self.session, self.kind = body, session, kind
        try:
            yield self.state, self.output
        except Exception as exc:
            self.state["error"] = type(exc).__name__
            raise


class RecordingUITest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        (root / "index.html").write_text("<html><head></head><body>llama-ui</body></html>")
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        self.proxy = ThreadingHTTPServer(("127.0.0.1", 0), ui.Handler)
        self.proxy.static = root
        self.proxy.upstream = f"http://127.0.0.1:{self.upstream.server_port}"
        self.proxy.browseros = self.proxy.upstream + "/mcp"
        self.proxy.recorder = Capture()
        self.proxy.model_info = {"model_path": "test fixture only"}
        for server in (self.upstream, self.proxy):
            threading.Thread(target=server.serve_forever, daemon=True).start()

    def tearDown(self):
        for server in (self.proxy, self.upstream):
            server.shutdown()
            server.server_close()
        self.temp.cleanup()

    def call(self, method, path, body=None, headers=None):
        with contextlib.closing(http.client.HTTPConnection("127.0.0.1", self.proxy.server_port, timeout=3)) as conn:
            conn.request(method, path, body, headers or {})
            response = conn.getresponse()
            return response.status, response.read()

    def test_activation_replay_rejects_cross_site(self):
        status, _ = self.call("POST", "/api/activation-replay", '{}', {'Origin': 'https://example.invalid'})
        self.assertEqual(status, 403)

    def test_activation_replay_only_resolves_selected_inference(self):
        from types import SimpleNamespace
        root = Path(self.temp.name)
        request_id = 'a' * 32
        directory = root / request_id
        directory.mkdir()
        (directory / 'server-info.json').write_text('{}')
        calls = []
        def enqueue(path):
            calls.append(path)
            (path / 'activation-replay-status.json').write_text('{"status":"queued"}')
        self.proxy.recorder.directory = root
        self.proxy.recorder.replay_worker = SimpleNamespace(enqueue=enqueue)
        self.proxy.observability = SimpleNamespace(detail=lambda sid: {'nodes': [{'id':request_id, 'request_id':request_id, 'kind':'completion'}]})
        status, body = self.call('POST', '/api/activation-replay', json.dumps({'session_id':'chat','node_id':request_id}))
        self.assertEqual(status,202)
        self.assertEqual(calls,[directory])
        status, _ = self.call('POST', '/api/activation-replay', json.dumps({'session_id':'chat','node_id':'../evil'}))
        self.assertEqual(status,400)
        self.assertEqual(len(calls),1)

    def test_inference_is_byte_identical_and_session_not_forwarded(self):
        raw = b'{ "messages": [{"role":"user","content":"test"}], "temperature":0.37,"stream":true }'
        status, result = self.call("POST", "/v1/chat/completions", raw,
                                   {ui.SESSION: "conversation-one", "Content-Type": "application/json"})
        self.assertEqual(status, 200)
        self.assertEqual(self.upstream.seen[0], raw)
        self.assertNotIn(ui.SESSION, self.upstream.seen[1])
        self.assertEqual(result, self.proxy.recorder.output.getvalue())
        self.assertEqual(self.proxy.recorder.session, "conversation-one")
        self.assertTrue(self.proxy.recorder.state["complete"])

    def test_truncated_upstream_marked_incomplete(self):
        self.call("POST", "/v1/chat/completions", b"truncate")
        self.assertFalse(self.proxy.recorder.state["complete"])
        self.assertEqual(self.proxy.recorder.state["error"], "IncompleteRead")

    def test_only_configured_mcp_relay_unwraps_headers(self):
        from urllib.parse import quote
        self.call("POST", "/cors-proxy?url=" + quote(self.proxy.browseros), b'{"method":"tools/list"}',
                  {"x-llama-server-proxy-header-Content-Type": "application/json"})
        self.assertEqual(self.upstream.seen[2], "/mcp")
        self.assertEqual(self.upstream.seen[1]["Content-Type"], "application/json")
        self.assertEqual(self.proxy.recorder.kind, "mcp")
        self.call("POST", "/cors-proxy?url=http%3A%2F%2Fexample.invalid%2Fmcp", b"{}")
        self.assertTrue(self.upstream.seen[2].startswith("/cors-proxy?"))

    def test_html_and_props_seed_browseros(self):
        status, body = self.call("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b'/bonsai-observability.js', body)
        _, body = self.call("GET", "/props")
        props = json.loads(body)
        server = json.loads(props["ui_settings"]["mcpServers"])[0]
        self.assertTrue(server["useProxy"])
        self.assertEqual(server["url"], self.proxy.browseros)

    def test_cross_origin_bridge_accepts_only_known_ui(self):
        status, _ = self.call("POST", "/browseros/mcp", b"{}", {"Origin": "http://127.0.0.1:8080", "Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 200)
        self.assertFalse(any(k.lower().startswith("sec-fetch-") for k in self.upstream.seen[1]))
        status, _ = self.call("POST", "/browseros/mcp", b"{}", {"Origin": "https://example.invalid"})
        self.assertEqual(status, 403)

    def test_sse_multiline_and_done(self):
        parsed = ui.parse_response(b'data: {"a":\r\ndata: 1}\r\n\r\ndata: [DONE]\r\n\r\n', "text/event-stream")
        self.assertEqual(parsed["events"], [{"a": 1}])
        self.assertTrue(parsed["done_marker"])

    def test_browser_view_is_scoped_and_rejects_cross_site_requests(self):
        class View:
            def frame(self, session):
                return {"status": "waiting", "session": session}
        self.proxy.browser_view = View()
        status, raw = self.call("GET", "/api/browser-view/chat-one")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["session"], "chat-one")
        status, _ = self.call("GET", "/api/browser-view/chat-one", headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 403)
        status, _ = self.call("GET", "/api/browser-view/%2E%2E%2Fprivate")
        self.assertEqual(status, 404)

    def test_browser_view_missing_configuration_is_explicit(self):
        status, _ = self.call("GET", "/api/browser-view/chat-one")
        self.assertEqual(status, 503)

    def test_comparison_stream_and_origin_boundaries(self):
        class Comparison:
            def status(self):
                return {"ready": True}
            def validate(self, body):
                if not isinstance(body, dict) or not body.get("prompt"):
                    raise ValueError("prompt required")
                return body
            def run(self, body, emit, cancel_event=None):
                emit("delta", {"model": "fixture", "content": body["prompt"]})
                emit("done", {"status": "complete"})
        self.proxy.comparison = Comparison()
        code, raw = self.call("POST", "/api/comparison/run", b'{"prompt":"bounded fixture"}')
        self.assertEqual(code, 200)
        self.assertIn(b'event: delta\n', raw)
        self.assertIn(b'bounded fixture', raw)
        self.assertIn(b'event: done\n', raw)
        code, _ = self.call("POST", "/api/comparison/run", b'{}')
        self.assertEqual(code, 400)
        code, _ = self.call("POST", "/api/comparison/run", b'{"prompt":"x"}', {"Sec-Fetch-Site":"cross-site"})
        self.assertEqual(code, 403)
        code, _ = self.call("GET", "/api/comparison/status", headers={"Origin":"https://example.invalid"})
        self.assertEqual(code, 403)
        code, _ = self.call("DELETE", "/api/comparison/run")
        self.assertEqual(code, 405)

    def test_streamed_tool_arguments_assembled_without_changes(self):
        events = [
            {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "id": "call1", "function": {"name": "read", "arguments": '{"page":'}}]}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "function": {"arguments": "22}"}}]}, "finish_reason": "tool_calls"}]},
        ]
        raw = b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events)
        parsed = ui.parse_response(raw, "text/event-stream")
        self.assertEqual(parsed["choices"][0]["message"]["tool_calls"][0]["function"], {"name": "read", "arguments": '{"page":22}'})
        self.assertEqual(parsed["events"], events)


if __name__ == "__main__":
    unittest.main()

class WorkspaceSourceHTTPTest(RecordingUITest):
    def setUp(self):
        super().setUp()
        from workspace_sources import WorkspaceSources
        self.proxy.workspace = object()
        self.proxy.workspace_sources = WorkspaceSources(Path(self.temp.name)/'sources',None,'http://localhost:5210')

    def test_source_upload_download_and_origin_boundary(self):
        raw=b'[{"value":0},{"value":null}]'
        headers={'Content-Type':'application/octet-stream','X-Source-Filename':'fixture.json'}
        status,body=self.call('POST','/api/workspace/sources',raw,headers)
        self.assertEqual(status,200)
        sid=json.loads(body)['source_id']
        status,body=self.call('GET','/api/workspace/sources/'+sid+'/file')
        self.assertEqual((status,body),(200,raw))
        status,body=self.call('GET','/api/workspace/sources/'+sid)
        self.assertEqual(json.loads(body)['record_count'],2)
        self.assertEqual(self.call('POST','/api/workspace/sources',raw,{**headers,'Origin':'https://unrelated.example'})[0],403)
        self.assertEqual(self.call('POST','/api/workspace/sources',raw,{'Content-Type':'application/json'})[0],400)
