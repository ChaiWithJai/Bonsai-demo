import json
from pathlib import Path
import tempfile
import unittest
from workspace_sources import WorkspaceSources
from workspace_data.email_intake import extract_email
from test_workspace_sources import Client

MAIL=b'''From: Alex <alex@example.test>\nTo: Team <team@example.test>\nSubject: Launch review\nDate: Mon, 21 Sep 2026 09:30:00 -0400\nMessage-ID: <one@example.test>\nContent-Type: text/plain; charset=utf-8\n\nKeep the runtime review open.\n'''

class CollectionTest(unittest.TestCase):
    def test_collection_preserves_distinct_originals_and_record_identity(self):
        with tempfile.TemporaryDirectory() as root:
            sources=WorkspaceSources(root,Client(),'http://localhost:5210')
            email=sources.upload('review.eml',MAIL)
            table=sources.upload('metrics.csv',b'group,value\nA,0\nB,\n')
            combined=sources.collection([email['source_id'],table['source_id']])
            self.assertEqual(combined['kind'],'collection');self.assertEqual(combined['record_count'],3)
            self.assertEqual(combined['records'][0]['id'],email['records'][0]['id'])
            self.assertEqual(combined['records'][0]['locator']['source_filename'],'review.eml')
            self.assertTrue(combined['requires_structuring'])
            self.assertEqual(sources.download(email['source_id'])[0],MAIL)
            self.assertEqual(combined['records'][1]['data']['value'],'0')
            self.assertEqual(combined['records'][2]['data']['value'],'')
            self.assertEqual(sources.collection([email['source_id'],table['source_id']])['source_id'],combined['source_id'])
            snapshot=json.loads(sources.download(combined['source_id'])[0]);self.assertEqual(len(snapshot['sources']),2)
            with self.assertRaises(ValueError):sources.collection([email['source_id'],email['source_id']])
            with self.assertRaises(ValueError):sources.collection([combined['source_id'],email['source_id']])
            (Path(root)/email['source_id']/'source.bin').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'integrity'):sources.collection([email['source_id'],table['source_id']])

    def test_collection_applies_human_corrections_only_when_requested(self):
        with tempfile.TemporaryDirectory() as root:
            sources=WorkspaceSources(root,Client(),'http://localhost:5210')
            first=sources.upload('first.json',b'[{"value":1}]');second=sources.upload('second.json',b'[{"value":2}]')
            sources.review({'source_id':first['source_id'],'snapshot_id':first['review']['snapshot_id'],'record_id':first['records'][0]['id'],
                            'previous_event_id':None,'author':'Unit test simulated human','reviewer_kind':'human','action':'correct','note':'Isolated unit fixture','corrected_data':{'value':3}})
            raw=sources.collection([first['source_id'],second['source_id']])
            corrected=sources.collection([first['source_id'],second['source_id']],True)
            self.assertEqual(raw['records'][0]['data']['value'],1);self.assertEqual(corrected['records'][0]['data']['value'],3)
            self.assertNotEqual(raw['source_id'],corrected['source_id']);self.assertEqual(sources.get(first['source_id'])['records'][0]['data']['value'],1)

    def test_collection_exposes_member_coverage_to_planner(self):
        from workspace_data.desktop_plan import profile
        from test_workspace_docx import document
        with tempfile.TemporaryDirectory() as root:
            sources=WorkspaceSources(root,Client(),'http://localhost:5210')
            word=sources.upload('notes.docx',document('<w:p><w:r><w:t>Team note</w:t></w:r></w:p>'))
            email=sources.upload('review.eml',MAIL)
            combined=sources.collection([word['source_id'],email['source_id']])
            manifest=sources.manifest(combined['source_id'])
            coverage=profile(manifest)['source_coverage']
            self.assertEqual(coverage[0]['coverage']['document_coverage']['embedded_media_not_read'],1)
            self.assertIn('email_coverage',coverage[1]['coverage'])
            self.assertEqual(coverage[0]['source_id'],word['source_id'])
            self.assertEqual(json.loads(sources.download(combined['source_id'])[0])['schema_version'],2)

    def test_email_and_mbox_parse_headers_thread_ids_and_bodies(self):
        result=extract_email('message.eml',MAIL,100)
        row=result['records'][0]['data'];self.assertEqual(row['sent_date'],'2026-09-21');self.assertEqual(row['message_id'],'<one@example.test>')
        self.assertEqual(row['body'],'Keep the runtime review open.')
        second=MAIL.replace(b'<one@example.test>',b'<two@example.test>').replace(b'Keep the runtime review open.',b'The runtime review is complete.')
        mbox=b'From alex@example.test Mon Sep 21 09:30:00 2026\n'+MAIL+b'\nFrom alex@example.test Mon Sep 21 10:00:00 2026\n'+second
        parsed=extract_email('messages.mbox',mbox,100);self.assertEqual(len(parsed['records']),2)
        self.assertEqual(parsed['records'][1]['data']['body'],'The runtime review is complete.')
        with self.assertRaises(ValueError):extract_email('bad.mbox',b'not a mailbox',100)

    def test_html_email_extracts_text_without_executing_or_fetching_resources(self):
        html=MAIL.replace(b'text/plain',b'text/html').replace(b'Keep the runtime review open.',b'<style>secret css</style><p>Read <b>this</b>.</p><script>bad()</script><img src="https://example.test/tracker">')
        row=extract_email('html.eml',html,100)['records'][0]
        self.assertEqual(row['data']['body'],'Read this.');self.assertNotIn('bad()',row['data']['body'])
