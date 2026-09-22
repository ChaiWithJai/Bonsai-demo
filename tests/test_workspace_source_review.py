import copy
import unittest
from workspace_data.source_review import validate_source_review,review_schema,expand_review_ids
from workspace_data.proposal_schema import GENERATION_SCHEMA

class SourceReviewTest(unittest.TestCase):
    def setUp(self):
        self.aliases={'R1':'s:0','R2':'s:1'}
        self.manifest={'filename':'notes.txt','records':[{'id':'s:0','data':{'text':'Orchard has 5 issues'},'locator':{}},{'id':'s:1','data':{'text':'Orchard has 2 issues'},'locator':{}}]}
        self.first={'values':{'issues':5},'evidence':[{'record_id':'R1','field':'text','quote':'5 issues'}]}
        self.proposal={'structure':{'records':[self.first]}}
    def test_observed_silent_omission_fails_even_with_prose_claim(self):
        self.proposal['interpretation']={'rationale':'Two records were created'}
        with self.assertRaisesRegex(ValueError,'R2'):
            validate_source_review(self.manifest,self.proposal,self.aliases,['s:1'])
    def test_added_observation_passes(self):
        self.proposal['structure']['records'].append({'values':{'issues':2},'evidence':[{'record_id':'R2','field':'text','quote':'2 issues'}]})
        result=validate_source_review(self.manifest,self.proposal,self.aliases,['s:1'])
        self.assertEqual(result['represented_records'],1)
    def test_exclusion_requires_actual_quote_and_cannot_duplicate_data(self):
        self.proposal['source_review']=[{'reason':'Outside the requested period','evidence':{'record_id':'R2','field':'text','quote':'2 issues'}}]
        result=validate_source_review(self.manifest,self.proposal,self.aliases,['s:1'])
        self.assertEqual(result['excluded_records'],1)
        self.proposal['source_review'][0]['evidence']['quote']='99 issues'
        with self.assertRaisesRegex(ValueError,'not present'):validate_source_review(self.manifest,self.proposal,self.aliases,['s:1'])
        self.proposal['source_review'][0]['evidence']={'record_id':'R1','field':'text','quote':'5 issues'}
        with self.assertRaisesRegex(ValueError,'also be cited'):validate_source_review(self.manifest,self.proposal,self.aliases,['s:1'])
    def test_missing_context_cannot_be_counted_as_reviewed(self):
        with self.assertRaisesRegex(ValueError,'missing from'):validate_source_review(self.manifest,self.proposal,{'R1':'s:0'},['s:1'])
    def test_schema_is_isolated_and_ids_expand(self):
        before=copy.deepcopy(GENERATION_SCHEMA);schema=review_schema(GENERATION_SCHEMA)
        self.assertIn('source_review',schema['required']);self.assertEqual(GENERATION_SCHEMA,before)
        self.proposal['source_review']=[{'reason':'Context','evidence':{'record_id':'R2','field':'text','quote':'2 issues'}}]
        expand_review_ids(self.proposal,self.aliases)
        self.assertEqual(self.proposal['source_review'][0]['evidence']['record_id'],'s:1')

    def test_unused_sources_absent_from_findings_are_still_inspectable(self):
        from workspace_source_jobs import SourceJobs
        proposal={'interpretation':{'findings':[]},'structure':{'records':[]}}
        packet={'record_id_map':self.aliases,'records':[{'id':'R1','data':{'text':'first'}},{'id':'R2','data':{'text':'second'}}]}
        self.assertEqual([r['id'] for r in SourceJobs.proposal_examples(proposal,packet)],['s:0','s:1'])
