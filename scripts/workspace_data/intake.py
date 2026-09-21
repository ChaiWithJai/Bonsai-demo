"""Preserve desktop sources before extraction, classification, or generation.

Intake does not infer domain fields or treat media registration as extraction.
"""
import csv
import hashlib
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

MAX_BYTES = 25 * 1024 * 1024
MAX_ROWS = 100_000
MEDIA = {'.png': 'image', '.jpg': 'image', '.jpeg': 'image', '.webp': 'image',
         '.pdf': 'document', '.wav': 'audio', '.mp3': 'audio', '.m4a': 'audio',
         '.mp4': 'video', '.mov': 'video', '.webm': 'video'}

FILE_KINDS = {'.docx': 'document', '.xlsx': 'workbook', '.eml': 'email', '.mbox': 'email', '.csv': 'table', '.tsv': 'table', '.json': 'table', '.jsonl': 'table', '.txt': 'text', '.md': 'text'}

def extract(name, content):
    suffix = Path(name).suffix.lower()
    if suffix == '.xlsx':
        from workspace_data.xlsx import extract_xlsx
        return extract_xlsx(content, MAX_ROWS)
    if suffix == '.docx':
        from workspace_data.docx import extract_docx
        return extract_docx(content, MAX_ROWS)
    if suffix in {'.eml','.mbox'}:
        from workspace_data.email_intake import extract_email
        return extract_email(name,content,MAX_ROWS)
    if suffix in MEDIA:
        return {'kind': MEDIA[suffix], 'status': 'needs_extractor', 'records': []}
    if suffix not in {'.csv', '.tsv', '.json', '.jsonl', '.txt', '.md'}:
        raise ValueError('Unsupported source format')
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('Text sources must use UTF-8') from exc
    records = []
    if suffix in {'.csv', '.tsv'}:
        reader = csv.DictReader(io.StringIO(text, newline=''), delimiter='\t' if suffix == '.tsv' else ',')
        headers = reader.fieldnames
        if not headers or any(not h for h in headers) or len(set(headers)) != len(headers):
            raise ValueError('Table headers must be nonempty and unique')
        for ordinal, row in enumerate(reader, 1):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f'Table record {ordinal} has a different width from its header')
            records.append({'locator': {'record': ordinal, 'ending_line': reader.line_num}, 'data': row})
            if len(records) > MAX_ROWS:
                raise ValueError('Source exceeds the intake row limit')
    elif suffix in {'.json', '.jsonl'}:
        def reject_constant(value):
            raise ValueError(f'Non-finite JSON value: {value}')
        if suffix == '.json':
            data = json.loads(text, parse_constant=reject_constant)
            if not isinstance(data, list):
                raise ValueError('JSON source must contain an array of objects')
            values = [(value, {'json_pointer': f'/{i}'}) for i, value in enumerate(data)]
        else:
            values = [(json.loads(line, parse_constant=reject_constant), {'line': i})
                      for i, line in enumerate(text.splitlines(), 1) if line.strip()]
        for value, locator in values:
            if not isinstance(value, dict):
                raise ValueError('Each JSON record must be an object')
            records.append({'locator': locator, 'data': value})
    else:
        records = [{'locator': {'line': i}, 'data': {'text': line}}
                   for i, line in enumerate(text.splitlines(), 1) if line.strip()]
    if not records or len(records) > MAX_ROWS:
        raise ValueError(f'Provide between 1 and {MAX_ROWS} records')
    return {'kind': 'text' if suffix in {'.txt', '.md'} else 'table',
            'status': 'extracted', 'records': records}


def save_manifest(folder, manifest):
    temp = folder / 'manifest.tmp'
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    temp.replace(folder / 'manifest.json')


def extract_saved(root, manifest):
    """Retry a failed supported file without replacing its original or prior attempts."""
    folder = Path(root) / manifest['source_id']
    raw = (folder / 'source.bin').read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['sha256']:
        raise ValueError('Stored source integrity mismatch')
    if manifest['status'] == 'extracted':
        return manifest
    if Path(manifest['filename']).suffix.lower() not in FILE_KINDS:
        raise ValueError('Use the media extraction workflow for this file')
    attempt = uuid.uuid4().hex
    evidence = folder / 'extractions' / attempt
    evidence.mkdir(parents=True)
    (evidence / 'previous-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    result = {**manifest, 'records': [], 'extraction_attempt_id': attempt,
              'extraction_attempted_at': datetime.now(timezone.utc).isoformat()}
    for key in ('extraction_error', 'extraction_run_id', 'extraction_run_url', 'evidence_error'):
        result.pop(key, None)
    try:
        extraction = extract(manifest['filename'], raw)
        for i, record in enumerate(extraction['records']):
            record.update(id=f"{manifest['source_id']}:{i}", source_id=manifest['source_id'])
        result.update(extraction)
    except Exception as exc:
        result.update(status='extraction_failed', extraction_error=str(exc), extraction_error_type=type(exc).__name__)
    else:
        result.pop('extraction_error_type', None)
    (evidence / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    save_manifest(folder, result)
    return result


def ingest(root, name, content):
    if not isinstance(name, str) or not name or len(name) > 255:
        raise ValueError('A source filename is required')
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_BYTES:
        raise ValueError('Source must contain 1 byte to 25 MiB')
    name = name.replace('\\', '/').rsplit('/', 1)[-1]
    suffix = Path(name).suffix.lower()
    if suffix not in FILE_KINDS and suffix not in MEDIA:
        raise ValueError('Unsupported source format')
    digest = hashlib.sha256(content).hexdigest()
    source_id = hashlib.sha256((digest + suffix).encode()).hexdigest()
    folder = Path(root) / source_id
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / 'source.bin'
    if source.exists() and source.read_bytes() != content:
        raise ValueError('Stored source integrity mismatch')
    existing = folder / 'manifest.json'
    if source.exists() and existing.exists():
        return json.loads(existing.read_text())
    source.write_bytes(content)
    manifest = {'schema_version': 1, 'source_id': source_id, 'sha256': digest,
                'filename': name, 'bytes': len(content), 'origin': 'user-provided',
                'extractor': 'desktop-intake-v1', 'classification_status': 'not_started',
                'kind': FILE_KINDS.get(suffix, MEDIA.get(suffix)), 'status': 'needs_extractor', 'records': []}
    save_manifest(folder, manifest)
    return extract_saved(root, manifest) if suffix in FILE_KINDS else manifest
