"""Persisted learning and due-diligence actions using the existing harness store."""
import datetime as dt
import json
from pathlib import Path
import re
import threading
import uuid

from workspace_bond_math import price_bond
from workspace_gateway import gateway_request
from workspace_treasury import fetch_yields


class LearningWorkstreams:
    def __init__(self, worker):
        self.worker = worker
        self.root = worker.store.root / 'learning-workstreams'
        self.root.mkdir(exist_ok=True)
        self.lock = threading.Lock()
        for path in self.root.glob('*/*/action.json'):
            action = json.loads(path.read_text())
            if action['status'] == 'running':
                action.update(status='interrupted', error='The service stopped before this action finished; no automatic retry was made')
                self.save(path, action)

    @staticmethod
    def save(path, value):
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))
        temp.replace(path)

    def folder(self, key):
        if not isinstance(key, str) or not re.fullmatch('[a-f0-9]{32}', key):
            raise ValueError('Choose a saved learning workstream')
        folder = self.root / key
        if not (folder / 'session.json').is_file():
            raise ValueError('Learning workstream not found')
        return folder

    def list(self):
        return {'workstreams': [json.loads(p.read_text()) for p in sorted(self.root.glob('*/session.json'))]}

    def create(self, kind):
        if kind not in ('bond_math', 'financial_diligence', 'legal_diligence'):
            raise ValueError('Choose a supported learning workflow')
        key = uuid.uuid4().hex
        folder = self.root / key
        folder.mkdir()
        session = {'id': key, 'kind': kind, 'created_at': dt.datetime.now(dt.timezone.utc).isoformat()}
        self.save(folder / 'session.json', session)
        return self.get(key)

    def get(self, key):
        folder = self.folder(key)
        return {**json.loads((folder / 'session.json').read_text()),
                'actions': [json.loads(p.read_text()) for p in sorted(folder.glob('*/action.json'))]}

    def act(self, key, payload):
        folder = self.folder(key)
        operation = payload.get('operation')
        if operation not in ('calculate_bond', 'fetch_treasury', 'evaluate_evidence'):
            raise ValueError('Unsupported learning action')
        if operation == 'calculate_bond':
            inputs = payload.get('inputs')
            required = {'face', 'coupon_rate', 'annual_yield', 'periods', 'frequency'}
            if not isinstance(inputs, dict) or set(inputs) != required:
                raise ValueError('Confirm all five bond inputs')
            if payload.get('confirmed') is not True:
                raise ValueError('Confirm the bond assumptions before calculating')
            # Validate before creating a run. The saved action keeps the exact inputs.
            computed = price_bond(**inputs)
        if operation == 'evaluate_evidence' and payload.get('cloud_evaluation_requested') is not True:
            raise ValueError('Explicitly request cloud evaluation of this claim and evidence')
        if not self.lock.acquire(blocking=False):
            raise ValueError('Wait for the current learning action to finish')
        try:
            aid = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '-' + uuid.uuid4().hex
            target = folder / aid
            target.mkdir()
            action = {'id': aid, 'operation': operation, 'request': payload, 'status': 'running',
                      'created_at': dt.datetime.now(dt.timezone.utc).isoformat()}
            self.save(target / 'action.json', action)
            client = self.worker.client
            rid = None
            try:
                experiment = client.get_experiment_by_name('bonsai-learning-workstreams')
                eid = experiment.experiment_id if experiment else client.create_experiment('bonsai-learning-workstreams')
                run = client.create_run(eid, tags={'mlflow.runName': operation, 'learning_workstream_id': key,
                    'operation': operation, 'human_review_status': 'unreviewed', 'training_executed': 'false'})
                rid = run.info.run_id
                action['mlflow_url'] = f'{self.worker.tracking_uri}/#/experiments/{eid}/runs/{rid}'
                action['run_id'] = rid
            except Exception:
                action['trace_error'] = 'MLflow run could not be created; local action is preserved'
            try:
                if operation == 'calculate_bond':
                    result = computed
                elif operation == 'fetch_treasury':
                    result = fetch_yields(payload.get('year'), target / 'treasury')
                else:
                    result = gateway_request({'operation': operation, 'claim': payload.get('claim'),
                                              'evidence': payload.get('evidence')})
                action.update(status='completed', result=result)
            except Exception as exc:
                action.update(status='failed', error=str(exc) if operation != 'evaluate_evidence'
                              else 'Gateway evaluation failed; check backend configuration and provider availability')
            action['finished_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
            self.save(target / 'action.json', action)
            if rid:
                try:
                    client.log_artifacts(rid, str(target), 'evidence')
                    client.set_terminated(rid, 'FINISHED' if action['status'] == 'completed' else 'FAILED')
                except Exception:
                    action['trace_error'] = 'MLflow evidence upload failed; local action is preserved'
                    self.save(target / 'action.json', action)
            return action
        finally:
            self.lock.release()
