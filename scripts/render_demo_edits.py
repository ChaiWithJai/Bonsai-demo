#!/usr/bin/env python3
"""Render auditable silent editorial drafts from actual Bonsai recordings.

No generated screen interaction or synthetic voice. Every trim, freeze and
source hash is recorded. Run with a Python containing Pillow and ffmpeg on PATH.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import textwrap
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT = '/System/Library/Fonts/Supplemental/Arial.ttf'
W,H = 1440,1080


def run(args):
    result = subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-4000:])


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def duration(p):
    return float(subprocess.check_output(['ffprobe','-v','quiet','-show_entries','format=duration','-of','csv=p=0',str(p)]))


def card(path,title,body):
    im=Image.new('RGB',(W,1000),'#f3f0e9'); d=ImageDraw.Draw(im)
    d.text((70,65),title,font=ImageFont.truetype(FONT,38),fill='#242b33')
    lines=[]
    for para in body.splitlines():
        lines.extend(textwrap.wrap(para,92) or [''])
    size=28 if len(lines)<=23 else 22
    y=150
    for line in lines:
        if y+size>965:raise ValueError('Card exceeds frame; use an explicitly labelled excerpt')
        d.text((70,y),line,font=ImageFont.truetype(FONT,size),fill='#242b33');y+=size+9
    im.save(path)


def banner(path,title,label):
    im=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(im)
    d.rectangle((0,0,W,79),fill='#242b33')
    d.text((28,10),title,font=ImageFont.truetype(FONT,26),fill='white')
    d.text((28,46),label,font=ImageFont.truetype(FONT,19),fill='#dfd9c9')
    im.save(path)


def segment(out,source,start,length,target,title,label):
    overlay=out.with_suffix('.png');banner(overlay,title,label)
    is_image=source.suffix.lower() in ('.png','.jpg')
    held=max(0,target-length) if not is_image else target
    inputs=['-loop','1','-i',str(source)] if is_image else ['-ss',str(start),'-t',str(length),'-i',str(source)]
    filt=f'[0:v]fps=25,scale=1440:1000:force_original_aspect_ratio=decrease,pad=1440:1000:(ow-iw)/2:(oh-ih)/2:color=0xf3f0e9,setsar=1,tpad=stop_mode=clone:stop_duration={held},pad=1440:1080:0:80:color=0x242b33[v];[v][1:v]overlay=0:0:shortest=1,format=yuv420p[out]'
    run(['ffmpeg','-hide_banner','-loglevel','error',*inputs,'-loop','1','-i',str(overlay),'-filter_complex',filt,'-map','[out]','-an','-t',str(target),'-c:v','libx264','-preset','veryfast','-crf','22','-threads','2','-y',str(out)])
    return {'source':str(source.relative_to(ROOT)),'source_sha256':sha(source),'start_seconds':start,
            'source_seconds':length,'output_seconds':target,'held_frame_seconds':held,'label':label,
            'output_sha256':sha(out)}


def concatenate(parts,out):
    listing=out.with_suffix('.concat.txt')
    listing.write_text(''.join("file '"+str(p.resolve()).replace("'","'\\''")+"'\n" for p in parts))
    run(['ffmpeg','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart','-y',str(out)])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='.cache/demos/visual-edits');args=parser.parse_args()
    output=ROOT/args.output;output.mkdir(parents=True,exist_ok=True);cards=output/'cards';cards.mkdir(exist_ok=True)
    card(cards/'financial-proof.png','Checked arithmetic · synthetic financial case','Original answer later claimed USD 95 million of excess net debt.\n\nSource inputs: net debt 69; approved EBITDA 19; maximum leverage 3.50.\n\nMaximum net debt = 3.50 × 19 = 66.5 million.\nExcess net debt = 69 − 66.5 = 2.5 million.\n\nThe ratio 69 / 19 ≈ 3.63 was correct. The later dollar claim was not.\n\nAnalyst arithmetic check; not a human-reviewed training label.')
    card(cards/'legal-proof.png','Evidence scope · synthetic legal case','Observed answer: “A service interruption that is not a material breach gives no termination right at all.”\n\nThe supplied clause supports a narrower statement: interruption alone does not establish a termination right under section 12.1.\n\nOther provisions and legal grounds were not supplied.\n\nThis is an analyst assessment of source scope, not a legal determination.')
    card(cards/'diagnostic.png','What the activation view does and does not show','32 recorded answer tokens are fed through a reconstructed prefix.\nThree selected layers produce 96 measured vectors, each 5,120 values wide.\n\nThese are new teacher-forced measurements.\nThey are not the original activations.\nThey do not establish why the original error occurred.\n\nInspect sources, recorded model/tool events, and diagnostic measurements together.\n\nLocal Bonsai 2 27B · Apple M5 Pro · 48 GiB memory.')
    for kind,file in [('financial','lender-review.txt'),('legal','agreement-exceptions.txt')]:
        source=ROOT/'evals/demos'/kind/file
        if not source.exists() and kind=='legal':source=next((ROOT/'evals/demos/legal').glob('*agreement*'))
        text=source.read_text();card(cards/(kind+'-source.png'),'Source excerpt · '+source.name,'\n'.join(text.splitlines()[:19]))
    bond=ROOT/'.cache/demos/bond-image-workflow-20260923/raw-screen.webm'
    treasury=ROOT/'.cache/demos/native-treasury-20260923/raw-screen.webm'
    fin=ROOT/'.cache/demos/native-diligence-financial-20260923/raw-screen.webm'
    legal=ROOT/'.cache/demos/native-diligence-legal-20260923/raw-screen.webm'
    def clip(p,s,l,t,caption):return (p,s,l,t,caption+(' · held frame' if t>l else ' · recorded excerpt'))
    def still(p,t,caption):return (p,0,t,t,caption+' · still evidence')
    specs=[('01-bond-learning','Understand each bond payment',[
       clip(bond,63,2,5,'Result first: inspect a yield change'),clip(bond,0,4,10,'Synthetic sample worksheet'),
       clip(bond,19,8,12,'Confirm the missing yield'),clip(bond,31,14,14,'Checked calculation in New chat'),
       clip(bond,61,4,14,'Inspect and reprice payments'),clip(treasury,23,3,10,'Dated Treasury context'),clip(bond,63,2,5,'Try your own working')],[bond,treasury]),
      ('02-financial-diligence','Reconcile the lender definition',[
       clip(fin,39,6,6,'Result first: leverage exceeds the stated limit'),still(cards/'financial-source.png',14,'Synthetic source'),
       clip(fin,39,21,21,'Calculation and source comparison'),clip(fin,73,5,14,'Retain the erroneous final claim'),
       still(cards/'financial-proof.png',15,'Check the arithmetic')],[fin]),
      ('03-legal-diligence','Inspect agreement exceptions',[
       clip(legal,90,6,6,'Result first: summary and agreement differ'),still(cards/'legal-source.png',14,'Synthetic source excerpt'),
       clip(legal,85,25,25,'Inspect clauses and exceptions'),clip(legal,123,2,10,'Retain the overbroad claim'),
       still(cards/'legal-proof.png',15,'Review the scope of the conclusion')],[legal])]
    for num,kind,source in [('04','financial',fin),('05','legal',legal)]:
        diag=ROOT/f'.cache/demos/{kind}-activation-inspection-20260923/raw-screen-v2.webm'
        shot=ROOT/f'tools/design-review/shots/92-{kind}-activation-window.desktop.png'
        specs.append((num+'-'+kind+'-error-inspection','Inspect the '+kind+' mistake',[
          still(cards/(kind+'-proof.png'),10,'Observed error and evidence check'),still(cards/(kind+'-source.png'),10,'Synthetic source excerpt'),
          clip(source,73 if kind=='financial' else 123,5 if kind=='financial' else 2,12,'Original answer'),
          clip(diag,0,duration(diag),10,'Measured diagnostic interaction'),still(shot,18,'Inspect captured values'),
          still(cards/'diagnostic.png',10,'Limits and next action')],[source,diag]))
    index=[]
    for ident,title,segments,raws in specs:
        folder=output/ident;folder.mkdir(exist_ok=True);edits=[];parts=[]
        for i,(source,start,length,target,label) in enumerate(segments):
            part=folder/f'segment-{i:02}.mp4'
            edits.append(segment(part,source,start,length,target,title,'SILENT DRAFT · '+label));parts.append(part)
        main=folder/'main-visual-draft.mp4';concatenate(parts,main)
        # The result clip is an explicit excerpt from the edited draft.
        short=folder/'short-visual-draft.mp4'
        run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(main),'-t','20','-c','copy','-movflags','+faststart','-y',str(short)])
        walks=[]
        for i,raw in enumerate(raws):
            p=folder/f'walkthrough-{i:02}.mp4';n=duration(raw)
            segment(p,raw,0,n,n,title,'UNVOICED WALKTHROUGH · original recording · synthetic development case');walks.append(p)
        walk=folder/'walkthrough-unvoiced.mp4';concatenate(walks,walk)
        manifest={'id':ident,'status':'visual_edit_draft_audio_pending','no_human_camera_or_microphone_track':True,
                  'edits':edits,'outputs':{p.name:{'sha256':sha(p),'duration_seconds':duration(p)} for p in [main,short,walk]},
                  'narration':'Blocked on AI_GATEWAY_API_KEY; no replacement voice used',
                  'review':'Automated render and visual inspection; not human signoff'}
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');index.append(manifest)
        print(ident,'rendered',flush=True)
    (output/'manifest.json').write_text(json.dumps(index,indent=2)+'\n')
    rows=''.join(f'<section><h2>{x["id"]}</h2><video controls preload="metadata" src="{x["id"]}/main-visual-draft.mp4"></video><p><a href="{x["id"]}/short-visual-draft.mp4">Short cut</a> · <a href="{x["id"]}/walkthrough-unvoiced.mp4">Unvoiced walkthrough</a> · <a href="{x["id"]}/manifest.json">Edit evidence</a></p></section>' for x in index)
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Bonsai demo visual drafts</title><style>body{font:16px system-ui;background:#f3f0e9;color:#242b33;max-width:1100px;margin:40px auto}video{width:100%}section{margin:40px 0}a{color:#315940}</style><h1>Five visual drafts</h1><p>Actual recorded runs. Silent editorial drafts; Dolly narration and six-language delivery are incomplete. Holds and edits are labeled. Synthetic documents are not customer cases.</p>'+rows)

if __name__=='__main__':main()
