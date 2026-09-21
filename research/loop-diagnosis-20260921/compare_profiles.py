"""Bounded sequential development trials from the identical saved W1 continuation."""
import json,pathlib,sys,sqlite3,shutil,time,hashlib
from urllib.request import urlopen
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from workspace_provider import LocalProvider
from workspace_store import WorkspaceStore
from workspace_tools import WorkspaceTools
from workspace_worker import WorkspaceWorker
import mlflow
from mlflow import MlflowClient
mlflow.set_tracking_uri("http://127.0.0.1:5210")
origin='http://127.0.0.1:5257';key='9133f03e28d9407395f0f45829a780f9'
src=ROOT/'.cache/workspace-live-v3-20260921/workspace'
out=ROOT/'.cache/workspace-profile-comparison-v2-20260921';out.mkdir(exist_ok=False)
with urlopen(origin+'/api/workspace',timeout=5) as r: status=json.load(r)
if status['running_attempts']:raise RuntimeError('UI worker is busy; do not compete for its model')
with sqlite3.connect(src/'workspace.sqlite3') as a,sqlite3.connect(out/'frozen.sqlite3') as b:a.backup(b)
with sqlite3.connect(out/'frozen.sqlite3') as c:
 request=c.execute('select request from attempts where id=?',('b05d3920ff2a4cde8d91c2559200b58e',)).fetchone()[0]
 # Each trial resumes the identical W1 context, before the diagnosed W2 failure.
 c.execute('delete from events where attempt_id=?',('b05d3920ff2a4cde8d91c2559200b58e',))
 c.execute('delete from attempts where id=?',('b05d3920ff2a4cde8d91c2559200b58e',))
order=[('legacy-greedy',42),('bonsai2-instruct',42),('bonsai2-instruct',43),('bonsai2-instruct',44)]
mlflow.set_experiment('bonsai-workspace-attempts')
with mlflow.start_span(name='profile-comparison-export-preflight') as probe:
 probe_id=probe.trace_id
mlflow.flush_trace_async_logging()
if mlflow.get_trace(probe_id) is None:raise RuntimeError('Trace export preflight failed')
manifest={'order':order,'source_revision':'7c89f55427c2fd69cb5d7714cf64cdcdd71fab93fa806c46cab3037ed26008ee','request':request,'scope':'development_screening_not_latency_benchmark','cache':'shared_warm_server_ordered_not_cold','concurrent_backup':'CPU and disk backup may affect latency; no speed comparison','stop_guard':'two identical unmatched fragments on same revision','model_info':status['model_info']}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2));results=[]
for index,(profile,seed) in enumerate(order):
 with urlopen(origin+'/api/workspace',timeout=5) as r:
  if json.load(r)['running_attempts']:raise RuntimeError('UI worker became busy; stop trial queue')
 trial=out/f'{index}-{profile}-{seed}';trial.mkdir();shutil.copyfile(out/'frozen.sqlite3',trial/'workspace.sqlite3')
 for a in (src/'attempts').iterdir():
  for name in ('messages.json','summary.json'):
   if (a/name).exists():
    dest=trial/'attempts'/a.name/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(a/name,dest)
 store=WorkspaceStore(trial);provider=LocalProvider(origin,status['model'],profile=profile,seed=seed)
 worker=WorkspaceWorker(store,provider,WorkspaceTools(store,origin),MlflowClient(tracking_uri='http://127.0.0.1:5210'),'http://127.0.0.1:5210',status['model_info'])
 try:
  ws=store.get(key);assert ws['head']==manifest['source_revision']
  aid=worker.start(key,ws['head'],request,'W2')['attempt_id'];print(json.dumps({'started':aid,'profile':profile,'seed':seed}),flush=True)
  with worker.guard:thread=worker.running[aid][1]
  thread.join(660)
  if thread.is_alive():worker.cancel(aid);thread.join(15);raise RuntimeError('Attempt did not finish within outer bound')
  summary=json.loads((trial/'attempts'/aid/'summary.json').read_text())
  mlflow.flush_trace_async_logging()
  if mlflow.get_trace(summary['trace_id']) is None:raise RuntimeError('Completed attempt trace is missing; stop comparison')
  results.append({'profile':profile,'seed':seed,**summary})
  (out/'results.json').write_text(json.dumps(results,indent=2));print(json.dumps({'finished':aid,'profile':profile,'status':summary['status'],'error':summary.get('error'),'run_id':summary['run_id']}),flush=True)
 finally:worker.close()
print('Comparison terminal',flush=True)
