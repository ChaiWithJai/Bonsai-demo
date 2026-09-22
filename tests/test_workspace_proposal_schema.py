import unittest
from jsonschema import Draft202012Validator
from workspace_data.proposal_schema import PROPOSAL_SCHEMA, GENERATION_SCHEMA
from workspace_provider import LocalProvider

class ProposalSchemaTests(unittest.TestCase):
    def test_supported_views_and_nullable_structure(self):
        validator=Draft202012Validator(PROPOSAL_SCHEMA)
        for view in [{'component':'RecordTable','columns':['value']},
                     {'component':'ForceDirectedGraph','groupBy':['value']},
                     {'component':'Scatterplot','x':'x','y':'value','color':None},
                     {'component':'LineChart','x':'x','y':'value','color':'group'}]:
            value={'interpretation':{'findings':[{'text':'One observation','record_ids':['r1']}],
                                    'rationale':'Inspect it','uncertainties':[],'questions':['Confirm?']},
                   'structure':None,'plan':{'title':'View','summary':'Inspect','fields':[{'name':'value','type':'number'}],'view':view}}
            validator.validate(value)
            value['structure']={'rationale':'Extract values','records':[{'values':{'value':0,'missing':None,'flag':False},'evidence':[{'record_id':'r1','field':'text','quote':'0'}]}]}
            validator.validate(value)
            value['structure']['records'][0]['id']='invented'
            self.assertTrue(list(validator.iter_errors(value)))

    def test_schema_is_isolated_from_unstructured_and_tool_calls(self):
        original=LocalProvider('http://127.0.0.1:5257','test')
        constrained=LocalProvider('http://127.0.0.1:5257','test',response_schema=PROPOSAL_SCHEMA)
        self.assertEqual(original.payload([],[],100)['response_format'],{'type':'json_object'})
        self.assertEqual(constrained.payload([],[],100)['response_format']['json_schema']['schema'],PROPOSAL_SCHEMA)
        self.assertNotIn('response_format',constrained.payload([],[{'type':'function'}],100))
        configured=constrained.configured({'profile':'legacy-greedy','seed':43})
        self.assertEqual(configured.response_schema,PROPOSAL_SCHEMA)
        self.assertIsNot(configured.response_schema,constrained.response_schema)

    def test_generation_shape_still_rejects_extra_fields(self):
        schema=GENERATION_SCHEMA['properties']['structure']['anyOf'][0]['properties']['records']['items']
        validator=Draft202012Validator(schema)
        record={'values':{'value':0},'evidence':[{'record_id':'r1','field':'text','quote':'0'}]}
        validator.validate(record)
        record['id']='invented'
        self.assertTrue(list(validator.iter_errors(record)))
        self.assertNotIn('maxItems',GENERATION_SCHEMA['properties']['structure']['anyOf'][0]['properties']['records'])
