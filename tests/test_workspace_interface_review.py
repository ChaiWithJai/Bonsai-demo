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
