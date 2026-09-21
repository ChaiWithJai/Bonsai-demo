import unittest
from workspace_acceptance import validate_checks

class AcceptanceTests(unittest.TestCase):
    def test_empty_contract_does_not_claim_request_coverage(self):
        self.assertEqual(validate_checks(None), [])
        self.assertEqual(validate_checks([]), [])

    def test_contract_is_copied_and_bounded(self):
        step={'target':{'test_id':'record-row'},'action':'count','value':3}
        original=[step]; result=validate_checks(original)
        step['value']=99
        self.assertEqual(result[0]['value'],3)
        with self.assertRaises(ValueError): validate_checks(original*21)

    def test_executable_or_ambiguous_contracts_are_rejected(self):
        for step in [
            {'target':{'selector':'body'},'action':'visible','value':True},
            {'target':{'test_id':'x'},'action':'evaluate','value':'alert(1)'},
            {'target':{'test_id':'x'},'action':'count','value':True},
            {'target':{'test_id':'x'},'action':'click','value':None},
            {'target':{'role':'heading','name':''},'action':'visible','value':True},
        ]:
            with self.subTest(step=step), self.assertRaises(ValueError): validate_checks([step])
