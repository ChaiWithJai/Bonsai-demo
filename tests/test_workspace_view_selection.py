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
        self.assertEqual(compiled['node_membership']['all-records'], ['r'])
        self.assertEqual(len(compiled['chart']['props']['edges']),1)

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


class PlanningContractTest(unittest.TestCase):
    def test_profile_and_validator_agree_on_required_structure(self):
        from workspace_data.desktop_plan import profile
        from workspace_data.proposal import structured_manifest, planning_profile
        for kind, flag, required in [('document',False,True),('text',False,True),('email',False,True),('collection',True,True),('video',True,True),('table',False,False)]:
            with self.subTest(kind=kind):
                source={'source_id':'s','filename':'source','status':'extracted','kind':kind,'requires_structuring':flag,'records':[{'id':'r','data':{'text':'Observed source'}}]}
                self.assertEqual(planning_profile(profile(source))['requires_structuring'],required)
                if required:
                    with self.assertRaisesRegex(ValueError,'require explicit'):structured_manifest(source,None,{})
                else:self.assertIs(structured_manifest(source,None,{}),source)

    def test_structured_speech_preserves_original_media_type(self):
        from workspace_data.proposal import structured_manifest
        for kind in ('audio','video'):
            with self.subTest(kind=kind):
                source={'source_id':'s','kind':kind,'filename':'original.'+('mp4' if kind=='video' else 'wav'),'records':[{'id':'r','source_id':'s','locator':{'start_seconds':5.58},'data':{'text':'a stated requirement'}}]}
                structure={'rationale':'Preserve stated requirement','records':[{'values':{'requirement':'a stated requirement'},'evidence':[{'record_id':'r1','field':'text','quote':'a stated requirement'}]}]}
                result=structured_manifest(source,structure,{'r1':'r'})
                locator=result['records'][0]['locator']['source_evidence'][0]['locator']
                self.assertEqual(locator['source_kind'],kind)
                self.assertEqual(locator['source_filename'],source['filename'])
                self.assertEqual(locator['start_seconds'],5.58)
                self.assertNotIn('source_kind',source['records'][0]['locator'])
