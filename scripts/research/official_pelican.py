#!/usr/bin/env python3
"""Offline official BF16 evaluation; hooks measure this execution, not a replay.
Uses an already downloaded pinned HF snapshot. Never downloads model weights.
"""
import argparse, hashlib, json, math, os, struct, subprocess, sys, time
from pathlib import Path

MODELS = {
 'Qwen/Qwen3.8-27B': '1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0',
 'Qwen/Qwen3.6-27B': '6a9e13bd6fc8f0983b9b99948120bc37f49c13e9',
}
PROMPT = 'Generate an SVG of a pelican riding a bicycle'

def write(path, obj):
 path.write_text(json.dumps(obj, indent=2, ensure_ascii=False))

def verify_safetensors(snapshot):
 index=json.loads((snapshot/'model.safetensors.index.json').read_text())
 weight_map=index['weight_map'];expected_shards=set(weight_map.values())
 observed={};parameter_count=0;manifest=[]
 for name in sorted(expected_shards):
  if Path(name).name!=name:raise ValueError('Unsafe shard path')
  path=snapshot/name
  with path.open('rb') as f:
   header_length=struct.unpack('<Q',f.read(8))[0]
   if header_length>64*1024*1024:raise ValueError('Unreasonable tensor header')
   header=json.loads(f.read(header_length))
  max_offset=0
  for key,tensor in header.items():
   if key=='__metadata__':continue
   if key in observed or weight_map.get(key)!=name:raise ValueError('Shard/index tensor mismatch')
   if tensor['dtype']!='BF16':raise ValueError('Official weight is not BF16')
   count=math.prod(tensor['shape']);start,end=tensor['data_offsets']
   if end-start!=count*2 or start<0:raise ValueError('Invalid tensor byte count')
   max_offset=max(max_offset,end);parameter_count+=count;observed[key]=name
  if path.stat().st_size!=8+header_length+max_offset:raise ValueError('Incomplete safetensors shard')
  manifest.append({'name':name,'bytes':path.stat().st_size,'cache_blob':path.resolve().name})
 if observed!=weight_map:raise ValueError('Incomplete checkpoint tensor set')
 if parameter_count!=27781427952:raise ValueError(f'Unexpected official parameter count: {parameter_count}')
 return manifest,parameter_count

def audit_functional_shapes(snapshot):
 import torch
 from transformers import AutoConfig,AutoModelForImageTextToText
 weights={}
 for path in snapshot.glob('*.safetensors'):
  with path.open('rb') as f:header=json.loads(f.read(struct.unpack('<Q',f.read(8))[0]))
  weights.update({k:v['shape'] for k,v in header.items() if k!='__metadata__'})
 with torch.device('meta'):
  model=AutoModelForImageTextToText.from_config(AutoConfig.from_pretrained(snapshot,local_files_only=True),dtype=torch.bfloat16)
 functional={k:list(v.shape) for k,v in model.state_dict().items()}
 missing=set(functional)-set(weights)
 mismatched=[k for k in functional if k in weights and functional[k]!=weights[k]]
 excluded={k:v for k,v in weights.items() if k not in functional}
 allowed={'mtp.fc.weight':[5120,10240], 'mtp.layers.0.mlp.down_proj.weight':[5120,17408],
 'mtp.layers.0.mlp.gate_proj.weight':[17408,5120], 'mtp.layers.0.mlp.up_proj.weight':[17408,5120],
 'mtp.layers.0.self_attn.k_proj.weight':[1024,5120], 'mtp.layers.0.self_attn.q_proj.weight':[12288,5120],
 'mtp.layers.0.self_attn.v_proj.weight':[1024,5120], 'mtp.layers.0.input_layernorm.weight':[5120],
 'mtp.layers.0.post_attention_layernorm.weight':[5120], 'mtp.layers.0.self_attn.k_norm.weight':[256],
 'mtp.layers.0.self_attn.o_proj.weight':[5120,6144], 'mtp.layers.0.self_attn.q_norm.weight':[256],
 'mtp.norm.weight':[5120], 'mtp.pre_fc_norm_embedding.weight':[5120], 'mtp.pre_fc_norm_hidden.weight':[5120]}
 if missing or mismatched or excluded!=allowed:raise ValueError(f'Functional checkpoint coverage mismatch: missing={missing}, mismatched={mismatched}, excluded={excluded}')
 active=sum(p.numel() for p in model.parameters());excluded_count=sum(math.prod(v) for v in excluded.values())
 if active!=27356728560 or excluded_count!=424699392:raise ValueError('Unexpected functional/MTP parameter counts')
 return {'checkpoint_parameters':27781427952,'loaded_model_parameters':active,
 'excluded_auxiliary_mtp_parameters':excluded_count,'excluded_auxiliary_mtp_shapes':excluded,
 'functional_tensor_count':len(functional),'missing_functional_keys':[], 'mismatched_functional_keys':[],
 'scope':'Standard autoregressive generation; official Transformers Qwen3_5PreTrainedModel explicitly ignores ^mtp.* auxiliary multi-token prediction weights. Vision parameters loaded but unused for this text-only prompt.'}

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--model',choices=MODELS,required=True)
 p.add_argument('--output',type=Path,required=True)
 p.add_argument('--snapshot-path',type=Path,help='Existing official revision directory outside the HF cache')
 p.add_argument('--max-new-tokens',type=int,default=4096)
 p.add_argument('--capture-steps',type=int,default=4096)
 p.add_argument('--layers',default='0,31,63')
 p.add_argument('--seed',type=int,default=42)
 p.add_argument('--tracking-uri',default='sqlite:////home/chaiwithjai/bonsai-workspace/mlflow.db')
 p.add_argument('--mlflow-python',default='/home/chaiwithjai/bonsai-workspace/venv/bin/python')
 a=p.parse_args()
 if not 1 <= a.max_new_tokens <= 8192 or not 1 <= a.capture_steps <= 8192: p.error('Token/capture bound exceeded')
 a.output.mkdir(parents=True,exist_ok=False)
 source_dir=a.output/'runtime-source';source_dir.mkdir()
 source_hashes={}
 for source in [Path(__file__),Path(__file__).with_name('research_envelope.py'),Path(__file__).with_name('log_official_pelican.py'),Path(__file__).resolve().parents[1]/'svg_output.py']:
  data=source.read_bytes();(source_dir/source.name).write_bytes(data)
  source_hashes[source.name]=hashlib.sha256(data).hexdigest()
 os.environ['HF_HUB_OFFLINE']='1'
 # Transformers 5.5 otherwise schedules all weight copies into futures.
 # Its supported synchronous path materializes each tensor only when assigned.
 os.environ['HF_DEACTIVATE_ASYNC_LOAD']='1'
 import torch, transformers
 from huggingface_hub import snapshot_download
 from transformers import AutoModelForImageTextToText, AutoTokenizer, GenerationConfig
 snapshot=a.snapshot_path.resolve() if a.snapshot_path else Path(snapshot_download(a.model,revision=MODELS[a.model],local_files_only=True))
 if snapshot.name!=MODELS[a.model]:raise ValueError('Snapshot directory must match pinned revision')
 config=json.loads((snapshot/'config.json').read_text())
 if config.get('quantization_config'): raise ValueError('Quantized checkpoints are forbidden')
 manifest,expected_parameters=verify_safetensors(snapshot)
 functional_audit=audit_functional_shapes(snapshot)
 write(a.output/'functional-weight-audit.json',functional_audit)
 request={'messages':[{'role':'user','content':PROMPT}], 'max_new_tokens':a.max_new_tokens,
 'temperature':0.3,'top_p':0.95,'top_k':20,'min_p':0.0,'repetition_penalty':1.0,'seed':a.seed,'enable_thinking':False}
 write(a.output/'request.json',request)
 request_hash=hashlib.sha256((a.output/'request.json').read_bytes()).hexdigest()
 identity={'repo':a.model,'revision':MODELS[a.model],'weight_dtype':'bfloat16','quantized':False,
 'runtime_source_sha256':source_hashes,'sampler_order':['temperature','top_k','top_p','min_p','draw'],
 'functional_weight_audit':functional_audit,'snapshot':str(snapshot),'shards':manifest,'torch':torch.__version__,'transformers':transformers.__version__,
 'loader':'transformers_from_pretrained_synchronous','loader_environment':{'HF_DEACTIVATE_ASYNC_LOAD':'1'},
 'device':torch.cuda.get_device_name(),'capture_kind':'same_execution_forward_hooks',
 'source_request_sha256':request_hash,'instrumented_timing':True,
 'interpretation':'Decoder residual outputs, not weight changes; neuron dimensions are not semantically aligned across models.'}
 write(a.output/'identity.json',identity)
 tokenizer=AutoTokenizer.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False)
 rendered=tokenizer.apply_chat_template(request['messages'],tokenize=False,add_generation_prompt=True,enable_thinking=False)
 (a.output/'rendered-prompt.txt').write_text(rendered)
 inputs=tokenizer(rendered,return_tensors='pt',add_special_tokens=False).to('cuda')
 write(a.output/'input-tokens.json',inputs['input_ids'][0].tolist())
 torch.manual_seed(a.seed); torch.cuda.manual_seed_all(a.seed)
 started=time.monotonic()
 model,loading_info=AutoModelForImageTextToText.from_pretrained(snapshot,local_files_only=True,trust_remote_code=False,
     dtype=torch.bfloat16,device_map='cuda',attn_implementation='sdpa',output_loading_info=True)
 model.eval()
 loading_info={key:sorted(value) if isinstance(value,set) else value for key,value in loading_info.items()}
 write(a.output/'loading-info.json',loading_info)
 if any(loading_info.get(k) for k in ('missing_keys','mismatched_keys','error_msgs','conversion_errors')):raise ValueError('Official loader reported missing/mismatched functional weights')
 if any(not k.startswith('mtp.') for k in loading_info.get('unexpected_keys',[])):raise ValueError('Unexpected non-MTP weights')
 identity['parameter_count']=sum(t.numel() for t in model.parameters())
 if identity['parameter_count']!=functional_audit['loaded_model_parameters']:raise ValueError('Loaded parameter count differs from verified checkpoint')
 identity['parameter_dtypes']=sorted({str(t.dtype) for t in model.parameters()})
 identity['load_seconds']=time.monotonic()-started
 if any(t.dtype!=torch.bfloat16 for t in model.parameters() if t.is_floating_point()):
  raise ValueError('Model contains unexpected non-BF16 parameters')
 write(a.output/'identity.json',identity)
 layers=model.model.language_model.layers
 selected=[int(x) for x in a.layers.split(',')]
 if len(set(selected))!=len(selected) or any(i<0 or i>=len(layers) for i in selected): raise ValueError('Invalid layers')
 counters={i:0 for i in selected}; captures=[]; handles=[]
 # Forward call zero is the entire prefill and predicts generated token zero.
 # Forward call N>0 consumes generated token N-1 and predicts token N.
 def hook_for(layer):
  def hook(module,args,output):
   call=counters[layer]; counters[layer]+=1
   if call>=a.capture_steps+1:return
   tensor=output[0] if isinstance(output,tuple) else output
   vector=tensor[0,-1,:].detach().float().cpu().contiguous()
   if not torch.isfinite(vector).all(): raise ValueError('Nonfinite activation vector')
   filename=f'layer-{layer:02d}-forward-{call:04d}.f32'
   (a.output/filename).write_bytes(vector.numpy().astype('<f4').tobytes())
   captures.append({'layer':layer,'forward_call':call,'phase':'prefill_last_position' if call==0 else 'decode',
      'predicts_generated_token_index':call,'consumes_generated_token_index':None if call==0 else call-1,
      'dimensions':vector.numel(),'dtype':'float32 little-endian','file':filename,
      'mean':vector.mean().item(),'rms':vector.square().mean().sqrt().item(),
      'min':vector.min().item(),'max':vector.max().item()})
  return hook
 for i in selected:handles.append(layers[i].register_forward_hook(hook_for(i)))
 torch.cuda.synchronize();started=time.monotonic()
 try:
  with torch.inference_mode():
   official_generation=json.loads((snapshot/'generation_config.json').read_text())
   generation=GenerationConfig(max_new_tokens=a.max_new_tokens,do_sample=True,temperature=.3,
      top_p=.95,top_k=20,min_p=0.0,repetition_penalty=1.,encoder_repetition_penalty=1.,
      no_repeat_ngram_size=0,num_beams=1,typical_p=1.,epsilon_cutoff=0.,eta_cutoff=0.,
      forced_bos_token_id=None,forced_eos_token_id=None,bad_words_ids=None,suppress_tokens=None,
      begin_suppress_tokens=None,renormalize_logits=False,use_cache=True,return_dict_in_generate=True,
      bos_token_id=official_generation.get('bos_token_id'),eos_token_id=official_generation.get('eos_token_id'),
      pad_token_id=official_generation.get('pad_token_id'))
   write(a.output/'effective-generation-config.json',generation.to_dict())
   output=model.generate(**inputs,generation_config=generation)

  torch.cuda.synchronize();elapsed=time.monotonic()-started
 finally:
  for h in handles:h.remove()
 generated=output.sequences[0,inputs['input_ids'].shape[1]:].tolist()
 for c in captures:
  index=c['predicts_generated_token_index']
  c['input_token_text']=tokenizer.decode([generated[index-1]]) if index>0 else ''
  c['predicted_token_id']=generated[index] if index<len(generated) else None
  c['predicted_token_text']=tokenizer.decode([generated[index]]) if index<len(generated) else None
 text=tokenizer.decode(generated,skip_special_tokens=True)
 (a.output/'output.txt').write_text(text)
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
 from svg_output import inspect_svg
 svg=inspect_svg(text)
 if svg.get('valid'):(a.output/'output.svg').write_text(svg['source'])
 result={'generated_token_ids':generated,'generated_tokens':len(generated),'seconds':elapsed,
 'tokens_per_second_instrumented':len(generated)/elapsed,'length_bound_reached':len(generated)>=a.max_new_tokens,
 'svg':svg,'source_request_sha256':request_hash,'layers':selected,'capture_steps_requested':a.capture_steps,
 'recorded_vectors':len(captures),'captures':captures,'identity':identity}
 write(a.output/'result.json',result)
 from research_envelope import emit
 emit(a.output)
 subprocess.run([a.mlflow_python,str(Path(__file__).with_name('log_official_pelican.py')),
  '--directory',str(a.output),'--tracking-uri',a.tracking_uri],check=True)
 from research_envelope import emit
 emit(a.output)
 print(json.dumps({'output':str(a.output),'model':a.model,'svg_valid':svg.get('valid'),'vectors':len(captures)}))

if __name__=='__main__':main()
