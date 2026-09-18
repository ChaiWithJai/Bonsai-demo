"""Transient, page-scoped BrowserOS screenshots for the native UI.

This is polling, not video or a desktop stream. Successful page-scoped calls or
an exact acknowledgement of a newly created tab can select a page. Tab lists and
arbitrary run output never select one. Images stay in memory and are not
inference context or MLflow data.
"""
import base64
import json
import re
import threading
import time
import uuid
from urllib.request import Request, urlopen


PAGE_TOOLS = {'read', 'grep', 'snapshot', 'diff', 'navigate', 'act', 'screenshot',
              'evaluate', 'wait', 'download', 'upload', 'pdf'}
SESSION_META = 'com.browseros.neo/session'


def rpc_messages(payload):
    """Accept a decoded JSON-RPC envelope or recording_ui's parsed SSE wrapper."""
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get('events'), list):
        return [event for event in payload['events'] if isinstance(event, dict)]
    return [payload]


class BrowserLiveView:
    def __init__(self, endpoint, *, transport=None, clock=time.time,
                 poll_seconds=2, idle_seconds=300):
        self.endpoint = endpoint
        self.transport = transport or self._rpc
        self.clock = clock
        self.poll_seconds = poll_seconds
        self.idle_seconds = idle_seconds
        self.sessions = {}
        self.lock = threading.RLock()

    def _state(self, session):
        if not isinstance(session, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', session) or session == 'unassigned':
            return None
        return self.sessions.setdefault(session, {'pending': {}, 'page': None,
            'last_tool': None, 'touched': 0, 'frame': None, 'last_poll': None,
            'transport_session': None, 'neo_session': None, 'capture_lock': threading.Lock()})

    def observe_request(self, session, request, headers=None):
        if not isinstance(request, dict) or request.get('method') != 'tools/call':
            return
        params = request.get('params') or {}
        if not isinstance(params, dict):
            return
        args = params.get('arguments') or {}
        if not isinstance(args, dict):
            return
        name = params.get('name')
        page = args.get('page')
        creates_page = name == 'tabs' and args.get('action') == 'new'
        closes_page = name == 'tabs' and args.get('action') == 'close'
        if name not in PAGE_TOOLS and not (creates_page or closes_page):
            return
        if not creates_page and (isinstance(page, bool) or not isinstance(page, int) or not 0 <= page <= 2**32-1):
            return
        request_id = request.get('id')
        if not isinstance(request_id, (int, str)) or isinstance(request_id, bool):
            return
        with self.lock:
            state = self._state(session)
            if state is None:
                return
            lowered = {str(k).lower(): v for k, v in (headers or {}).items()}
            # Store only scoped handles, never authorization/cookies or all headers.
            transport_session = lowered.get('mcp-session-id')
            state['pending'][request_id] = {'page': page, 'tool': name,
                'transport_session': transport_session,
                'neo_session': args.get('session'), 'close': closes_page,
                'create': creates_page}
            while len(state['pending']) > 64:
                state['pending'].pop(next(iter(state['pending'])))

    def observe_response(self, session, response):
        with self.lock:
            state = self.sessions.get(session)
            if not state:
                return
            for message in rpc_messages(response):
                request_id = message.get('id')
                if not isinstance(request_id, (int, str)):
                    continue
                pending = state['pending'].pop(request_id, None)
                result = message.get('result')
                if not pending or not isinstance(result, dict) or message.get('error') or result.get('isError'):
                    continue
                if pending['create']:
                    # Only the first tool-generated status block is authoritative.
                    # Never search the appended, untrusted page snapshot for IDs.
                    content = result.get('content')
                    first = content[0] if isinstance(content, list) and content else None
                    status = first.get('text') if isinstance(first, dict) and first.get('type') == 'text' else None
                    match = re.fullmatch(r'opened page ([0-9]{1,10})', status.strip()) if isinstance(status, str) else None
                    if not match or int(match.group(1)) > 2**32-1:
                        continue
                    pending['page'] = int(match.group(1))
                if pending['close']:
                    if state['page'] == pending['page']:
                        state.update(page=None, frame=None)
                    continue
                meta = result.get('_meta') or {}
                neo_session = meta.get(SESSION_META) if isinstance(meta, dict) else None
                if state['page'] != pending['page']:
                    state['frame'] = None
                    state['last_poll'] = None
                state.update(page=pending['page'], last_tool=pending['tool'],
                    transport_session=pending['transport_session'],
                    neo_session=neo_session or pending['neo_session'], touched=self.clock())

    def _status(self, state):
        result = {'status': 'waiting', 'transport': 'polled_screenshot',
            'message': 'Waiting for a successful agent tool call on a specific browser page.',
            'page_id': None, 'title': '', 'url': '', 'captured_at': None,
            'image_data_url': None, 'last_tool': None}
        if not state or state['page'] is None:
            return result
        result.update(page_id=state['page'], last_tool=state['last_tool'])
        if self.clock() - state['touched'] > self.idle_seconds:
            result.update(status='idle', message='Browser activity is idle. A new agent page action will resume previews.')
        elif not state['transport_session'] and not state['neo_session']:
            result.update(status='unavailable', message='The observed browser call did not provide a reusable session handle.')
        else:
            result.update(status='ready', message='Live page snapshots; not a continuous video stream.')
        return result

    def status(self, session):
        with self.lock:
            return self._status(self.sessions.get(session))

    def frame(self, session):
        with self.lock:
            state = self.sessions.get(session)
            status = self._status(state)
        if status['status'] != 'ready':
            return status
        # One pending capture per conversation, with bounded polling and no disk writes.
        with state['capture_lock']:
            with self.lock:
                status = self._status(state)
                if status['status'] != 'ready':
                    return status
                now = self.clock()
                if state['last_poll'] is not None and now - state['last_poll'] < self.poll_seconds:
                    return dict(state['frame'] or status)
                state['last_poll'] = now
                page = state['page']
                transport_session = state['transport_session']
                args = {'page': page, 'format': 'jpeg', 'quality': 65,
                        'fullPage': False, 'annotate': False,
                        'size': {'width': 1024, 'height': 768}}
                if state['neo_session']:
                    args['session'] = state['neo_session']
            try:
                response = self.transport({'jsonrpc': '2.0', 'id': 'preview-' + uuid.uuid4().hex,
                    'method': 'tools/call', 'params': {'name': 'screenshot', 'arguments': args}}, transport_session)
                envelopes = rpc_messages(response)
                result = next((m.get('result') for m in envelopes if isinstance(m.get('result'), dict)), {})
                if result.get('isError') or not result:
                    raise ValueError('Screenshot unavailable')
                image = next((p for p in result.get('content', []) if isinstance(p, dict) and p.get('type') == 'image'), None)
                if not image or image.get('mimeType') not in ('image/jpeg', 'image/png', 'image/webp'):
                    raise ValueError('No supported screenshot returned')
                data = image.get('data', '')
                if not isinstance(data, str) or len(data) > 6 * 1024 * 1024:
                    raise ValueError('Screenshot exceeds preview size')
                base64.b64decode(data, validate=True)
                status.update(status='live', captured_at=self.clock(),
                    image_data_url='data:' + image['mimeType'] + ';base64,' + data)
            except Exception:
                # Do not expose server errors containing page content or session secrets.
                status.update(status='unavailable', message='BrowserOS could not capture this agent page. The tunnel or page may be unavailable.')
            with self.lock:
                if state['page'] != page:
                    return self._status(state)
                state['frame'] = status
                return dict(status)

    def _rpc(self, payload, transport_session):
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream',
                   'MCP-Protocol-Version': '2025-06-18'}
        if transport_session:
            headers['MCP-Session-Id'] = transport_session
        request = Request(self.endpoint, data=json.dumps(payload).encode(), headers=headers)
        with urlopen(request, timeout=8) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError('Response too large')
            if 'text/event-stream' not in response.headers.get('Content-Type', ''):
                return json.loads(raw)
        events = []
        for block in raw.decode().replace('\r\n', '\n').split('\n\n'):
            data = '\n'.join(line[5:].strip() for line in block.splitlines() if line.startswith('data:'))
            if data and data != '[DONE]':
                events.append(json.loads(data))
        return {'events': events}
