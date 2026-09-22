import unittest
from workspace_data.task_contract import task_record_ids,validate_task_records

class TaskContractTest(unittest.TestCase):
    def setUp(self):
        self.packet={'record_id_map':{'r1':'a','r2':'b'}}
    def record(self,*refs):return {'evidence':[{'record_id':ref} for ref in refs]}
    def check(self,records):validate_task_records({'structure':{'records':records}},self.packet,['a','b'])
    def test_missing_record_cannot_be_hidden_by_chart_choice(self):
        with self.assertRaisesRegex(ValueError,'Missing: r2'):
            self.check([self.record('r1')])
    def test_duplicates_or_combined_sources_do_not_satisfy_retention(self):
        with self.assertRaisesRegex(ValueError,'repeated: r1'):
            self.check([self.record('r1'),self.record('r1'),self.record('r2')])
        with self.assertRaisesRegex(ValueError,'exactly one distinct'):
            self.check([self.record('r1','r2')])
    def test_repeated_passages_same_source_and_resolved_ids_are_allowed(self):
        self.check([self.record('r1','a'),self.record('b')])
    def test_contract_is_opt_in_and_scope_explicit(self):
        source={'records':[{'id':'a','locator':{'page':1}},{'id':'b','locator':{'page':2}}]}
        self.assertEqual(task_record_ids(source,None,None),[])
        self.assertEqual(task_record_ids(source,{'pages':[2]},{'record_policy':'one_per_source_record'}),['b'])
        with self.assertRaises(ValueError):task_record_ids(source,None,{'record_policy':'guess'})
        with self.assertRaises(ValueError):task_record_ids({'records':[{'id':str(i)} for i in range(31)]},None,{'record_policy':'one_per_source_record'})
    def test_sampled_context_cannot_pass_required_coverage(self):
        with self.assertRaisesRegex(ValueError,'missing from the model context'):
            validate_task_records({'structure':None},self.packet,['a','b','c'])
    def test_malformed_structure_is_a_validation_error(self):
        for proposal in [None,{'structure':[]},{'structure':{'records':[None]}}]:
            with self.assertRaises(ValueError):validate_task_records(proposal,self.packet,['a','b'])
