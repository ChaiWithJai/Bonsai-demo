"""Real native tool-call loops for bounded two-model public grant research."""
import json
import re
import time
from urllib.request import Request, urlopen
from browser_research import BrowserResearch


FINAL_STOPS = ['<tool_call>', '<function_call>', '</think>']


def citation_inventory(sources):
    rows = []
    seen = set()
    for source in sources:
        url = source.get('url')
        if not isinstance(url, str) or not url.startswith(('https://', 'http://')) or url in seen:
            continue
        seen.add(url)
        rows.append({'url': url, 'evidence_type': source.get('evidence_type'),
                     'url_provenance': source.get('url_provenance', 'recorded_source_url')})
    return rows


def audit_citations(content, sources):
    inventory = citation_inventory(sources)
    allowed = {row['url'] for row in inventory}
    opened = {row['url'] for row in inventory if row['evidence_type'] == 'opened_page'}
    markdown = re.findall(r'\[[^\]\n]+\]\(<?(https?://[^\s)>]+)>?\)', content)
    referenced = {url.rstrip('.,;!') for url in re.findall(r'https?://[^\s<>`\)\]]+', content)}
    matched = sorted(set(markdown) & allowed)
    unsupported = sorted(referenced - allowed)
    missing = not bool(set(markdown) & opened)
    return {'status': 'passed' if matched and not unsupported and not missing else 'failed',
        'matched_urls': matched, 'unsupported_urls': unsupported, 'missing_citations': missing,
        'opened_page_citations': sorted(set(markdown) & opened),
        'source_inventory': inventory,
        'scope': 'URL provenance only; not claim verification',
        'requirement': 'At least one inline markdown citation to a successfully opened/read source; every referenced URL must be in observed source inventory.'}


def citation_instruction(sources):
    inventory = citation_inventory(sources)
    return ('\nUse inline Markdown citations [source label](exact URL) next to the supported claims. '
            'Use at least one opened_page source citation. Search-page citations are discovery evidence only. '
            'Do not cite URLs merely seen as links but never opened/read. '
            'These are the exact source URLs successfully read in this trajectory; do not invent or shorten them:\n' +
            json.dumps(inventory, ensure_ascii=False))


def final_request(request):
    request.update(max_tokens=1024, tool_choice='none', stop=list(FINAL_STOPS))
    request.pop('tools', None)


def fit_request(api, model, request, budget):
    """Measure the rendered conversation, retaining raw tool evidence on disk."""
    compactions = []
    for cap in (None, 1800, 900, 400):
        if cap is not None:
            for message in request['messages']:
                if message.get('role') == 'tool':
                    try:
                        data = json.loads(message['content'])
                    except (ValueError, TypeError):
                        continue
                    if isinstance(data.get('content'), str) and len(data['content']) > cap:
                        data.update(content=data['content'][:cap], truncated=True,
                            context_note='Source text shortened to fit context; full response retained in browser artifacts.')
                        message['content'] = json.dumps(data)
                        compactions.append({'tool_call_id': message.get('tool_call_id'), 'content_characters': cap})
        rendered = api._post(api.endpoints[model], '/apply-template', request)['prompt']
        tokens = api._post(api.endpoints[model], '/tokenize', {'content': rendered, 'add_special': True, 'parse_special': True})['tokens']
        if not isinstance(tokens, list) or not all(type(t) is int for t in tokens):
            raise ValueError('Invalid tokenizer response')
        if len(tokens) + request['max_tokens'] <= budget:
            return {'prompt_tokens': len(tokens), 'context_budget': budget, 'reserved_output_tokens': request['max_tokens'],
                    'compactions': compactions, 'rendered_prompt': rendered}
    raise ValueError('Research conversation exceeds shared context even after explicit source truncation')


def stream_turn(api, model, request, folder, root, parent_id, send, cancel, turn):
    started = time.monotonic()
    (folder / 'request.json').write_text(json.dumps(request, indent=2))
    span = api.client.start_span(f'{model}.inference.{turn}', trace_id=root.trace_id, parent_id=parent_id,
        span_type='LLM', inputs=request)
    result = {'content': '', 'reasoning_content': '', 'tool_calls': [], 'finish_reason': None,
              'done_marker': False, 'timings': None, 'first_delta_ms': None, 'span_id': span.span_id}
    calls = {}
    status = 'ERROR'
    try:
        http = Request(api.endpoints[model].rstrip('/') + '/v1/chat/completions', data=json.dumps(request).encode(),
                       headers={'Content-Type': 'application/json', 'Accept': 'text/event-stream'})
        with urlopen(http, timeout=60) as response, (folder / 'response.sse').open('wb') as raw:
            for line in response:
                raw.write(line)
                if cancel.is_set():
                    raise InterruptedError('Comparison cancelled')
                if not line.startswith(b'data:') or not line[5:].strip():
                    continue
                if line[5:].strip() == b'[DONE]':
                    result['done_marker'] = True
                    break
                event = json.loads(line[5:])
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
                    fragment = {'model': model, 'turn': turn}
                    for field in ('content', 'reasoning_content'):
                        if isinstance(delta.get(field), str) and delta[field]:
                            result[field] += delta[field]
                            fragment[field] = delta[field]
                    for call in delta.get('tool_calls') or []:
                        index = call.get('index', 0)
                        target = calls.setdefault(index, {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                        if call.get('id'):
                            target['id'] = call['id']
                        for field in ('name', 'arguments'):
                            part = (call.get('function') or {}).get(field)
                            if isinstance(part, str):
                                target['function'][field] += part
                    if len(fragment) > 2:
                        if result['first_delta_ms'] is None:
                            result['first_delta_ms'] = (time.monotonic() - started) * 1000
                        send('delta', fragment)
        result['tool_calls'] = [calls[k] for k in sorted(calls)]
        if not result['done_marker'] or result['finish_reason'] not in ('stop', 'length', 'tool_calls'):
            raise RuntimeError('Incomplete inference stream')
        status = 'OK'
        return result
    except Exception as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)[:200]
        raise
    finally:
        result['elapsed_ms'] = (time.monotonic() - started) * 1000
        (folder / 'result.json').write_text(json.dumps(result, indent=2))
        api.client.end_span(root.trace_id, span.span_id, outputs=result, status=status)
        if status == 'OK':
            api.schedule_replay(model, folder, root.trace_id, turn)


def run_research(api, model, options, run_id, root, folder, send, cancel, eid, preflight):
    start = time.monotonic()
    result = {'model': model, 'task': 'grant_research', 'status': 'error', 'content': '', 'reasoning_content': '',
        'finish_reason': None, 'timings': None, 'time_to_first_token_ms': None, 'trace_id': root.trace_id,
        'experiment_id': eid, 'trace_url': f'http://127.0.0.1:5210/#/experiments/{eid}/traces?traceId={root.trace_id}',
        'tool_calls_count': 0, 'tool_errors': 0, 'sources': [], 'steps': [], 'inference_turns': 0,
        'independent_browser_session': True, 'isolation': 'Independent MCP session and newly owned tabs; shared signed-in browser profile, public-only tools'}
    path = folder / model
    path.mkdir(mode=0o700)
    identity = api._identity(model)
    result['identity'] = identity
    (path / 'identity.json').write_text(json.dumps(identity, indent=2))
    agent = api.client.start_span(f'{model}.grant-research', trace_id=root.trace_id, parent_id=root.span_id,
        span_type='AGENT', inputs=options, attributes={'comparison.server_identity': identity})
    result['span_id'] = agent.span_id
    browser_key = f'comparison_{run_id}_{model}'
    browser = BrowserResearch(path / 'browser', endpoint=api.browseros_url, browser_view=api.browser_view,
        session_key=browser_key, client_name=f'{model}-grant-research')
    request = api._request(identity['model_id'], options)
    messages = request['messages']
    budget = preflight.get(model, {}).get('shared_context_budget', 8192)
    send('model_started', {'model': model, 'model_id': identity['model_id'], 'identity': identity,
                          'task': 'grant_research', 'browser_session': browser_key})
    try:
        if not identity['available']:
            raise ValueError('Configured verified model unavailable')
        for turn in range(1, 8):
            if cancel.is_set():
                raise InterruptedError('Comparison cancelled')
            final = result['tool_calls_count'] >= 6 or turn == 7
            if final:
                messages.append({'role': 'user', 'content': 'The research tool budget is exhausted. Produce the final source-linked grant brief now in at most 350 words, focusing on one best lead and optionally one fallback, using only evidence already returned. Do not call tools, write tool-call markup, or promise future browsing. State missing evidence, historical deadlines, eligibility gaps and whether leads are construction grants, equipment/training support or compute credits. If evidence is insufficient, say so explicitly.' + citation_instruction(browser.sources)})
            request['messages'] = messages
            request['max_tokens'] = 1024 if final else options['max_tokens']
            request['tool_choice'] = 'none' if final else 'required' if turn == 1 else 'auto'
            if final:
                # Final synthesis has no executable tools. Stop before a model
                # starts another tool block or leaks a reasoning delimiter.
                final_request(request)
            turn_path = path / f'turn-{turn}'
            turn_path.mkdir(mode=0o700)
            measured = fit_request(api, model, request, budget)
            (turn_path / 'preflight.json').write_text(json.dumps(measured, indent=2))
            step = {'model': model, 'turn': turn, 'phase': 'final' if final else 'inference',
                    'message': 'Synthesize observed sources' if final else 'Model selects next research action', 'status': 'running'}
            result['steps'].append(step)
            send('step', dict(step))
            output = stream_turn(api, model, request, turn_path, root, agent.span_id, send, cancel, turn)
            step['status'] = 'completed'
            result['inference_turns'] += 1
            if result['time_to_first_token_ms'] is None and output['first_delta_ms'] is not None:
                result['time_to_first_token_ms'] = (time.monotonic() - start) * 1000 - output['elapsed_ms'] + output['first_delta_ms']
            calls = output['tool_calls']
            assistant = {'role': 'assistant', 'content': output['content']}
            if calls:
                assistant['tool_calls'] = calls
            messages.append(assistant)
            if not calls:
                if re.search(r'<\/?(?:tool_call|function_call|tool_response)\b', output['content'], re.I):
                    raise RuntimeError('Model emitted raw tool-call markup instead of a final research answer')
                result.update(content=output['content'], reasoning_content=output['reasoning_content'],
                    finish_reason=output['finish_reason'], timings=output['timings'], truncated=output['finish_reason'] == 'length')
                if result['tool_calls_count'] == 0:
                    raise RuntimeError('Model produced no browser calls; not a completed research trajectory')
                audit = audit_citations(output['content'], browser.sources)
                result['citation_audit'] = audit
                result['citation_repair_attempted'] = False
                (turn_path / 'citation-audit.json').write_text(json.dumps(audit, indent=2))
                if audit['status'] != 'passed' and any(source.get('evidence_type') == 'opened_page' for source in browser.sources):
                    # Exactly one additional native model turn, without new tools.
                    # The original answer and audit remain in their turn artifacts.
                    result['citation_repair_attempted'] = True
                    repair_turn = turn + 1
                    repair_path = path / f'turn-{repair_turn}'
                    repair_path.mkdir(mode=0o700)
                    messages.append({'role': 'user', 'content':
                        'Your draft failed its citation check. Rewrite the complete final brief in at most 350 words using the same observed evidence, with inline Markdown citations. Remove unsupported URLs and unsupported claims. Do not browse or call tools. Do not claim that citation repair verifies eligibility or factual accuracy. Citation check: ' +
                        json.dumps({'missing_citations': audit['missing_citations'], 'unsupported_urls': audit['unsupported_urls']}) + citation_instruction(browser.sources)})
                    final_request(request)
                    request['messages'] = messages
                    measured = fit_request(api, model, request, budget)
                    (repair_path / 'preflight.json').write_text(json.dumps(measured, indent=2))
                    repair_step = {'model': model, 'turn': repair_turn, 'phase': 'final', 'status': 'running',
                                   'message': 'One model-native citation repair using the same observed sources; no new tools'}
                    result['steps'].append(repair_step)
                    send('step', dict(repair_step))
                    repaired = stream_turn(api, model, request, repair_path, root, agent.span_id, send, cancel, repair_turn)
                    result['inference_turns'] += 1
                    repair_step['status'] = 'completed'
                    messages.append({'role': 'assistant', 'content': repaired['content']})
                    result.update(content=repaired['content'], reasoning_content=repaired['reasoning_content'],
                        finish_reason=repaired['finish_reason'], timings=repaired['timings'], truncated=repaired['finish_reason'] == 'length')
                    if repaired['tool_calls'] or re.search(r'<\/?(?:tool_call|function_call|tool_response)\b', repaired['content'], re.I):
                        raise RuntimeError('Citation repair emitted a tool call instead of a final answer')
                    audit = audit_citations(repaired['content'], browser.sources)
                    result['citation_audit'] = audit
                    (repair_path / 'citation-audit.json').write_text(json.dumps(audit, indent=2))
                if audit['status'] != 'passed':
                    raise RuntimeError('Final citation audit failed: missing opened-page citation or unsupported URLs; raw answer retained')
                result['status'] = 'completed'
                break
            if final:
                raise RuntimeError('Model emitted tools after final-answer tool budget was disabled')
            for call in calls:
                name = call.get('function', {}).get('name', '')
                call_id = call.get('id')
                if not call_id:
                    raise RuntimeError('Model emitted a tool call without an ID')
                if result['tool_calls_count'] >= 6:
                    messages.append({'role': 'tool', 'tool_call_id': call_id, 'content': json.dumps({'error': 'Research tool budget exhausted; synthesize available evidence.'})})
                    continue
                result['tool_calls_count'] += 1
                tool_step = {'model': model, 'turn': turn, 'tool_call_id': call_id, 'name': name, 'status': 'running'}
                result['steps'].append(tool_step)
                tool_span = api.client.start_span(f'{model}.{name}', trace_id=root.trace_id, parent_id=agent.span_id,
                    span_type='TOOL', inputs=call, attributes={'tool_call_id': call_id})
                tool_result = None
                try:
                    arguments = json.loads(call['function']['arguments'])
                    if not isinstance(arguments, dict):
                        raise ValueError('Tool arguments must be an object')
                    tool_step['arguments'] = arguments
                    send('tool_started', dict(tool_step))
                    tool_result = browser.call(name, arguments)
                    tool_step.update(status='completed', url=tool_result['url'], page_id=tool_result['page_id'],
                        source=tool_result['source'], content_excerpt=tool_result['content'][:300])
                    result['sources'] = list(browser.sources)
                except Exception as exc:
                    result['tool_errors'] += 1
                    tool_result = {'error': type(exc).__name__ + ': ' + str(exc)[:220]}
                    tool_step.update(status='error', error=tool_result['error'])
                finally:
                    api.client.end_span(root.trace_id, tool_span.span_id, outputs=tool_result,
                        status='OK' if tool_step['status'] == 'completed' else 'ERROR')
                send('tool_finished', dict(tool_step))
                messages.append({'role': 'tool', 'tool_call_id': call_id, 'content': json.dumps(tool_result)})
        if not result['content']:
            raise RuntimeError('No final research answer produced')
        if not browser.sources:
            raise RuntimeError('No browser source was successfully read; grant research remains unverified')
    except InterruptedError as exc:
        result.update(status='cancelled', error=str(exc))
    except Exception as exc:
        result.update(status='error', error=type(exc).__name__ + ': ' + str(exc)[:240])
    finally:
        result['elapsed_ms'] = (time.monotonic() - start) * 1000
        result['sources'] = list(browser.sources)
        result['evidence_status'] = 'opened_sources_require_eligibility_review' if any(s['evidence_type'] == 'opened_page' for s in browser.sources) else 'search_discovery_only' if browser.sources else 'no_sources'
        result['eligibility_verified'] = False
        result['latency_measurement'] = 'Whole research trajectory wall time; first text delta may precede tools. Final timings describe only the final inference.'
        (path / 'result.json').write_text(json.dumps(result, indent=2))
        (path / 'conversation.json').write_text(json.dumps(messages, indent=2))
        api.client.end_span(root.trace_id, agent.span_id, outputs=result, status='OK' if result['status'] == 'completed' else 'ERROR')
        api.client.log_metric(run_id, model + '.research_elapsed_ms', result['elapsed_ms'])
        api.client.log_metric(run_id, model + '.tool_calls_count', result['tool_calls_count'])
        api.client.log_metric(run_id, model + '.tool_errors', result['tool_errors'])
        send('model_finished', result)
    return result
