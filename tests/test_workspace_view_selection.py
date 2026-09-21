import unittest
from workspace_data.desktop_plan import compile_plan

class ViewSelectionTest(unittest.TestCase):
    def test_self_comparison_is_rejected_without_inventing_coordinates(self):
        source = {'source_id':'s','sha256':'sha','filename':'counts.json','status':'extracted',
                  'records':[{'id':'r','source_id':'s','locator':{'record':1},'data':{'model':'A','count':12}}]}
        plan = {'title':'Counts','summary':'One observed model','fields':[{'name':'model','type':'text'},{'name':'count','type':'number'}],
                'view':{'component':'Scatterplot','x':'count','y':'count','color':None}}
        with self.assertRaisesRegex(ValueError, 'different source fields'): compile_plan(source, plan)
        plan['view'] = {'component':'ForceDirectedGraph','groupBy':['model']}
        compiled = compile_plan(source, plan)
        self.assertEqual(compiled['rows'][0]['data']['count'], 12)
        self.assertEqual(list(compiled['node_membership'].values()), [['r']])

    def test_table_keeps_missing_and_zero_without_plot_exclusions(self):
        source = {'source_id':'s','sha256':'sha','filename':'counts.json','status':'extracted',
                  'records':[{'id':str(i),'source_id':'s','locator':{'record':i},'data':{'count':value}} for i,value in enumerate([0,None,12])]}
        plan = {'title':'Counts','summary':'Source values','fields':[{'name':'count','type':'number'}], 'view':{'component':'RecordTable'}}
        compiled = compile_plan(source, plan)
        self.assertEqual([row['data']['count'] for row in compiled['rows']], [0,None,12])
        self.assertEqual(compiled['excluded_record_ids'], [])
        self.assertEqual(compiled['chart']['props']['columns'], ['count'])

    def test_overview_columns_do_not_discard_record_fields(self):
        source = {'source_id':'s','sha256':'sha','filename':'counts.json','status':'extracted',
                  'records':[{'id':'r','source_id':'s','locator':{'record':1},'data':{'label':'A','count':0,'detail':'Evidence'}}]}
        plan = {'title':'Overview','summary':'Selected fields','fields':[{'name':'label','type':'text'},{'name':'count','type':'number'},{'name':'detail','type':'text'}], 'view':{'component':'RecordTable','columns':['label','count']}}
        compiled = compile_plan(source, plan)
        self.assertEqual(compiled['chart']['props']['columns'], ['label','count'])
        self.assertEqual(compiled['rows'][0]['data']['detail'], 'Evidence')
        for columns in ([], ['invented'], ['label','label']):
            plan['view']['columns'] = columns
            with self.assertRaisesRegex(ValueError, 'overview columns'): compile_plan(source, plan)
