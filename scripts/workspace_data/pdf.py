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
            embedded=text
            ocr_trigger='empty_embedded_text' if not text else 'sparse_embedded_text' if len(re.sub(r'\s+', '', text)) < 120 else None
            if ocr_trigger:
                method='poppler+apple-vision-ocr' if embedded else 'apple-vision-ocr'
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
                    existing={' '.join(line.split()) for line in embedded.splitlines()}
                    additional=[line['text'] for line in ocr_lines if ' '.join(line['text'].split()) not in existing]
                    text='\n'.join(([embedded] if embedded else [])+additional).strip()
                    (evidence/f'ocr-page-{number}.json').write_text(json.dumps(ocr_lines,indent=2))
                except (ValueError,subprocess.TimeoutExpired,OSError) as exc:
                    error=str(exc)
            page_status='extracted' if text and not error else 'needs_review'
            coverage.append({'page':number,'method':method,'characters':len(text),'embedded_characters':len(embedded),'ocr_trigger':ocr_trigger,'status':page_status,'error':error})
            # Keep every page addressable, including a blank or unreadable page.
            records.append({'locator':{'page':number},'data':{'page':number,'title':next((line.strip() for line in text.splitlines() if line.strip()),'Page '+str(number)),
                            'text':text,'extraction_method':method,'extraction_status':page_status}})
        report={'page_count':count,'pages_with_text':sum(bool(r['data']['text']) for r in records),
                'ocr_pages':[p['page'] for p in coverage if p['ocr_trigger'] is not None],
                'unresolved_pages':[p['page'] for p in coverage if p['status']=='needs_review'],
                'pages':coverage,'limitation':'Embedded text is extracted on text-bearing pages. OCR supplements pages with fewer than 120 non-whitespace embedded characters, including header-only scans. Existing text is preserved; denser mixed text/image pages may still contain unread image content. Diagrams, charts and tables are not semantically interpreted; page text is unreviewed.'}
        (evidence/'coverage.json').write_text(json.dumps(report,indent=2))
        if not report['pages_with_text']:
            raise ValueError('No readable text was extracted from any page; inspect the saved coverage report')
        return {'kind':'document','status':'extracted','extractor':'pdf-pages-v2:poppler+apple-vision',
                'records':records,'extraction_coverage':report,'review_status':'page_text_unreviewed'}
