import copy
import unittest
from workspace_diligence import validate, source_quote


class DiligenceEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.packet = [{'id': 'S1', 'text': 'Only 1 of the 4 requested addbacks is approved.'}]
        self.proposal = {'summary': 'Approval differs from the request.', 'findings': [{
            'claim': 'All four addbacks are approved', 'assessment': 'conflicting',
            'explanation': 'The approved amount is smaller.',
            'evidence': [{'source': 'S1', 'quote': 'Only 1 of the 4 requested addbacks is approved.'}],
            'next_question': 'Has the remaining amount been approved since this document?'}]}

    def test_exact_source_quote_is_preserved(self):
        self.assertEqual(validate(self.proposal, self.packet), self.proposal)

    def test_whitespace_repair_preserves_original_and_rejects_paraphrase(self):
        original = 'Only 1 of the 4 requested\naddbacks is approved.'
        self.assertEqual(source_quote(original, original.replace('\n', ' ')), original)
        with self.assertRaises(ValueError):
            source_quote(original, 'Only one of four requested addbacks is approved.')

    def test_invented_quote_or_source_and_unbounded_labels_are_rejected(self):
        for field, value in [('quote', 'All 4 addbacks are approved.'), ('source', 'S2')]:
            bad = copy.deepcopy(self.proposal);bad['findings'][0]['evidence'][0][field] = value
            with self.assertRaises(ValueError):
                validate(bad, self.packet)
        bad = copy.deepcopy(self.proposal);bad['findings'][0]['assessment'] = 'human_approved'
        with self.assertRaises(ValueError):
            validate(bad, self.packet)
