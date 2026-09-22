"""Own one pinned local Bonsai server under the existing shared GPU queue."""
from contextlib import contextmanager
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import time
from urllib.request import urlopen
import hashlib
import socket
import signal

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=str) + '\n')


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def stop_owned(process):
    if process is None or process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)





def context_capacity(config):
    """Require an explicit bounded context; zero must never request the full model window."""
    value = config.get('context', 16384)
    if type(value) is not int or not 4096 <= value <= 262144:
        raise ValueError('Workspace context must be an integer from 4096 to 262144 tokens; omit it for 16384')
    return value


def server_command(config, runtime, model, port):
    return [str(runtime), '-m', str(model), '--host', '127.0.0.1', '--port', str(port),
            '-ngl', '99', '-c', str(context_capacity(config)), '-np', '1', '--jinja',
            '--reasoning-budget', '0', '--alias', config['alias']]


@contextmanager
def model_server(config, output):
    context = context_capacity(config)
    output = Path(output)
    model = Path(config['model'])
    runtime = Path(config['runtime_directory'])/'llama-server'
    if sha(model) != config['model_sha256'] or sha(runtime) != config['runtime_sha256']:
        raise ValueError('Pinned model or runtime hash mismatch')
    identity = {key:config[key] for key in ('model_sha256','runtime_sha256','model_revision','model_label')}
    identity.update(runtime_libraries={p.name:sha(p) for p in runtime.parent.glob('*.dylib') if not p.is_symlink()},
                    platform=platform.platform(), hardware=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string','hw.memsize'],text=True).strip(),
                    context=context, gpu_layers=99)
    save(output/'identity.json',identity)
    if config.get('mmproj'):
        projector=Path(config['mmproj'])
        if sha(projector)!=config.get('mmproj_sha256'):raise ValueError('Vision projector hash mismatch')
        identity.update(mmproj=str(projector),mmproj_sha256=config['mmproj_sha256'],image_max_tokens=1024)
        save(output/'identity.json',identity)
    spec=importlib.util.spec_from_file_location('desktop_shared_queue',config['queue'])
    queue=importlib.util.module_from_spec(spec);spec.loader.exec_module(queue)
    job_id='desktop-ui-'+output.name
    with (queue.ROOT/'worker.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        queue.put(job_id,'mac',{'kind':'generative-ui-owned-run','output':str(output),'runner_sha256':sha(__file__),'model_sha256':identity['model_sha256']})
        for i in range(3):
            available,reason=queue.probe('mac')
            save(output/f'quiet-check-{i+1}.json',{'available':available,'reason':reason,'at':time.time()})
            print(f'Quiet check {i+1}/3: {reason}',flush=True)
            if not available:
                queue.update(job_id,'queued',reason)
                raise RuntimeError('Shared GPU lane unavailable; no model launched')
            if i<2:time.sleep(30)
        if not queue.claim('mac',job_id):raise RuntimeError('Shared queue claim refused')
        process=None
        completed=False
        try:
            if sha(runtime)!=identity['runtime_sha256']:raise ValueError('Runtime changed before launch')
            for name,digest in identity['runtime_libraries'].items():
                if sha(runtime.parent/name)!=digest:raise ValueError('Runtime library changed before launch')
            port=free_port()
            command=server_command(config, runtime, model, port)
            if config.get('mmproj'):
                if sha(config['mmproj'])!=identity['mmproj_sha256']:raise ValueError('Vision projector changed before launch')
                command+=['--mmproj',config['mmproj'],'--image-max-tokens','1024']
            save(output/'server-command.json',command)
            with (output/'server.log').open('w') as log:
                process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                save(output/'process.json',{'runner_pid':os.getpid(),'server_pid':process.pid,'job_id':job_id})
                endpoint=f'http://127.0.0.1:{port}'
                for _ in range(240):
                    if process.poll() is not None:raise RuntimeError('Owned model server exited')
                    try:
                        with urlopen(endpoint+'/health',timeout=1) as response:
                            if json.load(response).get('status')=='ok':break
                    except OSError:pass
                    time.sleep(1)
                else:raise TimeoutError('Owned model server did not become ready')
                yield endpoint,identity
                completed=True
        finally:
            try:
                stop_owned(process)
                queue.update(job_id,'completed' if completed else 'failed','Owned server stopped; evidence in '+str(output))
            except BaseException:
                queue.update(job_id,'needs_review','Owned server cleanup could not be confirmed')
                raise
