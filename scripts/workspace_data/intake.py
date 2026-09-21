"""Preserve desktop sources before extraction, classification, or generation.

Intake does not infer domain fields or treat media registration as extraction.
"""
import csv
import hashlib
import io
import json
from pathlib import Path

MAX_BYTES = 25 * 1024 * 1024
MAX_ROWS = 100_000
MEDIA = {'.png': 'image', '.jpg': 'image', '.jpeg': 'image', '.webp': 'image',
         '.pdf': 'document', '.wav': 'audio', '.mp3': 'audio', '.m4a': 'audio',
         '.mp4': 'video', '.mov': 'video', '.webm': 'video'}


def extract(name, content):
    suffix = Path(name).suffix.lower()
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


def ingest(root, name, content):
    if not isinstance(name, str) or not name or len(name) > 255:
        raise ValueError('A source filename is required')
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_BYTES:
        raise ValueError('Source must contain 1 byte to 25 MiB')
    # Name is metadata only. No user-controlled path becomes a storage path.
    name = name.replace('\\', '/').rsplit('/', 1)[-1]
    extraction = extract(name, content)
    digest = hashlib.sha256(content).hexdigest()
    source_id = hashlib.sha256((digest + Path(name).suffix.lower()).encode()).hexdigest()
    folder = Path(root) / source_id
    for i, record in enumerate(extraction['records']):
        record['id'] = f'{source_id}:{i}'
        record['source_id'] = source_id
    manifest = {'schema_version': 1, 'source_id': source_id, 'sha256': digest,
                'filename': name, 'bytes': len(content), 'origin': 'user-provided',
                'extractor': 'desktop-intake-v1', 'classification_status': 'not_started',
                **extraction}
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / 'source.bin'
    if source.exists() and source.read_bytes() != content:
        raise ValueError('Stored source integrity mismatch')
    existing = folder / 'manifest.json'
    if source.exists() and existing.exists():
        # Re-uploading the same bytes must not discard extraction or review lineage.
        return json.loads(existing.read_text())
    source.write_bytes(content)
    (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest
