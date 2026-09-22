"""Replay a frozen source planning case; never confirm the resulting proposal."""
import hashlib,json,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'.cache/two-video-contract-replay'
OLD=ROOT/'.cache/workspace-live-v3-20260921/workspace/source-jobs/fc13c99468914a25b4ca8fc49c1f5757'
def api(path='',body=None):
 req=urllib.request.Request('http://127.0.0.1:5257/api/workspace'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-Eval-Actor':'codex-development-contract-replay'})
 return json.load(urllib.request.urlopen(req,timeout=30))
def save(name,value):(OUT/name).write_text(json.dumps(value,indent=2))
assert not (OUT/'started.json').exists(),'Observe the existing replay, never start it twice'
state=api();assert not state['running_attempts'] and not state['running_source_jobs']
old=json.loads((OLD/'planning-status.json').read_text()) if (OLD/'planning-status.json').exists() else json.loads((OLD/'status.json').read_text())
manifest=api('/sources/'+old['source_id'])
save('protocol.json',{'scope':'single development replay against recorded baseline; not randomized or held-out','baseline_job_id':old['id'],'baseline_run_id':'ba94fd5b3358436d973cb0ed37524de1','source_id':old['source_id'],'request':old['request'],'interventions':['explicit required-structure profile and instruction','comparison instruction distinguishes omissions from contradictions'],'checks':['identical source packet and request','same checkpoint, sampling profile and seed','first proposal valid without schema repair','no unsupported arm-posture disagreement in cited findings'],'limitations':['warm shared runtime; no latency causal claim','Codex semantic audit is not human acceptance','combined prompt/profile intervention'],'files':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['scripts/workspace_data/desktop_plan.py','scripts/workspace_data/proposal.py','scripts/workspace_source_jobs.py']}})
save('runtime.json',state);save('source.json',manifest)
started=api('/sources/'+old['source_id']+'/generate',{'request':old['request'],'apply_reviews':False});save('started.json',started);print(json.dumps(started),flush=True)
