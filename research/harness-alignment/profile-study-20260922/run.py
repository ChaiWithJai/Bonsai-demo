"""Run the frozen development profile study against the existing local workspace.

No confirmation, manual correction, inference restart, or generation retry occurs.
A polling error keeps observing the same job. Reusing an output folder is rejected.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=False)
protocol=json.loads(Path(__file__).with_name('protocol.json').read_text())
fixtures=Path(__file__).parents[1]/'fixtures/desktop-regressions'
base='http://127.0.0.1:5257/api/workspace'
def save(name,value):
    (args.output/name).write_text(json.dumps(value,indent=2)+'\n')
def api(path='',body=None,headers=None):
    data=json.dumps(body).encode() if isinstance(body,dict) else body
    return json.load(urllib.request.urlopen(urllib.request.Request(base+path,data=data,headers=headers or {'Content-Type':'application/json'}),timeout=30))
state=api();assert not state['running_attempts'] and not state['running_source_jobs']
assert state['model_info']==protocol['model_info'],'Runtime metadata changed since protocol freeze'
save('protocol.json',protocol)
sources={}
for case in protocol['cases']:
    raw=(fixtures/case['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==case['sha256']
    source=api('/sources',raw,{'Content-Type':'application/octet-stream','X-Source-Filename':case['upload_name']})
    assert source['status']=='extracted';assert source['sha256']==case['sha256']
    sources[case['id']]=source
save('sources.json',sources)
results=[]
for ordinal,trial in enumerate(protocol['order']):
    case=next(c for c in protocol['cases'] if c['id']==trial['case'])
    state=api();assert not state['running_attempts'] and not state['running_source_jobs'],'Another task owns inference'
    assert state['model_info']==protocol['model_info'],'Runtime metadata changed during study'
    payload={'request':case['request'],'generation_config':{'profile':trial['profile'],'seed':trial['seed']}}
    save(f'{ordinal}-request.json',payload)
    job=api('/sources/'+sources[case['id']]['source_id']+'/generate',payload)
    save(f'{ordinal}-job.json',job)
    print(json.dumps({'trial':ordinal,**trial,'job_id':job['id'],'status':job['status']}),flush=True)
    while job['status'] in ('queued','running'):
        time.sleep(10)
        try:job=api('/source-jobs/'+job['id'])
        except Exception as exc:
            print(json.dumps({'trial':ordinal,'job_id':job['id'],'poll_error':str(exc),'action':'Keep observing this job; no retry'}),flush=True)
            continue
        save(f'{ordinal}-job.json',job)
        print(json.dumps({'trial':ordinal,'job_id':job['id'],'status':job['status'],'stage':job['stage']}),flush=True)
    results.append({'ordinal':ordinal,**trial,'job_id':job['id'],'run_id':job.get('run_id'),'status':job['status'],'elapsed_seconds':job.get('elapsed_seconds'),'error':job.get('error')})
    save('results.json',results)
print('Study finished; proposals remain unconfirmed.',flush=True)
