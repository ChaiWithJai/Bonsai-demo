"""Resolve immutable source-job evidence for a curated interface export."""
import hashlib
import json
from pathlib import Path
import re


def source_evidence(root, fixture):
    job = fixture.get('source_job')
    if not job:
        return []
    jid = job.get('id')
    if not isinstance(jid, str) or not re.fullmatch(r'[a-f0-9]{32}', jid):
        raise ValueError('Invalid source job reference')
    folder = Path(root) / 'source-jobs' / jid
    manifest = json.loads((folder / 'original-manifest.json').read_text())
    files = []

    def verified_raw(path, sha, artifact):
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError('Original source integrity mismatch during review export')
        files.append((path, artifact))

    prefix = 'source-jobs/' + jid
    verified_raw(folder / 'source.bin', manifest['sha256'], prefix)
    for name in ('original-manifest.json', 'source-manifest.json', 'proposal.json',
                 'compiled.json', 'source-packet.json', 'confirmation.json',
                 'model-info.json', 'harness-hashes.json', 'planning-status.json'):
        path = folder / name
        if not path.is_file():
            raise ValueError('Source job evidence is incomplete: ' + name)
        files.append((path, prefix))
    for member in manifest.get('sources', []):
        sid = member['source_id']
        if not re.fullmatch(r'[a-f0-9]{64}', sid):
            raise ValueError('Invalid collection source reference')
        member_folder = folder / 'originals' / sid
        verified_raw(member_folder / 'source.bin', member['sha256'], prefix + '/originals/' + sid)
        files.append((member_folder / 'provenance.json', prefix + '/originals/' + sid))
    return files
