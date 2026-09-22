import tempfile
import unittest
from workspace_store import WorkspaceStore, RevisionConflict

class InterfaceReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = WorkspaceStore(self.temp.name)
        self.project = self.store.create('Review fixture', {'App.svelte': '<h1>Source</h1>'}, {'kind': 'test'})
        self.key = self.project['id']

    def body(self, **changes):
        return dict(revision=self.project['head'], author='Synthetic reviewer', reviewer_kind='test',
                    action='accept', note='Isolated test fixture', **changes)

    def test_only_latest_human_acceptance_exports_exact_revision(self):
        first = self.store.review_interface(self.key, self.body())
        self.assertEqual(self.store.export_interface_reviews(self.key)['example_count'], 0)
        body = self.body(previous_event_id=first['event_id']); body['reviewer_kind'] = 'human'
        second = self.store.review_interface(self.key, body)
        export = self.store.export_interface_reviews(self.key)
        self.assertEqual(export['example_count'], 1)
        self.assertEqual(export['training_candidates'][0]['files'], self.project['files'])
        body.update(previous_event_id=second['event_id'], action='reject')
        self.store.review_interface(self.key, body)
        self.assertEqual(self.store.export_interface_reviews(self.key)['example_count'], 0)
        self.assertEqual(len(self.store.interface_reviews(self.key)['events']), 3)

    def test_accepted_export_retains_input_coverage_and_hashes_it(self):
        import json
        import hashlib
        from workspace_store import encoded
        coverage={'records_shown':1,'records_total':3,'member_coverage':[
            {'source_id':'omitted','records_shown':0,'records_total':2,'represented':False}]}
        fixture={'kind':'desktop','compiled':{'planning_coverage':coverage},
                 'source_job':{'proposal_sha256':'proposal-hash'}}
        project=self.store.create('Coverage fixture',{'App.svelte':'<h1>Coverage</h1>'},fixture)
        # The human enum is simulated only inside this temporary test database.
        self.store.review_interface(project['id'],{'revision':project['head'],
            'author':'Synthetic unit test','reviewer_kind':'human','action':'accept',
            'note':'Isolated policy test, not a real review','previous_event_id':None})
        result=self.store.export_interface_reviews(project['id'])
        candidate=result['training_candidates'][0]
        self.assertEqual(candidate['source_fixture'],fixture)
        original_hash=result['dataset_sha256']
        candidate['source_fixture']['compiled']['planning_coverage']['records_shown']=3
        altered={'task':'generated_interface','examples':[candidate]}
        self.assertNotEqual(hashlib.sha256(encoded(altered).encode()).hexdigest(),original_hash)
        self.assertEqual(self.store.export_interface_reviews(project['id'])['dataset_sha256'],original_hash)

    def test_stale_review_and_changed_revision_are_rejected(self):
        self.store.review_interface(self.key, self.body())
        with self.assertRaises(RevisionConflict): self.store.review_interface(self.key, self.body())
        self.store.patch(self.key, self.project['head'], [{'path': 'App.svelte', 'old_text': 'Source', 'new_text': 'Changed'}], author='test')
        with self.assertRaises(RevisionConflict): self.store.review_interface(self.key, self.body())
        self.assertIsNone(self.store.interface_reviews(self.key)['latest'])
        self.assertEqual(self.store.export_interface_reviews(self.key)['example_count'], 0)

    def test_active_attempt_prevents_review(self):
        self.store.start_attempt(self.key, self.project['head'], 'Change the UI')
        with self.assertRaises(RevisionConflict): self.store.review_interface(self.key, self.body())

class InterfaceExportTest(unittest.TestCase):
    def test_mlflow_export_preserves_exact_bundle_and_does_not_infer_acceptance(self):
        import json
        from pathlib import Path
        from types import SimpleNamespace
        from workspace_worker import WorkspaceWorker
        class Client:
            def get_experiment_by_name(self, name): return SimpleNamespace(experiment_id='32')
            def create_run(self, eid, tags):
                self.tags = tags
                return SimpleNamespace(info=SimpleNamespace(run_id='export'))
            def log_artifact(self, rid, path, location):
                self.bundle = json.loads(Path(path).read_text())
            def log_metric(self, rid, name, value): self.count = value
            def set_terminated(self, rid, status): self.status = status
        with tempfile.TemporaryDirectory() as folder:
            store = WorkspaceStore(folder)
            project = store.create('Export fixture', {'App.svelte': '<p>Data</p>'}, {'kind':'test'})
            client = Client()
            worker = SimpleNamespace(store=store, client=client, tracking_uri='http://localhost:5210')
            result = WorkspaceWorker.export_interface_reviews(worker, project['id'])
            self.assertEqual(result['example_count'], 0)
            self.assertEqual(client.bundle['training_candidates'], [])
            self.assertEqual(client.tags['dataset_sha256'], result['dataset_sha256'])
            self.assertEqual(client.status, 'FINISHED')

    def test_annotation_evidence_preserves_origin_without_creating_candidates(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.store=WorkspaceStore(temp.name)
        self.key=self.store.create('Note evidence fixture',{'App.svelte':'<h1>Fixture</h1>'},{'kind':'test'})['id']
        import json
        empty=self.store.export_interface_reviews(self.key)
        self.assertEqual(empty['annotation_evidence']['records'],[])
        note={'id':'note1','record_id':'r1','note':'Development evidence','review_origin':'codex-development','record_snapshot':{'id':'r1','data':{'count':0}}}
        with self.store.connect() as db:
            db.execute('CREATE TABLE notes (workspace_id TEXT, id TEXT PRIMARY KEY, payload TEXT)')
            db.execute('INSERT INTO notes VALUES (?,?,?)',(self.key,note['id'],json.dumps(note)))
            db.execute('INSERT INTO notes VALUES (?,?,?)',('another-project','other',json.dumps({'note':'other project'})))
        result=self.store.export_interface_reviews(self.key)
        self.assertEqual(result['annotation_evidence']['records'],[note])
        self.assertEqual(result['example_count'],0)
        self.assertEqual(result['training_candidates'],[])
        self.assertEqual(result['dataset_sha256'],empty['dataset_sha256'])
        self.assertNotEqual(result['annotation_evidence']['sha256'],empty['annotation_evidence']['sha256'])
