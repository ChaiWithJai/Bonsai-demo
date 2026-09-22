"""Version-bound interpretation judgments, independent of build confirmation."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid
from workspace_data.record_review import digest


def context(folder, job):
    proposal = job.get('proposal')
    if job.get('proposal_contract') != 'source-proposal-v2-structured' or not proposal:
        raise ValueError('This job has no validated structured proposal to review')
    actual = hashlib.sha256(json.dumps(proposal, sort_keys=True).encode()).hexdigest()
    if actual != job.get('proposal_sha256'):
        raise ValueError('Proposal contents no longer match their recorded version')
    manifest = json.loads((Path(folder) / 'source-manifest.json').read_text())
    packet = json.loads((Path(folder) / 'source-packet.json').read_text())
    return {'proposal_sha256': actual, 'source_snapshot_sha256': digest(manifest),
            'input_sha256': digest({'request': job['request'], 'packet': packet})}, manifest


def state(folder, job):
    version, _ = context(folder, job)
    events = sorted((json.loads(path.read_text()) for path in (Path(folder) / 'proposal-reviews').glob('*.json')),
                    key=lambda event: event['sequence'])
    current = [event for event in events if all(event.get(k) == v for k, v in version.items())]
    return {**version, 'events': events, 'latest': current[-1] if current else None,
            'eligible_version': job['status'] != 'superseded'}


def save(folder, job, body):
    # The caller holds the Workspace guard across status lookup and this write.
    review = state(folder, job)
    if not review['eligible_version']:
        raise ValueError('Review the latest revised proposal')
    if any(body.get(key) != review[key] for key in ('proposal_sha256', 'source_snapshot_sha256', 'input_sha256')):
        raise ValueError('Proposal or source changed. Reload before reviewing.')
    author, kind, action, note = (body.get(key) for key in ('author', 'reviewer_kind', 'action', 'note'))
    if not isinstance(author, str) or not 1 <= len(author.strip()) <= 100:
        raise ValueError('Provide a reviewer name, up to 100 characters')
    if kind not in ('human', 'codex', 'test') or action not in ('accept', 'reject', 'defer'):
        raise ValueError('Choose an explicit reviewer kind and judgment')
    if not isinstance(note, str) or not 1 <= len(note.strip()) <= 4000:
        raise ValueError('Explain the review using 1 to 4000 characters')
    previous = review['latest']
    if body.get('previous_event_id') != (previous['event_id'] if previous else None):
        raise ValueError('Another review was saved. Reload before changing the judgment.')
    event = {key: review[key] for key in ('proposal_sha256', 'source_snapshot_sha256', 'input_sha256')}
    event.update(schema_version=1, event_id=uuid.uuid4().hex,
                 sequence=max((e['sequence'] for e in review['events']), default=0)+1,
                 created_at=datetime.now(timezone.utc).isoformat(), job_id=job['id'],
                 author=author.strip(), reviewer_kind=kind, action=action, note=note.strip(),
                 identity_basis='self_declared_local_reviewer', previous_event_id=body.get('previous_event_id'))
    target = Path(folder) / 'proposal-reviews'
    target.mkdir(exist_ok=True)
    with (target / (event['event_id'] + '.json')).open('x') as file:
        json.dump(event, file, indent=2, ensure_ascii=False, allow_nan=False)
    return event


def export(folder, job):
    review = state(folder, job)
    _, manifest = context(folder, job)
    latest = review['latest']
    planning_path = Path(folder) / 'planning-status.json'
    planning = json.loads(planning_path.read_text()) if planning_path.exists() else job
    candidates = []
    if review['eligible_version'] and latest and latest['reviewer_kind'] == 'human' and latest['action'] == 'accept':
        candidates.append({'job_id': job['id'], 'request': job['request'],
                           'source_manifest': manifest,
                           'source_packet': json.loads((Path(folder) / 'source-packet.json').read_text()),
                           'target': job['proposal'], 'review': latest,
                           'proposal_sha256': review['proposal_sha256'],
                           'source_snapshot_sha256': review['source_snapshot_sha256'],
                           'input_sha256': review['input_sha256'],
                           'planning_run_id': planning.get('run_id', job.get('planning_run_id')),
                           'planning_trace_id': planning.get('trace_id'),
                           'parent_job_id': job.get('parent_job_id'),
                           'view_selection': job.get('view_selection')})
    dataset = {'task': 'source_interpretation', 'examples': candidates}
    return {'schema_version': 1, 'dataset_task': dataset['task'], 'dataset_sha256': digest(dataset),
            'example_count': len(candidates), 'training_candidates': candidates,
            'review_events': review['events'], 'proposal_sha256': review['proposal_sha256'],
            'source_snapshot_sha256': review['source_snapshot_sha256'],
            'policy': 'Only the latest human-declared acceptance of the current proposal and source snapshot is eligible. '
                      'Superseded proposals, deferred or rejected judgments, tests and Codex reviews are excluded. '
                      'Identity is self-declared. Build confirmation is not a review. No training is executed.'}
