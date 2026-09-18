"""Bounded, recorded comparisons of two configured local inference servers."""
import concurrent.futures
import hashlib
import json
import math
import re
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError

LIMITATIONS = [
    'Same prompt, shared project context and requested settings. Text and public browser research are separate task types.',
    'Sequential is the default. Concurrent runs contend for the shared GPU.',
    'Sequential timing still includes other system workloads; production context pools and slots differ.',
    'One sample is not a benchmark or a quality ranking; cache and quantization differ.',
    'Reasoning text is generated output, not internal activation evidence.',
    'First-text-delta latency measures arrival of the first nonempty content or reasoning fragment, not a physical token timestamp.',
]


class ComparisonBusy(RuntimeError):
    pass


class ComparisonAPI:
    def __init__(self, tracking_uri, records_dir, endpoints=None, client=None, browseros_url='http://127.0.0.1:19010/mcp', browser_view=None, replay_worker=None):
        self.endpoints = endpoints or {'bonsai': 'http://127.0.0.1:8081', 'qwen': 'http://127.0.0.1:8082'}
        if set(self.endpoints) != {'bonsai', 'qwen'}:
            raise ValueError('Exactly bonsai and qwen endpoints are required')
        for endpoint in self.endpoints.values():
            url = urlsplit(endpoint)
            if url.scheme != 'http' or url.hostname not in ('localhost', '127.0.0.1', '::1') or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
                raise ValueError('Comparison endpoints must be configured localhost HTTP origins')
        self.directory = Path(records_dir).resolve()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if client is None:
            import mlflow
            from mlflow import MlflowClient
            # Span export uses MLflow's process tracking URI even with an explicit
            # client. This is the recorder's same URI; do not change its experiment.
            mlflow.set_tracking_uri(tracking_uri)
            client = MlflowClient(tracking_uri=tracking_uri)
        self.client = client
        self.run_lock = threading.Lock()
        self.browseros_url = browseros_url
        self.browser_view = browser_view
        self.replay_worker = replay_worker

    def schedule_replay(self, model, turn_path, trace_id, turn):
        """Queue a separate capture from persisted inference evidence, never block on it."""
        turn_path = Path(turn_path)
        state = {'status': 'unavailable', 'message': 'Activation replay worker is not configured'}
        try:
            output = json.loads((turn_path / 'result.json').read_text())
            if not output.get('done_marker') or output.get('error') or output.get('finish_reason') not in ('stop', 'length', 'tool_calls'):
                return None
            if self.replay_worker is not None:
                rendered = json.loads((turn_path / 'preflight.json').read_text())['rendered_prompt']
                source = {'comparison_run_id': turn_path.parent.parent.name, 'model': model, 'turn': turn,
                          'request_sha256': hashlib.sha256((turn_path / 'request.json').read_bytes()).hexdigest(),
                          'rendered_prompt_sha256': hashlib.sha256(rendered.encode()).hexdigest(),
                          'trace_id': trace_id, 'span_id': output.get('span_id')}
                self.replay_worker.enqueue_comparison(turn_path, model, source)
                # The worker owns the live status; it may already be running.
                return {'status_path': str(turn_path / 'activation-replay-status.json'), 'source': source}
        except Exception as exc:
            state = {'status': 'error', 'error': 'Replay scheduling failed: ' + str(exc)[:300]}
        state['updated_at'] = time.time()
        (turn_path / 'activation-replay-status.json').write_text(json.dumps(state, indent=2))
        return state

    def _get(self, endpoint, path):
        with urlopen(endpoint.rstrip('/') + path, timeout=3) as response:
            return json.load(response)

    def _post(self, endpoint, path, payload):
        request = Request(endpoint.rstrip('/') + path, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=10) as response:
            return json.load(response)

    def _identity(self, model):
        endpoint = self.endpoints[model]
        row = {'id': model, 'label': model.capitalize(), 'endpoint': endpoint, 'available': False, 'model_id': None, 'identity': {}}
        try:
            health = self._get(endpoint, '/health')
            models = self._get(endpoint, '/v1/models')
            props = self._get(endpoint, '/props')
            data = models.get('data') or []
            row['model_id'] = data[0].get('id') if data else None
            row['identity'] = {key: props[key] for key in ('model_path', 'build_info', 'default_generation_settings', 'model_alias', 'model_size', 'n_ctx_train', 'total_slots') if key in props}
            row['identity']['models_response'] = models
            row['available'] = health.get('status') == 'ok' and bool(row['model_id'])
            if row['model_id']:
                row['label'] = Path(row['model_id']).name.removesuffix('.gguf')
            model_path = props.get('model_path', '')
            match = re.search(r'(PQ2_0|IQ2_XXS)', model_path)
            row['quantization'] = match.group(1) if match else 'Unverified'
            manifest_path = Path(__file__).resolve().parents[1] / '.cache/bonsai' / ('release-manifest.json' if model == 'bonsai' else 'qwen38-manifest.json')
            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_text())
                checkpoint = manifest.get('checkpoint', {})
                files = checkpoint.get('files') or [checkpoint]
                matches = [f for f in files if f.get('verified') is True and re.fullmatch(r'[a-f0-9]{64}', str(f.get('sha256', ''))) and f.get('path') and model_path and Path(f['path']).resolve() == Path(model_path).resolve()]
                expected = checkpoint.get('repo') == 'prism-ml/Ternary-Bonsai-2-27B-gguf' if model == 'bonsai' else checkpoint.get('base_model') == 'Qwen/Qwen3.8-27B'
                if matches and expected:
                    row['identity']['checkpoint_provenance'] = {'repo': checkpoint.get('repo'), 'revision': checkpoint.get('revision'), 'file': matches[0],
                        'binding': 'Current /props model path matches previously SHA-verified manifest; hash not recalculated per request'}
            if 'checkpoint_provenance' not in row['identity']:
                row.update(available=False, error='Loaded model lacks matching verified expected-checkpoint provenance')
        except Exception as exc:
            row['error'] = type(exc).__name__ + ': local inference server unavailable'
        return row

    def status(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            models = list(pool.map(self._identity, self.endpoints))
        recent = []
        for path in sorted(self.directory.glob('*/summary.json'), key=lambda p: p.stat().st_mtime, reverse=True):
            if not re.fullmatch(r'[a-f0-9]{32}', path.parent.name):
                continue
            try:
                saved = json.loads(path.read_text())
                review_path = path.parent / 'review.json'
                if review_path.is_file():
                    review = json.loads(review_path.read_text())
                    saved['review'] = review
                    saved['status'] = review.get('status', saved.get('status'))
                    for result in saved.get('results', []):
                        if result.get('model') in review.get('models', []):
                            result.update(status=review.get('status', 'reviewed'), error=review.get('error'))
                recent.append(saved)
            except (OSError, ValueError):
                continue
            if len(recent) >= 5:
                break
        return {'models': models, 'modes': ['sequential', 'concurrent'], 'default_mode': 'sequential',
            'tasks': ['text', 'grant_research'],
            'limits': {'max_tokens': 512, 'thinking_budget_tokens': 128, 'prompt_characters': 12000, 'research_tool_calls': 6, 'research_final_tokens': 1024},
            'busy': self.run_lock.locked(), 'recent_runs': recent, 'limitations': LIMITATIONS}

    @staticmethod
    def validate(body):
        if not isinstance(body, dict):
            raise ValueError('Request must be an object')
        allowed = {'prompt', 'mode', 'temperature', 'max_tokens', 'thinking_budget_tokens', 'task', 'project_context'}
        if set(body) - allowed:
            raise ValueError('Unsupported comparison setting')
        prompt = body.get('prompt')
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12000:
            raise ValueError('Prompt must contain 1–12000 characters')
        mode = body.get('mode', 'sequential')
        if mode not in ('sequential', 'concurrent'):
            raise ValueError('Unknown comparison mode')
        maximum = body.get('max_tokens', 512)
        thinking = body.get('thinking_budget_tokens', 0)
        temp = body.get('temperature', 0.3)
        if type(maximum) is not int or not 1 <= maximum <= 512:
            raise ValueError('max_tokens must be between 1 and 512')
        if type(thinking) is not int or not 0 <= thinking <= 128:
            raise ValueError('thinking_budget_tokens must be between 0 and 128')
        if type(temp) not in (int, float) or not math.isfinite(temp) or not 0 <= temp <= 2:
            raise ValueError('temperature must be between 0 and 2')
        task = body.get('task', 'text')
        if task not in ('text', 'grant_research'):
            raise ValueError('Unknown comparison task')
        context = body.get('project_context', '')
        if not isinstance(context, str) or len(context) > 4000:
            raise ValueError('Project context must be at most 4000 characters')
        return {'prompt': prompt, 'mode': mode, 'temperature': temp, 'task': task, 'project_context': context,
                'max_tokens': maximum, 'thinking_budget_tokens': thinking}

    def _experiment(self):
        experiment = self.client.get_experiment_by_name('bonsai-local-comparisons')
        return experiment.experiment_id if experiment else self.client.create_experiment('bonsai-local-comparisons')

    def preflight(self, options):
        """Render/tokenize both exact model requests before either can generate."""
        checked = {}
        for model, endpoint in self.endpoints.items():
            identity = self._identity(model)
            if not identity['available']:
                raise ValueError(model + ': configured verified model is unavailable')
            settings = identity['identity'].get('default_generation_settings', {})
            context = settings.get('n_ctx')
            slots = identity['identity'].get('total_slots', 1)
            if type(context) is not int or context < 1 or type(slots) is not int or slots < 1:
                raise ValueError(model + ': context capacity could not be verified')
            # Conservatively reserve one equal share of the configured context pool.
            budget = context // slots
            request = self._request(identity['model_id'], options)
            try:
                rendered = self._post(endpoint, '/apply-template', request)['prompt']
                tokens = self._post(endpoint, '/tokenize', {'content': rendered, 'add_special': True, 'parse_special': True})['tokens']
                if not isinstance(tokens, list) or not all(type(token) is int for token in tokens):
                    raise ValueError('Invalid token response')
            except Exception as exc:
                raise ValueError(model + ': prompt token preflight unavailable; no inference started') from exc
            checked[model] = {'identity': identity, 'rendered_prompt': rendered, 'prompt_tokens': len(tokens),
                'context_budget': budget, 'configured_context': context, 'slots': slots,
                'reserved_output_tokens': options['max_tokens']}
        shared_budget = min(row['context_budget'] for row in checked.values())
        for model, row in checked.items():
            row['shared_context_budget'] = shared_budget
            if row['prompt_tokens'] + options['max_tokens'] > shared_budget:
                raise ValueError(f'{model}: rendered prompt ({row["prompt_tokens"]} tokens) plus output budget exceeds shared context {shared_budget}; no inference started')
        return checked

    @staticmethod
    def _request(model_id, options):
        request = {'model': model_id, 'messages': [{'role': 'user', 'content': options['prompt']}],
            'stream': True, 'stream_options': {'include_usage': True},
            'temperature': options['temperature'], 'top_p': 0.95, 'top_k': 20, 'min_p': 0,
            'seed': 42, 'cache_prompt': False, 'repeat_penalty': 1.0,
            'max_tokens': options['max_tokens'], 'thinking_budget_tokens': options['thinking_budget_tokens'],
            'chat_template_kwargs': {'enable_thinking': options['thinking_budget_tokens'] > 0}}
        if options.get('task') == 'grant_research':
            from browser_research import TOOLS, research_messages
            request.update(messages=research_messages(options), tools=TOOLS, tool_choice='auto')
        return request

    def run(self, body, emit, cancel_event=None):
        options = self.validate(body)
        if not self.run_lock.acquire(blocking=False):
            raise ComparisonBusy('Another comparison is running')
        cancel = cancel_event or threading.Event()
        emit_lock = threading.Lock()
        def send(event, data):
            with emit_lock:
                if cancel.is_set():
                    return
                try:
                    emit(event, data)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    cancel.set()
        run_id = root = None
        results = []
        try:
            eid = self._experiment()
            run = self.client.create_run(eid, tags={'mlflow.runName': 'Local comparison · ' + options['mode'],
                'comparison.scope': options['task'], 'comparison.contention': str(options['mode'] == 'concurrent').lower()})
            run_id = run.info.run_id
            folder = self.directory / run_id
            folder.mkdir(mode=0o700)
            (folder / 'comparison.json').write_text(json.dumps(options, indent=2))
            for key, value in options.items():
                if key not in ('prompt', 'project_context'):
                    self.client.log_param(run_id, key, value)
            for key, value in {'seed': 42, 'cache_prompt': False, 'top_p': 0.95,
                               'top_k': 20, 'min_p': 0, 'repeat_penalty': 1.0}.items():
                self.client.log_param(run_id, key, value)
            url = f'http://127.0.0.1:5210/#/experiments/{eid}/runs/{run_id}'
            root = self.client.start_trace('local-model-comparison', span_type='CHAIN', inputs=options,
                experiment_id=eid, run_id=run_id, attributes={'comparison.limitations': LIMITATIONS})
            send('run_started', {'run_id': run_id, 'mode': options['mode'], 'settings': options, 'mlflow_url': url})
            preflight = {} if cancel.is_set() else self.preflight(options)
            (folder / 'preflight.json').write_text(json.dumps(preflight, indent=2))
            def execute(model):
                if options['task'] == 'grant_research':
                    from grant_research import run_research
                    return run_research(self, model, options, run_id, root, folder, send, cancel, eid, preflight)
                return self._model(model, options, run_id, root, folder, send, cancel, eid, preflight.get(model))
            if options['mode'] == 'concurrent':
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(execute, self.endpoints))
            else:
                for model in self.endpoints:
                    results.append(execute(model))
            state = 'cancelled' if cancel.is_set() else 'completed' if all(r['status'] == 'completed' for r in results) else 'error'
            summary = {'run_id': run_id, 'status': state, 'mode': options['mode'], 'settings': options, 'results': results,
                       'mlflow_url': url, 'contention': options['mode'] == 'concurrent', 'limitations': LIMITATIONS,
                       'trace_id': root.trace_id, 'experiment_id': eid,
                       'trace_url': f'http://127.0.0.1:5210/#/experiments/{eid}/traces?traceId={root.trace_id}'}
            (folder / 'summary.json').write_text(json.dumps(summary, indent=2))
            self.client.log_artifacts(run_id, str(folder), 'comparison')
            self.client.end_trace(root.trace_id, outputs=summary, status='OK' if state == 'completed' else 'ERROR')
            root = None
            self.client.set_terminated(run_id, status='FINISHED' if state == 'completed' else 'KILLED' if state == 'cancelled' else 'FAILED')
            send('run_finished', summary)
            return summary
        except Exception as exc:
            if run_id:
                (folder / 'failure.json').write_text(json.dumps({'error': str(exc), 'type': type(exc).__name__}, indent=2))
                self.client.log_artifacts(run_id, str(folder), 'comparison')
            if root:
                self.client.end_trace(root.trace_id, status='ERROR')
            if run_id:
                self.client.set_terminated(run_id, status='FAILED')
            raise
        finally:
            self.run_lock.release()

    def _model(self, model, options, run_id, root, folder, send, cancel, eid, preflight=None):
        started = time.monotonic()
        result = {'model': model, 'status': 'error', 'content': '', 'reasoning_content': '',
            'finish_reason': None, 'timings': None, 'elapsed_ms': None,
            'time_to_first_token_ms': None, 'trace_id': root.trace_id, 'experiment_id': eid,
            'trace_url': f'http://127.0.0.1:5210/#/experiments/{eid}/traces?traceId={root.trace_id}'}
        identity = self._identity(model)
        result['identity'] = identity
        request = self._request(identity['model_id'], options)
        result['latency_measurement'] = 'Client-observed first nonempty content/reasoning SSE delta, not physical token timing'
        path = folder / model
        path.mkdir(mode=0o700)
        (path / 'request.json').write_text(json.dumps(request, indent=2))
        (path / 'identity.json').write_text(json.dumps(identity, indent=2))
        span = self.client.start_span('comparison.' + model, trace_id=root.trace_id, parent_id=root.span_id,
            span_type='LLM', inputs=request, attributes={'comparison.server_identity': identity})
        result['span_id'] = span.span_id
        send('model_started', {'model': model, 'model_id': identity['model_id'], 'identity': identity})
        done = False
        try:
            if cancel.is_set():
                result['status'] = 'cancelled'
                return result
            if not identity['available']:
                raise RuntimeError('Configured local model is unavailable')
            started = time.monotonic()
            http = Request(self.endpoints[model].rstrip('/') + '/v1/chat/completions',
                data=json.dumps(request).encode(), headers={'Content-Type': 'application/json', 'Accept': 'text/event-stream'})
            # Socket timeout bounds stalled prefill/read; max_tokens bounds generation.
            with urlopen(http, timeout=60) as response, (path / 'response.sse').open('wb') as raw:
                for line in response:
                    raw.write(line)
                    if cancel.is_set():
                        result['status'] = 'cancelled'
                        break
                    if not line.startswith(b'data:'):
                        continue
                    payload = line[5:].strip()
                    if payload == b'[DONE]':
                        done = True
                        break
                    if not payload:
                        continue
                    event = json.loads(payload)
                    if event.get('error'):
                        raise RuntimeError('Inference server returned an error')
                    if event.get('timings'):
                        result['timings'] = event['timings']
                    if event.get('usage'):
                        result['usage'] = event['usage']
                    for choice in event.get('choices', []):
                        if choice.get('finish_reason'):
                            result['finish_reason'] = choice['finish_reason']
                        delta = choice.get('delta') or {}
                        fragment = {'model': model}
                        for field in ('content', 'reasoning_content'):
                            if isinstance(delta.get(field), str) and delta[field]:
                                result[field] += delta[field]
                                fragment[field] = delta[field]
                        if len(fragment) > 1:
                            if result['time_to_first_token_ms'] is None:
                                result['time_to_first_token_ms'] = (time.monotonic() - started) * 1000
                            send('delta', fragment)
                if result['status'] != 'cancelled':
                    if not done or result['finish_reason'] not in ('stop', 'length'):
                        raise RuntimeError('Incomplete inference stream')
                    result['status'] = 'completed'
                    result['truncated'] = result['finish_reason'] == 'length'
        except HTTPError as exc:
            (path / 'response-error.bin').write_bytes(exc.read(1024 * 1024))
            result['error'] = f'HTTP {exc.code}: inference server rejected the request'
        except Exception as exc:
            result['error'] = type(exc).__name__ + ': ' + str(exc)[:200]
        finally:
            result['elapsed_ms'] = (time.monotonic() - started) * 1000
            result['done_marker'] = done
            (path / 'result.json').write_text(json.dumps(result, indent=2))
            self.client.end_span(root.trace_id, span.span_id, outputs=result,
                status='OK' if result['status'] == 'completed' else 'ERROR')
            if result['status'] == 'completed':
                replay_path = path / 'turn-1'
                replay_path.mkdir(mode=0o700)
                for filename in ('request.json', 'result.json'):
                    (replay_path / filename).write_bytes((path / filename).read_bytes())
                (replay_path / 'preflight.json').write_text(json.dumps(preflight or {}, indent=2))
                self.schedule_replay(model, replay_path, root.trace_id, 1)
            self.client.log_metric(run_id, model + '.elapsed_ms', result['elapsed_ms'])
            if result['time_to_first_token_ms'] is not None:
                self.client.log_metric(run_id, model + '.time_to_first_token_ms', result['time_to_first_token_ms'])
            for key, value in (result.get('timings') or {}).items():
                if type(value) in (int, float) and math.isfinite(value):
                    self.client.log_metric(run_id, model + '.server.' + key, value)
            send('model_finished', result)
        return result
