import json
from pathlib import Path
import tempfile
import unittest
from workspace_data.intake import ingest
from workspace_data.record_review import save_review, state, export_reviews, apply_human_reviews


class RecordReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = ingest(self.root, 'review.json', b'[{"value":0,"label":"A"},{"value":null,"label":"B"}]')

    def body(self, **changes):
        return {'snapshot_id':state(self.root,self.manifest)['snapshot_id'],
                'record_id':self.manifest['records'][0]['id'], 'previous_event_id':None,
                'author':'Fixture reviewer', 'reviewer_kind':'test', 'action':'accept',
                'note':'Synthetic test; not human feedback', **changes}

    def test_only_explicit_latest_human_reviews_are_candidates(self):
        # The human-kind branch below is a unit fixture in an isolated temporary store.
        first=save_review(self.root,self.manifest,self.body())
        self.assertEqual(export_reviews(self.root,self.manifest)['training_candidates'],[])
        second=save_review(self.root,self.manifest,self.body(previous_event_id=first['event_id'],reviewer_kind='human',action='correct',corrected_data={'value':2,'label':'A'}))
        bundle=export_reviews(self.root,self.manifest)
        self.assertEqual(len(bundle['training_candidates']),1)
        self.assertEqual(bundle['training_candidates'][0]['input']['value'],0)
        self.assertEqual(bundle['training_candidates'][0]['target']['value'],2)
        self.assertIsNone(bundle['source_manifest']['records'][1]['data']['value'])
        save_review(self.root,self.manifest,self.body(previous_event_id=second['event_id'],action='reject'))
        self.assertEqual(export_reviews(self.root,self.manifest)['training_candidates'],[])
        self.assertEqual(len(export_reviews(self.root,self.manifest)['review_events']),3)

    def test_dataset_version_tracks_candidates_and_is_stable_on_repeat_export(self):
        empty = export_reviews(self.root, self.manifest)
        first = save_review(self.root, self.manifest, self.body())
        self.assertEqual(export_reviews(self.root, self.manifest)['dataset_sha256'], empty['dataset_sha256'])
        # Human-kind feedback is simulated only inside this temporary test store.
        second = save_review(self.root, self.manifest, self.body(
            previous_event_id=first['event_id'], reviewer_kind='human', action='correct',
            corrected_data={'value': 2, 'label': 'A'}))
        reviewed = export_reviews(self.root, self.manifest)
        self.assertEqual(reviewed['example_count'], 1)
        self.assertNotEqual(reviewed['dataset_sha256'], empty['dataset_sha256'])
        self.assertEqual(reviewed['dataset_sha256'], export_reviews(self.root, self.manifest)['dataset_sha256'])
        save_review(self.root, self.manifest, self.body(previous_event_id=second['event_id'],
            reviewer_kind='human', action='correct', corrected_data={'value': 3, 'label': 'A'}))
        self.assertNotEqual(reviewed['dataset_sha256'], export_reviews(self.root, self.manifest)['dataset_sha256'])

    def test_stale_edits_and_source_changes_cannot_overwrite_reviews(self):
        original=self.body()
        save_review(self.root,self.manifest,original)
        with self.assertRaisesRegex(ValueError,'Another review'):
            save_review(self.root,self.manifest,original)
        self.manifest['records'][0]['data']['value']=3
        with self.assertRaisesRegex(ValueError,'extraction changed'):
            save_review(self.root,self.manifest,original)
        self.assertEqual(state(self.root,self.manifest)['prior_snapshot_events'],1)
        self.assertEqual(state(self.root,self.manifest)['latest'],{})

    def test_rejects_invented_fields_and_nonfinite_values(self):
        for data in ({'value':5}, {'value':5,'label':'A','invented':1}, {'value':float('nan'),'label':'A'}):
            with self.assertRaises(ValueError):
                save_review(self.root,self.manifest,self.body(action='correct',corrected_data=data))

    def test_reupload_preserves_extraction_and_review(self):
        path=self.root/self.manifest['source_id']/'manifest.json'
        self.manifest['extraction_run_id']='test-version'
        path.write_text(json.dumps(self.manifest))
        save_review(self.root,self.manifest,self.body())
        again=ingest(self.root,'renamed.json',b'[{"value":0,"label":"A"},{"value":null,"label":"B"}]')
        self.assertEqual(again,self.manifest)
        self.assertEqual(len(state(self.root,again)['latest']),1)

    def test_review_application_is_derived_and_ignores_test_feedback(self):
        first=save_review(self.root,self.manifest,self.body(action='correct',corrected_data={'value':7,'label':'A'}))
        self.assertEqual(apply_human_reviews(self.root,self.manifest)['records'][0]['data']['value'],0)
        save_review(self.root,self.manifest,self.body(previous_event_id=first['event_id'],reviewer_kind='human',action='correct',corrected_data={'value':8,'label':'A'}))
        result=apply_human_reviews(self.root,self.manifest)
        self.assertEqual(result['records'][0]['data']['value'],8)
        self.assertEqual(self.manifest['records'][0]['data']['value'],0)
        save_review(self.root,self.manifest,self.body(record_id=self.manifest['records'][1]['id'],reviewer_kind='human',action='reject'))
        self.assertEqual(len(apply_human_reviews(self.root,self.manifest)['records']),1)


if __name__=='__main__':unittest.main()
