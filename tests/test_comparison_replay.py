"""Replay hooks preserve per-model/per-turn provenance without waiting for capture."""
import hashlib
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from comparison_api import ComparisonAPI
from grant_research import stream_turn
from test_comparison_api import FakeClient
import test_comparison_api as comparison_tests

class ReplayHooksTest(unittest.TestCase):
    def test_each_model_and_turn_including_repair_queues_saved_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            worker = SimpleNamespace(enqueue_comparison=lambda path, model, source: calls.append((path, model, source)))
            api = ComparisonAPI('unused', tmp, client=FakeClient(), replay_worker=worker)
            for model in ('bonsai', 'qwen'):
                for turn in (1, 2, 3):  # tool, final, and citation repair share stream_turn
                    path = Path(tmp)/('a'*32)/model/f'turn-{turn}'
                    path.mkdir(parents=True)
                    (path/'preflight.json').write_text(json.dumps({'rendered_prompt': model + str(turn)}))
                    with patch('grant_research.urlopen', return_value=comparison_tests.ComparisonTest().stream()):
                        stream_turn(api, model, {'model': model, 'messages': []}, path,
                                    SimpleNamespace(trace_id='trace'), 'agent', lambda *a: None, threading.Event(), turn)
            self.assertEqual(len(calls), 6)
            for path, model, source in calls:
                self.assertEqual(source['model'], model)
                self.assertEqual(source['comparison_run_id'], 'a'*32)
                self.assertEqual(source['request_sha256'], hashlib.sha256((path/'request.json').read_bytes()).hexdigest())
                self.assertEqual(json.loads((path/'request.json').read_text())['model'], model)
                self.assertTrue(json.loads((path/'result.json').read_text())['done_marker'])
                self.assertEqual(source['span_id'], f'{model}.inference.{source["turn"]}')

    def test_text_inferences_also_queue_their_own_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls=[]
            api=comparison_tests.ComparisonTest().make_api(tmp)
            api.replay_worker=SimpleNamespace(enqueue_comparison=lambda *a: calls.append(a))
            api.preflight=lambda options: {m: {'rendered_prompt': m + ' exact template'} for m in ('bonsai','qwen')}
            with patch('comparison_api.urlopen', side_effect=lambda *a, **k: comparison_tests.ComparisonTest().stream()):
                summary=api.run({'prompt':'shared'}, lambda *a: None)
            self.assertEqual(summary['status'], 'completed')
            self.assertEqual([c[1] for c in calls], ['bonsai','qwen'])
            self.assertTrue(all(c[0].name == 'turn-1' for c in calls))
            self.assertNotEqual(calls[0][2]['rendered_prompt_sha256'],calls[1][2]['rendered_prompt_sha256'])

    def test_incomplete_stream_does_not_enqueue(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls=[]
            api=ComparisonAPI('unused', tmp, client=FakeClient(), replay_worker=SimpleNamespace(enqueue_comparison=lambda *a: calls.append(a)))
            path=Path(tmp)
            with patch('grant_research.urlopen', return_value=comparison_tests.ComparisonTest().stream(False)):
                with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
                    stream_turn(api, 'qwen', {}, path, SimpleNamespace(trace_id='trace'), 'agent', lambda *a: None, threading.Event(), 1)
            self.assertFalse(calls)

    def test_queue_failure_durable_without_invalidating_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fail(*args): raise RuntimeError('queue unavailable')
            api=ComparisonAPI('unused', tmp, client=FakeClient(), replay_worker=SimpleNamespace(enqueue_comparison=fail))
            path=Path(tmp)
            (path/'preflight.json').write_text('{"rendered_prompt":"real context"}')
            with patch('grant_research.urlopen', return_value=comparison_tests.ComparisonTest().stream()):
                result=stream_turn(api, 'bonsai', {}, path, SimpleNamespace(trace_id='trace'), 'agent', lambda *a: None, threading.Event(), 1)
            self.assertTrue(result['done_marker'])
            status=json.loads((path/'activation-replay-status.json').read_text())
            self.assertEqual(status['status'],'error')
            self.assertIn('queue unavailable', status['error'])
