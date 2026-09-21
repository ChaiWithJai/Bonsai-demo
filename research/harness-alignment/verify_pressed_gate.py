"""Post-run gate audit of preserved development outputs. Performs no inference."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'.cache/pressed-gate-audit'
if OUT.exists():
    raise SystemExit('Audit directory already exists; preserve the prior evidence')
OUT.mkdir()

def api(path,body=None):
    request=urllib.request.Request('http://127.0.0.1:5257/api/workspace'+path,
                                  data=json.dumps(body).encode() if body is not None else None,
                                  headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=120) as response:
        return json.load(response)

def step(name,action,value):
    return {'target':{'role':'button','name':name},'action':action,'value':value}

contract=[step('Measured observations','click',None),
          step('Measured observations','pressed',True),
          step('All records','pressed',False),
          step('Spoken requirements','pressed',False),
          step('Clear filters','click',None),step('All records','pressed',True),
          step('Measured observations','pressed',False)]
(OUT/'contract.json').write_text(json.dumps(contract,indent=2))
summary={'scope':'Post-run check on preserved development outputs; original trial outcomes unchanged',
         'inference_submitted':False,'contract':contract,'results':[],
         'checker_sha256':hashlib.sha256((ROOT/'scripts/workspace-tools/check_request.mjs').read_bytes()).hexdigest()}
for profile,key,expected in [('legacy-greedy','7eda27addd6943ebb127bea7dc852da9',False),
                             ('bonsai2-instruct','32403b0a26bd447abcfebd26c9ef3b59',True)]:
    before=api('/'+key)
    preview=api('/'+key+'/preview',{})
    assert preview.get('ok',True) and preview.get('url'), preview
    folder=OUT/profile;folder.mkdir()
    result=subprocess.run(['node',str(ROOT/'scripts/workspace-tools/check_request.mjs'),preview['url'],
                           str(OUT/'contract.json'),str(folder)],text=True,capture_output=True,timeout=90)
    (folder/'process.txt').write_text(result.stdout+'\n'+result.stderr)
    report=json.loads((folder/'report.json').read_text())
    after=api('/'+key)
    assert before['head']==after['head'] and before['files']==after['files']
    assert before['attempts']==after['attempts'], 'Audit must not create edit attempts'
    summary['results'].append({'profile':profile,'workspace_id':key,'revision':before['head'],
                               'passed':report['passed'],'expected_pass':expected,'preview_url':preview['url'],
                               'report':report})
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2))
    assert report['passed'] is expected,summary['results'][-1]
print(json.dumps(summary,indent=2))
