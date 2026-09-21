"""Run the native Workspace with one owned, pinned model under the shared queue.
Adapted from the frozen bonsai-generative-ui prototype's runtime ownership path.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from urllib.request import urlopen
from workspace_runtime import model_server

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--config',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--proxy-command',type=Path,required=True)
args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
config=json.loads(args.config.read_text());command=json.loads(args.proxy_command.read_text())
def stop(*unused):raise KeyboardInterrupt()
signal.signal(signal.SIGTERM,stop)
reload_requested=False
def reload_proxy(*unused):
    global reload_requested
    reload_requested=True
signal.signal(signal.SIGUSR1,reload_proxy)
with model_server(config,args.output) as (endpoint,identity):
    files=[{'path':config['model'],'sha256':config['model_sha256'],'verified':True}]
    if config.get('mmproj'):files.append({'path':config['mmproj'],'sha256':config['mmproj_sha256'],'verified':True})
    manifest={'checkpoint':{'repo':'prism-ml/Ternary-Bonsai-2-27B-gguf','revision':config['model_revision'],'files':files},'runtime':identity}
    release=args.output/'release-manifest.json';release.write_text(json.dumps(manifest,indent=2))
    command[command.index('--upstream')+1]=endpoint
    command[command.index('--release-manifest')+1]=str(release.resolve())
    (args.output/'proxy-command.json').write_text(json.dumps(command,indent=2))
    with (args.output/'proxy.log').open('w') as log:
        proxy=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        try:
            print('MODEL READY '+endpoint+'; native Workspace PID '+str(proxy.pid),flush=True)
            while proxy.poll() is None:
                time.sleep(1)
                if reload_requested:
                    reload_requested=False
                    port=command[command.index('--port')+1]
                    with urlopen(f'http://127.0.0.1:{port}/api/workspace',timeout=5) as response:state=json.load(response)
                    if state['running_attempts'] or state['running_source_jobs']:
                        print('Proxy reload deferred: Workspace job active',flush=True);continue
                    proxy.terminate();proxy.wait(timeout=20)
                    proxy=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
                    print('Reloaded idle Workspace proxy; model retained',flush=True)
            raise RuntimeError('Workspace proxy stopped: '+str(proxy.returncode))
        finally:
            if proxy.poll() is None:
                proxy.terminate()
                try:proxy.wait(timeout=15)
                except subprocess.TimeoutExpired:proxy.kill();proxy.wait()
