"""One bounded, traced intake reply, before any source evidence is available."""
import hashlib
import json
from pathlib import Path
import threading
import time
import uuid
from workspace_store import RevisionConflict
from workspace_provider import GenerationCancelled

ROLES = ('Research analyst', 'Data analyst', 'Evidence reviewer')
SYSTEM = '''You are Bonsai, helping a user plan a data exploration workstream.
No files are attached to this conversation yet. You cannot search their machine, read their email,
inspect files, or claim findings. Discuss their question and help identify useful evidence.
Reply conversationally in under 150 words. Suggest a suitable way to explore the data and ask at
most one useful clarification. Invite relevant files when appropriate. Do not generate code or a
visualization yet. Actual extraction, source-backed interpretation and user confirmation happen
after attachment. Prior messages are conversation context, not source evidence.'''


def context(jobs, jid, role=None):
    if not jid:
        return []
    job = jobs.get(jid)
    if job.get('kind') != 'intake_conversation' or job['status'] != 'completed':
        raise ValueError('Choose a completed intake conversation')
    if role is not None and job['role'] != role:
        raise ValueError('Conversation belongs to another role')
    return json.loads((jobs.root / jid / 'messages.json').read_text()) + [
        {'role':'assistant', 'content':job['reply']}]


def start(jobs, role, message, parent=None):
    if role not in ROLES:
        raise ValueError('Choose an available workstream role')
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 4000:
        raise ValueError('Write a message of 1 to 4,000 characters')
    with jobs.worker.guard:
        w = jobs.worker
        if w.running or w.source_jobs:
            raise RevisionConflict('Another Workspace job is using the local model')
        messages = context(jobs, parent, role) + [{'role':'user','content':message.strip()}]
        if len(messages) > 11 or sum(len(m['content']) for m in messages) > 12000:
            raise ValueError('Attach evidence to continue this discussion, or start a new workstream')
        jid = uuid.uuid4().hex
        folder = jobs.root / jid
        folder.mkdir()
        status = {'id':jid,'kind':'intake_conversation','role':role,'source_id':'',
                  'filename':role,'request':message.strip(),'parent_job_id':parent,
                  'status':'queued','stage':'Thinking about your question','created_at':time.time()}
        jobs.save(folder,'messages.json',messages)
        jobs.save(folder,'status.json',status)
        cancel = threading.Event()
        thread = threading.Thread(target=run,args=(jobs,folder,status,messages,cancel),daemon=True)
        jobs.active[jid] = (cancel,thread)
        w.source_jobs.add(jid)
        thread.start()
        return status


def run(jobs, folder, status, conversation, cancel):
    w=jobs.worker; rid=None; root=None; started=time.monotonic()
    def update(**values):
        status.update(values);jobs.save(folder,'status.json',status)
    try:
        exp=w.client.get_experiment_by_name('bonsai-workspace-data')
        eid=exp.experiment_id if exp else w.client.create_experiment('bonsai-workspace-data')
        tags={'mlflow.runName':'Discuss workstream before attachment','job_id':status['id'],
              'task':'intake_conversation','model':w.provider.model,
              'sampling_profile':w.provider.profile,'sampling_seed':str(w.provider.seed),
              'prompt_sha256':hashlib.sha256(SYSTEM.encode()).hexdigest(),
              'source_evidence_available':'false','review_status':'unreviewed'}
        rid=w.client.create_run(eid,tags=tags).info.run_id
        messages=[{'role':'system','content':SYSTEM+'\nYour role: '+status['role']}] + conversation
        jobs.save(folder,'request.json',messages)
        jobs.save(folder,'model-info.json',w.model_info)
        jobs.save(folder,'harness-hashes.json',{'workspace_intake_chat.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        root=w.client.start_trace('workspace.intake_conversation',span_type='AGENT',experiment_id=eid,
                                 run_id=rid,inputs={'messages':messages},attributes={'model_info':w.model_info})
        update(status='running',run_id=rid,trace_id=root.trace_id,
               mlflow_url=f'{w.tracking_uri}/#/experiments/{eid}/runs/{rid}')
        preflight=jobs.planner.preflight(messages,[],768)
        jobs.save(folder,'preflight.json',preflight)
        if not preflight['fits']:
            raise ValueError('Conversation exceeds model context. Start a new workstream.')
        response=jobs.planner.generate(messages,[],'intake-'+status['id'],cancel,lambda delta:None,768)
        jobs.save(folder,'response.json',response)
        if cancel.is_set():
            raise GenerationCancelled('Intake reply cancelled')
        reply=response['message']['content']
        if not isinstance(reply,str) or not reply.strip() or response.get('finish_reason') == 'length':
            raise ValueError('Bonsai did not finish a reply within the response budget')
        update(status='completed',stage='Ready for your reply or files',reply=reply.strip())
    except Exception as exc:
        jobs.save(folder,'failure.json',{'error':str(exc),'provider_evidence':getattr(exc,'evidence',None)})
        update(status='cancelled' if cancel.is_set() else 'failed',stage='Reply stopped',error=str(exc))
    finally:
        update(elapsed_seconds=round(time.monotonic()-started,3))
        try:
            if root:
                w.client.end_trace(root.trace_id,outputs={'reply':status.get('reply'),'error':status.get('error')},status='OK' if status['status']=='completed' else 'ERROR')
            if rid:
                w.client.log_artifacts(rid,str(folder),'intake-conversation')
                w.client.set_terminated(rid,'FINISHED' if status['status']=='completed' else 'FAILED')
        except Exception as exc:
            update(evidence_error=str(exc))
        finally:
            with w.guard:
                jobs.active.pop(status['id'],None);w.source_jobs.discard(status['id'])


def workstreams(records):
    """Recover discoverable conversations from persisted jobs, independent of browsers."""
    by_id = {item['id']:item for item in records}
    def root_for(item):
        seen=set()
        while item.get('parent_job_id') in by_id:
            if item['id'] in seen:
                return None
            seen.add(item['id'])
            parent=by_id[item['parent_job_id']]
            if parent.get('kind') != 'intake_conversation':
                break
            item=parent
        return item['id']
    groups={}
    roots={}
    for item in records:
        if item.get('kind') != 'intake_conversation':
            continue
        root=root_for(item)
        if root is None:
            continue
        roots[item['id']]=root
        groups.setdefault(root,[]).append(item)
    result=[]
    for root, turns in groups.items():
        turns.sort(key=lambda item:(item.get('created_at',0),item['id']))
        sources=sorted((item for item in records if item.get('intake_job_id') in roots
                        and roots[item['intake_job_id']]==root),
                       key=lambda item:(item.get('created_at',0),item['id']))
        first=by_id[root];latest=turns[-1]
        source=sources[-1] if sources else None
        activity=max(turns+sources,key=lambda item:(item.get('created_at',0),item['id']))
        result.append({'id':root,'title':first['request'][:150],'role':first['role'],
                       'latest_intake_id':latest['id'],'source_id':source['source_id'] if source else '',
                       'source_ids':list(dict.fromkeys(item['source_id'] for item in sources)),
                       'workspace_id':source.get('workspace_id') if source else None,
                       'workspace_ids':list(dict.fromkeys(item['workspace_id'] for item in sources if item.get('workspace_id'))),
                       'status':activity['status'],'stage':activity['stage'],
                       'updated_at':activity.get('created_at',0),'turn_count':len(turns)})
    return sorted(result,key=lambda item:(item['updated_at'],item['id']),reverse=True)
