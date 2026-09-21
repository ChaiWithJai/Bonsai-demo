"""Page-bound PDF extraction with Poppler text and explicit Apple Vision fallback."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def command(argv, timeout=60):
    result = subprocess.run(argv, capture_output=True, timeout=timeout)
    if result.returncode:
        raise ValueError(f'{Path(argv[0]).name} failed: '+result.stderr.decode(errors='replace')[-1500:])
    return result.stdout


def extract_pdf(content, evidence):
    evidence = Path(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    for name in ('pdfinfo','pdftotext','pdftoppm'):
        if not shutil.which(name):
            raise ValueError(f'PDF extraction requires {name}; original file is preserved')
    with tempfile.TemporaryDirectory(prefix='bonsai-pdf-') as temp:
        original = Path(temp)/'source.pdf'
        original.write_bytes(content)
        info = command(['pdfinfo',str(original)]).decode(errors='replace')
        (evidence/'pdfinfo.txt').write_text(info)
        match = re.search(r'^Pages:\s+(\d+)',info,re.M)
        if not match:
            raise ValueError('PDF page count could not be verified')
        count = int(match.group(1))
        if not 1 <= count <= 250:
            raise ValueError(f'This PDF has {count} pages; current per-upload limit is 250 pages')
        raw = command(['pdftotext','-layout','-enc','UTF-8',str(original),'-']).decode('utf-8')
        (evidence/'embedded-text.txt').write_text(raw)
        pages = raw.split('\f')
        if pages and not pages[-1].strip():
            pages.pop()
        if len(pages) != count:
            raise ValueError(f'PDF page coverage mismatch: {len(pages)} text pages for {count} PDF pages')
        records, coverage = [], []
        for number, text in enumerate(pages,1):
            method='poppler-embedded-text';ocr_lines=[];error=None
            text=text.strip()
            if not text:
                method='apple-vision-ocr'
                try:
                    prefix=Path(temp)/f'page-{number}'
                    command(['pdftoppm','-f',str(number),'-l',str(number),'-singlefile','-scale-to','2000','-png',str(original),str(prefix)])
                    binary=ROOT/'.cache/workspace-tools/ocr-image'
                    if not binary.exists():
                        if not shutil.which('swiftc'):
                            raise ValueError('OCR requires Apple Vision and swiftc on this Mac')
                        binary.parent.mkdir(parents=True,exist_ok=True)
                        command(['swiftc',str(ROOT/'scripts/workspace-tools/ocr_image.swift'),'-o',str(binary)],timeout=120)
                    ocr_lines=json.loads(command([str(binary),str(prefix)+'.png']))
                    text='\n'.join(line['text'] for line in ocr_lines).strip()
                    (evidence/f'ocr-page-{number}.json').write_text(json.dumps(ocr_lines,indent=2))
                except (ValueError,subprocess.TimeoutExpired,OSError) as exc:
                    error=str(exc)
            coverage.append({'page':number,'method':method,'characters':len(text),'status':'extracted' if text else 'needs_review','error':error})
            # Keep every page addressable, including a blank or unreadable page.
            records.append({'locator':{'page':number},'data':{'page':number,'title':next((line.strip() for line in text.splitlines() if line.strip()),'Page '+str(number)),
                            'text':text,'extraction_method':method,'extraction_status':'extracted' if text else 'needs_review'}})
        report={'page_count':count,'pages_with_text':sum(bool(r['data']['text']) for r in records),
                'ocr_pages':[p['page'] for p in coverage if p['method']=='apple-vision-ocr'],
                'unresolved_pages':[p['page'] for p in coverage if p['status']=='needs_review'],
                'pages':coverage,'limitation':'Embedded text is extracted on text-bearing pages. OCR is used only when embedded text is absent. Diagrams, charts and tables are not semantically interpreted; page text is unreviewed.'}
        (evidence/'coverage.json').write_text(json.dumps(report,indent=2))
        if not report['pages_with_text']:
            raise ValueError('No readable text was extracted from any page; inspect the saved coverage report')
        return {'kind':'document','status':'extracted','extractor':'pdf-pages-v1:poppler+apple-vision',
                'records':records,'extraction_coverage':report,'review_status':'page_text_unreviewed'}
