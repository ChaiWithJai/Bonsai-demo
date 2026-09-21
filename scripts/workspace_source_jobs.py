"""Bounded, persisted source-to-project jobs sharing the Workspace model lane."""
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import uuid
from workspace_data.desktop_plan import profile, compile_plan, PLAN_INSTRUCTIONS
from workspace_data.record_review import apply_human_reviews
from workspace_provider import GenerationCancelled
from workspace_store import RevisionConflict
from workspace_tools import ROOT


class SourceJobs:
    def __init__(self, worker, sources):
        self.worker, self.sources = worker, sources
        self.root = worker.store.root / 'source-jobs'
        self.root.mkdir(exist_ok=True)
        self.active = {}
        # Workspace's process ownership lock has already been acquired.
        for path in self.root.glob('*/status.json'):
            value = json.loads(path.read_text())
            if value['status'] in ('running', 'queued'):
                value.update(status='interrupted', error='Service stopped before this job finished')
                self.save(path.parent, 'status.json', value)

    @staticmethod
    def save(folder, name, value):
        path = folder / name
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False))
        temp.replace(path)

    def get(self, jid):
        if not isinstance(jid, str) or not re.fullmatch('[a-f0-9]{32}', jid):
            raise ValueError('Invalid source job')
        path = self.root / jid / 'status.json'
        if not path.exists():
            raise ValueError('Source job not found')
        return json.loads(path.read_text())

    def list(self):
        return {'jobs': [json.loads(p.read_text()) for p in sorted(self.root.glob('*/status.json'), key=lambda p:p.stat().st_mtime, reverse=True)]}

    def start(self, source_id, request, apply_reviews=False):
        if not isinstance(request, str) or not 10 <= len(request.strip()) <= 4000:
            raise ValueError('Describe the visualization in 10 to 4,000 characters')
        if type(apply_reviews) is not bool:
            raise ValueError('apply_reviews must be a boolean')
        with self.sources.lock:
            manifest = self.sources.manifest(source_id)
            original = json.loads(json.dumps(manifest))
            raw = (self.sources.root / source_id / 'source.bin').read_bytes()
            if hashlib.sha256(raw).hexdigest() != manifest['sha256']:
                raise ValueError('Source bytes no longer match their recorded hash')
            if apply_reviews:
                manifest = apply_human_reviews(self.sources.root, manifest)
            context = profile(manifest)
        with self.worker.guard:
            if self.worker.running or self.worker.source_jobs:
                raise RevisionConflict('Another Workspace job is using the local model')
            jid = uuid.uuid4().hex
            folder = self.root / jid
            folder.mkdir()
            self.save(folder, 'original-manifest.json', original)
            self.save(folder, 'source-manifest.json', manifest)
            (folder / 'source.bin').write_bytes(raw)
            self.save(folder, 'profile.json', context)
            status = {'id':jid, 'source_id':source_id, 'filename':manifest['filename'], 'request':request.strip(),
                      'apply_reviews':apply_reviews, 'status':'queued', 'stage':'Preparing source', 'created_at':time.time()}
            self.save(folder, 'status.json', status)
            cancel = threading.Event()
            thread = threading.Thread(target=self.run, args=(folder, manifest, context, status, cancel), daemon=True)
            self.active[jid] = (cancel, thread)
            self.worker.source_jobs.add(jid)
            thread.start()
            return status

    def cancel(self, jid):
        with self.worker.guard:
            if jid not in self.active:
                raise RevisionConflict('Source job is no longer running')
            self.active[jid][0].set()
        return {'cancel_requested':True}

    def close(self):
        with self.worker.guard:
            active = list(self.active.values())
            for cancel, _ in active:
                cancel.set()
        for _, thread in active:
            thread.join(timeout=15)

    def run(self, folder, manifest, context, status, cancel):
        w = self.worker
        root = run_id = None
        started = time.monotonic()
        def update(**values):
            status.update(values)
            self.save(folder, 'status.json', status)
        def check():
            if cancel.is_set():
                raise GenerationCancelled('Source job cancelled')
        def span(name, inputs, operation):
            check()
            child = w.client.start_span(name, trace_id=root.trace_id, parent_id=root.span_id, inputs=inputs)
            try:
                result = operation()
                w.client.end_span(root.trace_id, child.span_id, outputs=result, status='OK')
                return result
            except Exception as exc:
                w.client.end_span(root.trace_id, child.span_id, outputs={'error':str(exc)}, status='ERROR')
                raise
        try:
            experiment = w.client.get_experiment_by_name('bonsai-workspace-data')
            eid = experiment.experiment_id if experiment else w.client.create_experiment('bonsai-workspace-data')
            tags = {'mlflow.runName':'Source to editable visualization', 'source_id':manifest['source_id'],
                    'job_id':status['id'], 'scope':'development', 'model':w.provider.model,
                    'sampling_profile':w.provider.profile, 'sampling_seed':str(w.provider.seed),
                    'prompt_sha256':hashlib.sha256(PLAN_INSTRUCTIONS.encode()).hexdigest(),
                    'initial_ui_origin':'authored scaffold with model-authored typed visualization plan'}
            run_id = w.client.create_run(eid, tags=tags).info.run_id
            root = w.client.start_trace('workspace.source_to_project', span_type='AGENT', experiment_id=eid,
                                       run_id=run_id, inputs=tags | {'request':status['request']}, attributes={'model_info':w.model_info})
            update(status='running', stage='Planning visualization', run_id=run_id, trace_id=root.trace_id,
                   mlflow_url=f'{w.tracking_uri}/#/experiments/{eid}/runs/{run_id}')
            self.save(folder, 'model-info.json', w.model_info)
            source_files = ['workspace_source_jobs.py','workspace_data/desktop_plan.py','workspace-tools/render_chart.mjs',
                            'workspace_provider.py','workspace-tools/package-lock.json']
            self.save(folder,'harness-hashes.json',{name:hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest() for name in source_files})
            messages = [{'role':'system','content':PLAN_INSTRUCTIONS},
                        {'role':'user','content':json.dumps({'request':status['request'],'source_profile':context},ensure_ascii=False)}]
            failures = set()
            for turn in range(2):
                check()
                preflight = span('context.preflight', {'turn':turn}, lambda:w.provider.preflight(messages, [], 3000))
                self.save(folder, f'preflight-{turn}.json', preflight)
                if not preflight['fits']:
                    raise ValueError('Source profile exceeds the model context; choose fewer fields or a smaller source')
                response = span('model.plan', {'turn':turn,'messages':messages}, lambda:w.provider.generate(messages, [], 'source-'+status['id'], cancel, lambda delta:None, 3000))
                self.save(folder, f'model-{turn}.json', response)
                try:
                    plan = json.loads(response['message']['content'])
                    compiled = span('plan.validate', {'plan':plan}, lambda:compile_plan(manifest, plan))
                    break
                except (ValueError, TypeError, KeyError) as exc:
                    error = str(exc)
                    self.save(folder, f'validation-{turn}.json', {'error':error})
                    if error in failures or turn == 1:
                        raise ValueError('Plan validation failed within the two-call budget: '+error) from exc
                    failures.add(error)
                    messages += [response['message'], {'role':'user','content':'Correct only the JSON plan using this validation error: '+error}]
                    update(stage='Repairing invalid plan once')
            self.save(folder, 'compiled.json', compiled)
            self.save(folder, 'chart.json', compiled['chart'])
            update(stage='Rendering Semiotic component')
            rendered = span('semiotic.render', compiled['chart'], lambda:w.tools.command(
                [w.tools.node,str(ROOT/'scripts/workspace-tools/render_chart.mjs'),str(folder/'chart.json'),str(folder/'render')],folder/'render',cancel))
            if not rendered['ok']:
                raise ValueError('Semiotic rendering failed: '+rendered['stderr'][-2000:])
            evidence = json.loads((folder/'render/render-evidence.json').read_text())
            fixture = {'kind':'desktop','compiled':compiled,'render_evidence':evidence,
                       'chart_svg':(folder/'render/chart.svg').read_text(),'source_job':status.copy()}
            check()
            project = w.store.create(title=plan['title'][:150], files={'App.svelte':(ROOT/'examples/workspace/desktop/App.svelte').read_text()}, fixture=fixture)
            update(workspace_id=project['id'], stage='Building editable project')
            build = span('project.build', {'revision':project['head']},lambda:w.tools.build(project,folder/'build',cancel))
            if not build['ok']:
                raise ValueError('Project build failed: '+build['stderr'][-2000:])
            preview = w.tools.preview(project,build)
            w.latest[project['id']] = preview
            update(stage='Checking data and interactions')
            checked = span('project.browser_check',preview,lambda:w.tools.check_browser(project,preview,folder/'check',cancel))
            if not checked['ok']:
                raise ValueError('Project browser checks failed: '+json.dumps(checked.get('report')))
            check()
            update(status='completed',stage='Ready to explore and edit',preview=preview,revision=project['head'])
        except Exception as exc:
            self.save(folder,'failure.json',{'error':str(exc),'provider_evidence':getattr(exc,'evidence',None)})
            update(status='cancelled' if cancel.is_set() else 'failed',stage='Stopped',error=str(exc))
        finally:
            update(elapsed_seconds=round(time.monotonic()-started,3))
            try:
                if root:
                    w.client.end_trace(root.trace_id,outputs=status,status='OK' if status['status']=='completed' else 'ERROR')
                if run_id:
                    w.client.log_artifacts(run_id,str(folder),'source-project')
                    w.client.log_metric(run_id,'workflow_passed',int(status['status']=='completed'))
                    w.client.set_terminated(run_id,'FINISHED' if status['status']=='completed' else 'FAILED')
            except Exception as exc:
                update(evidence_error=str(exc))
            finally:
                with w.guard:
                    self.active.pop(status['id'],None)
                    w.source_jobs.discard(status['id'])
