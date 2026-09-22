"""Fork a view choice while retaining the archived source, records, and citations."""
import hashlib
import json
from pathlib import Path
import shutil
import time
import uuid
from workspace_data.proposal import validate_proposal
from workspace_data.desktop_plan import compile_plan
from workspace_data.task_contract import validate_task_records,validate_compiled_retention
from workspace_store import RevisionConflict


def revise_view(jobs,jid,body,actor='interactive-unattributed'):
    with jobs.worker.guard:
        parent=jobs.get(jid)
        if not isinstance(body,dict) or set(body)!={'proposal_sha256','view'}:
            raise ValueError('Provide the saved proposal hash and a view choice')
        if parent['status']!='awaiting_confirmation' or body['proposal_sha256']!=parent.get('proposal_sha256'):
            raise RevisionConflict('Choose the current unconfirmed proposal before changing its view')
        source=jobs.root/jid
        required=['source-manifest.json','source-packet.json','profile.json','compiled.json','model-info.json']
        if any(not (source/name).is_file() for name in required):raise ValueError('Saved proposal evidence is incomplete')
        read=lambda name:json.loads((source/name).read_text())
        proposal=json.loads(json.dumps(parent['proposal']))
        if proposal['plan']['view']==body['view']:raise ValueError('Choose a different view or field mapping')
        proposal['plan']['view']=body['view']
        proposal['plan']['summary']='View selected from saved data. Records and cited source passages are unchanged; review the new layout before building.'
        packet=read('source-packet.json');aliases={ref:ref for ref in packet['record_id_map'].values()}
        validate_task_records(proposal,packet,parent.get('task_record_ids',[]))
        manifest=read('source-manifest.json');previous=read('compiled.json')
        validate_proposal(manifest,proposal,aliases)
        if previous['plan']!=parent['proposal']['plan'] or previous['source_sha256']!=manifest['sha256']:
            raise ValueError('Saved plan and compiled source do not match')
        compiled={**previous,**compile_plan({**manifest,'records':previous['rows']},proposal['plan'])}
        compiled['grouping_origin']=previous.get('grouping_origin',compiled['grouping_origin'])
        validate_compiled_retention(compiled,parent.get('task_record_ids',[]))
        if compiled['rows']!=previous['rows']:
            raise ValueError('Changing the view must preserve all compiled records and citations')
        ident=uuid.uuid4().hex;folder=jobs.root/ident;folder.mkdir()
        for name in required+['source.bin','original-manifest.json','generation-config.json','generation-settings.json']:
            if (source/name).is_file():shutil.copy2(source/name,folder/name)
        selection={'actor':actor,'parent_job_id':jid,'parent_run_id':parent.get('planning_run_id') or parent.get('run_id'),
                   'previous_view':parent['proposal']['plan']['view'],'selected_view':body['view'],'model_calls':0,
                   'identity_basis':'Local interaction; not an acceptance or training label'}
        status={key:parent[key] for key in ('source_id','source_ids','filename','request','intake_job_id','apply_reviews','source_scope','generation_config','task_contract','task_record_ids','source_review_record_ids','source_coverage') if key in parent}
        status.update(id=ident,parent_job_id=jid,parent_proposal_sha256=parent['proposal_sha256'],
                      parent_planning_run_id=selection['parent_run_id'],parent_source_snapshot_sha256=hashlib.sha256((source/'source-manifest.json').read_bytes()).hexdigest(),
                      kind='view_revision',view_selection=selection,model_calls=0,created_at=time.time(),
                      status='awaiting_confirmation',stage='Review the selected view',proposal_contract='source-proposal-v2-structured',
                      proposal=proposal,proposal_sha256=hashlib.sha256(json.dumps(proposal,sort_keys=True).encode()).hexdigest(),
                      feedback='Selected a different view using the saved records and citations; no model inference.')
        jobs.save(folder,'view-selection.json',selection);jobs.save(folder,'compiled.json',compiled);jobs.save(folder,'chart.json',compiled['chart']);jobs.save(folder,'proposal.json',proposal)
        scripts=Path(__file__).parent
        jobs.save(folder,'harness-hashes.json',{name:hashlib.sha256((scripts/name).read_bytes()).hexdigest() for name in ['workspace_view_revision.py','workspace_data/proposal.py','workspace_data/desktop_plan.py','workspace_data/task_contract.py']})
        jobs.save(folder,'status.json',status)
        try:
            client=jobs.worker.client;experiment=client.get_experiment_by_name('bonsai-workspace-data');eid=experiment.experiment_id if experiment else client.create_experiment('bonsai-workspace-data')
            run=client.create_run(eid,tags={'mlflow.runName':'Select view from saved proposal','job_id':ident,'parent_job_id':jid,'model_calls':'0','review_status':'unreviewed','view_origin':'explicit_selection'}).info.run_id
            status.update(run_id=run,mlflow_url=f'{jobs.worker.tracking_uri}/#/experiments/{eid}/runs/{run}')
            jobs.save(folder,'status.json',status);client.log_artifacts(run,str(folder),'source-project');client.log_metric(run,'model_calls',0);client.set_terminated(run,'FINISHED')
        except Exception as exc:
            status['evidence_error']=str(exc);jobs.save(folder,'status.json',status)
        return jobs.get(ident)
