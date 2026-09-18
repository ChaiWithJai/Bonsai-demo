#!/usr/bin/env python3
"""Capture a new isolated replay of recorded context, never historical activations."""
from pathlib import Path
import fcntl, argparse, datetime, hashlib, json, math, os, shutil, struct, subprocess, time, urllib.request
import mlflow
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'.cache/bonsai/activation-diagnostic'
LIB=ROOT/'prefill-campaign/research/fa-q32g2-isolated-20260916-0255/bin'
BINARY=BASE/'bin/capture-activations'
RUN='281f312036ae40cea5686b09123633ff'
RECORD=Path('/home/chaiwithjai/bonsai-workspace/comparison-records')/RUN
SOURCE=RECORD/'bonsai/turn-4'
EXPECTED='3643e345eb191c9753065d32c0bc48770610d66125a0280f05f476df2e4e6194'
def digest(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--native-record',type=Path)
 parser.add_argument('--comparison-turn',type=Path)
 parser.add_argument('--upstream',default='http://127.0.0.1:8081')
 parser.add_argument('--tracking-uri',default='sqlite:////home/chaiwithjai/bonsai-workspace/mlflow.db')
 args=parser.parse_args()
 os.umask(0o077)
 lock=(BASE/'capture.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX)
 activity={}
 for endpoint in dict.fromkeys((args.upstream,os.environ.get('COMPARISON_QWEN_ENDPOINT','http://127.0.0.1:8083'))):
  try:
   slots=json.load(urllib.request.urlopen(endpoint+'/slots',timeout=10))
   activity[endpoint]=any(s.get('is_processing') for s in slots)
  except (OSError,ValueError):
   # An offline peer must not prevent replay of a verified recorded request.
   activity[endpoint]=None
 memory={l.split(':')[0]:int(l.split()[1])*1024 for l in Path('/proc/meminfo').read_text().splitlines()}
 if memory['MemAvailable']<20*1024**3:raise RuntimeError('Need 20 GiB available')
 release=json.loads((ROOT/'.cache/bonsai/release-manifest.json').read_text());model=next(f for f in release['checkpoint']['files'] if 'mmproj' not in f['filename'])
 assert model['verified'] and digest(model['path'])==model['sha256']
 if args.native_record:
  record=args.native_record.resolve();request=json.loads((record/'request.bin').read_text());exchange=json.loads((record/'exchange.json').read_text())
  if exchange.get('kind')!='completion' or not exchange.get('complete') or exchange.get('status',500)>=400:raise ValueError('Only successful completed inference requests can be replayed')
  info=json.loads((record/'server-info.json').read_text())
  verified=info.get('checkpoint_release',{}).get('verified_file',{})
  if verified.get('sha256')!=model['sha256'] or Path(info.get('model_path','')).resolve()!=Path(model['path']).resolve():raise ValueError('Recorded checkpoint differs from capture checkpoint')
  for message in request.get('messages',[]):
   content=message.get('content')
   if isinstance(content,list) and any(part.get('type')!='text' for part in content):raise ValueError('Image/audio replay is unsupported; context was not truncated')
  def post(path,payload):
   req=urllib.request.Request(args.upstream+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
   return json.load(urllib.request.urlopen(req,timeout=60))
  current=json.load(urllib.request.urlopen(args.upstream+'/props',timeout=10))
  if current.get('model_path')!=info.get('model_path') or current.get('build_info')!=info.get('build_info'):raise ValueError('Serving runtime changed since original inference')
  rendered=post('/apply-template',request)['prompt'];tokens=post('/tokenize',{'content':rendered,'add_special':True,'parse_special':True})['tokens']
  if len(tokens)+32>65536:raise ValueError('Recorded context exceeds instrumented 65536-token limit; no truncation performed')
  preflight={'rendered_prompt':rendered,'prompt_tokens':len(tokens)}
  (record/'activation-replay-preflight.json').write_text(json.dumps(preflight))
  render_hash=hashlib.sha256(rendered.encode()).hexdigest()
  source={'request_id':record.name,'native_request_id':record.name,'session':exchange.get('session'),'request_sha256':digest(record/'request.bin'),'request_path':str(record/'request.bin'),'rendered_prompt_sha256':render_hash,'trace_id':exchange.get('trace_id')}
  defaults=info.get('default_generation_settings',{}).get('params',{})
  for key,fallback in {'temperature':0.8,'top_p':0.95,'top_k':40,'min_p':0.05,'seed':4294967295}.items():
   if request.get(key) is None:request[key]=defaults.get(key,fallback)
  out=record/'activation-replay-artifacts';out.mkdir(exist_ok=True)
  shutil.copyfile(record/'request.bin',out/'source-request.json')
 elif args.comparison_turn:
  record=args.comparison_turn.resolve();request=json.loads((record/'request.json').read_text());preflight=json.loads((record/'preflight.json').read_text())
  identity=json.loads((record.parent/'identity.json').read_text());provenance=identity['identity']['checkpoint_provenance'];model=provenance['file']
  if not model.get('verified') or digest(model['path'])!=model['sha256']:raise ValueError('Comparison checkpoint hash mismatch')
  release={'checkpoint':{'repo':provenance['repo'],'revision':provenance.get('revision')}}
  rendered=preflight['rendered_prompt'];render_hash=hashlib.sha256(rendered.encode()).hexdigest()
  summary_path=record.parent.parent/'summary.json';summary=json.loads(summary_path.read_text()) if summary_path.exists() else {}
  result_path=record/'result.json';original=json.loads(result_path.read_text()) if result_path.exists() else {}
  source={'comparison_run_id':record.parent.parent.name,'model':record.parent.name,'turn':int(record.name.split('-')[-1]),'request_sha256':digest(record/'request.json'),'request_path':str(record/'request.json'),'rendered_prompt_sha256':render_hash,'trace_id':summary.get('trace_id'),'span_id':original.get('span_id')}
  status_path=record/'activation-replay-status.json'
  if status_path.exists():
   prior=json.loads(status_path.read_text()).get('source',{})
   for key in ('trace_id','span_id'):
    if not source.get(key):source[key]=prior.get(key)
  out=record/'activation-replay-artifacts';out.mkdir(exist_ok=True);shutil.copyfile(record/'request.json',out/'source-request.json')
 else:
  assert digest(SOURCE/'request.json')==EXPECTED
  request=json.loads((SOURCE/'request.json').read_text());preflight=json.loads((SOURCE/'preflight.json').read_text());summary=json.loads((RECORD/'summary.json').read_text());original=json.loads((SOURCE/'result.json').read_text())
  rendered=preflight['rendered_prompt'];render_hash=hashlib.sha256(rendered.encode()).hexdigest()
  out=BASE/('replay-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));out.mkdir(parents=True)
  for name in ('request.json','preflight.json','result.json'):shutil.copyfile(SOURCE/name,out/('source-'+name))
  source={'comparison_run_id':RUN,'model':'bonsai','turn':4,'request_sha256':EXPECTED,'request_path':str(SOURCE/'request.json'),'preflight_path':str(SOURCE/'preflight.json'),'rendered_prompt_sha256':render_hash,'trace_id':summary['trace_id'],'span_id':original['span_id']}
 (out/'rendered-prompt.txt').write_text(rendered)
 config={'decode_steps':32,'context':max(8192,((preflight['prompt_tokens']+32+1023)//1024)*1024),'n_threads':20,'sampler':'source_sampling','expected_prompt_tokens':preflight['prompt_tokens'],**{k:request[k] for k in ('temperature','top_p','top_k','min_p','seed')}}
 (out/'config.json').write_text(json.dumps(config,indent=2))
 settings={**config,'original_request_settings':{k:v for k,v in request.items() if k not in ('messages','tools')},'shared_hardware_activity_at_start':activity,'timing_is_contended':(True if any(activity.values()) else None if None in activity.values() else False),'layers':[0,31,63],'n_batch':2048,'n_ubatch':256,'flash_attention':True,'prefill_captured':False,'vector_dtype':'little-endian float32','repeat_penalty':1,'differences':['New isolated model context, not original production activations','32 decode-token bound instead of original max_tokens','Single instrumented sequence; context sized to full recorded prompt','Fresh prefill without production prefix cache','Standalone top-k/top-p/min-p/temperature sampling; server stop strings, grammar, repeat/presence/frequency penalties and other sampler stages are not applied; random default seed creates a new sample','Instrumentation synchronizes selected residual tensors; timing is not production latency']}
 env={**os.environ,'LD_LIBRARY_PATH':str(LIB)};env.pop('LD_PRELOAD',None)
 mlflow.set_tracking_uri(args.tracking_uri);mlflow.set_experiment('bonsai-native-ui')
 started_at=time.time();start=time.monotonic()
 with mlflow.start_run(run_name=('Native chat '+args.native_record.name+' instrumented replay') if args.native_record else ('Comparison '+str(source.get('model'))+' turn '+str(source.get('turn'))+' instrumented replay')) as run:
  mlflow.set_tags({'kind':'new_instrumented_real_request_replay','source_request_id':source.get('request_id',''),'source_comparison_run_id':source.get('comparison_run_id',''),'source_model':source.get('model','bonsai'),'source_turn':str(source.get('turn','')),'historical_chat_capture':'false'})
  mlflow.log_params({'checkpoint_sha256':model['sha256'],'source_request_sha256':source['request_sha256'],'rendered_prompt_sha256':render_hash,'decode_steps_requested':32,'layers':'0,31,63'})
  with mlflow.start_span(name='instrumented_real_context_replay',span_type='LLM') as span:
   span.set_inputs({'source':source,'rendered_prompt':rendered,'settings':settings})
   with (out/'runtime.log').open('w') as log:
    proc=subprocess.Popen([str(BINARY),model['path'],str(out/'rendered-prompt.txt'),str(out),str(out/'config.json')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    time.sleep(.3)
    observed=sorted({l.split()[-1] for l in Path(f'/proc/{proc.pid}/maps').read_text().splitlines() if 'libggml' in l or 'libllama' in l})
    try:code=proc.wait(timeout=300)
    except subprocess.TimeoutExpired:proc.kill();proc.wait();raise
   assert len(observed)>=4 and all(p.startswith(str(LIB)+'/') for p in observed),observed
   if code:raise RuntimeError(f'Capture exit {code}: {out}/runtime.log')
   result=json.loads((out/'capture.json').read_text());steps=len(result['tokens'])
   assert result['passed'] and 0<steps<=32 and len(result['samples'])==steps*3
   assert {(s['step'],s['layer']) for s in result['samples']}=={(t['step'],l) for t in result['tokens'] for l in (0,31,63)}
   for sample in result['samples']:
    f=out/sample['vector_file'];raw=f.read_bytes();assert len(raw)==5120*4
    values=struct.unpack('<5120f',raw);assert all(math.isfinite(v) for v in values)
    assert all(abs(a-b)<1e-6 for a,b in zip(values[:16],sample['sample']))
    assert math.isclose(math.sqrt(sum(v*v for v in values)/len(values)),sample['stats']['rms'],rel_tol=1e-6)
    sample.update(vector_file=str(f),vector_sha256=digest(f))
   span.set_outputs({'generated_text':result['generated_text'],'captured_vectors':len(result['samples']),'decode_steps':steps});trace_id=span.trace_id
  elapsed=time.monotonic()-start
  result.update({'kind':'new_instrumented_real_request_replay','historical_chat_capture':False,'relationship':'replay_of_same_rendered_context; not original activations','source':source,'replay':{'trace_id':trace_id,'run_id':run.info.run_id,'experiment_id':run.info.experiment_id,'started_at':started_at,'elapsed_ms':elapsed*1000,'request_path':str(out/'source-request.json'),'response_path':str(out/'capture.json'),'rendered_prompt':rendered},'diagnostic_trace_id':trace_id,'prompt':request['messages'][-1].get('content',''),'rendered_prompt':rendered,'model':{'repo':release['checkpoint']['repo'],'revision':release['checkpoint']['revision'],'sha256':model['sha256'],'path':model['path']},'runtime':{'binary':str(BINARY),'sha256':digest(BINARY),'source_sha256':digest(ROOT/'scripts/capture_activations.cpp'),'library_path':str(LIB),'observed_library_paths':observed},'settings':settings,'elapsed_seconds':elapsed,'available_memory_before_bytes':memory['MemAvailable'],'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'mlflow':{'run_id':run.info.run_id,'url':f'http://127.0.0.1:5210/#/experiments/{run.info.experiment_id}/runs/{run.info.run_id}'},'interpretation':'Actual residual-stream F32 vectors from a NEW instrumented execution of the exact recorded request context. Not the original request activations; not a causal explanation of the original answer.'})
  (out/'replay-latest.json').write_text(json.dumps(result,indent=2)+'\n')
  mlflow.log_metrics({'captured_vectors':len(result['samples']),'decode_steps':steps,'elapsed_seconds':elapsed,'nonfinite_values':0})
  mlflow.log_artifacts(str(out),artifact_path='activation-replay')
  for name in ('capture_activations.cpp','capture_activations_replay.py'):mlflow.log_artifact(str(ROOT/'scripts'/name),artifact_path='activation-replay/source')
 destination=(args.native_record or args.comparison_turn)/'activation-replay.json' if (args.native_record or args.comparison_turn) else BASE/'replay-latest.json'
 tmp=destination.with_suffix('.tmp');tmp.write_text(json.dumps(result,indent=2)+'\n');tmp.replace(destination)
 print(json.dumps({'passed':True,'path':str(destination),'samples':len(result['samples']),'mlflow':result['mlflow'],'trace_id':trace_id,'elapsed_seconds':elapsed}))
if __name__=='__main__':main()
