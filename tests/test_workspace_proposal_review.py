import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from workspace_data import proposal_review as review


class ProposalReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.proposal = {'structure': {'records': [{'data': {'count': 0}}]}}
        self.job = {'id': 'fixture', 'status': 'awaiting_confirmation', 'request': 'Interpret this fixture',
                    'proposal_contract': 'source-proposal-v2-structured', 'proposal': self.proposal,
                    'proposal_sha256': hashlib.sha256(json.dumps(self.proposal, sort_keys=True).encode()).hexdigest(),
                    'planning_run_id': 'test-run'}
        (self.root/'source-manifest.json').write_text(json.dumps({'source_id': 'fixture', 'sha256': 'original-hash', 'records': []}))
        (self.root/'source-packet.json').write_text(json.dumps({'records': [], 'coverage': 'Synthetic partial context'}))

    def save(self, kind='test', action='accept', **overrides):
        current = review.state(self.root, self.job)
        return review.save(self.root, self.job, {
            'proposal_sha256': current['proposal_sha256'], 'source_snapshot_sha256': current['source_snapshot_sha256'],
            'input_sha256': current['input_sha256'],
            'previous_event_id': current['latest']['event_id'] if current['latest'] else None,
            'author': 'Synthetic unit test', 'reviewer_kind': kind, 'action': action, 'note': 'Isolated policy test', **overrides})

    def test_build_confirmation_and_automated_reviews_are_not_training_labels(self):
        self.job['status'] = 'completed'
        self.job['confirmation'] = {'decision': 'accept'}
        self.assertEqual(review.export(self.root, self.job)['example_count'], 0)
        for kind in ('test', 'codex'):
            self.save(kind)
            self.assertEqual(review.export(self.root, self.job)['example_count'], 0)

    def test_human_acceptance_binds_source_context_target_and_review(self):
        # 'human' exercises the export policy only in this temporary database.
        event = self.save('human')
        bundle = review.export(self.root, self.job)
        candidate = bundle['training_candidates'][0]
        self.assertEqual(candidate['review'], event)
        self.assertEqual(candidate['target'], self.proposal)
        self.assertEqual(candidate['source_manifest']['sha256'], 'original-hash')
        self.assertEqual(candidate['source_packet']['coverage'], 'Synthetic partial context')
        self.assertEqual(candidate['planning_run_id'], 'test-run')
        self.assertEqual(bundle['dataset_sha256'], review.export(self.root, self.job)['dataset_sha256'])
        self.save('human', 'defer')
        self.assertEqual(review.export(self.root, self.job)['example_count'], 0)
        self.assertEqual(len(review.state(self.root, self.job)['events']), 2)

    def test_stale_review_and_changed_source_are_rejected(self):
        self.save('human')
        with self.assertRaisesRegex(ValueError, 'Another review'):
            self.save('human', previous_event_id=None)
        old = review.state(self.root, self.job)['source_snapshot_sha256']
        (self.root/'source-manifest.json').write_text('{"source_id":"changed"}')
        self.assertEqual(review.export(self.root, self.job)['example_count'], 0)
        with self.assertRaisesRegex(ValueError, 'source changed'):
            self.save('human', source_snapshot_sha256=old)

    def test_superseded_proposal_cannot_be_accepted_or_exported(self):
        self.save('human')
        self.job['status'] = 'superseded'
        self.assertEqual(review.export(self.root, self.job)['example_count'], 0)
        with self.assertRaisesRegex(ValueError, 'latest revised'):
            self.save('human')

    def test_mutated_proposal_is_not_its_saved_version(self):
        self.proposal['structure']['records'][0]['data']['count'] = 12
        with self.assertRaisesRegex(ValueError, 'recorded version'):
            review.export(self.root, self.job)

    def test_changed_question_or_packet_requires_another_review(self):
        self.save('human')
        self.job['request'] = 'A different interpretation task'
        self.assertEqual(review.export(self.root, self.job)['example_count'], 0)
        self.save('human')
        (self.root/'source-packet.json').write_text('{"records":[],"coverage":"Changed"}')
        self.assertEqual(review.export(self.root, self.job)['example_count'], 0)

    def test_completed_export_uses_archived_planning_trace(self):
        self.job.update(status='completed', run_id='build-run', trace_id='build-trace')
        (self.root/'planning-status.json').write_text('{"run_id":"planning-run","trace_id":"planning-trace"}')
        self.save('human')
        candidate = review.export(self.root, self.job)['training_candidates'][0]
        self.assertEqual(candidate['planning_run_id'], 'planning-run')
        self.assertEqual(candidate['planning_trace_id'], 'planning-trace')
