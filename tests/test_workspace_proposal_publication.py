import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from workspace_source_jobs import SourceJobs


class ProposalPublicationTest(unittest.TestCase):
    def setup_job(self, root, client):
        jobs=SourceJobs.__new__(SourceJobs)
        jobs.root=root/'source-jobs';jobs.root.mkdir()
        jobs.worker=SimpleNamespace(store=SimpleNamespace(root=root),client=client,tracking_uri='http://localhost:5210')
        jobs.export_proposal_reviews=lambda jid: {'dataset_sha256':'empty-version','dataset_task':'source_interpretation',
                                                'example_count':0,'training_candidates':[],'review_events':[{'reviewer_kind':'test'}]}
        return jobs

    def test_zero_human_examples_remain_zero_in_mlflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);client=Mock()
            client.get_experiment_by_name.return_value=SimpleNamespace(experiment_id='12')
            client.create_run.return_value=SimpleNamespace(info=SimpleNamespace(run_id='run'))
            jobs=self.setup_job(root,client)
            result=jobs.publish_proposal_reviews('a'*32)
            self.assertEqual(result['example_count'],0)
            client.log_metric.assert_called_once_with('run','reviewed_examples',0)
            client.set_terminated.assert_called_once_with('run','FINISHED')
            path=Path(client.log_artifact.call_args.args[1])
            self.assertEqual(json.loads(path.read_text())['training_candidates'],[])
            self.assertTrue((path.parent/'publication.json').exists())
            self.assertEqual(client.create_run.call_args.kwargs['tags']['training_executed'],'false')

    def test_failed_publication_retains_local_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);client=Mock()
            client.get_experiment_by_name.return_value=SimpleNamespace(experiment_id='12')
            client.create_run.return_value=SimpleNamespace(info=SimpleNamespace(run_id='run'))
            client.log_artifact.side_effect=RuntimeError('Offline')
            jobs=self.setup_job(root,client)
            with self.assertRaisesRegex(RuntimeError,'Offline'):jobs.publish_proposal_reviews('a'*32)
            client.set_terminated.assert_called_once_with('run','FAILED')
            self.assertEqual(len(list(jobs.root.glob('*/review-exports/*/proposal-reviews.json'))),1)
            self.assertEqual(list(jobs.root.glob('*/review-exports/*/publication.json')),[])

    def test_candidate_publication_requires_and_includes_original_evidence(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);client=Mock()
            client.get_experiment_by_name.return_value=SimpleNamespace(experiment_id='12')
            client.create_run.return_value=SimpleNamespace(info=SimpleNamespace(run_id='run'))
            jobs=self.setup_job(root,client);jid='a'*32;folder=jobs.root/jid;folder.mkdir()
            raw=b'Synthetic original'
            (folder/'source.bin').write_bytes(raw)
            (folder/'original-manifest.json').write_text(json.dumps({'sha256':hashlib.sha256(raw).hexdigest()}))
            for name in ('source-manifest.json','source-packet.json','proposal.json','model-info.json','harness-hashes.json'):
                (folder/name).write_text('{}')
            jobs.export_proposal_reviews=lambda jid: {'dataset_sha256':'fixture-version','dataset_task':'source_interpretation',
                                                    'example_count':1,'training_candidates':[{'synthetic_unit_fixture':True}]}
            jobs.publish_proposal_reviews(jid)
            artifacts=[Path(call.args[1]).name for call in client.log_artifact.call_args_list]
            self.assertIn('source.bin',artifacts)
            self.assertIn('source-packet.json',artifacts)
            self.assertIn('model-info.json',artifacts)
            client.reset_mock();(folder/'source.bin').write_bytes(b'Tampered')
            with self.assertRaisesRegex(ValueError,'integrity'):jobs.publish_proposal_reviews(jid)
            client.create_run.assert_not_called()
