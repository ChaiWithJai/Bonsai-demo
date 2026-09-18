"""No servers: validate official status and persisted capture binding."""
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from comparison_api import ComparisonAPI
from observability_api import Observability
class BindingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
  self.folder=self.base/('a'*32);self.turn=self.folder/'qwen/turn-1';self.turn.mkdir(parents=True)
  self.rid='b'*32;self.research=self.base/'research'/self.rid;self.research.mkdir(parents=True)
  self.identity={'repo':'Qwen/Qwen3.8-27B','revision':'1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0','weight_dtype':'bfloat16','quantized':False}
  self.request={'messages':[{'role':'user','content':'hello'}]}
  self.write(self.turn/'request.json',self.request);self.write(self.research/'request.json',self.request)
  self.capture={'kind':'live_instrumented_inference','passed':True,'model':self.identity,'generated_text':'answer','source':{'research_id':self.rid,'request_sha256':hashlib.sha256((self.research/'request.json').read_bytes()).hexdigest()}}
  self.record={'status':'completed','model_identity':self.identity,'response':{'choices':[{'message':{'content':'answer'}}]}}
  self.result={'content':'answer','activation_capture':{'research_id':self.rid},'identity':{'identity':{'checkpoint_provenance':self.identity}}}
  self.api=Observability.__new__(Observability);self.api.research_directory=self.research.parent;self.api.manifest=None
 def write(self,p,d):p.write_text(json.dumps(d))
 def bind(self):
  self.write(self.research/'activation-capture.json',self.capture);self.write(self.research/'research.json',self.record);self.write(self.turn/'result.json',self.result)
  nodes=[{'kind':'completion','turn':1,'activations':{'status':'not_captured'}}];self.api.attach_comparison_replay(self.folder,'qwen',nodes,[]);return nodes[0]
 def test_matching_capture_attaches(self):self.assertEqual(self.bind()['activations']['status'],'captured')
 def test_different_request_rejected(self):
  self.write(self.turn/'request.json',{'messages':[]});self.assertNotIn('activation_capture',self.bind())
 def test_different_output_rejected(self):
  self.result['content']='different';self.assertNotIn('activation_capture',self.bind())
 def test_different_checkpoint_rejected(self):
  self.result['identity']['identity']['checkpoint_provenance']=dict(self.identity,revision='wrong');self.assertNotIn('activation_capture',self.bind())
 def test_different_capture_identity_rejected(self):
  self.capture['model']=dict(self.identity,weight_dtype='float16');self.assertNotIn('activation_capture',self.bind())
 def test_capture_text_must_match_actual_output(self):
  self.capture['generated_text']='invented';self.assertNotIn('activation_capture',self.bind())
 def test_consistently_quantized_capture_cannot_attach_to_bf16(self):
  self.record['model_identity']=dict(self.identity,quantized=True);self.capture['model']=self.record['model_identity'];self.assertNotIn('activation_capture',self.bind())
 def test_missing_request_rejected_without_exception(self):
  (self.research/'request.json').unlink();self.assertNotIn('activation_capture',self.bind())
 def test_status_rejects_quantized_official_repo(self):
  api=ComparisonAPI.__new__(ComparisonAPI);api.endpoints={'qwen':'http://unused'}
  for quantized,expected in [(True,False),(False,True)]:
   props={'checkpoint_provenance':dict(self.identity,verified=True,quantized=quantized)}
   api._get=lambda endpoint,path:{'/health':{'status':'ok'},'/v1/models':{'data':[{'id':'Qwen/Qwen3.8-27B'}]},'/props':props}[path]
   self.assertEqual(api._identity('qwen')['available'],expected)
if __name__=='__main__':unittest.main()
