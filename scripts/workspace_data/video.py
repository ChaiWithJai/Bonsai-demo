"""Add timestamped speech to video evidence without replacing visual records."""
import hashlib
import json
import uuid
from .audio import extract_audio
from .intake import save_manifest


def extract_speech(sources, source_id):
    with sources.lock:
        manifest=sources.manifest(source_id)
        if manifest['kind']!='video':raise ValueError('Choose a video source')
        if manifest.get('audio_coverage'):return sources.get(source_id)
        folder=sources.root/source_id
        raw=(folder/'source.bin').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=manifest['sha256']:raise ValueError('Source hash mismatch')
        evidence=folder/'extractions'/uuid.uuid4().hex;evidence.mkdir(parents=True)
        (evidence/'previous-manifest.json').write_text(json.dumps(manifest,indent=2))
        client=sources.client;exp=client.get_experiment_by_name('bonsai-workspace-data')
        eid=exp.experiment_id if exp else client.create_experiment('bonsai-workspace-data')
        rid=client.create_run(eid,tags={'mlflow.runName':'Video speech transcription','source_id':source_id,
            'source_sha256':manifest['sha256'],'extractor':'faster-whisper-cpu','bonsai_inference':'false'}).info.run_id
        success=False
        try:
            result=extract_audio(raw,evidence)
            records=result['records']
            for i,row in enumerate(records,1):
                row.update(id=f'{source_id}:speech:{i}',source_id=source_id,extraction_id=rid,evidence_status='transcript_unreviewed')
                row['locator']['evidence_channel']='speech'
            manifest.update(records=manifest['records']+records,status='extracted',requires_structuring=True,
                audio_coverage=result['audio_coverage'],speech_extraction_run_id=rid,
                speech_extraction_run_url=f'{sources.tracking_uri}/#/experiments/{eid}/runs/{rid}',
                speech_extractor=result['extractor'],review_status='multimodal_unreviewed')
            manifest.pop('speech_extraction_error',None)
            if not manifest.get('vision_coverage'):
                manifest['visual_extraction_pending']=True
            success=True
        except Exception as exc:
            manifest['speech_extraction_error']=str(exc)
            (evidence/'failure.json').write_text(json.dumps({'error':str(exc)}))
        # A speech failure leaves existing visual records and status intact.
        save_manifest(folder,manifest)
        (evidence/'manifest.json').write_text(json.dumps(manifest,indent=2))
        try:
            client.log_artifacts(rid,str(evidence),'video-speech')
            client.log_artifact(rid,str(folder/'source.bin'),'source')
            client.set_terminated(rid,'FINISHED' if success else 'FAILED')
        except Exception as exc:
            manifest['evidence_error']=str(exc);save_manifest(folder,manifest)
        return sources.get(source_id)
