import argparse,base64,json,xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
parser=argparse.ArgumentParser(description='Build a self-contained explorer from five retained Pelican captures.')
parser.add_argument('--records-root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();ROOT=args.records_root
rows=[]
for suffix,name in [('0101','Bonsai 1'),('0102','Bonsai 2 · original'),('0436','Qwen 3.6 · official BF16'),('0038','Qwen 3.8 · official BF16'),('0202','Bonsai 2 · rerun')]:
 p=ROOT/('b020260918000000000000000000'+suffix)
 r=json.loads((p/'result.json').read_text());a=json.loads((p/'activation-capture.json').read_text());ident=r['identity']
 by={}
 for s in a['samples']:by.setdefault(s['step'],{})[s['layer']]=s
 tokens=[];rms=[]
 for i in sorted(by):
  assert set(by[i])=={0,31,63}
  tokens.append(by[i][0]['input_token_text']);rms.append([round(by[i][l]['stats']['rms'],5) for l in [0,31,63]])
 svg=r['svg'];source=svg.get('source','');shapes={};repair=None
 text=(p/'output.txt').read_text()
 bad='<line x1="110" y2="100" x2="120" y2="100"/>'
 if not svg['valid'] and text.count(bad)==1:
  fixed=text.replace(bad,'<line x1="110" y1="100" x2="120" y2="100"/>')
  fixed=fixed[fixed.index('<svg'):fixed.index('</svg>')+6]
  import sys
  sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
  from svg_output import inspect_svg
  assert inspect_svg(fixed)['valid']
  repair='data:image/svg+xml;base64,'+base64.b64encode(fixed.encode()).decode()
 if svg['valid']:shapes=dict(Counter(e.tag.split('}')[-1] for e in ET.fromstring(source).iter()))
 rows.append(dict(name=name,id=p.name,repo=ident['repo'],revision=ident['revision'],precision=ident.get('weight_format',ident.get('weight_dtype')),tokens=tokens,rms=rms,maxRms=max(max(x) for x in rms),seconds=r['seconds'],count=r['recorded_vectors'],svg=('data:image/svg+xml;base64,'+base64.b64encode(source.encode()).decode()) if svg['valid'] else None,repair=repair,error=svg.get('error',''),shapes=shapes,output=text))
out=args.output;out.parent.mkdir(parents=True,exist_ok=True)
payload=json.dumps(rows,separators=(',',':')).replace('<','\\u003c')
out.write_text(Path(__file__).with_name('explorer.html').read_text().replace('__PELICAN_DATA__',payload));assert out.stat().st_size<1_000_000
print(out, out.stat().st_size)
