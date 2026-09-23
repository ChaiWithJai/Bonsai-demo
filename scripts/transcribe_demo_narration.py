#!/usr/bin/env python3
"""CPU transcription for draft caption timing, never a pronunciation approval."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
from faster_whisper import WhisperModel

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def stamp(seconds):
    ms=round(seconds*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--job')
    args=p.parse_args()
    folders=sorted((ROOT/'.cache/demos/narration').glob(args.job or '*'))
    folders=[f for f in folders if (f/'narration.mp3').exists()]
    model=WhisperModel('small',device='cpu',compute_type='int8',cpu_threads=4,num_workers=1,download_root=str(ROOT/'.cache/narration-asr-models'))
    for folder in folders:
        audio=folder/'narration.mp3';target=folder/'transcript.json';audio_hash=sha(audio)
        if target.exists() and json.loads(target.read_text()).get('audio_sha256')==audio_hash:continue
        # No supplied script or language hint: preserve independent ASR observations.
        segments,info=model.transcribe(str(audio),beam_size=5,word_timestamps=True,condition_on_previous_text=False)
        rows=[{'start':s.start,'end':s.end,'text':s.text,'avg_logprob':s.avg_logprob,'words':[{'start':w.start,'end':w.end,'word':w.word,'probability':w.probability} for w in s.words or []]} for s in segments]
        result={'audio_sha256':audio_hash,'model':'Systran/faster-whisper-small','engine_version':importlib.metadata.version('faster-whisper'),'device':'cpu','compute_type':'int8','detected_language':info.language,'language_probability':info.language_probability,'segments':rows,'human_reviewed':False,'status':'asr_draft_not_pronunciation_approval'}
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        vtt='WEBVTT\n\n'+''.join(f'{stamp(s["start"])} --> {stamp(s["end"])}\n{s["text"].strip()}\n\n' for s in rows)
        (folder/'captions-draft.vtt').write_text(vtt)
        print(json.dumps({'job':folder.name,'detected_language':info.language,'segments':len(rows)}),flush=True)

if __name__=='__main__':main()
