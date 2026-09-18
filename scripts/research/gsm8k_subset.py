#!/usr/bin/env python3
"""First 10 official GSM8K test items; bounded local rule-only replication."""
import hashlib,json,re,time
from decimal import Decimal, InvalidOperation
from pathlib import Path
import requests,mlflow
ROOT=Path(__file__).resolve().parents[2]
REV='3101c7d5072418e28b9008a6636bde82a006892c'
URL=f'https://raw.githubusercontent.com/openai/grade-school-math/{REV}/grade_school_math/data/test.jsonl'
OUT=ROOT/'docs/research-20260918/gsm8k-subset'/time.strftime('%Y%m%d-%H%M%S')
OUT.mkdir(parents=True)
def save(name,x):(OUT/name).write_text(json.dumps(x,indent=2))
def number(x):
 try:return str(Decimal(x.replace(',','').replace('$','').strip()).normalize())
 except InvalidOperation:return None
s=requests.Session();raw=s.get(URL,timeout=30);raw.raise_for_status();(OUT/'official-test.jsonl').write_bytes(raw.content)
items=[json.loads(x) for x in raw.text.splitlines()][:10]
model=s.get('http://127.0.0.1:8081/v1/models',timeout=10).json()['data'][0]['id']
manifest=json.loads((ROOT/'.cache/bonsai/release-manifest.json').read_text())
settings=dict(temperature=1.0,top_p=.95,top_k=20,min_p=0,repeat_penalty=1,presence_penalty=0,frequency_penalty=0,max_tokens=1024,thinking_budget_tokens=128,seed=42,stream=False,cache_prompt=False)
meta={'dataset_url':URL,'revision':REV,'sha256':hashlib.sha256(raw.content).hexdigest(),'selection':'First10 official test rows in original file order','settings':settings,'model':model,'manifest':manifest,'deviations':['10 of1319 test items; not full benchmark','1024 total output cap vs paper32768','Thinking budget128 vs paper xhigh','GB10 llama.cpp PQ2_0 rather than H100 vLLM','Fixed seed42; rule-only final boxed-answer extraction; no LLM judge']}
save('protocol.json',meta)
mlflow.set_tracking_uri('http://127.0.0.1:5210');mlflow.set_experiment('GSM8K bounded official test subset')
results=[]
with mlflow.start_run(run_name='Bonsai2 first10 fixed GSM8K items') as run:
 save('mlflow.json',{'run_id':run.info.run_id,'experiment_id':run.info.experiment_id})
 mlflow.set_tags({'scope':'bounded_subset_not_paper_reproduction','dataset_revision':REV,'checkpoint_repo':manifest['checkpoint']['repo']})
 mlflow.log_params(settings)
 try:
  for i,item in enumerate(items):
   prompt=item['question']+'\nPlease reason step by step, and put your final answer within \\boxed{}.'
   req={'model':model,'messages':[{'role':'user','content':prompt}],**settings};save(f'{i:02}-request.json',req)
   start=time.time();r=s.post('http://127.0.0.1:8081/v1/chat/completions',json=req,timeout=(10,240));r.raise_for_status();data=r.json();save(f'{i:02}-response.json',data)
   content=data['choices'][0]['message'].get('content') or ''; matches=re.findall(r'\\boxed\{\s*([^{}]+)\s*\}',content)
   predicted=number(matches[-1]) if matches else None;gold=number(item['answer'].split('####')[-1]);passed=predicted==gold if predicted is not None else False
   result={'index':i,'question':item['question'],'gold_answer':gold,'extracted_answer':predicted,'correct':passed,'unparsed':predicted is None,'finish_reason':data['choices'][0].get('finish_reason'),'elapsed_seconds':time.time()-start}
   results.append(result);save('results.json',results);print(json.dumps(result),flush=True)
   mlflow.log_metric('item_correct',int(passed),step=i)
 finally:
  summary={'completed':len(results),'correct':sum(x['correct'] for x in results),'unparsed':sum(x['unparsed'] for x in results),'accuracy':sum(x['correct'] for x in results)/len(results) if results else None,'scope':'First10 bounded rule-only local subset, not full-paper reproduction'}
  save('summary.json',summary);mlflow.log_metrics({k:v for k,v in summary.items() if isinstance(v,(int,float))});mlflow.log_artifacts(str(OUT),artifact_path='evidence')
print(str(OUT),flush=True)
