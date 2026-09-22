from pathlib import Path
import socket
import tempfile
import threading
from types import SimpleNamespace
import unittest
from urllib.parse import urlparse
import urllib.request
from workspace_store import WorkspaceStore, RevisionConflict
from workspace_tools import WorkspaceTools
from workspace_worker import WorkspaceWorker

class PreviewLifecycleTests(unittest.TestCase):
    def test_close_releases_port_and_reopen_preserves_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);store=WorkspaceStore(root/'store')
            project=store.create(title='Development lifecycle',files={'App.svelte':'<p>Keep me</p>'},fixture={'kind':'desktop','compiled':{'rows':[]},'render_evidence':{}})
            assets=root/'assets';assets.mkdir();(assets/'index.html').write_text('Development preview')
            tools=WorkspaceTools(store,'http://127.0.0.1:5257');self.addCleanup(tools.close)
            build={'ok':True,'revision':project['head'],'assets':str(assets)}
            preview=tools.preview(project,build)
            self.assertEqual(urllib.request.urlopen(preview['url']).read(),b'Development preview')
            worker=SimpleNamespace(guard=threading.Lock(),running={},source_jobs=set(),store=store,tools=tools,latest={project['id']:preview})
            self.assertTrue(WorkspaceWorker.close_preview(worker,project['id'])['closed'])
            self.assertNotIn(project['id'],worker.latest)
            with self.assertRaises(OSError):socket.create_connection(('127.0.0.1',urlparse(preview['url']).port),timeout=1)
            self.assertEqual(store.get(project['id'])['head'],project['head'])
            self.assertFalse(WorkspaceWorker.close_preview(worker,project['id'])['closed'])
            reopened=tools.preview(store.get(project['id']),build)
            self.assertEqual(urllib.request.urlopen(reopened['url']).read(),b'Development preview')
            worker.running={'active':True}
            with self.assertRaises(RevisionConflict):WorkspaceWorker.close_preview(worker,project['id'])
            self.assertIn(project['id'],tools.servers)
