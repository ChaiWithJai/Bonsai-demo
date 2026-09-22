"""Summarize current review eligibility without exporting user content or labels."""
import argparse
from collections import Counter
import json
from pathlib import Path
from workspace_data import proposal_review
from workspace_store import WorkspaceStore


def inventory(root):
    if not (root/'workspace.sqlite3').is_file():raise ValueError('Existing workspace database required')
    proposals, interfaces, errors = [], [], []
    kinds = Counter()
    jobs = root / 'source-jobs'
    for folder in sorted(jobs.iterdir()) if jobs.is_dir() else []:
        if not (folder / 'status.json').is_file():continue
        try:
            job = json.loads((folder / 'status.json').read_text())
            if job.get('proposal_contract') != 'source-proposal-v2-structured':continue
            state = proposal_review.state(folder,job)
            latest = state['latest']
            eligible = bool(state['eligible_version'] and latest and latest['reviewer_kind']=='human' and latest['action']=='accept')
            for event in state['events']:kinds['proposal:'+event['reviewer_kind']+':'+event['action']]+=1
            proposals.append({'job_id':job['id'],'proposal_sha256':state['proposal_sha256'],
                              'review':({key:latest[key] for key in ('event_id','reviewer_kind','action')} if latest else None),
                              'superseded':not state['eligible_version'],'candidate':eligible})
        except (OSError,ValueError,KeyError,TypeError) as exc:
            errors.append({'kind':'proposal','id':folder.name,'error_kind':type(exc).__name__})
    store = WorkspaceStore(root)
    for project in store.list():
        try:
            state=store.interface_reviews(project['id']);latest=state['latest']
            for event in state['events']:kinds['interface:'+event['reviewer_kind']+':'+event['action']]+=1
            interfaces.append({'project_id':project['id'],'revision':state['revision'],
                               'review':({key:latest[key] for key in ('reviewer_kind','action')} if latest else None),
                               'candidate':bool(latest and latest['reviewer_kind']=='human' and latest['action']=='accept')})
        except (OSError,ValueError,KeyError,TypeError) as exc:
            errors.append({'kind':'interface','id':project['id'],'error_kind':type(exc).__name__})
    return {'schema_version':1,'scope':'Current eligibility inventory, not a training export or authenticated identity check',
            'summary':{'proposals':len(proposals),'proposal_candidates':sum(p['candidate'] for p in proposals),
                       'interfaces':len(interfaces),'interface_candidates':sum(p['candidate'] for p in interfaces),
                       'review_events':dict(kinds),'unreadable':len(errors)},
            'proposals':proposals,'interfaces':interfaces,'errors':errors,
            'limitations':['Human identity is self-declared in this local harness','No names, review notes, prompts, filenames or source text are exported','Build confirmation and record notes do not count as acceptance']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=inventory(args.workspace)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['summary']))


if __name__=='__main__':main()
