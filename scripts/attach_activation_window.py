"""Attach checked teacher-forced artifacts to their original trace without replacing it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import math
import struct


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def attach(folder):
    folder = Path(folder).resolve()
    provenance = json.loads((folder/'provenance.json').read_text())
    record = Path(provenance['source_record'])
    for name in ('request','response'):
        if digest(record/(name+'.bin')) != provenance['source_'+name+'_sha256']:
            raise ValueError('Recorded source changed')
    capture = json.loads((folder/'capture.json').read_text())
    if capture.get('teacher_forced') is not True or capture.get('passed') is not True:
        raise ValueError('Expected successful teacher-forced capture')
    if len(capture['samples']) != len(capture['tokens'])*3 or not 1 <= len(capture['tokens']) <= 64:
        raise ValueError('Invalid capture shape')
    for sample in capture['samples']:
        path=folder/sample['vector_file']
        if path.parent!=folder or path.stat().st_size!=5120*4:
            raise ValueError('Invalid vector path or size')
        values=struct.unpack('<5120f',path.read_bytes())
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Nonfinite vector')
    target = record/'activation-window-artifacts'
    if target.exists():
        raise ValueError('Window already attached; use a new record or version')
    shutil.copytree(folder,target)
    exchange=json.loads((record/'exchange.json').read_text())
    run=json.loads((folder/'mlflow.json').read_text())
    identity=json.loads((folder.parent/'identity.json').read_text())
    rendered=(target/'rendered-prompt.txt').read_text()
    source={'native_request_id':record.name,'request_id':record.name,'session':exchange['session'],
            'request_sha256':provenance['source_request_sha256'],'response_sha256':provenance['source_response_sha256'],
            'rendered_prompt_sha256':hashlib.sha256(rendered.encode()).hexdigest()}
    for sample in capture['samples']:
        path=target/sample['vector_file'];sample.update(vector_file=str(path),vector_sha256=digest(path))
    capture.update(kind='new_teacher_forced_reconstructed_window',source=source,rendered_prompt=rendered,
                   settings=json.loads((target/'config.json').read_text()),replay=run,mlflow=run,
                   model={'sha256':identity['model_sha256']},runtime=identity,
                   provenance=provenance,interpretation=provenance['scope'])
    (record/'activation-window-preflight.json').write_text(json.dumps({'rendered_prompt':rendered}))
    (record/'activation-window.json').write_text(json.dumps(capture,indent=2))
    return str(record/'activation-window.json')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('folder');args=parser.parse_args()
    print(attach(args.folder))
