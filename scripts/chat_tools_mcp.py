"""Stateless MCP tools for the existing native New chat agent loop."""
import json


TOOLS = [
    {'name': 'calculate_bond', 'description': 'Calculate a regular coupon-date bond after reviewing the assumptions with the user. Rates are annual DECIMALS, not percentages. Returns deterministic cash flows, duration and a saved evidence link. No accrued interest or irregular coupons.',
     'inputSchema': {'type': 'object', 'additionalProperties': False,
                     'properties': {'face': {'type': 'number'}, 'coupon_rate': {'type': 'number'},
                                    'annual_yield': {'type': 'number'}, 'periods': {'type': 'integer'},
                                    'frequency': {'type': 'integer', 'enum': [1, 2, 4, 12]}},
                     'required': ['face', 'coupon_rate', 'annual_yield', 'periods', 'frequency']}},
    {'name': 'treasury_yields', 'description': 'Fetch the official daily Treasury par yield curve. Show observation date separately from retrieval time. Par yields are context, not spot rates or an executable quote. Does not change bond inputs.',
     'inputSchema': {'type': 'object', 'additionalProperties': False,
                     'properties': {'year': {'type': 'integer', 'minimum': 1990, 'maximum': 9999}}, 'required': ['year']}},
    {'name': 'jev_evidence_check', 'description': 'Send a selected claim and source text to Jev through Vercel AI Gateway for supported/conflicting/insufficient classification. This is a CLOUD call. Use only when the user requests cloud evaluation. The answer requires review and is not legal or investment approval.',
     'inputSchema': {'type': 'object', 'additionalProperties': False,
                     'properties': {'claim': {'type': 'string', 'maxLength': 8000},
                                    'evidence': {'type': 'string', 'maxLength': 80000}},
                     'required': ['claim', 'evidence']}}
]


for name, description, extra in [
    ('mayor_exercise', 'Get a synthetic bond exercise for a mayoral era. Confirm assumptions in chat, fetch Treasury context separately, then quiz the user without revealing the solution.', {}),
    ('grade_mayor_exercise', 'Check a USER-SUBMITTED numeric answer and its units for a mayor exercise. Do not call to reveal an answer before the user attempts it. Does not grade the reasoning.', {'answer': {'type': 'number'}, 'unit': {'type': 'string', 'enum': ['USD', 'years', 'USD/bp', 'years^2']}})
]:
    properties = {'era': {'type': 'string', 'enum': ['giuliani', 'bloomberg', 'de_blasio', 'adams', 'mamdani']}, **extra}
    TOOLS.append({'name': name, 'description': description, 'inputSchema': {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}})

TOOLS.append({'name': 'prepare_mayor_report', 'description': 'Prepare the five-mayor bond learning report: fetch dated official Treasury context for Giuliani, Bloomberg, de Blasio, Adams and Mamdani and return explicit synthetic exercise assumptions. Explain the evidence, then ask one exercise at a time without revealing answers. This retrieves data but does not capture a camera frame.', 'inputSchema': {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False}})


def call_tool(service, name, args):
    schemas = {tool['name']: tool['inputSchema'] for tool in TOOLS}
    if name not in schemas or not isinstance(args, dict) or set(args) != set(schemas[name]['required']):
        raise ValueError('Unknown tool or invalid arguments')
    if name == 'prepare_mayor_report':
        from mayor_bond_exercises import ERAS, exercise
        from treasury_insights_mcp import call as treasury_call
        rows = []
        for era in ERAS:
            task = exercise(era)
            rows.append({'exercise': task, 'treasury': treasury_call(service, 'get_curve', {'date': task['context_date']})})
        return {'content': [{'type': 'text', 'text': json.dumps({'eras': rows, 'review_status': 'unreviewed',
                'instructions': 'Create a concise report separating sourced Treasury observations from synthetic exercise inputs. Link sources. Ask only the first exercise and wait for the user answer.'}, allow_nan=False)}], 'isError': False}
    kind = 'financial_diligence' if name == 'jev_evidence_check' else 'bond_math'
    session = service.create(kind)
    if name in ('mayor_exercise', 'grade_mayor_exercise'):
        payload = {'operation': name, **args, 'actor': 'native_chat_tool'}
    elif name == 'calculate_bond':
        payload = {'operation': 'calculate_bond', 'inputs': args, 'confirmed': True,
                   'actor': 'native_chat_tool', 'confirmation_scope': 'model supplied inputs; not a human review label'}
    elif name == 'treasury_yields':
        payload = {'operation': 'fetch_treasury', 'year': args['year'], 'actor': 'native_chat_tool'}
    else:
        payload = {'operation': 'evaluate_evidence', **args, 'cloud_evaluation_requested': True,
                   'actor': 'native_chat_tool'}
    action = service.act(session['id'], payload)
    output = {k: action[k] for k in ('status', 'result', 'error', 'trace_error', 'mlflow_url') if k in action}
    output['saved_evidence_url'] = '/api/workspace/learning/'+session['id']
    if name == 'treasury_yields' and output.get('result'):
        result = dict(output['result'])
        result['observation_count'] = len(result.pop('observations'))
        output['result'] = result
    if name == 'calculate_bond' and output.get('result'):
        result = dict(output['result'])
        payments = result.pop('payments')
        result['payment_count'] = len(payments)
        result['payments_preview'] = payments if len(payments) <= 24 else payments[:12] + payments[-1:]
        result['preview_truncated'] = len(payments) > 24
        result['full_schedule_location'] = output['saved_evidence_url']
        output['result'] = result
    return {'content': [{'type': 'text', 'text': json.dumps(output, ensure_ascii=False, allow_nan=False)}],
            'isError': action['status'] != 'completed'}


def dispatch(service, request):
    if not isinstance(request, dict) or request.get('jsonrpc') != '2.0':
        return {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Invalid request'}}
    method, ident = request.get('method'), request.get('id')
    if 'id' not in request:
        return None
    try:
        if method == 'initialize':
            requested = request.get('params', {}).get('protocolVersion')
            version = requested if requested in ('2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25') else '2025-03-26'
            result = {'protocolVersion': version, 'capabilities': {'tools': {}},
                      'serverInfo': {'name': 'Bonsai chat tools', 'version': '1.0.0'},
                      'instructions': 'Use tools inside this conversation. Show the inputs and evidence. Tool results are not human approval.'}
        elif method == 'ping':
            result = {}
        elif method == 'tools/list':
            result = {'tools': TOOLS}
        elif method == 'tools/call':
            params = request.get('params', {})
            try:
                result = call_tool(service, params.get('name'), params.get('arguments', {}))
            except (ValueError, TypeError, KeyError) as exc:
                result = {'content': [{'type': 'text', 'text': str(exc)}], 'isError': True}
        else:
            return {'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32601, 'message': 'Method not found'}}
        return {'jsonrpc': '2.0', 'id': ident, 'result': result}
    except Exception:
        return {'jsonrpc': '2.0', 'id': ident, 'error': {'code': -32603, 'message': 'Chat tool service failed'}}
