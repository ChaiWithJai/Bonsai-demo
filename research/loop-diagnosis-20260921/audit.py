import pathlib,json,hashlib,sqlite3,shutil
root=pathlib.Path(__file__).resolve().parents[2];out=pathlib.Path(__file__).resolve().parent;base=root/'.cache/workspace-live-v3-20260921/workspace';aid='b05d3920ff2a4cde8d91c2559200b58e'
c=sqlite3.connect(base/'workspace.sqlite3');events=[{'sequence':s,'kind':k,'payload':json.loads(p)} for s,k,p in c.execute('select sequence,kind,payload from events where attempt_id=? and kind!=?',(aid,'model.delta'))]
(out/'events.json').write_text(json.dumps(events,indent=2));rows=[]
for f in sorted((base/'attempts'/aid).glob('model-*.json')):
 d=json.loads(f.read_text());d=d.get('evidence',d);chunks=[];reason=[];content=[]
 for line in d.get('raw_response','').splitlines():
  if not line.startswith('data: '):continue
  try:j=json.loads(line[6:])
  except ValueError:continue
  for ch in j.get('choices',[]):
   delta=ch.get('delta',{});reason.append(delta.get('reasoning_content') or '');content.append(delta.get('content') or '')
   for tc in delta.get('tool_calls',[]):chunks.append(tc.get('function',{}).get('arguments') or '')
 row={'file':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'reasoning_chars':len(''.join(reason)),'content_chars':len(''.join(content)),'tool_argument_chars':len(''.join(chunks)),'request_settings':{k:v for k,v in d.get('request',{}).items() if k not in ('messages','tools')},'old_text_sha256':[]}
 for tc in d.get('message',{}).get('tool_calls',[]):
  try: args=json.loads(tc['function']['arguments'])
  except ValueError:continue
  for edit in args.get('edits',[]):row['old_text_sha256'].append(hashlib.sha256(edit['old_text'].encode()).hexdigest())
 rows.append(row)
(out/'generation-audit.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
for src,name in [('/tmp/bonsai2-loop-paper.txt','paper.txt'),('/Users/jaibhagat/.browseros/tool-output/read-1790008022781-494b292a-3a1d-4b2d-9b6b-68ba279bd833.md','pinned-card.md'),('/Users/jaibhagat/.browseros/tool-output/read-1790008022765-5581add0-a23a-4f6f-a063-e6eb4a4a12f4.md','community-report.md')]:shutil.copyfile(src,out/name)
shutil.copyfile(base/'attempts'/aid/'summary.json',out/'attempt-summary.json')
