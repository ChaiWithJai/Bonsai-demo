import json,sys
from pathlib import Path
import mlflow
p=Path(sys.argv[1]);r=json.loads((p/'result.json').read_text());req=json.loads((p/'request.json').read_text());identity=r['identity']
mlflow.set_tracking_uri('sqlite:////home/chaiwithjai/bonsai-workspace/mlflow.db');mlflow.set_experiment('official-live-comparison')
with mlflow.start_run(run_name='Qwen3.8 official live '+p.name) as run:
 mlflow.set_tags({'kind':'same_execution_live_inference','research_id':p.name,**{k:str(v) for k,v in json.loads((p/'research.json').read_text()).get('comparison_metadata',{}).items() if v is not None}})
 mlflow.log_params({'repo':identity['repo'],'revision':identity['revision'],'weight_dtype':'bfloat16','source_request_sha256':r['source_request_sha256']})
 mlflow.log_metrics({'generated_tokens':r['generated_tokens'],'instrumented_seconds':r['seconds'],'recorded_vectors':r['recorded_vectors']})
 with mlflow.start_span(name='recorded_inference_artifact_import',span_type='LLM') as span:
  span.set_attributes({'span_timing_scope':'post_run_artifact_import; not inference wall-clock duration','recorded_instrumented_seconds':r['seconds']});span.set_inputs(req);span.set_outputs({'text':(p/'output.txt').read_text(),'research_id':p.name,'recorded_vectors':r['recorded_vectors']})
 meta={'run_id':run.info.run_id,'experiment_id':run.info.experiment_id,'trace_id':span.trace_id}
 (p/'mlflow.json').write_text(json.dumps(meta))
 s=json.loads((p/'research.json').read_text());s.update(meta,mlflow_url=f'http://127.0.0.1:5210/#/experiments/{run.info.experiment_id}/runs/{run.info.run_id}');(p/'research.json').write_text(json.dumps(s,indent=2))
 c=json.loads((p/'activation-capture.json').read_text());c['mlflow']=meta;(p/'activation-capture.json').write_text(json.dumps(c,indent=2))
 mlflow.log_artifacts(str(p),'inference')
