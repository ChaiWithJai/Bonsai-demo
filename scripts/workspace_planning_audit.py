"""Index saved planning evidence without inferring factual or human acceptance.

Only hashes and structural metadata are exported, not prompts or source content.
Live and unreadable jobs remain visible but are excluded from comparisons.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def inspect_job(folder):
    status = read(folder / 'status.json')
    if status.get('kind') in ('vision_extraction', 'intake_conversation'):
        return None
    packet_path = folder / 'source-packet.json'
    if not packet_path.exists():
        return None
    responses = [read(path) for path in sorted(folder.iterdir())
                 if re.fullmatch(r'model-\d+\.json', path.name)]
    failure = read(folder / 'failure.json') if (folder / 'failure.json').exists() else {}
    failed_request = (failure.get('provider_evidence') or {}).get('request')
    payload = responses[0].get('request') if responses else failed_request
    info = read(folder / 'model-info.json') if (folder / 'model-info.json').exists() else None
    validated = (status.get('proposal_contract') == 'source-proposal-v2-structured'
                 and isinstance(status.get('proposal'), dict))
    live = status.get('status') in ('queued', 'running')
    errors = sorted(path.name for path in folder.glob('validation-*.json'))
    confirmation = read(folder / 'confirmation.json') if (folder / 'confirmation.json').exists() else {}
    sampling = ({key:value for key,value in payload.items()
                 if key not in ('messages', 'response_format', 'tools', 'model')}
                if payload else None)
    case = {'source_packet': digest(read(packet_path)), 'request': digest(status.get('request'))}
    record = {
        'job_id': status['id'], 'file_extension': Path(status.get('filename', '')).suffix.lower() or None,
        'case_key': digest(case), 'source_packet_sha256': case['source_packet'],
        'model_info_sha256': digest(info) if info is not None else None,
        'sampling_sha256': digest(sampling) if sampling is not None else None,
        'response_format': (payload.get('response_format', {}).get('type', 'unspecified') if payload else None),
        'response_schema_sha256': digest(payload['response_format']) if payload and 'response_format' in payload else None,
        'harness_sha256': digest(read(folder / 'harness-hashes.json')) if (folder / 'harness-hashes.json').exists() else None,
        'completed_responses': len(responses), 'request_attempts': len(responses) + int(bool(failed_request)),
        'validation_failures': len(errors), 'proposal_validated': validated,
        'first_pass_valid': bool(validated and len(responses) == 1 and not errors),
        'status': status.get('status'), 'in_progress': live,
        'planning_run_id': status.get('planning_run_id') or status.get('run_id'),
        'build_run_id': status.get('run_id') if status.get('planning_run_id') else None,
        'confirmation_actor': confirmation.get('actor'),
        'semantic_quality': 'not_assessed', 'human_review': 'not_assessed',
    }
    record['comparison_eligible'] = not live and isinstance(status.get('request'),str) and bool(status['request'].strip()) and all(record[key] is not None for key in ('model_info_sha256','sampling_sha256'))
    return record


def audit(root):
    records, unreadable = [], []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not (folder / 'status.json').exists():
            continue
        try:
            record = inspect_job(folder)
            if record is not None:
                records.append(record)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            unreadable.append({'job_id':folder.name,'error_kind':type(exc).__name__})
    cohorts = defaultdict(list)
    for record in records:
        if record['comparison_eligible']:
            cohorts[(record['case_key'], record['model_info_sha256'], record['sampling_sha256'])].append(record['job_id'])
    return {
        'schema_version':1, 'scope':'Observed planning shape and execution only; not an accuracy score or training dataset',
        'jobs':records, 'unreadable_jobs':unreadable,
        'summary':{'indexed_jobs':len(records),'in_progress':sum(r['in_progress'] for r in records),
                   'validated_proposals':sum(r['proposal_validated'] for r in records),
                   'first_pass_valid':sum(r['first_pass_valid'] for r in records),
                   'formats':dict(Counter(r['response_format'] or 'unknown' for r in records))},
        'matched_cohorts':[{'case_key':key[0],'model_info_sha256':key[1],'sampling_sha256':key[2],'job_ids':ids}
                           for key,ids in cohorts.items() if len(ids)>1],
        'limitations':['Matching does not establish a randomized or causal experiment',
                       'Confirmation actors do not establish human-reviewed training acceptance',
                       'Unfinished jobs and missing configuration evidence are excluded from matched cohorts',
                       'No prompts, filenames or source text are included'],
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_jobs',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.source_jobs)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2))
    print(json.dumps(result['summary']))


if __name__ == '__main__':
    main()
