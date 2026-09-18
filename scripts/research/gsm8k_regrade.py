#!/usr/bin/env python3
"""Regrade saved GSM8K outputs, preserving first-pass scores; no inference."""
import argparse,json,re
from pathlib import Path
from decimal import Decimal,InvalidOperation

def extract(text):
 starts=[m.end() for m in re.finditer(r'\\boxed\{',text)]
 if not starts:return None
 start=starts[-1];depth=1;end=start
 while end<len(text) and depth:
  if text[end]=='{':depth+=1
  elif text[end]=='}':depth-=1
  end+=1
 if depth:return None
 value=re.sub(r'\\text\{[ A-Za-z]+\}', '', text[start:end-1]).replace('{,}',',').replace('\\,','').replace('\\$','').replace('$','').replace(',','').strip()
 if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?',value):return None
 try:return str(Decimal(value).normalize())
 except InvalidOperation:return None

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
 results=json.loads((a.directory/'results.json').read_text());out=[]
 for item in results:
  response=json.loads((a.directory/f"{item['index']:02}-response.json").read_text())
  prediction=extract(response['choices'][0]['message'].get('content') or '')
  out.append({**item,'initial_extracted_answer':item['extracted_answer'],'initial_correct':item['correct'],'extracted_answer':prediction,'correct':prediction==item['gold_answer'] if prediction is not None else False,'unparsed':prediction is None})
 summary={'scope':'Same saved inference; balanced-box numeric-normalization regrade','completed':len(out),'correct':sum(x['correct'] for x in out),'unparsed':sum(x['unparsed'] for x in out),'accuracy':sum(x['correct'] for x in out)/len(out),'reason':'Initial parser did not normalize nested LaTeX thousands separators or text units; initial results retained.'}
 (a.directory/'regraded-results.json').write_text(json.dumps(out,indent=2));(a.directory/'regraded-summary.json').write_text(json.dumps(summary,indent=2))
 import mlflow
 mlflow.set_tracking_uri('http://127.0.0.1:5210');run=json.loads((a.directory/'mlflow.json').read_text())
 with mlflow.start_run(run_id=run['run_id']):
  mlflow.log_metrics({'regraded_'+k:v for k,v in summary.items() if isinstance(v,(int,float))});mlflow.log_artifact(str(a.directory/'regraded-results.json'),'evidence');mlflow.log_artifact(str(a.directory/'regraded-summary.json'),'evidence');mlflow.log_artifact(__file__,'grading-source')
 print(json.dumps(summary,indent=2))
