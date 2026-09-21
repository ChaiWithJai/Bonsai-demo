import unittest
from workspace_compare import compare, MATCH_FIELDS

class ComparisonTest(unittest.TestCase):
    def test_missing_or_changed_metadata_does_not_match(self):
        self.assertFalse(compare([{'tags': {}}, {'tags': {}}])['task_metadata_matches'])
        tags = {key: 'same' for key in MATCH_FIELDS}
        self.assertTrue(compare([{'tags': tags}, {'tags': tags}])['task_metadata_matches'])
        changed = dict(tags, dataset_sha256='different')
        self.assertFalse(compare([{'tags': tags}, {'tags': changed}])['task_metadata_matches'])

    def test_configuration_differences_are_explicit(self):
        report = compare([{'tags': {'sampling_seed': '42'}}, {'tags': {'sampling_seed': '43'}}])
        self.assertEqual(report['configuration_differences'], {'sampling_seed': ['42', '43']})
        with self.assertRaises(ValueError): compare([{'tags': {}}])

class ProjectComparisonBoundaryTest(unittest.TestCase):
    def test_cannot_compare_attempts_outside_selected_project(self):
        from types import SimpleNamespace
        from workspace_worker import WorkspaceWorker
        store = SimpleNamespace(get=lambda key: {'attempts': [{'id': 'owned', 'status': 'completed'}]})
        worker = SimpleNamespace(store=store)
        with self.assertRaisesRegex(ValueError, 'from this project'):
            WorkspaceWorker.comparison(worker, 'project', ['owned', 'foreign'])
        with self.assertRaisesRegex(ValueError, 'distinct'):
            WorkspaceWorker.comparison(worker, 'project', ['owned', 'owned'])
