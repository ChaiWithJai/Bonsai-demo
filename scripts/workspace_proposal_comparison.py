"""Compare archived proposal revisions without changing review or build state."""
from collections import Counter
import hashlib
import json


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)


def compare(jobs,jid):
    current=jobs.get(jid)
    if not current.get('parent_job_id'):raise ValueError('This proposal has no previous version')
    previous=jobs.get(current['parent_job_id'])
    if not current.get('proposal') or not previous.get('proposal'):
        raise ValueError('Both versions need a saved proposal')
    def load(job,name):
        path=jobs.root/job['id']/name
        return json.loads(path.read_text()) if path.is_file() else None
    def same(name):
        a=load(previous,name);b=load(current,name)
        return None if a is None or b is None else canonical(a)==canonical(b)
    def rows(job):return (job['proposal'].get('structure') or {}).get('records',[])
    def row_key(row):
        return canonical({'values':row['values'],'evidence':sorted(row['evidence'],key=canonical)})
    left=Counter(map(row_key,rows(previous)));right=Counter(map(row_key,rows(current)))
    unchanged=sum((left&right).values())
    def side(job):
        planning=load(job,'planning-status.json') or job
        return {'id':job['id'],'proposal_sha256':job.get('proposal_sha256'),
                'plan':job['proposal']['plan'],'interpretation':job['proposal']['interpretation'],
                'records':rows(job),'generation_config':job.get('generation_config'),
                'planning_run_id':job.get('planning_run_id') or job.get('run_id'),
                'planning_elapsed_seconds':planning.get('elapsed_seconds'),'planning_url':planning.get('mlflow_url')}
    snapshot=load(previous,'source-manifest.json')
    frozen=current.get('parent_source_snapshot_sha256')
    # Lineage uses the actual archived bytes, not reserialized JSON.
    path=jobs.root/previous['id']/'source-manifest.json'
    lineage=None if snapshot is None or not frozen else hashlib.sha256(path.read_bytes()).hexdigest()==frozen
    return {'previous':side(previous),'current':side(current),'feedback':current.get('feedback'),
            'matches':{'source_snapshot':same('source-manifest.json'),'source_context':same('source-packet.json'),
                       'generation_settings':same('generation-settings.json'),'model_runtime':same('model-info.json'),
                       'harness':same('harness-hashes.json'),'recorded_parent_snapshot':lineage},
            'records':{'previous':sum(left.values()),'current':sum(right.values()),'unchanged':unchanged,
                       'previous_only':sum((left-right).values()),'current_only':sum((right-left).values())},
            'view_changed':canonical(previous['proposal']['plan']['view'])!=canonical(current['proposal']['plan']['view']),
            'limitations':['Unchanged records means matching values and cited passages, regardless of order.',
                           'Previous-only and current-only records can represent edits, additions, or removals; identities are not inferred.',
                           'Matching metadata does not prove identical inference context or cache state, factual accuracy, or human acceptance.']}
