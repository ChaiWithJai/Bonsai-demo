"""Provenance timestamps must not masquerade as quoted source content."""
import unittest
from workspace_data.proposal import structured_manifest


class TimestampEvidenceTests(unittest.TestCase):
    def source(self, value):
        return {'source_id':'s','kind':'video','filename':'clip.mp4','records':[
            {'id':'s:0','source_id':'s','data':{'text':'Stage: Review'},
             'locator':{'time_seconds':value}}]}

    def structure(self, field, quote):
        return {'rationale':'Inspect this sampled moment','records':[
            {'values':{'stage':'Review'},'evidence':[
                {'record_id':'r1','field':'text','quote':'Stage: Review'},
                {'record_id':'r1','field':field,'quote':quote}]}]}

    def test_explicit_timestamp_preserves_provenance_and_zero(self):
        for value in (0, 2.875):
            with self.subTest(value=value):
                result=structured_manifest(self.source(value),self.structure('locator.time_seconds',str(value)),{'r1':'s:0'})
                citation=result['records'][0]['locator']['source_evidence'][1]
                self.assertEqual(citation['field'],'locator.time_seconds')
                self.assertEqual(citation['locator']['time_seconds'],value)
                self.assertEqual(citation['locator']['source_kind'],'video')
                self.assertEqual(result['records'][0]['evidence_status'],'model_structured_unreviewed')

    def test_partial_invented_and_non_numeric_quotes_are_rejected(self):
        for field,quote in [('locator.time_seconds','2'),('locator.time_seconds','true'),
                            ('locator.time_seconds','NaN'),('locator.time_seconds','"2.875"'),
                            ('locator.start_seconds','2.875'),('time_seconds','2.875')]:
            with self.subTest(field=field,quote=quote),self.assertRaises(ValueError):
                structured_manifest(self.source(2.875),self.structure(field,quote),{'r1':'s:0'})

    def test_invalid_source_timestamps_are_rejected(self):
        for value,quote in [(True,'true'),(float('inf'),'Infinity'),(-1,'-1'),('2.875','2.875')]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                structured_manifest(self.source(value),self.structure('locator.time_seconds',quote),{'r1':'s:0'})

    def test_extra_record_id_error_identifies_the_required_repair(self):
        structure=self.structure('locator.time_seconds','0')
        structure['records'][0]['id']='stage_intake'
        with self.assertRaisesRegex(ValueError, "Unexpected keys: \['id'\]; missing keys: \[\]"):
            structured_manifest(self.source(0),structure,{'r1':'s:0'})
        del structure['records'][0]['id']
        self.assertEqual(len(structured_manifest(self.source(0),structure,{'r1':'s:0'})['records']),1)
