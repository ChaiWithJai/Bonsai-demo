#!/usr/bin/env python3
"""Plan or resume the 30 Dolly/Fish Audio narration jobs through AI Gateway.

Default is a local plan. --execute performs the user-requested speech calls.
Completed outputs are reused only when their request and audio hashes match.
No substitute provider, automatic retry, inferred review label, or secret logging.
"""
import argparse
import base64
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys
from workspace_gateway import gateway_request

ROOT=Path(__file__).resolve().parents[1]
MODEL='fish-audio/s2.1-pro-free'
LANGUAGES=('zh','fa','pt','hi','kn','fr')
VOICE='ce3b16c14af54adebba5ebe50a3d4417'


def digest(raw):return hashlib.sha256(raw).hexdigest()


def save(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temp.replace(path)


def jobs(source):
    data=json.loads(source.read_text())
    master=ROOT/'docs/demos/scripts/english-masters.json'
    if data['source_master_sha256']!=digest(master.read_bytes()):
        raise ValueError('English masters changed; review translations before synthesizing')
    expected={d['id'] for d in json.loads(master.read_text())['demos']}
    if set(data['languages'])!=set(LANGUAGES):raise ValueError('All six requested languages are required')
    result=[]
    for language in LANGUAGES:
        entries=data['languages'][language]['demos']
        if len(entries)!=5 or {d['id'] for d in entries}!=expected:
            raise ValueError('Each language must contain the five distinct demos')
        for entry in entries:
            text=entry['narration']
            if not isinstance(text,str) or not text.strip() or len(text)>15000:
                raise ValueError('Invalid narration text')
            payload={'operation':'narrate','language':language,'text':text}
            identity={'request':payload,'model':MODEL,'voice':VOICE}
            result.append({'id':entry['id']+'-'+language,'demo':entry['id'],'language':language,
                           'locale':data['languages'][language]['locale'],
                           'direction':data['languages'][language]['direction'],
                           'request':payload,'request_sha256':digest(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()),
                           'model':MODEL,'voice':VOICE,'human_reviewed':False})
    return result


def configuration():
    # Return presence flags and the public voice identifier, never credential values.
    code='console.log(JSON.stringify({authenticated:!!(process.env.AI_GATEWAY_API_KEY||process.env.VERCEL_OIDC_TOKEN),voice:process.env.BONSAI_DOLLY_VOICE_ID||null}))'
    value=subprocess.run(['node','--env-file-if-exists='+str(ROOT/'.env'),'-e',code],capture_output=True,text=True,check=True)
    return json.loads(value.stdout)


def synthesize(job,folder,request_fn=gateway_request):
    result=request_fn(job['request'])
    if result.get('model')!=MODEL or result.get('voice')!=VOICE or result.get('language')!=job['language']:
        raise ValueError('Speech provider returned an unexpected model, voice, or language')
    if result.get('media_type') not in ('audio/mpeg','audio/mp3'):
        raise ValueError('Speech provider did not return MP3 audio')
    raw=base64.b64decode(result['audio_base64'],validate=True)
    if not 100<len(raw)<30_000_000:raise ValueError('Unexpected audio size')
    audio=folder/'narration.mp3';temporary=folder/'narration.pending.mp3';temporary.write_bytes(raw)
    try:
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(temporary)]))
        streams=probe.get('streams',[])
        if len(streams)!=1 or streams[0].get('codec_type')!='audio':raise ValueError('Expected one audio stream')
        seconds=float(probe['format']['duration'])
        if not 1<seconds<240:raise ValueError('Unexpected narration duration')
        subprocess.run(['ffmpeg','-v','error','-i',str(temporary),'-f','null','-'],check=True,capture_output=True)
        temporary.replace(audio)
    finally:
        temporary.unlink(missing_ok=True)
    metadata={k:v for k,v in result.items() if k!='audio_base64'}
    return {**job,'status':'synthesized_needs_listening_review','duration_seconds':seconds,
            'audio_sha256':digest(raw),'provider':metadata,'timing_fits_main_window':60<=seconds<=90,
            'subtitle_status':'not_aligned','human_reviewed':False}


def reusable(job,folder):
    meta=folder/'job.json';audio=folder/'narration.mp3'
    if not meta.exists() or not audio.exists():return None
    previous=json.loads(meta.read_text())
    if previous.get('request_sha256')==job['request_sha256'] and previous.get('audio_sha256')==digest(audio.read_bytes()) and previous.get('status')=='synthesized_needs_listening_review':return previous
    return None


def review_page(source, output):
    data=json.loads(source.read_text())
    masters={x['id']:x for x in json.loads((ROOT/'docs/demos/scripts/english-masters.json').read_text())['demos']}
    sections=[]
    for language, group in data['languages'].items():
        cards=[]
        for entry in group['demos']:
            ident=entry['id']
            text=''.join('<p>'+html.escape(p)+'</p>' for p in entry['paragraphs'])
            cards.append(f'<details><summary>{html.escape(masters[ident]["title"])}</summary><video controls preload="none" src="../visual-edits/{ident}/main-visual-draft.mp4"></video><div class="columns"><article lang="en"><h3>English master</h3><p>{html.escape(masters[ident]["narration"])}</p></article><article lang="{group["locale"]}" dir="{group["direction"]}"><h3>{language} · draft</h3>{text}</article></div></details>')
        sections.append('<section><h2>'+group['locale']+'</h2>'+''.join(cards)+'</section>')
    css='body{font:17px/1.6 system-ui;background:#f3f0e9;color:#242b33;max-width:1200px;margin:32px auto;padding:0 20px}details{background:#fff9;border:1px solid #cbc7bf;border-radius:12px;padding:16px;margin:12px 0}summary{cursor:pointer;font-weight:600}.columns{display:grid;grid-template-columns:1fr 1fr;gap:32px}article{min-width:0}video{max-width:800px;width:100%;display:block;margin:20px auto}article[dir=rtl]{font-size:20px}@media(max-width:750px){.columns{grid-template-columns:1fr}}'
    (output/'review.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Bonsai narration review</title><style>'+css+'</style><h1>30 narration drafts</h1><p>Five demonstrations in six languages. Translations are drafts, not native-speaker approvals. Videos are silent visual edits. Dolly synthesis, pronunciation, subtitles and synchronization remain incomplete.</p>'+''.join(sections)+'</html>')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--language',choices=LANGUAGES);parser.add_argument('--demo');parser.add_argument('--output',default='.cache/demos/narration');args=parser.parse_args()
    source=ROOT/'docs/demos/scripts/localizations.json';queue=jobs(source)
    if args.language:queue=[j for j in queue if j['language']==args.language]
    if args.demo:queue=[j for j in queue if j['demo']==args.demo]
    if not queue:raise ValueError('No matching narration jobs')
    output=ROOT/args.output;output.mkdir(parents=True,exist_ok=True)
    config=configuration()
    report={'status':'planned','source_sha256':digest(source.read_bytes()),'credential_present':config['authenticated'],
            'configured_voice_matches_dolly':config['voice']==VOICE,'jobs':[]}
    for job in queue:
        folder=output/job['id'];folder.mkdir(exist_ok=True)
        existing=reusable(job,folder)
        report['jobs'].append(existing or {**job,'status':'pending'})
    save(output/'queue.json',report)
    review_page(source,output)
    if not args.execute:
        print(json.dumps({'jobs':len(queue),'credential_present':config['authenticated'],'voice_matches':config['voice']==VOICE,'queue':str(output/'queue.json')}));return
    if not config['authenticated'] or config['voice']!=VOICE:
        report['status']='blocked_configuration';save(output/'queue.json',report)
        raise ValueError('Set server-side Gateway authentication and the configured Dolly voice before execution')
    for index,job in enumerate(queue):
        folder=output/job['id']
        if reusable(job,folder):continue
        save(folder/'request.json',job)
        try:
            completed=synthesize(job,folder);save(folder/'job.json',completed);report['jobs'][index]=completed
        except Exception:
            report['jobs'][index]={**job,'status':'failed','error':'Speech synthesis or audio validation failed; no automatic retry performed'}
            report['status']='stopped_after_failure';save(output/'queue.json',report)
            raise RuntimeError('Narration job failed: '+job['id']) from None
        save(output/'queue.json',report);print(job['id'],'synthesized; listening review required',flush=True)
    report['status']='synthesized_needs_listening_review';save(output/'queue.json',report)


if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(1)
