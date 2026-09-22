import json
from pathlib import Path
import tempfile
import unittest
from workspace_regression_case import assess, load_case, DEFAULT_SUITE

class RegressionCaseTests(unittest.TestCase):
    def test_values_preserve_multiplicity_and_distinguish_bool_from_number(self):
        case=load_case(DEFAULT_SUITE,'email-thread')
        compiled={'rows':[{'data':dict(row)} for row in case['expected_records']],
                  'plan':{'view':case['expected_view']},'excluded_record_ids':[]}
        compiled['rows'][0]['data']['open_issue_count']=5.0
        self.assertTrue(assess(case,compiled)['passed'])
        compiled['rows'].reverse()
        self.assertTrue(assess(case,compiled)['passed'])
        compiled['rows'][0]['data']['open_issue_count']=True
        self.assertFalse(assess(case,compiled)['checks']['record_values'])
        compiled['rows']=[{'data':case['expected_records'][0]}]*2
        self.assertFalse(assess(case,compiled)['checks']['record_values'])

    def test_source_changes_fail_integrity(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);suite=json.loads(DEFAULT_SUITE.read_text())
            (root/'suite.json').write_text(json.dumps(suite))
            (root/suite['cases'][0]['file']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'checksum'):
                load_case(root/'suite.json','dated-series')
