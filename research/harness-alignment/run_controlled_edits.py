"""Run the frozen development protocol through the live Workspace model queue.

Never retries a mutation. Interrupted or uncertain attempts must be inspected before
another invocation. Existing output directories are refused.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from workspace_compare import compare

BASE='http://127.0.0.1:5257'
STORE=ROOT/'.cache/workspace-live-v3-20260921/workspace'


def api(path, body=None):
    request=Request(BASE+'/api/workspace'+path, data=json.dumps(body).encode() if body is not None else None,
                    headers={'Content-Type':'application/json'})
    with urlopen(request,timeout=15) as response:return json.load(response)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    protocol_path=ROOT/'research/harness-alignment/CONTROLLED-EDIT-PROTOCOL.json'
    protocol=json.loads(protocol_path.read_text())
    state=api('')
    if state['running_attempts'] or state['running_source_jobs']:raise RuntimeError('Workspace model lane is busy')
    if state['model_info']!=protocol['model_info']:raise RuntimeError('Runtime identity changed from the frozen protocol')
    source=api('/'+protocol['source_workspace_id'])
    if source['head']!=protocol['source_revision']:raise RuntimeError('Starting project changed')
    if hashlib.sha256(json.dumps(source['fixture'],sort_keys=True).encode()).hexdigest()!=protocol['dataset_sha256']:
        raise RuntimeError('Source fixture changed')
    sources={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
             for path in list((ROOT/'scripts').glob('workspace*.py'))+list((ROOT/'scripts/workspace-tools').glob('*.mjs'))}
    manifest={'protocol':protocol,'protocol_sha256':hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
              'git_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'harness_sources':sources,'execution_status':'running'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'source-workspace.json').write_text(json.dumps(source,indent=2)+'\n')
    from mlflow import MlflowClient
    client=MlflowClient('http://127.0.0.1:5210')
    results=[];comparison_rows=[]
    for index,configuration in enumerate(protocol['order']):
        for name,sha in sources.items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise RuntimeError('Harness changed during trials')
        status=api('')
        if status['running_attempts'] or status['running_source_jobs']:raise RuntimeError('Workspace became busy; no trial started')
        folder=out/f'trial-{index+1}';folder.mkdir()
        intent={'phase':'copy_requested','configuration':configuration}
        def record(): (folder/'state.json').write_text(json.dumps(intent,indent=2)+'\n')
        record()
        copied=api('/'+source['id']+'/trial-copy',{'base_revision':source['head'],
                   'title':f'Development trial {index+1} · {configuration["profile"]}'})
        trial=copied['workspace'];intent.update(workspace_id=trial['id'],phase='prepared');record()
        assert trial['head']==protocol['trial_base_revision'] and not trial['attempts']
        assert trial['fixture']==source['fixture'] and trial['files']==source['files']
        intent['phase']='attempt_requested';record()
        started=api('/'+trial['id']+'/attempts',{'base_revision':trial['head'],'request':protocol['request'],
                    'case':'baseline','request_checks':protocol['request_checks'],'generation_config':configuration})
        aid=started['attempt_id'];intent.update(attempt_id=aid,phase='running');record()
        print(json.dumps({'started':index+1,**intent}),flush=True)
        deadline=time.monotonic()+700
        while True:
            if time.monotonic()>deadline:raise RuntimeError('Observation deadline reached. Inspect saved attempt; do not restart it.')
            try:
                current=api('/'+trial['id'])
                current_status=api('')
            except Exception as exc:
                intent['observation_error']=str(exc);record();time.sleep(2);continue
            attempt=next(a for a in current['attempts'] if a['id']==aid)
            if attempt['status']!='running' and aid not in current_status['running_attempts']:break
            time.sleep(2)
        summary=json.loads((STORE/'attempts'/aid/'summary.json').read_text())
        if summary.get('generation_config')!=configuration:raise RuntimeError('Attempt did not use requested configuration')
        run=client.get_run(summary['run_id'])
        row={'run_id':summary['run_id'],'url':summary.get('mlflow_url'),
             'tags':{k:v for k,v in run.data.tags.items() if not k.startswith('mlflow.')},
             'outcome':{k:summary.get(k) for k in ('status','error','elapsed_seconds','repairs','trace_id','verification_scope','request_verification')},
             'browser_check':(summary.get('check') or {}).get('report'),'loop_detection':summary.get('loop_detection')}
        comparison_rows.append(row)
        (folder/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        intent.update(phase='terminal',status=summary['status'],run_id=summary['run_id']);record()
        results.append({'trial':index+1,'workspace_id':trial['id'],'configuration':configuration,**summary})
        (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
        print(json.dumps({'finished':index+1,'status':summary['status'],'run_id':summary['run_id'],'repairs':summary['repairs'],'error':summary.get('error')}),flush=True)
        if len(comparison_rows)>1:
            report=compare(comparison_rows)
            (out/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
            if not report['task_metadata_matches']:raise RuntimeError('Frozen task metadata did not match; preserve evidence and stop')
        if summary.get('trace_export_error'):raise RuntimeError('Attempt evidence export failed; stop trials')
    manifest['execution_status']='terminal'
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Controlled development trials terminal',flush=True)


if __name__=='__main__':main()
