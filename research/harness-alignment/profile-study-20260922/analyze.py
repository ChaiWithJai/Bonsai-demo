"""Inspect frozen values and paired inputs. Does not judge prose or rename fields."""
import argparse
from collections import Counter
import json
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--results',type=Path,required=True)
parser.add_argument('--workspace',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
protocol=json.loads((args.results/'protocol.json').read_text())
results=json.loads((args.results/'results.json').read_text())
def read(folder,name):
    p=folder/name
    return json.loads(p.read_text()) if p.is_file() else None
def value_key(value):
    if type(value) in (int,float):return ('number',value)
    return (type(value).__name__,json.dumps(value,sort_keys=True))
def key(row,fields):return tuple(value_key(row[f]) for f in fields)
reports=[]
for result in results:
    case=next(c for c in protocol['cases'] if c['id']==result['case'])
    folder=args.workspace/'source-jobs'/result['job_id'];compiled=read(folder,'compiled.json')
    proposal=read(folder,'proposal.json');models=[p for p in folder.glob('model-*.json') if p.stem[6:].isdigit()]
    report={**result,'model_calls':len(models),'compiled':compiled is not None,'data_checks':None,
            'assessment_limits':'No automatic judgment of interpretation, chart usefulness, or human acceptance.'}
    if compiled:
        mapping=case.get('semantic_field_mapping') or {k:k for k in case['expected_records'][0]}
        fields=list(mapping);rows=[r['data'] for r in compiled['rows']]
        missing=sorted({v for row in rows for v in mapping.values() if v not in row})
        actual=[{k:row[v] for k,v in mapping.items()} for row in rows] if not missing else None
        values_match=Counter(key(r,fields) for r in actual)==Counter(key(r,fields) for r in case['expected_records']) if actual is not None else None
        report['data_checks']={'source_hash':compiled['source_sha256']==case['sha256'],'record_count':len(rows),'expected_count':len(case['expected_records']),'frozen_field_values_match':values_match,'unresolved_field_names':missing,'field_mapping':mapping,'actual_records':rows,'view':compiled['plan']['view'],'excluded_record_ids':compiled['excluded_record_ids'],'frozen_view_mapping_match':all(compiled['plan']['view'].get(k)==v for k,v in case['expected_view'].items()) if case.get('expected_view') else None}
        report['interpretation']=proposal.get('interpretation') if proposal else None
    reports.append(report)
pairs=[]
for case in protocol['cases']:
    pair=[r for r in reports if r['case']==case['id']]
    if len(pair)!=2:continue
    a,b=[args.workspace/'source-jobs'/r['job_id'] for r in pair]
    checks={}
    for filename in ['source-manifest.json','source-packet.json','harness-hashes.json','model-info.json']:
        left,right=read(a,filename),read(b,filename);checks[filename]=None if left is None or right is None else left==right
    left,right=read(a,'model-0.json'),read(b,'model-0.json')
    checks['first_request_messages']=left['request']['messages']==right['request']['messages'] if left and right else None
    changed=sorted(k for k in set(left['request'])|set(right['request']) if left['request'].get(k)!=right['request'].get(k)) if left and right else []
    pairs.append({'case':case['id'],'input_matches':checks,'changed_first_request_fields':changed})
output={'scope':protocol['scope'],'attempts':reports,'paired_inputs':pairs,'human_acceptance':False,'builds_confirmed':0}
args.output.write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps([{k:r[k] for k in ('case','profile','status','model_calls','elapsed_seconds')} for r in reports],indent=2))
