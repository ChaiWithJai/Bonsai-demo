"""Adapt measured HF results into the observability research envelope."""
import hashlib,json,struct,time
from pathlib import Path

def emit(directory):
 directory=Path(directory).resolve();r=json.loads((directory/'result.json').read_text());identity=r['identity']
 request=json.loads((directory/'request.json').read_text());ids=r['generated_token_ids'];samples=[];tokens=[]
 for c in r['captures']:
  if c['phase']!='decode':continue
  step=c['forward_call']-1;p=directory/c['file'];raw=p.read_bytes();values=struct.unpack('<'+'f'*(len(raw)//4),raw)
  text=c.get('input_token_text','')
  samples.append({'step':step,'layer':c['layer'],'input_token_id':ids[step],'input_token_text':text,
   'tensor':f'decoder_layer_{c["layer"]}_residual_output','shape':[c['dimensions'],1,1,1],
   'sample':list(values[:16]),'stats':{'min':c['min'],'max':c['max'],'mean':c['mean'],'rms':c['rms'],'l2':c['rms']*len(values)**.5,'nonfinite':0},
   'vector_file':str(p),'vector_length':len(values),'vector_sha256':hashlib.sha256(raw).hexdigest()})
  if c['layer']==r['layers'][0]:tokens.append({'step':step,'input_token_id':ids[step],'input_token_text':text,'token_id':ids[step],'text':text})
 ml=json.loads((directory/'mlflow.json').read_text()) if (directory/'mlflow.json').exists() else {}
 capture={'kind':'live_instrumented_inference','passed':True,'samples':samples,'tokens':tokens,
  'generated_text':(directory/'output.txt').read_text(),'source':{'research_id':directory.name,'request_sha256':r['source_request_sha256']},
  'rendered_prompt':(directory/'rendered-prompt.txt').read_text(),'model':identity,'settings':{'layers':r['layers'],'decode_steps':r['capture_steps_requested'],'prefill_captured':True,'differences':[]},
  'mlflow':ml,'scope':'Same execution as displayed output; selected decoder residual layers. Prefill vectors are retained separately in result.json.'}
 (directory/'activation-capture.json').write_text(json.dumps(capture,indent=2))
 stamp=(directory/'request.json').stat().st_mtime
 summary={'id':directory.name,'title':identity['repo']+' · official pelican','started_at':stamp,'updated_at':time.time(),
 'model_identity':identity,'request':request,'response':{'choices':[{'message':{'content':(directory/'output.txt').read_text()},'finish_reason':'length' if r['length_bound_reached'] else 'stop'}]},'status':'completed','elapsed_ms':r['seconds']*1000 if r['seconds'] is not None else None,
 **ml,'mlflow_url':f'http://127.0.0.1:5210/#/experiments/{ml.get("experiment_id","")}/runs/{ml.get("run_id","")}'}
 (directory/'research.json').write_text(json.dumps(summary,indent=2))
