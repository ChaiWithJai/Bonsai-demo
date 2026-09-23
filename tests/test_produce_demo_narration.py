import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from produce_demo_narration import jobs, reusable, synthesize, ROOT, MODEL, VOICE, digest


class NarrationProductionTests(unittest.TestCase):
    def test_complete_language_demo_matrix(self):
        queue=jobs(ROOT/'docs/demos/scripts/localizations.json')
        self.assertEqual(len(queue),30)
        self.assertEqual(len({j['id'] for j in queue}),30)
        self.assertTrue(all(j['direction']=='rtl' for j in queue if j['language']=='fa'))
        self.assertTrue(all(j['human_reviewed'] is False for j in queue))

    def test_different_voice_is_rejected_before_writing_audio(self):
        job=jobs(ROOT/'docs/demos/scripts/localizations.json')[0]
        request=Mock(return_value={'model':MODEL,'voice':'wrong-voice','language':'zh'})
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,'unexpected model, voice, or language'):
                synthesize(job,Path(td),request)
            self.assertEqual(list(Path(td).iterdir()),[])

    def test_resume_requires_audio_integrity_and_same_request(self):
        job=jobs(ROOT/'docs/demos/scripts/localizations.json')[0]
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td);audio=folder/'narration.mp3';audio.write_bytes(b'fixture-not-real-audio')
            metadata={**job,'status':'synthesized_needs_listening_review','audio_sha256':digest(audio.read_bytes())}
            (folder/'job.json').write_text(json.dumps(metadata))
            self.assertIsNotNone(reusable(job,folder))
            self.assertIsNone(reusable({**job,'request_sha256':'changed'},folder))
            audio.write_bytes(b'corrupted')
            self.assertIsNone(reusable(job,folder))

    def test_invalid_audio_is_rejected(self):
        job=jobs(ROOT/'docs/demos/scripts/localizations.json')[0]
        request=Mock(return_value={'model':MODEL,'voice':VOICE,'language':'zh','media_type':'audio/mpeg','audio_base64':'!notbase64'})
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):synthesize(job,Path(td),request)
            self.assertEqual(list(Path(td).iterdir()),[])
