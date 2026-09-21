"""Bounded, persisted source-to-project jobs sharing the Workspace model lane."""
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import uuid
from workspace_data.desktop_plan import profile, compile_plan, PLAN_INSTRUCTIONS
from workspace_data.proposal import PROPOSAL_INSTRUCTIONS, source_packet, validate_proposal, revision_messages
from workspace_data.record_review import apply_human_reviews
from workspace_provider import GenerationCancelled, LocalProvider
from workspace_store import RevisionConflict
from workspace_tools import ROOT


class SourceJobs:
    def __init__(self, worker, sources):
        self.worker, self.sources = worker, sources
        provider=worker.provider
        self.planner = LocalProvider(f'http://{provider.host}:{provider.port}',provider.model,timeout=240,max_bytes=provider.max_bytes,profile=provider.profile,seed=provider.seed) if isinstance(provider,LocalProvider) else provider
        self.root = worker.store.root / 'source-jobs'
        self.root.mkdir(exist_ok=True)
        self.active = {}
        # Workspace's process ownership lock has already been acquired.
        for path in self.root.glob('*/status.json'):
            value = json.loads(path.read_text())
            if value['status']=='awaiting_confirmation' and value.get('proposal_contract')!='source-proposal-v2-structured':
                value.update(status='needs_revision',stage='Needs explicit source-backed structure')
                self.save(path.parent,'legacy-proposal-status.json',json.loads(path.read_text()))
                self.save(path.parent,'status.json',value)
            if value['status'] in ('running', 'queued'):
                value.update(status='interrupted', error='Service stopped before this job finished')
                self.save(path.parent, 'status.json', value)

    @staticmethod
    def proposal_examples(proposal, packet):
        cited = {rid for finding in proposal['interpretation']['findings'] for rid in finding['record_ids']}
        for record in (proposal.get('structure') or {}).get('records', []):
            cited.update(item['record_id'] for item in record['evidence'])
        return [{**row, 'id': packet['record_id_map'][row['id']]}
                for row in packet['records'] if packet['record_id_map'][row['id']] in cited]

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
        status = json.loads(path.read_text())
        packet_path = path.parent / 'source-packet.json'
        if status.get('proposal') and packet_path.is_file():
            status['source_examples'] = self.proposal_examples(status['proposal'], json.loads(packet_path.read_text()))
        if status['status'] in ('awaiting_confirmation', 'needs_revision'):
            for child_path in self.root.glob('*/status.json'):
                child = json.loads(child_path.read_text())
                if (child.get('parent_job_id') == jid
                        and child.get('proposal_contract') == 'source-proposal-v2-structured'
                        and child.get('proposal_sha256') and child.get('proposal')):
                    status.update(status='superseded', stage='A revised proposal is available',
                                  superseded_by=child['id'])
                    break
        return status

    def list(self):
        return {'jobs': [self.get(p.parent.name) for p in sorted(self.root.glob('*/status.json'), key=lambda p:p.stat().st_mtime, reverse=True)]}

    def start(self, source_id, request, apply_reviews=False, revision=None):
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
            if revision:
                parent = self.get(revision['parent_job_id'])
                if (parent['status'] not in ('awaiting_confirmation', 'needs_revision')
                        or parent.get('proposal_sha256') != revision.get('parent_proposal_sha256')):
                    raise RevisionConflict('Review the latest proposal before revising it')
            jid = uuid.uuid4().hex
            folder = self.root / jid
            folder.mkdir()
            self.save(folder, 'original-manifest.json', original)
            self.save(folder, 'source-manifest.json', manifest)
            (folder / 'source.bin').write_bytes(raw)
            for member in manifest.get('sources',[]):
                member_folder=folder/'originals'/member['source_id'];member_folder.mkdir(parents=True)
                member_raw=(self.sources.root/member['source_id']/'source.bin').read_bytes()
                if hashlib.sha256(member_raw).hexdigest()!=member['sha256']:
                    raise ValueError('Attached original file integrity mismatch')
                (member_folder/'source.bin').write_bytes(member_raw)
                self.save(member_folder,'provenance.json',member)
            self.save(folder, 'profile.json', context)
            if revision:
                self.save(folder, 'revision-request.json', revision)
            status = {'id':jid, 'source_id':source_id, 'filename':manifest['filename'], 'request':request.strip(),
                      'source_ids':[s['source_id'] for s in manifest.get('sources',[])] or [source_id],
                      'apply_reviews':apply_reviews, 'status':'queued', 'stage':'Preparing source', 'created_at':time.time()}
            if revision:
                status['parent_job_id'] = revision['parent_job_id']
                status['feedback'] = revision['feedback']
                status['parent_proposal_sha256'] = revision.get('parent_proposal_sha256')
                status['parent_planning_run_id'] = revision.get('parent_planning_run_id')
                status['parent_source_snapshot_sha256'] = revision.get('parent_source_snapshot_sha256')
            self.save(folder, 'status.json', status)
            cancel = threading.Event()
            thread = threading.Thread(target=self.run, args=(folder, manifest, context, status, cancel), daemon=True)
            self.active[jid] = (cancel, thread)
            self.worker.source_jobs.add(jid)
            thread.start()
            return status

    def start_vision(self, source_id):
        from workspace_vision_jobs import start_vision
        return start_vision(self,source_id)

    def confirm(self, jid, proposal_sha256, actor='interactive-unattributed'):
        with self.worker.guard:
            status=self.get(jid)
            if status['status'] != 'awaiting_confirmation' or status.get('proposal_contract')!='source-proposal-v2-structured' or status.get('proposal_sha256') != proposal_sha256:
                raise RevisionConflict('Review the current proposal before confirming it')
            if self.worker.running or self.worker.source_jobs:
                raise RevisionConflict('Another Workspace job is running')
            folder=self.root/jid
            self.save(folder,'planning-status.json',status)
            confirmation={'decision':'accept','proposal_sha256':proposal_sha256,'actor':actor,'created_at':time.time(),
                          'identity_basis':'local unauthenticated interaction; not a training label'}
            self.save(folder,'confirmation.json',confirmation)
            status.update(status='queued',stage='Building your confirmed view',planning_run_id=status['run_id'])
            self.save(folder,'status.json',status)
            manifest=json.loads((folder/'source-manifest.json').read_text())
            context=json.loads((folder/'profile.json').read_text())
            cancel=threading.Event()
            thread=threading.Thread(target=self.run,args=(folder,manifest,context,status,cancel,True),daemon=True)
            self.active[jid]=(cancel,thread);self.worker.source_jobs.add(jid);thread.start()
            return status

    def revise(self, jid, feedback, actor='interactive-unattributed'):
        status=self.get(jid)
        if status['status'] not in ('awaiting_confirmation','needs_revision'):
            raise RevisionConflict('Only a pending proposal can be revised')
        if not isinstance(feedback,str) or not 1<=len(feedback.strip())<=4000:
            raise ValueError('Describe what to change in the proposal')
        return self.start(status['source_id'],status['request'],status['apply_reviews'],
                          {'parent_job_id':jid,'feedback':feedback.strip(),'actor':actor,'previous_proposal':status['proposal'],
                           'parent_proposal_sha256':status.get('proposal_sha256'),
                           'parent_planning_run_id':status.get('run_id'),
                           'parent_source_snapshot_sha256':hashlib.sha256((self.root/jid/'source-manifest.json').read_bytes()).hexdigest(),
                           'identity_basis':'local unauthenticated interaction; not a training label'})

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

    def run(self, folder, manifest, context, status, cancel, confirmed=False):
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
            tags = {'mlflow.runName':'Build confirmed visualization' if confirmed else 'Discuss source interpretation', 'source_id':manifest['source_id'],
                    'job_id':status['id'], 'scope':'development', 'model':w.provider.model, 'model_call_timeout_seconds':str(getattr(self.planner,'timeout','test')),
                    'sampling_profile':w.provider.profile, 'sampling_seed':str(w.provider.seed),
                    'prompt_sha256':hashlib.sha256(PROPOSAL_INSTRUCTIONS.encode()).hexdigest(),
                    'initial_ui_origin':'authored scaffold with model-authored typed visualization plan'}
            if status.get('planning_run_id'):
                tags['planning_run_id']=status['planning_run_id']
            if status.get('parent_job_id'):
                tags['parent_job_id']=status['parent_job_id']
                for key in ('parent_proposal_sha256','parent_planning_run_id','parent_source_snapshot_sha256'):
                    if status.get(key):tags[key]=status[key]
            tags['source_snapshot_sha256']=hashlib.sha256((folder/'source-manifest.json').read_bytes()).hexdigest()
            if status.get('parent_source_snapshot_sha256'):
                tags['revision_source_changed']=str(tags['source_snapshot_sha256']!=status['parent_source_snapshot_sha256']).lower()
            run_id = w.client.create_run(eid, tags=tags).info.run_id
            root = w.client.start_trace('workspace.source_to_project', span_type='AGENT', experiment_id=eid,
                                       run_id=run_id, inputs=tags | {'request':status['request']}, attributes={'model_info':w.model_info})
            update(status='running', stage='Planning visualization', run_id=run_id, trace_id=root.trace_id,
                   mlflow_url=f'{w.tracking_uri}/#/experiments/{eid}/runs/{run_id}')
            self.save(folder, 'model-info.json', w.model_info)
            source_files = ['workspace_data/intake.py','workspace_data/xlsx.py','workspace_sources.py','workspace_source_jobs.py','workspace_data/proposal.py','workspace_data/desktop_plan.py','workspace-tools/render_chart.mjs',
                            'workspace_provider.py','workspace-tools/package-lock.json']
            self.save(folder,'harness-hashes.json',{name:hashlib.sha256((ROOT/'scripts'/name).read_bytes()).hexdigest() for name in source_files})
            if not confirmed:
                packet=source_packet(manifest,request=status['request'])
                self.save(folder,'source-packet.json',packet)
                messages = [{'role':'system','content':PROPOSAL_INSTRUCTIONS},
                            {'role':'user','content':json.dumps({'request':status['request'],'source_profile':{k:v for k,v in context.items() if k!='extraction_coverage'},'source_evidence':{k:v for k,v in packet.items() if k!='record_id_map'}},ensure_ascii=False)}]
                if (folder/'revision-request.json').exists():
                    messages += revision_messages(json.loads((folder/'revision-request.json').read_text()), packet['record_id_map'])
                failures = set()
                for turn in range(2):
                    check()
                    preflight = span('context.preflight', {'turn':turn}, lambda:self.planner.preflight(messages, [], 4096))
                    self.save(folder, f'preflight-{turn}.json', preflight)
                    if not preflight['fits']:
                        raise ValueError('Source profile exceeds the model context; choose fewer fields or a smaller source')
                    response = span('model.plan', {'turn':turn,'messages':messages}, lambda:self.planner.generate(messages, [], 'source-'+status['id'], cancel, lambda delta:None, 4096))
                    self.save(folder, f'model-{turn}.json', response)
                    try:
                        proposal = json.loads(response['message']['content'])
                        compiled = span('plan.validate', {'proposal':proposal}, lambda:validate_proposal(manifest, proposal, packet['record_id_map']))
                        for finding in proposal['interpretation']['findings']:
                            finding['record_ids']=[packet['record_id_map'][ref] for ref in finding['record_ids']]
                        if proposal.get('structure'):
                            for row in proposal['structure']['records']:
                                for item in row['evidence']:
                                    item['record_id']=packet['record_id_map'][item['record_id']]
                        plan = proposal['plan']
                        break
                    except (ValueError, TypeError, KeyError) as exc:
                        error = str(exc)
                        self.save(folder, f'validation-{turn}.json', {'error':error})
                        if error in failures or turn == 1:
                            raise ValueError('Plan validation failed within the two-call budget: '+error) from exc
                        failures.add(error)
                        messages += [response['message'], {'role':'user','content':'Correct the complete JSON proposal using this validation error: '+error}]
                        update(stage='Repairing invalid plan once')
                self.save(folder, 'compiled.json', compiled)
                self.save(folder, 'chart.json', compiled['chart'])
                self.save(folder,'proposal.json',proposal)
                digest=hashlib.sha256(json.dumps(proposal,sort_keys=True).encode()).hexdigest()
                update(status='awaiting_confirmation',proposal_contract='source-proposal-v2-structured',stage='Does this interpretation fit your question?',proposal=proposal,
                       proposal_sha256=digest,source_coverage={k:v for k,v in packet.items() if k not in ('records','record_id_map')},
                       source_examples=self.proposal_examples(proposal, packet))
                return
            compiled=json.loads((folder/'compiled.json').read_text())
            if compiled.get('record_origin')=='model_structured_unreviewed':
                compiled['grouping_origin']='model-structured fields, unreviewed; not learned similarity clusters'
                compiled['original_record_count']=len(manifest['records'])
            self.save(folder,'render-compiled.json',compiled)
            plan=compiled['plan']
            confirmation=json.loads((folder/'confirmation.json').read_text())
            span('human.confirmation',confirmation,lambda:confirmation)
            if compiled['chart']['component'] == 'RecordTable':
                update(stage='Preparing source record table')
                evidence = {'renderer': 'authored-accessible-html-table-v1', 'record_count': len(compiled['rows'])}
                chart_svg = ''
                self.save(folder, 'table-evidence.json', evidence)
            else:
                update(stage='Rendering Semiotic component')
                rendered = span('semiotic.render', compiled['chart'], lambda:w.tools.command(
                    [w.tools.node,str(ROOT/'scripts/workspace-tools/render_chart.mjs'),str(folder/'chart.json'),str(folder/'render')],folder/'render',cancel))
                if not rendered['ok']:
                    raise ValueError('Semiotic rendering failed: '+rendered['stderr'][-2000:])
                evidence = json.loads((folder/'render/render-evidence.json').read_text())
                chart_svg = (folder/'render/chart.svg').read_text()
            fixture = {'kind':'desktop','compiled':compiled,'render_evidence':evidence,
                       'chart_svg':chart_svg,'source_job':status.copy()}
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
                    w.client.end_trace(root.trace_id,outputs=status,status='OK' if status['status'] in ('completed','awaiting_confirmation') else 'ERROR')
                if run_id:
                    w.client.log_artifacts(run_id,str(folder),'source-project')
                    w.client.log_metric(run_id,'workflow_passed',int(status['status']=='completed'))
                    w.client.log_metric(run_id,'proposal_ready',int(status['status']=='awaiting_confirmation'))
                    w.client.set_terminated(run_id,'FINISHED' if status['status'] in ('completed','awaiting_confirmation') else 'FAILED')
            except Exception as exc:
                update(evidence_error=str(exc))
            finally:
                with w.guard:
                    self.active.pop(status['id'],None)
                    w.source_jobs.discard(status['id'])
