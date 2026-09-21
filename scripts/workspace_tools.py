"""Fixed compiler, preview service, and browser checks for workspace revisions."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import math
from pathlib import Path
import signal
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'examples/workspace/reviewed-cache-explorer'


def starter():
    provenance = json.loads((FIXTURE / 'provenance.json').read_text())
    task = json.loads((FIXTURE / 'task.json').read_text())
    return {'title': 'Bonsai source explorer', 'files': {'App.svelte': (FIXTURE / 'App.svelte').read_text()},
            'fixture': {'provenance': provenance, 'task': task}}


def evidence_links(compiled, parent_origin):
    links = {}
    for row in compiled['rows']:
        for passage in row.get('locator', {}).get('source_evidence', []):
            rid = passage.get('record_id', '')
            sid = rid.split(':', 1)[0]
            if not re.fullmatch(r'[a-f0-9]{64}', sid):
                continue
            locator = passage.get('locator', {})
            fragment, label = '', 'Open original source'
            page = locator.get('page')
            seconds = locator.get('start_seconds', locator.get('time_seconds'))
            if type(page) is int and page > 0:
                fragment, label = '#page=' + str(page), 'Open original page ' + str(page)
            elif type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0:
                fragment, label = '#t=' + str(seconds), f'Open original at {seconds:g}s'
            links[rid] = {'url': parent_origin.rstrip('/') + '/api/workspace/sources/' + sid + '/file' + fragment,
                          'label': label}
    return links


class WorkspaceTools:
    def __init__(self, store, parent_origin, node='node'):
        self.store, self.parent_origin, self.node = store, parent_origin, node
        self.servers = {}
        self.lock = threading.Lock()
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS notes (workspace_id TEXT NOT NULL, id TEXT PRIMARY KEY, payload TEXT NOT NULL)')

    def close(self):
        for server in self.servers.values():
            server.shutdown()
            server.server_close()

    def command(self, argv, directory, cancel, timeout=120):
        directory.mkdir(parents=True, exist_ok=True)
        # Commands and entrypoints are authored. Never load model build configs.
        with (directory / 'stdout.txt').open('w') as stdout, (directory / 'stderr.txt').open('w') as stderr:
            process = subprocess.Popen(argv, cwd=ROOT / 'scripts/workspace-tools', stdout=stdout, stderr=stderr, start_new_session=True)
            deadline = time.monotonic() + timeout
            try:
                while process.poll() is None:
                    if cancel.wait(0.05) or time.monotonic() >= deadline:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait()
                        raise RuntimeError('Tool cancelled or exceeded its wall-clock limit')
                return {'ok': process.returncode == 0, 'exit_code': process.returncode,
                        'stdout': (directory / 'stdout.txt').read_text()[-12000:],
                        'stderr': (directory / 'stderr.txt').read_text()[-12000:]}
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()

    def build(self, workspace, directory, cancel):
        source = directory / 'App.svelte'
        directory.mkdir(parents=True, exist_ok=True)
        source.write_text(workspace['files']['App.svelte'])
        result = self.command([self.node, str(ROOT / 'scripts/workspace-tools/render.mjs'), str(source), str(directory / 'assets')], directory, cancel)
        result.update(revision=workspace['head'], assets=str(directory / 'assets'))
        return result

    def preview(self, workspace, build):
        if not build or not build['ok'] or build['revision'] != workspace['head']:
            raise ValueError('Build the current revision before previewing it')
        key = workspace['id']
        with self.lock:
            if key not in self.servers:
                server = ThreadingHTTPServer(('127.0.0.1', 0), self.handler(key))
                server.assets = Path(build['assets'])
                server.revision = build['revision']
                self.servers[key] = server
                threading.Thread(target=server.serve_forever, daemon=True).start()
            server = self.servers[key]
            server.assets, server.revision = Path(build['assets']), build['revision']
            return {'url': f'http://127.0.0.1:{server.server_port}/', 'revision': build['revision']}

    def check_browser(self, workspace, preview, directory, cancel, case='baseline'):
        if case not in ('baseline', 'W1', 'W2'):
            raise ValueError('Unknown authored browser check')
        if preview['revision'] != workspace['head']:
            raise ValueError('Preview does not match the current revision')
        directory.mkdir(parents=True, exist_ok=True)
        task = directory / 'task.json'
        desktop = workspace['fixture'].get('kind') == 'desktop'
        task.write_text(json.dumps(workspace['fixture']['compiled'] if desktop else workspace['fixture']['task']))
        checker = 'check_desktop.mjs' if desktop else 'check.mjs'
        result = self.command([self.node, str(ROOT / 'scripts/workspace-tools' / checker), preview['url'], str(task), str(directory), case], directory, cancel)
        report = directory / 'report.json'
        result.update(revision=workspace['head'], case=case,
                      report=json.loads(report.read_text()) if report.exists() else None)
        result['ok'] = result['ok'] and bool(result['report']) and result['report'].get('passed') is True
        return result

    def handler(self, key):
        owner = self
        fixture = self.store.get(key)['fixture']
        desktop = fixture.get('kind') == 'desktop'
        task = fixture.get('task')
        source_rows = fixture['compiled']['rows'] if desktop else task['inputs']['contract']['rows']

        class PreviewHandler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def send(self, value, status=200, content_type='application/json'):
                body = value if isinstance(value, bytes) else json.dumps(value).encode()
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Referrer-Policy', 'no-referrer')
                self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors " + owner.parent_origin)
                self.end_headers()
                self.wfile.write(body)

            def allowed(self):
                origin = f'http://127.0.0.1:{self.server.server_port}'
                return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}' and self.headers.get('Origin') in (None, origin)

            def do_GET(self):
                if not self.allowed():
                    return self.send({'error': 'Preview origin required'}, 403)
                parsed = urlsplit(self.path)
                params = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
                if parsed.path in ('/', '/app.js'):
                    filename = 'index.html' if parsed.path == '/' else 'app.js'
                    return self.send((self.server.assets / filename).read_bytes(), content_type='text/html' if filename == 'index.html' else 'text/javascript')
                if desktop and parsed.path == '/api/desktop':
                    return self.send(fixture['compiled'] | {'interaction':fixture['render_evidence'].get('interaction', {}), 'evidence_links':evidence_links(fixture['compiled'], owner.parent_origin)})
                if desktop and parsed.path == '/api/chart.svg':
                    return self.send(fixture['chart_svg'].encode(), content_type='image/svg+xml')
                if parsed.path == '/api/task' and not desktop:
                    return self.send(task['inputs'])
                if parsed.path == '/api/annotations':
                    with owner.store.connect() as db:
                        return self.send([json.loads(r['payload']) for r in db.execute('SELECT payload FROM notes WHERE workspace_id=? ORDER BY rowid', (key,))])
                if parsed.path == '/api/records':
                    rows = source_rows
                    for parameter, field in [('cluster', 'cluster_id'), ('size', 'parameter_size'), ('runtime', 'runtime')]:
                        if params.get(parameter):
                            rows = [r for r in rows if r.get(field) == params[parameter]]
                    return self.send({'rows': rows, 'total_rows': len(rows), 'returned_rows': len(rows)})
                return self.send({'error': 'Not found'}, 404)

            def do_POST(self):
                if not self.allowed() or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                    return self.send({'error': 'Preview origin required'}, 403)
                if self.path != '/api/annotations':
                    return self.send({'error': 'Not found'}, 404)
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 20000 or self.headers.get('Transfer-Encoding'):
                        raise ValueError('Invalid note payload size')
                    note = json.loads(self.rfile.read(size))
                    record = next((r for r in source_rows if r['id'] == note.get('record_id')), None)
                    if record is None or not isinstance(note.get('note'), str) or not 0 < len(note['note'].strip()) <= 4000:
                        raise ValueError('Invalid note or source record')
                    if desktop:
                        saved = {'id':uuid.uuid4().hex, 'record_id':record['id'], 'note':note['note'].strip(),
                                 'record_snapshot':record, 'created_at':datetime.now(timezone.utc).isoformat(),
                                 'review_origin':self.headers.get('X-Eval-Actor', 'interactive-unattributed')}
                        with owner.store.connect() as db:
                            db.execute('INSERT INTO notes VALUES (?,?,?)',(key,saved['id'],json.dumps(saved)))
                        return self.send(saved,201)
                    for field in ('start', 'end'):
                        datetime.strptime(note[field], '%Y-%m-%d')
                    if note['start'] > note['end']:
                        raise ValueError('Reversed interval')
                    saved = {field: note[field] for field in ('record_id', 'note', 'start', 'end')}
                    saved.update(id=uuid.uuid4().hex, record_snapshot=record,
                                 interval_record_ids=[r['id'] for r in source_rows if note['start'] <= r['date'] <= note['end']],
                                 created_at=datetime.now(timezone.utc).isoformat(),
                                 review_origin=self.headers.get('X-Eval-Actor', 'interactive-unattributed'))
                    with owner.store.connect() as db:
                        db.execute('INSERT INTO notes VALUES (?,?,?)', (key, saved['id'], json.dumps(saved)))
                    return self.send(saved, 201)
                except (ValueError, KeyError, TypeError, AttributeError) as exc:
                    return self.send({'error': str(exc)}, 400)

        return PreviewHandler
