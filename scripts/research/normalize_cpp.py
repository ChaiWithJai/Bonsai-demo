#!/usr/bin/env python3
"""Publish completed actual native Bonsai capture into research observability."""
import argparse,hashlib,json,math,shutil,struct,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--identity',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--binary',type=Path,required=True);p.add_argument('--cpp-source',type=Path,required=True);p.add_argument('--elapsed-seconds',type=float);p.add_argument('--tracking-uri',default='sqlite:////home/chaiwithjai/bonsai-workspace/mlflow.db');p.add_argument('--mlflow-python',default='/home/chaiwithjai/bonsai-workspace/venv/bin/python');a=p.parse_args()
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(name,obj):(a.output/name).write_text(json.dumps(obj,indent=2))
c=json.loads((a.source/'capture.json').read_text());identity=json.loads(a.identity.read_text());settings=json.loads((a.source/'config.json').read_text());request=json.loads((a.source/'request.json').read_text())
if a.elapsed_seconds is None:a.elapsed_seconds=c.get('generation_seconds')
if settings.get('sampler_order'):
 identity['sampler_order']=settings['sampler_order']
 identity['sampling_protocol']=settings.get('protocol')
 if c.get('sampler_order')!=settings['sampler_order']:raise ValueError('Runtime sampler order differs from config')
if not c['passed']:raise ValueError('Capture did not pass')
if digest(Path(identity['path']))!=identity['sha256']:raise ValueError('Official model hash mismatch')
a.output.mkdir(parents=True,exist_ok=False)
request.update(settings);request['max_new_tokens']=settings['decode_steps'];write('request.json',request);request_hash=digest(a.output/'request.json')
identity.update({'weight_format':'official_PQ2_0_native_ternary','weight_dtype':'native_packed_ternary','third_party_requantization':False,'capture_kind':'same_execution_native_residuals','source_request_sha256':request_hash})
identity['runtime']={'binary':str(a.binary.resolve()),'binary_sha256':digest(a.binary),'source':str(a.cpp_source.resolve()),'source_sha256':digest(a.cpp_source)}
shutil.copyfile(a.cpp_source,a.output/'capture-source.cpp')
if digest(a.output/'capture-source.cpp')!=identity['runtime']['source_sha256']:raise ValueError('Archived source hash mismatch')
if a.binary.stat().st_size<=32*1024*1024:
 shutil.copyfile(a.binary,a.output/'capture-binary')
 if digest(a.output/'capture-binary')!=identity['runtime']['binary_sha256']:raise ValueError('Archived binary hash mismatch')
write('identity.json',identity);shutil.copyfile(a.source/'prompt.txt',a.output/'rendered-prompt.txt');(a.output/'output.txt').write_text(c['generated_text'])
for sample in c['samples']:
 src=a.source/sample['vector_file'];dst=a.output/src.name;shutil.copyfile(src,dst);raw=dst.read_bytes();v=struct.unpack('<'+'f'*(len(raw)//4),raw)
 if len(v)!=sample['vector_length'] or not all(math.isfinite(x) for x in v):raise ValueError('Invalid vector')
 if not math.isclose((sum(x*x for x in v)/len(v))**.5,sample['stats']['rms'],rel_tol=1e-6):raise ValueError('Vector stats mismatch')
 sample.update(vector_file=str(dst.resolve()),vector_sha256=digest(dst))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));from svg_output import inspect_svg
svg=inspect_svg(c['generated_text'])
if svg.get('valid'):(a.output/'output.svg').write_text(svg['source'])
r={'identity':identity,'generated_tokens':len(c['tokens']),'seconds':a.elapsed_seconds,'recorded_vectors':len(c['samples']),'svg':svg,'source_request_sha256':request_hash,'layers':sorted(set(s['layer'] for s in c['samples']))}
write('result.json',r)
write('native-capture.json',c)
shutil.copyfile(a.source/'config.json',a.output/'runtime-config.json')
if (a.source/'runtime.log').exists():shutil.copyfile(a.source/'runtime.log',a.output/'runtime.log')
subprocess.run([a.mlflow_python,str(Path(__file__).with_name('log_official_pelican.py')),'--directory',str(a.output),'--tracking-uri',a.tracking_uri],check=True)
ml=json.loads((a.output/'mlflow.json').read_text());c.update({'kind':'live_instrumented_inference','source':{'research_id':a.output.name,'request_sha256':request_hash},'model':identity,'settings':{**settings,'layers':r['layers'],'prefill_captured':False},'rendered_prompt':(a.output/'rendered-prompt.txt').read_text(),'mlflow':ml,'interpretation':'Measured decoder residual outputs during this actual generation, not historical replay or causal attribution.'});write('activation-capture.json',c)
write('research.json',{'id':a.output.name,'title':identity['repo']+(' · aligned sampler pelican' if settings.get('sampler_order') else ' · official native ternary pelican'),'started_at':(a.source/'request.json').stat().st_mtime,'updated_at':time.time(),'model_identity':identity,'request':request,'response':{'choices':[{'message':{'content':c['generated_text']},'finish_reason':'stop' if c['reached_eog'] else 'length'}]},'status':'completed','elapsed_ms':a.elapsed_seconds*1000 if a.elapsed_seconds is not None else None,**ml,'mlflow_url':f'http://127.0.0.1:5210/#/experiments/{ml["experiment_id"]}/runs/{ml["run_id"]}'})
print(json.dumps({'output':str(a.output),'svg_valid':svg.get('valid'),'vectors':len(c['samples']),**ml}))
