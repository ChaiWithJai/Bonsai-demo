import importlib.util,json,pathlib,struct,tempfile,unittest
P=pathlib.Path(__file__).resolve().parents[1]/'scripts/research/summarize_pelican.py'
spec=importlib.util.spec_from_file_location('pelican_report',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ReportTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=pathlib.Path(self.t.name);self.out=self.root/'report'
 def fixture(self):
  for suffix,label,repo,rev in m.MODELS:
   p=self.root/(m.PREFIX+suffix);p.mkdir();req={'messages':m.PROMPT,**m.EXPECTED,'enable_thinking':False};(p/'request.json').write_text(json.dumps(req));h=m.sha((p/'request.json').read_bytes())
   ident={'repo':repo,'revision':rev,'source_request_sha256':h,'sampler_order':['temperature','top_k','top_p','min_p','categorical_draw']}
   ident.update({'quantized':False,'weight_dtype':'bfloat16'} if repo.startswith('Qwen/') else {'sha256':'e4781999f1997ef97ce0c58d05750835acc999d18d83ee6489ba7ac7b14cb5f6' if suffix=='0101' else '3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1'})
   text='<svg xmlns="http://www.w3.org/2000/svg"><circle r="2"/></svg>';(p/'output.txt').write_text(text)
   samples=[]
   for layer in (0,31,63):
    raw=struct.pack('<5120f',*([1.,2.]*2560));f=f'{layer}.f32';(p/f).write_bytes(raw);samples.append({'step':0,'layer':layer,'vector_file':f,'vector_length':5120,'vector_sha256':m.sha(raw),'sample':[1.,2.]})
   cap={'kind':'live_instrumented_inference','passed':True,'source':{'research_id':p.name,'request_sha256':h},'model':ident,'samples':samples,'generated_text':text}
   result={'identity':ident,'source_request_sha256':h,'svg':{'valid':True,'source':text},'seconds':1.25,'generated_tokens':2,'recorded_vectors':3}
   research={'status':'completed','model_identity':ident,'response':{'choices':[{'message':{'content':text}}]}}
   for name,d in [('identity.json',ident),('activation-capture.json',cap),('result.json',result),('research.json',research)]: (p/name).write_text(json.dumps(d))
 def test_pending_writes_nothing(self):
  with self.assertRaisesRegex(FileNotFoundError,'Pending'):m.summarize(self.root,self.out)
  self.assertFalse(self.out.exists())
 def test_valid_four_and_isolated_images(self):
  self.fixture();d=m.summarize(self.root,self.out);self.assertEqual(len(d['runs']),4)
  html=(self.out/'comparison.html').read_text();self.assertEqual(html.count('src="data:image/svg+xml;base64,'),4);self.assertNotIn('<svg',html);self.assertNotIn('<script',html)
 def test_tampered_vector_rejected(self):
  self.fixture();(self.root/(m.PREFIX+'0101')/'0.f32').write_bytes(struct.pack('<2f',3,4))
  with self.assertRaisesRegex(ValueError,'hash mismatch'):m.summarize(self.root,self.out)
 def test_wrong_revision_rejected(self):
  self.fixture();p=self.root/(m.PREFIX+'0101')/'identity.json';d=json.loads(p.read_text());d['revision']='bad';p.write_text(json.dumps(d))
  with self.assertRaisesRegex(ValueError,'checkpoint mismatch'):m.summarize(self.root,self.out)
 def test_numeric_mismatch_rejected(self):
  self.fixture();p=self.root/(m.PREFIX+'0101')/'request.json';d=json.loads(p.read_text());d['temperature']=1;p.write_text(json.dumps(d))
  with self.assertRaisesRegex(ValueError,'numeric setting mismatch'):m.summarize(self.root,self.out)
 def test_wrong_dtype_even_with_matching_repo_revision(self):
  self.fixture();p=self.root/(m.PREFIX+'0436')/'identity.json';d=json.loads(p.read_text());d['weight_dtype']='float16';p.write_text(json.dumps(d))
  with self.assertRaisesRegex(ValueError,'dtype/quantization'):m.summarize(self.root,self.out)
 def test_missing_layer_rejected(self):
  self.fixture();p=self.root/(m.PREFIX+'0101')/'activation-capture.json';d=json.loads(p.read_text());d['samples'].pop();p.write_text(json.dumps(d))
  with self.assertRaisesRegex(ValueError,'Unexpected layers'):m.summarize(self.root,self.out)
 def test_output_mismatch_rejected(self):
  self.fixture();p=self.root/(m.PREFIX+'0101')/'activation-capture.json';d=json.loads(p.read_text());d['generated_text']='wrong';p.write_text(json.dumps(d))
  with self.assertRaisesRegex(ValueError,'Capture output mismatch'):m.summarize(self.root,self.out)
 def test_full_identity_mismatch_rejected(self):
  self.fixture();p=self.root/(m.PREFIX+'0101')/'activation-capture.json';d=json.loads(p.read_text());d['model']['unexpected']='different';p.write_text(json.dumps(d))
  with self.assertRaisesRegex(ValueError,'full identity mismatch'):m.summarize(self.root,self.out)
 def test_invalid_svg_is_retained_evaluation_outcome(self):
  self.fixture();p=self.root/(m.PREFIX+'0102');text='<svg xmlns="http://www.w3.org/2000/svg" width="1" width="2"><script>bad()</script></svg>'
  (p/'output.txt').write_text(text)
  for name in ('result.json','activation-capture.json','research.json'):
   f=p/name;d=json.loads(f.read_text())
   if name=='result.json':d['svg']=m.inspect_svg(text)
   elif name=='activation-capture.json':d['generated_text']=text
   else:d['response']['choices'][0]['message']['content']=text
   f.write_text(json.dumps(d))
  d=m.summarize(self.root,self.out);self.assertTrue(d['evidence_audit_passed']);self.assertFalse(d['output_validation_passed']);self.assertFalse(d['runs'][1]['output_validation_passed'])
  html=(self.out/'comparison.html').read_text();self.assertEqual(html.count('src="data:image/svg+xml;base64,'),3);self.assertIn('&lt;script&gt;',html);self.assertNotIn('<script>',html);self.assertIn('duplicate attribute',html)
if __name__=='__main__':unittest.main()
