import copy
import unittest
from workspace_data.proposal import structured_manifest


class SparseStructureTest(unittest.TestCase):
    def setUp(self):
        self.source={'source_id':'s','records':[{'id':'r','locator':{'page':1},'data':{'text':'measured 0; flag false; timing 14 ms'}}]}
        self.citation={'record_id':'r1','field':'text','quote':'timing 14 ms'}
        self.structure={'rationale':'Distinct observations have different fields','records':[
            {'values':{'value':0,'flag':False,'empty':'','missing':None},'evidence':[self.citation]},
            {'values':{'timing':14,'unit':'ms'},'evidence':[self.citation]}]}

    def test_absent_fields_are_null_without_changing_values_or_inputs(self):
        original=copy.deepcopy(self.structure);source=copy.deepcopy(self.source)
        result=structured_manifest(self.source,self.structure,{'r1':'r'})
        self.assertEqual(self.structure,original);self.assertEqual(self.source,source)
        first,second=result['records']
        self.assertEqual(set(first['data']),set(second['data']))
        for before,after in zip(original['records'],result['records']):
            for key,value in before['values'].items():
                self.assertEqual(after['data'][key],value);self.assertIs(type(after['data'][key]),type(value))
        self.assertIsNone(first['data']['timing']);self.assertIsNone(second['data']['value'])
        self.assertEqual(first['locator']['source_evidence'][0]['quote'],'timing 14 ms')
        normalized=result['structuring_normalization']
        self.assertFalse(normalized['model_values_changed'])
        self.assertEqual(normalized['added_fields'][0]['fields'],['timing','unit'])
        self.assertEqual(normalized['added_fields'][1]['fields'],['empty','flag','missing','value'])

    def test_union_limit_cannot_be_bypassed_with_sparse_records(self):
        self.structure['records'][0]['values']={f'a{i}':i for i in range(11)}
        self.structure['records'][1]['values']={f'b{i}':i for i in range(10)}
        with self.assertRaisesRegex(ValueError,'twenty distinct fields'):
            structured_manifest(self.source,self.structure,{'r1':'r'})

    def test_sparse_shape_does_not_relax_citation_validation(self):
        self.structure['records'][1]['evidence']=[{**self.citation,'quote':'invented'}]
        with self.assertRaisesRegex(ValueError,'not present'):
            structured_manifest(self.source,self.structure,{'r1':'r'})
