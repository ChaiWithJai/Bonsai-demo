import json
import unittest
from workspace_data.proposal import source_packet

class SourcePacketTest(unittest.TestCase):
    def test_long_email_retains_question_passage_and_reports_partial_coverage(self):
        body='beginning '+('irrelevant '*1000)+' latency regression 42ms '+('later '*2000)+'ending'
        source={'records':[{'id':'original','locator':{'message':1},'data':{'body':body}}]}
        packet=source_packet(source,request='Investigate the latency regression')
        row=packet['records'][0]
        self.assertIn('latency regression 42ms',row['data']['body'])
        self.assertEqual(packet['record_id_map'],{'r1':'original'})
        self.assertEqual(packet['excerpted_record_ids'],['r1'])
        self.assertIn('partial',packet['coverage'])
        for start,end in row['field_excerpts']['body']['shown_ranges']:self.assertIn(body[start:end],row['data']['body'])
        self.assertLessEqual(len(json.dumps(row,ensure_ascii=False)),32000)

    def test_relevant_record_survives_a_tight_budget(self):
        rows=[{'id':str(i),'locator':{'line':i},'data':{'text':'routine event '*40}} for i in range(20)]
        rows[19]['data']['text']='critical latency regression'
        packet=source_packet({'records':rows},max_chars=700,request='latency regression')
        self.assertIn('19',packet['record_id_map'].values())
        self.assertLessEqual(sum(len(json.dumps(r,ensure_ascii=False)) for r in packet['records']),700)

    def test_small_source_keeps_all_values_unchanged(self):
        data={'value':0,'missing':None,'text':'source text'}
        packet=source_packet({'records':[{'id':'source','locator':{'line':1},'data':data}]})
        self.assertEqual(packet['records'][0]['data'],data)
        self.assertEqual(packet['coverage'],'all records and fields')

    def test_collection_sample_represents_smaller_file_and_discloses_omission(self):
        rows=[{'id':f'a:{i}','source_id':'a','locator':{},'data':{'text':'latency '*12}} for i in range(20)]
        rows.append({'id':'b:0','source_id':'b','locator':{},'data':{'text':'team requirement'}})
        manifest={'records':rows,'sources':[{'source_id':'a','filename':'large.txt','records':20},
                                           {'source_id':'b','filename':'small.txt','records':1}]}
        packet=source_packet(manifest,max_chars=400,request='latency')
        self.assertIn('b:0',packet['record_id_map'].values())
        self.assertTrue(all(m['represented'] for m in packet['member_coverage']))
        self.assertLessEqual(sum(len(json.dumps(r,ensure_ascii=False)) for r in packet['records']),400)
        tiny=source_packet(manifest,max_chars=1,request='latency')
        self.assertFalse(any(m['represented'] for m in tiny['member_coverage']))
        self.assertIn('partial',tiny['coverage'])

    def test_requested_page_beats_keyword_matches_under_budget(self):
        rows=[{'id':str(i),'locator':{'page':i},'data':{'text':'latency regression '*20}} for i in range(1, 21)]
        rows[18]['data']['text']='Previously omitted profiler labels'
        packet=source_packet({'records':rows},max_chars=200,request='latency regression; inspect page 19')
        self.assertEqual(packet['record_id_map'],{'r19':'19'})
        self.assertEqual(packet['requested_page_coverage']['shown'],[19])

    def test_page_ranges_disclose_missing_and_over_budget_pages(self):
        rows=[{'id':str(i),'locator':{'page':i},'data':{'text':'content '*20}} for i in range(1, 5)]
        packet=source_packet({'records':rows},max_chars=250,request='Inspect pages 3-5')
        coverage=packet['requested_page_coverage']
        self.assertEqual(coverage['requested'],[3,4,5])
        self.assertEqual(coverage['shown'],[3])
        self.assertEqual(coverage['omitted'],[4])
        self.assertEqual(coverage['not_found'],[5])
        self.assertIn('partial',packet['coverage'])

    def test_excess_citations_have_actionable_feedback(self):
        from workspace_data.proposal import validate_proposal
        proposal={'interpretation':{'findings':[{'text':'Both frames repeat three records','record_ids':['r'+str(i) for i in range(1,7)]}],'rationale':'Compare duplicates','questions':['Group these records?'],'uncertainties':[]},'structure':None,'plan':{}}
        with self.assertRaisesRegex(ValueError,'This finding has 6. Split a finding'):
            validate_proposal({},proposal,{'r'+str(i):str(i) for i in range(1,7)})


class PlanningCoverageTest(unittest.TestCase):
    def test_pdf_summary_and_collection_gaps_survive_without_page_logs(self):
        from workspace_data.proposal import planning_profile
        coverage={'page_count':3,'pages_with_text':2,'unresolved_pages':[2],
                  'ocr_pages':[3],'limitation':'Diagrams were not interpreted',
                  'pages':[{'page':2,'status':'unresolved'}]}
        original={'extraction_coverage':coverage,
                  'source_coverage':[{'source_id':'pdf','coverage':{'extraction_coverage':coverage}}]}
        result=planning_profile(original)
        for value in [result['extraction_coverage'],result['source_coverage'][0]['coverage']['extraction_coverage']]:
            self.assertEqual(value['unresolved_pages'],[2])
            self.assertEqual(value['ocr_pages'],[3])
            self.assertEqual(value['page_count'],3)
            self.assertEqual(value['limitation'],'Diagrams were not interpreted')
            self.assertNotIn('pages',value)
        self.assertIn('pages',coverage)

class RepairDiagnosticsTest(unittest.TestCase):
    def test_independent_violations_are_reported_together_without_mutation(self):
        from workspace_data.proposal import repair_diagnostics
        manifest={'records':[{'id':'source','locator':{},'data':{'x':1,'extra':2}}]}
        value={'interpretation':{'findings':[{'text':'Example','record_ids':['r1']*6}]},'structure':None,
               'plan':{'fields':[{'name':'x','type':'number'}],'view':{'component':'RecordTable','columns':['x']*21}}}
        before=json.dumps(value,sort_keys=True)
        result=repair_diagnostics(manifest,value,{'r1':'source'},ValueError('First validation failure'))
        self.assertTrue(any('6 entries' in error for error in result))
        self.assertTrue(any('Missing: extra' in error for error in result))
        self.assertTrue(any('21 entries' in error for error in result))
        self.assertEqual(json.dumps(value,sort_keys=True),before)
        self.assertEqual(repair_diagnostics(manifest,None,{},'Malformed JSON'),['Malformed JSON'])

    def test_schema_repair_preserves_heterogeneous_measurements(self):
        from workspace_data.proposal import repair_diagnostics,validate_schema_repair_preservation
        previous={'structure':{'records':[{'values':{'before':14,'after':520}},{'values':{'variant':'Baseline','value':402.1}}]}}
        repaired={'structure':{'records':[{'values':{'before':14,'after':520,'variant':None,'value':None}},{'values':{'before':None,'after':None,'variant':'Baseline','value':402.1}}]}}
        frozen=json.dumps(previous,sort_keys=True)
        hints=repair_diagnostics({},previous,{},'All structured records must use the same fields')
        self.assertTrue(any('union of existing fields: after, before, value, variant' in hint for hint in hints))
        validate_schema_repair_preservation(previous,repaired)
        repaired['structure']['records'][1]['values']['value']=None
        with self.assertRaisesRegex(ValueError,'discarded or changed.*value'):
            validate_schema_repair_preservation(previous,repaired)
        repaired['structure']['records'].pop()
        with self.assertRaisesRegex(ValueError,'number and order'):
            validate_schema_repair_preservation(previous,repaired)
        self.assertEqual(json.dumps(previous,sort_keys=True),frozen)
