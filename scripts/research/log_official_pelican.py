#!/usr/bin/env python3
"""Log local actual BF16 evaluation with the existing MLflow environment."""
import argparse,json
from pathlib import Path
import mlflow
p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--tracking-uri',required=True);a=p.parse_args()
r=json.loads((a.directory/'result.json').read_text());identity=r['identity']
mlflow.set_tracking_uri(a.tracking_uri);mlflow.set_experiment('official-pelican-research')
with mlflow.start_run(run_name=identity['repo']+' official pelican') as run:
 mlflow.set_tags({'kind':'official_same_execution_activation_capture','model_repository':identity['repo'],'model_revision':identity['revision'],'weight_format':identity.get('weight_format',identity.get('weight_dtype','unknown'))})
 mlflow.log_params({'model':identity['repo'],'revision':identity['revision'],'weight_dtype':identity.get('weight_dtype','native_packed_ternary'),'source_request_sha256':r['source_request_sha256'],'layers':','.join(map(str,r['layers']))})
 mlflow.log_metrics({k:v for k,v in {'generated_tokens':r['generated_tokens'],'instrumented_seconds':r['seconds'],'recorded_vectors':r['recorded_vectors'],'svg_valid':int(r['svg'].get('valid',False))}.items() if v is not None})
 with mlflow.start_span(name='recorded_inference_artifact_import',span_type='LLM') as span:
  span.set_inputs(json.loads((a.directory/'request.json').read_text()))
  span.set_attributes({'model_repository':identity['repo'],'model_revision':identity['revision'],'activation_artifact_directory':str(a.directory),'same_execution_activations':True,'span_timing_scope':'post_run_artifact_import; not inference wall-clock duration','recorded_instrumented_seconds':r['seconds']})
  span.set_outputs({'text':(a.directory/'output.txt').read_text(),'generated_tokens':r['generated_tokens'],'recorded_vectors':r['recorded_vectors']})
 mlflow.log_artifacts(str(a.directory),'inference')
 (a.directory/'mlflow.json').write_text(json.dumps({'run_id':run.info.run_id,'experiment_id':run.info.experiment_id,'trace_id':span.trace_id}))
