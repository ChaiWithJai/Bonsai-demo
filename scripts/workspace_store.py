"""Persistent project revisions and ordered attempt events for the Workspace tab.

Model edits operate on source text with an explicit base hash. No host commands or
arbitrary filesystem paths are accepted here.
"""
from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path, PurePosixPath
import sqlite3
import uuid


class RevisionConflict(ValueError):
    pass


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def validate_path(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('Use a relative project path')
    path=PurePosixPath(value)
    if path.is_absolute() or any(part in ('..', '.', '') for part in value.split('/')) or len(value)>200:
        raise ValueError('Path must remain inside the project')
    if path.parts[0] in ('.git', 'node_modules', '.env') or path.name.startswith('.env'):
        raise ValueError('Project internals and credentials are not editable')
    return value


def validate_files(files):
    if not isinstance(files,dict) or not 1<=len(files)<=100:
        raise ValueError('A workspace needs 1 to 100 text files')
    for path,content in files.items():
        validate_path(path)
        if not isinstance(content,str) or len(content.encode())>250_000 or '\x00' in content:
            raise ValueError('Project files must be bounded UTF-8 text')
    if len(encoded(files).encode())>2_000_000:
        raise ValueError('Project exceeds the two-megabyte source limit')


class WorkspaceStore:
    def __init__(self,root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'workspace.sqlite3'
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, head TEXT NOT NULL,
                    created_at TEXT NOT NULL, fixture TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS revisions (
                    workspace_id TEXT NOT NULL, hash TEXT NOT NULL, parent TEXT,
                    files TEXT NOT NULL, author TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(workspace_id,hash));
                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, base_revision TEXT NOT NULL,
                    request TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS interface_reviews (
                    id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
                    revision TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    attempt_id TEXT NOT NULL, sequence INTEGER NOT NULL, kind TEXT NOT NULL,
                    payload TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(attempt_id,sequence));
            ''')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        db.row_factory=sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _revision(files,parent):
        return hashlib.sha256(encoded({'parent':parent,'files':files}).encode()).hexdigest()

    def create(self,title,files,fixture):
        validate_files(files)
        if not isinstance(title,str) or not 1<=len(title.strip())<=150:raise ValueError('Provide a workspace title')
        if not isinstance(fixture,dict):raise ValueError('Fixture provenance is required')
        key=uuid.uuid4().hex;revision=self._revision(files,None);now=timestamp()
        with self.connect() as db:
            db.execute('INSERT INTO revisions VALUES (?,?,?,?,?,?)',(key,revision,None,encoded(files),'authored_starter',now))
            db.execute('INSERT INTO workspaces VALUES (?,?,?,?,?)',(key,title.strip(),revision,now,encoded(fixture)))
        return self.get(key)

    def list(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT id,title,head,created_at FROM workspaces ORDER BY created_at DESC')]

    def get(self,key,revision=None):
        with self.connect() as db:
            workspace=db.execute('SELECT * FROM workspaces WHERE id=?',(key,)).fetchone()
            if workspace is None:raise ValueError('Workspace not found')
            revision=revision or workspace['head']
            row=db.execute('SELECT * FROM revisions WHERE workspace_id=? AND hash=?',(key,revision)).fetchone()
            if row is None:raise ValueError('Workspace revision not found')
            attempts=[dict(a) for a in db.execute('SELECT * FROM attempts WHERE workspace_id=? ORDER BY created_at',(key,))]
            return {**dict(workspace),'fixture':json.loads(workspace['fixture']),'revision':revision,
                    'parent_revision':row['parent'],'files':json.loads(row['files']),'author':row['author'],'attempts':attempts}

    def patch(self,key,base,edits,author='model',attempt=None):
        if not isinstance(edits,list) or not 1<=len(edits)<=20:raise ValueError('Provide 1 to 20 exact text edits')
        if author not in ('model','human','test'):raise ValueError('Record the edit author kind')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            active=db.execute("SELECT id FROM attempts WHERE workspace_id=? AND status='running'",(key,)).fetchone()
            if attempt is not None:
                row=db.execute('SELECT workspace_id,status FROM attempts WHERE id=?',(attempt,)).fetchone()
                if row is None or row['workspace_id']!=key or row['status']!='running':
                    raise RevisionConflict('Patch belongs to no running attempt in this workspace')
            elif active is not None:
                raise RevisionConflict('A running attempt owns this workspace')
            if author=='model' and attempt is None:
                raise ValueError('Model patches require a running attempt')
            head=db.execute('SELECT head FROM workspaces WHERE id=?',(key,)).fetchone()
            if head is None:raise ValueError('Workspace not found')
            if head['head']!=base:raise RevisionConflict('Workspace changed; read the current revision before patching')
            row=db.execute('SELECT files FROM revisions WHERE workspace_id=? AND hash=?',(key,base)).fetchone()
            files=json.loads(row['files'])
            for index, edit in enumerate(edits):
                if not isinstance(edit,dict) or set(edit)!={'path','old_text','new_text'}:raise ValueError('Each edit requires path, old_text and new_text')
                path=validate_path(edit['path']);old,new=edit['old_text'],edit['new_text']
                if path not in files:raise ValueError('The first slice only patches existing starter files')
                if PurePosixPath(path).name in ('package.json','package-lock.json','pnpm-lock.yaml','uv.lock'):raise ValueError('Dependencies are pinned for this experiment')
                if not isinstance(old,str) or not old or not isinstance(new,str) or len(new)>16000:raise ValueError('Provide bounded nonempty exact-match edits')
                count=files[path].count(old)
                if count!=1:raise RevisionConflict(f'{path}: edit {index+1} old_text matched {count} times; expected exactly once. Prefix: {old[:160]!r}')
                files[path]=files[path].replace(old,new,1)
            validate_files(files)
            if files==json.loads(row['files']):raise ValueError('Patch makes no change')
            revision=self._revision(files,base)
            db.execute('INSERT INTO revisions VALUES (?,?,?,?,?,?)',(key,revision,base,encoded(files),author,timestamp()))
            db.execute('UPDATE workspaces SET head=? WHERE id=?',(revision,key))
            if attempt is not None:
                self._append_event(db,attempt,'patch.applied',{
                    'base_revision':base,'revision':revision,'author':author,
                    'paths':sorted({edit['path'] for edit in edits}),
                    'edits_sha256':hashlib.sha256(encoded(edits).encode()).hexdigest()})
        return self.get(key)

    def start_attempt(self,key,base,request):
        if not isinstance(request,str) or not 1<=len(request.strip())<=8000:raise ValueError('Provide a bounded request')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            head=db.execute('SELECT head FROM workspaces WHERE id=?',(key,)).fetchone()
            if head is None or head['head']!=base:raise RevisionConflict('Start from the current workspace revision')
            if db.execute("SELECT id FROM attempts WHERE workspace_id=? AND status='running'",(key,)).fetchone():raise RevisionConflict('A workspace attempt is already running')
            aid=uuid.uuid4().hex;now=timestamp()
            db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?)',(aid,key,base,request.strip(),'running',now))
            db.execute('INSERT INTO events VALUES (?,?,?,?,?)',(aid,1,'attempt.started',encoded({'workspace_id':key,'base_revision':base}),now))
        return aid

    def event(self,attempt,kind,payload):
        allowed={'verification.reused','trace.started','context.checkpoint','loop.detected','model.delta','tool.started','tool.finished','build.finished','preview.ready','check.finished','attempt.completed','attempt.failed','attempt.cancelled'}
        if kind not in allowed or not isinstance(payload,dict):raise ValueError('Unknown event contract')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT status FROM attempts WHERE id=?',(attempt,)).fetchone()
            if row is None or row['status']!='running':raise RevisionConflict('Attempt is not running')
            sequence=self._append_event(db,attempt,kind,payload)
            if kind.startswith('attempt.'):
                db.execute('UPDATE attempts SET status=? WHERE id=?',(kind.split('.')[1],attempt))
        return sequence

    @staticmethod
    def _append_event(db,attempt,kind,payload):
        sequence=db.execute('SELECT COALESCE(MAX(sequence),0) FROM events WHERE attempt_id=?',(attempt,)).fetchone()[0]+1
        db.execute('INSERT INTO events VALUES (?,?,?,?,?)',(attempt,sequence,kind,encoded(payload),timestamp()))
        return sequence

    def recover_interrupted(self):
        """Call once on exclusive service startup, never on browser reconnect."""
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            attempts=[row['id'] for row in db.execute("SELECT id FROM attempts WHERE status='running'")]
            for attempt in attempts:
                self._append_event(db,attempt,'attempt.failed',{
                    'reason':'Service restarted; attempt interrupted. Saved revisions remain available.',
                    'interrupted':True})
                db.execute("UPDATE attempts SET status='failed' WHERE id=?",(attempt,))
        return attempts

    def events(self,attempt,after=0):
        if not isinstance(after,int) or after<0:raise ValueError('Event cursor must be nonnegative')
        with self.connect() as db:
            return [{**dict(row),'payload':json.loads(row['payload'])} for row in db.execute('SELECT * FROM events WHERE attempt_id=? AND sequence>? ORDER BY sequence',(attempt,after))]

    def review_interface(self, key, body):
        revision = body.get('revision')
        author, kind, action, note = (body.get(k) for k in ('author', 'reviewer_kind', 'action', 'note'))
        if not isinstance(author, str) or not 1 <= len(author.strip()) <= 100:
            raise ValueError('Provide a reviewer name')
        if kind not in ('human', 'codex', 'test') or action not in ('accept', 'reject'):
            raise ValueError('Choose a reviewer kind and accept or reject')
        if not isinstance(note, str) or not 1 <= len(note.strip()) <= 4000:
            raise ValueError('Explain the judgment using 1 to 4000 characters')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            workspace = db.execute('SELECT head FROM workspaces WHERE id=?', (key,)).fetchone()
            if workspace is None or workspace['head'] != revision:
                raise RevisionConflict('Project changed. Review the current saved revision.')
            if db.execute("SELECT id FROM attempts WHERE workspace_id=? AND status='running'", (key,)).fetchone():
                raise RevisionConflict('Wait for the active edit before reviewing')
            rows = db.execute('SELECT payload FROM interface_reviews WHERE workspace_id=? AND revision=? ORDER BY rowid', (key, revision)).fetchall()
            previous = json.loads(rows[-1]['payload']) if rows else None
            if body.get('previous_event_id') != (previous['event_id'] if previous else None):
                raise RevisionConflict('Another review was saved. Reload before reviewing.')
            event = {'event_id': uuid.uuid4().hex, 'workspace_id': key, 'revision': revision,
                     'created_at': timestamp(), 'author': author.strip(), 'reviewer_kind': kind,
                     'action': action, 'note': note.strip(), 'previous_event_id': body.get('previous_event_id'),
                     'identity_basis': 'self_declared_local_reviewer', 'scope': 'generated_interface'}
            db.execute('INSERT INTO interface_reviews VALUES (?,?,?,?,?)',
                       (event['event_id'], key, revision, encoded(event), event['created_at']))
        return event

    def interface_reviews(self, key):
        workspace = self.get(key)
        with self.connect() as db:
            events = [json.loads(row['payload']) for row in db.execute(
                'SELECT payload FROM interface_reviews WHERE workspace_id=? ORDER BY rowid', (key,))]
        current = [event for event in events if event['revision'] == workspace['head']]
        return {'revision': workspace['head'], 'events': events, 'latest': current[-1] if current else None}

    def export_interface_reviews(self, key):
        workspace = self.get(key)
        reviews = self.interface_reviews(key)
        if reviews['revision'] != workspace['head']:
            raise RevisionConflict('Project changed during export. Try again.')
        latest = reviews['latest']
        candidates = []
        if latest and latest['reviewer_kind'] == 'human' and latest['action'] == 'accept':
            candidates.append({'workspace_id': key, 'revision': workspace['head'],
                               'review': latest, 'files': workspace['files'],
                               'source_fixture': workspace['fixture'], 'attempts': workspace['attempts']})
        with self.connect() as db:
            has_notes = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='notes'").fetchone()
            notes = [json.loads(row['payload']) for row in db.execute('SELECT payload FROM notes WHERE workspace_id=? ORDER BY rowid', (key,))] if has_notes else []
        annotation_evidence = {'schema_version': 1, 'records': notes,
                               'sha256': hashlib.sha256(encoded(notes).encode()).hexdigest(),
                               'policy': 'Record notes are supporting evidence, not acceptance labels. Preserve their original review_origin and record_snapshot; no note alone qualifies a training candidate.'}
        dataset = {'task': 'generated_interface', 'examples': candidates}
        return {'schema_version': 1, 'dataset_sha256': hashlib.sha256(encoded(dataset).encode()).hexdigest(),
                'dataset_task': dataset['task'], 'review_events': reviews['events'],
                'training_candidates': candidates, 'example_count': len(candidates),
                'annotation_evidence': annotation_evidence,
                'policy': 'Only the latest human-declared acceptance of the current revision is a candidate. '
                          'Automated checks and test reviews do not establish human acceptance.'}
