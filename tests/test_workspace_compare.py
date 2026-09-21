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
