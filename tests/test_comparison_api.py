import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from comparison_api import ComparisonAPI, ComparisonBusy


class FakeClient:
    def __init__(self):
        self.terminated = []
    def get_experiment_by_name(self, name):
        return SimpleNamespace(experiment_id='9')
    def create_run(self, *args, **kwargs):
        return SimpleNamespace(info=SimpleNamespace(run_id='a' * 32))
    def start_trace(self, *args, **kwargs):
        return SimpleNamespace(trace_id='trace-real-test', span_id='root')
    def start_span(self, *args, **kwargs):
        return SimpleNamespace(span_id=args[0])
    def set_terminated(self, run_id, status):
        self.terminated.append(status)
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class ComparisonTest(unittest.TestCase):
    def test_shared_context_and_settings_are_forwarded(self):
        settings=ComparisonAPI.validate({'prompt':'Explain this','project_context':'Shared facts',
            'max_tokens':4096,'temperature':.7,'top_p':.8,'top_k':12,'min_p':.1,'seed':73,'repeat_penalty':1.1})
        request=ComparisonAPI._request('model',settings)
        self.assertEqual(request['messages'],[{'role':'system','content':'Shared facts'},{'role':'user','content':'Explain this'}])
        for key in ('temperature','top_p','top_k','min_p','seed','repeat_penalty','max_tokens'):
            self.assertEqual(request[key],settings[key])

    def test_rejects_invalid_sampling(self):
        for key,value in [('top_p',0),('min_p',float('nan')),('top_k',1.5),('seed',True),('repeat_penalty',0)]:
            with self.assertRaises(ValueError):ComparisonAPI.validate({'prompt':'x',key:value})

    def make_api(self, folder):
        api = ComparisonAPI('unused', folder, client=FakeClient())
        api._identity = lambda model: {'id': model, 'model_id': model, 'available': True}
        api.preflight = lambda options: {}
        return api

    def test_preflight_checks_both_rendered_prompts_before_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            api = ComparisonAPI('unused', folder, client=FakeClient())
            api._identity = lambda model: {'model_id': model, 'available': True, 'identity': {
                'default_generation_settings': {'n_ctx': 8192}, 'total_slots': 1}}
            calls = []
            def posted(endpoint, path, payload):
                calls.append((endpoint, path, payload))
                return {'prompt': 'rendered template'} if path == '/apply-template' else {'tokens': [1] * (8000 if ':8083' in endpoint else 20)}
            api._post = posted
            with self.assertRaisesRegex(ValueError, 'qwen: rendered prompt'):
                api.preflight(api.validate({'prompt': 'short Unicode source'}))
            self.assertEqual([c[1] for c in calls], ['/apply-template', '/tokenize', '/apply-template', '/tokenize'])
            self.assertEqual(calls[1][2]['content'], 'rendered template')
            self.assertTrue(calls[1][2]['parse_special'])

    def test_failed_preflight_never_calls_inference(self):
        with tempfile.TemporaryDirectory() as folder:
            api = self.make_api(folder)
            def fail(options):
                raise ValueError('context overflow')
            api.preflight = fail
            with patch('comparison_api.urlopen') as opened:
                with self.assertRaisesRegex(ValueError, 'context overflow'):
                    api.run({'prompt': 'x'}, lambda *args: None)
            opened.assert_not_called()
            self.assertTrue((Path(folder)/('a'*32)/'failure.json').is_file())

    def stream(self, finished=True):
        events = [dict(choices=[dict(delta={'reasoning_content': 'thinking'})]),
                  dict(choices=[dict(delta={'content': 'answer'}, finish_reason='stop')],
                       timings={'predicted_per_second': 12}, usage={'completion_tokens': 2})]
        body = ''.join('data: ' + json.dumps(e) + '\n\n' for e in events)
        return io.BytesIO((body + ('data: [DONE]\n\n' if finished else '')).encode())

    def test_matching_inputs_actual_deltas_and_saved_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            api = self.make_api(folder)
            requests, events = [], []
            def opened(request, **kwargs):
                requests.append(json.loads(request.data))
                return self.stream()
            with patch('comparison_api.urlopen', side_effect=opened):
                summary = api.run({'prompt': 'same question'}, lambda name, data: events.append((name, data)))
            self.assertEqual(summary['status'], 'completed')
            self.assertFalse(summary['contention'])
            self.assertEqual(len(requests), 2)
            self.assertNotEqual(requests[0].pop('model'), requests[1].pop('model'))
            self.assertEqual(requests[0], requests[1])
            self.assertFalse(requests[0]['cache_prompt'])
            self.assertEqual(requests[0]['seed'], 42)
            self.assertNotIn('tools', requests[0])
            self.assertEqual([e[1]['model'] for e in events if e[0] == 'model_started'], ['bonsai', 'qwen'])
            self.assertEqual([r['content'] for r in summary['results']], ['answer', 'answer'])
            self.assertEqual(summary['results'][0]['timings']['predicted_per_second'], 12)
            self.assertTrue((Path(folder)/('a'*32)/'bonsai/response.sse').is_file())
            self.assertEqual(api.client.terminated, ['FINISHED'])

    def test_incomplete_stream_retained_as_error(self):
        with tempfile.TemporaryDirectory() as folder:
            api = self.make_api(folder)
            with patch('comparison_api.urlopen', side_effect=lambda *a, **k: self.stream(False)):
                summary = api.run({'prompt': 'x'}, lambda *args: None)
            self.assertEqual(summary['status'], 'error')
            self.assertEqual(summary['results'][0]['content'], 'answer')
            self.assertFalse(summary['results'][0]['done_marker'])
            self.assertEqual(api.client.terminated, ['FAILED'])

    def test_validation_and_single_inflight_guard(self):
        for body in ({'prompt': 'x', 'max_tokens': 4097}, {'prompt': 'x', 'endpoint': 'http://evil'},
                     {'prompt': 'x', 'thinking_budget_tokens': 129}, {'prompt': 'x', 'temperature': float('nan')},
                     {'prompt': 'x', 'max_tokens': True}):
            with self.assertRaises(ValueError):
                ComparisonAPI.validate(body)
        normalized = ComparisonAPI.validate({'prompt': 'x'})
        self.assertEqual(ComparisonAPI.validate(normalized), normalized)
        with tempfile.TemporaryDirectory() as folder:
            api = self.make_api(folder)
            api.run_lock.acquire()
            with self.assertRaises(ComparisonBusy):
                api.run(normalized, lambda *args: None)
            api.run_lock.release()

    def test_disconnect_cancels_without_starting_inference(self):
        with tempfile.TemporaryDirectory() as folder:
            api = self.make_api(folder)
            def gone(*args):
                raise BrokenPipeError()
            with patch('comparison_api.urlopen') as opened:
                summary = api.run({'prompt': 'x'}, gone)
            opened.assert_not_called()
            self.assertEqual(summary['status'], 'cancelled')
            self.assertEqual(api.client.terminated, ['KILLED'])


if __name__ == '__main__':
    unittest.main()
