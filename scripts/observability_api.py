"""Read-only views over captured exchanges and their actual MLflow traces."""
import json
import hashlib
import math
import struct
import re
from pathlib import Path

LIMITATIONS = [
    'Each trace records one HTTP exchange, not a whole agent run.',
    'Sequence edges indicate recorded order, not proof of causality.',
    'Reasoning text is model output, not a measurement of internal activations.',
    'Absent token, cost or activation measurements are unavailable, not zero.',
]

def tool_error(response):
    for event in [response, *response.get('events', [])]:
        if isinstance(event, dict) and (event.get('error') or
                isinstance(event.get('result'), dict) and event['result'].get('isError')):
            return 'MCP returned an error; inspect the recorded response.'
    return None

def title_generation(request):
    prefix = 'Based on the following interaction, generate a short, concise title (maximum 6-8 words)'
    for message in request.get('messages', []):
        if message.get('role') != 'user':
            continue
        content = message.get('content')
        if isinstance(content, str) and content.startswith(prefix):
            return True
    return False

class Observability:
    def __init__(self, recorder, model_info, manifest=None, comparison_directory=None):
        self.recorder = recorder
        self.model_info = model_info
        self.manifest = Path(manifest) if manifest else None
        self.trace_cache = {}
        self.comparison_directory = Path(comparison_directory) if comparison_directory else self.recorder.directory.parent / 'comparison-records'
        self.comparison_trace_cache = {}
        self.research_directory = self.recorder.directory.parent / 'research-records'

    @staticmethod
    def json_file(path, default=None):
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            return {} if default is None else default

    def research_summary(self, folder):
        record = self.json_file(folder / 'research.json')
        if not record or not (folder / 'request.json').is_file():
            return None
        identity = record.get('model_identity') or {}
        response = record.get('response') or {}
        output = '\n'.join(choice.get('message', {}).get('content', '') for choice in response.get('choices', [])
                           if isinstance(choice.get('message', {}).get('content'), str))
        return {'id': 'research_' + folder.name, 'source': 'research', 'research_id': folder.name, 'latest_output': output, 'last_output': output,
            'title': record.get('title') or 'Pelican research · ' + str(identity.get('repo', folder.name)),
            'label': identity.get('repo') or identity.get('label'),
            'started_at': record.get('started_at', (folder / 'research.json').stat().st_mtime),
            'updated_at': record.get('updated_at', (folder / 'research.json').stat().st_mtime),
            'node_count': 1, 'completion_count': 1, 'tool_count': 0,
            'error_count': int(record.get('status') == 'error'), 'status': record.get('status'),
            'experiment_id': record.get('experiment_id'), 'mlflow_url': record.get('mlflow_url')}

    def research_detail(self, sid):
        if not re.fullmatch(r'research_[a-f0-9]{32}', sid):
            raise KeyError(sid)
        folder = self.research_directory / sid[9:]
        session = self.research_summary(folder)
        if session is None:
            raise KeyError(sid)
        record = self.json_file(folder / 'research.json')
        raw = (folder / 'request.json').read_bytes()
        request = json.loads(raw)
        expected = hashlib.sha256(raw).hexdigest()
        identity = record.get('model_identity') or {}
        node = {'id': sid + '_inference', 'request_id': sid + '_inference', 'source': 'research',
            'research_id': folder.name, 'kind': 'completion', 'category': 'inference',
            'generation_available': True, 'name': 'Instrumented research inference',
            'request': request, 'request_sha256': expected, 'response': record.get('response', {}),
            'server': identity, 'model_identity': identity, 'settings': {k: v for k, v in request.items() if k not in ('messages', 'tools')},
            'complete': record.get('status') == 'completed', 'execution_status': record.get('status'),
            'error': record.get('error'), 'elapsed_ms': record.get('elapsed_ms'),
            'timings': [record['timings']] if record.get('timings') else [],
            'started_at': record.get('started_at'), 'timestamp_source': 'research_record',
            'trace_id': record.get('trace_id'), 'trace_url': record.get('trace_url'),
            'experiment_id': record.get('experiment_id'), 'run_id': record.get('run_id'),
            'tool_calls': [], 'tool_results': [], 'assessments': [],
            'activations': {'status': 'not_captured', 'scope': 'Original research inference'}}
        result = self.json_file(folder / 'result.json')
        if (identity and result.get('identity') == identity
                and result.get('source_request_sha256') == expected):
            metrics = {key: result.get(key) for key in ('seconds', 'generated_tokens', 'recorded_vectors')}
            metrics = {key: value for key, value in metrics.items()
                       if isinstance(value, (int, float)) and not isinstance(value, bool)
                       and math.isfinite(value) and value >= 0}
            if metrics:
                seconds = metrics.get('seconds')
                tokens = metrics.get('generated_tokens')
                if seconds and tokens is not None:
                    metrics['output_tokens_per_total_second'] = tokens / seconds
                metrics['scope'] = 'Prefill + decode including activation capture; not decode-only throughput'
                node['research_metrics'] = metrics
        capture = self.json_file(folder / 'activation-capture.json')
        source = capture.get('source') or {}
        if capture:
            valid = (capture.get('kind') == 'live_instrumented_inference' and capture.get('passed') is True
                     and source.get('research_id') == folder.name and source.get('request_sha256') == expected
                     and capture.get('model') == identity)
            if valid:
                node['activation_capture'] = capture
                node['activations'] = {'status': 'captured', 'scope': 'Measured during this original inference; not a replay'}
            else:
                node['activation_replay_status'] = {'status': 'error', 'error': 'Live capture provenance does not match this research request and model.'}
        return {'session': session, 'nodes': [node], 'edges': [], 'model_evidence': self.model(),
            'historical_model_evidence': identity, 'mlflow_url': record.get('mlflow_url'),
            'limitations': ['Activations were sampled during the recorded original research execution, not reconstructed from HTTP.',
                'Activation dimensions across models are not aligned semantic features; measurements alone do not establish causal explanations.']}

    def comparison_folders(self):
        if not self.comparison_directory.is_dir():
            return []
        return [p for p in self.comparison_directory.iterdir() if p.is_dir() and re.fullmatch(r'[a-f0-9]{32}', p.name)]

    def comparison_summary(self, folder, model):
        path = folder / model
        result = self.json_file(path / 'result.json')
        options = self.json_file(folder / 'comparison.json')
        run = self.json_file(folder / 'summary.json')
        identity = self.json_file(path / 'identity.json')
        turns = list(path.glob('turn-*/request.json')) or ([path / 'request.json'] if (path / 'request.json').is_file() else [])
        if not turns:
            return None
        review = self.json_file(folder / 'review.json')
        reviewed = not review.get('models') or model in review.get('models', [])
        status = review.get('status') if review and reviewed else result.get('status', 'running')
        label = identity.get('label') or identity.get('model_id') or model
        label = Path(label).name.removesuffix('.gguf')
        tool_steps = [step for step in result.get('steps', []) if step.get('tool_call_id')]
        updated = (path / 'result.json').stat().st_mtime if (path / 'result.json').is_file() else max(p.stat().st_mtime for p in turns)
        return {'id': f'comparison_{folder.name}_{model}', 'source': 'comparison', 'run_id': folder.name,
            'model': model, 'label': label, 'task': options.get('task', 'text'),
            'title': f'{label} · {options.get("task", "text")} · {folder.name[:8]}',
            'prompt': options.get('prompt'), 'status': status, 'review': review if reviewed else None,
            'started_at': (folder / 'comparison.json').stat().st_mtime if (folder / 'comparison.json').is_file() else min(p.stat().st_mtime for p in turns),
            'updated_at': updated, 'timestamp_source': 'artifact_mtime',
            'node_count': len(turns) + len(tool_steps), 'completion_count': len(turns), 'tool_count': len(tool_steps),
            'error_count': result.get('tool_errors', 0) + int(status not in ('completed', 'running')),
            'latest_output': result.get('content', ''), 'last_output': result.get('content', ''),
            'citation_audit': result.get('citation_audit'), 'experiment_id': result.get('experiment_id', run.get('experiment_id')),
            'trace_url': result.get('trace_url', run.get('trace_url')), 'mlflow_url': run.get('mlflow_url'),
            'trace_id': result.get('trace_id', run.get('trace_id'))}

    def comparison_spans(self, trace_id):
        if not trace_id:
            return []
        if trace_id not in self.comparison_trace_cache:
            try:
                self.comparison_trace_cache[trace_id] = self.recorder.mlflow.get_trace(trace_id).data.spans
            except Exception:
                return []
        return self.comparison_trace_cache[trace_id]

    def comparison_detail(self, sid):
        match = re.fullmatch(r'comparison_([a-f0-9]{32})_(bonsai|qwen)', sid)
        if not match:
            raise KeyError(sid)
        folder = self.comparison_directory / match.group(1)
        model = match.group(2)
        session = self.comparison_summary(folder, model)
        if session is None:
            raise KeyError(sid)
        path = folder / model
        identity = self.json_file(path / 'identity.json')
        result = self.json_file(path / 'result.json')
        trace_id = session.get('trace_id')
        spans = self.comparison_spans(trace_id)
        by_id = {s.span_id: s for s in spans}
        tool_spans = {s.attributes.get('tool_call_id'): s for s in spans if s.name.startswith(model + '.') and s.attributes.get('tool_call_id')}
        conversation = self.json_file(path / 'conversation.json', [])
        tool_results = {m.get('tool_call_id'): m for m in conversation if isinstance(m, dict) and m.get('role') == 'tool'}
        nodes, edges = [], []
        turn_folders = sorted([p for p in path.glob('turn-*') if re.fullmatch(r'turn-\d+', p.name)], key=lambda p: int(p.name[5:]))
        if not turn_folders and (path / 'request.json').is_file():
            turn_folders = [path]
        for turn_folder in turn_folders:
            if not (turn_folder / 'request.json').is_file():
                continue
            turn = int(turn_folder.name[5:]) if turn_folder != path else 1
            request = self.json_file(turn_folder / 'request.json')
            output = self.json_file(turn_folder / 'result.json')
            span = by_id.get(output.get('span_id'))
            if not output and (turn_folder / 'response.sse').is_file():
                from recording_ui import parse_response
                response = parse_response((turn_folder / 'response.sse').read_bytes(), 'text/event-stream')
            else:
                response = {'choices': [{'message': {key: output.get(key, [] if key == 'tool_calls' else '') for key in ('content', 'reasoning_content', 'tool_calls')},
                    'finish_reason': output.get('finish_reason')}], 'timings': output.get('timings'), 'usage': output.get('usage'), 'done_marker': output.get('done_marker')}
            inference_id = f'{sid}_turn_{turn}'
            complete = bool(output) and not output.get('error') and bool(output.get('done_marker'))
            node = {'id': inference_id, 'request_id': inference_id, 'source': 'comparison', 'kind': 'completion',
                'category': 'inference', 'generation_available': True, 'name': f'{model.capitalize()} inference · turn {turn}',
                'model': model, 'turn': turn, 'run_id': folder.name, 'trace_id': trace_id, 'span_id': output.get('span_id'),
                'trace_url': session.get('trace_url'), 'experiment_id': session.get('experiment_id'),
                'request': request, 'response': response,
                'settings': {key: value for key, value in request.items() if key not in ('messages', 'tools')},
                'server': identity.get('identity', identity), 'model_identity': identity,
                'timings': [output['timings']] if output.get('timings') else [],
                'usage': output.get('usage'), 'elapsed_ms': output.get('elapsed_ms'), 'complete': complete,
                'status': None, 'execution_status': 'error' if output.get('error') else 'completed' if complete else 'running',
                'error': output.get('error'), 'started_at': span.start_time_ns / 1e9 if span else (turn_folder / 'request.json').stat().st_mtime,
                'timestamp_source': 'mlflow_span' if span else 'artifact_mtime',
                'tool_calls': output.get('tool_calls', []),
                'tool_results': [m for m in request.get('messages', []) if m.get('role') == 'tool'],
                'preflight': self.json_file(turn_folder / 'preflight.json'),
                'citation_audit': self.json_file(turn_folder / 'citation-audit.json') or None,
                'activations': {'status': 'not_captured', 'scope': 'Original inference'}, 'assessments': []}
            nodes.append(node)
            for index, step in enumerate(result.get('steps', [])):
                call_id = step.get('tool_call_id')
                if step.get('turn') != turn or not call_id:
                    continue
                tool_span = tool_spans.get(call_id)
                stored = tool_results.get(call_id)
                actual_output = tool_span.outputs if tool_span else self.json_file_text(stored.get('content')) if stored else {'status': 'unavailable', 'reason': 'Full tool result not found; only recorded step metadata is available'}
                tool_id = f'{sid}_tool_{index}'
                tool_node = {'id': tool_id, 'request_id': tool_id, 'source': 'comparison', 'kind': 'tool', 'category': 'browser_tool',
                    'generation_available': False, 'name': f'{model.capitalize()} → {step.get("name", "browser tool")}',
                    'model': model, 'turn': turn, 'run_id': folder.name, 'trace_id': trace_id,
                    'span_id': tool_span.span_id if tool_span else None, 'trace_url': session.get('trace_url'), 'experiment_id': session.get('experiment_id'),
                    'request': tool_span.inputs if tool_span else {'name': step.get('name'), 'arguments': step.get('arguments'), 'tool_call_id': call_id},
                    'response': actual_output, 'settings': {}, 'server': identity.get('identity', identity), 'model_identity': identity,
                    'timings': [], 'elapsed_ms': (tool_span.end_time_ns - tool_span.start_time_ns) / 1e6 if tool_span and tool_span.end_time_ns else None,
                    'started_at': tool_span.start_time_ns / 1e9 if tool_span else (step.get('source') or {}).get('observed_at'),
                    'timestamp_source': 'mlflow_span' if tool_span else 'source_observation' if (step.get('source') or {}).get('observed_at') else 'unavailable',
                    'complete': step.get('status') in ('completed', 'error'), 'status': None, 'execution_status': step.get('status'),
                    'error': step.get('error'), 'tool_calls': [], 'tool_results': [], 'assessments': [], 'tool_call_id': call_id,
                    'scope': 'One executed browser wrapper; underlying MCP protocol artifacts are retained separately',
                    'span_availability': 'recorded' if tool_span else 'not_available'}
                nodes.append(tool_node)
                if any(call.get('id') == call_id for call in node['tool_calls']):
                    edges.append({'from': inference_id, 'to': tool_id, 'type': 'tool_call', 'label': 'Exact model tool-call ID: ' + call_id})
        for left, right in zip(nodes, nodes[1:]):
            edges.append({'from': left['id'], 'to': right['id'], 'type': 'sequence', 'label': 'Recorded model/step order'})
        pending = {}
        linked = set()
        for node in nodes:
            for item in node['tool_results']:
                call_id = item.get('tool_call_id')
                if call_id in pending and call_id not in linked:
                    edges.append({'from': pending[call_id], 'to': node['id'], 'type': 'tool_result', 'label': 'Returned tool result: ' + call_id})
                    linked.add(call_id)
            if node.get('tool_call_id'):
                pending[node['tool_call_id']] = node['id']
        self.attach_comparison_replay(folder, model, nodes, edges)
        session['node_count'] = len(nodes)
        session['instrumented_replay_count'] = sum(n.get('category') == 'instrumented_replay' for n in nodes)
        return {'session': session, 'nodes': nodes, 'edges': edges,
            'model_evidence': self.model(), 'historical_model_evidence': identity,
            'limitations': ['This is an actual comparison model trajectory, not a native chat or synthetic trace.',
                'Model weights/activation diagnostics in the global Model tab are separate from this historical model identity.',
                'MCP initialization is protocol setup and is not presented as a generation step.',
                'Tool wrapper spans can include more than one underlying BrowserOS HTTP call.',
                'Artifact timestamp fallbacks are labeled and are not measured request start times.'],
            'mlflow_url': session.get('mlflow_url') or (f'http://127.0.0.1:5210/#/experiments/{session["experiment_id"]}' if session.get('experiment_id') else None)}

    def attach_comparison_replay(self, folder, model, nodes, edges):
        attached = set()
        for node in list(nodes):
            if node.get('kind') != 'completion' or not node.get('turn'):
                continue
            turn_folder = folder / model / f"turn-{node['turn']}"
            request_path = turn_folder / 'request.json'
            raw = request_path.read_bytes() if request_path.is_file() else b''
            expected = hashlib.sha256(raw).hexdigest()
            node['request_sha256'] = expected
            result = self.json_file(turn_folder / 'result.json')
            live = result.get('activation_capture') or {}
            rid = live.get('research_id', '')
            if re.fullmatch(r'[a-f0-9]{32}', str(rid)):
                research_folder = self.research_directory / rid
                record = self.json_file(research_folder / 'research.json')
                research_request = self.json_file(research_folder / 'request.json')
                capture = self.json_file(research_folder / 'activation-capture.json')
                identity = record.get('model_identity') or {}
                provenance = result.get('identity', {}).get('identity', {}).get('checkpoint_provenance', {})
                content = ((record.get('response', {}).get('choices') or [{}])[0].get('message') or {}).get('content')
                source = capture.get('source') or {}
                valid = ((research_folder / 'request.json').is_file() and request_path.is_file()
                    and record.get('status') == 'completed' and research_request == self.json_file(request_path)
                    and content == result.get('content') and capture.get('generated_text') == content and capture.get('passed') is True
                    and capture.get('kind') == 'live_instrumented_inference' and source.get('research_id') == rid
                    and source.get('request_sha256') == hashlib.sha256((research_folder / 'request.json').read_bytes()).hexdigest()
                    and capture.get('model') == identity and identity.get('repo') == provenance.get('repo')
                    and identity.get('revision') == provenance.get('revision')
                    and identity.get('weight_dtype') == provenance.get('weight_dtype') == 'bfloat16'
                    and identity.get('quantized') is provenance.get('quantized') is False)
                if valid:
                    node['activation_capture'] = capture
                    node['activations'] = {'status':'captured','scope':'Measured during this original comparison inference'}
                    node['research_id'] = rid
                    continue
                node['activation_replay_status'] = {'status':'error','error':'Same-execution comparison capture failed request, output or checkpoint binding'}
                continue
            status = self.json_file(turn_folder / 'activation-replay-status.json')
            if status:
                identity = status.get('source') or status
                valid = identity.get('comparison_run_id') == folder.name and identity.get('model') == model and identity.get('turn') == node['turn'] and identity.get('request_sha256') == expected
                node['activation_replay_status'] = status if valid else {'status': 'error', 'error': 'Replay status identity does not match this recorded request.'}
            replay = self.json_file(turn_folder / 'activation-replay.json')
            if replay:
                before = len(nodes)
                self._attach_comparison_replay_manifest(folder, model, nodes, edges, replay)
                if len(nodes) > before:
                    attached.add(node['turn'])
                    node['activation_replay_status'] = {**status, 'status': 'completed'}
                else:
                    node['activation_replay_status'] = {'status': 'error', 'error': 'Replay provenance failed validation for this recorded request.'}
        if self.manifest:
            replay = self.json_file(self.manifest.parent / 'activation-diagnostic/replay-latest.json')
            if (replay.get('source') or {}).get('turn') not in attached:
                self._attach_comparison_replay_manifest(folder, model, nodes, edges, replay)

    def _attach_comparison_replay_manifest(self, folder, model, nodes, edges, replay):
        source = replay.get('source') or {}
        if replay.get('kind') != 'new_instrumented_real_request_replay' or not replay.get('passed') or source.get('comparison_run_id') != folder.name or source.get('model') != model:
            return
        turn = source.get('turn')
        if type(turn) is not int or turn < 1:
            return
        request_path = folder / model / f'turn-{turn}' / 'request.json'
        if not request_path.is_file() or hashlib.sha256(request_path.read_bytes()).hexdigest() != source.get('request_sha256'):
            return
        preflight = self.json_file(folder / model / f'turn-{turn}' / 'preflight.json')
        original_rendered = preflight.get('rendered_prompt')
        replay_rendered = replay.get('rendered_prompt')
        expected_rendered_hash = source.get('rendered_prompt_sha256')
        if not isinstance(original_rendered, str) or not isinstance(replay_rendered, str) or not expected_rendered_hash:
            return
        if any(hashlib.sha256(text.encode()).hexdigest() != expected_rendered_hash for text in (original_rendered, replay_rendered)):
            return
        original = next((n for n in nodes if n.get('kind') == 'completion' and n.get('turn') == turn), None)
        if original is None:
            return
        original['activation_replay'] = replay
        meta = replay.get('replay') or {}
        replay_id = original['id'] + '_instrumented_replay'
        node = {'id': replay_id, 'request_id': replay_id, 'source': 'instrumented_replay', 'kind': 'completion',
            'category': 'instrumented_replay', 'generation_available': True,
            'name': 'New instrumented replay of turn ' + str(turn), 'model': model, 'turn': turn,
            'run_id': meta.get('run_id'), 'trace_id': meta.get('trace_id'), 'experiment_id': meta.get('experiment_id'),
            'span_id': None, 'trace_url': f'http://127.0.0.1:5210/#/experiments/{meta["experiment_id"]}/traces?traceId={meta["trace_id"]}' if meta.get('experiment_id') and meta.get('trace_id') else None,
            'request': {'rendered_prompt': replay.get('rendered_prompt'), 'source': source, 'settings': replay.get('settings')},
            'response': {'choices': [{'message': {'content': replay.get('generated_text', '')}, 'finish_reason': None}], 'tokens': replay.get('tokens')},
            'server': {'model': replay.get('model'), 'runtime': replay.get('runtime')}, 'settings': replay.get('settings', {}),
            'timings': [], 'elapsed_ms': meta.get('elapsed_ms'), 'started_at': meta.get('started_at'),
            'timestamp_source': 'replay_manifest', 'status': None, 'execution_status': 'completed', 'complete': True,
            'tool_calls': [], 'tool_results': [], 'assessments': [], 'activation_replay': replay,
            'activations': {'status': 'captured', 'scope': 'This new instrumented replay only'},
            'scope': replay.get('relationship', 'New replay; not original inference activations')}
        nodes.append(node)
        edges.append({'from': original['id'], 'to': replay_id, 'type': 'replay_of',
                      'label': 'New instrumented replay of matching recorded request; not original activations'})

    def attach_native_replays(self, rows, nodes, edges):
        by_id = {node['id']: node for node in nodes}
        for row in rows:
            original = by_id.get(row.get('request_id'))
            if not original or row.get('kind') != 'completion':
                continue
            raw = self.read(row, 'request.bin')
            expected = hashlib.sha256(raw).hexdigest()
            original['source'] = 'native'
            original['request_sha256'] = expected
            original['activations'] = {'status': 'not_captured', 'scope': 'Original inference'}
            directory = row['_directory']
            status = self.json_file(directory / 'activation-replay-status.json')
            if status:
                identity = status.get('source') or status
                valid = identity.get('native_request_id', identity.get('request_id')) == original['id'] and identity.get('request_id', original['id']) == original['id'] and identity.get('request_sha256') == expected and identity.get('session') == row.get('session')
                original['activation_replay_status'] = status if valid else {'status': 'error', 'error': 'Replay status identity does not match this native request.'}
            replay = self.json_file(directory / 'activation-replay.json')
            if not replay:
                continue
            source = replay.get('source') or {}
            preflight = self.json_file(directory / 'activation-replay-preflight.json')
            rendered = preflight.get('rendered_prompt')
            replay_rendered = replay.get('rendered_prompt')
            rendered_hash = source.get('rendered_prompt_sha256')
            valid = (replay.get('kind') == 'new_instrumented_real_request_replay' and replay.get('passed') is True and
                     source.get('native_request_id', source.get('request_id')) == original['id'] and source.get('request_id', original['id']) == original['id'] and
                     source.get('request_sha256') == expected and source.get('session') == row.get('session') and
                     isinstance(rendered, str) and isinstance(replay_rendered, str) and rendered_hash and
                     all(hashlib.sha256(text.encode()).hexdigest() == rendered_hash for text in (rendered, replay_rendered)))
            if not valid:
                original['activation_replay_status'] = {'status': 'error', 'error': 'Replay request or rendered-context provenance failed validation.'}
                continue
            original['activation_replay'] = replay
            original['activation_replay_status'] = {**status, 'status': 'completed'}
            meta = replay.get('replay') or {}
            replay_id = original['id'] + '_instrumented_replay'
            nodes.append({'id': replay_id, 'request_id': replay_id, 'source': 'instrumented_replay',
                'kind': 'completion', 'category': 'instrumented_replay', 'generation_available': True,
                'name': 'Instrumented replay of native model turn', 'original_request_id': original['id'],
                'request_sha256': expected, 'session': row.get('session'),
                'trace_id': meta.get('trace_id'), 'run_id': meta.get('run_id'), 'experiment_id': meta.get('experiment_id'),
                'trace_url': f'http://127.0.0.1:5210/#/experiments/{meta["experiment_id"]}/traces?traceId={meta["trace_id"]}' if meta.get('experiment_id') and meta.get('trace_id') else None,
                'request': {'rendered_prompt': rendered, 'source': source, 'settings': replay.get('settings')},
                'response': {'choices': [{'message': {'content': replay.get('generated_text', '')}, 'finish_reason': None}], 'tokens': replay.get('tokens')},
                'server': {'model': replay.get('model'), 'runtime': replay.get('runtime')}, 'settings': replay.get('settings', {}),
                'timings': [], 'elapsed_ms': meta.get('elapsed_ms'), 'started_at': meta.get('started_at'),
                'timestamp_source': 'replay_manifest', 'status': None, 'execution_status': 'completed', 'complete': True,
                'tool_calls': [], 'tool_results': [], 'assessments': [], 'activation_replay': replay,
                'activation_replay_status': {'status': 'completed'},
                'activations': {'status': 'captured', 'scope': 'This instrumented replay only'}})
            edges.append({'from': original['id'], 'to': replay_id, 'type': 'replay_of',
                          'label': 'New instrumented replay of matching native request; not original activations'})

    @staticmethod
    def json_file_text(text):
        try:
            return json.loads(text)
        except (ValueError, TypeError):
            return {'content': text}

    def records(self):
        rows = []
        for path in self.recorder.directory.glob('*/exchange.json'):
            if not re.fullmatch(r'[a-f0-9]{32}', path.parent.name):
                continue
            try:
                row = json.loads(path.read_text())
                row['_directory'] = path.parent
                rows.append(row)
            except (OSError, ValueError):
                continue
        return sorted(rows, key=lambda r: r.get('started_at', 0))

    def read(self, row, filename):
        try:
            return (row['_directory'] / filename).read_bytes()
        except OSError:
            return b''

    def parsed(self, row):
        from recording_ui import parse_payload, parse_response
        values = (parse_payload(self.read(row, 'request.bin')),
                  parse_response(self.read(row, 'response.bin'), row.get('content_type', '')))
        return tuple(v if isinstance(v, dict) else {'malformed_payload': v} for v in values)

    def summary(self, sid, rows):
        title, output = '', ''
        semantic_errors = 0
        for row in rows:
            if row.get('kind') != 'completion':
                if row.get('complete') and row.get('status', 500) < 400:
                    semantic_errors += bool(tool_error(self.parsed(row)[1]))
                continue
            request, response = self.parsed(row)
            if title_generation(request):
                continue
            if not title:
                for message in request.get('messages', []):
                    if message.get('role') == 'user':
                        content = message.get('content', '')
                        if isinstance(content, list):
                            content = ' '.join(p.get('text', '') for p in content if isinstance(p, dict))
                        title = str(content)[:140]
                        break
            for choice in response.get('choices', []):
                content = choice.get('message', {}).get('content')
                if content and row.get('complete') and row.get('status', 500) < 400 and choice.get('finish_reason') == 'stop':
                    output = content
        # Background MCP reconnects must not promote an old conversation above
        # a newly generated answer. Preserve their timestamps on their nodes.
        activity = [r for r in rows if r.get('kind') == 'completion'] or rows
        return dict(id=sid, title=title or 'Unassigned exchanges', started_at=rows[0]['started_at'],
                    updated_at=activity[-1]['started_at'], last_exchange_at=rows[-1]['started_at'], node_count=len(rows),
                    completion_count=sum(r.get('kind') == 'completion' for r in rows),
                    tool_count=sum(r.get('kind') == 'mcp' for r in rows),
                    error_count=semantic_errors + sum(not r.get('complete') or r.get('status', 500) >= 400 for r in rows),
                    last_output=output, latest_output=output)

    def sessions(self):
        self.trace_cache.clear()
        groups = {}
        for row in self.records():
            groups.setdefault(row.get('session') or 'unassigned', []).append(row)
        self.comparison_trace_cache.clear()
        comparisons = [summary for folder in self.comparison_folders() for model in ('bonsai', 'qwen')
                       if (summary := self.comparison_summary(folder, model)) is not None]
        research = [summary for folder in self.research_directory.glob('*') if folder.is_dir() and re.fullmatch(r'[a-f0-9]{32}', folder.name)
                    if (summary := self.research_summary(folder)) is not None]
        return {'sessions': sorted([self.summary(s, r) for s, r in groups.items()] + comparisons + research,
                                   key=lambda r: r['updated_at'], reverse=True), 'limitations': LIMITATIONS}

    def trace_server(self, trace_id):
        if not trace_id:
            return {'status': 'unavailable'}
        if trace_id not in self.trace_cache:
            try:
                trace = self.recorder.mlflow.get_trace(trace_id)
                self.trace_cache[trace_id] = {
                    'server': trace.data.spans[0].attributes.get('bonsai.server', {}),
                    'assessments': [a.to_dictionary() for a in (trace.info.assessments or [])],
                }
            except Exception:
                return {'status': 'unavailable', 'reason': 'MLflow trace could not be read'}
        return self.trace_cache[trace_id]['server']

    def detail(self, sid):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', sid):
            raise ValueError('Invalid session ID')
        if sid.startswith('research_'):
            return self.research_detail(sid)
        if sid.startswith('comparison_'):
            return self.comparison_detail(sid)
        rows = [r for r in self.records() if (r.get('session') or 'unassigned') == sid]
        if not rows:
            raise KeyError(sid)
        nodes, edges = [], []
        for row in rows:
            request, response = self.parsed(row)
            calls = [c for choice in response.get('choices', []) for c in choice.get('message', {}).get('tool_calls', [])]
            timings = [e['timings'] for e in response.get('events', []) if isinstance(e, dict) and e.get('timings')]
            if response.get('timings'):
                timings.append(response['timings'])
            node = {k: v for k, v in row.items() if not k.startswith('_')}
            node.update(id=row['request_id'], request=request, response=response,
                        name='Model inference' if row.get('kind') == 'completion' else request.get('params', {}).get('name', request.get('method', 'MCP')),
                        settings={k: v for k, v in request.items() if k not in ('messages', 'tools')},
                        server=self.trace_server(row.get('trace_id')), timings=timings, tool_calls=calls,
                        tool_results=[m for m in request.get('messages', []) if m.get('role') == 'tool'])
            node['assessments'] = self.trace_cache.get(row.get('trace_id'), {}).get('assessments', [])
            node['generation_available'] = row.get('kind') == 'completion'
            node['category'] = 'inference' if row.get('kind') == 'completion' else 'browser_tool' if request.get('method') == 'tools/call' else 'protocol'
            if node['category'] == 'protocol':
                node['name'] = 'MCP protocol setup · ' + str(request.get('method', 'exchange'))
            node['trace_url'] = f'http://127.0.0.1:5210/#/experiments/3/traces?traceId={row["trace_id"]}' if row.get('trace_id') else None
            if row.get('kind') == 'completion':
                if calls:
                    node['name'] = 'Model → ' + ', '.join(c.get('function', {}).get('name', 'tool') for c in calls)
                elif any(c.get('finish_reason') == 'stop' and c.get('message', {}).get('content') for c in response.get('choices', [])):
                    node['name'] = 'Model answer'
                if title_generation(request):
                    node['name'] = 'Chat title generation'
                    node['auxiliary'] = True
                    node['category'] = 'title_generation'
            if row.get('kind') == 'mcp' and tool_error(response):
                node['error'] = node.get('error') or tool_error(response)
            if nodes:
                edges.append(dict(from_=nodes[-1]['id'], to=node['id'], type='sequence', label='Next recorded exchange'))
                edges[-1]['from'] = edges[-1].pop('from_')
            nodes.append(node)
        # Link only exact model-emitted IDs to the first subsequent request
        # carrying their tool result. MCP transport has its own JSON-RPC IDs;
        # those are deliberately not treated as model tool-call IDs.
        pending = {}
        linked = set()
        for node in nodes:
            for result in node['tool_results']:
                call_id = result.get('tool_call_id')
                if call_id in pending and call_id not in linked:
                    edges.append({'from': pending[call_id], 'to': node['id'],
                                  'type': 'tool_result', 'label': 'Tool result: ' + call_id})
                    linked.add(call_id)
            for call in node['tool_calls']:
                if call.get('id'):
                    pending[call['id']] = node['id']
        self.attach_native_replays(rows, nodes, edges)
        return {'session': self.summary(sid, rows), 'nodes': nodes, 'edges': edges,
                'model_evidence': self.model(), 'limitations': LIMITATIONS,
                'mlflow_url': 'http://127.0.0.1:5210/#/experiments/3'}

    def activation_vector(self, sid, node_id, step, layer):
        """Return one verified vector from the selected inference's attached replay."""
        detail = self.detail(sid)
        node = next((n for n in detail['nodes'] if n['id'] == node_id), None)
        replay = (node or {}).get('activation_capture') or (node or {}).get('activation_replay') or {}
        sample = next((s for s in replay.get('samples', []) if s.get('step') == step and s.get('layer') == layer), None)
        if not sample:
            raise KeyError('Measured vector unavailable')
        path = Path(sample['vector_file']).resolve()
        roots = [self.research_directory.resolve(), self.recorder.directory.resolve(), (self.recorder.directory.parent / 'comparison-records').resolve()]
        if self.manifest:
            roots.append((self.manifest.parent / 'activation-diagnostic').resolve())
        if not any(path.is_relative_to(root) for root in roots):
            raise ValueError('Vector outside capture storage')
        length = sample.get('vector_length')
        if not isinstance(length, int) or not 0 < length <= 65536 or path.stat().st_size != length * 4:
            raise ValueError('Invalid vector shape')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != sample.get('vector_sha256'):
            raise ValueError('Vector hash mismatch')
        values = struct.unpack('<' + str(length) + 'f', raw)
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Nonfinite vector')
        return {'node_id': node_id, 'step': step, 'layer': layer, 'values': values,
                'vector_sha256': sample['vector_sha256'], 'length': length,
                'scope': 'Measured residual stream during the original inference' if replay.get('kind') == 'live_instrumented_inference' else 'Measured residual stream of this separate instrumented replay'}

    def model(self):
        checkpoint = {'status': 'not_verified', 'explanation': 'Release verification has not yet been attached.'}
        if self.manifest and self.manifest.is_file():
            try:
                checkpoint = json.loads(self.manifest.read_text())
            except (OSError, ValueError):
                pass
        diagnostics = None
        activation_diagnostic = None
        if self.manifest:
            try:
                diagnostics = json.loads((self.manifest.parent / 'model-evidence-inventory.json').read_text())
            except (OSError, ValueError):
                pass
            try:
                activation_diagnostic = json.loads((self.manifest.parent / 'activation-diagnostic/latest.json').read_text())
            except (OSError, ValueError):
                pass
        return {'current_server': self.model_info, 'checkpoint': checkpoint, 'diagnostics': diagnostics,
                'activation_diagnostic': activation_diagnostic,
                'activations': {'status': 'not_captured', 'explanation': 'HTTP traces do not record layer activations. No activation capture is attached to these inference nodes.'},
                'limitations': LIMITATIONS}
