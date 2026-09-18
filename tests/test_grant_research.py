import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from comparison_api import ComparisonAPI
from grant_research import run_research, fit_request, audit_citations
from test_comparison_api import FakeClient


class GrantResearchTest(unittest.TestCase):
    def test_citation_audit_requires_opened_page_and_rejects_unread_urls(self):
        sources = [{'url':'https://example.org/program','evidence_type':'opened_page'},
                   {'url':'https://www.google.com/search?q=grant','evidence_type':'search_page'}]
        passed = audit_citations('A conditional lead [program](https://example.org/program).',sources)
        self.assertEqual(passed['status'],'passed')
        self.assertEqual(passed['matched_urls'],['https://example.org/program'])
        self.assertEqual(passed['scope'],'URL provenance only; not claim verification')
        self.assertTrue(audit_citations('No citations here.',sources)['missing_citations'])
        self.assertTrue(audit_citations('[Search](https://www.google.com/search?q=grant)',sources)['missing_citations'])
        unsupported = audit_citations('[Program](https://example.org/program) [Unopened](https://example.org/discovered-link)',sources)
        self.assertEqual(unsupported['status'],'failed')
        self.assertEqual(unsupported['unsupported_urls'],['https://example.org/discovered-link'])

    def test_citation_repair_is_one_model_turn_without_new_browser_actions(self):
        for repaired_text, expected_status in [('[Program](https://example.org/program) remains a conditional lead.','completed'),
                                               ('Still no citations.','error')]:
            with self.subTest(expected_status=expected_status), tempfile.TemporaryDirectory() as directory:
                api = ComparisonAPI('unused',directory,client=FakeClient())
                api._identity = lambda model: {'available':True,'model_id':model}
                api._post = lambda endpoint,path,payload: {'prompt':'rendered'} if path=='/apply-template' else {'tokens':[1]}
                browser_calls=[]
                class Browser:
                    def __init__(self,*args,**kwargs):self.sources=[]
                    def call(self,name,arguments):
                        browser_calls.append(name)
                        source={'url':'https://example.org/program','page_id':1,'observed_at':1,'evidence_type':'opened_page'}
                        self.sources.append(source)
                        return {'url':source['url'],'page_id':1,'source':source,'content':'Source evidence'}
                requests=[]
                def generate(api,model,request,*args):
                    requests.append(json.loads(json.dumps(request)))
                    calls=[{'id':'native-call','type':'function','function':{'name':'browser_open','arguments':'{"url":"https://example.org/program"}'}}] if len(requests)==1 else []
                    return {'content':'' if calls else 'First draft lacks citations.' if len(requests)==2 else repaired_text,
                            'reasoning_content':'','tool_calls':calls,'finish_reason':'tool_calls' if calls else 'stop',
                            'timings':None,'first_delta_ms':None,'elapsed_ms':1}
                options=api.validate({'prompt':'Find grants','task':'grant_research'})
                with patch('grant_research.BrowserResearch',Browser),patch('grant_research.stream_turn',side_effect=generate):
                    result=run_research(api,'bonsai',options,'a'*32,SimpleNamespace(trace_id='trace',span_id='root'),
                        Path(directory),lambda *a:None,threading.Event(),'9',{})
                self.assertEqual(result['status'],expected_status)
                self.assertEqual(len(requests),3)
                self.assertEqual(browser_calls,['browser_open'])
                self.assertTrue(result['citation_repair_attempted'])
                self.assertNotIn('tools',requests[-1])
                self.assertEqual(requests[-1]['max_tokens'],1024)
                self.assertEqual(requests[-1]['tool_choice'],'none')
                self.assertEqual(result['content'],repaired_text)
                self.assertTrue((Path(directory)/'bonsai/turn-2/citation-audit.json').is_file())
                self.assertEqual(result['citation_audit']['status'],'passed' if expected_status=='completed' else 'failed')

    def test_six_tool_budget_has_identical_explicit_final_boundary_for_both_models(self):
        final_requests = {}
        with tempfile.TemporaryDirectory() as directory:
            api = ComparisonAPI('unused', directory, client=FakeClient())
            api._identity = lambda model: {'available': True, 'model_id': model}
            api._post = lambda endpoint, path, payload: {'prompt':'rendered'} if path=='/apply-template' else {'tokens':[1]}
            class Browser:
                def __init__(self, *args, **kwargs):
                    self.sources = []
                def call(self, name, arguments):
                    source = {'url':'https://example.org/grants', 'page_id':10, 'observed_at':1, 'evidence_type':'opened_page'}
                    self.sources.append(source)
                    return {'source':source, 'url':source['url'], 'page_id':10, 'content':'Observed test fixture'}
            def turn(api, model, request, *args):
                is_final = request['tool_choice'] == 'none'
                if is_final:
                    final_requests[model] = json.loads(json.dumps(request))
                calls = [] if is_final else [{'id':f'call-{i}', 'type':'function', 'function':{
                    'name':'browser_open', 'arguments':'{"url":"https://example.org/grants"}'}} for i in range(6)]
                return {'content':'Final conditional lead [source](https://example.org/grants)' if is_final else '', 'reasoning_content':'',
                    'tool_calls':calls, 'finish_reason':'stop' if is_final else 'tool_calls',
                    'timings':None, 'first_delta_ms':None, 'elapsed_ms':1}
            options = api.validate({'prompt':'Find community data center grant leads', 'task':'grant_research'})
            with patch('grant_research.BrowserResearch', Browser), patch('grant_research.stream_turn', side_effect=turn):
                for model in ('bonsai','qwen'):
                    result = run_research(api,model,options,'a'*32,SimpleNamespace(trace_id='trace',span_id='root'),
                        Path(directory),lambda *a:None,threading.Event(),'9',{})
                    self.assertEqual(result['tool_calls_count'],6)
                    self.assertEqual(result['status'],'completed')
            for request in final_requests.values():
                self.assertNotIn('tools',request)
                self.assertEqual(request['tool_choice'],'none')
                self.assertEqual(request['max_tokens'],1024)
                self.assertEqual(request['stop'],['<tool_call>','<function_call>','</think>'])
                self.assertEqual(request['messages'][-1]['role'],'user')
                self.assertIn('budget is exhausted',request['messages'][-1]['content'])
                self.assertIn('Do not call tools',request['messages'][-1]['content'])
            final_requests['bonsai'].pop('model');final_requests['qwen'].pop('model')
            self.assertEqual(final_requests['bonsai'],final_requests['qwen'])

    def test_raw_tool_markup_is_a_failed_answer(self):
        with tempfile.TemporaryDirectory() as directory:
            api = ComparisonAPI('unused', directory, client=FakeClient())
            api._identity = lambda model: {'available': True, 'model_id': model}
            api._post = lambda endpoint, path, payload: {'prompt':'rendered'} if path=='/apply-template' else {'tokens':[1]}
            output = {'content':'<tool_call>{"name":"browser_open"}</tool_call>', 'reasoning_content':'',
                      'tool_calls':[], 'finish_reason':'stop', 'timings':None, 'first_delta_ms':None, 'elapsed_ms':1}
            with patch('grant_research.stream_turn', return_value=output):
                result = run_research(api,'bonsai',api.validate({'prompt':'Find grants','task':'grant_research'}),
                    'a'*32,SimpleNamespace(trace_id='trace',span_id='root'),Path(directory),lambda *a:None,
                    threading.Event(),'9',{})
            self.assertEqual(result['status'],'error')
            self.assertIn('raw tool-call markup',result['error'])

    def test_native_tool_choice_result_round_trip_and_final_output(self):
        with tempfile.TemporaryDirectory() as directory:
            api = ComparisonAPI('unused', directory, client=FakeClient())
            api._identity = lambda model: {'available': True, 'model_id': model}
            api._post = lambda endpoint, path, payload: {'prompt': 'rendered'} if path == '/apply-template' else {'tokens': [1] * 20}
            observed = []
            class Browser:
                def __init__(self, *args, **kwargs):
                    self.sources = []
                def call(self, name, arguments):
                    observed.append((name, arguments))
                    source = {'url': 'https://example.org/program', 'page_id': 10, 'observed_at': 1, 'evidence_type': 'opened_page'}
                    self.sources.append(source)
                    return {'source': source, 'url': source['url'], 'page_id': 10, 'content': 'Actual test fixture source'}
            requests = []
            def turn(api, model, request, *args):
                requests.append(json.loads(json.dumps(request)))
                call = {'id': 'model-emitted-1', 'type': 'function', 'function': {'name': 'browser_open', 'arguments': '{"url":"https://example.org/program"}'}}
                return {'content': '' if len(requests)==1 else 'Conditional lead from [source](https://example.org/program)', 'reasoning_content': '',
                        'tool_calls': [call] if len(requests)==1 else [], 'finish_reason': 'tool_calls' if len(requests)==1 else 'stop',
                        'timings': None, 'first_delta_ms': None, 'elapsed_ms': 1}
            options = api.validate({'prompt': 'Find grant leads', 'task': 'grant_research', 'project_context': 'Location unknown'})
            with patch('grant_research.BrowserResearch', Browser), patch('grant_research.stream_turn', side_effect=turn):
                result = run_research(api, 'bonsai', options, 'a'*32, SimpleNamespace(trace_id='trace',span_id='root'),
                    Path(directory), lambda *args: None, threading.Event(), '9', {})
            self.assertEqual(requests[0]['tool_choice'], 'required')
            tool_results = [m for m in requests[1]['messages'] if m['role']=='tool']
            self.assertEqual(tool_results[0]['tool_call_id'], 'model-emitted-1')
            self.assertEqual(observed, [('browser_open', {'url':'https://example.org/program'})])
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['tool_calls_count'], 1)
            self.assertFalse(result['eligibility_verified'])
            self.assertEqual(result['evidence_status'], 'opened_sources_require_eligibility_review')

    def test_context_compaction_is_explicit_and_retains_source_url(self):
        api = SimpleNamespace(endpoints={'bonsai':'local'})
        def post(endpoint, path, payload):
            if path=='/apply-template':
                return {'prompt': json.dumps(payload)}
            return {'tokens': [1] * len(payload['content'])}
        api._post = post
        request = {'max_tokens': 100, 'messages':[{'role':'tool','tool_call_id':'x','content':json.dumps({'content':'x'*4000,'source':{'url':'https://example.org'}})}]}
        result = fit_request(api, 'bonsai', request, 2400)
        self.assertTrue(result['compactions'])
        self.assertIn('https://example.org', request['messages'][0]['content'])
        self.assertTrue(json.loads(request['messages'][0]['content'])['truncated'])


if __name__ == '__main__':
    unittest.main()
