"""Timestamped CPU transcription using the prototype's pinned Whisper adapter."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

MODEL_SHA='2a166925539a16005f14ff328359f9b9adb9dc4fb631bb3b227526862e93e2ef'

def extract_audio(content,evidence):
    evidence=Path(evidence);evidence.mkdir(parents=True,exist_ok=True)
    python=os.environ.get('BONSAI_AUDIO_PYTHON');model=os.environ.get('BONSAI_AUDIO_MODEL_DIR')
    if not python or not model:raise ValueError('Local speech adapter is not configured; original audio is preserved')
    model=Path(model)
    if hashlib.sha256((model/'model.bin').read_bytes()).hexdigest()!=MODEL_SHA:raise ValueError('Speech model checksum mismatch')
    with tempfile.TemporaryDirectory(prefix='bonsai-speech-') as folder:
        path=Path(folder)/'source';path.write_bytes(content)
        probe=subprocess.run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],capture_output=True,timeout=30,check=True)
        metadata=json.loads(probe.stdout);duration=float(metadata['format']['duration'])
        if not math.isfinite(duration) or not 0<duration<=300:raise ValueError('Speech extraction currently accepts up to five minutes')
        if not any(s.get('codec_type')=='audio' for s in metadata['streams']):raise ValueError('No audio stream found')
        (evidence/'media-metadata.json').write_text(json.dumps(metadata,indent=2))
        result=subprocess.run([python,str(Path(__file__).with_name('transcribe_worker.py')),str(path),str(model)],capture_output=True,timeout=300)
        (evidence/'transcription-stderr.txt').write_bytes(result.stderr)
        if result.returncode:raise ValueError('Speech transcription failed: '+result.stderr.decode(errors='replace')[-1000:])
        transcript=json.loads(result.stdout)
    (evidence/'transcript.json').write_text(json.dumps(transcript,indent=2,ensure_ascii=False))
    records=[]
    for i,segment in enumerate(transcript['segments'],1):
        start,end=segment['start_seconds'],segment['end_seconds'];text=segment['text'].strip()
        if not all(type(t) in (int,float) and math.isfinite(t) for t in (start,end)) or not 0<=start<=end<=duration+1:raise ValueError('Invalid speech timestamp')
        if text:records.append({'locator':{'segment':i,'start_seconds':start,'end_seconds':end},'data':{'text':text,'start_seconds':start,'end_seconds':end}})
    if not records:raise ValueError('No speech transcribed; original audio is preserved')
    return {'kind':'audio','status':'extracted','extractor':'faster-whisper-base.en-cpu-int8','requires_structuring':True,'records':records,
            'review_status':'transcript_unreviewed','audio_coverage':{'duration_seconds':duration,'segments':len(records),'model_sha256':MODEL_SHA,
            'limitation':'English speech transcription using Whisper on CPU, not native Bonsai audio. No speaker identification. Transcription may contain errors and needs review.'}}
