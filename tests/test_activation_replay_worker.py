import hashlib, importlib.util, json, queue, tempfile, threading, unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('replay_worker',Path(__file__).parents[1]/'scripts/activation_replay_worker.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ReplayQueueTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)
  self.worker=m.ReplayWorker.__new__(m.ReplayWorker);self.worker.jobs=queue.Queue();self.worker.pending=set();self.worker.lock=threading.Lock();self.worker.upstream='http://localhost:8081'
  (self.path/'request.bin').write_bytes(b'{"messages":[]}')
  (self.path/'exchange.json').write_text(json.dumps({'request_id':'x','session':'chat','kind':'completion','complete':True,'status':200}))
 def test_native_dedup_and_hash(self):
  self.worker.enqueue(self.path);self.worker.enqueue(self.path)
  self.assertEqual(self.worker.jobs.qsize(),1)
  status=json.loads((self.path/'activation-replay-status.json').read_text())
  self.assertEqual(status['source']['request_sha256'],hashlib.sha256((self.path/'request.bin').read_bytes()).hexdigest())
  self.assertEqual(status['status'],'queued')
 def test_failed_exchange_not_queued(self):
  (self.path/'exchange.json').write_text(json.dumps({'kind':'completion','complete':False,'status':200}))
  self.worker.enqueue(self.path);self.assertTrue(self.worker.jobs.empty())
 def test_completed_capture_returns_durable_status(self):
  (self.path/'activation-replay.json').write_text('{}');self.worker.enqueue(self.path)
  self.assertTrue(self.worker.jobs.empty());self.assertEqual(json.loads((self.path/'activation-replay-status.json').read_text())['status'],'completed')
 def test_comparison_preserves_identity(self):
  source={'comparison_run_id':'x','model':'qwen','turn':5,'request_sha256':'sha'}
  self.worker.enqueue_comparison(self.path,'qwen',source)
  status=json.loads((self.path/'activation-replay-status.json').read_text());self.assertEqual(status['source'],source)

if __name__=='__main__':unittest.main()
