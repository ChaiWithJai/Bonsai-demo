#!/usr/bin/env python3
"""Verify an existing pinned HF snapshot against publisher Git/LFS digests.
Fetches metadata only; never downloads model weights.
"""
import argparse,hashlib,json
from pathlib import Path
from huggingface_hub import HfApi

def verify(repo,revision,snapshot):
 info=HfApi().model_info(repo,revision=revision,files_metadata=True)
 if info.sha!=revision:raise ValueError('Publisher revision mismatch')
 index=json.loads((snapshot/'model.safetensors.index.json').read_text())
 required=set(index['weight_map'].values())|{'config.json','model.safetensors.index.json','tokenizer.json','tokenizer_config.json'}
 files=[]
 for entry in info.siblings:
  p=snapshot/entry.rfilename
  if not p.exists():
   if entry.rfilename in required:raise ValueError('Missing required file '+entry.rfilename)
   continue
  if entry.lfs:
   expected=entry.lfs.sha256; h=hashlib.sha256()
  else:
   expected=entry.blob_id;h=hashlib.sha1();h.update(f'blob {p.stat().st_size}\0'.encode())
  with p.open('rb') as f:
   for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
  if h.hexdigest()!=expected:raise ValueError('Digest mismatch '+entry.rfilename)
  files.append({'name':entry.rfilename,'digest':expected,'algorithm':'sha256' if entry.lfs else 'git-blob-sha1','bytes':p.stat().st_size})
  print('Verified',entry.rfilename,flush=True)
 if not required <= {f['name'] for f in files}:raise ValueError('Required files absent from publisher metadata')
 return {'repo':repo,'revision':revision,'path':str(snapshot),'files':files,'passed':True}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--revision',required=True);p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 result=verify(a.repo,a.revision,a.snapshot);a.output.write_text(json.dumps(result,indent=2))
