"""Frozen development edit from a preserved failed selection-state audit."""
import hashlib
import json
from pathlib import Path
import time
import urllib.request
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'.cache/selection-repair'
if OUT.exists():raise SystemExit('Preserve the existing attempt directory')
OUT.mkdir()
def api(path='',body=None):
 req=urllib.request.Request('http://127.0.0.1:5257/api/workspace'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
def save(name,data):(OUT/name).write_text(json.dumps(data,indent=2))
status=api();assert not status['running_attempts'] and not status['running_source_jobs']
source=api('/7eda27addd6943ebb127bea7dc852da9');save('source.json',source);save('runtime.json',status)
checks=json.loads((ROOT/'.cache/pressed-gate-audit/contract.json').read_text())
checks.insert(1,{'target':{'test_id':'record-row'},'action':'count','value':1})
checks.append({'target':{'test_id':'record-row'},'action':'count','value':3})
request='Make the record-type filter buttons expose their current selection to assistive technology using aria-pressed true or false. Exactly one of All records, Measured observations and Spoken requirements should be selected. Clear filters must select All records again. Preserve filtering, search, source links, original values and note saving. Read the current file and make a focused edit.'
files=['scripts/workspace_acceptance.py','scripts/workspace-tools/check_request.mjs','scripts/workspace_worker.py','scripts/workspace_provider.py']
save('protocol.json',{'scope':'single development repair; not a model comparison','source_revision':source['head'],'request':request,'request_checks':checks,'generation_config':{'profile':'legacy-greedy','seed':42},'file_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}})
copy=api('/'+source['id']+'/trial-copy',{'base_revision':source['head'],'title':'Accessible evidence filters'});save('copy.json',copy)
key=copy['workspace']['id'] if 'workspace' in copy else copy['id']
project=api('/'+key)
started=api('/'+key+'/attempts',{'base_revision':project['head'],'request':request,'request_checks':checks,'generation_config':{'profile':'legacy-greedy','seed':42}});save('started.json',started)
print(json.dumps({'workspace_id':key,**started}),flush=True)
# Observe the same attempt. Observation timeout does not restart or cancel it.
for _ in range(360):
 try:
  project=api('/'+key);save('latest.json',project)
  attempt=next(x for x in project['attempts'] if x['id']==started['attempt_id'])
  if attempt['status'] not in ('queued','running'):
   save('terminal.json',attempt);print(json.dumps(attempt),flush=True);break
 except Exception as exc:save('observation-error.json',{'error':str(exc)})
 time.sleep(2)
else:raise SystemExit('Observation window ended; inspect the same saved attempt')
