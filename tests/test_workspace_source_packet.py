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

    def test_excess_citations_have_actionable_feedback(self):
        from workspace_data.proposal import validate_proposal
        proposal={'interpretation':{'findings':[{'text':'Both frames repeat three records','record_ids':['r'+str(i) for i in range(1,7)]}],'rationale':'Compare duplicates','questions':['Group these records?'],'uncertainties':[]},'structure':None,'plan':{}}
        with self.assertRaisesRegex(ValueError,'This finding has 6. Split a finding'):
            validate_proposal({},proposal,{'r'+str(i):str(i) for i in range(1,7)})
