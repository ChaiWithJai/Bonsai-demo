import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('verify_snapshot',Path(__file__).parents[1]/'scripts/research/verify_official_snapshot.py'); module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class SnapshotVerificationTests(unittest.TestCase):
 def test_publisher_digests_required_files_and_corruption(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); contents={'model.safetensors.index.json':json.dumps({'weight_map':{'weight':'model-00001.safetensors'}}).encode(),'model-00001.safetensors':b'weights','config.json':b'{}','tokenizer.json':b'{}','tokenizer_config.json':b'{}'}; entries=[]
   for name,data in contents.items():
    (root/name).write_bytes(data);lfs=SimpleNamespace(sha256=hashlib.sha256(data).hexdigest()) if name.endswith('.safetensors') else None
    entries.append(SimpleNamespace(rfilename=name,lfs=lfs,blob_id=hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()))
   with patch.object(module,'HfApi') as api:
    api.return_value.model_info.return_value=SimpleNamespace(sha='revision',siblings=entries)
    self.assertTrue(module.verify('publisher/model','revision',root)['passed'])
    (root/'model-00001.safetensors').write_bytes(b'corrupt')
    with self.assertRaisesRegex(ValueError,'Digest mismatch'):module.verify('publisher/model','revision',root)
    (root/'model-00001.safetensors').unlink()
    with self.assertRaisesRegex(ValueError,'Missing required'):module.verify('publisher/model','revision',root)
    api.return_value.model_info.return_value.sha='different'
    with self.assertRaisesRegex(ValueError,'revision mismatch'):module.verify('publisher/model','revision',root)
if __name__=='__main__':unittest.main()
