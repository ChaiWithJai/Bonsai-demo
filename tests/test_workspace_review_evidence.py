import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from workspace_review_evidence import source_evidence

class EvidenceTest(unittest.TestCase):
    def test_original_integrity_and_complete_evidence_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); jid = 'a' * 32; folder = root / 'source-jobs' / jid
            folder.mkdir(parents=True)
            raw = b'Original data'
            (folder / 'source.bin').write_bytes(raw)
            (folder / 'original-manifest.json').write_text(json.dumps({'sha256':hashlib.sha256(raw).hexdigest()}))
            names = ('source-manifest.json','proposal.json','compiled.json','source-packet.json',
                     'confirmation.json','model-info.json','harness-hashes.json','planning-status.json')
            for name in names: (folder / name).write_text('{}')
            fixture = {'source_job': {'id': jid}}
            self.assertEqual(len(source_evidence(root, fixture)), 10)
            (folder / 'proposal.json').unlink()
            with self.assertRaisesRegex(ValueError, 'incomplete'): source_evidence(root, fixture)
            (folder / 'proposal.json').write_text('{}')
            (folder / 'source.bin').write_bytes(b'Changed')
            with self.assertRaisesRegex(ValueError, 'integrity'): source_evidence(root, fixture)

    def test_job_reference_cannot_escape_store(self):
        with self.assertRaises(ValueError): source_evidence('/tmp', {'source_job': {'id':'../escape'}})
        self.assertEqual(source_evidence('/tmp', {'kind':'test'}), [])

    def test_interpretation_export_does_not_require_build_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); jid='b'*32; folder=root/'source-jobs'/jid
            folder.mkdir(parents=True)
            raw=b'Unbuilt source'
            (folder/'source.bin').write_bytes(raw)
            (folder/'original-manifest.json').write_text(json.dumps({'sha256':hashlib.sha256(raw).hexdigest()}))
            for name in ('source-manifest.json','proposal.json','source-packet.json','model-info.json','harness-hashes.json'):
                (folder/name).write_text('{}')
            fixture={'source_job':{'id':jid}}
            self.assertEqual(len(source_evidence(root,fixture,require_build=False)),7)
            with self.assertRaisesRegex(ValueError,'incomplete'):
                source_evidence(root,fixture)
            (folder/'source.bin').write_bytes(b'Altered')
            with self.assertRaisesRegex(ValueError,'integrity'):
                source_evidence(root,fixture,require_build=False)
