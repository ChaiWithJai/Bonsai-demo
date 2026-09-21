"""Development video: CPU speech, Bonsai frames, then an unconfirmed source proposal."""
import hashlib,json,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'.cache/video-speech-development/live'
if OUT.exists():raise SystemExit('Preserve prior execution; inspect its saved job IDs')
OUT.mkdir()
def save(name,value):(OUT/name).write_text(json.dumps(value,indent=2))
def api(path,body=None,raw=None):
 data=raw if raw is not None else json.dumps(body).encode() if body is not None else None
 headers={'Content-Type':'application/octet-stream','X-Source-Filename':'development-narrated-observations.mp4'} if raw is not None else {'Content-Type':'application/json'}
 with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:5257/api/workspace'+path,data=data,headers=headers),timeout=330) as r:return json.load(r)
state=api('');assert not state['running_attempts'] and not state['running_source_jobs'];save('runtime.json',state)
raw=(ROOT/'.cache/video-speech-development/development-narrated-observations.mp4').read_bytes()
save('protocol.json',{'scope':'Synthetic development video, English speech and a sampled frame','source_sha256':hashlib.sha256(raw).hexdigest(),'confirmed':False,'harness_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['scripts/workspace_data/video.py','scripts/workspace_data/audio.py','scripts/workspace_data/vision.py','scripts/workspace_vision_jobs.py','scripts/workspace_data/desktop_plan.py']}})
source=api('/sources',raw=raw);save('uploaded.json',source)
speech=api('/sources/'+source['source_id']+'/extract',{});save('speech.json',speech)
assert speech.get('audio_coverage') and not speech.get('speech_extraction_error'),speech
job=api('/sources/'+source['source_id']+'/vision',{});save('vision-started.json',job);print('vision '+job['id'],flush=True)
def observe(job,name):
 for _ in range(330):
  try:
   status=api('/source-jobs/'+job['id']);save(name,status)
   if status['status'] not in ('queued','running'):return status
  except Exception as exc:save('observation-error.json',{'job_id':job['id'],'error':str(exc)})
  time.sleep(2)
 raise RuntimeError('Observation window ended; inspect same job, do not restart')
terminal=observe(job,'vision-latest.json');assert terminal['status']=='completed',terminal
# Status precedes evidence export; wait for this reservation to be released.
for _ in range(60):
 if job['id'] not in api('')['running_source_jobs']:break
 time.sleep(1)
else:raise RuntimeError('Vision still owns its reservation')
merged=api('/sources/'+source['source_id']);save('merged.json',merged)
assert all(row in merged['records'] for row in speech['records'])
assert any(row['locator'].get('evidence_channel')=='visual' for row in merged['records'])
assert merged['kind']=='video'
job=api('/sources/'+source['source_id']+'/generate',{'request':'Structure this development video into visible observations and spoken requirements. Preserve the evidence channel and timestamp for every record. Do not treat a spoken requirement as a measured value or infer that speech and screen content prove each other. Propose an explorable source-linked view.'});save('planning-started.json',job);print('planning '+job['id'],flush=True)
terminal=observe(job,'planning-latest.json');assert terminal['status']=='awaiting_confirmation',terminal
print('Proposal awaits review; no confirmation submitted',flush=True)
