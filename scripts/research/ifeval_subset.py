#!/usr/bin/env python3
"""First10 pinned official IFEval prompts scored with unmodified strict evaluator."""
import sys,json,time,dataclasses,importlib.metadata,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.cache/ifeval-deps'))
sys.path.insert(0,str(ROOT/'docs/research-20260918/ifeval-official'))
import requests,mlflow
from instruction_following_eval import evaluation_lib
ap=argparse.ArgumentParser();ap.add_argument('--resume',type=Path);ap.add_argument('--disable-thinking',action='store_true');args=ap.parse_args()
OUT=args.resume or ROOT/'docs/research-20260918/ifeval-subset'/time.strftime('%Y%m%d-%H%M%S');OUT.mkdir(parents=True,exist_ok=bool(args.resume))
def save(name,x):(OUT/name).write_text(json.dumps(x,indent=2))
source=ROOT/'docs/research-20260918/ifeval-official';items=evaluation_lib.read_prompt_list(str(source/'data__input_data.jsonl'))[:10]
s=requests.Session();model=s.get('http://127.0.0.1:8081/v1/models',timeout=10).json()['data'][0]['id']
settings=dict(temperature=1.0,top_p=.95,top_k=20,min_p=0,repeat_penalty=1,presence_penalty=0,frequency_penalty=0,max_tokens=1024,thinking_budget_tokens=0,seed=42,stream=False,cache_prompt=False)
if args.disable_thinking:settings['chat_template_kwargs']={'enable_thinking':False}
protocol={'dataset_and_evaluator_revision':'4700efb9afa54286b0e04473ba80a13e8461e25f','source_manifest':json.loads((source/'sources.json').read_text()),'selection':'First10 official input_data.jsonl rows','model':model,'manifest':json.loads((ROOT/'.cache/bonsai/release-manifest.json').read_text()),'settings':settings,'dependencies':{x:importlib.metadata.version(x) for x in ['absl-py','langdetect','nltk','immutabledict']},'deviations':['10 fixed prompts, not full541-item IFEval','1024 output tokens versus paper32768','Thinking disabled versus paper xhigh','GB10 llama.cpp versus H100 vLLM','Fixed seed42'],'grading':'Unmodified official test_instruction_following_strict; no response transformations; prompt-level strict'}
if not args.resume:save('protocol.json',protocol)
save('selected-inputs.json',[dataclasses.asdict(x) for x in items]);results=[]
mlflow.set_tracking_uri('http://127.0.0.1:5210');mlflow.set_experiment('IFEval bounded official strict subset')
prior=json.loads((OUT/'mlflow.json').read_text()) if args.resume else {}
with mlflow.start_run(run_id=prior.get('run_id'),run_name='Bonsai2 first10 IFEval strict'+(' explicit thinking disabled' if args.disable_thinking else '')) as run:
 save('mlflow.json',{'run_id':run.info.run_id,'experiment_id':run.info.experiment_id});mlflow.log_params(settings);mlflow.set_tags({'scope':'bounded_subset_not_paper_reproduction','dataset_revision':protocol['dataset_and_evaluator_revision']})
 start=time.time()
 try:
  for i,item in enumerate(items):
   if time.time()-start>540:break
   req={'model':model,'messages':[{'role':'user','content':item.prompt}],**settings};save(f'{i:02}-request.json',req)
   t=time.time();cached=OUT/f'{i:02}-response.json'
   if cached.exists():response=json.loads(cached.read_text())
   else:
    response=s.post('http://127.0.0.1:8081/v1/chat/completions',json=req,timeout=(10,90));response.raise_for_status();response=response.json();save(f'{i:02}-response.json',response)
   answer=response['choices'][0]['message'].get('content') or ''
   graded=evaluation_lib.test_instruction_following_strict(item,{item.prompt:answer})
   result={'index':i,'key':item.key,**dataclasses.asdict(graded),'elapsed_seconds':time.time()-t,'finish_reason':response['choices'][0].get('finish_reason')};results.append(result);save('results.json',results)
   print(json.dumps({'index':i,'passed':graded.follow_all_instructions,'instructions':graded.follow_instruction_list,'elapsed':result['elapsed_seconds']}),flush=True)
 finally:
  summary={'completed':len(results),'prompt_strict_correct':sum(x['follow_all_instructions'] for x in results),'prompt_strict_accuracy':sum(x['follow_all_instructions'] for x in results)/len(results) if results else 0,'truncated':sum(x['finish_reason']=='length' for x in results),'scope':'Bounded first10 subset; not full IFEval or paper reproduction'}
  save('summary.json',summary);mlflow.log_metrics({k:v for k,v in summary.items() if isinstance(v,(int,float))});mlflow.log_artifacts(str(OUT),'evidence');mlflow.log_artifact(__file__,'runner')
print(OUT,flush=True)
