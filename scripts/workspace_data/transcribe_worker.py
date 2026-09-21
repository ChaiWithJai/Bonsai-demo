"""Isolated optional ASR runtime; no remote calls or automatic model downloads."""
import importlib.metadata
import json
import sys
from faster_whisper import WhisperModel
model=WhisperModel(sys.argv[2],device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
segments,info=model.transcribe(sys.argv[1],beam_size=5,language='en',temperature=0,condition_on_previous_text=False)
print(json.dumps({'runtime':importlib.metadata.version('faster-whisper'),'ctranslate2':importlib.metadata.version('ctranslate2'),
 'language':info.language,'duration':info.duration,'segments':[{'start_seconds':s.start,'end_seconds':s.end,'text':s.text.strip(),'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob} for s in segments]}))
