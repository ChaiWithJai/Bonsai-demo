"""Bounded streaming transport to an already running local recording proxy.

This module never starts inference or retries a generation. The caller owns the
conversation, cancellation, tool execution, and whole-attempt trace.
"""
import http.client
import json
import re
import socket
import threading
import time
from urllib.parse import urlsplit


class GenerationCancelled(RuntimeError):
    pass


class ProviderError(RuntimeError):
    pass


class LocalProvider:
    contract_version = 'bonsai-workspace-openai-tools-v1'

    def __init__(self, endpoint, model, timeout=120, max_bytes=2_000_000):
        url = urlsplit(endpoint)
        if (url.scheme != 'http' or url.hostname not in ('localhost', '127.0.0.1', '::1')
                or url.username or url.password or url.query or url.fragment
                or url.path not in ('', '/')):
            raise ValueError('Configure an existing localhost recording-proxy origin')
        if not isinstance(model, str) or not model:
            raise ValueError('An explicit model identity is required')
        if not 0 < timeout <= 600 or not 1024 <= max_bytes <= 8_000_000:
            raise ValueError('Provider limits exceed the bounded attempt contract')
        self.host, self.port = url.hostname, url.port or 80
        self.model, self.timeout, self.max_bytes = model, timeout, max_bytes

    def generate(self, messages, tools, session, cancel, emit, max_tokens):
        if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,200}', session):
            raise ValueError('Invalid workspace conversation ID')
        if not isinstance(max_tokens, int) or not 1 <= max_tokens <= 16384:
            raise ValueError('Provide an explicit bounded output-token budget')
        if cancel.is_set():
            raise GenerationCancelled('Attempt cancelled before generation')
        payload = {'model': self.model, 'messages': messages, 'tools': tools,
                   'stream': True, 'max_tokens': max_tokens, 'temperature': 0}
        body = json.dumps(payload, allow_nan=False).encode()
        if len(body) > self.max_bytes:
            raise ProviderError('Context exceeds the request byte limit')
        connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        transport = []
        finished = threading.Event()
        expired = threading.Event()
        deadline = time.monotonic() + self.timeout

        def watch():
            while not finished.wait(0.05):
                if time.monotonic() >= deadline:
                    expired.set()
                if cancel.is_set() or expired.is_set():
                    # shutdown wakes a blocked read, unlike merely closing the
                    # file wrapper retained by HTTPResponse.
                    sock = transport[0] if transport else connection.sock
                    if sock is not None:
                        try:
                            sock.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                    return

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        raw = bytearray()
        content, reasoning, calls = [], [], {}
        finish_reason, done, trace_id = None, False, None
        usage = None

        def check():
            if cancel.is_set():
                raise GenerationCancelled('Attempt cancelled during generation')
            if expired.is_set() or time.monotonic() >= deadline:
                raise ProviderError('Generation exceeded its wall-clock limit')

        try:
            connection.request('POST', '/v1/chat/completions', body, {
                'Content-Type': 'application/json', 'Accept': 'text/event-stream',
                'X-Bonsai-Conversation': session})
            transport.append(connection.sock)
            response = connection.getresponse()
            trace_id = response.getheader('X-Bonsai-Trace-ID')
            if response.status != 200:
                raise ProviderError(f'Local inference returned HTTP {response.status}')
            if 'text/event-stream' not in response.getheader('Content-Type', ''):
                raise ProviderError('Expected a streaming completion response')
            data_lines = []
            while True:
                check()
                line = response.readline(min(65537, self.max_bytes - len(raw) + 1))
                check()
                if not line:
                    break
                raw.extend(line)
                if len(raw) > self.max_bytes or len(line) > 65536:
                    raise ProviderError('Completion exceeds the response byte limit')
                line = line.decode('utf-8').rstrip('\r\n')
                if line.startswith('data:'):
                    data_lines.append(line[5:].lstrip(' '))
                    continue
                if line or not data_lines:
                    continue
                data = '\n'.join(data_lines)
                data_lines = []
                if data == '[DONE]':
                    done = True
                    break
                event = json.loads(data)
                if not isinstance(event, dict) or event.get('error'):
                    raise ProviderError('Invalid or failed completion event')
                if event.get('usage') is not None:
                    usage = event['usage']
                for choice in event.get('choices', []):
                    if choice.get('index', 0) != 0:
                        raise ProviderError('Only one completion choice is supported')
                    delta = choice.get('delta', {})
                    for field, target in (('content', content), ('reasoning_content', reasoning)):
                        text = delta.get(field)
                        if text:
                            if not isinstance(text, str):
                                raise ProviderError('Completion text must be a string')
                            target.append(text)
                            emit({'field': field, 'text': text})
                    for tool in delta.get('tool_calls', []):
                        index = tool.get('index')
                        if not isinstance(index, int) or not 0 <= index < 8:
                            raise ProviderError('Invalid tool-call index')
                        call = calls.setdefault(index, {'id': '', 'type': 'function',
                                                       'function': {'name': '', 'arguments': ''}})
                        if tool.get('type', 'function') != 'function':
                            raise ProviderError('Unsupported tool-call type')
                        if tool.get('id'):
                            if call['id'] and call['id'] != tool['id']:
                                raise ProviderError('Tool-call identity changed midstream')
                            call['id'] = tool['id']
                        for field in ('name', 'arguments'):
                            fragment = tool.get('function', {}).get(field, '')
                            if not isinstance(fragment, str):
                                raise ProviderError('Tool-call fragment must be text')
                            call['function'][field] += fragment
                    if choice.get('finish_reason'):
                        finish_reason = choice['finish_reason']
            check()
            if not done or finish_reason not in ('stop', 'tool_calls'):
                raise ProviderError('Completion ended without a complete stop or tool call')
            if bool(calls) != (finish_reason == 'tool_calls'):
                raise ProviderError('Tool calls and finish reason disagree')
            ids = set()
            allowed = {tool['function']['name'] for tool in tools}
            for call in calls.values():
                if not call['id'] or call['id'] in ids or call['function']['name'] not in allowed:
                    raise ProviderError('Tool call has an unknown name or invalid identity')
                ids.add(call['id'])
                if not isinstance(json.loads(call['function']['arguments']), dict):
                    raise ProviderError('Tool arguments must be a JSON object')
            message = {'role': 'assistant', 'content': ''.join(content)}
            if reasoning:
                message['reasoning_content'] = ''.join(reasoning)
            if calls:
                message['tool_calls'] = [calls[index] for index in sorted(calls)]
            return {'message': message, 'finish_reason': finish_reason, 'usage': usage,
                    'proxy_trace_id': trace_id, 'request': payload,
                    'raw_response': raw.decode('utf-8'), 'contract_version': self.contract_version}
        except (OSError, http.client.HTTPException, ValueError, TypeError, KeyError) as exc:
            check()
            raise ProviderError(f'Invalid or interrupted local completion: {type(exc).__name__}') from exc
        finally:
            finished.set()
            connection.close()
            watcher.join(timeout=1)
