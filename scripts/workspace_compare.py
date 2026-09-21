"""Export an evidence comparison of explicit MLflow Workspace attempts."""
import argparse
import json
from pathlib import Path
import tempfile

MATCH_FIELDS = ('dataset_sha256', 'base_revision', 'prompt_sha256', 'case_id', 'request_sha256', 'initial_model_input_sha256')
CONFIG_FIELDS = ('model_revision', 'runtime_revision', 'harness_revision',
                 'sampling_profile', 'sampling_seed', 'hardware_id', 'cache_condition')


def compare(rows):
    if len(rows) < 2:
        raise ValueError('Choose at least two runs')
    matching = {key: all(row['tags'].get(key) for row in rows) and
                len({row['tags'].get(key) for row in rows}) == 1 for key in MATCH_FIELDS}
    return {'schema_version': 1, 'task_metadata_matches': all(matching.values()),
            'matched_fields': matching,
            'configuration_differences': {key: [r['tags'].get(key) for r in rows]
                for key in CONFIG_FIELDS if len({r['tags'].get(key) for r in rows}) > 1},
            'interpretation': 'Descriptive comparison only. Matching task metadata does not establish '
                'identical conversation history, cache state, or held-out performance. Missing outcomes '
                'remain unknown; MLflow run status alone is not task success.',
            'runs': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tracking-uri', default='http://127.0.0.1:5210')
    parser.add_argument('--run', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from mlflow import MlflowClient
    client = MlflowClient(args.tracking_uri)
    rows = []
    for rid in args.run:
        run = client.get_run(rid)
        with tempfile.TemporaryDirectory() as folder:
            summary = json.loads(Path(client.download_artifacts(rid, 'attempt/summary.json', folder)).read_text())
        rows.append({'run_id': rid, 'url': f'{args.tracking_uri}/#/experiments/{run.info.experiment_id}/runs/{rid}',
                     'tags': {k: v for k, v in run.data.tags.items() if not k.startswith('mlflow.')},
                     'outcome': {k: summary.get(k) for k in ('status', 'error', 'elapsed_seconds', 'repairs', 'trace_id', 'revision')},
                     'browser_check': (summary.get('check') or {}).get('report'),
                     'loop_detection': summary.get('loop_detection')})
    report = compare(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(args.output)


if __name__ == '__main__':
    main()
