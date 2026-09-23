#!/usr/bin/env python3
"""Assemble explicit audio-timed scenes from recorded source material."""
import argparse
import json
from pathlib import Path
from render_demo_edits import ROOT,segment,concatenate,run,sha,duration

def main():
    p=argparse.ArgumentParser();p.add_argument('plan');a=p.parse_args()
    plan_path=Path(a.plan);plan=json.loads(plan_path.read_text())
    audio=ROOT/plan['audio'];audio_seconds=duration(audio)
    if sha(audio)!=plan['audio_sha256']:raise ValueError('Audio changed since timing review')
    scenes=plan['scenes']
    if not scenes or scenes[0]['at']!=0 or any(b['at']<=a['at'] for a,b in zip(scenes,scenes[1:])):raise ValueError('Scene times must strictly increase from zero')
    if scenes[-1]['at']>=audio_seconds:raise ValueError('Last scene must begin before narration ends')
    output=ROOT/'.cache/demos/narrated-edits'/plan['id'];output.mkdir(parents=True,exist_ok=True)
    edits=[];parts=[]
    for i,scene in enumerate(scenes):
        source=ROOT/scene['source']
        if sha(source)!=scene['source_sha256']:raise ValueError('Source changed since scene review')
        target=(scenes[i+1]['at'] if i+1<len(scenes) else audio_seconds+2)-scene['at']
        length=min(scene['length'],target)
        label=scene['label']+(' · still evidence' if source.suffix=='.png' else (' · recorded excerpt + held frame' if target>length else ' · recorded excerpt'))
        part=output/f'scene-{i:02}.mp4'
        edits.append(segment(part,source,scene['start'],length,target,plan['title'],'DOLLY NARRATION · '+label));parts.append(part)
    visual=output/'visual.mp4';concatenate(parts,visual)
    final=output/'main.mp4'
    run(['ffmpeg','-v','error','-i',str(visual),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-af','apad','-t',str(audio_seconds+2),'-movflags','+faststart','-y',str(final)])
    run(['ffmpeg','-v','error','-i',str(final),'-f','null','-'])
    evidence={'status':'narrated_edit_pending_review','plan':plan,'plan_sha256':sha(plan_path),'edits':edits,'output_sha256':sha(final),'duration_seconds':duration(final),'human_reviewed':False}
    (output/'manifest.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(final)

if __name__=='__main__':main()
