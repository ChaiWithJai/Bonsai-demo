#!/usr/bin/env python3
"""Serve llama-ui, forwarding unchanged inference bodies and recording actual traffic.

No agent, model fallback, or prewritten answers live here. One MLflow trace per
HTTP exchange; conversation IDs group traces into sessions. Browser-local history
remains owned by llama-ui. Direct browser-to-MCP calls are outside this recorder.
"""
import argparse
import contextlib
import http.client
import json
import mimetypes
import os
from pathlib import Path
import re
import time
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
       "te", "trailer", "transfer-encoding", "upgrade", "host"}
SESSION = "X-Bonsai-Conversation"
UI_ORIGINS = {"http://127.0.0.1:8080", "http://localhost:8080", "http://127.0.0.1:8088", "http://localhost:8088"}
SCRIPT = r'''(() => {
  const original = window.fetch.bind(window);
  window.fetch = (input, init) => {
    const url = new URL(input instanceof Request ? input.url : input, location.href);
    if (url.origin !== location.origin ||
        !(/^\/v1\/(chat\/completions|stream)/.test(url.pathname) || url.pathname === '/cors-proxy'))
      return original(input, init);
    const conversation = location.hash.match(/^#\/chat\/([^/?#]+)/)?.[1];
    if (!conversation) return original(input, init);
    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    headers.set('X-Bonsai-Conversation', conversation);
    return original(input, {...init, headers});
  };
})();'''.encode()


def parse_payload(raw):
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return {"raw": raw.decode("utf-8", errors="replace")}


def parse_response(raw, content_type):
    if "text/event-stream" not in content_type:
        return parse_payload(raw)
    events = []
    for block in raw.decode("utf-8", errors="replace").replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(line[5:].lstrip() for line in block.splitlines() if line.startswith("data:"))
        if data and data != "[DONE]":
            events.append(parse_payload(data.encode()))
    choices = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        for choice in event.get("choices", []):
            entry = choices.setdefault(choice.get("index", 0), {"message": {"role": "assistant", "content": ""}, "tools": {}})
            delta = choice.get("delta", {})
            for field in ("content", "reasoning_content"):
                if delta.get(field):
                    entry["message"][field] = entry["message"].get(field, "") + delta[field]
            for tool in delta.get("tool_calls", []):
                accumulated = entry["tools"].setdefault(tool.get("index", 0), {"type": "function", "function": {"name": "", "arguments": ""}})
                if tool.get("id"):
                    accumulated["id"] = tool["id"]
                for field in ("name", "arguments"):
                    accumulated["function"][field] += tool.get("function", {}).get(field, "")
            if choice.get("finish_reason"):
                entry["finish_reason"] = choice["finish_reason"]
    assembled = []
    for index, entry in sorted(choices.items()):
        if entry["tools"]:
            entry["message"]["tool_calls"] = [v for _, v in sorted(entry["tools"].items())]
        assembled.append({"index": index, "message": entry["message"], "finish_reason": entry.get("finish_reason")})
    return {"choices": assembled, "events": events, "done_marker": b"[DONE]" in raw}


def clean_headers(headers):
    blocked = HOP | {p.strip().lower() for p in headers.get("Connection", "").split(",")}
    return {k: v for k, v in headers.items() if k.lower() not in blocked and k.lower() != SESSION.lower()}


class Recorder:
    def __init__(self, tracking_uri, directory):
        import mlflow
        self.mlflow = mlflow
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment("bonsai-native-ui")
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    @contextlib.contextmanager
    def exchange(self, kind, body, session, model_info):
        request_id = uuid.uuid4().hex
        directory = self.directory / request_id
        directory.mkdir(mode=0o700)
        (directory / "request.bin").write_bytes(body)
        (directory / "server-info.json").write_text(json.dumps(model_info, indent=2))
        state = {"request_id": request_id, "session": session, "kind": kind,
                 "started_at": time.time(), "complete": False,
                 "scope": "one HTTP exchange, not a whole agent run"}
        request = parse_payload(body)
        name = f"llama-ui.{kind}"
        if kind == "mcp" and isinstance(request, dict):
            name = "browseros." + str(request.get("params", {}).get("name", request.get("method", "mcp")))
        with self.mlflow.start_span(name=name, span_type="LLM" if kind == "completion" else "TOOL") as span:
            state["trace_id"] = span.trace_id
            metadata = {"bonsai.request_id": request_id, "bonsai.capture_scope": state["scope"],
                        "bonsai.session_attribution": "browser route at request time; keep the chat open while running"}
            if session:
                metadata["mlflow.trace.session"] = session
            self.mlflow.update_current_trace(metadata=metadata)
            span.set_inputs(request)
            span.set_attribute("bonsai.server", model_info)
            try:
                with (directory / "response.bin").open("wb") as output:
                    yield state, output
            except Exception as exc:
                state["error"] = type(exc).__name__
                span.set_status("ERROR")
                raise
            finally:
                state["elapsed_ms"] = (time.time() - state["started_at"]) * 1000
                if session and session.startswith('workspace-'):
                    state['activation_replay'] = 'not_scheduled_for_workspace_attempt'
                (directory / "exchange.json").write_text(json.dumps(state, indent=2))
                response = (directory / "response.bin").read_bytes()
                span.set_outputs(parse_response(response, state.get("content_type", "")))
                span.set_attribute("bonsai.capture", state)
                if state.get("status", 500) >= 400 or not state["complete"]:
                    span.set_status("ERROR")
                worker = getattr(self, "replay_worker", None)
                if worker and kind == "completion" and state.get("complete") and state.get("status", 500) < 400 and not (session and session.startswith('workspace-')):
                    worker.enqueue(directory)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def end_headers(self):
        origin = self.headers.get("Origin", "")
        if origin in UI_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Expose-Headers", "mcp-session-id, X-Bonsai-Trace-ID")
            self.send_header("Vary", "Origin")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization, MCP-Session-ID, MCP-Protocol-Version, Last-Event-ID, X-Bonsai-Conversation")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt, *args):
        # Never print URLs: MCP query strings can contain credentials.
        pass

    def respond(self, status, data, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def respond_file(self, raw, mime):
        total=len(raw);start=0;end=total-1;status=200
        requested=self.headers.get('Range')
        if requested:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
            try:
                if not match or not any(match.groups()):raise ValueError()
                first,last=match.groups()
                if first:
                    start=int(first);end=min(int(last),total-1) if last else total-1
                else:
                    length=int(last)
                    if length<=0:raise ValueError()
                    start=max(0,total-length)
                if not 0<=start<=end<total:raise ValueError()
                status=206
            except ValueError:
                self.send_response(416);self.send_header('Content-Range',f'bytes */{total}');self.send_header('Content-Length','0');self.end_headers();return
        self.send_response(status);self.send_header('Content-Type',mime)
        self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','no-store')
        if status==206:self.send_header('Content-Range',f'bytes {start}-{end}/{total}')
        self.send_header('Content-Length',str(end-start+1));self.end_headers()
        if self.command!='HEAD':self.wfile.write(raw[start:end+1])

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/bonsai-tools':
            return self.respond(405, b'Stateless MCP uses POST', 'text/plain')
        if path.startswith('/api/workspace'):
            return self.workspace_request()
        origin = self.headers.get("Origin")
        if origin and origin not in UI_ORIGINS:
            return self.respond(403, b"Origin is not an allowed local llama-ui", "text/plain")
        if path == "/api/comparison/status":
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                return self.respond(403, b"Local UI access required", "text/plain")
            return self.respond(200, json.dumps(self.server.comparison.status()).encode(), "application/json")
        if path.startswith("/api/browser-view/"):
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                return self.respond(403, b"Local UI access required", "text/plain")
            session = unquote(path[len("/api/browser-view/"):])
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session):
                return self.respond(404, b"Conversation not found", "text/plain")
            if not getattr(self.server, "browser_view", None):
                return self.respond(503, b"Browser view is not configured", "text/plain")
            data = self.server.browser_view.frame(session)
            return self.respond(200, json.dumps(data).encode(), "application/json")
        if path.startswith("/api/observability/"):
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                return self.respond(403, b"Local UI access required", "text/plain")
            try:
                suffix = path[len("/api/observability/"):]
                if suffix == "sessions":
                    data = self.server.observability.sessions()
                elif suffix == "activation-vector":
                    from urllib.parse import parse_qs
                    q = parse_qs(urlsplit(self.path).query)
                    data = self.server.observability.activation_vector(q['session'][0], q['node'][0], int(q['step'][0]), int(q['layer'][0]))
                elif suffix == "model":
                    data = self.server.observability.model()
                elif suffix.startswith("sessions/"):
                    data = self.server.observability.detail(unquote(suffix[len("sessions/"):]))
                else:
                    raise KeyError(suffix)
                return self.respond(200, json.dumps(data).encode(), "application/json")
            except (KeyError, ValueError, OSError):
                return self.respond(404, b"Observability resource not found", "text/plain")
        if path == "/props" and self.server.browseros:
            from urllib.request import urlopen
            try:
                with urlopen(self.server.upstream + "/props", timeout=5) as response:
                    props = json.load(response)
                settings = props.setdefault("ui_settings", {})
                servers = json.loads(settings.get("mcpServers", "[]"))
                servers = [item for item in servers if item.get("id") != "browseros-mac"]
                servers.append({"id": "browseros-mac", "name": "BrowserOS Neo · MacBook",
                    "url": self.server.browseros, "enabled": True, "useProxy": True,
                    "requestTimeoutSeconds": 300})
                settings["mcpServers"] = json.dumps(servers)
                props["cors_proxy_enabled"] = True
                return self.respond(200, json.dumps(props).encode(), "application/json")
            except Exception:
                return self.respond(502, b"Upstream props unavailable", "text/plain")
        if path == "/bonsai-observability.js":
            return self.respond(200, SCRIPT, "text/javascript")
        if path == "/bonsai-recording-status":
            return self.respond(200, json.dumps({"recording": True, "upstream": self.server.upstream,
                "browseros_configured": bool(self.server.browseros),
                "browseros_endpoint": self.server.browseros,
                "scope": "completion and proxied MCP HTTP exchanges"}).encode(), "application/json")
        asset = (self.server.static / unquote(path).lstrip("/")).resolve()
        if path == "/":
            asset = self.server.static / "index.html"
        if asset.is_relative_to(self.server.static) and asset.is_file():
            data = asset.read_bytes()
            if asset.name == "index.html":
                data = data.replace(b"<head>", b'<head><script src="/bonsai-observability.js"></script>', 1)
            return self.respond(200, data, mimetypes.guess_type(str(asset))[0] or "application/octet-stream")
        return self.forward()

    do_HEAD = do_GET

    def do_POST(self):
        if urlsplit(self.path).path == '/api/bonsai-tools':
            return self.chat_tools_request()
        if urlsplit(self.path).path.startswith('/api/workspace'):
            return self.workspace_request()
        if urlsplit(self.path).path == "/api/activation-replay":
            return self.activation_replay()
        if urlsplit(self.path).path == "/api/comparison/run":
            return self.comparison_run()
        return self.forward()

    do_DELETE = do_POST

    def chat_tools_request(self):
        origin = self.headers.get('Origin')
        if self.headers.get('Sec-Fetch-Site') == 'cross-site' or (origin and origin not in UI_ORIGINS):
            return self.respond(403, b'Local chat origin required', 'text/plain')
        if self.command != 'POST':
            return self.respond(405, b'Stateless MCP uses POST', 'text/plain')
        service = getattr(self.server, 'workspace_learning', None)
        if service is None:
            return self.respond(503, b'Chat tools are not configured', 'text/plain')
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 150000 or self.headers.get('Transfer-Encoding'):
                raise ValueError('Invalid request size')
            request = json.loads(self.rfile.read(length))
        except (ValueError, TypeError):
            return self.respond(400, b'Invalid MCP request', 'text/plain')
        from chat_tools_mcp import dispatch
        result = dispatch(service, request)
        if result is None:
            return self.respond(202, b'', 'application/json')
        return self.respond(200, json.dumps(result).encode(), 'application/json')

    def workspace_request(self):
        worker = getattr(self.server, 'workspace', None)
        if worker is None:
            return self.respond(503, b'{"error":"Workspace is not enabled on this recording service"}', 'application/json')
        origin = self.headers.get('Origin')
        if self.headers.get('Sec-Fetch-Site') == 'cross-site' or (origin and origin not in UI_ORIGINS):
            return self.respond(403, b'{"error":"Local UI origin required"}', 'application/json')
        from workspace_store import RevisionConflict
        try:
            parsed = urlsplit(self.path)
            parts = parsed.path.strip('/').split('/')
            sources = self.server.workspace_sources
            if parts == ['api', 'workspace', 'sources'] and self.command == 'POST':
                from workspace_data.intake import MAX_BYTES
                from urllib.parse import unquote
                size = int(self.headers.get('Content-Length', '0'))
                if (not 0 < size <= MAX_BYTES or self.headers.get('Transfer-Encoding')
                        or self.headers.get('Content-Type') != 'application/octet-stream'):
                    raise ValueError('Upload one source of at most 25 MiB')
                content = self.rfile.read(size)
                if len(content) != size:
                    raise ValueError('Incomplete source upload')
                result = sources.upload(unquote(self.headers.get('X-Source-Filename', '')), content)
                return self.respond(200, json.dumps(result).encode(), 'application/json')
            payload = {}
            if self.command == 'POST':
                size = int(self.headers.get('Content-Length', '0'))
                limit = 65536 if parts[:3] == ['api', 'workspace', 'sources'] else 16000
                if not 0 < size <= limit or self.headers.get('Transfer-Encoding'):
                    raise ValueError('Invalid request size')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('Expected a JSON object')
            if parts[:3] == ['api', 'workspace', 'learning']:
                learning = self.server.workspace_learning
                if len(parts) == 3 and self.command == 'GET':
                    result = learning.list()
                elif len(parts) == 3 and self.command == 'POST':
                    result = learning.create(payload.get('kind'))
                elif len(parts) == 4 and self.command == 'GET':
                    result = learning.get(parts[3])
                elif len(parts) == 5 and parts[4] == 'actions' and self.command == 'POST':
                    result = learning.act(parts[3], payload)
                else:
                    raise ValueError('Unknown learning route')
            elif parts[:3] == ['api', 'workspace', 'source-jobs']:
                jobs = self.server.workspace_source_jobs
                if len(parts) == 3 and self.command == 'GET':
                    result = jobs.list()
                elif len(parts) == 4 and parts[3] == 'intake' and self.command == 'POST':
                    from workspace_intake_chat import start
                    result = start(jobs,payload.get('role'),payload.get('message'),payload.get('parent_job_id'))
                elif len(parts) == 4 and self.command == 'GET':
                    result = jobs.get(parts[3])
                elif len(parts) == 5 and parts[4] == 'comparison' and self.command == 'GET':
                    from workspace_proposal_comparison import compare
                    result = compare(jobs,parts[3])
                elif len(parts) == 5 and parts[4] == 'proposal-preview' and self.command == 'GET':
                    from workspace_proposal_preview import preview
                    return self.respond(200,preview(jobs,parts[3]),'image/svg+xml')
                elif len(parts) == 5 and parts[4] == 'reviews' and self.command in ('GET', 'POST'):
                    result = jobs.proposal_reviews(parts[3], payload if self.command == 'POST' else None)
                elif len(parts) == 5 and parts[4] == 'review-export' and self.command == 'GET':
                    result = jobs.export_proposal_reviews(parts[3])
                elif len(parts) == 5 and parts[4] == 'review-export' and self.command == 'POST':
                    result = jobs.publish_proposal_reviews(parts[3])
                elif len(parts) == 5 and parts[4] == 'cancel' and self.command == 'POST':
                    result = jobs.cancel(parts[3])
                elif len(parts) == 5 and parts[4] == 'confirm' and self.command == 'POST':
                    result = jobs.confirm(parts[3],payload.get('proposal_sha256'),self.headers.get('X-Eval-Actor','interactive-unattributed'))
                elif len(parts) == 5 and parts[4] == 'revalidate' and self.command == 'POST':
                    result = jobs.revalidate(parts[3])
                elif len(parts) == 5 and parts[4] == 'retry-build' and self.command == 'POST':
                    result = jobs.retry_build(parts[3],payload.get('proposal_sha256'),self.headers.get('X-Eval-Actor','interactive-unattributed'))
                elif len(parts) == 5 and parts[4] == 'view-revision' and self.command == 'POST':
                    from workspace_view_revision import revise_view
                    result = revise_view(jobs,parts[3],payload,self.headers.get('X-Eval-Actor','interactive-unattributed'))
                elif len(parts) == 5 and parts[4] == 'revise' and self.command == 'POST':
                    result = jobs.revise(parts[3],payload.get('feedback'),self.headers.get('X-Eval-Actor','interactive-unattributed'),payload.get('review_unused_sources',False))
                else:
                    raise ValueError('Unknown source job route')
            elif parts[:3] == ['api', 'workspace', 'sources']:
                if len(parts) == 3 and self.command == 'GET':
                    result = sources.list()
                elif len(parts) == 4 and parts[3] == 'collection' and self.command == 'POST':
                    result = sources.collection(payload.get('source_ids'),payload.get('apply_reviews',False))
                elif len(parts) == 4 and self.command == 'GET':
                    query = parse_qs(parsed.query)
                    result = sources.get(parts[3], offset=int(query.get('offset',['0'])[0]), limit=int(query.get('limit',['100'])[0]), query=query.get('q',[''])[0])
                elif len(parts) == 5 and parts[4] == 'extract' and self.command == 'POST':
                    result = sources.extract_media(parts[3], refresh_pdf=payload.get('refresh_pdf') is True)
                elif len(parts) == 5 and parts[4] == 'vision' and self.command == 'POST':
                    result = self.server.workspace_source_jobs.start_vision(parts[3],payload.get('page'))
                elif len(parts) == 5 and parts[4] == 'generate' and self.command == 'POST':
                    result = self.server.workspace_source_jobs.start(parts[3], payload.get('request'), payload.get('apply_reviews', False), intake_job_id=payload.get('intake_job_id'),source_scope=payload.get('source_scope'), generation_config=payload.get('generation_config'),task_contract=payload.get('task_contract'))
                elif len(parts) == 6 and parts[4] == 'pages' and self.command == 'GET':
                    raw, mime = sources.pdf_page(parts[3], int(parts[5]))
                    return self.respond(200, raw, mime)
                elif len(parts) == 5 and parts[4] == 'file' and self.command == 'GET':
                    raw, mime = sources.download(parts[3])
                    return self.respond_file(raw, mime)
                elif len(parts) == 5 and parts[4] == 'review' and self.command == 'POST':
                    if payload.get('source_id') != parts[3]:
                        raise ValueError('Review must belong to this source')
                    result = sources.review(payload)
                elif len(parts) == 5 and parts[4] == 'export' and self.command == 'POST':
                    result = sources.export(parts[3])
                elif len(parts) == 6 and parts[4] == 'exports' and self.command == 'GET':
                    raw, mime = sources.download(parts[3], parts[5])
                    return self.respond(200, raw, mime)
                else:
                    raise ValueError('Unknown source route')
            elif self.command == 'GET' and parts == ['api', 'workspace', 'workstreams']:
                result = self.server.workspace_source_jobs.workstreams()
            elif self.command == 'GET' and parts == ['api', 'workspace']:
                result = worker.status()
            elif self.command == 'POST' and parts == ['api', 'workspace']:
                result = worker.create()
            elif len(parts) == 3 and re.fullmatch('[a-f0-9]{32}', parts[2]) and self.command == 'GET':
                result = worker.get(parts[2])
            elif len(parts) == 4 and re.fullmatch('[a-f0-9]{32}', parts[2]):
                if parts[3] == 'trial-copy' and self.command == 'POST':
                    result = worker.copy_for_trial(parts[2], payload.get('base_revision'), payload.get('title'))
                elif parts[3] == 'attempts' and self.command == 'POST':
                    result = worker.start(parts[2], payload['base_revision'], payload['request'], payload.get('case', 'baseline'), payload.get('request_checks'), payload.get('generation_config'))
                elif parts[3] == 'reviews' and self.command == 'GET':
                    result = worker.store.interface_reviews(parts[2])
                elif parts[3] == 'reviews' and self.command == 'POST':
                    result = worker.store.review_interface(parts[2], payload)
                elif parts[3] == 'review-export' and self.command == 'POST':
                    result = worker.export_interface_reviews(parts[2])
                elif parts[3] == 'review-export' and self.command == 'GET':
                    result = worker.store.export_interface_reviews(parts[2])
                elif parts[3] == 'comparison' and self.command == 'GET':
                    result = worker.comparison(parts[2], parse_qs(parsed.query).get('attempt', []))
                elif parts[3] == 'preview' and self.command == 'DELETE':
                    result = worker.close_preview(parts[2])
                elif parts[3] == 'preview' and self.command == 'POST':
                    result = worker.restore_preview(parts[2])
                elif parts[3] == 'events' and self.command == 'GET':
                    after = int(parse_qs(parsed.query).get('after', ['0'])[0])
                    result = {'events': worker.store.events(parts[2], after)}
                elif parts[3] == 'cancel' and self.command == 'POST':
                    worker.cancel(parts[2])
                    result = {'cancelled': True}
                else:
                    raise ValueError('Unknown Workspace route')
            else:
                raise ValueError('Unknown Workspace route')
            return self.respond(200, json.dumps(result).encode(), 'application/json')
        except RevisionConflict as exc:
            return self.respond(409, json.dumps({'error': str(exc)}).encode(), 'application/json')
        except (ValueError, KeyError, TypeError) as exc:
            return self.respond(400, json.dumps({'error': str(exc)}).encode(), 'application/json')

    def activation_replay(self):
        if self.command != "POST" or self.headers.get("Sec-Fetch-Site") == "cross-site" or (self.headers.get("Origin") and self.headers.get("Origin") not in UI_ORIGINS):
            return self.respond(403, b"Local POST required", "text/plain")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length < 4096: raise ValueError("Invalid body size")
            payload = json.loads(self.rfile.read(length))
            detail = self.server.observability.detail(payload['session_id'])
            node = next(n for n in detail['nodes'] if n['id'] == payload['node_id'] and n.get('kind') == 'completion' and n.get('category') != 'instrumented_replay')
            worker = self.server.recorder.replay_worker
            match = re.fullmatch(r"comparison_([a-f0-9]{32})_(bonsai|qwen)_turn_(\d+)", node['id'])
            if match:
                run, model, turn = match.groups()
                directory = self.server.recorder.directory.parent / 'comparison-records' / run / model / ('turn-' + turn)
                worker.enqueue_comparison(directory, model, {'comparison_run_id': run, 'model': model, 'turn': int(turn), 'request_sha256': __import__('hashlib').sha256((directory/'request.json').read_bytes()).hexdigest()})
            else:
                request_id = node['request_id']
                if not re.fullmatch(r'[a-f0-9]{32}', request_id): raise ValueError('Invalid inference ID')
                directory = self.server.recorder.directory / request_id
                if not (directory/'server-info.json').exists():
                    exchange = json.loads((directory/'exchange.json').read_text())
                    trace = self.server.recorder.mlflow.get_trace(exchange['trace_id'])
                    info = next(span.attributes['bonsai.server'] for span in trace.data.spans if span.attributes.get('bonsai.server'))
                    (directory/'server-info.json').write_text(json.dumps(info))
                worker.enqueue(directory)
            return self.respond(202, (directory/'activation-replay-status.json').read_bytes(), 'application/json')
        except (KeyError, ValueError, StopIteration, OSError) as exc:
            return self.respond(400, json.dumps({'error': str(exc)}).encode(), 'application/json')

    def comparison_run(self):
        if self.command != "POST":
            return self.respond(405, b"POST required", "text/plain")
        origin = self.headers.get("Origin")
        if (origin and origin not in UI_ORIGINS) or self.headers.get("Sec-Fetch-Site") == "cross-site":
            return self.respond(403, b"Local UI access required", "text/plain")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if self.headers.get("Transfer-Encoding") or not 0 < length <= 65536:
                raise ValueError("A bounded JSON request is required")
            body = self.server.comparison.validate(json.loads(self.rfile.read(length)))
        except (ValueError, TypeError) as exc:
            return self.respond(400, str(exc).encode(), "text/plain")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        cancel = threading.Event()
        lock = threading.Lock()
        def emit(name, data):
            with lock:
                try:
                    self.wfile.write(("event: " + name + "\ndata: " + json.dumps(data) + "\n\n").encode())
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    cancel.set()
                    raise
        try:
            self.server.comparison.run(body, emit, cancel_event=cancel)
        except (BrokenPipeError, ConnectionResetError):
            cancel.set()
        except Exception as exc:
            try:
                emit("error", {"message": str(exc)})
            except (BrokenPipeError, ConnectionResetError):
                pass

    def forward(self):
        path = urlsplit(self.path).path
        origin = self.headers.get("Origin")
        if origin and origin not in UI_ORIGINS:
            return self.respond(403, b"Origin is not an allowed local llama-ui", "text/plain")
        if self.headers.get("Transfer-Encoding"):
            return self.respond(400, b"Content-Length required", "text/plain")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.respond(400, b"Invalid Content-Length", "text/plain")
        if length < 0 or length > 64 * 1024 * 1024:
            return self.respond(413, b"Request too large", "text/plain")
        body = self.rfile.read(length)
        if len(body) != length:
            return self.respond(400, b"Incomplete request", "text/plain")
        headers = clean_headers(self.headers)
        target = urlsplit(self.server.upstream + self.path)
        kind = "completion" if path == "/v1/chat/completions" and self.command == "POST" else None
        if path == "/browseros/mcp":
            origin = self.headers.get("Origin")
            if (origin and origin not in UI_ORIGINS) or (not origin and self.headers.get("Sec-Fetch-Site") == "cross-site"):
                return self.respond(403, b"Origin is not an allowed local llama-ui", "text/plain")
            if not self.server.browseros:
                return self.respond(503, b"BrowserOS is not configured", "text/plain")
            target = urlsplit(self.server.browseros)
            # Validate the caller locally, then make a server-to-server request.
            # BrowserOS rejects cross-site browser fetch metadata even via SSH.
            headers = {k: v for k, v in headers.items() if k.lower() not in {"origin", "referer", "cookie"} and not k.lower().startswith("sec-fetch-")}
            kind = "mcp" if self.command == "POST" else None
        if path == "/cors-proxy":
            endpoint = parse_qs(urlsplit(self.path).query).get("url", [""])[0]
            # Only the configured BrowserOS endpoint is relayed by this process.
            # Other MCPs continue to use the upstream's own proxy policy.
            if self.server.browseros and endpoint == self.server.browseros:
                target = urlsplit(endpoint)
                prefix = "x-llama-server-proxy-header-"
                headers = {k[len(prefix):]: v for k, v in self.headers.items() if k.lower().startswith(prefix)}
                headers = clean_headers(headers)
                headers["Content-Length"] = str(len(body))
                kind = "mcp" if self.command == "POST" else None
        headers = {key: value for key, value in headers.items() if key.lower() != "accept-encoding"}
        headers["Accept-Encoding"] = "identity"
        headers["Connection"] = "close"
        session = self.headers.get(SESSION)
        if session and not re.fullmatch(r"[A-Za-z0-9_.:%-]{1,200}", session):
            session = None
        browser_view = getattr(self.server, "browser_view", None) if kind == "mcp" else None
        if browser_view and session:
            browser_view.observe_request(session, parse_payload(body), headers)
        capture = self.server.recorder.exchange(kind, body, session, self.server.model_info) if kind else contextlib.nullcontext(({}, None))
        conn_class = http.client.HTTPSConnection if target.scheme == "https" else http.client.HTTPConnection
        connection = conn_class(target.hostname, target.port, timeout=300)
        sent = False
        try:
            with capture as (state, output):
                connection.request(self.command, target.path + ("?" + target.query if target.query else ""), body=body, headers=headers)
                response = connection.getresponse()
                state.update(status=response.status, content_type=response.getheader("Content-Type", ""))
                self.send_response(response.status)
                for key, value in response.getheaders():
                    if key.lower() not in HOP | {"content-length", "access-control-allow-origin", "access-control-expose-headers"}:
                        self.send_header(key, value)
                self.send_header("Connection", "close")
                if state.get("trace_id"):
                    self.send_header("X-Bonsai-Trace-ID", state["trace_id"])
                self.end_headers()
                sent = True
                self.close_connection = True
                while chunk := response.read1(65536):
                    if output:
                        output.write(chunk)
                        output.flush()
                    self.wfile.write(chunk)
                    self.wfile.flush()
                # Content-Length truncation can otherwise look like successful EOF.
                if response.length not in (None, 0):
                    raise http.client.IncompleteRead(b"")
                state["complete"] = True
                if browser_view and session and output and response.status < 400:
                    output.flush()
                    raw = (self.server.recorder.directory / state["request_id"] / "response.bin").read_bytes()
                    browser_view.observe_response(session, parse_response(raw, state.get("content_type", "")))
        except Exception as exc:
            print(f"Request failed: {type(exc).__name__}", flush=True)
            if not sent:
                self.respond(502, b"Upstream or recording unavailable; request was not completed", "text/plain")
        finally:
            connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--upstream", default="http://127.0.0.1:8080")
    parser.add_argument("--static-dir", type=Path, required=True)
    parser.add_argument("--tracking-uri", required=True)
    parser.add_argument("--records-dir", type=Path, required=True)
    parser.add_argument("--browseros-url", help="Verified Streamable HTTP endpoint reachable from this server")
    parser.add_argument("--release-manifest", type=Path, help="Verified checkpoint evidence JSON")
    parser.add_argument("--comparison-records-dir", type=Path, help="Directory for head-to-head comparison artifacts")
    parser.add_argument('--workspace-dir', type=Path, help='Enable Workspace with a persistent store and attempt artifacts')
    parser.add_argument('--workspace-profile', choices=['legacy-greedy', 'bonsai2-instruct', 'bonsai2-medium'], default='legacy-greedy', help='Explicit sampling profile for Workspace experiments')
    parser.add_argument('--workspace-seed', type=int, default=42, help='Recorded sampling seed for Workspace attempts')
    parser.add_argument('--workspace-max-tokens', type=int, default=4096, help='Output token limit for each Workspace model call')
    parser.add_argument("--bonsai-endpoint", default=os.environ.get("BONSAI_COMPARISON_ENDPOINT", "http://127.0.0.1:8081"))
    parser.add_argument("--qwen-endpoint", default=os.environ.get("QWEN_COMPARISON_ENDPOINT", "http://127.0.0.1:8082"))
    parser.add_argument("--mlflow-base-url", default=os.environ.get("BONSAI_MLFLOW_BASE_URL", "http://127.0.0.1:5210"))
    parser.add_argument("--replay-diagnostic-dir", type=Path, help="Directory for replay lock/build artifacts")
    parser.add_argument("--replay-capture-binary", type=Path, help="Instrumented capture executable")
    parser.add_argument("--replay-runtime-lib-dir", type=Path, help="Directory containing matching llama.cpp shared libraries")
    parser.add_argument("--replay-activity-port", type=int, action="append", default=[], help="Local llama-server port to check for active inference before replay")
    args = parser.parse_args()
    UI_ORIGINS.update({f"http://127.0.0.1:{args.port}", f"http://localhost:{args.port}"})
    os.umask(0o077)
    static = args.static_dir.resolve()
    if not (static / "index.html").is_file():
        parser.error("static-dir must contain a built llama-ui index.html")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.static, server.upstream, server.browseros = static, args.upstream.rstrip("/"), args.browseros_url
    server.recorder = Recorder(args.tracking_uri, args.records_dir)
    from browser_live_view import BrowserLiveView
    server.browser_view = BrowserLiveView(args.browseros_url) if args.browseros_url else None
    from urllib.request import urlopen
    with urlopen(server.upstream + "/props", timeout=5) as response:
        props = json.load(response)
    server.model_info = {k: props.get(k) for k in ("model_path", "model_alias", "build_info", "default_generation_settings")}
    if args.release_manifest and server.model_info.get("model_path"):
        release = json.loads(args.release_manifest.read_text())
        loaded = Path(server.model_info["model_path"]).resolve()
        matching = [item for item in release.get("checkpoint", {}).get("files", [])
                    if item.get("verified") and item.get("path") and Path(item["path"]).resolve() == loaded]
        if matching:
            # Snapshot provenance with each new trace, rather than attributing
            # a future mutable deployment manifest to historical requests.
            server.model_info["checkpoint_release"] = {
                "repo": release["checkpoint"].get("repo"),
                "revision": release["checkpoint"].get("revision"),
                "verified_file": matching[0],
                "runtime": release.get("runtime"),
                "matched_loaded_model_path": True,
            }
    from activation_replay_worker import ReplayWorker
    server.recorder.replay_worker = ReplayWorker(args.records_dir, server.upstream, args.tracking_uri,
        release_manifest=args.release_manifest, diagnostic_dir=args.replay_diagnostic_dir,
        capture_binary=args.replay_capture_binary, runtime_lib_dir=args.replay_runtime_lib_dir,
        activity_ports=args.replay_activity_port, mlflow_base_url=args.mlflow_base_url)
    from observability_api import Observability
    comparison_records = args.comparison_records_dir or args.records_dir.parent / "comparison-records"
    server.observability = Observability(server.recorder, server.model_info, args.release_manifest,
        comparison_directory=comparison_records, mlflow_base_url=args.mlflow_base_url)
    from comparison_api import ComparisonAPI
    server.comparison = ComparisonAPI(args.tracking_uri, comparison_records,
        endpoints={"bonsai": args.bonsai_endpoint, "qwen": args.qwen_endpoint},
        browseros_url=args.browseros_url, browser_view=server.browser_view, replay_worker=server.recorder.replay_worker)
    if args.workspace_dir:
        from mlflow import MlflowClient
        from workspace_provider import LocalProvider
        from workspace_store import WorkspaceStore
        from workspace_tools import WorkspaceTools
        from workspace_worker import WorkspaceWorker
        from workspace_sources import WorkspaceSources
        if not server.model_info.get('checkpoint_release'):
            parser.error('Workspace requires a verified release manifest matching the loaded model')
        with urlopen(server.upstream + '/v1/models', timeout=5) as response:
            model = json.load(response)['data'][0]['id']
        store = WorkspaceStore(args.workspace_dir)
        server.workspace_sources = WorkspaceSources(args.workspace_dir / 'sources', MlflowClient(tracking_uri=args.tracking_uri), args.tracking_uri)
        origin = f'http://127.0.0.1:{args.port}'
        server.workspace = WorkspaceWorker(store, LocalProvider(origin, model, profile=args.workspace_profile, seed=args.workspace_seed), WorkspaceTools(store, origin),
            MlflowClient(tracking_uri=args.tracking_uri), args.tracking_uri, server.model_info, args.workspace_max_tokens)
        from workspace_source_jobs import SourceJobs
        server.workspace_source_jobs = SourceJobs(server.workspace, server.workspace_sources)
        from workspace_learning import LearningWorkstreams
        server.workspace_learning = LearningWorkstreams(server.workspace, server.workspace_sources)
    print(f"Recording llama-ui: http://127.0.0.1:{args.port}; model upstream unchanged: {server.upstream}", flush=True)
    try:
        server.serve_forever()
    finally:
        if getattr(server, 'workspace', None):
            server.workspace_source_jobs.close()
            server.workspace.close()
        server.recorder.mlflow.flush_trace_async_logging()
        server.server_close()


if __name__ == "__main__":
    main()
