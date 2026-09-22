"""Persisted native vision extraction sharing the Workspace model reservation."""
import base64
import hashlib
import json
from pathlib import Path
import threading
import time
import uuid
from workspace_data.vision import image_units,validate_ocr,OCR_PROMPT,PDF_PAGE_PROMPT,PDF_PAGE_SCHEMA
from workspace_provider import GenerationCancelled,LocalProvider
from workspace_store import RevisionConflict


def start_vision(jobs,source_id,page=None):
    w=jobs.worker
    if not w.model_info.get('checkpoint_release',{}).get('runtime',{}).get('mmproj_sha256'):
        raise ValueError('This runtime has no verified vision projector')
    with jobs.sources.lock:
        manifest=jobs.sources.manifest(source_id)
        is_pdf=Path(manifest['filename']).suffix.lower()=='.pdf'
        if is_pdf:
            if type(page) is not int or not 1 <= page <= 250:
                raise ValueError('Select one PDF page between 1 and 250')
        elif manifest['kind'] not in ('image','video') or page is not None:
            raise ValueError('Choose an image, video, or a selected PDF page')
        raw=(jobs.sources.root/source_id/'source.bin').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=manifest['sha256']:raise ValueError('Original source checksum mismatch')
    with w.guard:
        if w.running or w.source_jobs:raise RevisionConflict('Another Workspace job is using the model')
        jid=uuid.uuid4().hex;folder=jobs.root/jid;folder.mkdir()
        jobs.save(folder,'original-manifest.json',manifest);(folder/'source.bin').write_bytes(raw)
        status={'id':jid,'source_id':source_id,'filename':manifest['filename'],'request':'Read visible source content with Bonsai vision',
                'page':page,'kind':'vision_extraction','status':'queued','stage':'Preparing visual evidence','created_at':time.time()}
        jobs.save(folder,'status.json',status);cancel=threading.Event()
        thread=threading.Thread(target=run_vision,args=(jobs,folder,manifest,status,cancel),daemon=True)
        jobs.active[jid]=(cancel,thread);w.source_jobs.add(jid);thread.start();return status


def run_vision(jobs,folder,manifest,status,cancel):
    w=jobs.worker;run_id=None;started=time.monotonic()
    def update(**values):status.update(values);jobs.save(folder,'status.json',status)
    def check():
        if cancel.is_set():raise GenerationCancelled('Vision extraction cancelled')
        if time.monotonic()-started>600:raise ValueError('Vision job exceeded its ten-minute budget')
    try:
        exp=w.client.get_experiment_by_name('bonsai-workspace-data');eid=exp.experiment_id if exp else w.client.create_experiment('bonsai-workspace-data')
        run_id=w.client.create_run(eid,tags={'mlflow.runName':'Bonsai visual source extraction','source_id':manifest['source_id'],'review_status':'unreviewed'}).info.run_id
        update(status='running',run_id=run_id,mlflow_url=f'{w.tracking_uri}/#/experiments/{eid}/runs/{run_id}')
        jobs.save(folder,'model-info.json',w.model_info)
        is_pdf=Path(manifest['filename']).suffix.lower()=='.pdf'
        units=image_units(manifest,folder/'source.bin',folder,page=status['page']) if is_pdf else image_units(manifest,folder/'source.bin',folder)
        planner=jobs.planner
        if is_pdf and isinstance(planner,LocalProvider):
            planner=LocalProvider(f'http://{planner.host}:{planner.port}',planner.model,timeout=planner.timeout,max_bytes=planner.max_bytes,profile=planner.profile,seed=planner.seed,response_schema=PDF_PAGE_SCHEMA)
        if is_pdf:jobs.save(folder,'response-schema.json',PDF_PAGE_SCHEMA)
        jobs.save(folder,'generation-config.json',{'profile':jobs.planner.profile,'seed':jobs.planner.seed,'max_tokens':4096,'selected_pdf_page':status.get('page')})
        jobs.save(folder,'harness-hashes.json',{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ['workspace_vision_jobs.py','workspace_data/vision.py']})
        jobs.save(folder,'units.json',[{**u,'sha256':hashlib.sha256(Path(u['path']).read_bytes()).hexdigest()} for u in units])
        records=[]
        for index,unit in enumerate(units):
            check();update(stage=f'Reading visual sample {index+1} of {len(units)}')
            content=base64.b64encode(Path(unit['path']).read_bytes()).decode()
            messages=[{'role':'user','content':[{'type':'text','text':PDF_PAGE_PROMPT if is_pdf else OCR_PROMPT},{'type':'image_url','image_url':{'url':f'data:{unit["mime"]};base64,{content}'}}]}]
            jobs.save(folder,f'request-{index}.json',messages)
            response=planner.generate(messages,[],'workspace-vision-'+status['id'],cancel,lambda delta:None,4096)
            jobs.save(folder,f'response-{index}.json',response)
            rows=validate_ocr(json.loads(response['message']['content']),manifest['source_id'],unit['locator'],run_id)
            records.extend(rows);jobs.save(folder,f'records-{index}.json',rows)
        check()
        if not records:raise ValueError('No legible visual records found; prior extraction preserved')
        for row in records:row['locator']['evidence_channel']='visual'
        speech=[row for row in manifest['records'] if row.get('locator',{}).get('evidence_channel')=='speech']
        if is_pdf:
            speech=[row for row in manifest['records'] if not (row.get('locator',{}).get('evidence_channel')=='visual' and row.get('locator',{}).get('page')==status['page'])]
        updated={**manifest,'records':speech+records,'status':'extracted','extractor':'Bonsai 2 27B vision','requires_structuring':True,
                 'review_status':'model_extracted_unreviewed','extraction_run_id':run_id,'extraction_run_url':status['mlflow_url'],
                 'vision_coverage':{'samples':len(units),'records':len(records),'limitation':'Visual content is model-extracted and unreviewed. '+('Up to 20 frames distributed across the video, including beginning, middle and near the end for clips of at least half a second. This visual pass does not read speech or unsampled motion; speech coverage is reported separately.' if manifest['kind']=='video' else 'Visible text/table extraction is not verified semantic understanding.')}}
        if is_pdf:
            pages=sorted({row['locator']['page'] for row in updated['records'] if row.get('locator',{}).get('evidence_channel')=='visual'})
            updated['extractor']=manifest.get('extractor','PDF extraction') if manifest.get('pdf_visual_runs') else manifest.get('extractor','PDF extraction')+' + Bonsai page observations'
            updated['pdf_visual_runs']={**manifest.get('pdf_visual_runs',{}),str(status['page']):{'run_id':run_id,'url':status['mlflow_url']}}
            updated['vision_coverage']={'samples':len(pages),'records':sum(row.get('locator',{}).get('evidence_channel')=='visual' for row in updated['records']),
                'pages':pages,'limitation':'Only PDF pages '+', '.join(map(str,pages))+' have model visual observations. Original text and OCR are retained separately. All model observations are unreviewed; diagrams on other pages have not been visually read.'}
        updated.pop('visual_extraction_pending',None);updated.pop('image_coverage',None);updated.pop('extraction_error',None)
        with jobs.sources.lock:
            current=jobs.sources.manifest(manifest['source_id'])
            if current!=manifest:raise RevisionConflict('Source changed during extraction; saved results were not applied')
            archive=jobs.sources.root/manifest['source_id']/'extractions'/status['id'];archive.mkdir(parents=True)
            jobs.save(archive,'previous-manifest.json',manifest);jobs.save(archive,'manifest.json',updated)
            jobs.save(jobs.sources.root/manifest['source_id'],'manifest.json',updated)
        update(status='completed',stage='Visual records ready for review',record_count=len(records))
    except Exception as exc:
        jobs.save(folder,'failure.json',{'error':str(exc),'provider_evidence':getattr(exc,'evidence',None)})
        update(status='cancelled' if cancel.is_set() else 'failed',stage='Visual extraction stopped',error=str(exc))
    finally:
        update(elapsed_seconds=round(time.monotonic()-started,3))
        try:
            if run_id:
                w.client.log_artifacts(run_id,str(folder),'vision-extraction');w.client.set_terminated(run_id,'FINISHED' if status['status']=='completed' else 'FAILED')
        except Exception as exc:update(evidence_error=str(exc))
        finally:
            with w.guard:jobs.active.pop(status['id'],None);w.source_jobs.discard(status['id'])
