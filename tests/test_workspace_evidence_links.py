import unittest
from workspace_tools import evidence_links

class EvidenceLinksTest(unittest.TestCase):
    def test_pages_timestamps_and_invalid_ids(self):
        sid='a'*64
        passages=[{'record_id':sid+':page','locator':{'page':3}},
                  {'record_id':sid+':audio','locator':{'start_seconds':0}},
                  {'record_id':sid+':video','locator':{'time_seconds':15}},
                  {'record_id':'../../escape','locator':{}}]
        links=evidence_links({'rows':[{'locator':{'source_evidence':passages}}]},'http://127.0.0.1:5257')
        self.assertEqual(len(links),3)
        self.assertTrue(links[sid+':page']['url'].endswith('/file#page=3'))
        self.assertTrue(links[sid+':audio']['url'].endswith('/file#t=0'))
        self.assertTrue(links[sid+':video']['url'].endswith('/file#t=15'))
