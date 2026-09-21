import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from workspace_sources import WorkspaceSources

class Client:
    def get_experiment_by_name(self, name): return SimpleNamespace(experiment_id='test')
    def create_run(self, *args, **kwargs):
        self.tags = kwargs['tags']
        return SimpleNamespace(info=SimpleNamespace(run_id='test-export'))
    def log_artifact(self, *args): pass
    def log_metric(self, *args): pass
    def set_terminated(self, *args): pass

class SourcesTest(unittest.TestCase):
    def test_upload_review_export_preserves_source_and_excludes_test_feedback(self):
        with tempfile.TemporaryDirectory() as folder:
            service=WorkspaceSources(folder,Client(),'http://localhost:5210')
            raw=b'[{"label":"A","value":0},{"label":"B","value":null}]'
            source=service.upload('../../records.json',raw);sid=source['source_id']
            self.assertEqual(service.download(sid)[0],raw)
            self.assertEqual(source['record_count'],2)
            service.review({'source_id':sid,'snapshot_id':source['review']['snapshot_id'],
                'record_id':source['records'][0]['id'],'previous_event_id':None,'author':'Synthetic fixture',
                'reviewer_kind':'test','action':'correct','note':'Synthetic API test only',
                'corrected_data':{'label':'A','value':9}})
            exported=service.export(sid)
            self.assertEqual(exported['training_candidates'],0)
            bundle=json.loads(service.download(sid,exported['url'].rsplit('/',1)[1])[0])
            self.assertEqual(exported['dataset_sha256'], bundle['dataset_sha256'])
            self.assertEqual(service.client.tags['dataset_sha256'], bundle['dataset_sha256'])
            self.assertEqual(service.client.tags['dataset_task'], 'source_extraction')
            self.assertEqual(bundle['source_manifest']['records'][0]['data']['value'],0)
            self.assertIsNone(bundle['source_manifest']['records'][1]['data']['value'])
            self.assertEqual(len(bundle['review_events']),1)
            self.assertEqual(service.upload('renamed.json',raw)['review']['latest'], service.get(sid)['review']['latest'])
            for value in ('../../escape','f'*63,'G'*64):
                with self.assertRaises(ValueError): service.get(value)
            with self.assertRaises(ValueError):service.download(sid,'../../escape')
