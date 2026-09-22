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

class CompiledRetentionTest(unittest.TestCase):
    def setUp(self):
        self.compiled={'rows':[{'id':'a'},{'id':'b'}],'excluded_record_ids':[],
            'chart':{'component':'Scatterplot','props':{'data':[{'record_id':'a'},{'record_id':'b'}]}},'node_membership':{}}
    def test_chart_data_cannot_drop_or_duplicate_records(self):
        from workspace_data.task_contract import validate_compiled_retention
        validate_compiled_retention(self.compiled,['a','b'])
        for data in [[{'record_id':'a'}],[{'record_id':'a'},{'record_id':'a'}]]:
            self.compiled['chart']['props']['data']=data
            with self.assertRaisesRegex(ValueError,'Chart data'):
                validate_compiled_retention(self.compiled,['a','b'])
    def test_render_targets_are_checked_separately_from_source_rows(self):
        from workspace_data.task_contract import validate_retained_interactions
        evidence={'interaction':{'points':[{'record_id':'a'},{'record_id':'b'}]}}
        self.assertEqual(validate_retained_interactions(self.compiled,evidence,['a','b'])['checked_targets'],'point_targets')
        evidence['interaction']['points'].pop()
        with self.assertRaisesRegex(ValueError,'interaction targets'):
            validate_retained_interactions(self.compiled,evidence,['a','b'])
    def test_structured_identity_and_table_count_remain_required(self):
        from workspace_data.task_contract import validate_retained_interactions
        self.compiled['record_origin']='model_structured_unreviewed'
        self.compiled['rows']=[{'id':'out1','locator':{'source_evidence':[{'record_id':'a'}]}},{'id':'out2','locator':{'source_evidence':[{'record_id':'b'}]}}]
        self.compiled['chart']={'component':'RecordTable'}
        self.assertEqual(validate_retained_interactions(self.compiled,{'record_count':2},['a','b'])['retained_rows'],2)
        with self.assertRaisesRegex(ValueError,'Table evidence'):
            validate_retained_interactions(self.compiled,{'record_count':1},['a','b'])
        self.compiled['rows'][1]['locator']['source_evidence'][0]['record_id']='a'
        with self.assertRaisesRegex(ValueError,'omit or duplicate'):
            validate_retained_interactions(self.compiled,{'record_count':2},['a','b'])
    def test_graph_membership_and_targets_must_agree(self):
        from workspace_data.task_contract import validate_retained_interactions
        self.compiled['chart']={'component':'ForceDirectedGraph'};self.compiled['node_membership']={'group1':['a'],'group2':['b']}
        with self.assertRaisesRegex(ValueError,'group interaction'):
            validate_retained_interactions(self.compiled,{'interaction':{'nodes':[{'id':'group1'}]}},['a','b'])
        result=validate_retained_interactions(self.compiled,{'interaction':{'nodes':[{'id':'group1'},{'id':'group2'}]}},['a','b'])
        self.assertEqual(result['checked_targets'],'group_targets')

    def test_missing_scatter_coordinate_retains_record_without_invented_point(self):
        from workspace_data.task_contract import validate_retained_interactions
        self.compiled['rows']=[{'id':'a','data':{'date':'2026-09-14','count':0}}, {'id':'b','data':{'date':'2026-09-15','count':None}}]
        self.compiled['plan']={'view':{'x':'date','y':'count'}}
        self.compiled['excluded_record_ids']=['b']
        self.compiled['chart']['props']['data']=[{'record_id':'a'}]
        evidence={'interaction':{'points':[{'record_id':'a'}]}}
        result=validate_retained_interactions(self.compiled,evidence,['a','b'])
        self.assertEqual(result['retained_rows'],2)
        self.assertEqual(result['unplotted_retained_rows'],1)
        self.compiled['rows'][1]['data']['count']=0
        with self.assertRaisesRegex(ValueError,'explicitly missing'):
            validate_retained_interactions(self.compiled,evidence,['a','b'])
        self.compiled['rows'][1]['data']['count']=None
        self.compiled['chart']['props']['data'].append({'record_id':'b'})
        with self.assertRaisesRegex(ValueError,'Chart data'):
            validate_retained_interactions(self.compiled,evidence,['a','b'])

    def test_missing_record_exception_does_not_allow_line_gaps_or_unknown_ids(self):
        from workspace_data.task_contract import validate_compiled_retention
        self.compiled['excluded_record_ids']=['missing']
        with self.assertRaisesRegex(ValueError,'explicitly missing'):
            validate_compiled_retention(self.compiled,['a','b'])
        self.compiled['excluded_record_ids']=['b']
        self.compiled['chart']['component']='LineChart'
        with self.assertRaisesRegex(ValueError,'explicitly missing'):
            validate_compiled_retention(self.compiled,['a','b'])
