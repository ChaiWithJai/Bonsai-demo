from pathlib import Path
import json
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from workspace_store import WorkspaceStore, RevisionConflict
from workspace_worker import WorkspaceWorker, checkpoint_context, FailedPatchTracker
from workspace_tools import WorkspaceTools


class TraceClient:
    def __init__(self):
        self.spans = []
        self.runs = []

    def get_experiment_by_name(self, name):
        return SimpleNamespace(experiment_id='test')

    def create_run(self, eid, tags):
        self.runs.append({'tags': tags})
        return SimpleNamespace(info=SimpleNamespace(run_id=str(len(self.runs))))

    def set_tag(self, run_id, key, value):
        self.runs[int(run_id) - 1]['tags'][key] = value

    def start_trace(self, name, **kwargs):
        self.spans.append({'name': name, **kwargs})
        return SimpleNamespace(trace_id='test-trace', span_id='root')

    def start_span(self, name, **kwargs):
        self.spans.append({'name': name, **kwargs})
        return SimpleNamespace(span_id=str(len(self.spans)))

    def end_span(self, *args, **kwargs):
        pass

    def end_trace(self, *args, **kwargs):
        self.runs[-1]['trace_result'] = kwargs

    def set_terminated(self, run_id, status):
        self.runs[-1]['status'] = status

    def log_artifacts(self, run_id, folder, path):
        self.runs[-1]['summary'] = json.loads((Path(folder) / 'summary.json').read_text())


class Provider:
    model = 'test-only'
    contract_version = 'test-provider'

    def __init__(self, store):
        self.store = store
        self.calls = []
        self.block = False
        self.entered = threading.Event()

    def generate(self, messages, tools, session, cancel, emit, max_tokens):
        self.calls.append(json.loads(json.dumps(messages)))
        self.entered.set()
        if self.block:
            cancel.wait(3)
            raise RuntimeError('Cancelled fixture')
        if messages[-1]['role'] == 'user':
            workspace = self.store.get(self.key)
            old = 'Bonsai repository observations' if 'Bonsai repository observations' in workspace['files']['App.svelte'] else 'First revision'
            new = 'First revision' if old.startswith('Bonsai') else 'Second revision'
            message = {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'patch-' + str(len(self.calls)), 'type': 'function', 'function': {
                'name': 'apply_patch', 'arguments': json.dumps({'base_revision': workspace['head'], 'edits': [{'path': 'App.svelte', 'old_text': old, 'new_text': new}]})}}]}
        else:
            message = {'role': 'assistant', 'content': 'Updated the existing title.'}
        return {'message': message, 'proxy_trace_id': 'fixture-exchange'}

    def preflight(self, messages, tools, max_tokens):
        return {'fits': True, 'prompt_tokens': 100, 'reserved_output_tokens': max_tokens, 'context_capacity': 16384}


class StubTools:
    def build(self, workspace, directory, cancel):
        return {'ok': True, 'revision': workspace['head'], 'assets': 'test-only'}

    def preview(self, workspace, build):
        return {'url': 'http://127.0.0.1:1/', 'revision': workspace['head']}

    def check_browser(self, workspace, preview, directory, cancel, case):
        return {'ok': True, 'revision': workspace['head'], 'case': case}

    def close(self):
        pass


class WorkerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = WorkspaceStore(self.temp.name)
        self.provider = Provider(self.store)
        self.client = TraceClient()
        self.worker = WorkspaceWorker(self.store, self.provider, StubTools(), self.client, 'http://127.0.0.1:5210')
        self.addCleanup(self.worker.close)
        self.workspace = self.worker.create()
        self.provider.key = self.workspace['id']

    def wait(self, aid):
        with self.worker.guard:
            active = self.worker.running.get(aid)
        if active:
            active[1].join(timeout=5)
            self.assertFalse(active[1].is_alive())
        return self.store.get(self.workspace['id'])['attempts'][-1]

    def test_repeated_failed_fragment_stops_before_third_generation(self):
        calls = []
        def repeated(*args, **kwargs):
            calls.append(1)
            edits = [{'path': 'App.svelte', 'old_text': 'absent fixture text',
                      'new_text': 'different replacement ' + str(len(calls))}]
            return {'message': {'role': 'assistant', 'content': '', 'tool_calls': [
                {'id': str(len(calls)), 'type': 'function', 'function': {'name': 'apply_patch',
                 'arguments': json.dumps({'base_revision': self.workspace['head'], 'edits': edits})}}]}}
        self.provider.generate = repeated
        aid = self.worker.start(self.workspace['id'], self.workspace['head'], 'Repeated edit fixture')['attempt_id']
        self.assertEqual(self.wait(aid)['status'], 'failed')
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.store.get(self.workspace['id'])['head'], self.workspace['head'])
        self.assertTrue(any(e['kind'] == 'loop.detected' for e in self.store.events(aid)))
        self.assertEqual(self.client.runs[-1]['summary']['loop_detection']['repetitions'], 2)

    def test_two_turn_history_and_complete_trace_include_enforced_tools(self):
        first = self.worker.start(self.workspace['id'], self.workspace['head'], 'Change the title')['attempt_id']
        self.assertEqual(self.wait(first)['status'], 'completed')
        one = self.store.get(self.workspace['id'])
        second = self.worker.start(one['id'], one['head'], 'Refine that title')['attempt_id']
        self.assertEqual(self.wait(second)['status'], 'completed')
        two = self.store.get(one['id'])
        self.assertEqual(two['parent_revision'], one['head'])
        self.assertIn('Second revision', two['files']['App.svelte'])
        self.assertIn('Change the title', self.provider.calls[2][1]['content'])
        names = [span['name'] for span in self.client.spans]
        for name in ('workspace.attempt', 'context.select', 'model.generate', 'tool.apply_patch', 'tool.build', 'tool.preview', 'tool.check_browser'):
            self.assertIn(name, names)
        self.assertEqual(self.client.runs[-1]['status'], 'FINISHED')
        self.assertEqual(self.store.events(second)[-1]['kind'], 'attempt.completed')
        first_tags, second_tags = (run['tags'] for run in self.client.runs)
        self.assertNotEqual(first_tags['request_sha256'], second_tags['request_sha256'])
        self.assertNotEqual(first_tags['initial_model_input_sha256'], second_tags['initial_model_input_sha256'])
        hashes = json.loads((self.store.root / 'attempts' / second / 'source-hashes.json').read_text())
        self.assertIn('workspace-tools/check_desktop.mjs', hashes)

    def test_cancel_closes_stream_and_service_does_not_start_duplicate_generation(self):
        self.provider.block = True
        aid = self.worker.start(self.workspace['id'], self.workspace['head'], 'Pause fixture')['attempt_id']
        self.assertTrue(self.provider.entered.wait(2))
        with self.assertRaises(RevisionConflict):
            self.worker.start(self.workspace['id'], self.workspace['head'], 'Duplicate')
        self.worker.cancel(aid)
        self.assertEqual(self.wait(aid)['status'], 'cancelled')
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(self.store.get(self.workspace['id'])['head'], self.workspace['head'])
        self.assertEqual(self.client.runs[-1]['status'], 'KILLED')

    def test_exclusive_ownership_does_not_interrupt_an_existing_worker(self):
        self.provider.block = True
        aid = self.worker.start(self.workspace['id'], self.workspace['head'], 'Pause fixture')['attempt_id']
        self.assertTrue(self.provider.entered.wait(2))
        with self.assertRaises(RuntimeError):
            WorkspaceWorker(self.store, self.provider, StubTools(), self.client, 'http://127.0.0.1:5210')
        self.assertEqual(self.store.get(self.workspace['id'])['attempts'][-1]['status'], 'running')
        self.worker.cancel(aid)
        self.wait(aid)

    def test_failed_browser_check_cannot_be_reported_as_completion(self):
        self.worker.tools.check_browser = lambda workspace, *args: {'ok': False, 'revision': workspace['head'], 'error': 'Fixture failure'}
        aid = self.worker.start(self.workspace['id'], self.workspace['head'], 'Change title')['attempt_id']
        self.assertEqual(self.wait(aid)['status'], 'failed')
        self.assertFalse(any(event['kind'] == 'attempt.completed' for event in self.store.events(aid)))
        self.assertEqual(self.client.runs[-1]['status'], 'FAILED')

    def test_build_returns_browser_failure_to_model_and_repairs_within_budget(self):
        steps = []
        checks = []
        def checker(workspace, *args):
            checks.append(workspace['head'])
            return {'ok': len(checks) > 1, 'revision': workspace['head'], 'error': 'Fixture browser assertion'}
        self.worker.tools.check_browser = checker
        def generate(messages, *args):
            index = len(steps)
            steps.append(index)
            if index == 4:
                return {'message': {'role': 'assistant', 'content': 'Verified repair.'}}
            if index in (1, 3):
                name, parameters = 'build', {}
            else:
                workspace = self.store.get(self.workspace['id'])
                if index == 2:
                    diagnostic = json.loads(messages[-1]['content'])
                    self.assertFalse(diagnostic['ok'])
                    self.assertIn('Fixture browser assertion', diagnostic['browser_check']['error'])
                old, new = ('Bonsai repository observations', 'First revision') if index == 0 else ('First revision', 'Fixed revision')
                name, parameters = 'apply_patch', {'base_revision': workspace['head'], 'edits': [{'path': 'App.svelte', 'old_text': old, 'new_text': new}]}
            return {'message': {'role': 'assistant', 'content': '', 'tool_calls': [{'id': str(index), 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(parameters)}}]}}
        self.provider.generate = generate
        aid = self.worker.start(self.workspace['id'], self.workspace['head'], 'Repair a browser failure')['attempt_id']
        self.assertEqual(self.wait(aid)['status'], 'completed')
        self.assertEqual(len(steps), 5)
        self.assertEqual(len(checks), 2)
        self.assertEqual(self.client.runs[-1]['summary']['repairs'], 1)

    def test_last_model_call_patch_is_verified_without_a_ninth_generation(self):
        calls = []
        def generate(*args):
            index = len(calls)
            calls.append(index)
            name, parameters = 'read_file', {'path': 'App.svelte'}
            if index == 7:
                name, parameters = 'apply_patch', {'base_revision': self.workspace['head'], 'edits': [{'path': 'App.svelte', 'old_text': 'Bonsai repository observations', 'new_text': 'Last call revision'}]}
            return {'message': {'role': 'assistant', 'content': '', 'tool_calls': [{'id': str(index), 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(parameters)}}]}}
        self.provider.generate = generate
        aid = self.worker.start(self.workspace['id'], self.workspace['head'], 'Edit on the last model call')['attempt_id']
        self.assertEqual(self.wait(aid)['status'], 'completed')
        self.assertEqual(len(calls), 8)
        self.assertEqual(self.client.runs[-1]['summary']['completion_source'], 'authored_verification_of_current_revision')

    def test_context_checkpoint_keeps_unicode_source_readable(self):
        workspace = dict(self.workspace, files={'App.svelte': '<p>Evidence · café</p>'})
        messages = checkpoint_context(workspace, 'Keep source labels', [])
        self.assertIn('Evidence · café', messages[1]['content'])
        packet = json.loads(messages[1]['content'].split('\n', 1)[1])
        self.assertEqual(packet['files'], workspace['files'])

    def test_context_checkpoint_preserves_current_source_and_failure_evidence(self):
        events = [{'kind': 'build.finished', 'payload': {'ok': False, 'revision': self.workspace['head'], 'stderr': 'Exact compiler diagnostic'}}]
        messages = checkpoint_context(self.workspace, 'Keep runtime drilldown', events)
        packet = json.loads(messages[1]['content'].split('\n', 1)[1])
        self.assertEqual(packet['files'], self.workspace['files'])
        self.assertEqual(packet['revision'], self.workspace['head'])
        self.assertEqual(packet['recent_diagnostics'][0]['error'], 'Exact compiler diagnostic')
        self.assertEqual(messages[-1]['content'], 'Keep runtime drilldown')


if __name__ == '__main__':
    unittest.main()

class FailedPatchTrackerTest(unittest.TestCase):
    def test_revision_and_fragment_changes_are_not_repetition(self):
        tracker = FailedPatchTracker()
        args = {'edits': [{'path': 'App.svelte', 'old_text': 'first'}]}
        failure = {'ok': False, 'current_revision': 'a', 'error': 'App.svelte: edit 1 old_text matched 0 times; expected exactly once.'}
        self.assertIsNone(tracker.observe('apply_patch', args, failure))
        self.assertIsNone(tracker.observe('apply_patch', args, dict(failure, current_revision='b')))
        args['edits'][0]['old_text'] = 'second'
        self.assertIsNone(tracker.observe('apply_patch', args, failure))
        self.assertIsNone(tracker.observe('read_file', args, failure))
        self.assertIsNone(tracker.observe('apply_patch', args, {'ok': True}))
        self.assertEqual(tracker.observe('apply_patch', args, failure)['repetitions'], 2)
