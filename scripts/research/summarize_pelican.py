#!/usr/bin/env python3
"""Audit four fixed Pelican executions; emit portable JSON and isolated SVG images."""
import argparse,base64,hashlib,html,json,math,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from svg_output import inspect_svg
PREFIX='b020260918000000000000000000'
MODELS=[('0101','Bonsai 1','prism-ml/Ternary-Bonsai-27B-gguf','86e89f34c93201c3dfd5e5880fedb0022fc7e34d'),('0102','Bonsai 2','prism-ml/Ternary-Bonsai-2-27B-gguf','6ed5e12bf84b7a63069882c91dd9e9218647d17b'),('0436','Qwen 3.6','Qwen/Qwen3.6-27B','6a9e13bd6fc8f0983b9b99948120bc37f49c13e9'),('0038','Qwen 3.8','Qwen/Qwen3.8-27B','1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0')]
PROMPT=[{'role':'user','content':'Generate an SVG of a pelican riding a bicycle'}]
EXPECTED={'temperature':.3,'top_p':.95,'top_k':20,'min_p':0,'seed':42,'max_new_tokens':4096}
def sha(data):return hashlib.sha256(data).hexdigest()
def load(p):return json.loads(p.read_text())
def require(ok,why):
 if not ok:raise ValueError(why)
def vector(directory,s):
 # Archived absolute paths are rebased to this record; never read outside it.
 p=directory/Path(s['vector_file']).name;raw=p.read_bytes()
 require(sha(raw)==s['vector_sha256'],'Activation vector hash mismatch')
 require(s['vector_length']==5120 and len(raw)==5120*4,'Activation vector size mismatch')
 v=struct.unpack('<'+'f'*s['vector_length'],raw)
 require(all(math.isfinite(x) for x in v),'Nonfinite activation')
 require(all(math.isfinite(x) and math.isclose(x,y,rel_tol=1e-6,abs_tol=1e-7) for x,y in zip(s['sample'],v)),'Activation sample mismatch')
 require(len(s['sample'])>0 and len(s['sample'])<=len(v),'Empty/oversized activation sample')
 return {'file':p.name,'sha256':sha(raw),'dimensions':len(v)}
def audit_one(root,spec):
 suffix,label,repo,revision=spec;rid=PREFIX+suffix;p=root/rid
 identity=load(p/'identity.json');request=load(p/'request.json');result=load(p/'result.json');capture=load(p/'activation-capture.json');research=load(p/'research.json')
 h=sha((p/'request.json').read_bytes())
 require((identity.get('repo'),identity.get('revision'))==(repo,revision),f'{label}: checkpoint mismatch')
 if repo.startswith('Qwen/'):
  require(identity.get('quantized') is False and identity.get('weight_dtype')=='bfloat16','Official Qwen dtype/quantization mismatch')
 else:
  expected_sha='e4781999f1997ef97ce0c58d05750835acc999d18d83ee6489ba7ac7b14cb5f6' if suffix=='0101' else '3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1'
  require(identity.get('sha256')==expected_sha,'Native checkpoint SHA mismatch')
 require(research.get('status')=='completed' and research.get('model_identity')==identity,'Research completion/identity mismatch')
 require(request.get('messages')==PROMPT,f'{label}: prompt mismatch')
 require(all(type(request.get(k)) in (int,float) and request[k]==v for k,v in EXPECTED.items()),f'{label}: numeric setting mismatch')
 require(request.get('repetition_penalty',request.get('repeat_penalty',1))==1,'Repetition penalty mismatch')
 require(request.get('enable_thinking',request.get('chat_template_kwargs',{}).get('enable_thinking')) is False,'Thinking setting mismatch')
 require(capture.get('kind')=='live_instrumented_inference' and capture.get('passed') is True,'Not successful live capture')
 require(capture.get('source',{}).get('research_id')==rid and capture['source'].get('request_sha256')==h,'Capture source mismatch')
 require(identity.get('source_request_sha256')==h and result.get('source_request_sha256')==h,'Request provenance mismatch')
 for model in (capture.get('model',{}),result.get('identity',{})):
  require(model==identity,'Capture/result full identity mismatch')
 samples=capture.get('samples',[]);require(bool(samples),'No activation samples')
 vectors=[vector(p,s) for s in samples]
 sampler_audit=load(p/'sampler-order-audit.json') if (p/'sampler-order-audit.json').exists() else None
 if repo.startswith('prism-ml/'):
  require(identity.get('sampler_order')==['temperature','top_k','top_p','min_p','categorical_draw'],'Native V2 sampler order missing/mismatched')
 if sampler_audit:
  require(sampler_audit.get('recorded_transformers_version')==identity.get('transformers'),'Sampler source audit version mismatch')
  require(sampler_audit.get('captured_during_original_inference') is False,'Post-run source audit mislabeled')
 require(len({v['file'] for v in vectors})==len(vectors),'Duplicate vector file')
 layers=sorted({s['layer'] for s in samples});require(layers==[0,31,63],'Unexpected layers')
 steps={s['step'] for s in samples};require(steps==set(range(len(steps))),'Noncontiguous decode steps')
 require(len(samples)==len(steps)*3 and {(s['step'],s['layer']) for s in samples}=={(step,layer) for step in steps for layer in (0,31,63)},'Missing/duplicate layer in decode step')
 prefill=[]
 for c in result.get('captures',[]):
  if c.get('phase')=='prefill_last_position':
   f=p/Path(c['file']).name;raw=f.read_bytes();vals=struct.unpack('<'+'f'*c['dimensions'],raw)
   require(c['dimensions']==5120 and len(raw)==5120*4,'Prefill dimension mismatch')
   require(all(math.isfinite(x) for x in vals),'Nonfinite prefill')
   prefill.append({'file':f.name,'sha256':sha(raw),'layer':c['layer'],'scope':'last prompt position only; digest computed during audit (not pre-existing manifest hash)'})
 require(result.get('recorded_vectors')==len(samples)+len(prefill),'Recorded vector count mismatch')
 output=(p/'output.txt').read_text()
 require(research.get('response',{}).get('choices',[{}])[0].get('message',{}).get('content')==output,'Research output mismatch')
 require(capture.get('generated_text')==output,'Capture output mismatch')
 svg=inspect_svg(output)
 stored_svg=result.get('svg',{})
 require(stored_svg.get('valid')==svg.get('valid'),'Stored SVG validation status differs from reinspection')
 if svg.get('valid'):
  require(stored_svg.get('source')==svg['source'],'Stored SVG differs from original output')
 else:
  require(stored_svg.get('error')==svg.get('error'),'Stored SVG validation error differs from reinspection')
 seconds=result.get('seconds');require(type(seconds) in (int,float) and math.isfinite(seconds) and seconds>0,'Missing measured latency')
 return {'research_id':rid,'label':label,'repo':repo,'revision':revision,'request_sha256':h,'output_sha256':sha(output.encode()),'evidence_audit_passed':True,'output_validation_passed':svg['valid'],'svg_validation_error':svg.get('error'),'svg_sha256':sha(svg['source'].encode()) if svg['valid'] else None,'svg_source':svg.get('source'),'original_output':output,'generated_tokens':result['generated_tokens'],'token_count_scope':'HF output includes terminal EOS; native count excludes EOS' ,'seconds_instrumented':seconds,'decode_vectors':len(vectors),'layers':layers,'vector_manifest':vectors,'prefill_vectors':prefill,'prefill_scope':capture.get('scope',capture.get('settings',{}).get('prefill_captured')),'identity':identity,'sampler_order':identity.get('sampler_order'),'post_run_sampler_source_audit':sampler_audit,'sampler_source_evidence':identity.get('runtime_source_sha256',identity.get('runtime',{})),'mlflow':capture.get('mlflow',{})}
def summarize(root,output):
 required=['identity.json','request.json','result.json','activation-capture.json','output.txt','research.json']
 pending=[str(root/(PREFIX+s[0])/f) for s in MODELS for f in required if not (root/(PREFIX+s[0])/f).is_file()]
 if pending:raise FileNotFoundError('Pending required final evidence: '+', '.join(pending))
 rows=[audit_one(root,s) for s in MODELS]
 limitations=['Single prompt and single seeded sample; visual quality is not automatically ranked.','Same numeric settings do not establish equal sampling implementations or identical random draws. Native V2 must record temperature before top-k/top-p; HF order evidence is reported from retained identity/source metadata, with missing evidence left explicit.','Native packed ternary CUDA llama.cpp and official BF16 Transformers/SDPA differ in precision, kernels, runtime, and generation/token accounting. All latencies include activation instrumentation and are not production benchmarks.','Hardware identity and runtime details are retained per execution; absent fields are unknown, not inferred.','Residual coordinates are not aligned across models. These observations are not causal attribution or a weight-change measurement.','HF prefill captures retain only the final prompt position; native prefill coverage is recorded separately.']
 audit={'passed':True,'evidence_audit_passed':True,'output_validation_passed':all(r['output_validation_passed'] for r in rows),'prompt':PROMPT,'numeric_settings':EXPECTED,'limitations':limitations,'runs':rows}
 output.mkdir(parents=True,exist_ok=True);(output/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
 esc=html.escape;cards=[]
 for r in rows:
  if r['output_validation_passed']:
   encoded=base64.b64encode(r['svg_source'].encode()).decode()
   visual=f'<img alt="{esc(r["label"])} original Pelican SVG" src="data:image/svg+xml;base64,{encoded}">'
  else:
   visual='<p><strong>SVG validation failed:</strong> '+esc(r['svg_validation_error'] or 'Unknown validation error')+'</p><details open><summary>Unchanged original output</summary><pre>'+esc(r['original_output'])+'</pre></details>'
  cards.append(f'<article><h2>{esc(r["label"])}</h2>{visual}<p>{r["generated_tokens"]} output tokens · {r["seconds_instrumented"]:.2f} instrumented seconds · {r["decode_vectors"]} verified decode vectors</p><p>{esc(r["repo"])}<br>{esc(r["revision"])}</p><details><summary>Execution evidence</summary><pre>{esc(json.dumps({k:v for k,v in r.items() if k not in ("svg_source","vector_manifest","original_output")},indent=2))}</pre></details></article>')
 doc='<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; style-src \'unsafe-inline\'"><title>Pelican execution comparison</title><style>body{font:16px system-ui;background:#f6f1e9;color:#242424;margin:28px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}article{background:white;padding:20px;border-radius:16px}img{width:100%;height:400px;object-fit:contain}pre{white-space:pre-wrap;overflow-wrap:anywhere} @media(max-width:800px){.grid{grid-template-columns:1fr}}</style><h1>Four real Pelican executions</h1><p>Generate an SVG of a pelican riding a bicycle</p><ul>'+''.join('<li>'+esc(x)+'</li>' for x in limitations)+'</ul><main class="grid">'+''.join(cards)+'</main>'
 (output/'comparison.html').write_text(doc);return audit
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--records-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 try:summarize(a.records_root,a.output)
 except (ValueError,FileNotFoundError,KeyError) as e:p.exit(2,str(e)+'\n')
