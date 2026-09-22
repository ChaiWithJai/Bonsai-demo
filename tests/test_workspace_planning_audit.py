import json
from pathlib import Path
import tempfile
import unittest
from workspace_planning_audit import audit

class PlanningAuditTests(unittest.TestCase):
    def job(self, root, key, *, status='awaiting_confirmation', schema='json_object', failed=False):
        p=root/key;p.mkdir()
        values={'status.json':{'id':key,'request':'PRIVATE PROMPT','filename':'private.pdf','status':status,
                             'proposal_contract':'source-proposal-v2-structured','proposal':{}},
                'source-packet.json':{'records':[{'text':'PRIVATE SOURCE'}]},'model-info.json':{'model':'frozen'},
                'model-0.json':{'request':{'messages':[{'role':'user','content':'PRIVATE PROMPT'}],
                                'seed':42,'response_format':{'type':schema}}}}
        if failed:
            del values['model-0.json'];values['status.json'].pop('proposal_contract');values['status.json'].pop('proposal')
            values['failure.json']={'provider_evidence':{'request':{'messages':[],'seed':42,'response_format':{'type':schema}}}}
        for name,value in values.items():(p/name).write_text(json.dumps(value))
        return p

    def test_matched_case_preserves_variant_and_excludes_live_jobs(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.job(root,'one');self.job(root,'two',schema='json_schema');self.job(root,'live',status='running')
            result=audit(root)
            self.assertEqual(result['summary']['indexed_jobs'],3)
            self.assertEqual(result['matched_cohorts'][0]['job_ids'],['one','two'])
            self.assertNotIn('PRIVATE',json.dumps(result));self.assertNotIn('private.pdf',json.dumps(result))
            self.assertTrue(all(r['semantic_quality']=='not_assessed' for r in result['jobs']))

    def test_transport_failure_and_unreadable_job_are_not_silent_successes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.job(root,'failed',status='failed',failed=True)
            p=root/'partial';p.mkdir();(p/'status.json').write_text('{')
            result=audit(root);row=result['jobs'][0]
            self.assertEqual(row['completed_responses'],0);self.assertEqual(row['request_attempts'],1)
            self.assertFalse(row['first_pass_valid']);self.assertFalse(row['proposal_validated'])
            self.assertEqual(len(result['unreadable_jobs']),1)
