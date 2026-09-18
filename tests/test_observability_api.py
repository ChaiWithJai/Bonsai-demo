import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from observability_api import Observability

class ObservabilityTest(unittest.TestCase):
    def make_comparison(self, directory):
        root = Path(directory)/'comparison-records'/('a'*32)
        root.mkdir(parents=True)
        (root/'comparison.json').write_text(json.dumps({'task':'grant_research','prompt':'Real recorded test prompt'}))
        (root/'summary.json').write_text(json.dumps({'experiment_id':'4','trace_id':'comparison-trace','trace_url':'http://127.0.0.1:5210/#/experiments/4/traces?traceId=comparison-trace'}))
        for model in ('bonsai','qwen'):
            path=root/model;path.mkdir()
            (path/'identity.json').write_text(json.dumps({'label':model,'identity':{'model_path':f'/{model}.gguf'}}))
            steps=[{'turn':1,'tool_call_id':f'{model}-call','name':'browser_open','arguments':{'url':'https://example.org'},'status':'completed'}]
            (path/'result.json').write_text(json.dumps({'status':'completed','content':model+' final','trace_id':'comparison-trace','experiment_id':'4','steps':steps}))
            (path/'conversation.json').write_text(json.dumps([{'role':'tool','tool_call_id':f'{model}-call','content':json.dumps({'content':model+' tool source'})}]))
            for turn in (1,2):
                t=path/f'turn-{turn}';t.mkdir()
                messages=[{'role':'user','content':model+' private context'}]
                if turn==2:messages.append({'role':'tool','tool_call_id':f'{model}-call','content':model+' result'})
                (t/'request.json').write_text(json.dumps({'messages':messages,'temperature':0.3}))
                (t/'preflight.json').write_text(json.dumps({'rendered_prompt':f'{model} actual rendered prompt {turn}'}))
                calls=[{'id':f'{model}-call','function':{'name':'browser_open','arguments':'{}'}}] if turn==1 else []
                (t/'result.json').write_text(json.dumps({'content':model+' final' if turn==2 else '', 'tool_calls':calls,
                    'finish_reason':'stop' if turn==2 else 'tool_calls','done_marker':True,'span_id':f'{model}-span-{turn}',
                    'timings':{'predicted_n':12,'predicted_per_second':3},'elapsed_ms':4000}))
        native=Path(directory)/'native-ui-records';native.mkdir()
        return root,Observability(SimpleNamespace(directory=native),{'model_path':'/current-bonsai.gguf'})

    def test_comparison_real_artifacts_keep_model_identity_and_exact_tool_edges(self):
        with tempfile.TemporaryDirectory() as directory:
            root,api=self.make_comparison(directory)
            sessions=api.sessions()['sessions']
            self.assertEqual(len(sessions),2)
            detail=api.detail('comparison_'+'a'*32+'_qwen')
            self.assertEqual(detail['session']['experiment_id'],'4')
            self.assertEqual(len(detail['nodes']),3)
            self.assertTrue(all(n['server']['model_path']=='/qwen.gguf' for n in detail['nodes']))
            self.assertTrue(all(n['status'] is None for n in detail['nodes']))
            self.assertEqual(detail['nodes'][0]['timings'][0]['predicted_n'],12)
            tool=detail['nodes'][1]
            self.assertFalse(tool['generation_available'])
            self.assertEqual(tool['timings'],[])
            self.assertIsNone(tool['span_id'])
            self.assertEqual(tool['span_availability'],'not_available')
            self.assertEqual(tool['response']['content'],'qwen tool source')
            self.assertEqual(len([e for e in detail['edges'] if e['type']=='tool_call']),1)
            self.assertEqual(len([e for e in detail['edges'] if e['type']=='tool_result']),1)
            self.assertNotIn('bonsai private context',json.dumps(detail))

    def test_replay_requires_exact_original_request_hash_and_remains_separate(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            root,api=self.make_comparison(directory)
            metadata=Path(directory)/'metadata';metadata.mkdir();(metadata/'activation-diagnostic').mkdir()
            api.manifest=metadata/'release-manifest.json'
            rendered='bonsai actual rendered prompt 2'
            replay={'kind':'new_instrumented_real_request_replay','passed':True,'rendered_prompt':rendered,
                'source':{'comparison_run_id':'a'*32,'model':'bonsai','turn':2,'request_sha256':'wrong',
                          'rendered_prompt_sha256':hashlib.sha256(rendered.encode()).hexdigest()},
                'replay':{'trace_id':'new-trace','run_id':'new-run','experiment_id':'5','started_at':1,'elapsed_ms':200},
                'generated_text':'Replay output','samples':[{'layer':0,'stats':{'rms':1}}]}
            f=metadata/'activation-diagnostic/replay-latest.json';f.write_text(json.dumps(replay))
            sid='comparison_'+'a'*32+'_bonsai'
            self.assertFalse(any('activation_replay' in n for n in api.detail(sid)['nodes']))
            replay['source']['request_sha256']=hashlib.sha256((root/'bonsai/turn-2/request.json').read_bytes()).hexdigest()
            replay['rendered_prompt']='different replay input'
            f.write_text(json.dumps(replay))
            self.assertFalse(any('activation_replay' in n for n in api.detail(sid)['nodes']))
            replay['rendered_prompt']=rendered
            f.write_text(json.dumps(replay));detail=api.detail(sid)
            original=next(n for n in detail['nodes'] if n['kind']=='completion' and n.get('turn')==2)
            self.assertEqual(original['activations']['status'],'not_captured')
            self.assertEqual(original['activation_replay']['replay']['trace_id'],'new-trace')
            replay_node=detail['nodes'][-1]
            self.assertEqual(replay_node['category'],'instrumented_replay')
            self.assertEqual(replay_node['trace_id'],'new-trace')
            self.assertEqual(replay_node['activations']['status'],'captured')
            self.assertEqual(detail['edges'][-1]['type'],'replay_of')
            self.assertFalse(any('activation_replay' in n for n in api.detail('comparison_'+'a'*32+'_qwen')['nodes']))

    def test_http_success_does_not_hide_mcp_error(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write_exchange(directory, 1, 'one', {'method': 'tools/call'},
                                {'result': {'isError': True, 'content': []}}, 'mcp')
            api = Observability(SimpleNamespace(directory=Path(directory)), {})
            detail = api.detail('one')
            self.assertEqual(detail['session']['error_count'], 1)
            self.assertIn('MCP returned an error', detail['nodes'][0]['error'])

    def test_partial_or_failed_later_answer_does_not_replace_completed_output(self):
        with tempfile.TemporaryDirectory() as directory:
            answer = lambda text, reason: {'choices': [{'message': {'content': text}, 'finish_reason': reason}]}
            self.write_exchange(directory, 1, 'one', {'messages': []}, answer('Completed answer', 'stop'))
            incomplete = self.write_exchange(directory, 2, 'one', {'messages': []}, answer('Cancelled answer', 'stop'))
            path = Path(directory) / incomplete / 'exchange.json'
            row = json.loads(path.read_text()); row['complete'] = False
            path.write_text(json.dumps(row))
            self.write_exchange(directory, 3, 'one', {'messages': []}, answer('Token limit answer', 'length'))
            failed = self.write_exchange(directory, 4, 'one', {'messages': []}, answer('Failed answer', 'stop'))
            path = Path(directory) / failed / 'exchange.json'
            row = json.loads(path.read_text()); row['status'] = 500
            path.write_text(json.dumps(row))
            api = Observability(SimpleNamespace(directory=Path(directory)), {})
            detail = api.detail('one')
            self.assertEqual(detail['session']['latest_output'], 'Completed answer')
            self.assertEqual(len(detail['nodes']), 4)
            self.assertEqual(detail['nodes'][-1]['response']['choices'][0]['message']['content'], 'Failed answer')
            self.assertEqual(api.sessions()['sessions'][0]['latest_output'], 'Completed answer')

    def test_scalar_and_array_payloads_remain_inspectable(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write_exchange(directory, 1, 'one', 'scalar request', ['array response'])
            self.write_exchange(directory, 2, 'one', 42, None)
            api = Observability(SimpleNamespace(directory=Path(directory)), {})
            detail = api.detail('one')
            self.assertEqual(detail['nodes'][0]['request'], {'malformed_payload': 'scalar request'})
            self.assertEqual(detail['nodes'][0]['response'], {'malformed_payload': ['array response']})
            self.assertEqual(detail['nodes'][1]['request'], {'malformed_payload': 42})
            self.assertEqual(detail['nodes'][1]['response'], {'malformed_payload': None})
            self.assertEqual(api.sessions()['sessions'][0]['latest_output'], '')

    def write_exchange(self, directory, index, session, request, response, kind='completion'):
        path = Path(directory) / f'{index:032x}'
        path.mkdir()
        (path / 'exchange.json').write_text(json.dumps(dict(
            request_id=path.name, session=session, kind=kind,
            started_at=index, complete=True, status=200)))
        (path / 'request.bin').write_text(json.dumps(request))
        (path / 'response.bin').write_text(json.dumps(response))
        return path.name

    def test_exact_tool_result_links_ignore_transport_ids_and_repeated_history(self):
        with tempfile.TemporaryDirectory() as directory:
            call = {'id': 'call_a', 'type': 'function', 'function': {'name': 'read', 'arguments': '{}'}}
            first = self.write_exchange(directory, 1, 'one', {'messages': []},
                {'choices': [{'message': {'tool_calls': [call]}}]})
            self.write_exchange(directory, 2, 'one',
                {'id': 'call_a', 'method': 'tools/call', 'params': {'name': 'read'}},
                {'id': 'call_a', 'result': {'content': 'transport result'}}, 'mcp')
            messages = [{'role': 'tool', 'tool_call_id': 'call_a', 'content': 'actual model tool result'}]
            consumer = self.write_exchange(directory, 3, 'one', {'messages': messages}, {'choices': []})
            self.write_exchange(directory, 4, 'one', {'messages': messages}, {'choices': []})
            api = Observability(SimpleNamespace(directory=Path(directory)), {})
            edges = api.detail('one')['edges']
            links = [edge for edge in edges if edge['type'] == 'tool_result']
            self.assertEqual(links, [{'from': first, 'to': consumer, 'type': 'tool_result', 'label': 'Tool result: call_a'}])
            self.assertEqual(len([edge for edge in edges if edge['type'] == 'sequence']), 3)

    def test_foreign_session_call_id_cannot_create_an_edge_or_leak_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write_exchange(directory, 1, 'private_other', {'messages': [{'role': 'user', 'content': 'PRIVATE_OTHER'}]},
                {'choices': [{'message': {'content': 'PRIVATE_OTHER', 'tool_calls': [{'id': 'shared_id'}]}}]})
            local = self.write_exchange(directory, 2, 'local',
                {'messages': [{'role': 'tool', 'tool_call_id': 'shared_id', 'content': 'local result'}]}, {'choices': []})
            api = Observability(SimpleNamespace(directory=Path(directory)), {})
            detail = api.detail('local')
            self.assertEqual([node['id'] for node in detail['nodes']], [local])
            self.assertEqual(detail['edges'], [])
            self.assertNotIn('PRIVATE_OTHER', json.dumps(detail))

    def test_session_isolation_and_missing_measurements(self):
        with tempfile.TemporaryDirectory() as directory:
            for i, session in enumerate(('one', 'two')):
                path = Path(directory) / (str(i) * 32)
                path.mkdir()
                (path / 'exchange.json').write_text(json.dumps(dict(request_id=path.name, session=session, kind='completion', started_at=i+1, complete=True, status=200)))
                (path / 'request.bin').write_text(json.dumps({'messages':[{'role':'user','content':session}],'temperature':0.3}))
                (path / 'response.bin').write_text(json.dumps({'choices':[{'message':{'content':'answer '+session},'finish_reason':'stop'}]}))
            api = Observability(SimpleNamespace(directory=Path(directory)), {'model_path':'current'})
            detail = api.detail('one')
            self.assertEqual(len(detail['nodes']), 1)
            self.assertEqual(detail['session']['last_output'], 'answer one')
            self.assertEqual(detail['nodes'][0]['server']['status'], 'unavailable')
            self.assertEqual(detail['nodes'][0]['timings'], [])
            self.assertEqual(api.model()['activations']['status'], 'not_captured')
            with self.assertRaises(ValueError):
                api.detail('../../secrets')
            with self.assertRaises(KeyError):
                api.detail('missing')

if __name__ == '__main__':
    unittest.main()
