"""Image OCR with addressable regions. OCR is not visual semantic interpretation."""
import json
from pathlib import Path
import shutil
import tempfile
from workspace_data.pdf import ROOT, command


def extract_image(content, evidence):
    evidence=Path(evidence);evidence.mkdir(parents=True,exist_ok=True)
    binary=ROOT/'.cache/workspace-tools/ocr-image'
    if not binary.exists():
        if not shutil.which('swiftc'):raise ValueError('Image OCR requires Apple Vision and swiftc on this Mac')
        binary.parent.mkdir(parents=True,exist_ok=True)
        command(['swiftc',str(ROOT/'scripts/workspace-tools/ocr_image.swift'),'-o',str(binary)],timeout=120)
    with tempfile.TemporaryDirectory(prefix='bonsai-image-') as temp:
        path=Path(temp)/'source-image';path.write_bytes(content)
        lines=json.loads(command([str(binary),str(path)]))
    (evidence/'ocr-regions.json').write_text(json.dumps(lines,indent=2,ensure_ascii=False))
    records=[]
    for index,line in enumerate(lines,1):
        if not line.get('text','').strip():continue
        box=line.get('bbox_normalized_bottom_left')
        if not isinstance(box,list) or len(box)!=4 or not all(isinstance(n,(float,int)) and 0<=n<=1 for n in box):
            raise ValueError('OCR returned an invalid source region')
        records.append({'locator':{'region':index,'bbox_normalized_bottom_left':box},
                        'data':{'text':line['text'],'ocr_confidence':line['confidence'],'extraction_method':'apple-vision-ocr'}})
    if not records:raise ValueError('No readable text detected. The original image is preserved; visual interpretation is not yet connected.')
    return {'kind':'image','status':'extracted','extractor':'image-regions-v1:apple-vision','requires_structuring':True,
            'records':records,'review_status':'image_text_unreviewed','image_coverage':{'text_regions':len(records),
            'limitation':'OCR text and region locations only. Chart values, diagram relationships, and non-text content are not interpreted. Recognition confidence is not factual confidence.'}}
