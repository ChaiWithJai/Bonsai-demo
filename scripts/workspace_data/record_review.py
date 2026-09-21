"""Append-only, source-version-bound reviews and explicit correction exports."""
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import uuid


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def snapshot_id(manifest):
    return digest({key: manifest.get(key) for key in ('source_id', 'sha256', 'extractor', 'extraction_run_id', 'records')})


def history(root, manifest):
    folder = Path(root) / manifest['source_id'] / 'reviews'
    events = [json.loads(path.read_text()) for path in folder.glob('*.json')]
    return sorted(events, key=lambda event: event['sequence'])


def state(root, manifest):
    snapshot = snapshot_id(manifest)
    events = history(root, manifest)
    current = [event for event in events if event['snapshot_id'] == snapshot]
    latest = {event['record_id']: event for event in current}
    return {'snapshot_id': snapshot, 'events': current, 'latest': latest,
            'prior_snapshot_events': len(events) - len(current)}


def save_review(root, manifest, body):
    snapshot = snapshot_id(manifest)
    if body.get('snapshot_id') != snapshot:
        raise ValueError('Source extraction changed. Reload before reviewing.')
    record = next((row for row in manifest['records'] if row['id'] == body.get('record_id')), None)
    if record is None:
        raise ValueError('Choose a record from this source snapshot')
    author, kind, action, note = (body.get(key) for key in ('author', 'reviewer_kind', 'action', 'note'))
    if not isinstance(author, str) or not 1 <= len(author.strip()) <= 100:
        raise ValueError('Provide a reviewer name, up to 100 characters')
    if kind not in ('human', 'codex', 'test') or action not in ('accept', 'correct', 'reject'):
        raise ValueError('Choose an explicit reviewer kind and review action')
    if not isinstance(note, str) or not 1 <= len(note.strip()) <= 4000:
        raise ValueError('Explain the review using 1 to 4000 characters')
    corrected = body.get('corrected_data')
    if action == 'correct':
        if not isinstance(corrected, dict) or set(corrected) != set(record['data']):
            raise ValueError('Corrected data must retain every original field name')
        if len(json.dumps(corrected, allow_nan=False)) > 50000:
            raise ValueError('Corrected record exceeds 50,000 characters')
        if digest(corrected) == digest(record['data']):
            raise ValueError('Correction must change a value; use Accept for unchanged data')
    elif corrected is not None:
        raise ValueError('Only a correction may supply corrected data')
    folder = Path(root) / manifest['source_id'] / 'reviews'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = state(root, manifest)
        previous = current['latest'].get(record['id'])
        if body.get('previous_event_id') != (previous['event_id'] if previous else None):
            raise ValueError('Another review was saved. Reload before changing this record.')
        events = history(root, manifest)
        event = {'schema_version': 1, 'event_id': uuid.uuid4().hex,
                 'sequence': max((e['sequence'] for e in events), default=0) + 1,
                 'created_at': datetime.now(timezone.utc).isoformat(),
                 'source_id': manifest['source_id'], 'source_sha256': manifest['sha256'],
                 'snapshot_id': snapshot, 'extraction_run_id': manifest.get('extraction_run_id'),
                 'extractor': manifest.get('extractor'), 'record_id': record['id'],
                 'locator': deepcopy(record['locator']), 'original_data': deepcopy(record['data']),
                 'action': action, 'corrected_data': deepcopy(corrected), 'note': note.strip(),
                 'author': author.strip(), 'reviewer_kind': kind,
                 'identity_basis': 'self_declared_local_reviewer',
                 'previous_event_id': body.get('previous_event_id')}
        with (folder / (event['event_id'] + '.json')).open('x') as file:
            json.dump(event, file, ensure_ascii=False, indent=2, allow_nan=False)
    return event


def export_reviews(root, manifest):
    review = state(root, manifest)
    examples = []
    for row in manifest['records']:
        event = review['latest'].get(row['id'])
        if not event or event['reviewer_kind'] != 'human' or event['action'] == 'reject':
            continue
        examples.append({'source_id': manifest['source_id'], 'snapshot_id': review['snapshot_id'],
                         'record_id': row['id'], 'locator': row['locator'],
                         'input': row['data'], 'target': event['corrected_data'] if event['action'] == 'correct' else row['data'],
                         'review_event_id': event['event_id'], 'author': event['author'],
                         'identity_basis': event['identity_basis'], 'action': event['action']})
    return {'schema_version': 1, 'purpose': 'reviewed extraction examples for dataset curation; no training executed',
            'source_id': manifest['source_id'], 'source_sha256': manifest['sha256'],
            'snapshot_id': review['snapshot_id'], 'source_manifest': manifest,
            'review_events': history(root, manifest), 'training_candidates': examples,
            'policy': 'Only latest human-declared accept/correct reviews of this snapshot are candidates. '
                      'Codex, tests, rejected records and unreviewed records are excluded. Reviewer identity is not authenticated.'}


def apply_human_reviews(root, manifest):
    """Create a derived working copy; never rewrite extraction or review events."""
    review = state(root, manifest)
    updated = deepcopy(manifest)
    records, applied = [], []
    for row in updated['records']:
        event = review['latest'].get(row['id'])
        if event and event['reviewer_kind'] == 'human':
            applied.append({'record_id':row['id'],'event_id':event['event_id'],'action':event['action']})
            if event['action'] == 'reject':
                continue
            if event['action'] == 'correct':
                row['data'] = deepcopy(event['corrected_data'])
            row['evidence_status'] = 'human_declared_review'
        records.append(row)
    if not records:
        raise ValueError('All source records were rejected; no records remain to visualize')
    updated.update(records=records,review_application={'source_snapshot_id':review['snapshot_id'],'events':applied},
                   review_status='human_declared_reviews_applied_to_some_records' if applied else manifest.get('review_status','source_values_unreviewed'))
    return updated
