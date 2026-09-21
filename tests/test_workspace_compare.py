import unittest
from workspace_compare import compare, MATCH_FIELDS, CONFIG_FIELDS

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

    def test_equal_missing_configuration_is_explicitly_unverified(self):
        tags = {key: 'same' for key in MATCH_FIELDS}
        report = compare([{'tags': tags}, {'tags': tags}])
        self.assertTrue(report['task_metadata_matches'])
        self.assertFalse(report['configuration_complete'])
        self.assertEqual(report['configuration_differences'], {})
        self.assertEqual(report['unverified_configuration'], {key: [0, 1] for key in CONFIG_FIELDS})

    def test_placeholder_metadata_cannot_establish_a_match(self):
        tags = {key: 'same' for key in MATCH_FIELDS + CONFIG_FIELDS}
        tags['dataset_sha256'] = 'unknown'
        tags['hardware_id'] = 'unverified-test'
        report = compare([{'tags': tags}, {'tags': tags}])
        self.assertFalse(report['task_metadata_matches'])
        self.assertEqual(report['task_field_differences'], {'dataset_sha256': ['unknown', 'unknown']})
        self.assertEqual(report['unverified_configuration'], {'hardware_id': [0, 1]})
        tags['hardware_id'] = 'recorded-machine'
        self.assertTrue(compare([{'tags': tags}, {'tags': tags}])['configuration_complete'])

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
