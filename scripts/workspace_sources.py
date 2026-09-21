"""Native Workspace source intake and review, with immutable original bytes."""
import json
from pathlib import Path
import re
import threading
import uuid
from workspace_data.intake import ingest
from workspace_data.record_review import state, save_review, export_reviews


class WorkspaceSources:
    def __init__(self, root, client, tracking_uri):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.client, self.tracking_uri = client, tracking_uri.rstrip('/')
        self.lock = threading.RLock()

    def manifest(self, source_id):
        if not isinstance(source_id, str) or not re.fullmatch('[a-f0-9]{64}', source_id):
            raise ValueError('Choose a source from this Workspace')
        path = self.root / source_id / 'manifest.json'
        if not path.is_file():
            raise ValueError('Source not found')
        return json.loads(path.read_text())

    @staticmethod
    def summary(manifest):
        return {key: value for key, value in manifest.items() if key != 'records'} | {'record_count': len(manifest['records'])}

    def list(self):
        return {'sources': [self.summary(json.loads(p.read_text())) for p in sorted(self.root.glob('*/manifest.json'))]}

    def get(self, source_id):
        with self.lock:
            m = self.manifest(source_id)
            return self.summary(m) | {'records': m['records'][:100], 'sample_limit': 100, 'review': state(self.root, m)}

    def upload(self, filename, content):
        with self.lock:
            manifest = ingest(self.root, filename, content)
            return self.get(manifest['source_id'])

    def review(self, body):
        with self.lock:
            return save_review(self.root, self.manifest(body.get('source_id')), body)

    def export(self, source_id):
        with self.lock:
            manifest = self.manifest(source_id)
            bundle = export_reviews(self.root, manifest)
            eid = uuid.uuid4().hex
            folder = self.root / source_id / 'exports' / eid
            folder.mkdir(parents=True)
            path = folder / 'record-reviews.json'
            path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False, allow_nan=False))
            experiment = self.client.get_experiment_by_name('bonsai-workspace-data')
            experiment_id = experiment.experiment_id if experiment else self.client.create_experiment('bonsai-workspace-data')
            run = self.client.create_run(experiment_id, tags={'mlflow.runName': 'Workspace review export', 'source_id': source_id, 'snapshot_id': bundle['snapshot_id'], 'training_executed': 'false'})
            try:
                self.client.log_artifact(run.info.run_id, str(path), 'review')
                self.client.log_artifact(run.info.run_id, str(self.root / source_id / 'source.bin'), 'source')
                self.client.log_metric(run.info.run_id, 'training_candidates', len(bundle['training_candidates']))
                self.client.log_metric(run.info.run_id, 'review_events', len(bundle['review_events']))
                self.client.set_terminated(run.info.run_id, 'FINISHED')
            except Exception:
                self.client.set_terminated(run.info.run_id, 'FAILED')
                raise
            return {'url': f'/api/workspace/sources/{source_id}/exports/{eid}', 'run_url': f'{self.tracking_uri}/#/experiments/{experiment_id}/runs/{run.info.run_id}', 'training_candidates': len(bundle['training_candidates'])}

    def download(self, source_id, export_id=None):
        self.manifest(source_id)
        if export_id is None:
            return (self.root / source_id / 'source.bin').read_bytes(), 'application/octet-stream'
        if not re.fullmatch('[a-f0-9]{32}', export_id):
            raise ValueError('Invalid export ID')
        path = self.root / source_id / 'exports' / export_id / 'record-reviews.json'
        if not path.is_file():
            raise ValueError('Export not found')
        return path.read_bytes(), 'application/json'
