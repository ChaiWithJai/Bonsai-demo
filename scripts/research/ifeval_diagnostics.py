#!/usr/bin/env python3
"""Record observed final/reasoning lengths without altering official strict grades."""
import sys,json
from pathlib import Path
p=Path(sys.argv[1]);rows=[]
for f in sorted(p.glob('*-response.json')):
 d=json.loads(f.read_text());c=d['choices'][0];m=c['message'];rows.append({'index':int(f.name.split('-')[0]),'finish_reason':c.get('finish_reason'),'reasoning_characters':len(m.get('reasoning_content') or ''),'final_characters':len(m.get('content') or ''),'usage':d.get('usage'),'output_starved':not bool((m.get('content') or '').strip())})
result={'scope':'Runtime diagnostic, not capability metric','items':rows,'empty_final_count':sum(x['output_starved'] for x in rows),'length_finish_count':sum(x['finish_reason']=='length' for x in rows)}
(p/'runtime-diagnostics.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
import mlflow
mlflow.set_tracking_uri('http://127.0.0.1:5210');run=json.loads((p/'mlflow.json').read_text())
with mlflow.start_run(run_id=run['run_id']):
 mlflow.log_artifact(str(p/'runtime-diagnostics.json'),'evidence');mlflow.log_metrics({'empty_final_count':result['empty_final_count'],'length_finish_count':result['length_finish_count']})
