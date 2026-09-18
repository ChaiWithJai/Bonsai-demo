#!/usr/bin/env python3
"""Loopback-only, offline BF16 server. Serialized generation and actual residual captures."""
import os
os.environ['HF_HUB_OFFLINE']='1';os.environ['HF_DEACTIVATE_ASYNC_LOAD']='1'
import argparse,json,hashlib,threading,time,uuid,queue,subprocess,sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import torch
from transformers import AutoTokenizer,AutoModelForImageTextToText,GenerationConfig,TextIteratorStreamer,StoppingCriteria,StoppingCriteriaList
from huggingface_hub import snapshot_download
from official_pelican import MODELS,verify_safetensors,audit_functional_shapes,write
from research_envelope import emit
p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8083);p.add_argument('--records',type=Path,default=Path('/home/chaiwithjai/bonsai-workspace/research-records'));a=p.parse_args()
repo='Qwen/Qwen3.8-27B';revision=MODELS[repo];snapshot=Path(snapshot_download(repo,revision=revision,local_files_only=True));manifest,_=verify_safetensors(snapshot);audit=audit_functional_shapes(snapshot)
for shard in manifest:
 path=snapshot/shard['name'];blob=path.resolve().name
 with path.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
 if len(blob)!=64 or actual!=blob:raise ValueError('HF cache shard hash mismatch: '+shard['name'])
 shard['sha256']=actual
model,info=AutoModelForImageTextToText.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False,dtype=torch.bfloat16,device_map='cuda',attn_implementation='sdpa',output_loading_info=True)
if any(info.get(k) for k in ('missing_keys','mismatched_keys','error_msgs','conversion_errors')):raise ValueError(str(info))
if sum(x.numel() for x in model.parameters())!=audit['loaded_model_parameters']:raise ValueError('Functional weight count mismatch')
if any(x.dtype!=torch.bfloat16 for x in model.parameters()):raise ValueError('Unexpected dtype')
model.eval();tokenizer=AutoTokenizer.from_pretrained(snapshot,local_files_only=True);official=json.loads((snapshot/'generation_config.json').read_text());lock=threading.Lock();active=False
identity={'repo':repo,'revision':revision,'verified':True,'weight_dtype':'bfloat16','quantized':False,'snapshot':str(snapshot),'shards':manifest,'functional_weight_audit':audit,'capture_kind':'same_execution_forward_hooks','runtime_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
class Cancel(StoppingCriteria):
 def __init__(self,event):self.event=event
 def __call__(self,input_ids,scores,**kw):return self.event.is_set()
def validate(r):
 if not isinstance(r.get('messages'),list) or not r['messages']:raise ValueError('messages required')
 for m in r['messages']:
  if not isinstance(m.get('content'),str) or m.get('role') not in ('system','user','assistant'):raise ValueError('Text messages only; tools/vision unsupported')
 if r.get('tools') or r.get('tool_choice'):raise ValueError('Tool calling unsupported in this endpoint')
 thinking=r.get('chat_template_kwargs',{}).get('enable_thinking',False)
 if r.get('thinking_budget_tokens',0) not in (0,-1):raise ValueError('Finite thinking budgets unsupported; use0 or-1')
 if r.get('thinking_budget_tokens')==-1:thinking=True
 if r.get('thinking_budget_tokens')==0:thinking=False
 out={'max_new_tokens':int(r.get('max_tokens',512)),'temperature':float(r.get('temperature',.3)),'top_p':float(r.get('top_p',.95)),'top_k':int(r.get('top_k',20)),'min_p':float(r.get('min_p',0)),'repetition_penalty':float(r.get('repeat_penalty',r.get('repetition_penalty',1))), 'seed':int(r.get('seed',42)),'thinking':bool(thinking)}
 if not 1<=out['max_new_tokens']<=4096 or not 0<=out['temperature']<=2 or not 0<out['top_p']<=1 or not 0<=out['top_k']<=1000 or not 0<=out['min_p']<=1 or not .1<=out['repetition_penalty']<=3 or not 0<=out['seed']<=4294967295:raise ValueError('Sampling setting outside supported bounds')
 if any(r.get(k,0) not in (0,None) for k in ('presence_penalty','frequency_penalty')) or r.get('stop'):raise ValueError('Presence/frequency penalties and custom stops unsupported')
 return out
def render(r):
 cfg=validate(r);return tokenizer.apply_chat_template(r['messages'],tokenize=False,add_generation_prompt=True,enable_thinking=cfg['thinking'])
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def response(self,obj,status=200):
  data=json.dumps(obj).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def do_GET(self):
  if self.path=='/health':return self.response({'status':'ok'})
  if self.path=='/v1/models':return self.response({'data':[{'id':repo,'object':'model','owned_by':'Qwen','weight_dtype':'bfloat16'}]})
  if self.path=='/slots':return self.response([{'is_processing':active}])
  if self.path=='/props':return self.response({'model_path':str(snapshot),'model_alias':repo,'build_info':'transformers '+__import__('transformers').__version__,'total_slots':1,'default_generation_settings':{'n_ctx':8192,'params':{'temperature':.3,'top_p':.95,'top_k':20,'min_p':0,'repeat_penalty':1}},'checkpoint_provenance':identity,'capabilities':{'text':True,'stream':True,'tools':False,'vision':False,'thinking':True,'finite_thinking_budget':False,'activation_capture':'all_generated_forward_steps_layers_0_31_63','max_tokens':4096}})
  self.response({'error':'Not found'},404)
 def do_POST(self):
  global active
  try:
   length=int(self.headers.get('Content-Length','0'))
   if length>1024*1024:raise ValueError('Request too large')
   r=json.loads(self.rfile.read(length))
   if self.path=='/apply-template':return self.response({'prompt':render(r)})
   if self.path=='/tokenize':return self.response({'tokens':tokenizer.encode(r['content'],add_special_tokens=False)})
   if self.path!='/v1/chat/completions':return self.response({'error':'Not found'},404)
   if r.get('stream') is not True:raise ValueError('This endpoint requires stream=true')
   cfg=validate(r);prompt=render(r);inputs=tokenizer(prompt,return_tensors='pt',add_special_tokens=False)
   if inputs.input_ids.shape[1]+cfg['max_new_tokens']>8192:raise ValueError('8192 total context bound exceeded')
  except Exception as e:return self.response({'error':str(e)},400)
  if not lock.acquire(blocking=False):return self.response({'error':'Single inference slot busy'},429)
  active=True;cancel=threading.Event();rid=uuid.uuid4().hex;directory=a.records/rid;directory.mkdir(parents=True);write(directory/'request.json',r);(directory/'rendered-prompt.txt').write_text(prompt);sourcehash=hashlib.sha256((directory/'request.json').read_bytes()).hexdigest();request_identity={**identity,'source_request_sha256':sourcehash};write(directory/'identity.json',request_identity);(directory/'server-source.py').write_bytes(Path(__file__).read_bytes())
  streamer=TextIteratorStreamer(tokenizer,skip_prompt=True,skip_special_tokens=True,timeout=1);captures=[];counts={i:0 for i in (0,31,63)};handles=[];state={};start=time.monotonic()
  def hook_for(layer):
   def hook(module,args,output):
    call=counts[layer];counts[layer]+=1;t=output[0] if isinstance(output,tuple) else output;v=t[0,-1,:].detach().float().cpu().contiguous()
    if not torch.isfinite(v).all():raise ValueError('Nonfinite activation')
    name=f'layer-{layer:02d}-forward-{call:04d}.f32';(directory/name).write_bytes(v.numpy().astype('<f4').tobytes());captures.append({'layer':layer,'forward_call':call,'phase':'prefill_last_position' if call==0 else 'decode','file':name,'dimensions':v.numel(),'mean':v.mean().item(),'rms':v.square().mean().sqrt().item(),'min':v.min().item(),'max':v.max().item()})
   return hook
  def generate():
   try:
    torch.manual_seed(cfg['seed']);torch.cuda.manual_seed_all(cfg['seed'])
    for i in counts:handles.append(model.model.language_model.layers[i].register_forward_hook(hook_for(i)))
    gc=GenerationConfig(max_new_tokens=cfg['max_new_tokens'],do_sample=cfg['temperature']>0,temperature=cfg['temperature'] or 1,top_p=cfg['top_p'],top_k=cfg['top_k'],min_p=cfg['min_p'],repetition_penalty=cfg['repetition_penalty'],bos_token_id=official.get('bos_token_id'),eos_token_id=official.get('eos_token_id'),pad_token_id=official.get('pad_token_id'),use_cache=True)
    write(directory/'effective-generation-config.json',gc.to_dict())
    with torch.inference_mode():result=model.generate(**inputs.to('cuda'),generation_config=gc,streamer=streamer,stopping_criteria=StoppingCriteriaList([Cancel(cancel)]))
    state['tokens']=result[0,inputs.input_ids.shape[1]:].tolist()
   except Exception as e:state['error']=repr(e);streamer.end()
   finally:
    for h in handles:h.remove()
    state['seconds']=time.monotonic()-start
  thread=threading.Thread(target=generate);thread.start()
  def send(obj):self.wfile.write(('data: '+json.dumps(obj)+'\n\n').encode());self.wfile.flush()
  try:
   self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Cache-Control','no-cache');self.send_header('Connection','close');self.end_headers();self.close_connection=True
   while True:
    try:part=next(streamer)
    except queue.Empty:
     self.wfile.write(b': heartbeat\n\n');self.wfile.flush();continue
    except StopIteration:break
    send({'id':rid,'model':repo,'choices':[{'index':0,'delta':{'content':part},'finish_reason':None}]})
   thread.join()
   if state.get('error'):send({'error':state['error']});return
   ids=state['tokens'];text=tokenizer.decode(ids,skip_special_tokens=True);(directory/'output.txt').write_text(text)
   for c in captures:
    index=c['forward_call'];c['input_token_text']=tokenizer.decode([ids[index-1]]) if index>0 else ''
   sys.path.insert(0,str(Path(__file__).resolve().parents[1]));from svg_output import inspect_svg
   result={'identity':request_identity,'generated_token_ids':ids,'generated_tokens':len(ids),'seconds':state['seconds'],'recorded_vectors':len(captures),'captures':captures,'layers':[0,31,63],'capture_steps_requested':cfg['max_new_tokens'],'length_bound_reached':len(ids)>=cfg['max_new_tokens'],'svg':inspect_svg(text),'source_request_sha256':sourcehash};write(directory/'result.json',result);emit(directory)
   summary=json.loads((directory/'research.json').read_text());summary['comparison_metadata']={'comparison_run_id':self.headers.get('X-Comparison-Run-Id'),'comparison_model':self.headers.get('X-Comparison-Model')};summary['title']='Qwen3.8 official live · '+r['messages'][-1]['content'][:80];write(directory/'research.json',summary)
   send({'id':rid,'model':repo,'research_id':rid,'activation_capture':{'research_id':rid,'kind':'live_instrumented_inference','source_request_sha256':sourcehash},'choices':[{'index':0,'delta':{},'finish_reason':'length' if result['length_bound_reached'] else 'stop'}],'usage':{'prompt_tokens':inputs.input_ids.shape[1],'completion_tokens':len(ids),'total_tokens':inputs.input_ids.shape[1]+len(ids)},'timings':{'predicted_n':len(ids),'predicted_ms':state['seconds']*1000,'predicted_per_second':len(ids)/state['seconds'],'scope':'instrumented_prefill_and_decode'}})
   subprocess.Popen(['/home/chaiwithjai/bonsai-workspace/venv/bin/python',str(Path(__file__).with_name('log_official_live.py')),str(directory)],stdout=(directory/'mlflow.log').open('w'),stderr=subprocess.STDOUT)
   self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
  except (BrokenPipeError,ConnectionResetError):cancel.set()
  finally:
   cancel.set();thread.join();active=False;lock.release()
print('Official BF16 server ready on127.0.0.1:'+str(a.port),flush=True);ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
