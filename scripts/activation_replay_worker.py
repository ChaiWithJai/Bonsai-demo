"""Durable serialized background replay queue; inference responses never wait for capture."""
import hashlib, json, os, signal, queue, subprocess, sys, threading, time
from pathlib import Path

class ReplayWorker:
    def __init__(self, records_dir, upstream, tracking_uri, release_manifest=None, diagnostic_dir=None,
                 capture_binary=None, runtime_lib_dir=None, activity_ports=None, mlflow_base_url='http://127.0.0.1:5210'):
        self.records_dir=Path(records_dir); self.upstream=upstream; self.tracking_uri=tracking_uri
        self.release_manifest=Path(release_manifest) if release_manifest else None
        self.diagnostic_dir=Path(diagnostic_dir) if diagnostic_dir else None
        self.capture_binary=Path(capture_binary) if capture_binary else None
        self.runtime_lib_dir=Path(runtime_lib_dir) if runtime_lib_dir else None
        self.activity_ports=list(activity_ports or [])
        self.mlflow_base_url=mlflow_base_url
        self.jobs=queue.Queue(); self.pending=set(); self.lock=threading.Lock()
        threading.Thread(target=self._run,daemon=True,name='activation-replay').start()
        for root in (self.records_dir,self.records_dir.parent/'comparison-records'):
            for path in root.glob('**/activation-replay-status.json'):
                try:
                    state=json.loads(path.read_text())
                    if state.get('status') in ('queued','running') and state.get('job'):self._enqueue(path.parent,state['source'],state['job'])
                except (ValueError,OSError):pass

    def _write(self,path,state):
        state['updated_at']=time.time(); tmp=path/'activation-replay-status.tmp'
        tmp.write_text(json.dumps(state,indent=2));tmp.replace(path/'activation-replay-status.json')

    def enqueue(self,path):
        path=Path(path);exchange=json.loads((path/'exchange.json').read_text())
        if exchange.get('kind')!='completion' or not exchange.get('complete') or exchange.get('status',500)>=400:return
        source={k:exchange.get(k) for k in ('request_id','session','trace_id')}
        source['request_sha256']=hashlib.sha256((path/'request.bin').read_bytes()).hexdigest()
        self._enqueue(path,source,{'kind':'native','upstream':self.upstream})

    def enqueue_comparison(self,path,model,source):
        self._enqueue(Path(path),source,{'kind':'comparison','model':model,'upstream':self.upstream})

    def _enqueue(self,path,source,job):
        with self.lock:
            if str(path) in self.pending:return
            if (path/'activation-replay.json').exists():
                self._write(path,{**source,'source':source,'job':job,'status':'completed'})
                return
            self.pending.add(str(path))
        self._write(path,{**source,'source':source,'job':job,'status':'queued'})
        self.jobs.put((path,source,job))

    def _run(self):
        while True:
            path,source,job=self.jobs.get()
            try:
                self._write(path,{**source,'source':source,'job':job,'status':'running'})
                command=[sys.executable,str(Path(__file__).with_name('capture_activations_replay.py')),'--native-record' if job['kind']=='native' else '--comparison-turn',str(path),'--upstream',job['upstream'],'--tracking-uri',self.tracking_uri]
                if self.release_manifest:command+=['--release-manifest',str(self.release_manifest)]
                if self.diagnostic_dir:command+=['--diagnostic-dir',str(self.diagnostic_dir)]
                if self.capture_binary:command+=['--capture-binary',str(self.capture_binary)]
                if self.runtime_lib_dir:command+=['--runtime-lib-dir',str(self.runtime_lib_dir)]
                if self.mlflow_base_url:command+=['--mlflow-base-url',self.mlflow_base_url]
                for port in self.activity_ports:command+=['--activity-port',str(port)]
                with (path/'activation-replay-worker.log').open('w') as log:
                    result=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    try:result.wait(timeout=1200)
                    except subprocess.TimeoutExpired:
                        os.killpg(result.pid,signal.SIGKILL);result.wait();raise
                if result.returncode:raise RuntimeError((path/'activation-replay-worker.log').read_text()[-1600:])
                if not (path/'activation-replay.json').exists():raise RuntimeError('Capture produced no replay manifest')
                self._write(path,{**source,'source':source,'job':job,'status':'completed'})
            except Exception as exc:self._write(path,{**source,'source':source,'job':job,'status':'error','error':str(exc)})
            finally:
                with self.lock:self.pending.discard(str(path))
                self.jobs.task_done()
