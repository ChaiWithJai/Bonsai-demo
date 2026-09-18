#!/usr/bin/env python3
"""Bounded capability smoke checks; NOT reproduction of whitepaper benchmarks.
Run with the MLflow environment and --execute only when inference is scheduled.
"""
import argparse, ast, base64, hashlib, io, json, re, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = dict(temperature=0, seed=42, top_p=0.95, top_k=20, max_tokens=512,
                thinking_budget_tokens=0, stream=False, cache_prompt=False)
CASES = [
 ('math', 'A community lab buys 17 routers at 24 dollars each and pays 35 dollars shipping. What is the total cost in dollars? Reply with the integer only.', '443'),
 ('instruction', 'Reply with exactly these three lowercase words, separated by a single comma and no spaces or punctuation beyond those two commas: cedar maple pine', 'cedar,maple,pine'),
 ('code', 'Write only a Python function named square with one argument x that returns x * x. No imports, markdown, explanation, or other statements.', None),
]
TOOL = {'type':'function','function':{'name':'get_fictional_grant','description':'Look up a fictional grant for this test. No external systems.','parameters':{'type':'object','properties':{'grant_id':{'type':'string','enum':['DEMO-7']}},'required':['grant_id'],'additionalProperties':False}}}

def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False))

def text_of(response):
    return response['choices'][0]['message'].get('content') or ''

def code_check(text):
    try:
        tree=ast.parse(text.strip())
        if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef): return False
        f=tree.body[0]
        if f.name!='square' or [a.arg for a in f.args.args]!=['x'] or f.decorator_list or len(f.body)!=1:return False
        node=f.body[0]
        return isinstance(node,ast.Return) and isinstance(node.value,ast.BinOp) and isinstance(node.value.op,ast.Mult) and all(isinstance(v,ast.Name) and v.id=='x' for v in [node.value.left,node.value.right])
    except (SyntaxError,ValueError):return False

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute',action='store_true')
    ap.add_argument('--url',default='http://127.0.0.1:8081')
    ap.add_argument('--tracking-uri',default='http://127.0.0.1:5210')
    ap.add_argument('--output',type=Path,default=ROOT/'docs/research-20260918/smoke')
    ap.add_argument('--skip-vision',action='store_true')
    args=ap.parse_args()
    if not args.execute:
        print(json.dumps({'mode':'plan_only','max_http_generation_requests':6,'cases':['math','instruction','code','tool_call','tool_result','vision'],'settings':SETTINGS,'scope':'bounded capability smoke; not benchmark reproduction'},indent=2));return
    import mlflow
    run_dir=args.output/time.strftime('%Y%m%d-%H%M%S');run_dir.mkdir(parents=True,exist_ok=False)
    session=requests.Session()
    models=session.get(args.url+'/v1/models',timeout=20);models.raise_for_status(); models=models.json()
    props=session.get(args.url+'/props',timeout=20);props.raise_for_status();props=props.json()
    manifest=json.loads((ROOT/'.cache/bonsai/release-manifest.json').read_text())
    identity={'manifest':manifest,'runtime_models':models,'runtime_props':props,'scope':'Manifest checkpoint hashes are recorded provenance; this script does not independently hash the loaded process weights.'}
    dump(run_dir/'identity.json',identity)
    model=models['data'][0]['id']; results=[]
    mlflow.set_tracking_uri(args.tracking_uri); mlflow.set_experiment('Bonsai whitepaper bounded capability smoke')
    with mlflow.start_run(run_name='Bonsai2 bounded capability checks') as run:
        mlflow.set_tags({'evaluation_scope':'bounded_smoke_not_paper_reproduction','checkpoint_repo':manifest['checkpoint']['repo'],'checkpoint_revision':manifest['checkpoint']['revision']})
        mlflow.log_params(SETTINGS)
        dump(run_dir/'mlflow.json',{'run_id':run.info.run_id,'experiment_id':run.info.experiment_id})
        def ask(name,messages,**extra):
            request={'model':model,'messages':messages,**SETTINGS,**extra}
            dump(run_dir/(name+'-request.json'),request)
            start=time.time()
            response=session.post(args.url+'/v1/chat/completions',json=request,timeout=(20,180))
            (run_dir/(name+'-response.txt')).write_text(response.text)
            response.raise_for_status(); data=response.json();dump(run_dir/(name+'-response.json'),data)
            return data, time.time()-start
        def record(name,passed,elapsed,detail=''):
            results.append({'case':name,'passed':bool(passed),'elapsed_seconds':elapsed,'detail':detail})
            dump(run_dir/'summary.json',{'scope':'bounded smoke, not full paper benchmark','results':results})
            mlflow.log_metric(name+'_passed',int(passed));mlflow.log_metric(name+'_seconds',elapsed)
        try:
            for name,prompt,answer in CASES:
                data,elapsed=ask(name,[{'role':'user','content':prompt}]);text=text_of(data).strip()
                passed=code_check(text) if name=='code' else text==answer
                record(name,passed,elapsed,'AST inspected only; generated code was not executed.' if name=='code' else 'Exact string match.')
            messages=[{'role':'user','content':'Use get_fictional_grant to look up DEMO-7. After receiving its result, reply with only the grant deadline date.'}]
            data,elapsed=ask('tool_call',messages,tools=[TOOL],tool_choice='required')
            message=data['choices'][0]['message'];calls=message.get('tool_calls') or []
            valid=len(calls)==1 and calls[0].get('function',{}).get('name')=='get_fictional_grant'
            if valid:
                try:valid=json.loads(calls[0]['function']['arguments'])=={'grant_id':'DEMO-7'}
                except (ValueError,TypeError):valid=False
            record('tool_call',valid,elapsed,'Native tool call arguments checked against fictional deterministic fixture.')
            if valid:
                fixture={'grant_id':'DEMO-7','deadline':'2026-12-15','fictional':True}
                dump(run_dir/'tool-fixture.json',fixture)
                messages.extend([message,{'role':'tool','tool_call_id':calls[0]['id'],'content':json.dumps(fixture)}])
                data,elapsed=ask('tool_result',messages,tools=[TOOL],tool_choice='none')
                record('tool_result',text_of(data).strip()=='2026-12-15',elapsed,'Exact fixture deadline; no external tool execution.')
            else:results.append({'case':'tool_result','status':'skipped','reason':'Native tool call did not match fixture schema.'})
            if args.skip_vision:
                results.append({'case':'vision','status':'skipped','reason':'Explicit --skip-vision.'})
            else:
                try:
                    from PIL import Image,ImageDraw
                    im=Image.new('RGB',(240,160),'white');ImageDraw.Draw(im).rectangle((40,40,200,120),fill='red');buf=io.BytesIO();im.save(buf,format='PNG');image=buf.getvalue();(run_dir/'vision-input.png').write_bytes(image)
                    image_content=[{'type':'text','text':'What color is the rectangle? Reply with one lowercase word only.'},{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(image).decode()}}]
                    data,elapsed=ask('vision',[{'role':'user','content':image_content}]);record('vision',text_of(data).strip()=='red',elapsed,'Generated local image; exact color label.')
                except ImportError:
                    results.append({'case':'vision','status':'skipped','reason':'Pillow is unavailable in the selected environment.'})
        except Exception as error:
            results.append({'status':'error','error':repr(error)})
            raise
        finally:
            dump(run_dir/'summary.json',{'scope':'bounded smoke, not full paper benchmark','results':results,'model_identity_file':'identity.json','run_id':run.info.run_id})
            mlflow.log_artifacts(str(run_dir),artifact_path='evidence')
    print(run_dir)

if __name__=='__main__':main()
