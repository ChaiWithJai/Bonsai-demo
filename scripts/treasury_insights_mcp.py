"""Dated Treasury context, isolated from camera tools and bond assumptions."""
import datetime as dt
import json
import re
from gb10_vision_mcp import schema

TOOLS = [schema('get_curve', 'Official Treasury par curve on an EXACT date. Non-trading dates return no observation; never silently substitute another date. Rates are percent, not decimals or municipal yields.', {'date': {'type': 'string'}}),
         schema('get_rate_history', 'Official daily Treasury par yields for one tenor over a bounded interval (at most 366 days). Null rates stay missing. Every source retrieval is saved in the harness and MLflow.', {'start': {'type': 'string'}, 'end': {'type': 'string'}, 'tenor': {'type': 'string', 'description': 'Treasury field such as BC_10YEAR'}})]


def call(service, name, args):
    if name not in [t['name'] for t in TOOLS] or not isinstance(args, dict):
        raise ValueError('Unknown Treasury tool')
    required = {'date'} if name == 'get_curve' else {'start', 'end', 'tenor'}
    if set(args) != required:
        raise ValueError('Invalid Treasury arguments')
    start = dt.date.fromisoformat(args['date'] if name == 'get_curve' else args['start'])
    end = start if name == 'get_curve' else dt.date.fromisoformat(args['end'])
    if start.year<1990 or end<start or (end-start).days>366 or end>dt.datetime.now(dt.timezone.utc).date():
        raise ValueError('Use an ordered historical interval of at most 366 days, from 1990 onward')
    tenor = args.get('tenor')
    if tenor is not None and (not isinstance(tenor, str) or not re.fullmatch(r'BC_\d+(YEAR|MONTH)', tenor)):
        raise ValueError('Invalid tenor')
    observations, sources = [], []
    for year in range(start.year,end.year+1):
        session = service.create('bond_math')
        action = service.act(session['id'], {'operation': 'fetch_treasury', 'year': year, 'actor': 'treasury_mcp'})
        if action['status'] != 'completed':
            raise ValueError(action.get('error', 'Treasury fetch failed'))
        result = action['result']
        sources.append({**{k: result[k] for k in ('source_url','fetched_at','sha256')},
                        'mlflow_url': action.get('mlflow_url'),
                        'saved_evidence_url': '/api/workspace/learning/'+session['id']})
        for row in result['observations']:
            if start.isoformat() <= row['observation_date'] <= end.isoformat():
                if tenor and tenor not in row['yields_percent']:
                    raise ValueError('Tenor absent in source observations')
                observations.append(row if not tenor else {'observation_date': row['observation_date'], 'yield_percent': row['yields_percent'][tenor]})
    return {'observations': observations, 'sources': sources, 'rate_unit': 'percent',
            'status': 'observed' if observations else 'no_observation_on_requested_dates',
            'usage': 'Treasury par yields only; not municipal yields, spot rates, or evidence of mayoral causation'}


def dispatch(service, request):
    if not isinstance(request,dict) or request.get('jsonrpc')!='2.0':
        return {'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid request'}}
    if 'id' not in request: return None
    method=request.get('method')
    if method=='initialize':
        result={'protocolVersion':'2025-03-26','capabilities':{'tools':{}},'serverInfo':{'name':'Treasury Insights','version':'1.0.0'}}
    elif method=='ping': result={}
    elif method=='tools/list': result={'tools':TOOLS}
    elif method=='tools/call':
        try:
            p=request.get('params',{})
            value=call(service,p.get('name'),p.get('arguments',{}))
            result={'content':[{'type':'text','text':json.dumps(value,allow_nan=False)}],'isError':False}
        except (ValueError,TypeError,KeyError) as exc:
            result={'content':[{'type':'text','text':str(exc)}],'isError':True}
    else: return {'jsonrpc':'2.0','id':request['id'],'error':{'code':-32601,'message':'Method not found'}}
    return {'jsonrpc':'2.0','id':request['id'],'result':result}
