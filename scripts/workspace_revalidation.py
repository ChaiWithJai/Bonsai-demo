"""Revalidate frozen model output under current contracts without inference."""
import hashlib
import json
from pathlib import Path
import shutil
import time
import uuid
from workspace_data.proposal import validate_proposal, validate_schema_repair_preservation
from workspace_store import RevisionConflict


def revalidate(jobs, jid):
    with jobs.worker.guard:
        parent=jobs.get(jid)
        if parent['status']!='failed' or parent.get('planning_run_id'):
            raise RevisionConflict('Choose a failed proposal attempt, not a confirmed build')
        source=jobs.root/jid
        responses=[source/f'model-{i}.json' for i in range(2) if (source/f'model-{i}.json').is_file()]
        if not responses:
            raise ValueError('This attempt has no saved model response to revalidate')
        required=['source-manifest.json','source-packet.json','profile.json','model-info.json']
        if any(not (source/name).is_file() for name in required):
            raise ValueError('The saved proposal evidence is incomplete')
        ident=uuid.uuid4().hex;folder=jobs.root/ident;folder.mkdir()
        for name in required+['original-manifest.json']:
            if (source/name).is_file():shutil.copy2(source/name,folder/name)
        for response in responses:shutil.copy2(response,folder/response.name)
        status={key:parent[key] for key in ('source_id','source_ids','filename','request','intake_job_id','apply_reviews','source_scope') if key in parent}
        status.update(id=ident,parent_job_id=jid,kind='source_revalidation',status='running',stage='Checking saved model response',created_at=time.time(),model_calls=0)
        jobs.save(folder,'status.json',status)
        client=jobs.worker.client;run_id=None
        try:
            experiment=client.get_experiment_by_name('bonsai-workspace-data')
            eid=experiment.experiment_id if experiment else client.create_experiment('bonsai-workspace-data')
            run_id=client.create_run(eid,tags={'mlflow.runName':'Revalidate saved source proposal','parent_job_id':jid,'parent_run_id':parent.get('run_id',''),'model_calls':'0','review_status':'unreviewed','job_id':ident}).info.run_id
            status.update(run_id=run_id,mlflow_url=f'{jobs.worker.tracking_uri}/#/experiments/{eid}/runs/{run_id}')
            scripts=Path(__file__).parent
            jobs.save(folder,'harness-hashes.json',{name:hashlib.sha256((scripts/name).read_bytes()).hexdigest() for name in ['workspace_revalidation.py','workspace_data/proposal.py','workspace_data/desktop_plan.py','workspace_data/proposal_schema.py']})
            jobs.save(folder,'revalidation.json',{'parent_job_id':jid,'parent_run_id':parent.get('run_id'),'response_file':responses[-1].name,'response_sha256':hashlib.sha256(responses[-1].read_bytes()).hexdigest(),'model_calls':0,'source_snapshot':'frozen parent evidence; current source is not substituted'})
            read=lambda name:json.loads((folder/name).read_text())
            proposal=json.loads(read(responses[-1].name)['message']['content'])
            previous=None
            if len(responses)>1:
                try:previous=json.loads(read(responses[0].name)['message']['content'])
                except json.JSONDecodeError:pass
            validate_schema_repair_preservation(previous,proposal)
            packet=read('source-packet.json')
            compiled=validate_proposal(read('source-manifest.json'),proposal,packet['record_id_map'])
            for finding in proposal['interpretation']['findings']:
                finding['record_ids']=[packet['record_id_map'][ref] for ref in finding['record_ids']]
            for row in (proposal.get('structure') or {}).get('records',[]):
                for item in row['evidence']:item['record_id']=packet['record_id_map'][item['record_id']]
            jobs.save(folder,'compiled.json',compiled);jobs.save(folder,'chart.json',compiled['chart']);jobs.save(folder,'proposal.json',proposal)
            status.update(status='awaiting_confirmation',stage='Saved response is ready for your review',proposal_contract='source-proposal-v2-structured',proposal=proposal,
                          proposal_sha256=hashlib.sha256(json.dumps(proposal,sort_keys=True).encode()).hexdigest(),
                          source_coverage={k:v for k,v in packet.items() if k not in ('records','record_id_map')})
        except Exception as exc:
            status.update(status='failed',stage='Saved response still needs correction',error=str(exc))
            jobs.save(folder,'failure.json',{'error':str(exc)})
        finally:
            jobs.save(folder,'status.json',status)
            if run_id:
                try:
                    client.log_artifacts(run_id,str(folder),'source-project')
                    client.log_metric(run_id,'model_calls',0)
                    client.set_terminated(run_id,'FINISHED' if status['status']=='awaiting_confirmation' else 'FAILED')
                except Exception as exc:
                    status['evidence_error']=str(exc);jobs.save(folder,'status.json',status)
        return jobs.get(ident)
